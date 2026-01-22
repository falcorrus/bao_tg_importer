from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio

# Ваши данные
api_id = 25727332
api_hash = '4306a0f13e21c95832ecd8c35cafffbb'
session_string = '1AZWarzoBu5YZIqdyYINwAwIbHqCxBPVzAL26nvywGQ7shpFn7nQ_sNfgFGeo7ih03U6ZlooOsjkvT0L9lajULRenBP90dAWmc9iLZodQG_t8aC5RhzEZ6pdMU_mRBC-knDuVAXpJJokLIPoeQvms11jiiGzDEaDTzznnEW9-R7IpgZbxxQa5NRyUSkyKPX66LBL1tCy7LB-7dHW_bA6CCL2QrOD0jbKLu5qtfpVnYOZyHa64kGxg1tQJfYZenPEMqz3xHFPM1xmtH26hn4PAYtdBI2L043PjBAszl2ELTIjtXqCOqmfS77o1f0xELV3eIsrYxhsHSg9c_I0QKQiMqJkIQd9VdKE='  # ВСТАВЬТЕ СЮДА ВАШ SESSION STRING после генерации

# Идентификатор чата (может быть @username или числовой ID)
chat_identifier = '@argentina_afisha'

async def get_chat_info():
    if not session_string:
        print('❌ Ошибка: Сначала получите session string!')
        print('Запустите: python3 generate_session.py')
        return
    
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        print('❌ Session невалидна! Получите новую через generate_session.py')
        return
    
    print(f'\n🔍 Получение информации о: {chat_identifier}\n')
    
    try:
        entity = await client.get_entity(chat_identifier)
        
        print('='*70)
        print('📊 ИНФОРМАЦИЯ О ЧАТЕ/КАНАЛЕ:')
        print('='*70)
        print(f'ID: {entity.id}')
        print(f'Название: {entity.title}')
        print(f'Username: {entity.username if hasattr(entity, "username") else "N/A"}')
        print(f'Тип: {entity.__class__.__name__}')
        
        if hasattr(entity, 'megagroup'):
            print(f'Мегагруппа (чат): {entity.megagroup}')
        if hasattr(entity, 'broadcast'):
            print(f'Канал (broadcast): {entity.broadcast}')
        
        print('='*70)
        
        # Попробуем получить последние сообщения
        print('\n📨 Получение последних сообщений...\n')
        messages = await client.get_messages(entity, limit=5)
        
        print(f'Получено сообщений: {len(messages)}')
        
        for i, msg in enumerate(messages, 1):
            print(f'\nСообщение {i}:')
            print(f'  ID: {msg.id}')
            print(f'  Дата: {msg.date}')
            print(f'  Текст: {msg.text[:100] if msg.text else "[нет текста]"}...')
            print(f'  От: {msg.sender_id}')
        
        print('\n' + '='*70)
        print('✅ ИСПОЛЬЗУЙТЕ В БАЗЕ ДАННЫХ:')
        print('='*70)
        print(f'\nУдалите старую запись:')
        print(f"DELETE FROM channel_sync_state WHERE channel_id = '{chat_identifier}';")
        print(f'\nДобавьте новую с правильным ID:')
        print(f"INSERT INTO channel_sync_state (channel_id, last_processed_message_id)")
        print(f"VALUES ('{entity.id}', 0);")
        print('\n' + '='*70)
        
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        print(f'\n💡 Возможные причины:')
        print(f'   - Неправильный username (должен начинаться с @)')
        print(f'   - Вы не состоите в этом чате/канале')
        print(f'   - Чат/канал приватный и недоступен')
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(get_chat_info())