import asyncio
import logging
from typing import Dict, List
import aiohttp
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session = None

    async def start(self):
        self.session = aiohttp.ClientSession()
        logger.info("Telegram Bot запущен")

    async def stop(self):
        if self.session:
            await self.session.close()
        logger.info("Telegram Bot остановлен")

    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML"):
        if not self.session:
            raise RuntimeError("Telegram Bot не запущен")

        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }

        try:
            async with self.session.post(url, json=data) as response:
                if response.status == 200:
                    logger.debug("Сообщение отправлено успешно")
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка отправки сообщения: {response.status} - {error_text}")
                    raise Exception(f"Telegram API error: {response.status}")

        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            raise

    async def send_email_notification(self, email: Dict):
        chat_id = email.get('chat_id')
        if not chat_id:
            logger.error("Не указан chat_id для отправки уведомления")
            return

        subject = email.get('subject', 'Без темы')
        date = email.get('date', datetime.now())
        preview = email.get('preview', '')

        # Экранируем HTML спецсимволы
        subject = self._escape_html(subject)
        preview = self._escape_html(preview)

        # Заменяем длинные URL на кликабельное слово "ссылка"
        preview = self._replace_urls_with_links(preview)

        text = f"""
📧 <b>{subject}</b>

{date}

{preview}
        """.strip()

        try:
            await self.send_message(chat_id, text)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление о письме: {e}")

    def _replace_urls_with_links(self, text: str) -> str:
        """Заменяет длинные URL на кликабельное слово 'link'"""
        if not text:
            return ""

        # Паттерн для поиска URL
        url_pattern = r'\bhttps?://[^\s<>"\']+[^\s<>"\'.,;!?)]'

        def replace_url(match):
            url = match.group(0)
            # Экранируем спецсимволы в URL для HTML
            escaped_url = self._escape_html(url)
            return f'<a href="{escaped_url}">link</a>'

        # Заменяем все найденные URL
        result = re.sub(url_pattern, replace_url, text)
        return result

    def _escape_html(self, text: str) -> str:
        """Экранирует HTML спецсимволы для Telegram"""
        if not text:
            return ""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))

    async def get_chat_id(self) -> str:
        if not self.session:
            raise RuntimeError("Telegram Bot не запущен")

        url = f"{self.base_url}/getUpdates"

        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    updates = data.get('result', [])
                    if updates:
                        chat_id = updates[-1]['message']['chat']['id']
                        logger.info(f"Найден chat_id: {chat_id}")
                        return str(chat_id)
                    else:
                        logger.warning("Нет сообщений для определения chat_id")
                        return None
        except Exception as e:
            logger.error(f"Ошибка получения chat_id: {e}")
            return None

    async def test_connection(self) -> bool:
        if not self.session:
            await self.start()

        url = f"{self.base_url}/getMe"

        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    bot_info = await response.json()
                    logger.info(f"Подключение к Telegram успешно. Bot: {bot_info['result']['first_name']}")
                    return True
                else:
                    logger.error(f"Ошибка подключения к Telegram: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Ошибка тестирования подключения: {e}")
            return False