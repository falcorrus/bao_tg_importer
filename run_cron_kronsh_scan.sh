#!/usr/bin/env bash

# Переходим в директорию скрипта на VPS
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

# Включаем строгий режим и обработку ошибок
set -Eeuo pipefail
trap 'send_tg_error "🚨 Ошибка в Kronsh Chat Scanner на VPS! Проверь логи: /root/scripts/bao_tg_importer/logs/kronsh_scan.log"' ERR

# Активируем venv и запускаем сканер
source venv/bin/activate
python3 scripts/scan_kronsh_chat.py

# Логируем успешное завершение
echo "$(date): ✅ Kronsh Scan Success"
