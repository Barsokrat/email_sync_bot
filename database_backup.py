import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List
import hashlib

logger = logging.getLogger(__name__)

class EmailDatabase:
    def __init__(self, db_path: str = "email_bot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sent_emails (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email_hash TEXT UNIQUE NOT NULL,
                        subject TEXT,
                        sender TEXT,
                        sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        message_id TEXT
                    )
                """)
                conn.commit()
                logger.info("База данных инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
    
    def get_email_hash(self, email_data: dict) -> str:
        """Создает уникальный хеш для письма"""
        # Используем комбинацию отправителя, темы и ID сообщения
        hash_string = f"{email_data.get('sender', '')}{email_data.get('subject', '')}{email_data.get('message_id', '')}"
        return hashlib.md5(hash_string.encode()).hexdigest()
    
    def is_email_sent(self, email_data: dict) -> bool:
        """Проверяет, было ли письмо уже отправлено"""
        email_hash = self.get_email_hash(email_data)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM sent_emails WHERE email_hash = ?", (email_hash,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Ошибка проверки письма: {e}")
            return False
    
    def mark_email_sent(self, email_data: dict):
        """Отмечает письмо как отправленное"""
        email_hash = self.get_email_hash(email_data)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO sent_emails 
                    (email_hash, subject, sender, message_id)
                    VALUES (?, ?, ?, ?)
                """, (
                    email_hash,
                    email_data.get('subject', '')[:200],  # Ограничиваем длину
                    email_data.get('sender', '')[:200],
                    email_data.get('message_id', '')
                ))
                conn.commit()
                logger.debug(f"Письмо отмечено как отправленное: {email_data.get('subject', '')[:50]}...")
        except Exception as e:
            logger.error(f"Ошибка записи в базу данных: {e}")
    
    def cleanup_old_records(self, days: int = 7):
        """Удаляет старые записи из базы данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cutoff_date = datetime.now() - timedelta(days=days)
                cursor.execute("DELETE FROM sent_emails WHERE sent_at < ?", (cutoff_date,))
                deleted = cursor.rowcount
                conn.commit()
                if deleted > 0:
                    logger.info(f"Удалено {deleted} старых записей из базы данных")
        except Exception as e:
            logger.error(f"Ошибка очистки базы данных: {e}")
    
    def get_stats(self) -> dict:
        """Возвращает статистику по отправленным письмам"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Всего отправлено
                cursor.execute("SELECT COUNT(*) FROM sent_emails")
                total = cursor.fetchone()[0]
                
                # За последние 24 часа
                yesterday = datetime.now() - timedelta(hours=24)
                cursor.execute("SELECT COUNT(*) FROM sent_emails WHERE sent_at > ?", (yesterday,))
                last_24h = cursor.fetchone()[0]
                
                # За последнюю неделю
                week_ago = datetime.now() - timedelta(days=7)
                cursor.execute("SELECT COUNT(*) FROM sent_emails WHERE sent_at > ?", (week_ago,))
                last_week = cursor.fetchone()[0]
                
                return {
                    'total': total,
                    'last_24h': last_24h,
                    'last_week': last_week
                }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {'total': 0, 'last_24h': 0, 'last_week': 0}
