#!/usr/bin/env python3
"""
Telegram Importer для Supabase
Использует Telethon для получения сообщений из Telegram каналов
и сохраняет их в Supabase базу данных.
"""

from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio
import os
import json
from datetime import datetime
import httpx
import sys

def load_config():
    """Загружает конфигурацию из переменных окружения или .env файла"""
    # Пытаемся загрузить .env файл, если он существует
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.replace('"', '').replace("'", "")
    except FileNotFoundError:
        pass  # .env файл не обязателен
    
    # Загружаем переменные
    config = {
        'api_id': int(os.getenv('TELEGRAM_API_ID', '25727332')),
        'api_hash': os.getenv('TELEGRAM_API_HASH', '4306a0f13e21c95832ecd8c35cafffbb'),
        'session_string': os.getenv('TELEGRAM_SESSION'),
        'supabase_url': os.getenv('MY_SUPABASE_URL'),
        'supabase_key': os.getenv('MY_SUPABASE_SERVICE_ROLE_KEY')
    }
    
    # Проверяем обязательные переменные
    required = ['session_string', 'supabase_url', 'supabase_key']
    for key in required:
        if not config[key]:
            print(f"❌ Ошибка: Не установлена переменная окружения {key.upper()}")
            print("\nДля запуска установите переменные окружения:")
            print("export TELEGRAM_API_ID=ваш_api_id")
            print("export TELEGRAM_API_HASH=ваш_api_hash")
            print("export TELEGRAM_SESSION='ваша_строка_сессии'")
            print("export MY_SUPABASE_URL='ваш_supabase_url'")
            print("export MY_SUPABASE_SERVICE_ROLE_KEY='ваш_supabase_ключ'")
            return None
    
    return config

async def telegram_importer():
    """
    Импортер сообщений из Telegram каналов в Supabase
    """
    config = load_config()
    if not config:
        return None
    
    client = TelegramClient(StringSession(config['session_string']), 
                           config['api_id'], config['api_hash'])
    await client.connect()
    
    try:
        print("🚀 Начинаем импорт из Telegram каналов...")
        
        # Получаем список каналов для синхронизации из Supabase
        async with httpx.AsyncClient() as http_client:
            headers = {
                'apikey': config['supabase_key'],
                'Authorization': f'Bearer {config['supabase_key']}',
                'Content-Type': 'application/json'
            }
            
            # Получаем каналы для синхронизации
            response = await http_client.get(
                f"{config['supabase_url']}/rest/v1/channel_sync_state?select=*",
                headers=headers
            )
            
            if response.status_code != 200:
                print(f"❌ Ошибка получения каналов: {response.text}")
                return None
                
            channels_to_sync = response.json()
        
        print(f"✅ Найдено {len(channels_to_sync)} каналов для синхронизации")
        
        total_synced = 0
        total_processed = 0
        
        for channel in channels_to_sync:
            print(f"\n🔄 Обрабатываем канал: {channel.get('channel_name', 'Unknown')} (ID: {channel['channel_id']})")
            
            try:
                # Получаем сущность канала
                entity = await client.get_entity(int(channel['channel_id']))
                
                # Получаем сообщения из канала, новые чем last_processed_message_id
                min_id = channel.get('last_processed_message_id', 0) or 0
                messages = await client.get_messages(
                    entity, 
                    limit=10,  # Ограничиваем за один запуск
                    min_id=min_id
                )
                
                if not messages or len(messages) == 0:
                    print(f"  ✅ Нет новых сообщений в канале {channel.get('channel_name', 'Unknown')}")
                    continue
                
                print(f"  ✅ Найдено {len(messages)} новых сообщений в канале {channel.get('channel_name', 'Unknown')}")
                
                # Подготовка сообщений для вставки
                posts_to_insert = []
                for msg in messages:
                    if msg.text:  # Только сообщения с текстом
                        post = {
                            'channel_id': channel['channel_id'],
                            'message_id': msg.id,
                            'content': msg.text,
                            'posted_at': datetime.fromtimestamp(msg.date.timestamp()).isoformat()
                        }
                        posts_to_insert.append(post)
                
                if not posts_to_insert:
                    print(f"  ⚠️  Нет текстовых сообщений для сохранения в {channel.get('channel_name', 'Unknown')}")
                    continue
                
                # Вставка сообщений в Supabase
                response = await http_client.post(
                    f"{config['supabase_url']}/rest/v1/posts?select=*",
                    headers=headers,
                    json=posts_to_insert
                )
                
                if response.status_code in [200, 201]:
                    print(f"  ✅ Успешно вставлено {len(posts_to_insert)} сообщений из {channel.get('channel_name', 'Unknown')}")
                    total_processed += len(posts_to_insert)
                    
                    # Обновляем состояние синхронизации - сохраняем максимальный ID сообщения
                    max_message_id = max(msg.id for msg in messages if msg.id is not None)
                    update_response = await http_client.patch(
                        f"{config['supabase_url']}/rest/v1/channel_sync_state",
                        headers=headers,
                        params={'channel_id': f'eq.{channel["channel_id"]}'},
                        json={'last_processed_message_id': max_message_id}
                    )
                    
                    if update_response.status_code in [200, 204]:
                        print(f"  ✅ Состояние синхронизации обновлено: {max_message_id}")
                        total_synced += 1
                    else:
                        print(f"  ❌ Ошибка обновления состояния синхронизации: {update_response.text}")
                else:
                    print(f"  ❌ Ошибка вставки сообщений: {response.text}")
                    
            except Exception as e:
                print(f"  ❌ Ошибка обработки канала {channel.get('channel_name', 'Unknown')}: {e}")
        
        print(f"\n🎉 Синхронизация завершена!")
        print(f"📊 Результаты:")
        print(f"   - Обработано каналов: {total_synced} из {len(channels_to_sync)}")
        print(f"   - Обработано сообщений: {total_processed}")
        
        result = {
            'message': 'Синхронизация успешно завершена',
            'channels_processed': len(channels_to_sync),
            'channels_synced': total_synced,
            'messages_processed': total_processed
        }
        
        return result
        
    finally:
        await client.disconnect()

if __name__ == '__main__':
    print("="*60)
    print("ТЕЛЕГРАМ ИМПОРТЕР ДЛЯ SUPABASE")
    print("="*60)
    
    result = asyncio.run(telegram_importer())
    
    if result:
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТ:")
        print("="*60)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\n❌ Синхронизация не была выполнена из-за ошибок конфигурации")
        sys.exit(1)