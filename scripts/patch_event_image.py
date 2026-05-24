#!/usr/bin/env python3
"""
Патч: обновляет image для существующего события в Supabase
по названию (title), генерируя фото через Gemini Imagen.

Использование:
  python3 scripts/patch_event_image.py --title "Камерный вечер для романтичных девушек"
  python3 scripts/patch_event_image.py --id 658
"""

import os
import sys
import asyncio
import argparse
import base64
import httpx
from datetime import datetime
from io import BytesIO
from PIL import Image

# ── Загрузка .env ──────────────────────────────────────────────────────────────
def load_config():
    for env_path in ['.env', '../.env']:
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
    return {
        'supabase_url': os.getenv('MY_SUPABASE_URL'),
        'supabase_key': os.getenv('MY_SUPABASE_SERVICE_ROLE_KEY'),
        'gemini_api_key': os.getenv('GEMINI_API_KEY', '').strip(),
    }


# ── Генерация изображения ──────────────────────────────────────────────────────
async def generate_image(prompt: str, api_key: str, client: httpx.AsyncClient) -> bytes | None:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-ultra-generate-001:predict?key={api_key}"
    payload = {
        "instances": [{"prompt": f"Cinematic, high-quality photorealistic image for an event: {prompt[:800]}. Minimalistic design. Any text shown on the image MUST be in clear, meaningful Russian language only. Avoid garbled or meaningless characters."}],
        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}
    }
    resp = await client.post(url, json=payload, timeout=60.0)
    if resp.status_code != 200:
        print(f"❌ Imagen API error {resp.status_code}: {resp.text}")
        return None
    data = resp.json()
    b64 = data.get('predictions', [{}])[0].get('bytesBase64Encoded')
    if not b64:
        print("❌ Нет bytesBase64Encoded в ответе")
        return None
    return base64.b64decode(b64)


# ── Сжатие изображения ─────────────────────────────────────────────────────────
def compress(image_bytes: bytes, max_kb: int = 500) -> bytes:
    max_bytes = max_kb * 1024
    if len(image_bytes) <= max_bytes:
        return image_bytes
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    for quality in range(85, 35, -10):
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        result = buf.getvalue()
        if len(result) <= max_bytes:
            print(f"  Сжато до {len(result)//1024}КБ (quality={quality})")
            return result
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=40, optimize=True)
    return buf.getvalue()


# ── Основная логика ────────────────────────────────────────────────────────────
async def patch(event_id: int | None, title: str | None):
    config = load_config()
    if not config['supabase_url'] or not config['supabase_key']:
        print("❌ Не найдены SUPABASE credentials в .env")
        sys.exit(1)

    headers = {
        'apikey': config['supabase_key'],
        'Authorization': f"Bearer {config['supabase_key']}",
        'Content-Type': 'application/json',
        'Prefer': 'return=representation',
    }

    async with httpx.AsyncClient() as client:
        # ── 1. Найти событие ───────────────────────────────────────────────────
        if event_id:
            url = f"{config['supabase_url']}/rest/v1/events?id=eq.{event_id}&select=id,title,description,image"
        else:
            encoded = title.replace(' ', '%20')
            url = f"{config['supabase_url']}/rest/v1/events?title=ilike.%25{encoded}%25&select=id,title,description,image&limit=5"

        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        events = resp.json()

        if not events:
            print("❌ Событие не найдено в базе данных")
            return

        # Если несколько — показать и взять первое
        if len(events) > 1:
            print(f"Найдено {len(events)} событий, обновляем первое:")
            for e in events:
                print(f"  [{e['id']}] {e['title']} | image: {bool(e.get('image'))}")

        event = events[0]
        print(f"\n📌 Событие: [{event['id']}] {event['title']}")
        print(f"   Текущее image: {event.get('image') or '(пусто)'}")

        # ── 2. Генерация фото ──────────────────────────────────────────────────
        prompt = event.get('description') or event.get('title') or "Интересное мероприятие"
        print(f"\n🎨 Генерируем изображение...")
        photo_bytes = await generate_image(prompt, config['gemini_api_key'], client)
        
        template_url = "https://nvodtxeehqnreyjuijsl.supabase.co/storage/v1/object/public/icons//event_gemini.jpeg"
        image_url = None

        if photo_bytes:
            print(f"   Размер оригинала: {len(photo_bytes)//1024}КБ")
            photo_bytes = compress(photo_bytes, max_kb=500)

            # ── 3. Загрузка в Supabase Storage ────────────────────────────────────
            date_str = datetime.now().strftime('%Y-%m-%d')
            file_path = f"{date_str}/patched/{event['id']}.jpg"
            storage_url = f"{config['supabase_url']}/storage/v1/object/events/{file_path}"
            storage_headers = {
                'apikey': config['supabase_key'],
                'Authorization': f"Bearer {config['supabase_key']}",
                'Content-Type': 'image/jpeg',
            }

            up = await client.put(storage_url, headers=storage_headers, content=photo_bytes)
            if up.status_code in (200, 201):
                image_url = f"{config['supabase_url']}/storage/v1/object/public/events/{file_path}"
                print(f"✅ Загружено: {image_url}")
            else:
                print(f"❌ Ошибка загрузки в Storage: {up.status_code} {up.text}")
                image_url = template_url
        else:
            print("❌ Не удалось сгенерировать изображение, используем шаблон")
            image_url = template_url

        # ── 4. Обновление записи в БД ─────────────────────────────────────────
        if image_url:
            patch_url = f"{config['supabase_url']}/rest/v1/events?id=eq.{event['id']}"
            patch_resp = await client.patch(patch_url, headers=headers, json={'image': image_url})
            if patch_resp.status_code < 300:
                print(f"✅ Событие [{event['id']}] обновлено в БД: image = {image_url}")
            else:
                print(f"❌ Ошибка обновления БД: {patch_resp.status_code} {patch_resp.text}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Патч: добавить/обновить фото события')
    parser.add_argument('--id', type=int, help='ID события в Supabase')
    parser.add_argument('--title', type=str, help='Часть названия события для поиска')
    args = parser.parse_args()

    if not args.id and not args.title:
        parser.print_help()
        sys.exit(1)

    asyncio.run(patch(args.id, args.title))
