#!/usr/bin/env python3
"""
Telegram to Supabase Importer
Простой скрипт для импорта сообщений из Telegram в Supabase
"""

from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio
import os
import json
from datetime import datetime
import httpx
import sys

from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.types import InputChannel

def print_header():
    print("="*60)
    print("ТЕЛЕГРАМ ИМПОРТЕР ДЛЯ SUPABASE")
    print("Использует Telethon для получения сообщений")
    print("="*60)

def print_success(message):
    print(f"✅ {message}")

def print_error(message):
    print(f"❌ {message}")

def print_info(message):
    print(f"ℹ️  {message}")

def load_config():
    """Загружает конфигурацию из .env или переменных окружения"""
    # Попробуем загрузить .env файл из родительской директории
    env_paths = ['.env', '../.env']  # Ищем сначала в текущей, потом в родительской
    
    for env_path in env_paths:
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value.replace('"', '').replace("'", "")
            break  # Если файл найден и прочитан, выходим из цикла
        except FileNotFoundError:
            continue  # Пробуем следующий путь

    # Загружаем конфигурацию
    config = {
        'api_id': os.getenv('TELEGRAM_API_ID', '').strip(),
        'api_hash': os.getenv('TELEGRAM_API_HASH', '').strip(),
        'session_string': os.getenv('TELEGRAM_SESSION', '').strip(),
        'supabase_url': os.getenv('MY_SUPABASE_URL', '').strip(),
        'supabase_key': os.getenv('MY_SUPABASE_SERVICE_ROLE_KEY', '').strip()
    }

    # Проверяем наличие всех необходимых параметров
    missing = [key for key, value in config.items() if not value]
    if missing:
        print_error(f"Отсутствуют следующие переменные: {', '.join(missing)}")
        print("\nПожалуйста, установите переменные окружения:")
        print("  TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION")
        print("  MY_SUPABASE_URL, MY_SUPABASE_SERVICE_ROLE_KEY")
        return None
    
    try:
        config['api_id'] = int(config['api_id'])
    except ValueError:
        print_error("TELEGRAM_API_ID должен быть числом")
        return None

    return config

def load_ollama_prompt():
    """Загружает промпт для Ollama из файла unified_ollama_prompt.md"""
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), '!Промты', 'unified_ollama_prompt.md'), 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print_error("Файл unified_ollama_prompt.md не найден. Убедитесь, что он находится в той же директории, что и скрипт.")
        return None

OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', 'http://127.0.0.1:11434/api/generate')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma3:latest')

# Глобальная переменная для хранения промпта
OLLAMA_PROMPT_TEMPLATE = None

async def classify_message_with_ollama(message_content: str) -> bool:
    """
    Classifies a message as an event or non-event using Ollama, specifically checking for a concrete event date.
    """
    if OLLAMA_PROMPT_TEMPLATE is None:
        print_error("Шаблон промпта Ollama не загружен.")
        return False

    prompt = OLLAMA_PROMPT_TEMPLATE.format(message_content=message_content)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                OLLAMA_API_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Ollama responses can vary, try to extract the most likely answer
            if "response" in result:
                ollama_response = result["response"].strip().upper()
                if "TRUE" in ollama_response:
                    return True
                elif "FALSE" in ollama_response:
                    return False
                print_error(f"Неожиданный ответ от Ollama (не содержит TRUE/FALSE): {ollama_response}")
            else:
                print_error(f"Неожиданный ответ от Ollama (нет поля 'response'): {result}")
            return False
            
        except httpx.RequestError as e:
            print_error(f"Ошибка запроса к Ollama: {e}")
            return False
        except httpx.HTTPStatusError as e:
            print_error(f"Ошибка HTTP статуса от Ollama: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            print_error(f"Неизвестная ошибка при классификации Ollama: {e}")
            return False

async def import_telegram_messages():
    """Основная функция импорта сообщений"""
    config = load_config()
    if not config:
        return None

    global OLLAMA_PROMPT_TEMPLATE
    OLLAMA_PROMPT_TEMPLATE = load_ollama_prompt()
    if OLLAMA_PROMPT_TEMPLATE is None:
        return None

    print_info("Подключение к Telegram...")
    client = TelegramClient(
        StringSession(config['session_string']),
        config['api_id'],
        config['api_hash']
    )
    
    await client.connect()
    
    try:
        # Проверим, подключились ли мы
        me = await client.get_me()
        print_success(f"Подключились как: {me.first_name} (@{me.username or 'N/A'})")
        
        print_info("Подключение к Supabase...")
        
        async with httpx.AsyncClient() as http_client:
            headers = {
                'apikey': config['supabase_key'],
                'Authorization': f"Bearer {config['supabase_key']}",
                'Content-Type': 'application/json'
            }

            # Получаем каналы для синхронизации
            print_info("Получение списка каналов...")
            response = await http_client.get(
                f"{config['supabase_url']}/rest/v1/channel_sync_state?select=*",
                headers=headers
            )
            
            if response.status_code != 200:
                print_error(f"Ошибка получения каналов: {response.text}")
                return None

            channels = response.json()
            print_success(f"Найдено {len(channels)} каналов для синхронизации")
            
            total_synced = 0
            total_messages = 0
            total_events_classified = 0
            
            for channel in channels:
                channel_name = channel.get('channel_name', str(channel['channel_id']))
                print_info(f"Обработка канала: {channel_name}")
                
                try:
                    entity = None # Initialize entity to None
                    channel_id_from_db = channel.get('channel_id')
                    channel_name_lookup = channel.get('channel_name', '').strip()

                    print_info(f"  Debug: channel_id_from_db={channel_id_from_db}, channel_name_lookup={channel_name_lookup}")

                    if channel_id_from_db is not None:
                        try:
                            channel_id = int(channel_id_from_db)
                            entity = await client.get_entity(channel_id)
                        except ValueError:
                            # Fallback to channel_name if numeric ID fails
                            if channel_name_lookup and channel_name_lookup.startswith('@'):
                                print_info(f"  Попытка получить канал по имени (после ошибки ID): {channel_name_lookup}")
                                entity = await client.get_entity(channel_name_lookup)
                    elif channel_name_lookup and channel_name_lookup.startswith('@'):
                        print_info(f"  Попытка получить канал по имени (без ID): {channel_name_lookup}")
                        entity = await client.get_entity(channel_name_lookup)
                    
                    if entity is None:
                        print_error(f"  Ошибка: Невозможно получить сущность для канала {channel_name}. Проверьте channel_id и channel_name в channel_sync_state.")
                        continue # Skip this channel
                    
                    # Определение last_id
                    last_id = channel.get('last_processed_message_id', 0) or 0
                    
                    # Определение списка ID топиков для обработки
                    thread_ids_to_process = []
                    specific_thread_id = channel.get('thread_id')

                    if specific_thread_id is not None:
                        thread_ids_to_process.append(specific_thread_id)
                        print_info(f"  Синхронизация конкретного топика ID={specific_thread_id}")
                    elif hasattr(entity, 'forum') and entity.forum:
                        print_info(f"  Обнаружен форум. Получение списка топиков...")
                        
                        input_channel = InputChannel(entity.id, entity.access_hash)
                        
                        forum_topics = await client(GetForumTopicsRequest(
                            channel=input_channel,
                            offset_date=0,
                            offset_id=0,
                            offset_topic=0,
                            limit=100
                        ))

                        # ID топика — это ID его корневого сервисного сообщения
                        new_thread_ids = [topic.id for topic in forum_topics.topics if topic.id != 1]
                        thread_ids_to_process.extend([1] + new_thread_ids)
                        
                        print_success(f"  Найдено топиков: {len(thread_ids_to_process)}")
                    else:
                        thread_ids_to_process.append(None)

                    # Обходим все топики
                    max_id_overall = last_id
                    
                    for thread_id in thread_ids_to_process:
                        if thread_id is None:
                            topic_label = "Основной канал"
                            thread_id_param = None
                        elif thread_id == 1:
                            topic_label = "Общий Топик (ID=1)"
                            thread_id_param = 1
                        else:
                            topic_label = f"Топик ID={thread_id}"
                            thread_id_param = thread_id

                        print_info(f"  > Синхронизация: {topic_label}")

                        # Получаем сообщения для ЭТОГО топика
                        # Если thread_id_param None, не передаем этот параметр вообще
                        if thread_id_param is None:
                            current_messages = await client.get_messages(
                                entity,
                                limit=20,
                                min_id=last_id
                            )
                        else:
                            current_messages = await client.get_messages(
                                entity,
                                limit=20,
                                min_id=last_id,
                                reply_to=thread_id_param
                            )
                        
                        if not current_messages:
                            continue
                            
                        # Подготовим сообщения для вставки
                        posts_to_insert = []
                        for msg in current_messages:
                            # ОБНОВЛЕНО: обрабатываем сообщения с текстом ИЛИ фото
                            if msg.text or msg.photo:
                                is_event = False
                                if msg.text:
                                    is_event = await classify_message_with_ollama(msg.text)

                                # ОБНОВЛЕНО: Логика загрузки изображения
                                image_url = None
                                if msg.photo:
                                    print_info(f"  > Найдено изображение в сообщении {msg.id}. Загрузка...")
                                    photo_bytes = await client.download_media(msg.photo, file=bytes)

                                    if photo_bytes:
                                        bucket_name = 'events' # ИЗМЕНЕНО: бакет 'events'
                                        file_path = f"Script/{entity.id}/{msg.id}.jpg" # ИЗМЕНЕНО: папка 'Script'
                                        storage_url = f"{config['supabase_url']}/storage/v1/object/{bucket_name}/{file_path}"
                                        
                                        storage_headers = {
                                            'apikey': config['supabase_key'],
                                            'Authorization': f"Bearer {config['supabase_key']}",
                                            'Content-Type': 'image/jpeg'
                                        }
                                        
                                        try:
                                            upload_response = await http_client.post(
                                                storage_url,
                                                headers=storage_headers,
                                                content=photo_bytes,
                                                params={"upsert": "true"}
                                            )
                                            upload_response.raise_for_status()
                                            
                                            image_url = f"{config['supabase_url']}/storage/v1/object/public/{bucket_name}/{file_path}"
                                            print_success(f"  > Изображение успешно загружено: {image_url}")
                                        except httpx.HTTPStatusError as e:
                                            print_error(f"  > Ошибка загрузки изображения в Supabase Storage: {e.response.status_code} - {e.response.text}")
                                        except Exception as e:
                                            print_error(f"  > Неизвестная ошибка при загрузке изображения: {e}")

                                if hasattr(entity, 'username') and entity.username:
                                    base_link = f"https://t.me/{entity.username}"
                                else:
                                    base_link = f"https://t.me/c/{abs(entity.id)}"

                                if thread_id_param is not None and thread_id_param != 1:
                                    post_link = f"{base_link}/{thread_id_param}/{msg.id}"
                                else:
                                    post_link = f"{base_link}/{msg.id}"

                                post = {
                                    'channel_name': f"@{entity.username}" if hasattr(entity, 'username') and entity.username else f"channel_{entity.id}",
                                    'message_id': msg.id,
                                    'content': msg.text or '', # Используем пустую строку, если текста нет
                                    'posted_at': datetime.fromtimestamp(msg.date.timestamp()).isoformat(),
                                    'is_event_filtered': True,
                                    'is_event': is_event,
                                    'post_link': post_link,
                                    'raw_channel_id': entity.id,
                                    'image': image_url
                                }
                                if is_event:
                                    total_events_classified += 1
                                posts_to_insert.append(post)
                        
                        if not posts_to_insert:
                            print_info(f"  Нет подходящих сообщений (текст/фото) для сохранения в {topic_label}")
                            continue
                        
                        # Вставляем в Supabase
                        try:
                            response = await http_client.post(
                                f"{config['supabase_url']}/rest/v1/posts?select=*,is_event_filtered,is_event,image",
                                headers=headers,
                                json=posts_to_insert
                            )
                            
                            if response.status_code in [200, 201]:
                                print_success(f"  Вставлено {len(posts_to_insert)} записей в {topic_label}")
                                total_messages += len(posts_to_insert)
                                
                                # Обновляем максимальный ID для этого прохода
                                max_id_current = max(msg.id for msg in current_messages)
                                if max_id_current > max_id_overall:
                                    max_id_overall = max_id_current
                            else:
                                print_error(f"  Ошибка вставки в {topic_label}: {response.text}")
                        except Exception as insert_error:
                            print_error(f"  Ошибка вставки в {topic_label}: {insert_error}")
                            
                            # Проверим, есть ли запись в channel_sync_state для этого канала
                            try:
                                channel_name_for_lookup = f"@{entity.username}" if hasattr(entity, 'username') and entity.username else f"channel_{entity.id}"
                                
                                # Проверим существующую запись
                                check_response = await http_client.get(
                                    f"{config['supabase_url']}/rest/v1/channel_sync_state",
                                    headers=headers,
                                    params={'channel_name': f'eq.{channel_name_for_lookup}'}
                                )
                                
                                if check_response.status_code == 200 and len(check_response.json()) == 0:
                                    # Нет записи для этого канала, создадим её
                                    for post in posts_to_insert:
                                        post['channel_name'] = channel_name_for_lookup
                                    
                                    # Добавим запись в channel_sync_state
                                    channel_state_data = {
                                        'channel_name': channel_name_for_lookup,
                                        'channel_id': entity.id,
                                        'last_processed_message_id': 0
                                    }
                                    
                                    await http_client.post(
                                        f"{config['supabase_url']}/rest/v1/channel_sync_state",
                                        headers=headers,
                                        json=channel_state_data
                                    )
                                    
                                    # Повторим вставку сообщений с правильным channel_name
                                    response = await http_client.post(
                                        f"{config['supabase_url']}/rest/v1/posts?select=*,is_event_filtered,is_event,image_url",
                                        headers=headers,
                                        json=posts_to_insert
                                    )
                                    
                                    if response.status_code in [200, 201]:
                                        print_success(f"  Вставлено {len(posts_to_insert)} сообщений (после обновления данных) в {topic_label}")
                                        total_messages += len(posts_to_insert)
                                        
                                        max_id_current = max(msg.id for msg in current_messages)
                                        if max_id_current > max_id_overall:
                                            max_id_overall = max_id_current
                                    else:
                                        print_error(f"  Ошибка вставки (после обновления данных) в {topic_label}: {response.text}")
                            except Exception as e:
                                print_error(f"  Ошибка при попытке исправить данные в {topic_label}: {e}")
                                
                    # Обновление общего последнего ID
                    if max_id_overall > last_id:
                        channel_name_for_update = f"@{entity.username}" if hasattr(entity, 'username') and entity.username else f"channel_{entity.id}"
                        update_response = await http_client.patch(
                            f"{config['supabase_url']}/rest/v1/channel_sync_state",
                            headers=headers,
                            params={'channel_name': f'eq.{channel_name_for_update}'},
                            json={'last_processed_message_id': max_id_overall}
                        )
                        
                        if update_response.status_code in [200, 204]:
                            print_success(f"  Состояние обновлено до: {max_id_overall}")
                            total_synced += 1
                        else:
                            print_error(f"  Ошибка обновления состояния: {update_response.text}")
                    else:
                        print_info(f"  Нет новых сообщений для обновления состояния в {channel_name}")
                
                except Exception as e:
                    print_error(f"Ошибка при обработке канала {channel_name}: {e}")
                    continue
            
            # Возвращаем результат
            result = {
                'status': 'success',
                'channels_synced': total_synced,
                'total_channels': len(channels),
                'messages_imported': total_messages,
                'events_classified': total_events_classified,
                'timestamp': datetime.now().isoformat()
            }
            
            print_success(f"Синхронизация завершена!")
            print_info(f"Обработано каналов: {total_synced}/{len(channels)}")
            print_info(f"Сообщений: {total_messages}")
            print_info(f"Событий: {total_events_classified}")
            
            return result
    
    except Exception as e:
        print_error(f"Ошибка при работе: {e}")
        return None
    finally:
        await client.disconnect()

def main():
    print_header()
    
    # Проверим установлены ли зависимости
    try:
        import telethon
        import httpx
    except ImportError as e:
        print_error(f"Отсутствует необходимая библиотека: {e.name}")
        print("Установите зависимости командой:")
        print("  pip install telethon httpx")
        return

    # Запускаем импорт
    result = asyncio.run(import_telegram_messages())
    
    if result:
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТ:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("="*60)
    else:
        print_error("Импорт не удался")
        sys.exit(1)

if __name__ == '__main__':
    main()
