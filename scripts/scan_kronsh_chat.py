#!/usr/bin/env python3
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession
from google import genai
from google.genai import types as genai_types
import httpx

# Определяем пути к файлам относительно скрипта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
ENV_PATH = os.path.join(PARENT_DIR, ".env")
PARTNERS_DOC_PATH = "/Users/eugene/MyProjects/floripaguru/!Docs/partners.md"
STATE_FILE_PATH = os.path.join(BASE_DIR, "scan_state.json")

# Загружаем переменные окружения вручную
config = {}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, val = line.split("=", 1)
            config[key.strip()] = val.strip().strip('"').strip("'")

# Валидация необходимых переменных
required_keys = ["TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION"]
missing = [k for k in required_keys if k not in config]
if missing:
    print(f"❌ Ошибка: В файле {ENV_PATH} отсутствуют ключи: {', '.join(missing)}")
    sys.exit(1)

api_id = int(config["TELEGRAM_API_ID"])
api_hash = config["TELEGRAM_API_HASH"]
session_string = config["TELEGRAM_SESSION"]
gemini_key = config.get("GEMINI_API_KEY")
openrouter_key = config.get("OPENROUTER_API_KEY")
use_openrouter = config.get("USE_OPENROUTER", "false").lower() == "true"
use_ollama = config.get("USE_OLLAMA", "false").lower() == "true"
ollama_url = config.get("OLLAMA_API_URL", "http://127.0.0.1:11434/api/generate")

async def call_ollama_local(chat_text: str, prompt_instruction: str) -> str:
    # Очередь локальных моделей по приоритету
    env_model = config.get("OLLAMA_MODEL", "")
    models = []
    if env_model:
        models.append(env_model)
    
    # Резервные модели на VPS
    for m in ["gemma4:12b-it-qat", "gemma4:e4b"]:
        if m not in models:
            models.append(m)
            
    for model in models:
        print(f"🤖 Запрос в локальную Ollama (модель: {model})...")
        payload = {
            "model": model,
            "prompt": f"{prompt_instruction}\n\nПЕРЕПИСКА:\n{chat_text}",
            "stream": False
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as httpx_client:
                res = await httpx_client.post(ollama_url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    content = data.get("response", "").strip()
                    if content:
                        print(f"✅ Успешный ответ от локальной Ollama ({model})")
                        return content
                else:
                    print(f"⚠️ Ошибка Ollama ({model}): {res.status_code} - {res.text}")
        except Exception as e:
            print(f"⚠️ Исключение при запросе Ollama ({model}): {e}")
    return ""

async def call_llm(chat_text: str) -> str:
    """Отправляет переписку в LLM для извлечения договоренностей."""
    prompt_instruction = (
        "Ты — аналитический ИИ-ассистент. Проанализируй следующую переписку с Иваном Кроншем (@kronsht).\n"
        "Выдели важные договоренности, новые идеи, финансовые условия, цены или задачи.\n"
        "Верни результат в виде краткого списка в формате Markdown. Формат заголовка пункта: ГГГГ-ММ-ДД: [Тема].\n"
        "Если в переписке нет никаких новых договоренностей, цен или идей (просто бытовой диалог, приветствия или обсуждение решенных вопросов),\n"
        "ответь строго одним словом: NO_IMPORTANT_INFO.\n"
        "Будь лаконичен, не пиши вводных слов, пиши сразу факты."
    )

    # 1. Если включена Ollama по умолчанию — пробуем сначала ее
    if use_ollama:
        res_ollama = await call_ollama_local(chat_text, prompt_instruction)
        if res_ollama:
            return res_ollama

    # 2. Пробуем OpenRouter
    if use_openrouter and openrouter_key:
        # Пул бесплатных моделей для отказоустойчивости
        primary_model = config.get("OPENROUTER_MODEL", "google/gemini-2.5-flash:free")
        models_to_try = [primary_model]
        
        fallbacks = [
            "google/gemini-2.5-flash:free",
            "meta-llama/llama-3.3-70b-instruct", # paid
            "deepseek/deepseek-chat",
            "qwen/qwen-2.5-72b-instruct:free",
            "meta-llama/llama-3-8b-instruct:free"
        ]
        for f_model in fallbacks:
            if f_model not in models_to_try:
                models_to_try.append(f_model)

        api_url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json"
        }

        for model in models_to_try:
            print(f"🤖 Запрос в OpenRouter (модель: {model})...")
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": prompt_instruction},
                    {"role": "user", "content": f"ПЕРЕПИСКА:\n{chat_text}"}
                ],
                "temperature": 0.1
            }
            try:
                async with httpx.AsyncClient(timeout=60.0) as httpx_client:
                    res = await httpx_client.post(api_url, headers=headers, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        content = data["choices"][0]["message"]["content"].strip()
                        if content:
                            print(f"✅ Успешный ответ от OpenRouter ({model})")
                            return content
                    else:
                        print(f"⚠️ Ошибка OpenRouter ({model}): {res.status_code} - {res.text}")
            except Exception as e:
                print(f"⚠️ Исключение при запросе OpenRouter ({model}): {e}")

    # 3. Fallback на Gemini API
    if gemini_key:
        print("🤖 Запрос в Google Gemini...")
        try:
            client = genai.Client(api_key=gemini_key)
            generate_config = genai_types.GenerateContentConfig(
                temperature=0.1,
                system_instruction=prompt_instruction
            )
            model_name = config.get("GEMINI_MODEL", "gemini-2.0-flash")
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=f"ПЕРЕПИСКА:\n{chat_text}",
                config=generate_config
            )
            return response.text.strip()
        except Exception as e:
            print(f"❌ Исключение при запросе Gemini: {e}")

    # 4. Последний рубеж: если Ollama не была запущена первой, пробуем ее как крайний вариант
    if not use_ollama:
        res_ollama = await call_ollama_local(chat_text, prompt_instruction)
        if res_ollama:
            return res_ollama
            
    return "NO_IMPORTANT_INFO"

async def main():
    print(f"🕒 Запуск сканирования чата с @kronsht в {datetime.now().isoformat()}")
    
    # Инициализация Telethon клиента
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("❌ Ошибка: Сессия Telegram невалидна! Запустите generate_session.py.")
        await client.disconnect()
        return

    try:
        # Находим чат с Иваном Кроншем
        print("🔍 Поиск чата с @kronsht...")
        entity = await client.get_entity("@kronsht")
        print(f"✅ Чат найден. ID: {entity.id}, Имя: {entity.first_name} {entity.last_name or ''}")
        
        # Считываем состояние последнего обработанного сообщения
        last_processed_id = 0
        if os.path.exists(STATE_FILE_PATH):
            try:
                with open(STATE_FILE_PATH, "r") as f:
                    state = json.load(f)
                    last_processed_id = state.get("last_processed_id", 0)
            except Exception as e:
                print(f"⚠️ Ошибка при чтении state-файла: {e}")

        # Считываем сообщения
        print(f"📥 Считывание сообщений после ID: {last_processed_id}...")
        messages = []
        async for msg in client.iter_messages(entity, min_id=last_processed_id, limit=200):
            # Пропускаем сообщения без текста
            if not msg.text:
                continue
            messages.append(msg)

        if not messages:
            print("📭 Нет новых сообщений для обработки.")
            await client.disconnect()
            return

        # Разворачиваем в хронологический порядок
        messages.reverse()
        max_message_id = max(msg.id for msg in messages)

        # Собираем переписку в текст
        chat_lines = []
        for msg in messages:
            sender = "Иван Кронш" if msg.sender_id == entity.id else "Я"
            time_str = msg.date.strftime("%Y-%m-%d %H:%M:%S")
            chat_lines.append(f"{sender} ({time_str}): {msg.text}")
        
        chat_text = "\n".join(chat_lines)
        print(f"📊 Собрано {len(messages)} новых сообщений для анализа.")

        # Вызываем LLM для анализа
        llm_response = await call_llm(chat_text)

        if not llm_response or llm_response.strip() == "NO_IMPORTANT_INFO":
            print("💤 ИИ не обнаружил важных договоренностей или идей в новых сообщениях.")
        else:
            print("🔥 Обнаружены важные договоренности! Добавление в лог...")
            
            # Дописываем в конец файла !Docs/Партнёры.md
            if os.path.exists(PARTNERS_DOC_PATH):
                with open(PARTNERS_DOC_PATH, "a", encoding="utf-8") as f:
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    f.write(f"\n\n### Автоматический лог переписки от {today_str}\n")
                    f.write(f"{llm_response}\n")
                print(f"📝 Данные успешно записаны в {PARTNERS_DOC_PATH}")
                
                # Запускаем садовника для обновления Obsidian локально
                try:
                    print("🌳 Запуск садовника для синхронизации с Obsidian...")
                    os.system("python3 /Users/eugene/.gemini/commands/garden_updater.py")
                except Exception as e:
                    print(f"⚠️ Ошибка при запуске садовника: {e}")
            else:
                print(f"❌ Ошибка: Файл {PARTNERS_DOC_PATH} не найден!")

        # Обновляем состояние последнего обработанного ID
        with open(STATE_FILE_PATH, "w") as f:
            json.dump({"last_processed_id": max_message_id, "updated_at": datetime.now().isoformat()}, f)
        print(f"💾 Состояние обновлено. Последний ID: {max_message_id}")

    except Exception as e:
        print(f"❌ Критическая ошибка во время работы скрипта: {e}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
