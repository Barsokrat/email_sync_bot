import asyncio
import logging
from typing import List, Dict
from datetime import datetime
import os
from dotenv import load_dotenv

from telegram_bot import TelegramBot
from email_client import EmailClient
from config import Config
from database import EmailDatabase

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmailSyncBot:
    def __init__(self):
        self.config = Config()
        self.telegram_bot = TelegramBot(self.config.telegram_token)
        self.email_client = EmailClient(self.config)
        self.database = EmailDatabase()
        self.is_running = False
        self.last_check = None
        self.start_time = None
        self.emails_processed = 0
        self.last_update_offset = 0
        self.sent_ids_file = 'sent_message_ids.txt'
        self.sent_message_ids = self._load_sent_ids()  # Загружаем из файла

    async def start(self):
        logger.info("Запускаю Email Sync Bot...")
        self.is_running = True
        self.start_time = datetime.now()

        await self.telegram_bot.start()
        await self.email_client.connect()

        # Запускаем два параллельных процесса
        await asyncio.gather(
            self.email_check_loop(),
            self.command_handler_loop()
        )

    async def email_check_loop(self):
        """Цикл проверки новых писем"""
        while self.is_running:
            try:
                # Переподключаемся каждую проверку (каждые 30 сек) чтобы видеть новые письма сразу
                logger.info("Переподключение к IMAP для обновления списка писем...")
                await self.email_client.disconnect()
                await self.email_client.connect()

                await self.check_new_emails()
                await asyncio.sleep(self.config.check_interval)
            except Exception as e:
                logger.error(f"Ошибка при проверке почты: {e}")
                await asyncio.sleep(60)

    async def command_handler_loop(self):
        """Цикл обработки команд от пользователей"""
        while self.is_running:
            try:
                await self.process_commands()
                await asyncio.sleep(2)  # Проверяем команды каждые 2 секунды
            except Exception as e:
                logger.error(f"Ошибка при обработке команд: {e}")
                await asyncio.sleep(5)

    async def process_commands(self):
        """Обработка команд от пользователей"""
        try:
            url = f"https://api.telegram.org/bot{self.config.telegram_token}/getUpdates"
            params = {"offset": self.last_update_offset + 1, "timeout": 1}

            async with self.telegram_bot.session.get(url, params=params) as response:
                if response.status != 200:
                    return

                data = await response.json()
                updates = data.get('result', [])

                for update in updates:
                    self.last_update_offset = update['update_id']

                    if 'message' not in update:
                        continue

                    message = update['message']
                    chat_id = str(message['chat']['id'])
                    text = message.get('text', '')
                    username = message.get('from', {}).get('username')
                    first_name = message.get('from', {}).get('first_name')
                    last_name = message.get('from', {}).get('last_name')

                    # Регистрация нового пользователя при /start
                    if text == '/start' or text == '/start@email_sync_wwl_bot':
                        self.database.add_user(chat_id, username, first_name, last_name)
                        await self.send_welcome(chat_id, first_name)
                        continue

                    if text == '/status' or text == '/status@email_sync_wwl_bot':
                        await self.send_status(chat_id)
                    elif text == '/health' or text == '/health@email_sync_wwl_bot':
                        await self.send_health(chat_id)
                    elif text == '/help' or text == '/help@email_sync_wwl_bot':
                        await self.send_help(chat_id)
                    elif text == '/users' or text == '/users@email_sync_wwl_bot':
                        # Только для админа
                        if chat_id == self.config.telegram_chat_id:
                            await self.send_users_list(chat_id)

        except Exception as e:
            logger.debug(f"Ошибка обработки команд: {e}")

    async def send_welcome(self, chat_id: str, first_name: str = None):
        """Приветствие нового пользователя"""
        name = first_name or "друг"
        welcome_text = f"""
👋 Привет, {name}!

Ты подписался на уведомления о новых письмах от WWL.

📬 Теперь ты будешь получать все новые письма автоматически!

Доступные команды:
/help - Справка по командам
/status - Статус бота
        """.strip()

        await self.telegram_bot.send_message(chat_id, welcome_text)
        logger.info(f"Новый пользователь зарегистрирован: {first_name} ({chat_id})")

    async def send_users_list(self, chat_id: str):
        """Отправляет список пользователей (только для админа)"""
        users_count = self.database.get_users_count()
        users_text = f"""
👥 <b>Активных пользователей:</b> {users_count}

Все пользователи получают уведомления о новых письмах.
        """.strip()

        await self.telegram_bot.send_message(chat_id, users_text)
        logger.info(f"Отправлен список пользователей в чат {chat_id}")

    async def send_status(self, chat_id: str):
        """Отправляет статус бота"""
        uptime = datetime.now() - self.start_time if self.start_time else None
        uptime_str = str(uptime).split('.')[0] if uptime else "неизвестно"

        last_check_str = self.last_check.strftime('%d.%m.%Y %H:%M:%S') if self.last_check else "ещё не было"

        users_count = self.database.get_users_count()

        status_text = f"""
🤖 <b>Статус Email Sync Bot</b>

✅ Бот работает
⏱ Uptime: {uptime_str}
📧 Обработано писем: {self.emails_processed}
👥 Активных пользователей: {users_count}
🔍 Последняя проверка: {last_check_str}
⚙️ Интервал проверки: {self.config.check_interval} сек

📬 Email: {self.config.email_address}
🔗 IMAP сервер: {self.config.email_server}
{"✅ Подключено" if self.email_client.is_connected else "❌ Не подключено"}
        """.strip()

        await self.telegram_bot.send_message(chat_id, status_text)
        logger.info(f"Отправлен статус в чат {chat_id}")

    async def send_health(self, chat_id: str):
        """Отправляет состояние здоровья бота"""
        try:
            # Проверяем IMAP
            imap_status = "✅" if self.email_client.is_connected else "❌"

            # Проверяем Telegram
            telegram_status = "✅" if self.telegram_bot.session and not self.telegram_bot.session.closed else "❌"

            health_text = f"""
🏥 <b>Health Check</b>

{imap_status} IMAP Connection
{telegram_status} Telegram API
✅ Bot Process

<i>Всё работает нормально!</i>
            """.strip()

            await self.telegram_bot.send_message(chat_id, health_text)
            logger.info(f"Отправлен health check в чат {chat_id}")

        except Exception as e:
            logger.error(f"Ошибка при отправке health: {e}")

    async def send_help(self, chat_id: str):
        """Отправляет справку по командам"""
        help_text = """
📖 <b>Доступные команды:</b>

/status - Показать статус бота и статистику
/health - Проверить работоспособность
/help - Показать эту справку

Бот автоматически отправляет уведомления о новых письмах.
        """.strip()

        await self.telegram_bot.send_message(chat_id, help_text)

    def _load_sent_ids(self) -> set:
        """Загружает ID отправленных писем из файла"""
        try:
            if os.path.exists(self.sent_ids_file):
                with open(self.sent_ids_file, 'r') as f:
                    ids = set(line.strip() for line in f if line.strip())
                logger.info(f"Загружено {len(ids)} ID отправленных писем")
                return ids
        except Exception as e:
            logger.error(f"Ошибка загрузки sent_ids: {e}")
        return set()

    def _save_sent_ids(self):
        """Сохраняет ID отправленных писем в файл"""
        try:
            # Сохраняем только последние 1000
            ids_to_save = list(self.sent_message_ids)[-1000:]
            with open(self.sent_ids_file, 'w') as f:
                f.write('\n'.join(ids_to_save))
        except Exception as e:
            logger.error(f"Ошибка сохранения sent_ids: {e}")

    async def check_new_emails(self):
        try:
            all_emails = await self.email_client.get_new_emails(since=self.last_check)

            # Фильтруем только те, которые ещё не отправляли
            new_emails = []
            for email in all_emails:
                msg_id = email.get('message_id')
                if msg_id and msg_id not in self.sent_message_ids:
                    new_emails.append(email)
                    self.sent_message_ids.add(msg_id)

            # Отправляем только новые всем пользователям
            active_users = self.database.get_active_users()

            for email in new_emails:
                # Рассылаем каждое письмо всем активным пользователям
                sent_count = 0
                for chat_id in active_users:
                    try:
                        email['chat_id'] = chat_id
                        await self.telegram_bot.send_email_notification(email)
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка отправки пользователю {chat_id}: {e}")

                logger.info(f"Отправлено уведомление о письме от {email['sender']} для {sent_count} пользователей")
                self.emails_processed += 1

            if new_emails:
                self.last_check = datetime.now()
                logger.info(f"Обработано {len(new_emails)} новых писем из {len(all_emails)}")
                # Сохраняем после каждой обработки
                self._save_sent_ids()

            # Ограничиваем размер set (храним только последние 1000)
            if len(self.sent_message_ids) > 1000:
                self.sent_message_ids = set(list(self.sent_message_ids)[-1000:])
                self._save_sent_ids()

        except Exception as e:
            logger.error(f"Ошибка при получении писем: {e}")

    async def stop(self):
        self.is_running = False
        await self.telegram_bot.stop()
        await self.email_client.disconnect()
        logger.info("Email Sync Bot остановлен")

async def main():
    bot = EmailSyncBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки...")
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())