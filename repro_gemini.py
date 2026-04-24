import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def test_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    
    with open("!Промты/unified_ollama_prompt.md", "r") as f:
        prompt_template = f.read()
        
    text = """Всем привет! 24 апреля в пятницу приглашаю на акриловый мастер-класс во взрослую мини-группу любого уровня художественной подготовки, и без неё 😉🖌🎨
По времени рассчитываем на +/- 2,5 часа
Канасвейрас.

Кто меня не знает, мои работы, и как проходят МК в группах со взрослыми можно посмотреть здесь:

https://www.instagram.com/yulia.ievskaya?igsh=MTBjZGRpajl4dmp2cw==

*можно выбрать другое изображение, главное что-то тропическое по теме"""

    context_date = "2026-04-23 (Thursday)"
    full_prompt_content = f"CURRENT CONTEXT DATE (Post Date): {context_date}\n\nMESSAGE CONTENT:\n{text}"
    
    generation_config = {
        "temperature": 0.1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_mime_type": "application/json",
    }
    
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config=generation_config,
        system_instruction=prompt_template
    )
    
    response = model.generate_content(full_prompt_content)
    print(response.text)

if __name__ == "__main__":
    test_gemini()
