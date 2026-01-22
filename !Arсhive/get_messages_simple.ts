import { TelegramClient, StringSession } from 'https://deno.land/x/grm/mod.ts';

async function getChannelMessages() {
  console.log("--- Telegram Channel Messages Getter ---");
  
  // Сначала попробуем получить значения из переменных окружения
  const envApiId = Deno.env.get("TELEGRAM_API_ID");
  const envApiHash = Deno.env.get("TELEGRAM_API_HASH");
  const envSession = Deno.env.get("TELEGRAM_SESSION");
  
  let apiId, apiHash, sessionString;
  
  // Если переменные окружения не найдены, используем prompt
  if (!envApiId || !envApiHash || !envSession) {
    console.log("Environment variables not found. Please enter the values:");
    apiId = parseInt(prompt("Enter your API ID: ") || "");
    apiHash = prompt("Enter your API HASH: ") || "";
    sessionString = prompt("Enter your SESSION string: ") || "";
  } else {
    console.log("Using values from environment variables.");
    apiId = parseInt(envApiId);
    apiHash = envApiHash;
    sessionString = envSession;
  }

  if (isNaN(apiId) || !apiHash || !sessionString) {
    console.error("API ID, API HASH, and SESSION string are required.");
    return;
  }

  const channelInput = prompt("Enter channel name or ID (e.g., @channel_name or -1001234567890): ") || "";

  const stringSession = new StringSession(sessionString);
  const client = new TelegramClient(stringSession, apiId, apiHash, {
    connectionRetries: 5,
  });

  try {
    console.log("Connecting to Telegram...");
    await client.connect();

    console.log("Fetching messages from channel...");
    
    // Try to get the entity first to confirm access
    let entity;
    try {
      entity = await client.getEntity(channelInput);
      console.log(`Successfully accessed channel: ${entity.title} (ID: ${entity.id})`);
    } catch (error) {
      console.error(`Failed to access channel: ${error}`);
      return;
    }

    // Get messages from the channel
    const messages = await client.getMessages(entity, {
      limit: 10 // Get last 10 messages
    });

    console.log(`\nFound ${messages.length} messages in the channel:`);
    
    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i];
      console.log(`\nMessage #${i + 1}:`);
      console.log(`  ID: ${msg.id}`);
      console.log(`  Date: ${new Date(msg.date * 1000).toISOString()}`);
      console.log(`  Text: ${msg.text ? msg.text.substring(0, 200) + (msg.text.length > 200 ? '...' : '') : '[No text]'}`);
      
      // Check if message has media
      if (msg.media) {
        console.log(`  Media: Yes`);
      }
    }

    // Now try with minId filter similar to your function
    console.log("\n--- Testing with minId filter (like in your function) ---");
    const filteredMessages = await client.getMessages(entity, {
      limit: 10,
      minId: 0 // This mimics your function's behavior when last_processed_message_id is 0
    });

    console.log(`With minId filter, found ${filteredMessages.length} messages:`);
    for (let i = 0; i < filteredMessages.length; i++) {
      const msg = filteredMessages[i];
      console.log(`  Message ID: ${msg.id}, Date: ${new Date(msg.date * 1000).toISOString()}, Text: ${msg.text ? msg.text.substring(0, 100) : '[No text]'}`);
    }

  } catch (error) {
    console.error("Error occurred:", error);
  } finally {
    await client.disconnect();
    console.log("\nDisconnected from Telegram.");
  }
}

getChannelMessages();