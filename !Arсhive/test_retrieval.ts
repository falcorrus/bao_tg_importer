import { TelegramClient, StringSession } from 'https://deno.land/x/grm/mod.ts';

async function testMessageRetrieval() {
  console.log("--- Testing Message Retrieval ---");
  
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

    // Проверим, может ли получить сообщения из конкретного диалога
    const dialogs = await client.getDialogs({ limit: 10 });
    console.log(`Found ${dialogs.length} dialogs`);

    // Попробуем получить сообщения из первого диалога
    if (dialogs.length > 0) {
      for (let i = 0; i < Math.min(3, dialogs.length); i++) {
        const dialog = dialogs[i];
        console.log(`\n--- Testing dialog: ${dialog.title} (ID: ${dialog.entity?.id || 'N/A'}) ---`);
        
        try {
          // Попробуем получить сообщения без фильтров
          const messages = await client.getMessages(dialog.entity, { 
            limit: 5 
          });
          console.log(`Messages from ${dialog.title}: ${messages.length}`);
          
          // Попробуем получить сообщения с разными параметрами
          const messagesWithFilter = await client.getMessages(dialog.entity, { 
            limit: 5,
            minId: 1
          });
          console.log(`Messages with minId filter: ${messagesWithFilter.length}`);
          
          // Попробуем получить только текстовые сообщения
          if (messages.length > 0) {
            for (let j = 0; j < Math.min(2, messages.length); j++) {
              const msg = messages[j];
              console.log(`  Message #${j + 1}: ID=${msg.id}, Date=${new Date(msg.date * 1000).toISOString()}, HasText=${!!msg.text}, HasMedia=${!!msg.media}`);
              if (msg.text) {
                console.log(`    Text preview: ${msg.text.substring(0, 50)}${msg.text.length > 50 ? '...' : ''}`);
              }
            }
          }
        } catch (error) {
          console.error(`Error getting messages from ${dialog.title}: ${error}`);
        }
      }
    }

  } catch (error) {
    console.error("Error occurred:", error);
  } finally {
    await client.disconnect();
    console.log("\nDisconnected from Telegram.");
  }
}

testMessageRetrieval();