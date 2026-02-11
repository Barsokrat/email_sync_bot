from flask import Flask, request, jsonify
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Настройка ротации логов: макс 10MB на файл, хранить 5 резервных копий
log_handler = RotatingFileHandler(
    'gtm_webhook.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[log_handler, console_handler]
)
logger = logging.getLogger(__name__)

def send_email(event_name, page_url, user_id):
    """Отправляет email с информацией о событии"""

    # Определяем название события
    event_display = "Page opened" if event_name == "gtm.historyChange" else event_name

    # Тема письма
    subject = f"User Activity, Event: {event_display}, Page URL: {page_url}, user_id: {user_id}"

    # Тело письма (минимальное)
    body = f"""Event: {event_display}
Page URL: {page_url}
User ID: {user_id}
"""

    # Настройки SMTP
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')
    recipient_email = os.getenv('RECIPIENT_EMAIL')

    # Создаем сообщение
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Отправляем
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

@app.route('/gtm-webhook', methods=['POST', 'OPTIONS'])
def gtm_webhook():
    """Обработчик GTM webhook"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        logger.info(f"Received webhook request: {request.json}")
        data = request.json

        event_name = data.get('event', '')
        page_url = data.get('page_url', '')
        user_data = data.get('user_data', {})
        user_id = user_data.get('user_id', 'unknown')

        logger.info(f"Processing event: {event_name}, URL: {page_url}, User: {user_id}")

        # Отправляем email
        success = send_email(event_name, page_url, user_id)

        if success:
            logger.info("Email sent successfully")
            return jsonify({'status': 'success'}), 200
        else:
            logger.error("Failed to send email")
            return jsonify({'status': 'error', 'message': 'Failed to send email'}), 500

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
