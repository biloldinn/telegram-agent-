import os
from dotenv import load_dotenv

load_dotenv()

# ============ TELEGRAM BOT SOZLAMALARI ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
OWNER_NAME = os.getenv("OWNER_NAME", "Admin")

# ============ MONGODB BAZA SOZLAMALARI ============
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "telegram_ai_bot")

# ============ AI KALITLARI ============
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ============ SINOV MUDDATI (TRIAL) ============
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "0"))

# ============ TO'LOV MA'LUMOTLARI ============
CARD_NUMBER = os.getenv("CARD_NUMBER", "")
CARD_OWNER = os.getenv("CARD_OWNER", "")

# ============ KANAL VA GURUH LINKLARI ============
CHANNEL_LINK = os.getenv("CHANNEL_LINK", None)
GROUP_LINK = os.getenv("GROUP_LINK", None)

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
