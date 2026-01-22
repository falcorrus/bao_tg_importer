from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetHistoryRequest
import asyncio

# Ваши данные
api_id = 25727332
api_hash = '4306a0f13e21c95832ecd8c35cafffbb'
session_string = '1AZWarzoBu5YZIqdyYINwAwIbHqCxBPVzAL26nvywGQ7shpFn7nQ_sNfgFGeo7ih03U6ZlooOsjkvT0L9lajULRenBP90dAWmc9iLZodQG_t8aC5RhzEZ6pdMU_mRBC-knDuVAXpJJokLIPoeQvms11jiiGzDEaDTzznnEW9-R7IpgZbxxQa5NRyUSkyKPX66LBL1tCy7LB-7dHW_bA6CCL2QrOD0jbKLu5qtfpVnYOZyHa64kGxg1tQJfYZenPEMqz3xHFPM1xmtH26hn4PAYtdBI2L043PjBAszl2ELTIjtXqCOqmfS77o1f0xELV3eIsrYxhsHSg9c_I0QKQiMqJkIQd9VdKE='

chat_identifier = '@argentina_afisha'  # или '@argentina_afisha'

async def test_methods():
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    
    print('='*70)
    print(f'🔍 Тестирование разных методов для: {chat_identifier}')
    print('='*70)
    
    try:
        entity = await client.get_entity(chat_identifier)
        print(f'\n✅ Канал найден: {entity.title} (ID: {entity.id})')
        
        # МЕТОД 1: client.get_messages (стандартный)
        print('\n' + '-'*70)
        print('МЕТОД 1: client.get_messages()')
        print('-'*70)
        try:
            messages1 = await client.get_messages(entity, limit=10)
            print(f'✅ Получено: {len(messages1)} сообщений')
            if messages1:
                print(f'Последнее сообщение ID: {messages1[0].id}')
                print(f'Текст: {messages1[0].text[:100] if messages1[0].text else "[медиа]"}')
        except Exception as e:
            print(f'❌ Ошибка: {e}')
        
        # МЕТОД 2: Итератор iter_messages
        print('\n' + '-'*70)
        print('МЕТОД 2: client.iter_messages() [ИТЕРАТОР]')
        print('-'*70)
        try:
            messages2 = []
            async for message in client.iter_messages(entity, limit=10):
                messages2.append(message)
            print(f'✅ Получено: {len(messages2)} сообщений')
            if messages2:
                print(f'Последнее сообщение ID: {messages2[0].id}')
                print(f'Текст: {messages2[0].text[:100] if messages2[0].text else "[медиа]"}')
        except Exception as e:
            print(f'❌ Ошибка: {e}')
        
        # МЕТОД 3: GetHistoryRequest (низкоуровневый API)
        print('\n' + '-'*70)
        print('МЕТОД 3: GetHistoryRequest() [LOW-LEVEL API]')
        print('-'*70)
        try:
            result = await client(GetHistoryRequest(
                peer=entity,
                offset_id=0,
                offset_date=None,
                add_offset=0,
                limit=10,
                max_id=0,
                min_id=0,
                hash=0
            ))
            print(f'✅ Получено: {len(result.messages)} сообщений')
            if result.messages:
                msg = result.messages[0]
                print(f'Последнее сообщение ID: {msg.id}')
                print(f'Текст: {msg.message[:100] if hasattr(msg, "message") and msg.message else "[медиа]"}')
        except Exception as e:
            print(f'❌ Ошибка: {e}')
        
        # МЕТОД 4: Проверка с reverse=True (сначала старые)
        print('\n' + '-'*70)
        print('МЕТОД 4: iter_messages(reverse=True) [СТАРЫЕ СНАЧАЛА]')
        print('-'*70)
        try:
            messages4 = []
            async for message in client.iter_messages(entity, limit=10, reverse=True):
                messages4.append(message)
            print(f'✅ Получено: {len(messages4)} сообщений')
            if messages4:
                print(f'Самое старое сообщение ID: {messages4[0].id}')
                print(f'Текст: {messages4[0].text[:100] if messages4[0].text else "[медиа]"}')
        except Exception as e:
            print(f'❌ Ошибка: {e}')
        
        # МЕТОД 5: Получить информацию о канале
        print('\n' + '-'*70)
        print('МЕТОД 5: Информация о канале')
        print('-'*70)
        try:
            full = await client.get_entity(entity)
            print(f'Тип: {full.__class__.__name__}')
            if hasattr(full, 'restricted'):
                print(f'Ограничен: {full.restricted}')
            if hasattr(full, 'participants_count'):
                print(f'Участников: {full.participants_count}')
            if hasattr(full, 'megagroup'):
                print(f'Мегагруппа: {full.megagroup}')
            if hasattr(full, 'broadcast'):
                print(f'Канал (broadcast): {full.broadcast}')
        except Exception as e:
            print(f'❌ Ошибка: {e}')
        
        # МЕТОД 6: Проверить подписку
        print('\n' + '-'*70)
        print('МЕТОД 6: Проверка участия в канале')
        print('-'*70)
        try:
            me = await client.get_me()
            participants = await client.get_participants(entity, limit=1)
            print(f'✅ Доступ к списку участников: Да')
            
            # Проверяем, подписаны ли мы
            dialogs = await client.get_dialogs()
            is_subscribed = any(d.id == entity.id for d in dialogs)
            print(f'Подписаны на канал: {"✅ Да" if is_subscribed else "❌ Нет"}')
            
        except Exception as e:
            print(f'Статус подписки: {e}')
        
        print('\n' + '='*70)
        print('РЕКОМЕНДАЦИЯ:')
        print('='*70)
        
        methods_worked = []
        if 'messages1' in locals() and messages1:
            methods_worked.append('get_messages')
        if 'messages2' in locals() and messages2:
            methods_worked.append('iter_messages')
        if 'result' in locals() and result.messages:
            methods_worked.append('GetHistoryRequest')
        if 'messages4' in locals() and messages4:
            methods_worked.append('iter_messages(reverse=True)')
        
        if methods_worked:
            print(f'✅ Работающие методы: {", ".join(methods_worked)}')
            print(f'\nИспользуйте метод: {methods_worked[0]}')
        else:
            print('❌ НИ ОДИН метод не вернул сообщения!')
            print('\nВозможные причины:')
            print('1. Вы не подписаны на канал (подпишитесь в Telegram)')
            print('2. Канал запретил доступ к истории сообщений')
            print('3. Канал пустой (нет сообщений)')
            print('4. Нужны права администратора')
            print('\n💡 Попробуйте:')
            print('1. Подписаться на канал в Telegram')
            print('2. Написать в канале хотя бы одно сообщение')
            print('3. Использовать другой канал для теста')
        
    except Exception as e:
        print(f'\n❌ Критическая ошибка: {e}')
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(test_methods())