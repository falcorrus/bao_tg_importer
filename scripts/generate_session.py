from telethon import TelegramClient
from telethon.sessions import StringSession

# Ваши данные из https://my.telegram.org/apps
api_id = 25727332
api_hash = '4306a0f13e21c95832ecd8c35cafffbb'

# Ваш личный номер телефона
phone = '+5548992012727'

print('Connecting to Telegram...\n')

async def main():
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start(phone=phone)
    
    print('\n' + '='*70)
    print('SESSION STRING:')
    print('='*70)
    session_string = client.session.save()
    print(session_string)
    print('='*70)
    print('\nCommand for Supabase:')
    print(f'supabase secrets set TELEGRAM_SESSION="{session_string}"')
    
    await client.disconnect()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
