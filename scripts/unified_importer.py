#!/usr/bin/env python3
"""
Unified Telegram to Supabase Importer with Ollama Processing
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
from typing import Optional
import logging
import subprocess

from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.types import InputChannel
from urllib.parse import quote

# Global logger instance
logger = None

def setup_logging():
    global logger
    if logger is not None:
        return logger

    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'importer.log')

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    return logger

# --- Утилиты для вывода --- (теперь используют logger)
def print_header():
    logger.info("="*60)
    logger.info("UNIFIED TELEGRAM & OLLAMA IMPORTER FOR SUPABASE")
    logger.info("="*60)

def print_success(message):
    logger.info(f"✅ {message}")

def print_error(message):
    logger.error(f"❌ {message}")

def print_info(message):
    logger.info(f"ℹ️  {message}")

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- Конфигурация и загрузка ---
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

    channel_id_str = os.getenv('TELEGRAM_TARGET_CHANNEL_ID')
    channel_name = os.getenv('TELEGRAM_TARGET_CHANNEL')

    config = {
        'api_id': os.getenv('TELEGRAM_API_ID'),
        'api_hash': os.getenv('TELEGRAM_API_HASH'),
        'session_string': os.getenv('TELEGRAM_SESSION'),
        'supabase_url': os.getenv('MY_SUPABASE_URL'),
        'supabase_key': os.getenv('MY_SUPABASE_SERVICE_ROLE_KEY'),
        'target_channel': int(channel_id_str) if channel_id_str else None,
        'channel_name': channel_name,
        'gemini_api_key': os.getenv('GEMINI_API_KEY', '').strip(),
        'gemini_model': os.getenv('GEMINI_MODEL', 'gemini-2.0-flash'),
        'check_interval': 300  # 5 минут
    }

    # Проверка наличия обязательных переменных
    missing = []
    if not config['api_id']: missing.append('TELEGRAM_API_ID')
    if not config['api_hash']: missing.append('TELEGRAM_API_HASH')
    if not config['session_string']: missing.append('TELEGRAM_SESSION')
    if not config['supabase_url']: missing.append('MY_SUPABASE_URL')
    if not config['supabase_key']: missing.append('MY_SUPABASE_SERVICE_ROLE_KEY')
    if not config['gemini_api_key']: missing.append('GEMINI_API_KEY')
    
    # target_channel и channel_name теперь опциональны, так как список каналов берется из Supabase
    # if not config['target_channel'] and not config['channel_name']:
    #     missing.append('TELEGRAM_TARGET_CHANNEL_ID or TELEGRAM_TARGET_CHANNEL')

    if missing:
        print_error(f"Отсутствуют следующие переменные: {', '.join(missing)}")
        return None
    
    try:
        config['api_id'] = int(config['api_id'])
    except ValueError:
        print_error("TELEGRAM_API_ID должен быть числом")
        return None

    return config

def load_ollama_prompt():
    """Загружает объединенный промпт для Ollama"""
    try:
        # Путь к файлу промпта (в папке !Промты на уровень выше от папки scripts)
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '!Промты', 'unified_ollama_prompt.md')
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print_error("Файл unified_ollama_prompt.md не найден.")
        return None

# --- Очистка данных ---
def sanitize_data(ollama_data: dict) -> dict:
    """Приводит данные от Ollama в соответствие со схемой Supabase."""
    # Обработка цены: только число или None
    price = ollama_data.get('price')
    if price is not None:
        if isinstance(price, (int, float)):
            ollama_data['price'] = int(price)
        elif isinstance(price, str):
            # Ищем первое число в строке (напр. "1000 руб" -> 1000)
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
    
    # Обработка дат
    when_day = ollama_data.get('whenDay')
    if when_day in ["null", "", None] or (isinstance(when_day, str) and len(when_day) < 5):
        ollama_data['whenDay'] = None
    elif isinstance(when_day, str):
        import datetime
        try:
            if 'T' in when_day:
                when_day = when_day.split('T')[0]
            datetime.datetime.strptime(when_day, '%Y-%m-%d')
            ollama_data['whenDay'] = when_day
        except ValueError:
            ollama_data['whenDay'] = None

    # Исправление NOT NULL полей (заменяем None на пустые строки)
    for field in ['link_site', 'link_contact', 'where', 'title', 'description', 'link_map', 'currency', 'author_username', 'author_link']:
        if ollama_data.get(field) is None:
            ollama_data[field] = ""

    # Обработка link_map: замена пробелов на + для корректного URL
    if ollama_data.get('link_map'):
        ollama_data['link_map'] = ollama_data['link_map'].replace(' ', '+')
    
    return ollama_data

def clean_markdown_html(text: str) -> str:
    """Очищает текст от Markdown и HTML тегов."""
    if not text:
        return ""
    
    # 1. HTML теги
    text = re.sub(r'<[^>]+>', '', text)
    
    # 2. Markdown ссылки [текст](ссылка) -> текст
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    
    # 3. Жирный/Курсив (простой вариант)
    # ***text*** -> text (редкий кейс, но бывает)
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'\1', text)
    text = re.sub(r'___(.*?)___', r'\1', text)
    # **text** -> text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    # *text* -> text
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    
    # 4. Моноширинный (код)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'```(.*?)```', r'\1', text, flags=re.DOTALL)
    
    return text.strip()

def normalize_text(text: str) -> str:
    """Приводит текст в более удобный для LLM формат."""
    if not text:
        return ""
    
    # Словарь для замены месяцев в верхнем регистре на title case
    month_map = {
        'ЯНВАРЯ': 'января', 'ФЕВРАЛЯ': 'февраля', 'МАРТА': 'марта',
        'АПРЕЛЯ': 'апреля', 'МАЯ': 'мая', 'ИЮНЯ': 'июня',
        'ИЮЛЯ': 'июля', 'АВГУСТА': 'августа', 'СЕНТЯБРЯ': 'сентября',
        'ОКТЯБРЯ': 'октября', 'НОЯБРЯ': 'ноября', 'ДЕКАБРЯ': 'декабря'
    }
    
    # Заменяем месяцы, используя re.sub с функцией для независимости от регистра
    def replace_month(match):
        return month_map.get(match.group(0).upper(), match.group(0))

    # Создаем паттерн (ЯНВАРЯ|ФЕВРАЛЯ|...|ДЕКАБРЯ)
    month_pattern = re.compile('|'.join(month_map.keys()), re.IGNORECASE)
    
    text = month_pattern.sub(replace_month, text)
    
    return text

# --- Whitelists for Supabase Tables ---
ALLOWED_EVENT_FIELDS = {
    'id', 'created_at', 'image', 'title', 'title_dop', 'description', 
    'whenDay', 'whenTime', 'link_site', 'price', 'where', 'author', 
    'link_map', 'link_contact', 'isAvailable', 'city', 'currency', 
    'isPriceFrom', 'category', 'isAuto', 'isOnline', 'author_username', 
    'author_link', 'post_link', 'message_id', 'channel_name'
}

ALLOWED_POST_FIELDS = {
    'id', 'channel_name', 'message_id', 'content', 'posted_at', 
    'is_event_filtered', 'is_event', 'post_link', 'raw_channel_id', 
    'image_url', 'created_at', 'image', 'title', 'title_dop', 
    'description', 'whenDay', 'whenTime', 'link_site', 'price', 
    'where', 'author', 'link_map', 'link_contact', 'isAvailable', 
    'city', 'currency', 'isPriceFrom', 'category', 'isOnline', 
    'author_username', 'author_link'
}

def filter_fields(data: dict, allowed_fields: set) -> dict:
    """Removes keys that are not in the allowed_fields set."""
    return {k: v for k, v in data.items() if k in allowed_fields}

async def check_event_exists_in_db(http_client, config, title, when_day, headers):
    """Checks if an event with the same title and date already exists in Supabase."""
    if not title or not when_day:
        return False
        
    try:
        # Normalize title slightly if needed, but 'eq' is safest for now
        encoded_title = quote(title)
        # Using exact match for title and whenDay
        url = f"{config['supabase_url']}/rest/v1/events?whenDay=eq.{when_day}&title=eq.{encoded_title}&select=id"
        
        resp = await http_client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return len(data) > 0
    except Exception as e:
        print_error(f"    Ошибка при проверке дубликатов: {e}")
        return False

# --- Взаимодействие с Gemini ---
async def process_message_with_gemini(content: str, config: dict, prompt_template: str, message_date: datetime) -> Optional[dict]:
    """
    Анализирует сообщение с помощью Google Gemini, классифицирует его и извлекает JSON.
    """
    if not prompt_template:
        print_error("Шаблон промпта не загружен.")
        return None

    # Нормализуем текст перед отправкой
    normalized_content = normalize_text(content)

    # Форматируем дату сообщения для контекста
    context_date_str = message_date.strftime('%Y-%m-%d (%A)')
    
    # Добавляем контекст даты перед контентом сообщения
    full_prompt_content = f"CURRENT CONTEXT DATE (Post Date): {context_date_str}\n\nMESSAGE CONTENT:\n{normalized_content}"
    
    # Configure Gemini
    genai.configure(api_key=config['gemini_api_key'])
    
    generation_config = {
        "temperature": 0.1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
    }
    
    model = genai.GenerativeModel(
        model_name=config['gemini_model'],
        generation_config=generation_config,
        system_instruction=prompt_template
    )
    
    max_retries = 5
    base_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            print_info(f"  Отправка запроса в Gemini (попытка {attempt + 1})...")
            # Run in executor to not block asyncio loop since genai is synchronous
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: model.generate_content(full_prompt_content))
            
            try:
                json_data = json.loads(response.text)
                print_success("  Gemini вернула валидный JSON.")
                # Much smaller delay for paid tier
                await asyncio.sleep(0.5) 
                return json_data
            except json.JSONDecodeError as e:
                print_error(f"  Ошибка парсинга JSON от Gemini: {e}")
                print_error(f"  Полученный ответ: {response.text}")
                return None
            except Exception as e:
                print_error(f"  Ошибка обработки ответа Gemini: {e}")
                return None
                
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                delay = base_delay * (2 ** attempt)
                print_info(f"  ⚠️ Лимит (429). Ждем {delay} сек...")
                await asyncio.sleep(delay)
            else:
                print_error(f"  Ошибка запроса к Gemini: {e}")
                return None
    
    print_error("  Не удалось получить ответ от Gemini после нескольких попыток.")
    return None

# --- Основная логика импорта ---
async def import_and_process_messages():
    """Основная функция импорта и обработки сообщений"""
    config = load_config()
    if not config:
        return None

    prompt_template = load_ollama_prompt()
    if not prompt_template:
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
        if me is None:
            print_error("Не удалось аутентифицироваться в Telegram. Сессия невалидна.")
            print_error("Пожалуйста, пересоздайте строку сессии (TELEGRAM_SESSION) и обновите ее в .env файле.")
            return None # Выходим из функции
        print_success(f"Подключились как: {me.first_name} (@{me.username or 'N/A'})")
        
        print_info("Подключение к Supabase...")
        async with httpx.AsyncClient() as http_client:
            headers = {
                'apikey': config['supabase_key'],
                'Authorization': f"Bearer {config['supabase_key']}",
                'Content-Type': 'application/json'
            }

            print_info("Получение списка каналов для синхронизации...")
            response = await http_client.get(
                f"{config['supabase_url']}/rest/v1/channel_sync_state?select=*",
                headers=headers
            )
            response.raise_for_status()
            channels = response.json()
            print_success(f"Найдено {len(channels)} каналов для синхронизации")
            
            total_synced = 0
            total_messages_processed = 0
            total_events_imported = 0
            
            for channel in channels:
                channel_name = channel.get('channel_name', str(channel['channel_id']))
                print_header()
                print_info(f"Обработка канала: {channel_name}")
                
                try:
                    posts_to_insert = []  # Initialize the list to collect posts for insertion - moved to start of channel processing for safety
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
                        
                        # Автоматическое обновление channel_id, если он был найден
                        if entity:
                            try:
                                # Формируем правильный ID (с префиксом -100 для каналов)
                                new_channel_id = entity.id
                                # Telethon часто возвращает ID без префикса -100 для каналов
                                if not str(new_channel_id).startswith('-100'):
                                    new_channel_id = int(f"-100{new_channel_id}")
                                
                                print_info(f"  ℹ️ Обнаружен отсутствующий channel_id. Сохраняем найденный ID: {new_channel_id}")
                                
                                row_id = channel.get('id')
                                if row_id:
                                    update_data = {'channel_id': new_channel_id}
                                    update_response = await http_client.patch(
                                        f"{config['supabase_url']}/rest/v1/channel_sync_state?id=eq.{row_id}",
                                        headers=headers,
                                        json=update_data
                                    )
                                    if update_response.status_code < 300:
                                        print_success(f"  ✅ channel_id успешно обновлен в базе (ID строки: {row_id})")
                                    else:
                                        print_error(f"  ❌ Ошибка обновления channel_id в базе: {update_response.text}")
                            except Exception as e:
                                print_error(f"  ⚠️ Не удалось автоматически обновить channel_id: {e}")
                    
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
                                limit=50, # Increased limit to 50 to match original unified_importer.py
                                min_id=last_id
                            )
                        else:
                            current_messages = await client.get_messages(
                                entity,
                                limit=50, # Increased limit to 50 to match original unified_importer.py
                                min_id=last_id,
                                reply_to=thread_id_param
                            )
                        
                        if not current_messages:
                            print_info(f"  Нет новых сообщений в {topic_label}.")
                            continue
                            
                        print_success(f"  Найдено {len(current_messages)} новых сообщений в {topic_label}.")
                        
                        for msg in reversed(current_messages): # Обрабатываем в хронологическом порядке
                            total_messages_processed += 1
                            max_id_overall = max(max_id_overall, msg.id)

                            if not msg.text:
                                continue

                            ollama_data = await process_message_with_gemini(msg.text, config, prompt_template, msg.date)

                            # --- Поддержка массива объектов или одиночного объекта ---
                            results_to_process = []
                            if isinstance(ollama_data, list):
                                results_to_process = ollama_data
                            elif isinstance(ollama_data, dict):
                                results_to_process = [ollama_data]
                            
                            for item in results_to_process:
                                # Событие, если есть флаг is_event ИЛИ если есть хотя бы дата и заголовок (иногда нейронка забывает флаг в массиве)
                                is_actually_event = item.get('is_event') or (item.get('whenDay') and item.get('title'))
                                
                                if item and is_actually_event:
                                    # Очистка и подготовка данных
                                    cleaned_data = sanitize_data(item)

                                    # Проверяем, является ли событие валидным (существует дата whenDay)
                                    when_day = cleaned_data.get('whenDay')
                                    original_is_event = True
                                    if when_day is None:
                                        print_info(f"  Сообщение {msg.id} - отсутствует дата события (whenDay пустое).")
                                        cleaned_data['is_event'] = False
                                        original_is_event = False
                                    else:
                                        total_events_imported += 1

                                    image_url = None
                                    if msg.photo:
                                        print_info(f"    Загрузка изображения из сообщения {msg.id}...")
                                        photo_bytes = await client.download_media(msg.photo, file=bytes)
                                        if photo_bytes:
                                            bucket_name = 'events'
                                            current_date = datetime.now().strftime('%Y-%m-%d')
                                            file_path = f"{current_date}/{entity.id}/{msg.id}.jpg"
                                            storage_url = f"{config['supabase_url']}/storage/v1/object/{bucket_name}/{file_path}"
                                            storage_headers = {
                                                'apikey': config['supabase_key'],
                                                'Authorization': f"Bearer {config['supabase_key']}",
                                                'Content-Type': 'image/jpeg'
                                            }
                                            
                                            try:
                                                upload_response = await http_client.put(storage_url, headers=storage_headers, content=photo_bytes)
                                                upload_response.raise_for_status()
                                                image_url = f"{config['supabase_url']}/storage/v1/object/public/{bucket_name}/{file_path}"
                                                print_success(f"    Изображение успешно загружено: {image_url}")
                                            except Exception as e:
                                                print_error(f"    Ошибка загрузки изображения: {e}")

                                    if hasattr(entity, 'username') and entity.username:
                                        base_link = f"https://t.me/{entity.username}"
                                    else:
                                        base_link = f"https://t.me/c/{abs(entity.id)}"

                                    if thread_id_param is not None and thread_id_param != 1:
                                        post_link = f"{base_link}/{thread_id_param}/{msg.id}"
                                    else:
                                        post_link = f"{base_link}/{msg.id}"

                                    author_username = ""
                                    author_link = ""
                                    if msg.sender:
                                        if hasattr(msg.sender, 'username') and msg.sender.username:
                                            author_username = msg.sender.username
                                            author_link = f"https://t.me/{msg.sender.username}"
                                        elif hasattr(msg.sender, 'id'):
                                            author_username = f"user_{msg.sender.id}"
                                            author_link = ""

                                    # Собираем финальный объект для вставки
                                    cleaned_text = clean_markdown_html(msg.text)
                                    final_post_data = {
                                        **cleaned_data,
                                        'channel_name': f"@{entity.username}" if hasattr(entity, 'username') and entity.username else f"channel_{entity.id}",
                                        'message_id': msg.id,
                                        'content': cleaned_text,
                                        'description': cleaned_text, # Принудительно используем очищенный текст
                                        'posted_at': msg.date.isoformat(),
                                        'post_link': post_link,
                                        'raw_channel_id': entity.id,
                                        'is_event_filtered': original_is_event,
                                        'author_username': author_username,
                                        'author_link': author_link,
                                        'city': channel.get('City')
                                    }
                                    
                                    # Добавляем картинку только если она есть, чтобы сработал дефолт в БД
                                    if image_url:
                                        final_post_data['image'] = image_url
                                        final_post_data['image_url'] = image_url

                                    # ЛОГИКА: если link_contact пуст, используем author_username
                                    if not final_post_data.get('link_contact'):
                                        final_post_data['link_contact'] = author_username

                                    # Финальная санитария ПЕРЕД добавлением в список
                                    final_post_data = sanitize_data(final_post_data)
                                    posts_to_insert.append(final_post_data)
                                    print_success(f"  Событие из сообщения {msg.id} добавлено в очередь на вставку.")


                        
                        if posts_to_insert:
                            print_info(f"  Вставка {len(posts_to_insert)} записей в Supabase (таблицы posts и events)...")
                            try:
                                # 1. Вставка в таблицу posts (лог)
                                # ЛОГИКА: если city == 1, в posts НЕ сохраняем
                                posts_for_log = [p for p in posts_to_insert if p.get('city') != 1]
                                
                                if posts_for_log:
                                    # Разделяем на пачки с одинаковыми ключами, чтобы избежать ошибки PGRST102
                                    posts_with_img = [p for p in posts_for_log if p.get('image')]
                                    posts_no_img = [p for p in posts_for_log if not p.get('image')]

                                    for batch in [posts_with_img, posts_no_img]:
                                        if batch:
                                            # Filter fields for posts table
                                            batch = [filter_fields(p, ALLOWED_POST_FIELDS) for p in batch]
                                            
                                            # Гарантируем одинаковые наборы ключей внутри пачки
                                            keys = set().union(*(d.keys() for d in batch))
                                            for d in batch:
                                                for k in keys:
                                                    if k not in d: d[k] = None

                                            resp = await http_client.post(f"{config['supabase_url']}/rest/v1/posts", headers=headers, json=batch)
                                            resp.raise_for_status()
                                    print_success(f"  Успешно вставлено {len(posts_for_log)} записей в таблицу 'posts'.")
                                else:
                                    print_info("  Пропуск вставки в 'posts' (все записи имеют city=1).")

                                # 2. Вставка в таблицу events (всегда сохраняем валидные события)
                                events_to_insert = []
                                for p in posts_to_insert:
                                    if p.get('is_event_filtered'):
                                        event_entry = p.copy()
                                        event_entry['isAuto'] = True
                                        event_entry['author'] = '666408b4-1566-447b-a36c-0e36c9ebc96d'
                                        
                                        if not event_entry.get('description') and p.get('content'):
                                            event_entry['description'] = p.get('content')
                                        if p.get('posted_at'):
                                            event_entry['created_at'] = p.get('posted_at')
                                        if p.get('post_link'):
                                            event_entry['link_site'] = p.get('post_link')
                                        if not event_entry.get('link_contact'):
                                            event_entry['link_contact'] = p.get('author_username')

                                        # Note: Manual popping of tech_fields is no longer strictly necessary 
                                        # because of filter_fields, but we keep the logic clean.
                                        
                                        # Если картинки нет — удаляем ключ (для дефолта БД)
                                        if not event_entry.get('image'):
                                            event_entry.pop('image', None)
                                        
                                        # --- DEDUPLICATION LOGIC START ---
                                        current_title = event_entry.get('title')
                                        current_day = event_entry.get('whenDay')

                                        # A. Local Batch Deduplication
                                        is_local_duplicate = False
                                        for existing in events_to_insert:
                                            if existing.get('title') == current_title and existing.get('whenDay') == current_day:
                                                is_local_duplicate = True
                                                break
                                        
                                        if is_local_duplicate:
                                            print_info(f"    ⚠️ Пропуск локального дубликата: {current_title} ({current_day})")
                                            continue

                                        # B. Database Deduplication
                                        if await check_event_exists_in_db(http_client, config, current_title, current_day, headers):
                                            print_info(f"    ⚠️ Пропуск дубликата (найден в БД): {current_title} ({current_day})")
                                            continue
                                        # --- DEDUPLICATION LOGIC END ---

                                        events_to_insert.append(event_entry)

                                if events_to_insert:
                                    # Также разделяем на пачки для events
                                    ev_with_img = [e for e in events_to_insert if 'image' in e]
                                    ev_no_img = [e for e in events_to_insert if 'image' not in e]

                                    for ev_batch in [ev_with_img, ev_no_img]:
                                        if ev_batch:
                                            # Filter fields for events table
                                            ev_batch = [filter_fields(e, ALLOWED_EVENT_FIELDS) for e in ev_batch]

                                            # Гарантируем одинаковые наборы ключей внутри пачки
                                            keys = set().union(*(d.keys() for d in ev_batch))
                                            for d in ev_batch:
                                                for k in keys:
                                                    if k not in d: d[k] = None

                                            resp = await http_client.post(f"{config['supabase_url']}/rest/v1/events", headers=headers, json=ev_batch)
                                            if resp.status_code not in [200, 201, 204]:
                                                print_error(f"  ОШИБКА 'events': {resp.status_code} - {resp.text}")
                                            else:
                                                print_success(f"  Успешно вставлено {len(ev_batch)} записей в таблицу 'events'.")

                                posts_to_insert = []
                            except Exception as e:
                                print_error(f"  Критическая ошибка вставки: {e}")

                    # Обновление last_processed_message_id
                    if max_id_overall > last_id:
                        print_info(f"  Обновление last_processed_message_id на {max_id_overall}...")
                        update_response = await http_client.patch(
                            f"{config['supabase_url']}/rest/v1/channel_sync_state?channel_name=eq.{channel.get('channel_name')}",
                            headers=headers,
                            json={'last_processed_message_id': max_id_overall}
                        )
                        if update_response.status_code in [200, 204]:
                            print_success(f"  Состояние для канала {channel_name} обновлено.")
                            total_synced += 1
                        else:
                            print_error(f"  Ошибка обновления состояния: {update_response.text}")
                
                except Exception as e:
                    print_error(f"Критическая ошибка при обработке канала {channel_name}: {e}")
                    continue
            
            result = {
                'status': 'success',
                'channels_synced': total_synced,
                'total_channels': len(channels),
                'messages_processed': total_messages_processed,
                'events_imported': total_events_imported,
                'timestamp': datetime.now().isoformat()
            }
            return result
    
    except Exception as e:
        print_error(f"Критическая ошибка: {e}")
        return None
    finally:
        await client.disconnect()
        print_info("Отключились от Telegram.")

def main():
    setup_logging() # Call setup_logging here
    print_header()
    try:
        import telethon, httpx
    except ImportError as e:
        print_error(f"Отсутствует необходимая библиотека: {e.name}. Установите ее: pip install telethon httpx")
        sys.exit(1)

    result = asyncio.run(import_and_process_messages())
    
    if result:
        print_info("\n" + "="*60)
        print_info("РЕЗУЛЬТАТ ВЫПОЛНЕНИЯ:")
        print_info(json.dumps(result, indent=2, ensure_ascii=False))
        print_info("="*60)

        # --- Логирование в файл log.md ---
        try:
            # Путь к log.md (на уровень выше от папки scripts)
            log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log.md')
            
            # Формируем строку: 2026-01-22 07:00 events_imported: 0
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            events_count = result.get('events_imported', 0)
            log_line = f"{timestamp} events_imported: {events_count}\n"
            
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(log_line)
            print_success(f"Запись добавлена в лог: {log_path}")
            
        except Exception as e:
            print_error(f"Не удалось записать в log.md: {e}")
        # ---------------------------------

        if sys.platform == 'darwin':
            events_imported = result.get('events_imported', 0)
            if events_imported > 0:
                message = f"Успешно вставлено {events_imported} записей"
                title = "Unified Importer"
                os.system(f"osascript -e 'display notification \"{message}\" with title \"{title}\"' ")
            else:
                message = "Нет новых событий для импорта."
                title = "Unified Importer"
                os.system(f"osascript -e 'display notification \"{message}\" with title \"{title}\"' ")
    else:
        print_error("Выполнение завершилось с ошибкой.")
        if sys.platform == 'darwin':
            message = "Импорт завершился с ошибкой."
            title = "Unified Importer"
            os.system(f"osascript -e 'display notification \"{message}\" with title \"{title}\"' ")
        sys.exit(1)

    # Pause briefly before closing
    import time
    time.sleep(2)

if __name__ == '__main__':
    main()
