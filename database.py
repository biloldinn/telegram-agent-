import sys
import os

# Windows UTF-8 encoding fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from config import MONGO_URI, DB_NAME, TRIAL_DAYS

effective_uri = MONGO_URI if (MONGO_URI and ("mongodb://" in MONGO_URI or "mongodb+srv://" in MONGO_URI)) else "mongodb://localhost:27017"
client = AsyncIOMotorClient(effective_uri, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]

users_col = db["users"]
payments_col = db["payments"]
messages_col = db["messages"]
products_col = db["products"]
referrals_col = db["referrals"]
persona_col = db["persona"]
settings_col = db["api_settings"]

async def init_db():
    """Boshlang'ich indekslar va mahsulotlarni kiritish"""
    try:
        await users_col.create_index("user_id", unique=True)
        await payments_col.create_index("id", unique=True)
        
        count = await products_col.count_documents({})
        if count == 0:
            default_products = [
                {
                    "id": 1,
                    "name": "To'liq SMM Xizmati",
                    "price": "250 000 so'm/oy",
                    "description": "Instagram va Telegram sahifalarini yuritish",
                    "details": "Kunlik 3 ta post, 5 ta story va mijozlar bilan muloqot"
                },
                {
                    "id": 2,
                    "name": "Target Reklama Sozlash",
                    "price": "150 000 so'm",
                    "description": "Facebook & Instagram orqali maqsadli auditoriyaga reklama",
                    "details": "Kreativ banner, matn va to'liq analitika"
                },
                {
                    "id": 3,
                    "name": "Kontent Yaratish (Reels/Post)",
                    "price": "100 000 so'm",
                    "description": "Sotuvchi Reels va postlar uchun ssenariylar",
                    "details": "10 ta video uchun ssenariy va muqova (cover)"
                }
            ]
            await products_col.insert_many(default_products)
        print("[MongoDB] Baza muvaffaqiyatli ulandi va sozlandi.")
        return True
    except Exception as e:
        print(f"[MongoDB] Ulanishda ogohlantirish: {e}")
        return False

# ============ FOYDALANUVCHILAR VA 3 KUNLIK SINOV ============
async def add_user(user_id: int, username: str, full_name: str, referrer_id: int = None):
    user = await users_col.find_one({"user_id": user_id})
    if not user and referrer_id and referrer_id != user_id:
        # Give referrer +1 count
        ref_user = await users_col.find_one({"user_id": referrer_id})
        if ref_user:
            new_count = ref_user.get('referral_count', 0) + 1
            up_data = {'referral_count': new_count}
            
            # If reached 5 and has active paid tariff, add 1 day
            if new_count % 5 == 0:
                t_end = ref_user.get("tariff_end")
                t_type = ref_user.get("tariff_type")
                if t_end and t_type != 'trial' and t_type != 'none':
                    from datetime import datetime, timedelta
                    end_dt = datetime.fromisoformat(t_end)
                    now = datetime.now()
                    if now < end_dt:
                        end_dt = end_dt + timedelta(days=1)
                        up_data['tariff_end'] = end_dt.isoformat()
                        try:
                            from main import bot
                            await bot.send_message(
                                referrer_id,
                                f"🎉 <b>TABRIKLAYMIZ!</b> Siz 5 ta yangi do'stingizni taklif qildingiz va tarifingizga <b>+1 KUN BONUS</b> qo'shildi!"
                            )
                        except Exception:
                            pass
            await users_col.update_one({'user_id': referrer_id}, {'$set': up_data})

    if not user:
        now = datetime.now()
        start_date = now.isoformat()
        end_date = (now + timedelta(days=TRIAL_DAYS)).isoformat()
        
        doc = {
            "user_id": user_id,
            "username": username or "",
            "full_name": full_name or "",
            "role": "trial",
            "tariff_type": "trial",
            "tariff_start": start_date,
            "tariff_end": end_date,
            "ai_enabled": 1,
            "customer_character": "normal",
            "created_at": start_date
        }
        await users_col.insert_one(doc)
        return True
    return False

async def get_user(user_id: int):
    return await users_col.find_one({"user_id": user_id})

async def update_user(user_id: int, **kwargs):
    await users_col.update_one({"user_id": user_id}, {"$set": kwargs})

async def check_user_access(user_id: int):
    user = await get_user(user_id)
    if not user:
        return False, "Ro'yxatdan o'tmagan", 0, "none"
    
    if user.get("role") in ["admin", "friend"]:
        return True, "Doimiy Faol", 999, user.get("role")
    
    t_end = user.get("tariff_end")
    if not t_end:
        return False, "Muddati belgilanmagan", 0, "none"
    
    try:
        end_dt = datetime.fromisoformat(t_end)
        now = datetime.now()
        if now < end_dt:
            diff = end_dt - now
            days = diff.days
            hours = int(diff.seconds // 3600)
            if user.get("tariff_type") == "trial" and days > 0:
                status = f"Sinov muddati ({days} kun, {hours} soat qoldi)"
            else:
                status = f"Faol ({days} kun qoldi)"
            return True, status, days, user.get("tariff_type")
        else:
            return False, "Sinov yoki tarif muddati tugagan", 0, user.get("tariff_type")
    except Exception:
        return False, "Xatolik", 0, "none"

async def activate_tariff(user_id: int, tariff_type: str, days=30):
    now = datetime.now()
    start_date = now.isoformat()
    end_date = (now + timedelta(days=days)).isoformat()
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {
            "tariff_type": tariff_type,
            "tariff_start": start_date,
            "tariff_end": end_date,
            "role": "paid",
            "ai_enabled": 1
        }}
    )

# ============ TO'LOVLAR ============
async def add_payment(user_id: int, tariff_type: str, amount: int, photo_id: str):
    count = await payments_col.count_documents({})
    payment_id = count + 1
    doc = {
        "id": payment_id,
        "user_id": user_id,
        "tariff_type": tariff_type,
        "amount": amount,
        "photo_id": photo_id,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    await payments_col.insert_one(doc)
    return payment_id

async def get_payment_by_id(payment_id: int):
    return await payments_col.find_one({"id": payment_id})

async def update_payment_status(payment_id: int, status: str):
    await payments_col.update_one({"id": payment_id}, {"$set": {"status": status}})

async def get_pending_payments():
    cursor = payments_col.find({"status": "pending"}).sort("created_at", -1)
    return await cursor.to_list(length=10)

# ============ XABARLAR TARIXI ============
async def save_message(user_id: int, message: str, response: str):
    await messages_col.insert_one({
        "user_id": user_id,
        "message": message,
        "response": response,
        "created_at": datetime.now().isoformat()
    })

async def get_user_messages(user_id: int, limit=5):
    cursor = messages_col.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
    res = await cursor.to_list(length=limit)
    return list(reversed(res))

# ============ EGASINING XARAKTERI (PERSONA) ============
async def save_owner_persona(persona_text: str):
    await persona_col.update_one(
        {"_id": "owner_persona"},
        {"$set": {"persona_prompt": persona_text, "updated_at": datetime.now().isoformat()}},
        upsert=True
    )

async def get_owner_persona():
    doc = await persona_col.find_one({"_id": "owner_persona"})
    if doc:
        return doc.get("persona_prompt")
    return None

# ============ MAHSULOTLAR ============
async def get_products():
    cursor = products_col.find({})
    return await cursor.to_list(length=50)

# ============ API SOZLAMALAR ============
async def save_api_settings(api_id: str, api_hash: str, phone: str):
    await settings_col.update_one(
        {"_id": "main_api"},
        {"$set": {"api_id": str(api_id), "api_hash": str(api_hash), "phone": str(phone), "is_active": 0}},
        upsert=True
    )

async def get_api_settings():
    return await settings_col.find_one({"_id": "main_api"})

async def set_api_active(status: bool):
    await settings_col.update_one({"_id": "main_api"}, {"$set": {"is_active": 1 if status else 0}})

# ============ STATISTIKA ============
async def get_stats():
    now_iso = datetime.now().isoformat()
    total_users = await users_col.count_documents({})
    active_users = await users_col.count_documents({"tariff_end": {"$gt": now_iso}})
    total_payments = await payments_col.count_documents({"status": "approved"})
    pending_payments = await payments_col.count_documents({"status": "pending"})
    
    pipeline = [{"$match": {"status": "approved"}}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
    res = await payments_col.aggregate(pipeline).to_list(1)
    total_amount = res[0]["total"] if res else 0
    total_messages = await messages_col.count_documents({})
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_payments": total_payments,
        "pending_payments": pending_payments,
        "total_amount": total_amount,
        "total_messages": total_messages
    }

async def update_business_info(user_id: int, text: str):
    await users_col.update_one({'user_id': user_id}, {'$set': {'business_info': text}})

async def update_group_settings(user_id: int, channel_link: str = None, group_reply_enabled: int = None):
    update_fields = {}
    if channel_link is not None:
        update_fields['channel_link'] = channel_link
    if group_reply_enabled is not None:
        update_fields['group_reply_enabled'] = group_reply_enabled
    if update_fields:
        await users_col.update_one({'user_id': user_id}, {'$set': update_fields})

async def update_user_persona(user_id: int, persona: str):
    await users_col.update_one({'user_id': user_id}, {'$set': {'persona': persona}})

async def update_user_api(user_id: int, api_id: int, api_hash: str):
    await users_col.update_one({'user_id': user_id}, {'$set': {'api_id': api_id, 'api_hash': api_hash}})

settings_col = db['settings']

async def get_settings():
    s = await settings_col.find_one({'_id': 'global_settings'})
    if not s:
        s = {'standard_price': 150000, 'smm_price': 300000}
        await settings_col.insert_one({'_id': 'global_settings', **s})
    return s

async def update_settings(standard_price=None, smm_price=None):
    update_data = {}
    if standard_price is not None:
        update_data['standard_price'] = standard_price
    if smm_price is not None:
        update_data['smm_price'] = smm_price
    if update_data:
        await settings_col.update_one({'_id': 'global_settings'}, {'$set': update_data}, upsert=True)
