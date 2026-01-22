#!/bin/bash

# Переходим в директорию проекта
PROJECT_DIR="/Users/eugene/MyProjects/myScripts/bao_tg_importer"
cd "$PROJECT_DIR"

# Загружаем переменные из .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Активируем venv
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ Виртуальное окружение venv не найдено в $PROJECT_DIR"
    exit 1
fi

# Запускаем основной скрипт
echo "🚀 Запускаю импорт из Telegram (Unified)..."
python3 scripts/unified_importer.py "$@" 2>&1 | tee /tmp/telegram_importer_output.txt
RESULT=${PIPESTATUS[0]}

deactivate

# Проверяем результат
if [ $RESULT -eq 0 ]; then
    osascript -e 'display notification "Импорт сообщений из Telegram завершен успешно!" with title "Telegram Importer"'
else
    echo "❌ Ошибка в работе скрипта. Подробности выше или в /tmp/telegram_importer_output.txt"
    osascript -e "display alert \"Ошибка при импорте сообщений из Telegram. Проверьте терминал или лог.\""
fi

# Пауза в конце
echo ""
echo "Нажмите любую клавишу для выхода..."
read -n 1
