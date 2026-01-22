import { TelegramClient } from "https://deno.land/x/gramjs@v2.16.11/mod.ts";
import { StringSession } from "https://deno.land/x/gramjs@v2.16.11/sessions/index.ts";
import { input } from "https://deno.land/x/input@2.0.3/index.ts";

const API_ID = 25727332;
const API_HASH = "4306a0f13e21c95832ecd8c35cafffbb";
const PHONE_NUMBER = "+5548992012727";

async function generateSession() {
  console.log("🔄 Подключение к Telegram через GramJS...\n");

  const session = new StringSession("");
  const client = new TelegramClient(session, API_ID, API_HASH, {
    connectionRetries: 5,
  });

  await client.start({
    phoneNumber: async () => PHONE_NUMBER,
    password: async () => {
      const pwd = await input("Введите пароль 2FA (или Enter): ");
      return pwd || undefined;
    },
    phoneCode: async () => {
      console.log("\n📱 Проверьте Telegram - вам пришел код");
      return await input("Введите код из Telegram: ");
    },
    onError: (err: Error) => console.error("❌ Ошибка:", err),
  });

  const sessionString = client.session.save() as unknown as string;

  console.log("\n" + "=".repeat(70));
  console.log("✅ УСПЕШНО! Ваш Session String:");
  console.log("=".repeat(70));
  console.log(sessionString);
  console.log("=".repeat(70));

  console.log("\n📋 Команда для Supabase:");
  console.log('supabase secrets set TELEGRAM_SESSION="' + sessionString + '"');

  await client.disconnect();
  console.log("\n✅ Готово!\n");
}

generateSession().catch(console.error);