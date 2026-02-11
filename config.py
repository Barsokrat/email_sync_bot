import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    telegram_token: str
    telegram_chat_id: str
    email_address: str
    email_password: str
    email_server: str
    email_port: int
    check_interval: int
    max_emails_per_batch: int

    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.email_address = os.getenv('EMAIL_ADDRESS')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.email_server = os.getenv('EMAIL_SERVER', 'imap.gmail.com')
        self.email_port = int(os.getenv('EMAIL_PORT', '993'))
        self.check_interval = int(os.getenv('CHECK_INTERVAL', '30'))
        self.max_emails_per_batch = int(os.getenv('MAX_EMAILS_PER_BATCH', '5'))

        self._validate()

    def _validate(self):
        if not self.telegram_token:
            raise ValueError("TELEGRAM_TOKEN не установлен")
        if not self.telegram_chat_id:
            raise ValueError("TELEGRAM_CHAT_ID не установлен")
        if not self.email_address:
            raise ValueError("EMAIL_ADDRESS не установлен")
        if not self.email_password:
            raise ValueError("EMAIL_PASSWORD не установлен")