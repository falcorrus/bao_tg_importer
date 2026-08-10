import asyncio
import json
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

# Manual .env parser
env_vars = {}
env_path = "/Users/eugene/MyProjects/myScripts/bao_tg_importer/.env"
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env_vars[key.strip()] = val.strip().strip('"').strip("'")

API_ID = int(env_vars.get("TELEGRAM_API_ID"))
API_HASH = env_vars.get("TELEGRAM_API_HASH")
SESSION_STR = env_vars.get("TELEGRAM_SESSION")

CHANNEL_USERNAME = "HelpinFloripa"

async def export_channel():
    print(f"Connecting to Telegram for channel: {CHANNEL_USERNAME}...")
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("Error: Telethon session is not authorized!")
        await client.disconnect()
        return

    print(f"Authorized successfully. Resolving entity {CHANNEL_USERNAME}...")
    try:
        entity = await client.get_entity(CHANNEL_USERNAME)
        print(f"Channel title: {getattr(entity, 'title', 'Unknown')} (ID: {entity.id})")
    except Exception as e:
        print(f"Failed to resolve channel entity: {e}")
        await client.disconnect()
        return

    print("Fetching all messages from channel...")
    messages_data = []
    count = 0

    async for msg in client.iter_messages(entity):
        count += 1
        if count % 100 == 0:
            print(f"Fetched {count} messages so far...")

        msg_dict = {
            "id": msg.id,
            "date": msg.date.isoformat() if msg.date else None,
            "text": msg.text or "",
            "views": msg.views,
            "forwards": msg.forwards,
            "reply_to_msg_id": msg.reply_to.reply_to_msg_id if msg.reply_to else None,
            "media_type": type(msg.media).__name__ if msg.media else None,
            "url": f"https://t.me/{CHANNEL_USERNAME}/{msg.id}"
        }
        messages_data.append(msg_dict)

    await client.disconnect()
    print(f"Total messages fetched: {len(messages_data)}")

    # Sort chronological (oldest to newest)
    messages_data.sort(key=lambda x: x["id"])

    # Output directory
    out_dir = "/Users/eugene/MyProjects/floripaguru/data"
    os.makedirs(out_dir, exist_ok=True)

    json_file = os.path.join(out_dir, "helpinfloripa_telegram_all.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(messages_data, f, ensure_ascii=False, indent=2)

    print(f"Saved JSON to: {json_file}")

    # Create Markdown summary
    md_file = os.path.join(out_dir, "helpinfloripa_telegram_all.md")
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(f"# Telegram Export: @{CHANNEL_USERNAME}\n\n")
        f.write(f"Total Messages: {len(messages_data)}\n\n")
        for m in messages_data:
            if not m["text"].strip():
                continue
            f.write(f"## Message #{m['id']} - {m['date']}\n")
            f.write(f"**Link:** [{m['url']}]({m['url']})\n\n")
            f.write(f"{m['text']}\n\n")
            f.write("---\n\n")

    print(f"Saved Markdown to: {md_file}")

if __name__ == "__main__":
    asyncio.run(export_channel())
