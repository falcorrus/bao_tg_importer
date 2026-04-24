import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
def load_env():
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

async def check_messages():
    load_env()
    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_string = os.getenv("TELEGRAM_SESSION")
    
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    
    channel_id = -1001799634358 # @brfloripa
    thread_id = 2186 # Творчество
    
    print(f"Checking thread {thread_id} in channel {channel_id}...")
    
    messages = await client.get_messages(channel_id, limit=5, reply_to=thread_id, min_id=194424)
    if not messages:
        print("NO NEW MESSAGES found with min_id=194424")
    for msg in messages:
        print(f"ID: {msg.id}, Date: {msg.date}, Text: {msg.text[:50]}...")
        if "акриловый мастер-класс" in (msg.text or ""):
            print("FOUND IT!")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(check_messages())
