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
        if self.imap:
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(None, self.imap.logout)
                logger.info("Отключение от почтового сервера")
            except Exception as e:
                logger.error(f"Ошибка при отключении: {e}")
                # Принудительно закрываем сокет: иначе "битое" соединение
                # (напр. SSL BAD_LENGTH) остаётся висеть на стороне Gmail и
                # накапливается до "Too many simultaneous connections".
                try:
                    await loop.run_in_executor(None, self.imap.shutdown)
                except Exception:
                    pass
            finally:
                self.is_connected = False
                self.imap = None

    async def get_new_emails(self, since: Optional[datetime] = None, is_sent=None) -> List[Dict]:
        if not self.is_connected:
            logger.error("Нет подключения к почтовому серверу")
            return []

        try:
            loop = asyncio.get_event_loop()

            # Формируем поисковый запрос
            if since:
                # Ищем письма с определенной даты (независимо от статуса прочитанности)
                date_str = since.strftime("%d-%b-%Y")
                search_criteria = f'(SINCE "{date_str}")'
            else:
                # Ищем письма за сегодня
                from datetime import datetime
                today_str = datetime.now().strftime("%d-%b-%Y")
                search_criteria = f'(SINCE "{today_str}")'

            # Обновляем состояние ящика без переподключения: NOOP заставляет
            # сервер прислать актуальные данные (новые письма видны сразу).
            # Так мы держим ОДНО постоянное соединение вместо переподключения
            # каждые 30 сек, которое накапливало висящие соединения на Gmail.
            try:
                await loop.run_in_executor(None, self.imap.noop)
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError) as e:
                logger.warning(f"IMAP соединение потеряно (noop): {e}. Переподключаюсь...")
                await self.disconnect()
                await self.connect()

            # Поиск писем с автоматическим переподключением
            try:
                result, message_numbers = await loop.run_in_executor(
                    None,
                    self.imap.search,
                    None,
                    search_criteria
                )
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError) as e:
                logger.warning(f"IMAP соединение потеряно: {e}. Переподключаюсь...")
                await self.disconnect()
                await self.connect()
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

            # Если есть дата с которой ищем - берём все письма
            # Иначе ограничиваем последними N письмами (для первого запуска)
            if not since:
                message_ids = message_ids[-self.config.max_emails_per_batch:]
                logger.info(f"Первый запуск: берём последние {len(message_ids)} писем")

            # Дедуп ДО тяжёлого фетча: батчем получаем только заголовок Message-ID
            # (лёгкий) и через колбэк is_sent отсеиваем уже отправленные письма.
            # Полный RFC822 тянем ТОЛЬКО для новых — иначе фетч сотен писем за день
            # каждые 30 сек рвал соединение (Broken pipe / System Error).
            to_fetch = message_ids
            if is_sent is not None and message_ids:
                id_map = await self._fetch_message_ids(message_ids)
                to_fetch = [seq for seq in message_ids
                            if not (id_map.get(seq) and is_sent(id_map[seq]))]

            emails = []
            for msg_id in to_fetch:
                email_data = await self._fetch_email(msg_id)
                if email_data:
                    emails.append(email_data)

            logger.info(f"Найдено {len(message_ids)} писем за период, новых к отправке: {len(emails)}")
            return emails

        except Exception as e:
            logger.error(f"Ошибка получения писем: {e}")
            # Пытаемся переподключиться при любой ошибке
            try:
                logger.info("Пытаюсь переподключиться после ошибки...")
                await self.disconnect()
                await self.connect()
            except Exception as reconnect_error:
                logger.error(f"Не удалось переподключиться: {reconnect_error}")
            return []

    async def _fetch_message_ids(self, seq_ids: list) -> dict:
        """Батч-фетч ТОЛЬКО заголовка Message-ID (без тела письма).

        Возвращает {seq(bytes): message_id(str)}. Используется для дедупликации
        до тяжёлого RFC822-фетча. BODY.PEEK не выставляет флаг \\Seen.
        """
        loop = asyncio.get_event_loop()
        result = {}
        CH = 100
        for i in range(0, len(seq_ids), CH):
            chunk = seq_ids[i:i + CH]
            try:
                typ, data = await loop.run_in_executor(
                    None,
                    self.imap.fetch,
                    b','.join(chunk),
                    '(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])'
                )
            except (imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError) as e:
                logger.warning(f"Ошибка батч-фетча Message-ID: {e}")
                continue
            for item in data:
                if isinstance(item, tuple) and len(item) >= 2 and item[1]:
                    try:
                        seq = item[0].split(b' ', 1)[0]
                        mid = email.message_from_bytes(item[1]).get('Message-ID')
                        if mid:
                            result[seq] = mid.strip()
                    except Exception:
                        pass
        return result

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

            # Получаем уникальный Message-ID из заголовков (не путать с IMAP message ID)
            real_message_id = email_message.get('Message-ID', None)
            if not real_message_id:
                # Если нет Message-ID, создаем уникальный на основе темы+даты+отправителя
                real_message_id = f"{subject}:{date_str}:{sender}"

            # Парсим дату
            try:
                email_date = email.utils.parsedate_to_datetime(date_str)
                # Получаем название часового пояса
                tz_name = email_date.strftime('%Z') if email_date.tzinfo else 'UTC'
                date_formatted = f"{email_date.strftime('%d.%m.%Y %H:%M')} ({tz_name})"
            except:
                email_date = datetime.now()
                date_formatted = f"{email_date.strftime('%d.%m.%Y %H:%M')} (UTC)"

            # Получаем превью текста письма
            preview = await self._extract_preview(email_message)

            return {
                'subject': subject,
                'sender': sender,
                'date': date_formatted,
                'preview': preview,
                'message_id': real_message_id
            }

        except Exception as e:
            logger.error(f"Ошибка обработки письма {msg_id}: {e}")
            return None

    async def _extract_preview(self, email_message, max_length: int = 2000) -> str:
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