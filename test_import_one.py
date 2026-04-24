import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import httpx

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

async def test_import():
    load_env()
    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_string = os.getenv("TELEGRAM_SESSION")
    
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    
    channel_id = -1001799634358 # @brfloripa
    thread_id = 135711 # NOT the thread of the message
    last_id = 194424
    
    print(f"Fetching messages for channel {channel_id}, thread {thread_id}, min_id {last_id}")
    
    entity = await client.get_entity(channel_id)
    current_messages = await client.get_messages(
        entity,
        limit=50,
        min_id=last_id,
        reply_to=thread_id
    )
    
    if not current_messages:
        print("NO NEW MESSAGES FOUND!")
    else:
        print(f"Found {len(current_messages)} messages.")
        for msg in current_messages:
            print(f"ID: {msg.id}, Text: {msg.text[:50]}...")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_import())
