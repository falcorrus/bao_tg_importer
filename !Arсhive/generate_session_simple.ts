import { TelegramClient, StringSession } from 'https://deno.land/x/grm/mod.ts';

const API_ID = 25727332;
const API_HASH = "4306a0f13e21c95832ecd8c35cafffbb";
const PHONE_NUMBER = "+5548992012727";

async function generateSession() {
  console.log("🔄 Подключение к Telegram...\n");

  const session = new StringSession("");
  const client = new TelegramClient(session, API_ID, API_HASH, {
    connectionRetries: 5,
  });

  await client.start({
    phoneNumber: async () => PHONE_NUMBER,
    password: async () => {
      const buf = new Uint8Array(1024);
      const encoder = new TextEncoder();
      const decoder = new TextDecoder();
      await Deno.stdout.write(encoder.encode("Введите пароль 2FA (или Enter если нет): "));
      const n = await Deno.stdin.read(buf);
      const pwd = decoder.decode(buf.subarray(0, n || 0)).trim();
      return pwd || undefined;
    },
    phoneCode: async () => {
      console.log("\n📱 Проверьте Telegram - вам пришел код");
      const buf = new Uint8Array(1024);
      const encoder = new TextEncoder();
      const decoder = new TextDecoder();
      await Deno.stdout.write(encoder.encode("Введите код из Telegram: "));
      const n = await Deno.stdin.read(buf);
      return decoder.decode(buf.subarray(0, n || 0)).trim();
    },
    onError: (err) => console.error("❌ Ошибка:", err),
  });

  const sessionString = client.session.save();

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