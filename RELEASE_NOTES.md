# Release Notes - Email Sync Bot

## 2026-03-03 - v1.2.1 - Critical Bug Fix: Duplicate Message Prevention

### 🐛 Fixed
- **Critical:** Бот отправлял одно и то же сообщение многократно каждые 30 секунд
- **Root cause:** ID письма добавлялся в `sent_message_ids` в памяти ДО отправки (строка 262), но сохранялся на диск ПОСЛЕ всей обработки (строка 285)
- **Impact:** Если между добавлением в память и сохранением на диск возникала ошибка (403 Forbidden от заблокировавших бота пользователей), файл не обновлялся
- **Result:** При следующей проверке письмо считалось "новым" и отправлялось снова

### ✅ Solution
- Перенесена логика записи `sent_message_ids`:
  - **ДО:** Добавление в память → отправка → сохранение на диск (один раз в конце)
  - **ПОСЛЕ:** Отправка → добавление в память → **немедленное** сохранение на диск (после каждого письма)
- Гарантирована атомарность: каждое успешно отправленное письмо сразу записывается в `sent_message_ids.txt`

### 📝 Changed Files
- `main.py` (строки 252-289):
  - Удалена строка 262: `self.sent_message_ids.append(msg_id)` из блока фильтрации
  - Добавлены строки 277-279: запись ID и сохранение файла сразу после отправки
  - Удалена строка 285: `self._save_sent_ids()` из условия `if new_emails:`

### 🧪 Testing
- **Before:** "Recognition request and feedback" отправлялось каждые 30 сек (loop)
- **After:**
  - 13:35:50 — обработано 1 новое письмо
  - 13:36:28 — 0 новых (дубликатов нет)
  - 13:37:06 — 0 новых (дубликатов нет)
  - ✅ Confirmed: No more duplicates

### 🚀 Deployment
- Server: `ec2-user@3.17.70.135` (AWS)
- Files updated: `/home/ec2-user/email_sync_bot/main.py`
- Service: `sudo systemctl restart email-sync-bot`
- Deployed: 2026-03-03 13:33 UTC

---

## Previous Releases

### 2026-02-XX - v1.2.0 - Multi-User Support
- Добавлена поддержка множественных пользователей
- SQLite база данных для хранения подписчиков
- Команды: `/start`, `/status`, `/health`, `/help`, `/users`

### 2026-01-XX - v1.1.0 - Initial Production Release
- Базовый функционал синхронизации email → Telegram
- IMAP клиент для Gmail
- Systemd service для автозапуска
- Ротация логов (10MB × 5 файлов)
