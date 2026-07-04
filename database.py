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
        """Инициализация базы данных с таблицей пользователей"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Таблица отправленных писем
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
                
                # Таблица пользователей бота
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS bot_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT UNIQUE NOT NULL,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                """)
                
                conn.commit()
                logger.info("База данных инициализирована с поддержкой многопользователности")
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
    
    def get_email_hash(self, email_data: dict) -> str:
        """Ключ дедупликации письма.

        Message-ID уникален и стабилен между проверками — используем его напрямую,
        чтобы дедуп не зависел от объёма писем (в отличие от старого deque(maxlen=1000)).
        Fallback на md5(sender+subject) только для писем без Message-ID.
        """
        message_id = (email_data.get('message_id') or '').strip()
        if message_id:
            return message_id
        hash_string = f"{email_data.get('sender', '')}{email_data.get('subject', '')}"
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
                    email_data.get('subject', '')[:200],
                    email_data.get('sender', '')[:200],
                    email_data.get('message_id', '')
                ))
                conn.commit()
                logger.debug(f"Письмо отмечено как отправленное: {email_data.get('subject', '')[:50]}...")
        except Exception as e:
            logger.error(f"Ошибка записи в базу данных: {e}")
    
    def add_user(self, chat_id: str, username: str = None, first_name: str = None, last_name: str = None) -> bool:
        """Добавляет нового пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO bot_users 
                    (chat_id, username, first_name, last_name, is_active)
                    VALUES (?, ?, ?, ?, 1)
                """, (chat_id, username, first_name, last_name))
                conn.commit()
                logger.info(f"Пользователь добавлен: {first_name or username or chat_id}")
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return False
    
    def get_active_users(self) -> List[str]:
        """Возвращает список активных chat_id"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT chat_id FROM bot_users WHERE is_active = 1")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения пользователей: {e}")
            return []
    
    def get_users_count(self) -> int:
        """Возвращает количество активных пользователей"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM bot_users WHERE is_active = 1")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Ошибка подсчета пользователей: {e}")
            return 0
    
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
        """Возвращает статистику по отправленным письмам и пользователям"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Письма
                cursor.execute("SELECT COUNT(*) FROM sent_emails")
                total_emails = cursor.fetchone()[0]
                
                yesterday = datetime.now() - timedelta(hours=24)
                cursor.execute("SELECT COUNT(*) FROM sent_emails WHERE sent_at > ?", (yesterday,))
                emails_24h = cursor.fetchone()[0]
                
                # Пользователи
                cursor.execute("SELECT COUNT(*) FROM bot_users WHERE is_active = 1")
                active_users = cursor.fetchone()[0]
                
                return {
                    'total_emails': total_emails,
                    'emails_24h': emails_24h,
                    'active_users': active_users
                }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {'total_emails': 0, 'emails_24h': 0, 'active_users': 0}
