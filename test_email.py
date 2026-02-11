import asyncio
import imaplib
import ssl
from datetime import datetime

async def test_imap():
    try:
        # Подключение к Gmail
        context = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL('imap.gmail.com', 993, ssl_context=context)
        imap.login('ddwdatalist@gmail.com', 'atyx yfxf qkyx bcxj')
        imap.select('INBOX')
        
        print("✅ Подключение к Gmail успешно")
        
        # Проверяем все непрочитанные письма
        result, messages = imap.search(None, 'UNSEEN')
        print(f"🔍 Непрочитанные письма: {len(messages[0].split()) if messages[0] else 0}")
        
        # Проверяем письма за последний час
        from datetime import datetime, timedelta
        since = datetime.now() - timedelta(hours=1)
        date_str = since.strftime("%d-%b-%Y")
        result, messages = imap.search(None, f'SINCE "{date_str}"')
        print(f"📅 Письма за сегодня: {len(messages[0].split()) if messages[0] else 0}")
        
        # Проверяем от конкретного отправителя
        result, messages = imap.search(None, 'FROM "v9091153210@gmail.com"')
        print(f"👤 Письма от v9091153210@gmail.com: {len(messages[0].split()) if messages[0] else 0}")
        
        # Последние 5 писем
        result, messages = imap.search(None, 'ALL')
        all_messages = messages[0].split()
        if all_messages:
            print(f"📧 Всего писем в INBOX: {len(all_messages)}")
            # Получаем последние 3 письма
            for i, msg_id in enumerate(all_messages[-3:]):
                result, msg_data = imap.fetch(msg_id, '(RFC822.HEADER)')
                if result == 'OK':
                    import email
                    header = email.message_from_bytes(msg_data[0][1])
                    subject = header.get('Subject', 'Без темы')
                    sender = header.get('From', 'Неизвестный')
                    date = header.get('Date', '')
                    print(f"  {i+1}. От: {sender}")
                    print(f"     Тема: {subject}")
                    print(f"     Дата: {date}")
        
        imap.logout()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

asyncio.run(test_imap())
