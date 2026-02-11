#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация - ОБНОВИТЕ ПУТЬ К ВАШЕМУ КЛЮЧУ
AWS_KEY_PATH="/path/to/your/keypair.pem"  # ← ЗАМЕНИТЕ НА ПУТЬ К ВАШЕМУ .pem ФАЙЛУ
AWS_USER="ec2-user"
AWS_HOST=""  # Будет заполнено при запуске
PROJECT_NAME="email_sync_bot"
REMOTE_PATH="/home/ec2-user/$PROJECT_NAME"

echo -e "${BLUE}🚀 Email Sync Bot - Скрипт развертывания на AWS${NC}"
echo ""

# Проверяем наличие ключа
if [ ! -f "$AWS_KEY_PATH" ]; then
    echo -e "${RED}❌ Ключ не найден: $AWS_KEY_PATH${NC}"
    exit 1
fi

# Запрашиваем IP адрес сервера
if [ -z "$1" ]; then
    echo -e "${YELLOW}Введите IP адрес вашего AWS сервера:${NC}"
    read -p "IP: " AWS_HOST
else
    AWS_HOST=$1
fi

if [ -z "$AWS_HOST" ]; then
    echo -e "${RED}❌ IP адрес не указан${NC}"
    exit 1
fi

echo -e "${BLUE}📋 Параметры развертывания:${NC}"
echo -e "Хост: ${GREEN}$AWS_HOST${NC}"
echo -e "Пользователь: ${GREEN}$AWS_USER${NC}"
echo -e "Ключ: ${GREEN}$AWS_KEY_PATH${NC}"
echo ""

# Устанавливаем права на ключ
chmod 400 "$AWS_KEY_PATH"

echo -e "${YELLOW}🔧 Подготовка сервера...${NC}"

# Проверяем подключение к серверу
ssh -i "$AWS_KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$AWS_USER@$AWS_HOST" "echo 'Подключение успешно'" || {
    echo -e "${RED}❌ Не удалось подключиться к серверу${NC}"
    exit 1
}

# Обновляем систему и устанавливаем Python
ssh -i "$AWS_KEY_PATH" "$AWS_USER@$AWS_HOST" << 'EOF'
    sudo yum update -y
    sudo yum install -y python3 python3-pip git

    # Создаем директорию для проекта
    mkdir -p ~/email_sync_bot

    echo "Сервер подготовлен"
EOF

echo -e "${YELLOW}📤 Загружаем файлы проекта...${NC}"

# Загружаем файлы проекта
scp -i "$AWS_KEY_PATH" -r \
    main.py \
    config.py \
    telegram_bot.py \
    email_client.py \
    requirements.txt \
    .env.example \
    "$AWS_USER@$AWS_HOST:$REMOTE_PATH/"

echo -e "${YELLOW}🔧 Настраиваем окружение...${NC}"

# Устанавливаем зависимости и настраиваем сервис
ssh -i "$AWS_KEY_PATH" "$AWS_USER@$AWS_HOST" << EOF
    cd $REMOTE_PATH

    # Создаем виртуальное окружение
    python3 -m venv venv
    source venv/bin/activate

    # Устанавливаем зависимости
    pip install -r requirements.txt

    # Копируем пример конфигурации
    if [ ! -f .env ]; then
        cp .env.example .env
        echo "📝 Создан файл .env - не забудьте его настроить!"
    fi

    echo "Зависимости установлены"
EOF

echo -e "${YELLOW}⚙️ Создаем systemd сервис...${NC}"

# Создаем systemd сервис
ssh -i "$AWS_KEY_PATH" "$AWS_USER@$AWS_HOST" << EOF
    sudo tee /etc/systemd/system/email-sync-bot.service > /dev/null << 'SERVICE_EOF'
[Unit]
Description=Email Sync Bot
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=$REMOTE_PATH
Environment=PATH=$REMOTE_PATH/venv/bin
ExecStart=$REMOTE_PATH/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

    sudo systemctl daemon-reload
    sudo systemctl enable email-sync-bot

    echo "Systemd сервис создан"
EOF

echo -e "${YELLOW}📋 Создаем скрипты управления...${NC}"

# Создаем скрипты управления на сервере
ssh -i "$AWS_KEY_PATH" "$AWS_USER@$AWS_HOST" << 'EOF'
    cd ~/email_sync_bot

    # Скрипт старта
    cat > start.sh << 'START_EOF'
#!/bin/bash
sudo systemctl start email-sync-bot
sudo systemctl status email-sync-bot
START_EOF

    # Скрипт остановки
    cat > stop.sh << 'STOP_EOF'
#!/bin/bash
sudo systemctl stop email-sync-bot
sudo systemctl status email-sync-bot
STOP_EOF

    # Скрипт перезапуска
    cat > restart.sh << 'RESTART_EOF'
#!/bin/bash
sudo systemctl restart email-sync-bot
sudo systemctl status email-sync-bot
RESTART_EOF

    # Скрипт просмотра логов
    cat > logs.sh << 'LOGS_EOF'
#!/bin/bash
sudo journalctl -u email-sync-bot -f
LOGS_EOF

    # Скрипт статуса
    cat > status.sh << 'STATUS_EOF'
#!/bin/bash
sudo systemctl status email-sync-bot
LOGS_EOF

    chmod +x *.sh

    echo "Скрипты управления созданы"
EOF

echo -e "${GREEN}✅ Развертывание завершено!${NC}"
echo ""
echo -e "${BLUE}📋 Следующие шаги:${NC}"
echo -e "1. Подключитесь к серверу: ${YELLOW}ssh -i $AWS_KEY_PATH $AWS_USER@$AWS_HOST${NC}"
echo -e "2. Перейдите в папку: ${YELLOW}cd $PROJECT_NAME${NC}"
echo -e "3. Настройте файл .env с вашими токенами"
echo -e "4. Запустите бота: ${YELLOW}./start.sh${NC}"
echo ""
echo -e "${BLUE}🔧 Команды управления:${NC}"
echo -e "• ${GREEN}./start.sh${NC} - запустить бота"
echo -e "• ${GREEN}./stop.sh${NC} - остановить бота"
echo -e "• ${GREEN}./restart.sh${NC} - перезапустить бота"
echo -e "• ${GREEN}./logs.sh${NC} - смотреть логи"
echo -e "• ${GREEN}./status.sh${NC} - статус бота"
echo ""
echo -e "${YELLOW}⚠️ Не забудьте настроить файл .env перед запуском!${NC}"