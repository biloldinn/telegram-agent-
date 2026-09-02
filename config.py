import os
from dotenv import load_dotenv

load_dotenv()

def clean_env(key, default=""):
    val = os.getenv(key, default)
    if val is None or not str(val).strip() or str(val).strip().strip('"').strip("'") == "":
        return default
    return str(val).strip().strip('"').strip("'")

def clean_int(key, default=0):
    val = clean_env(key, str(default))
    try:
        return int(val)
    except Exception:
        return default

# ============ TELEGRAM BOT SOZLAMALARI ============
BOT_TOKEN = clean_env("BOT_TOKEN", "")
ADMIN_ID = clean_int("ADMIN_ID", 7744852023)
OWNER_NAME = clean_env("OWNER_NAME", "Turg'unboyev Biloliddin")

# ============ MONGODB BAZA SOZLAMALARI ============
MONGO_URI = clean_env("MONGO_URI", "")
DB_NAME = clean_env("DB_NAME", "telegram_ai_bot")

# ============ AI KALITLARI ============
GEMINI_API_KEY = clean_env("GEMINI_API_KEY", "")
GROQ_API_KEY = clean_env("GROQ_API_KEY", "")
GROQ_API_KEY_BACKUP = clean_env("GROQ_API_KEY_BACKUP", "")

# ============ TELEGRAM API (Telethon userbot) ============
API_ID = clean_int("API_ID", 0)
API_HASH = clean_env("API_HASH", "")

# ============ SINOV MUDDATI (TRIAL) ============
TRIAL_DAYS = clean_int("TRIAL_DAYS", 3)

# ============ TO'LOV MA'LUMOTLARI ============
CARD_NUMBER = clean_env("CARD_NUMBER", "9860356634199596")
CARD_OWNER = clean_env("CARD_OWNER", "Turg'unboyev Biloliddin")

# ============ KANAL VA GURUH LINKLARI ============
CHANNEL_LINK = clean_env("CHANNEL_LINK", None)
GROUP_LINK = clean_env("GROUP_LINK", None)

# ============ TARIFLAR ============
TARIFFS = {
    "standart": {
        "name": "STANDART TARIF",
        "price": 15000,
        "duration": 30,
        "features": [
            "🟢 AI orqali mijozlarga avtomatik javob",
            "🟢 Xizmatlar va mahsulotlar haqida ma'lumot",
            "🟢 Narxlar va buyurtma olish",
            "⏱ 24/7 uzluksiz javob"
        ]
    },
    "smm": {
        "name": "SMM PRO TARIFI",
        "price": 25000,
        "duration": 30,
        "features": [
            "🟢 STANDART tarifidagi barcha imkoniyatlar",
            "🎙 Ovozli xabarlarga ovoz bilan javob berish (Audio)",
            "🗣 O'zbekcha tabiiy ovoz (Edge TTS)",
            "📊 Reklama va SMM yuborish statistikasi",
            "💎 24/7 VIP tezkor javob"
        ]
    }
}

# Meta (Instagram) API Configs
META_APP_ID = os.environ.get("META_APP_ID", "")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "agentai_webhook_secret")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://telegram-agent-production-f1a8.up.railway.app")
