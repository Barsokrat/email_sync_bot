# Email Sync Bot

Telegram бот для синхронизации входящих писем с любого email провайдера.

## Возможности

- Подключение к любому IMAP серверу (Gmail, Yandex, Mail.ru и т.д.)
- Отправка уведомлений о новых письмах в Telegram
- Показ превью письма с темой, отправителем и кратким содержанием
- Настраиваемый интервал проверки почты
- Обработка только непрочитанных писем
- Автоматическое развертывание на AWS EC2
- Systemd сервис для автозапуска и управления

## 🚀 Пошаговая инструкция для новых пользователей

### Шаг 1: Создание Telegram бота

1. **Найдите @BotFather** в Telegram
2. **Отправьте команду** `/newbot`
3. **Введите название** бота (например: "My Email Sync Bot")
4. **Введите username** (например: "my_email_sync_bot")
5. **Скопируйте токен** (например: `123456789:ABCdefGhIJklmNOpqrStUVwxyz`)
6. **Отправьте любое сообщение** вашему новому боту

### Шаг 2: Настройка email (Gmail)

1. **Включите двухфакторную аутентификацию:**
   - Идите в [Google Account Security](https://myaccount.google.com/security)
   - Включите "2-Step Verification"

2. **Создайте App Password:**
   - В том же разделе Security найдите "App passwords"
   - Выберите "Mail" → "Generate"
   - **Скопируйте 16-символьный пароль** (например: `abcd efgh ijkl mnop`)

### Шаг 3: Создание AWS EC2 сервера

1. **Войдите в AWS Console**
2. **Запустите EC2 инстанс:**
   - AMI: Amazon Linux 2023
   - Instance type: t2.micro (бесплатный)
   - **Создайте новую Key Pair** и скачайте .pem файл
   - Security Group: разрешите SSH (порт 22)
3. **Скопируйте Public IP** вашего инстанса

### Шаг 4: Развертывание бота

1. **Скачайте проект:**
   ```bash
   git clone <этот-репозиторий>
   cd email_sync_bot
   ```

2. **Обновите путь к ключу** в `deploy.sh`:
   ```bash
   # Замените эту строку на путь к вашему ключу:
   AWS_KEY_PATH="/path/to/your/keypair.pem"
   ```

3. **Запустите автоматическое развертывание:**
   ```bash
   ./deploy.sh YOUR_SERVER_IP
   ```

### Шаг 5: Настройка на сервере

1. **Подключитесь к серверу:**
   ```bash
   ssh -i /path/to/your/keypair.pem ec2-user@YOUR_SERVER_IP
   cd email_sync_bot
   ```

2. **Получите ваш Chat ID:**
   ```bash
   source venv/bin/activate
   python3 -c "
   import asyncio, aiohttp

   async def get_chat_id():
       token = 'ВАШ_TELEGRAM_TOKEN'
       async with aiohttp.ClientSession() as session:
           async with session.get(f'https://api.telegram.org/bot{token}/getUpdates') as resp:
               data = await resp.json()
               if data['result']:
                   chat_id = data['result'][-1]['message']['chat']['id']
                   print(f'Ваш Chat ID: {chat_id}')
               else:
                   print('Отправьте сообщение боту и запустите снова')

   asyncio.run(get_chat_id())
   "
   ```

3. **Настройте .env файл:**
   ```bash
   nano .env
   ```

   Заполните:
   ```env
   # Данные из Шага 1 и Шага 2
   TELEGRAM_TOKEN=123456789:ABCdefGhIJklmNOpqrStUVwxyz
   TELEGRAM_CHAT_ID=123456789
   EMAIL_ADDRESS=your-email@gmail.com
   EMAIL_PASSWORD=abcd efgh ijkl mnop
   EMAIL_SERVER=imap.gmail.com
   EMAIL_PORT=993
   CHECK_INTERVAL=30
   MAX_EMAILS_PER_BATCH=20
   ```

4. **Запустите бота:**
   ```bash
   ./start.sh
   ```

### Быстрая настройка (если у вас уже есть сервер)

Если у вас уже есть AWS инстанс, просто:

1. **Обновите deploy.sh** с вашим ключом и IP
2. **Запустите:** `./deploy.sh`
3. **Настройте .env** на сервере
4. **Запустите:** `./start.sh`

### Команды управления на сервере

- `./start.sh` - запустить бота
- `./stop.sh` - остановить бота
- `./restart.sh` - перезапустить бота
- `./logs.sh` - смотреть логи в реальном времени
- `./status.sh` - проверить статус бота

### Что делает скрипт развертывания

1. Обновляет систему и устанавливает Python 3
2. Создает папку проекта на сервере
3. Загружает все файлы проекта
4. Создает виртуальное окружение и устанавливает зависимости
5. Настраивает systemd сервис для автозапуска
6. Создает удобные скрипты управления

## Ручная установка

### Локально

1. Клонируйте репозиторий:
```bash
git clone <your-repo-url>
cd email_sync_bot
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Скопируйте файл конфигурации:
```bash
cp .env.example .env
```

4. Заполните настройки в файле `.env`

5. Запустите:
```bash
python main.py
```

### На AWS EC2 вручную

```bash
# Подключение к серверу
ssh -i keypair1.pem ec2-user@YOUR_SERVER_IP

# Обновление системы
sudo yum update -y
sudo yum install -y python3 python3-pip git

# Клонирование проекта
git clone <your-repo-url>
cd email_sync_bot

# Установка зависимостей
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Настройка
cp .env.example .env
nano .env

# Запуск
python main.py
```

## Конфигурация

Заполните файл `.env` следующими параметрами:

- `TELEGRAM_TOKEN` - токен вашего Telegram бота (получите у @BotFather)
- `TELEGRAM_CHAT_ID` - ID чата для отправки уведомлений
- `EMAIL_ADDRESS` - ваш email адрес
- `EMAIL_PASSWORD` - пароль от email (для Gmail используйте App Password)
- `EMAIL_SERVER` - IMAP сервер (по умолчанию imap.gmail.com)
- `EMAIL_PORT` - порт IMAP сервера (по умолчанию 993)
- `CHECK_INTERVAL` - интервал проверки почты в секундах (по умолчанию 30)
- `MAX_EMAILS_PER_BATCH` - максимальное количество писем за раз (по умолчанию 5)

## Настройка Gmail

1. Включите двухфакторную аутентификацию
2. Создайте App Password: Google Account → Security → App passwords
3. Используйте созданный пароль в `EMAIL_PASSWORD`

## Настройка Telegram бота

1. Создайте бота через @BotFather
2. Получите токен и укажите в `TELEGRAM_TOKEN`
3. Отправьте любое сообщение боту
4. Для получения chat_id можете запустить бота и посмотреть в логах

## Поддерживаемые почтовые провайдеры

- Gmail: imap.gmail.com:993
- Yandex: imap.yandex.ru:993
- Mail.ru: imap.mail.ru:993
- Outlook: outlook.office365.com:993

## Troubleshooting

### Проблемы с подключением к серверу
- Проверьте, что Security Group разрешает SSH подключения
- Убедитесь, что ключ имеет правильные права: `chmod 400 keypair1.pem`

### Проблемы с email
- Для Gmail обязательно используйте App Password, а не основной пароль
- Проверьте настройки IMAP в вашем почтовом провайдере

### Проблемы с Telegram
- Убедитесь, что вы отправили хотя бы одно сообщение боту
- Проверьте правильность токена бота