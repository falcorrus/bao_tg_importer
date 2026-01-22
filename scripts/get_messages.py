from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio
import sys

async def get_channel_messages():
    print("--- Telegram Channel Messages Getter ---")
    
    api_id = int(input("Enter your API ID: "))
    api_hash = input("Enter your API HASH: ")
    session_string = input("Enter your SESSION string: ")
    channel_input = input("Enter channel name or ID (e.g., @channel_name or -1001234567890): ")

    client = TelegramClient(StringSession(session_string), api_id, api_hash)

    try:
        print("Connecting to Telegram...")
        await client.connect()

        # Check if we're authorized
        if not await client.is_user_authorized():
            print("Session is not authorized. Please generate a new session.")
            return

        print("Fetching messages from channel...")
        
        try:
            # Try to get the entity first to confirm access
            entity = await client.get_entity(channel_input)
            print(f'Successfully accessed channel: {entity.title} (ID: {entity.id})')
        except Exception as e:
            print(f'Failed to access channel: {e}')
            return

        # Get messages from the channel
        messages = await client.get_messages(entity, limit=10)  # Get last 10 messages

        print(f'\nFound {messages.total if hasattr(messages, "total") else len(messages) if messages else 0} messages in the channel:')
        
        if messages:
            for i, msg in enumerate(messages):
                print(f'\nMessage #{i + 1}:')
                print(f'  ID: {msg.id}')
                print(f'  Date: {msg.date}')
                print(f'  Text: {msg.text[:200] + "..." if msg.text and len(msg.text) > 200 else msg.text or "[No text]"}')
                
                # Check if message has media
                if msg.media:
                    print(f'  Media: Yes')
        else:
            print("No messages found in the channel.")

        # Now try with min_id filter similar to your function
        print("\n--- Testing with min_id filter (like in your function) ---")
        filtered_messages = await client.get_messages(entity, limit=10, min_id=0)

        print(f'With min_id filter, found {len(filtered_messages) if filtered_messages else 0} messages:')
        if filtered_messages:
            for i, msg in enumerate(filtered_messages):
                print(f'  Message ID: {msg.id}, Date: {msg.date}, Text: {msg.text[:100] if msg.text else "[No text]"}')
        else:
            print("  No messages found with min_id filter.")

    except Exception as error:
        print(f"Error occurred: {error}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()
        print("\nDisconnected from Telegram.")

if __name__ == '__main__':
    asyncio.run(get_channel_messages())