# 📧 Email Sync Bot - Инструкция по настройке

## Что нужно для настройки

### 1. Создать Telegram бота (5 минут)
1. Найти @BotFather в Telegram
2. `/newbot` → название → username
3. Скопировать **токен бота**
4. Отправить любое сообщение новому боту

### 2. Настроить Gmail (5 минут)
1. [Google Account](https://myaccount.google.com/security) → включить 2FA
2. Security → App passwords → Mail → Generate
3. Скопировать **16-символьный пароль**

### 3. Создать AWS сервер (5 минут)
1. AWS Console → EC2 → Launch Instance
2. Amazon Linux 2023, t2.micro (бесплатный)
3. Создать Key Pair, скачать **.pem файл**
4. Security Group: разрешить SSH (порт 22)
5. Скопировать **Public IP**

### 4. Развернуть бота (5 минут)
```bash
# Скачать проект
git clone <этот-репозиторий>
cd email_sync_bot

# Обновить путь к ключу в deploy.sh
nano deploy.sh  # изменить AWS_KEY_PATH

# Развернуть
./deploy.sh YOUR_SERVER_IP
```

### 5. Настроить на сервере (5 минут)
```bash
# Подключиться
ssh -i your-key.pem ec2-user@YOUR_SERVER_IP
cd email_sync_bot

# Получить Chat ID (вставить свой токен)
source venv/bin/activate
python3 -c "
import asyncio, aiohttp
async def get_chat_id():
    token = 'ВАШ_TELEGRAM_TOKEN'  # ← ЗАМЕНИТЬ
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://api.telegram.org/bot{token}/getUpdates') as resp:
            data = await resp.json()
            if data['result']:
                print(f'Chat ID: {data[\"result\"][-1][\"message\"][\"chat\"][\"id\"]}')
asyncio.run(get_chat_id())
"

# Настроить конфиг
nano .env
```

**Заполнить .env:**
```env
TELEGRAM_TOKEN=123456789:ABCdefGhIJklmNOpqrStUVwxyz  # из шага 1
TELEGRAM_CHAT_ID=123456789                           # из команды выше
EMAIL_ADDRESS=your-email@gmail.com                   # ваш Gmail
EMAIL_PASSWORD=abcd efgh ijkl mnop                   # из шага 2
EMAIL_SERVER=imap.gmail.com
EMAIL_PORT=993
CHECK_INTERVAL=30
MAX_EMAILS_PER_BATCH=20
```

**Запустить:**
```bash
./start.sh
```

## Готово! 🎉

Бот будет:
- ✅ Проверять почту каждые 30 секунд
- ✅ Отправлять уведомления о новых письмах в Telegram
- ✅ Работать 24/7 с автозапуском
- ✅ Не присылать дубликаты

## Управление
```bash
./start.sh    # запустить
./stop.sh     # остановить
./restart.sh  # перезапустить
./logs.sh     # смотреть логи
./status.sh   # статус
```

## Для других почтовых провайдеров

**Yandex:**
```env
EMAIL_SERVER=imap.yandex.ru
EMAIL_PORT=993
```

**Mail.ru:**
```env
EMAIL_SERVER=imap.mail.ru
EMAIL_PORT=993
```

**Outlook:**
```env
EMAIL_SERVER=outlook.office365.com
EMAIL_PORT=993
```

## Troubleshooting

**"Permission denied" при подключении к серверу:**
```bash
chmod 400 your-key.pem
```

**"Application-specific password required":**
- Нужен App Password, а не обычный пароль Gmail

**Не приходят уведомления:**
- Проверьте, что отправили сообщение боту
- Проверьте Chat ID командой выше
- Посмотрите логи: `./logs.sh`