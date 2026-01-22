#!/bin/bash
# Переходим в папку проекта
cd /root/scripts/bao_tg_importer

# Активируем окружение
source venv/bin/activate

# Запускаем скрипт и пишем лог (дописываем в конец файла)
# Используем flock чтобы избежать одновременного запуска нескольких копий
/usr/bin/flock -n /var/lock/bao_importer.lock python3 scripts/unified_importer.py >> /root/scripts/bao_tg_importer/logs/cron.log 2>&1
