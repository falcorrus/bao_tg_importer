#!/usr/bin/env python3
"""
Telegram to Supabase Importer (Unified Version)
Скрипт для импорта сообщений из Telegram в таблицы posts и events
"""

from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio
import os
import json
from datetime import datetime
import httpx
import sys
import re

from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.types import InputChannel

def print_header():
    print("="*60)
    print("ТЕЛЕГРАМ ИМПОРТЕР (UNIFIED)")
    print("Использует единый промпт и двойную запись в БД")
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

    missing = [key for key, value in config.items() if not value]
    if missing:
        print_error(f"Отсутствуют переменные: {', '.join(missing)}")
        return None
    
    try:
        config['api_id'] = int(config['api_id'])
    except ValueError:
        print_error("TELEGRAM_API_ID должен быть числом")
        return None

    return config

def load_ollama_prompt():
    """Загружает единый промпт из папки !Промты"""
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), '!Промты', 'unified_ollama_prompt.md')
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print_error("Файл !Промты/unified_ollama_prompt.md не найден.")
        return None

OLLAMA_API_URL = os.getenv('OLLAMA_API_URL', 'http://127.0.0.1:11434/api/generate')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma3:latest')
OLLAMA_PROMPT_TEMPLATE = None

def sanitize_data(data: dict) -> dict:
    """Очистка данных перед вставкой в БД"""
    # Обработка цены: только число
    price = data.get('price')
    if price is not None:
        if isinstance(price, (int, float)):
            data['price'] = int(price)
        elif isinstance(price, str):
            match = re.search(r'\d+', price)
            data['price'] = int(match.group(0)) if match else None
        else:
            data['price'] = None

    # Поля NOT NULL (заменяем None на "")
    not_null_fields = ['link_site', 'link_contact', 'where', 'title', 'description', 'link_map', 'currency', 'author_username', 'author_link']
    for field in not_null_fields:
        if data.get(field) is None:
            data[field] = ""

    # Link Map: пробелы -> +
    if data.get('link_map'):
        data['link_map'] = data['link_map'].replace(' ', '+')
    
    return data

async def classify_message_with_ollama(message_content: str) -> list:
    """Анализирует сообщение через Ollama и возвращает список событий"""
    if OLLAMA_PROMPT_TEMPLATE is None:
        return []

    prompt = f"{OLLAMA_PROMPT_TEMPLATE}\n\n{message_content}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                OLLAMA_API_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"},
                timeout=45.0
            )
            response.raise_for_status()
            result = response.json()
            
            if "response" in result:
                raw_res = result["response"].strip()
                # Извлекаем JSON из текста (на случай мусора от Ollama)
                match = re.search(r'(\{.*\}|\[.*\])', raw_res, re.DOTALL)
                clean_res = match.group(0) if match else raw_res
                
                data = json.loads(clean_res)
                return data if isinstance(data, list) else [data]
            return []
        except Exception as e:
            print_error(f"Ошибка Ollama: {e}")
            return []

async def import_telegram_messages():
    """Основная логика импорта"""
    config = load_config()
    if not config: return None

    global OLLAMA_PROMPT_TEMPLATE
    OLLAMA_PROMPT_TEMPLATE = load_ollama_prompt()
    if not OLLAMA_PROMPT_TEMPLATE: return None

    print_info("Подключение к Telegram...")
    client = TelegramClient(StringSession(config['session_string']), config['api_id'], config['api_hash'])
    await client.connect()
    
    try:
        me = await client.get_me()
        print_success(f"Подключились как: {me.first_name}")
        
        async with httpx.AsyncClient() as http_client:
            headers = {
                'apikey': config['supabase_key'],
                'Authorization': f"Bearer {config['supabase_key']}",
                'Content-Type': 'application/json'
            }

            # Получаем список каналов
            response = await http_client.get(f"{config['supabase_url']}/rest/v1/channel_sync_state?select=*", headers=headers)
            channels = response.json()
            print_success(f"Каналов: {len(channels)}")
            
            total_messages = 0
            total_events = 0
            
            for channel in channels:
                channel_name = channel.get('channel_name')
                print_info(f"Обработка {channel_name}...")
                
                try:
                    # Получаем сущность канала
                    try:
                        entity = await client.get_entity(channel.get('channel_id') or channel_name)
                    except Exception:
                        print_error(f"Не удалось найти канал {channel_name}")
                        continue

                    last_id = channel.get('last_processed_message_id', 0) or 0
                    
                    # Определяем топики
                    thread_ids = [channel.get('thread_id')] if channel.get('thread_id') else [None]
                    
                    max_id_overall = last_id
                    
                    for tid in thread_ids:
                        messages = await client.get_messages(entity, limit=20, min_id=last_id, reply_to=tid)
                        if not messages: continue
                        
                        posts_to_insert = []
                        for msg in messages:
                            max_id_overall = max(max_id_overall, msg.id)
                            if not msg.text: continue

                            ollama_results = await classify_message_with_ollama(msg.text)

                            # Извлекаем автора
                            auth_name = ""
                            auth_link = ""
                            if msg.sender:
                                if hasattr(msg.sender, 'username') and msg.sender.username:
                                    auth_name = msg.sender.username
                                    auth_link = f"https://t.me/{auth_name}"
                                elif hasattr(msg.sender, 'id'):
                                    auth_name = f"user_{msg.sender.id}"

                            # Загружаем фото
                            img_url = None
                            if msg.photo:
                                print_info(f"  Загрузка фото {msg.id}...")
                                photo_bytes = await client.download_media(msg.photo, file=bytes)
                                if photo_bytes:
                                    f_path = f"Script/{entity.id}/{msg.id}.jpg"
                                    s_url = f"{config['supabase_url']}/storage/v1/object/events/{f_path}"
                                    await http_client.post(s_url, headers=headers, content=photo_bytes, params={"upsert": "true"})
                                    img_url = f"{config['supabase_url']}/storage/v1/object/public/events/{f_path}"

                            for event in ollama_results:
                                if event and event.get('is_event'):
                                    p_link = f"https://t.me/{entity.username}/{msg.id}" if hasattr(entity, 'username') and entity.username else f"https://t.me/c/{abs(entity.id)}/{msg.id}"
                                    
                                    post_data = {
                                        **event,
                                        'channel_name': channel_name,
                                        'message_id': msg.id,
                                        'content': msg.text,
                                        'description': msg.text, # Принудительно сохраняем переносы строк
                                        'posted_at': msg.date.isoformat(),
                                        'post_link': p_link,
                                        'raw_channel_id': entity.id,
                                        'author_username': auth_name,
                                        'author_link': auth_link,
                                        'city': channel.get('City'),
                                        'is_event_filtered': True
                                    }
                                    
                                    # Fallback для контактов
                                    if not post_data.get('link_contact'):
                                        post_data['link_contact'] = auth_name
                                    
                                    # Изображение
                                    if img_url:
                                        post_data['image'] = img_url

                                    posts_to_insert.append(sanitize_data(post_data))

                        if posts_to_insert:
                            # Вставка в posts (с разделением на пачки для ключей)
                            p_with_img = [p for p in posts_to_insert if p.get('image')]
                            p_no_img = [p for p in posts_to_insert if not p.get('image')]
                            for b in [p_with_img, p_no_img]:
                                if b:
                                    # Гарантируем одинаковые наборы ключей внутри пачки
                                    keys = set().union(*(d.keys() for d in b))
                                    for d in b:
                                        for k in keys:
                                            if k not in d: d[k] = None
                                    await http_client.post(f"{config['supabase_url']}/rest/v1/posts", headers=headers, json=b)
                            
                            # Вставка в events
                            events_to_insert = []
                            for p in posts_to_insert:
                                e = p.copy()
                                e['isAuto'] = True
                                e['author'] = '666408b4-1566-447b-a36c-0e36c9ebc96d'
                                e['link_site'] = p.get('post_link')
                                e['created_at'] = p.get('posted_at')
                                e['description'] = p.get('content') # Оригинал с переносами строк
                                
                                # Удаляем лишние поля
                                for f in ['is_event', 'is_event_filtered', 'raw_channel_id', 'content', 'posted_at']:
                                    e.pop(f, None)
                                
                                # Если картинки нет — удаляем ключ (для дефолта БД)
                                if not e.get('image'): e.pop('image', None)
                                events_to_insert.append(e)
                            
                            # Разделяем на пачки для events
                            ev_with_img = [e for e in events_to_insert if 'image' in e]
                            ev_no_img = [e for e in events_to_insert if 'image' not in e]
                            for ev_b in [ev_with_img, ev_no_img]:
                                if ev_b:
                                    res_ev = await http_client.post(f"{config['supabase_url']}/rest/v1/events", headers=headers, json=ev_b)
                                    if res_ev.status_code in [200, 201]:
                                        print_success(f"Вставлено {len(ev_b)} записей в events.")
                                        total_events += len(ev_b)
                                    else:
                                        print_error(f"Ошибка events: {res_ev.text}")

                    # Обновляем состояние канала
                    if max_id_overall > last_id:
                        await http_client.patch(f"{config['supabase_url']}/rest/v1/channel_sync_state?channel_name=eq.{channel_name}", headers=headers, json={'last_processed_message_id': max_id_overall})

                except Exception as e:
                    print_error(f"Ошибка канала {channel_name}: {e}")

            return {'events': total_events}
    finally:
        await client.disconnect()

if __name__ == '__main__':
    print_header()
    res = asyncio.run(import_telegram_messages())
    print(f"Готово! Импортировано событий: {res.get('events') if res else 0}")