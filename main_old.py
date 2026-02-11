import asyncio
import logging
from typing import List, Dict
from datetime import datetime, timedelta
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

    async def start(self):
        logger.info("Запускаю Email Sync Bot...")
        self.is_running = True

        await self.telegram_bot.start()
        await self.email_client.connect()

        # Очищаем старые записи из базы данных при запуске
        self.database.cleanup_old_records(days=7)

        while self.is_running:
            try:
                await self.check_new_emails()
                await asyncio.sleep(self.config.check_interval)
            except Exception as e:
                logger.error(f"Ошибка при проверке почты: {e}")
                await asyncio.sleep(60)

    async def check_new_emails(self):
        try:
            new_emails = await self.email_client.get_new_emails(since=self.last_check)

            new_count = 0
            for email in new_emails:
                # Проверяем, не отправляли ли мы уже это письмо
                if not self.database.is_email_sent(email):
                    await self.telegram_bot.send_email_notification(email)
                    self.database.mark_email_sent(email)
                    new_count += 1
                    logger.info(f"✅ Новое письмо: {email['subject'][:50]}... от {email['sender']}")
                else:
                    logger.debug(f"🔄 Письмо уже отправлялось: {email['subject'][:30]}...")

            if new_count > 0:
                self.last_check = datetime.now()
                logger.info(f"📧 Отправлено {new_count} новых уведомлений из {len(new_emails)} найденных")
            elif len(new_emails) > 0:
                logger.info(f"🔍 Найдено {len(new_emails)} писем, все уже отправлялись ранее")

            # Показываем статистику каждый час
            current_time = datetime.now()
            if not hasattr(self, 'last_stats_time') or (current_time - self.last_stats_time).seconds > 3600:
                stats = self.database.get_stats()
                logger.info(f"📊 Статистика: всего {stats['total']}, за 24ч {stats['last_24h']}, за неделю {stats['last_week']}")
                self.last_stats_time = current_time

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
