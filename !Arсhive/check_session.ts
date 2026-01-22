import { TelegramClient, StringSession } from 'https://deno.land/x/grm/mod.ts';

async function checkTelegramSession() {
  console.log("--- Telegram Session Checker ---");
  
  // Получаем значения из переменных окружения
  const envApiId = Deno.env.get("TELEGRAM_API_ID");
  const envApiHash = Deno.env.get("TELEGRAM_API_HASH");
  const envSession = Deno.env.get("TELEGRAM_SESSION");

  if (!envApiId || !envApiHash || !envSession) {
    console.error("Environment variables TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_SESSION are required.");
    return;
  }

  const apiId = parseInt(envApiId);
  const apiHash = envApiHash;
  const sessionString = envSession;

  if (isNaN(apiId) || !apiHash || !sessionString) {
    console.error("Valid API ID, API HASH, and SESSION string are required.");
    return;
  }

  const stringSession = new StringSession(sessionString);
  const client = new TelegramClient(stringSession, apiId, apiHash, {
    connectionRetries: 5,
  });

  try {
    console.log("Connecting to Telegram...");
    await client.connect();

    // Проверим, авторизован ли пользователь
    try {
      const me = await client.getMe();
      console.log(`\n✓ Successfully authenticated as: ${me.firstName} (@${me.username || 'N/A'})`);
    } catch (error) {
      console.error(`\n✗ Failed to get user info: ${error}`);
      return;
    }

    // Попробуем получить последние сообщения из сохраненных (Saved Messages)
    console.log("\n--- Testing with Saved Messages ---");
    try {
      const savedMessages = await client.getMessages('me', { limit: 5 });
      console.log(`✓ Found ${savedMessages.length} messages in Saved Messages`);
      
      for (let i = 0; i < Math.min(2, savedMessages.length); i++) {
        const msg = savedMessages[i];
        console.log(`  Message #${i + 1}: ID=${msg.id}, Date=${new Date(msg.date * 1000).toISOString()}, Text=${msg.text ? msg.text.substring(0, 100) : '[No text]'}`);
      }
    } catch (error) {
      console.error(`✗ Failed to get Saved Messages: ${error}`);
    }

    // Попробуем получить сообщения из "инбокса" (последние диалоги)
    console.log("\n--- Testing with Dialogs ---");
    try {
      const dialogs = await client.getDialogs({ limit: 10 });
      console.log(`✓ Found ${dialogs.length} dialogs/chats`);
      
      for (let i = 0; i < Math.min(5, dialogs.length); i++) {
        const dialog = dialogs[i];
        console.log(`  Dialog #${i + 1}: ${dialog.title} (ID: ${dialog.entity?.id || 'N/A'})`);
      }
    } catch (error) {
      console.error(`✗ Failed to get dialogs: ${error}`);
    }

    // Проверим конкретный публичный канал для сравнения
    console.log("\n--- Testing with a known public channel ---");
    try {
      // Попробуем популярный публичный канал как точка сравнения
      const publicChannel = await client.getEntity('@telegram');
      const publicMessages = await client.getMessages(publicChannel, { limit: 5 });
      console.log(`✓ Public channel '@telegram' found. Messages: ${publicMessages.length}`);
      
      for (let i = 0; i < Math.min(2, publicMessages.length); i++) {
        const msg = publicMessages[i];
        console.log(`  Message #${i + 1}: ID=${msg.id}, Date=${new Date(msg.date * 1000).toISOString()}, Text=${msg.text ? msg.text.substring(0, 100) : '[No text]'}`);
      }
    } catch (error) {
      console.error(`✗ Could not access public channel: ${error}`);
    }

  } catch (error) {
    console.error("Error occurred:", error);
  } finally {
    await client.disconnect();
    console.log("\nDisconnected from Telegram.");
  }
}

checkTelegramSession();