import asyncio
import logging
from logging.handlers import RotatingFileHandler
from typing import List, Dict
from datetime import datetime
import os
from dotenv import load_dotenv

from telegram_bot import TelegramBot
from email_client import EmailClient
from config import Config
from database import EmailDatabase

load_dotenv()

# Настройка ротации логов: макс 10MB на файл, хранить 5 резервных копий
log_handler = RotatingFileHandler(
    'bot.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Консольный вывод
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[log_handler, console_handler]
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
        # Дедупликация отправленных писем ведётся персистентно в SQLite
        # (таблица sent_emails), см. database.is_email_sent / mark_email_sent.

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
        """Цикл проверки новых писем.

        Держим ОДНО постоянное IMAP-соединение (открыто в start()). Обновление
        списка писем делает NOOP внутри get_new_emails, а переподключение
        происходит только при ошибке. Раньше здесь был disconnect()+connect()
        на каждой итерации — из-за "битых" закрытий соединения накапливались
        на Gmail до "Too many simultaneous connections", и бот слеп к почте.
        """
        while self.is_running:
            try:
                await self.check_new_emails()
                await asyncio.sleep(self.config.check_interval)
            except Exception as e:
                logger.error(f"Ошибка при проверке почты: {e}")
                # При сбое пересоздаём соединение перед следующей попыткой
                try:
                    await self.email_client.disconnect()
                    await self.email_client.connect()
                except Exception as reconnect_error:
                    logger.error(f"Не удалось переподключиться: {reconnect_error}")
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

    async def check_new_emails(self):
        try:
            # Дедуп идёт через SQLite по Message-ID — персистентно, без лимита
            # и переживает перезапуск бота (раньше был deque(maxlen=1000),
            # который "забывал" старые ID при большом суточном объёме писем
            # и рассылал одни и те же регистрации повторно).
            # is_sent передаём в get_new_emails, чтобы отсеять уже отправленные
            # письма ДО тяжёлого RFC822-фетча (сотни писем/день × каждые 30 сек).
            all_emails = await self.email_client.get_new_emails(
                since=self.last_check,
                is_sent=lambda mid: self.database.is_email_sent({'message_id': mid}),
            )

            # Перепроверяем на всякий случай (письма без Message-ID и т.п.)
            new_emails = [e for e in all_emails if not self.database.is_email_sent(e)]

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

                # ТОЛЬКО ПОСЛЕ отправки помечаем письмо как отправленное в БД
                self.database.mark_email_sent(email)

                logger.info(f"Отправлено уведомление о письме от {email['sender']} для {sent_count} пользователей")
                self.emails_processed += 1

            if new_emails:
                self.last_check = datetime.now()
                logger.info(f"Обработано {len(new_emails)} новых писем из {len(all_emails)}")

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
