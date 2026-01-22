import { TelegramClient, StringSession } from 'https://deno.land/x/grm/mod.ts';
import * as question from 'https://deno.land/x/question@0.0.2/mod.ts';

async function generateTelegramSession() {
  console.log("--- Telegram Session Generator ---");
  console.log("Please provide your Telegram API credentials and phone number.");
  console.log("You can get API ID and API HASH from https://my.telegram.org/");

  const apiId = parseInt(await question.prompt("Enter your API ID: "));
  const apiHash = await question.prompt("Enter your API HASH: ");
  const phoneNumber = await question.prompt("Enter your phone number (e.g., +1234567890): ");

  if (isNaN(apiId) || !apiHash || !phoneNumber) {
    console.error("API ID, API HASH, and Phone Number are required.");
    return;
  }

  const stringSession = new StringSession(""); // Start with an empty session
  const client = new TelegramClient(stringSession, apiId, apiHash, {
    connectionRetries: 5,
  });

  console.log("Connecting to Telegram...");
  await client.start({
    phoneNumber: phoneNumber,
    password: async () => await question.prompt("Enter your 2FA password (if any): "),
    phoneCode: async () => await question.prompt("Enter the code you received on Telegram: "),
    onError: (err) => console.error("Telegram client error:", err),
  });

  console.log("Successfully connected to Telegram!");
  const sessionString = client.session.save();
  console.log("\n--- Your Telegram Session String ---");
  console.log(sessionString);
  console.log("------------------------------------");
  console.log("Please copy the above session string and set it as TELEGRAM_SESSION in your Supabase Edge Function environment variables.");

  await client.disconnect();
  console.log("Disconnected from Telegram.");
}

generateTelegramSession();
