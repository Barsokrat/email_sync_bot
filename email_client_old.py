import asyncio
import logging
import imaplib
import email
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from email.header import decode_header
import ssl

logger = logging.getLogger(__name__)

class EmailClient:
    def __init__(self, config):
        self.config = config
        self.imap = None
        self.is_connected = False

    async def connect(self):
        try:
            loop = asyncio.get_event_loop()

            # Создаем SSL контекст
            context = ssl.create_default_context()

            # Подключаемся к IMAP серверу в отдельном потоке
            self.imap = await loop.run_in_executor(
                None,
                lambda: imaplib.IMAP4_SSL(self.config.email_server, self.config.email_port, ssl_context=context)
            )

            # Авторизуемся
            await loop.run_in_executor(
                None,
                self.imap.login,
                self.config.email_address,
                self.config.email_password
            )

            # Выбираем папку INBOX
            await loop.run_in_executor(None, self.imap.select, 'INBOX')

            self.is_connected = True
            logger.info(f"Подключение к {self.config.email_server} успешно")

        except Exception as e:
            logger.error(f"Ошибка подключения к почтовому серверу: {e}")
            self.is_connected = False
            raise

    async def disconnect(self):
        if self.imap and self.is_connected:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.imap.logout)
                self.is_connected = False
                logger.info("Отключение от почтового сервера")
            except Exception as e:
                logger.error(f"Ошибка при отключении: {e}")

    async def get_new_emails(self, since: Optional[datetime] = None) -> List[Dict]:
        if not self.is_connected:
            logger.error("Нет подключения к почтовому серверу")
            return []

        try:
            loop = asyncio.get_event_loop()

            # Формируем поисковый запрос
            if since:
                # Ищем письма с определенной даты
                date_str = since.strftime("%d-%b-%Y")
                search_criteria = f'(UNSEEN SINCE "{date_str}")'
            else:
                # Ищем только непрочитанные письма
                search_criteria = '(UNSEEN)'

            # Поиск писем
            result, message_numbers = await loop.run_in_executor(
                None,
                self.imap.search,
                None,
                search_criteria
            )

            if result != 'OK':
                logger.error("Ошибка поиска писем")
                return []

            message_ids = message_numbers[0].split()

            # Ограничиваем количество писем за раз
            # Берем самые новые письма
            message_ids = message_ids[-self.config.max_emails_per_batch:]

            emails = []
            for msg_id in message_ids:
                email_data = await self._fetch_email(msg_id)
                if email_data:
                    email_data['chat_id'] = self.config.telegram_chat_id
                    emails.append(email_data)

            logger.info(f"Найдено {len(emails)} новых писем")
            return emails

        except Exception as e:
            logger.error(f"Ошибка получения писем: {e}")
            return []

    async def _fetch_email(self, msg_id: bytes) -> Optional[Dict]:
        try:
            loop = asyncio.get_event_loop()

            # Получаем письмо
            result, msg_data = await loop.run_in_executor(
                None,
                self.imap.fetch,
                msg_id,
                '(RFC822)'
            )

            if result != 'OK':
                return None

            # Парсим письмо
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)

            # Извлекаем информацию
            subject = self._decode_header(email_message.get('Subject', 'Без темы'))
            sender = self._decode_header(email_message.get('From', 'Неизвестный отправитель'))
            date_str = email_message.get('Date', '')

            # Парсим дату
            try:
                email_date = email.utils.parsedate_to_datetime(date_str)
            except:
                email_date = datetime.now()

            # Получаем превью текста письма
            preview = await self._extract_preview(email_message)

            return {
                'subject': subject,
                'sender': sender,
                'date': email_date.strftime('%d.%m.%Y %H:%M'),
                'preview': preview,
                'message_id': msg_id.decode()
            }

        except Exception as e:
            logger.error(f"Ошибка обработки письма {msg_id}: {e}")
            return None

    async def _extract_preview(self, email_message, max_length: int = 200) -> str:
        try:
            preview = ""

            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        charset = part.get_content_charset() or 'utf-8'
                        text = part.get_payload(decode=True).decode(charset, errors='ignore')
                        preview = text[:max_length]
                        break
            else:
                charset = email_message.get_content_charset() or 'utf-8'
                text = email_message.get_payload(decode=True).decode(charset, errors='ignore')
                preview = text[:max_length]

            # Очищаем текст от лишних символов
            preview = ' '.join(preview.split())
            if len(preview) >= max_length:
                preview += "..."

            return preview

        except Exception as e:
            logger.error(f"Ошибка извлечения превью: {e}")
            return "Не удалось извлечь текст письма"

    def _decode_header(self, header_value: str) -> str:
        try:
            if not header_value:
                return ""

            decoded_parts = decode_header(header_value)
            decoded_string = ""

            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding, errors='ignore')
                    else:
                        decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += str(part)

            return decoded_string.strip()

        except Exception as e:
            logger.error(f"Ошибка декодирования заголовка: {e}")
            return str(header_value)

    async def test_connection(self) -> bool:
        try:
            await self.connect()
            await self.disconnect()
            return True
        except:
            return False