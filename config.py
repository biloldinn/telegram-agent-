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
ADMIN_ID = clean_int("ADMIN_ID", 6762465157)
OWNER_NAME = clean_env("OWNER_NAME", "Turg'unboyev Biloliddin")

# ============ MONGODB BAZA SOZLAMALARI ============
MONGO_URI = clean_env("MONGO_URI", "")
DB_NAME = clean_env("DB_NAME", "telegram_ai_bot")

# ============ AI KALITLARI ============
GEMINI_API_KEY = clean_env("GEMINI_API_KEY", "")
GROQ_API_KEY = clean_env("GROQ_API_KEY", "")
GROQ_API_KEY_BACKUP = clean_env("GROQ_API_KEY_BACKUP", "")

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
        "price": 50000,
        "duration": 30,
        "features": [
            "✅ AI orqali mijozlarga avtomatik javob",
            "✅ Xizmatlar va mahsulotlar haqida ma'lumot",
            "✅ Narxlar va buyurtma olish",
            "⚡ 24/7 uzluksiz javob"
        ]
    },
    "smm": {
        "name": "SMM PRO TARIFI",
        "price": 120000,
        "duration": 30,
        "features": [
            "✅ Professional SMM va Target konsultatsiyasi",
            "✅ Maxsus savdo skriptlari va takliflar",
            "✅ Barcha savollarga batafsil va moslashuvchan javob",
            "✅ Chegirmalar va aksiyalar taqdimoti",
            "⚡ Ustuvor (tezkor) AI javob"
        ]
    }
}
