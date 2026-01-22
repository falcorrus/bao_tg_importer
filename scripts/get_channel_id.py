#!/usr/bin/env python3
"""
Инструмент для получения числового ID Telegram-канала.
ID с префиксом -100 необходим для стабильной работы импортера.
"""

import asyncio
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

def load_config():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    config = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    config[k] = v.replace('"', '').replace("'", "")
    return config

async def main():
    conf = load_config()
    api_id = conf.get('TELEGRAM_API_ID')
    api_hash = conf.get('TELEGRAM_API_HASH')
    session = conf.get('TELEGRAM_SESSION')

    if not all([api_id, api_hash, session]):
        print("❌ Ошибка: Не найдены TELEGRAM_API_ID, HASH или SESSION в .env файле.")
        return

    client = TelegramClient(StringSession(session), int(api_id), api_hash)
    await client.connect()

    print("\n--- Получение ID канала ---")
    target = input("Введите @username канала или ссылку на пост: ").strip()
    
    # Очистка ссылки, если ввели t.me/username/123
    if 't.me/' in target:
        target = target.split('t.me/')[-1].split('/')[0]
        if not target.startswith('@'): target = '@' + target

    try:
        entity = await client.get_entity(target)
        print(f"\n✅ Успешно найдено!")
        print(f"Название: {entity.title}")
        print(f"Оригинальный ID: {entity.id}")
        
        # Формируем правильный ID для базы данных
        real_id = entity.id
        if not str(real_id).startswith('-100'):
            # В Telethon ID каналов положительные, но в базе и API они должны быть -100...
            real_id = int(f"-100{real_id}")
        
        print(f"\n👉 ДЛЯ БАЗЫ ДАННЫХ (channel_id): {real_id}")
        print(f"👉 ДЛЯ БАЗЫ ДАННЫХ (channel_name): @{entity.username if hasattr(entity, 'username') else target}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
