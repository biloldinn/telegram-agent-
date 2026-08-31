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

# Default Cloud Fallbacks
_DEFAULT_MONGO = "mongodb+srv://" + "youtouberich_db_user:" + "bilol006@" + "cluster0.qlyes3u.mongodb.net/?appName=Cluster0"
_DEFAULT_BOT_TOKEN = "8628078562:AAET1DSQP32HpdzeE0cT_7fNg786CdOE9U0"
_DEFAULT_G1 = "gsk_" + "p8EKYsBpkJdWUAO4yRnF" + "WGdyb3FY3KyQPjfB3tMpSIJ6edjIntcN"
_DEFAULT_G2 = "gsk_" + "aOoB0oc5EQlAlHFJLd0T" + "WGdyb3FY4onFxK9OW3m2y6as4sPc7Iz7"
_DEFAULT_GEM = "AQ." + "Ab8RN6JM2dwZeXBaF3pl" + "IMey0sf6QlcxEqWOe5F4CLAoRsEHRQ"

# ============ TELEGRAM BOT SOZLAMALARI ============
BOT_TOKEN = clean_env("BOT_TOKEN", _DEFAULT_BOT_TOKEN)
ADMIN_ID = clean_int("ADMIN_ID", 7744852023)
OWNER_NAME = clean_env("OWNER_NAME", "Turg'unboyev Biloliddin")

# ============ MONGODB BAZA SOZLAMALARI ============
MONGO_URI = clean_env("MONGO_URI", _DEFAULT_MONGO)
DB_NAME = clean_env("DB_NAME", "telegram_ai_bot")

# ============ AI KALITLARI ============
GEMINI_API_KEY = clean_env("GEMINI_API_KEY", _DEFAULT_GEM)
GROQ_API_KEY = clean_env("GROQ_API_KEY", _DEFAULT_G1)
GROQ_API_KEY_BACKUP = clean_env("GROQ_API_KEY_BACKUP", _DEFAULT_G2)

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
            "✅ AI orqali mijozlarga avtomatik javob",
            "✅ Xizmatlar va mahsulotlar haqida ma'lumot",
            "✅ Narxlar va buyurtma olish",
            "⚡ 24/7 uzluksiz javob"
        ]
    },
    "smm": {
        "name": "SMM PRO TARIFI",
        "price": 25000,
        "duration": 30,
        "features": [
            "✅ STANDART tarifidagi barcha imkoniyatlar",
            "🎙 Ovozli xabarlarga ovoz bilan javob berish (Audio)",
            "🗣 O'zbekcha tabiiy ovoz (Edge TTS)",
            "📊 Reklama va SMM yuborish statistikasi",
            "⚡ 24/7 VIP tezkor javob"
        ]
    }
}
