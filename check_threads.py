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

async def check_thread():
    load_env()
    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_string = os.getenv("TELEGRAM_SESSION")
    
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    
    channel_id = -1001799634358 # @brfloripa
    for tid in [135711, 2179, 2588, 2186]:
        print(f"Checking thread {tid}...")
        messages = await client.get_messages(channel_id, limit=1, reply_to=tid)
        for msg in messages:
            print(f"  Latest ID: {msg.id}, Date: {msg.date}")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(check_thread())
