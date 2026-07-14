#!/bin/bash
# Watchdog для email_sync_bot: перезапускает сервис, если он "тихо завис" —
# процесс жив (systemd active), но лог не обновлялся > STALE_MIN минут.
# Бот пишет строку в лог каждые ~30 сек, поэтому свежесть bot.log = живой
# опрос IMAP. Инцидент 2026-07-11: IMAP-чтение зависло без исключения, лог
# встал на 3 дня при active-сервисе, systemd этого не видел.
# Belt-and-suspenders к socket-таймауту в email_client.py: ловит ЛЮБОЙ фриз,
# не только IMAP-чтение. Ставится в cron root (*/5).
set -euo pipefail

LOG=/opt/email_sync_bot/bot.log
STALE_MIN=10
SERVICE=email-sync-bot

[ -f "$LOG" ] || exit 0
# Не мешаем ручной остановке: чиним только если сервис должен работать.
systemctl is-active --quiet "$SERVICE" || exit 0

last=$(stat -c %Y "$LOG")
now=$(date +%s)
age_min=$(( (now - last) / 60 ))

if [ "$age_min" -ge "$STALE_MIN" ]; then
    logger -t email-bot-watchdog "bot.log завис ${age_min} мин (>=${STALE_MIN}) при active-сервисе — рестарт ${SERVICE}"
    systemctl restart "$SERVICE"
fi
