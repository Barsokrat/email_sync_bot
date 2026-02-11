import imaplib
import ssl

def mark_all_read():
    try:
        context = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL('imap.gmail.com', 993, ssl_context=context)
        imap.login('ddwdatalist@gmail.com', 'atyx yfxf qkyx bcxj')
        imap.select('INBOX')
        
        # Найти все непрочитанные письма
        result, messages = imap.search(None, 'UNSEEN')
        
        if messages[0]:
            message_ids = messages[0].split()
            print(f"Найдено {len(message_ids)} непрочитанных писем")
            
            # Пользователь должен подтвердить
            confirm = input(f"Отметить {len(message_ids)} писем как прочитанные? (y/N): ")
            
            if confirm.lower() == 'y':
                # Отмечаем все как прочитанные
                for msg_id in message_ids:
                    imap.store(msg_id, '+FLAGS', '\\Seen')
                
                imap.expunge()
                print(f"✅ Отмечено {len(message_ids)} писем как прочитанные")
                print("Теперь бот будет видеть только новые письма!")
            else:
                print("Операция отменена")
        else:
            print("Непрочитанных писем не найдено")
        
        imap.logout()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

mark_all_read()
