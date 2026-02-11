import asyncio
import aiohttp
from config import Config

async def get_chat_id():
    try:
        config = Config()
        bot_token = config.telegram_token
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    updates = data.get('result', [])
                    if updates:
                        chat_id = updates[-1]['message']['chat']['id']
                        print(f"Ваш chat_id: {chat_id}")
                        
                        # Обновляем .env файл
                        with open('.env', 'r') as f:
                            content = f.read()
                        
                        content = content.replace('TELEGRAM_CHAT_ID=your_chat_id_here', f'TELEGRAM_CHAT_ID={chat_id}')
                        
                        with open('.env', 'w') as f:
                            f.write(content)
                        
                        print("✅ .env файл обновлен с вашим chat_id!")
                        print("Теперь настройте EMAIL_ADDRESS и EMAIL_PASSWORD в файле .env")
                    else:
                        print("❌ Нет сообщений. Отправьте любое сообщение боту @email_sync_wwl_bot и запустите скрипт снова.")
                else:
                    print(f"❌ Ошибка API: {response.status}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(get_chat_id())
