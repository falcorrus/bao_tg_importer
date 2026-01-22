import { TelegramClient, StringSession } from 'https://deno.land/x/grm/mod.ts';

async function testExistingSession() {
  console.log("--- Testing Existing Session ---");
  
  // Read credentials from .env
  const envContent = await Deno.readTextFile("scripts/.env");
  const lines = envContent.split('\n');
  
  let apiId, apiHash, sessionString;
  for (const line of lines) {
    if (line.startsWith('TELEGRAM_API_ID=')) {
      apiId = parseInt(line.split('=')[1]);
    } else if (line.startsWith('TELEGRAM_API_HASH=')) {
      apiHash = line.split('=')[1];
    } else if (line.startsWith('TELEGRAM_SESSION=')) {
      sessionString = line.split('=')[1];
    }
  }
  
  if (!apiId || !apiHash || !sessionString) {
    console.error("Could not read all credentials from scripts/.env");
    return;
  }
  
  console.log("Using existing credentials from .env");
  
  const stringSession = new StringSession(sessionString);
  const client = new TelegramClient(stringSession, apiId, apiHash, {
    connectionRetries: 5,
  });

  try {
    console.log("Connecting to Telegram...");
    await client.connect();

    // Check if we're authorized
    const me = await client.getMe();
    console.log(`Successfully authenticated as: ${me.firstName} (@${me.username || 'N/A'})`);

    // Try to join the specific channels if possible
    try {
      console.log("\nTrying to access @argentina_afisha...");
      const entity = await client.getEntity('@argentina_afisha');
      console.log(`Successfully accessed channel: ${entity.title} (ID: ${entity.id})`);
      
      // Try to join if we're not already a member
      console.log('Attempting to get messages...');
      const messages = await client.getMessages(entity, { limit: 5 });
      console.log(`Messages found: ${messages.length}`);
      
      if (messages.length > 0) {
        console.log('Sample message:');
        console.log(`ID: ${messages[0].id}, Date: ${new Date(messages[0].date * 1000).toISOString()}, Text: ${messages[0].text?.substring(0, 100) || '[No text]'}`);
      }
    } catch (error) {
      console.error(`Error accessing @argentina_afisha: ${error}`);
    }

  } catch (error) {
    console.error("Error occurred:", error);
  } finally {
    await client.disconnect();
    console.log("\nDisconnected from Telegram.");
  }
}

testExistingSession();