#!/usr/bin/env python3
"""
Supabase Post Filter with Ollama
Скрипт для фильтрации существующих сообщений в Supabase с использованием Ollama
"""

import asyncio
import os
import json
from datetime import datetime
import httpx
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession

def print_header():
    print("="*60)
    print("SUPABASE ПОСТ ФИЛЬТР С OLLAMA")
    print("Фильтрует существующие посты в Supabase")
    print("="*60)

def print_success(message):
    print(f"✅ {message}")

def print_error(message):
    print(f"❌ {message}")

def print_info(message):
    print(f"ℹ️  {message}")

def load_config():
    """Загружает конфигурацию из .env или переменных окружения"""
    env_paths = ['.env', '../.env']
    
    for env_path in env_paths:
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value.replace('"', '').replace("'", "")
            break
        except FileNotFoundError:
            continue

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
            print_info(f"Ollama Request Payload: {json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, ensure_ascii=False)}")
            response.raise_for_status()
            result = response.json()
            
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
            
            print_error(f"Неожиданный ответ от Ollama: {result}")
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

async def filter_existing_posts():
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
        me = await client.get_me()
        print_success(f"Подключились как: {me.first_name} (@{me.username or 'N/A'})")

        print_info("Подключение к Supabase...")
        
        async with httpx.AsyncClient() as http_client:
            headers = {
                'apikey': config['supabase_key'],
                'Authorization': f"Bearer {config['supabase_key']}",
                'Content-Type': 'application/json'
            }

            # Получаем посты, которые еще не были отфильтрованы
            print_info("Получение неотфильтрованных постов...")
            response = await http_client.get(
                f"{config['supabase_url']}/rest/v1/posts?is_event_filtered=eq.false&select=id,content,channel_name,message_id,raw_channel_id,image_url",
                headers=headers
            )
            
            if response.status_code != 200:
                print_error(f"Ошибка получения постов: {response.text}")
                return None

            posts_to_filter = response.json()
            print_success(f"Найдено {len(posts_to_filter)} постов для фильтрации")
            
            total_filtered = 0
            
            for post in posts_to_filter:
                post_id = post['id']
                content = post['content']
                channel_name = post['channel_name']
                message_id = post['message_id']
                raw_channel_id = post['raw_channel_id']
                image_url = post.get('image_url') # Use .get for safety

                # Construct post_link
                if channel_name.startswith('@'):
                    base_link = f"https://t.me/{channel_name.lstrip('@')}"
                elif raw_channel_id is not None:
                    base_link = f"https://t.me/c/{raw_channel_id}"
                elif channel_name.startswith('channel_'): # Try to infer raw_channel_id from channel_name
                    try:
                        inferred_channel_id = int(channel_name.replace('channel_', ''))
                        base_link = f"https://t.me/c/{inferred_channel_id}"
                    except ValueError:
                        print_error(f"  Ошибка: Невозможно определить raw_channel_id для поста {post_id} из channel_name: {channel_name}")
                        base_link = "" # Fallback to empty link
                else:
                    print_error(f"  Ошибка: Невозможно определить base_link для поста {post_id}. channel_name: {channel_name}, raw_channel_id: {raw_channel_id}")
                    base_link = "" # Fallback to empty link

                if base_link:
                    post_link = f"{base_link}/{message_id}"
                else:
                    post_link = None
                
                print_info(f"Фильтрация поста ID: {post_id}")
                is_event = await classify_message_with_ollama(content)

                # --- NEW IMAGE HANDLING LOGIC ---
                new_image_url = image_url # Start with existing image_url
                if not new_image_url: # Only process if image_url is missing
                    try:
                        entity = None
                        # Prioritize channel name if it's a username
                        if channel_name and channel_name.startswith('@'):
                            try:
                                entity = await client.get_entity(channel_name)
                            except Exception as e:
                                print_info(f"  > Could not get entity with channel_name '{channel_name}', trying raw_channel_id. Error: {e}")
                        
                        # Fallback to raw_channel_id
                        if not entity and raw_channel_id:
                            try:
                                entity = await client.get_entity(raw_channel_id)
                            except Exception as e:
                                print_error(f"  > Could not get entity with raw_channel_id '{raw_channel_id}'. Error: {e}")

                        if entity:
                            # Fetch the message from Telegram
                            tg_message = await client.get_messages(entity, ids=message_id)
                            if tg_message and tg_message.photo:
                                print_info(f"  > Найдено изображение для поста {post_id}. Загрузка...")
                                photo_bytes = await client.download_media(tg_message.photo, file=bytes)

                                if photo_bytes:
                                    bucket_name = 'events'
                                    file_path = f"Script/{entity.id}/{message_id}.jpg" # Use entity.id for path
                                    storage_url = f"{config['supabase_url']}/storage/v1/object/{bucket_name}/{file_path}"
                                    
                                    storage_headers = {
                                        'apikey': config['supabase_key'],
                                        'Authorization': f"Bearer {config['supabase_key']}",
                                        'Content-Type': 'image/jpeg'
                                    }
                                    
                                    upload_response = await http_client.post(
                                        storage_url,
                                        headers=storage_headers,
                                        content=photo_bytes,
                                        params={"upsert": "true"}
                                    )
                                    upload_response.raise_for_status()
                                    
                                    new_image_url = f"{config['supabase_url']}/storage/v1/object/public/{bucket_name}/{file_path}"
                                    print_success(f"  > Изображение успешно загружено: {new_image_url}")
                        else:
                            print_error(f"  > Не удалось получить entity для поста {post_id}, не можем проверить изображение.")

                    except Exception as e:
                        print_error(f"  > Ошибка обработки изображения для поста {post_id}: {e}")
                # --- END OF NEW LOGIC ---

                update_data = {
                    'is_event_filtered': True,
                    'is_event': is_event,
                    'post_link': post_link,
                    'image_url': new_image_url
                }
                
                update_response = await http_client.patch(
                    f"{config['supabase_url']}/rest/v1/posts?id=eq.{post_id}",
                    headers=headers,
                    json=update_data
                )
                
                if update_response.status_code in [200, 204]:
                    print_success(f"  Пост ID {post_id} обновлен: is_event={is_event}")
                    total_filtered += 1
                else:
                    print_error(f"  Ошибка обновления поста ID {post_id}: {update_response.text}")
            
            result = {
                'status': 'success',
                'posts_filtered': total_filtered,
                'total_posts_found': len(posts_to_filter),
                'timestamp': datetime.now().isoformat()
            }
            
            print_success(f"Фильтрация завершена!")
            print_info(f"Отфильтровано постов: {total_filtered}/{len(posts_to_filter)}")
            
            return result

    finally:
        await client.disconnect()

def main():
    print_header()
    
    try:
        import httpx
        import telethon
    except ImportError as e:
        print_error(f"Отсутствует необходимая библиотека: {e.name}")
        print("Установите зависимости командой:")
        print("  pip install httpx telethon")
        return

    result = asyncio.run(filter_existing_posts())
    
    if result:
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТ:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("="*60)
    else:
        print_error("Фильтрация не удалась")
        sys.exit(1)

if __name__ == '__main__':
    main()