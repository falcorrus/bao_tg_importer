import { TelegramClient, StringSession } from 'https://deno.land/x/grm/mod.ts';

async function generateTelegramSession() {
  console.log("--- Telegram Session Generator ---");
  console.log("Loading credentials from .env.txt...");
  
  // Read credentials from .env
  const envContent = await Deno.readTextFile("scripts/.env");
  const lines = envContent.split('\n');
  
  let apiId, apiHash, sessionString;
  for (const line of lines) {
    if (line.startsWith('TELEGRAM_API_ID=')) {
      apiId = parseInt(line.split('=')[1]);
    } else if (line.startsWith('TELEGRAM_API_HASH=')) {
      apiHash = line.split('=')[1];
    }
  }
  
  if (!apiId || !apiHash) {
    console.error("Could not read API credentials from scripts/.env.txt");
    return;
  }
  
  console.log("Using API ID and Hash from .env.txt");
  const phoneNumber = prompt("Enter your phone number (e.g., +1234567890): ") || "";

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
    password: async () => prompt("Enter your 2FA password (if any): ") || "",
    phoneCode: async () => prompt("Enter the code you received on Telegram: ") || "",
    onError: (err) => console.error("Telegram client error:", err),
  });

  console.log("Successfully connected to Telegram!");
  const newSessionString = client.session.save();
  console.log("\n--- Your NEW Telegram Session String ---");
  console.log(newSessionString);
  console.log("----------------------------------------");
  console.log("Please update the TELEGRAM_SESSION variable in your Supabase Edge Function environment variables.");

  await client.disconnect();
  console.log("Disconnected from Telegram.");
}

generateTelegramSession();