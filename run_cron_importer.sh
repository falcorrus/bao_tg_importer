#!/bin/bash

# Путь к директории скрипта
cd /root/scripts/bao_tg_importer

# Настройки уведомлений
TELEGRAM_BOT_TOKEN="6027699883:AAFKOu9gPsc7rd-SDQeFCHTt0edI73dXWSQ"
TELEGRAM_CHAT_ID="159194550"

send_tg_error() {
    local message="$1"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d text="${message}" > /dev/null
}

# Запуск импортера
source venv/bin/activate
python3 scripts/unified_importer.py

# Проверка кода выхода
if [ $? -ne 0 ]; then
    echo "$(date): 🚨 ERROR detected in importer"
    send_tg_error "🚨 Ошибка в BAO Importer на VPS! Проверь логи: /root/scripts/bao_tg_importer/logs/cron.log"
fi