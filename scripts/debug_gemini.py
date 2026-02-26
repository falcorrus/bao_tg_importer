import os
import json
import asyncio
from datetime import datetime
import google.generativeai as genai

def load_config():
    env_path = '/Users/eugene/MyProjects/myScripts/bao_tg_importer/.env'
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value.replace('"', '').replace("'", "")
    return {
        'gemini_api_key': os.getenv('GEMINI_API_KEY'),
        'gemini_model': os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
    }

def load_prompt():
    prompt_path = '/Users/eugene/MyProjects/myScripts/bao_tg_importer/!Промты/unified_ollama_prompt.md'
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()

async def test():
    config = load_config()
    prompt_template = load_prompt()
    
    content = """МАФИЯ РУССКАЯ + АНГЛИЙСКАЯ 

‼️ Играем в субботу, 28 февраля

🕠 Сбор в 18.00

📍Дон Культуры, Acevedo 1091

💰 7000 ARS

У маньяка есть шанс сыграть этот и следующий вечер бесплатно 🤑"""

    message_date = datetime(2026, 2, 26) 
    context_date_str = message_date.strftime('%Y-%m-%d (%A)')
    full_prompt_content = f"CURRENT CONTEXT DATE (Post Date): {context_date_str}\n\nMESSAGE CONTENT:\n{content}"
    
    genai.configure(api_key=config['gemini_api_key'])
    model = genai.GenerativeModel(
        model_name=config['gemini_model'],
        generation_config={"response_mime_type": "application/json", "temperature": 0.1},
        system_instruction=prompt_template
    )
    
    loop = asyncio.get_event_loop()
    print("Отправка в Gemini...")
    response = await loop.run_in_executor(None, lambda: model.generate_content(full_prompt_content))
    print("ОТВЕТ ОТ GEMINI:")
    print(response.text)
    
    try:
        data = json.loads(response.text)
        print("\nАНАЛИЗ ПОЛЕЙ:")
        print(f"is_event: {data.get('is_event')}")
        print(f"whenDay: {data.get('whenDay')}")
        print(f"where: {data.get('where')}")
    except Exception as e:
        print(f"Ошибка парсинга: {e}")

if __name__ == "__main__":
    asyncio.run(test())
