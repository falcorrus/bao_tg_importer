#!/usr/bin/env python3
"""
Ollama Supa JSON Extractor
Скрипт для извлечения структурированных данных из постов с помощью Ollama 
и обновления таблицы posts в Supabase.
"""

import asyncio
import os
import json
import httpx
import sys
from datetime import datetime

def print_header():
    print("="*60)
    print("OLLAMA JSON EXTRACTOR ДЛЯ SUPABASE")
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
        'supabase_url': os.getenv('MY_SUPABASE_URL', '').strip(),
        'supabase_key': os.getenv('MY_SUPABASE_SERVICE_ROLE_KEY', '').strip()
    }

    missing = [key for key, value in config.items() if not value]
    if missing:
        print_error(f"Отсутствуют следующие переменные: {', '.join(missing)}")
        print("\nПожалуйста, установите переменные окружения:")
        print("  MY_SUPABASE_URL, MY_SUPABASE_SERVICE_ROLE_KEY")
        return None
    
    return config

def load_ollama_prompt():
    """Загружает промпт для Ollama из единого файла unified_ollama_prompt.md"""
    try:
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '!Промты', 'unified_ollama_prompt.md')
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print_error("Файл unified_ollama_prompt.md не найден в папке !Промты.")
        return None

OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', 'http://127.0.0.1:11434/api/generate')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma3:latest')
OLLAMA_PROMPT_TEMPLATE = None

async def extract_json_with_ollama(content: str) -> list | None:
    """
    Извлекает структурированные JSON данные из текста с помощью Ollama.
    Возвращает список объектов (событий).
    """
    if OLLAMA_PROMPT_TEMPLATE is None:
        print_error("Шаблон промпта Ollama не загружен.")
        return None

    prompt = f"{OLLAMA_PROMPT_TEMPLATE}\n\n{content}"
    
    async with httpx.AsyncClient() as client:
        try:
            print_info("  Отправка запроса в Ollama...")
            response = await client.post(
                OLLAMA_API_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=60.0
            )
            response.raise_for_status()
            result = response.json()
            
            if "response" in result:
                try:
                    data = json.loads(result["response"])
                    
                    if isinstance(data, list):
                        print_success(f"  Ollama вернула массив из {len(data)} элементов.")
                        return data
                    elif isinstance(data, dict):
                        print_success("  Ollama вернула одиночный JSON объект.")
                        return [data]
                    else:
                        print_error(f"  Неожиданный формат данных от Ollama: {type(data)}")
                        return None
                except json.JSONDecodeError as e:
                    print_error(f"  Ошибка парсинга JSON от Ollama: {e}")
                    print_error(f"  Полученный ответ: {result['response']}")
                    return None
            else:
                print_error(f"  Неожиданный ответ от Ollama (нет поля 'response'): {result}")
                return None
            
        except Exception as e:
            print_error(f"  Ошибка при работе с Ollama: {e}")
            return None

def sanitize_data(ollama_data: dict) -> dict:
    """Приводит данные от Ollama в соответствие со схемой Supabase."""
    # Обработка цены: только число или None
    price = ollama_data.get('price')
    if price is not None:
        if isinstance(price, (int, float)):
            ollama_data['price'] = int(price)
        elif isinstance(price, str):
            import re
            match = re.search(r'\d+', price)
            if match:
                ollama_data['price'] = int(match.group(0))
            else:
                ollama_data['price'] = None
        else:
            ollama_data['price'] = None
    
    # Обработка категории: только int
    category = ollama_data.get('category')
    if category is not None:
        try:
            ollama_data['category'] = int(category)
        except (ValueError, TypeError):
            ollama_data['category'] = 0

    # Обработка isOnline: только bool
    is_online = ollama_data.get('isOnline')
    if is_online is not None:
        if isinstance(is_online, str):
            ollama_data['isOnline'] = is_online.lower() in ['true', 'yes', '1']
        else:
            ollama_data['isOnline'] = bool(is_online)
    else:
        ollama_data['isOnline'] = False

    # Исправление NOT NULL полей (заменяем None на пустые строки)
    for field in ['link_site', 'link_contact', 'where', 'title', 'description', 'link_map', 'currency', 'author_username', 'author_link']:
        if ollama_data.get(field) is None:
            ollama_data[field] = ""

    # Обработка link_map: замена пробелов на + для корректного URL
    if ollama_data.get('link_map'):
        ollama_data['link_map'] = ollama_data['link_map'].replace(' ', '+')

    return ollama_data

async def update_posts_with_ollama_json():
    """Основная функция для обновления постов"""
    config = load_config()
    if not config:
        return None

    global OLLAMA_PROMPT_TEMPLATE
    OLLAMA_PROMPT_TEMPLATE = load_ollama_prompt()
    if OLLAMA_PROMPT_TEMPLATE is None:
        return None

    print_info("Подключение к Supabase...")
    
    async with httpx.AsyncClient() as http_client:
        headers = {
            'apikey': config['supabase_key'],
            'Authorization': f"Bearer {config['supabase_key']}",
            'Content-Type': 'application/json'
        }

        # Получаем посты, которые являются событиями, но еще не обработаны (title is null)
        print_info("Получение списка необработанных событий из Supabase...")
        try:
            response = await http_client.get(
                f"{config['supabase_url']}/rest/v1/posts?is_event=eq.true&title=is.null",
                headers=headers
            )
            response.raise_for_status()
        except Exception as e:
            print_error(f"Ошибка получения постов: {e}")
            return None

        posts = response.json()
        if not posts:
            print_success("Нет новых событий для обработки.")
            return {
                'status': 'success',
                'posts_processed': 0,
                'posts_updated': 0,
                'posts_created': 0,
                'timestamp': datetime.now().isoformat()
            }
            
        print_success(f"Найдено {len(posts)} постов для обработки.")
        
        updated_count = 0
        created_count = 0
        for i, post in enumerate(posts):
            post_id = post['id']
            post_content = post['content']
            
            print_header()
            print_info(f"Обработка поста ID: {post_id} ({i + 1}/{len(posts)})")

            if not post_content or not post_content.strip():
                print_info("  Пост пропущен (пустой контент).")
                continue

            extracted_events = await extract_json_with_ollama(post_content)

            if extracted_events:
                # Список для массовой вставки в таблицу events
                events_to_sync = []

                # 1. Первый объект используем для ОБНОВЛЕНИЯ текущей записи в posts
                first_event = sanitize_data(extracted_events[0])
                try:
                    print_info(f"  Обновление основного поста ID: {post_id} в таблице posts...")
                    update_response = await http_client.patch(
                        f"{config['supabase_url']}/rest/v1/posts?id=eq.{post_id}",
                        headers=headers,
                        json=first_event
                    )
                    update_response.raise_for_status()
                    print_success(f"  Пост {post_id} успешно обновлен в posts.")
                    updated_count += 1

                    # Подготавливаем для вставки в events
                    event_for_sync = {
                        **first_event,
                        'channel_name': post.get('channel_name'),
                        'message_id': post.get('message_id'),
                        'content': post.get('content'),
                        'description': post.get('content'), # Оригинал с переносами строк
                        'posted_at': post.get('posted_at'),
                        'post_link': post.get('post_link'),
                        'city': post.get('city'),
                        'isAuto': True,
                        'author': '666408b4-1566-447b-a36c-0e36c9ebc96d'
                    }
                    
                    if post.get('posted_at'):
                        event_for_sync['created_at'] = post.get('posted_at')

                    # Специальные требования: link_site = post_link
                    if post.get('post_link'):
                        event_for_sync['link_site'] = post.get('post_link')
                    
                    # ЛОГИКА: если link_contact пуст, используем channel_name или author_username
                    if not event_for_sync.get('link_contact'):
                        # В этой таблице у нас есть channel_name, используем его как fallback
                        event_for_sync['link_contact'] = post.get('author_username') or post.get('channel_name')
                        
                    # Удаляем поля, которых нет в events
                    for f in ['is_event', 'is_event_filtered', 'raw_channel_id', 'content', 'image_url', 'posted_at']:
                        event_for_sync.pop(f, None)
                    events_to_sync.append(event_for_sync)

                except Exception as e:
                    print_error(f"  Ошибка обновления поста {post_id}: {e}")

                # 2. Остальные объекты (если есть) используем для СОЗДАНИЯ новых записей
                if len(extracted_events) > 1:
                    print_info(f"  Найдено дополнительных дат: {len(extracted_events) - 1}. Создание новых записей в posts...")
                    
                    additional_posts = []
                    for extra_event in extracted_events[1:]:
                        extra_clean = sanitize_data(extra_event)
                        new_post = {
                            **extra_clean,
                            'channel_name': post.get('channel_name'),
                            'message_id': post.get('message_id'),
                            'content': post.get('content'),
                            'posted_at': post.get('posted_at'),
                            'post_link': post.get('post_link'),
                            'raw_channel_id': post.get('raw_channel_id'),
                            'image': post.get('image'),
                            'city': post.get('city'),
                            'is_event_filtered': post.get('is_event_filtered', True)
                        }
                        additional_posts.append(new_post)
                        
                        # Также готовим для вставки в events
                        event_extra = new_post.copy()
                        event_extra['isAuto'] = True
                        event_extra['author'] = '666408b4-1566-447b-a36c-0e36c9ebc96d'
                        event_extra['description'] = post.get('content') # Оригинал с переносами строк
                        
                        if new_post.get('posted_at'):
                            event_extra['created_at'] = new_post.get('posted_at')

                        # Специальные требования: link_site = post_link
                        if new_post.get('post_link'):
                            event_extra['link_site'] = new_post.get('post_link')
                        
                        # ЛОГИКА: если link_contact пуст, используем author_username
                        if not event_extra.get('link_contact'):
                            event_extra['link_contact'] = new_post.get('author_username')

                        # Если картинки нет, удаляем поле для дефолта БД
                        if not event_extra.get('image'):
                            event_extra.pop('image', None)
                            
                        for f in ['is_event', 'is_event_filtered', 'raw_channel_id', 'content', 'image_url', 'posted_at']:
                            event_extra.pop(f, None)
                        events_to_sync.append(event_extra)
                    
                    try:
                        create_response = await http_client.post(
                            f"{config['supabase_url']}/rest/v1/posts",
                            headers=headers,
                            json=additional_posts
                        )
                        create_response.raise_for_status()
                        print_success(f"  Успешно создано {len(additional_posts)} дополнительных записей в posts.")
                        created_count += len(additional_posts)
                    except Exception as e:
                        print_error(f"  Ошибка при создании дополнительных записей в posts: {e}")

                # 3. СИНХРОНИЗАЦИЯ С ТАБЛИЦЕЙ events
                if events_to_sync:
                    try:
                        print_info(f"  Синхронизация {len(events_to_sync)} записей с таблицей events...")
                        
                        # Разделяем на пачки с одинаковыми ключами (из-за поля image)
                        ev_with_img = [e for e in events_to_sync if 'image' in e]
                        ev_no_img = [e for e in events_to_sync if 'image' not in e]

                        for ev_batch in [ev_with_img, ev_no_img]:
                            if ev_batch:
                                sync_response = await http_client.post(
                                    f"{config['supabase_url']}/rest/v1/events",
                                    headers=headers,
                                    json=ev_batch
                                )
                                sync_response.raise_for_status()
                        
                        print_success(f"  Таблица events успешно обновлена.")
                    except Exception as e:
                        print_error(f"  Ошибка синхронизации с events: {e}")

        result = {
            'status': 'success',
            'posts_processed': len(posts),
            'posts_updated': updated_count,
            'posts_created': created_count,
            'timestamp': datetime.now().isoformat()
        }
        return result

        result = {
            'status': 'success',
            'posts_processed': len(posts),
            'posts_updated': updated_count,
            'timestamp': datetime.now().isoformat()
        }
        return result

def main():
    print_header()
    
    try:
        import httpx
    except ImportError as e:
        print_error(f"Отсутствует необходимая библиотека: {e.name}")
        print("Установите зависимости командой: pip install httpx")
        return

    result = asyncio.run(update_posts_with_ollama_json())
    
    if result:
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТ:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("="*60)
    else:
        print_error("Обработка не удалась")
        sys.exit(1)

if __name__ == '__main__':
    main()
