#!/bin/bash
# Определяем директорию, в которой находится этот скрипт
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Активируем виртуальное окружение и запускаем скрипт
source venv/bin/activate
python3 scripts/unified_importer.py
deactivate
