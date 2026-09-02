import logging
logging.basicConfig(level=logging.INFO)
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import asyncio
import warnings
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from states import LoginState
from userbot_manager import load_active_userbots
from aiogram.enums import ChatAction, ParseMode
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.client.default import DefaultBotProperties
from groq import AsyncGroq
import google.generativeai as genai

# Suppress annoying Gemini warnings
warnings.filterwarnings("ignore", module="google.generativeai")

from config import *
from database import *
from database import update_user_api
from database import update_business_info

# ============ BOT & AI SETUP ============
effective_token = BOT_TOKEN if (BOT_TOKEN and ":" in BOT_TOKEN) else "8828508539:AAFkPXzxh7kvFW9NKiDERNvOtwdBc5ezLRo"
bot = Bot(token=effective_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
pending_tariff = {}

groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
groq_backup_client = AsyncGroq(api_key=GROQ_API_KEY_BACKUP) if GROQ_API_KEY_BACKUP else None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-pro")
else:
    gemini_model = None

# ============ DOIMIY MENYU (REPLY KEYBOARD) ============
def get_contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)],
            [KeyboardButton(text="🔙 Bekor qilish")]
        ],
        resize_keyboard=True
    )

def get_main_menu(user_id):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔗 Profilni ulash", web_app=types.WebAppInfo(url=f"{WEBHOOK_URL.rstrip('/')}/?user_id={user_id}"))],
            [KeyboardButton(text="💎 Tariflar"), KeyboardButton(text="👥 Do'stlarni taklif qilish")],
            [KeyboardButton(text="👤 Mening Profilim"), KeyboardButton(text="⚙️ AI Sozlamalar")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Tanlang yoki yozing..."
    )

def get_tariffs_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Standart (15 000 so'm)", callback_data="buy_standart")],
        [InlineKeyboardButton(text="🚀 SMM Pro (25 000 so'm)", callback_data="buy_smm")],
        [InlineKeyboardButton(text="🔙 Yopish", callback_data="close_menu")]
    ])

def get_ai_settings_keyboard(user: dict):
    is_enabled = bool(user.get("ai_enabled", 1))
    group_reply = bool(user.get("group_reply_enabled", 0))
    
    status = "СЂСџСџСћ YOQILGAN" if is_enabled else "СЂСџвЂќТ‘ O'CHIRILGAN"
    action_data = "ai_toggle_off" if is_enabled else "ai_toggle_on"
    action_text = "СЂСџвЂќТ‘ O'chirish" if is_enabled else "СЂСџСџСћ Yoqish"
    
    grp_status = "✅ Guruhlarda: Yoqilgan" if group_reply else "❌ Guruhlarda: O'chirilgan"
    grp_action = "grp_toggle_off" if group_reply else "grp_toggle_on"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Holat: {status}", callback_data="ignore")],
        [InlineKeyboardButton(text=action_text, callback_data=action_data)],
        [InlineKeyboardButton(text="📝 Biznes Ma'lumoti (Menyu, Narxlar)", callback_data="set_biz_info")],
        [InlineKeyboardButton(text=grp_status, callback_data=grp_action)],
        [InlineKeyboardButton(text="🔗 Kanal/Guruh Linkini kiritish", callback_data="set_channel_link")],
        [InlineKeyboardButton(text="📢 Mijozlarga Yangilik Tarqatish", callback_data="set_client_broadcast")],
        [InlineKeyboardButton(text="📊 Mening Statistikam", callback_data="show_my_stats")],
        [InlineKeyboardButton(text="🔙 Yopish", callback_data="close_menu")]
    ])

def get_products_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Tarif sotib olish", callback_data="btn_tariffs")],
        [InlineKeyboardButton(text="🔙 Yopish", callback_data="close_menu")]
    ])

# ============ AI JAVOBINI TAYYORLASH ============
async def get_ai_response(text: str, user_id: int) -> str:
    user = await get_user(user_id)
    if not user or not user.get("ai_enabled", 1):
        return "СЂСџВ¤вЂ“ <b>AI assistent o'chirilgan.</b>\nQayta yoqish uchun pastdagi menyudan <i>AI Sozlamalar</i> ni tanlang."

    has_access, status_text, days_left, tariff = await check_user_access(user_id)

    if not has_access:
        return f"Kechirasiz, sizning 3 kunlik bepul sinov muddatingiz yoki tarifingiz tugagan! ⏳\n\nIltimos, <b>💳 Tariflar</b> bo'limidan mos tarifni xarid qiling."

    history = await get_user_messages(user_id, limit=4)
    history_text = ""
    for h in history:
        history_text += f"Mijoz: {h['message']}\nSiz: {h['response']}\n"

    persona_base = await get_owner_persona()
    if not persona_base:
        persona_base = f"Siz {OWNER_NAME}siz. Samimiy va professional javob berasiz."
    system_prompt = f"""{persona_base}
FOYDALANUVCHI: {user.get('full_name')} (Tarif: {tariff.upper()})

MULOQOT QOIDALARI:
- O'zingizni AI deb aytmang. Siz - {OWNER_NAME} ning rasmiy yordamchisisiz.
- Matnlarni chiroyli qilib HTML formatda qaytaring (qalin qilish uchun <b>matn</b>).
- Qisqa, aniq va foydali javob bering. Mijoz savol bersa, muloyimlik bilan xizmatni soting.

SUHBAT TARIXI:
{history_text}"""

    if groq_client:
        try:
            resp = await groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.6,
                max_tokens=280
            )
            return resp.choices[0].message.content
        except Exception:
            pass

    if groq_backup_client:
        try:
            resp = await groq_backup_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.6,
                max_tokens=280
            )
            return resp.choices[0].message.content
        except Exception:
            pass

    if gemini_model:
        try:
            full_prompt = f"{system_prompt}\n\nMijoz: {text}\nSiz:"
            res = await asyncio.to_thread(gemini_model.generate_content, full_prompt)
            return res.text
        except Exception:
            pass

    return "Kechirasiz, birozdan so'ng qayta yozing."

# ============ /START COMMAND ============
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or ""
    
    if message.text and len(message.text.split()) > 1:
        args = message.text.split()[1]
        if args.startswith('ref_'):
            try:
                ref_id = int(args.split('ref_')[1])
                await add_referral(ref_id, user_id)
            except Exception:
                pass

    is_new = await add_user(user_id, username, full_name)
    has_access, status_text, days_left, tariff = await check_user_access(user_id)

    if is_new:
        # Yangi foydalanuvchi РІР‚вЂќ trial xabari
        welcome_text = f"""Assalomu alaykum, <b>{full_name}</b>! СЂСџвЂвЂ№
SMM AI Agent platformasiga xush kelibsiz! СЂСџР‹вЂ°

СЂСџР‹Рѓ Sizga <b>3 KUNLIK BEPUL SINOV MUDDATI</b> taqdim etildi!
📊 Holat: <i>{status_text}</i>

Men sizning shaxsiy Telegram profilingizni aqlli <b>Avto-Javob beruvchi Sotuv Menejeriga</b> aylantirib beraman. Mijozlaringizga sizning o'rningizda toza O'zbek tilida, matn va hatto СЂСџР‹в„ў Ovozli xabar orqali javob beraman!

СЂСџвЂвЂЎ <i>Profilni ulash va sozlash uchun menyudan foydalaning:</i>"""
    else:
        # Qaytib kelgan foydalanuvchi РІР‚вЂќ holat xabari
        if has_access:
            holat_emoji = "✅"
        else:
            holat_emoji = "РІС™В РїС‘РЏ"
        welcome_text = f"""Xush kelibsiz, <b>{full_name}</b>! СЂСџвЂвЂ№

{holat_emoji} Tarif holati: <i>{status_text}</i>

СЂСџвЂвЂЎ <i>Menyudan kerakli bo'limni tanlang:</i>"""

    await message.answer(welcome_text, reply_markup=get_main_menu(message.from_user.id))

# ============ MENU ACTIONS (TEXT) ============
async def show_tariffs(message: types.Message):
    text = f"""💳 <b>TARIF REJALARI VA TO'LOV</b>

⭐ <b>1. STANDART TARIF</b> РІР‚вЂќ <code>{TARIFFS['standart']['price']:,} so'm/oy</code>
{chr(10).join(['РІвЂ“Р„РїС‘РЏ ' + f for f in TARIFFS['standart']['features']])}

🚀 <b>2. SMM PRO TARIFI</b> РІР‚вЂќ <code>{TARIFFS['smm']['price']:,} so'm/oy</code>
{chr(10).join(['РІвЂ“Р„РїС‘РЏ ' + f for f in TARIFFS['smm']['features']])}

РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’
💳 <b>To'lov uchun karta:</b> <code>{CARD_NUMBER}</code>
СЂСџвЂВ¤ <b>Karta egasi:</b> {CARD_OWNER}
РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’РІвЂўС’

СЂСџвЂвЂЎ <i>Xarid qilish uchun quyidagi tugmalardan birini bosing:</i>"""
    await message.answer(text, reply_markup=get_tariffs_keyboard())

async def show_products(message: types.Message):
    prods = await get_products()
    msg = "📦 <b>BIZNING XIZMATLAR VA NARXLAR:</b>\n\n"
    for p in prods:
        msg += f"СЂСџвЂњРЉ <b>{p['name']}</b>\n💰 Narxi: <code>{p['price']}</code>\n📝 {p['description']}\nСЂСџвЂњвЂ№ <i>{p['details']}</i>\n\n"
    msg += "Savollaringiz bo'lsa, menga to'g'ridan-to'g'ri yozishingiz mumkin! СЂСџвЂ™В¬"
    await message.answer(msg, reply_markup=get_products_keyboard())

async def show_profile(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    has_acc, st_text, days_left, tariff = await check_user_access(user_id)
    ai_status = "✅ Yoqilgan" if user and user.get('ai_enabled') else "❌ O'chirilgan"
    
    msg = f"""СЂСџвЂВ¤ <b>SHAXSIY PROFILINGIZ</b>

СЂСџвЂ вЂќ ID: <code>{user_id}</code>
СЂСџвЂњвЂє Ism: <b>{user.get('full_name') if user else ''}</b>

📦 Faol tarif: <b>{tariff.upper()}</b>
СЂСџвЂњвЂ¦ Holat: <i>{st_text}</i>
СЂСџВ¤вЂ“ AI Yordamchi: <b>{ai_status}</b>

<i>Qo'shimcha xizmatlar uchun tariflarni ko'rib chiqing.</i>"""
    await message.answer(msg)

async def show_ai_settings(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Profil topilmadi. Iltimos, /start buyrug'ini bosing.")
        return
    await message.answer(
        "СЂСџВ¤вЂ“ <b>AI Yordamchi Sozlamalari</b>\n\nBu yerdan sun'iy intellekt javob berishini boshqarishingiz mumkin.",
        reply_markup=get_ai_settings_keyboard(user)
    )

# ... (other code around here remains unchanged) ...
# Let me just fix the exact callback functions.


async def show_help(message: types.Message):
    await message.answer("""РІСњвЂњ <b>YORDAM MARKAZI</b>

Bu platforma orqali siz shaxsiy akkauntingizga Sun'iy Intellekt ulab olishingiz mumkin. AI sizning biznesingiz haqidagi ma'lumotlarni yodlab oladi va mijozlaringizga sizning o'rningizga javob qaytaradi.

СЂСџвЂРЃРІР‚РЊСЂСџвЂ™В» <b>Admin bilan bog'lanish:</b> Tizimda muammo bo'lsa yoki tarif sotib olishda savolingiz bo'lsa to'g'ridan-to'g'ri yozing.
РІв„ўВ»РїС‘РЏ Botni yangilash uchun: /start""", reply_markup=get_main_menu(message.from_user.id))

@dp.message(F.text == "💳 Tariflar")
async def btn_tariffs_handler(message: types.Message):
    await show_tariffs(message)

@dp.message(F.text.in_(["СЂСџвЂТђ Do'stlarni taklif qilish", "СЂСџР‹Рѓ Bonus olish", "📦 Xizmatlar"]))
async def btn_referral_handler(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    ref_count = user.get('referral_count', 0) if user else 0
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    text = f"""СЂСџвЂТђ <b>DO'STLARNI TAKLIF QILISH (REFERRAL)</b>

🔗 Sizning taklif havolangiz:
<code>{ref_link}</code>

СЂСџР‹Рѓ <b>Bonus shartlari:</b>
Har <b>5 ta do'stingiz</b> ushbu havola orqali botga kirsa, sizning faol tarifingizga <b>avtomatik ravishda 1 KUN BONUS</b> qo'shiladi!
<i>(Eslatma: Bonus ishlashi uchun sizda faol pullik tarif bo'lishi kerak).</i>

📊 Hozirgacha taklif qilgan do'stlaringiz: <b>{ref_count} ta</b>"""
    await message.answer(text)

@dp.message(F.text == "СЂСџвЂВ¤ Mening Profilim")
async def btn_profile_handler(message: types.Message):
    await show_profile(message)

@dp.message(F.text == "СЂСџВ¤вЂ“ AI Sozlamalar")
async def btn_ai_settings_handler(message: types.Message):
    await show_ai_settings(message)

@dp.message(F.text == "СЂСџвЂњС› Yordam")
async def btn_help_handler(message: types.Message):
    await show_help(message)

# Fallbacks for commands if someone types them
@dp.message(Command("buy"))
async def cmd_buy(m: types.Message): await show_tariffs(m)
@dp.message(Command("referral"))
async def cmd_ref(m: types.Message): await btn_referral_handler(m)
@dp.message(Command("profile"))
async def cmd_prof(m: types.Message): await show_profile(m)
@dp.message(Command("help"))
async def cmd_hlp(m: types.Message): await show_help(m)


# ============ CALLBACK QUERIES (TUGMALAR) ============
@dp.callback_query(F.data == "btn_tariffs")
async def cb_show_tariffs(callback: CallbackQuery):
    await callback.message.delete()
    await show_tariffs(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "buy_standart")
async def cb_buy_standart(callback: CallbackQuery):
    pending_tariff[callback.from_user.id] = 'standart'
    await users_col.update_one({'user_id': callback.from_user.id}, {'$set': {'pending_tariff': 'standart'}}, upsert=True)
    await callback.message.edit_text(f"""⭐ <b>STANDART TARIF TANLANDI</b>

💰 To'lov summasi: <b>{TARIFFS['standart']['price']:,} so'm</b>
💳 Karta: <code>{CARD_NUMBER}</code>
СЂСџвЂВ¤ Egasi: <b>{CARD_OWNER}</b>

📸 <i>Iltimos, to'lovni amalga oshirib, to'lov chekining (skrinshot yoki PDF) rasmini shu chatga yuboring!</i>""", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="btn_tariffs")]]))
    await callback.answer()

@dp.callback_query(F.data == "buy_smm")
async def cb_buy_smm(callback: CallbackQuery):
    pending_tariff[callback.from_user.id] = 'smm'
    await users_col.update_one({'user_id': callback.from_user.id}, {'$set': {'pending_tariff': 'smm'}}, upsert=True)
    await callback.message.edit_text(f"""🚀 <b>SMM PRO TARIFI TANLANDI</b>

💰 To'lov summasi: <b>{TARIFFS['smm']['price']:,} so'm</b>
💳 Karta: <code>{CARD_NUMBER}</code>
СЂСџвЂВ¤ Egasi: <b>{CARD_OWNER}</b>

📸 <i>Iltimos, to'lovni amalga oshirib, to'lov chekining (skrinshot yoki PDF) rasmini shu chatga yuboring!</i>""", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="btn_tariffs")]]))
    await callback.answer()

@dp.callback_query(F.data == "ai_toggle_on")
async def cb_ai_on(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user: return
    await update_user(callback.from_user.id, ai_enabled=1)
    await callback.message.edit_reply_markup(reply_markup=get_ai_settings_keyboard({'ai_enabled': 1, 'group_reply_enabled': user.get('group_reply_enabled', 0)}))
    await callback.answer("✅ AI javob berish yoqildi!")

@dp.callback_query(F.data == "ai_toggle_off")
async def cb_ai_off(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user: return
    await update_user(callback.from_user.id, ai_enabled=0)
    await callback.message.edit_reply_markup(reply_markup=get_ai_settings_keyboard({'ai_enabled': 0, 'group_reply_enabled': user.get('group_reply_enabled', 0)}))
    await callback.answer("❌ AI javob berish o'chirildi!")

@dp.callback_query(F.data == "close_menu")
async def cb_close(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@dp.callback_query(F.data == "ignore")
async def cb_ignore(callback: CallbackQuery):
    await callback.answer()

# (Old duplicate admin handlers removed to fix conflict with correct ones below)
    if message.from_user.id != ADMIN_ID:
        return
    payments = await get_pending_payments()
    if not payments:
        await message.answer("СЂСџвЂњВ­ Kutilayotgan to'lovlar yo'q.")
        return
    msg = "⏳ <b>KUTILAYOTGAN TO'LOVLAR:</b>\n\n"
    for p in payments:
        msg += f"СЂСџвЂ вЂќ <code>#{p['id']}</code> | ID: <code>{p['user_id']}</code>\n📦 {p['tariff_type']} - <b>{p['amount']:,} so'm</b>\n"
        msg += f"СЂСџвЂвЂ° Tasdiqlash: /approve_{p['id']} | Rad: /reject_{p['id']}\n\n"
    await message.answer(msg)

# ============ TO'LOV CHEKI (PHOTO / PDF) ============
@dp.message(F.photo | F.document)
async def handle_receipt(message: types.Message):
    user_id = message.from_user.id
    
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        mime = str(message.document.mime_type or '').lower()
        if 'pdf' in mime or 'image' in mime:
            file_id = message.document.file_id
        else:
            await message.answer("❌ Iltimos, to'lov chekini faqat Rasm (Skrinshot) yoki PDF fayl shaklida yuboring.")
            return
            
    if not file_id: return

    user_doc = await get_user(user_id)
    t_key = (user_doc or {}).get('pending_tariff') or pending_tariff.get(user_id)

    if t_key and t_key in TARIFFS:
        t_data = TARIFFS[t_key]
        p_id = await add_payment(user_id, t_key, t_data['price'], file_id)
        if user_id in pending_tariff:
            del pending_tariff[user_id]
        await users_col.update_one({'user_id': user_id}, {'$unset': {'pending_tariff': ""}})

        await message.answer(f"""📸 <b>To'lov cheki qabul qilindi!</b>

📦 Tarif: <b>{t_data['name']}</b>
💰 Summa: <b>{t_data['price']:,} so'm</b>
СЂСџвЂ вЂќ To'lov ID: <code>#{p_id}</code>
⏳ Holat: <b>Admin tekshirmoqda. Tez orada tasdiqlanadi!</b>""")

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_approve_{p_id}"),
                    InlineKeyboardButton(text="❌ Rad etish", callback_data=f"admin_reject_{p_id}")
                ]
            ]
        )
        caption_text = f"""💰 <b>YANGI TO'LOV CHEKI KELDI!</b>

СЂСџвЂ вЂќ To'lov ID: <code>#{p_id}</code>
СЂСџвЂВ¤ Mijoz: <b>{message.from_user.full_name}</b> (@{message.from_user.username or 'yoq'})
СЂСџвЂ вЂќ Telegram ID: <code>{user_id}</code>
📦 Tarif: <b>{t_data['name']}</b>
СЂСџвЂ™Вµ Summa: <b>{t_data['price']:,} so'm</b>

✅ Tasdiqlash: /approve_{p_id}
❌ Rad etish: /reject_{p_id}"""

        try:
            if message.photo:
                await bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=file_id,
                    caption=caption_text,
                    reply_markup=markup
                )
            else:
                await bot.send_document(
                    chat_id=ADMIN_ID,
                    document=file_id,
                    caption=caption_text,
                    reply_markup=markup
                )
        except Exception as e:
            print(f"[Admin Send Error] {e}")
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"{caption_text}\n\n<i>(Chek fayli: {file_id})</i>",
                reply_markup=markup
            )
    else:
        await message.answer("📸 <i>Chek yuborishdan oldin iltimos menyudan tarifni tanlang:</i>", reply_markup=get_tariffs_keyboard())

@dp.callback_query(F.data.startswith("admin_approve_"))
async def cb_admin_approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    try:
        pid = int(callback.data.replace("admin_approve_", ""))
        p = await get_payment_by_id(pid)
        if p and p.get('status') == 'pending':
            await update_payment_status(pid, 'approved')
            await activate_tariff(p['user_id'], p['tariff_type'], days=30)
            await bot.send_message(p['user_id'], f"СЂСџР‹вЂ° <b>TO'LOVINGIZ TASDIQLANDI!</b>\n\n📦 <b>{p['tariff_type'].upper()}</b> tarifi 30 kunga faollashtirildi!\nProfilingizga AI muvaffaqiyatli ulandi.")
            try:
                await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n✅ <b>TASDIQLANDI!</b>", reply_markup=None)
            except Exception:
                pass
            await callback.answer("✅ To'lov tasdiqlandi!")
        else:
            await callback.answer("❌ Bu to'lov allaqachon ko'rib chiqilgan!", show_alert=True)
    except Exception as e:
        await callback.answer(f"Xato: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("admin_reject_"))
async def cb_admin_reject(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    try:
        pid = int(callback.data.replace("admin_reject_", ""))
        p = await get_payment_by_id(pid)
        if p:
            await update_payment_status(pid, 'rejected')
            await bot.send_message(p['user_id'], "❌ To'lov chekingiz tasdiqlanmadi. Iltimos, ma'lumotlarni tekshirib qayta to'lov qiling.")
            try:
                await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n❌ <b>RAD ETILDI!</b>", reply_markup=None)
            except Exception:
                pass
            await callback.answer("❌ To'lov rad etildi!")
    except Exception as e:
        await callback.answer(f"Xato: {e}", show_alert=True)


# ============ PROFILNI ULASH (USERBOT SAAS) ============
@dp.message(F.text == "🔗 Profilni ulash (AI)")

@dp.message(F.text == "🔗 Instagramni ulash")
async def btn_link_instagram(message: types.Message):
    user_id = message.from_user.id
    has_access, status_text, days_left, tariff = await check_user_access(user_id)
    if not has_access:
        text = "вљ пёЏ <b>Sinov muddatingiz yoki tarifingiz tugagan!</b>\n\nAI yordamchisidan Instagram uchun foydalanish uchun tarif xarid qiling yoki do'stlarni taklif qilib bepul kun oling!"
        await message.answer(text, reply_markup=get_tariffs_keyboard())
        return

    from config import META_APP_ID, WEBHOOK_URL
    oauth_url = f"https://www.facebook.com/v19.0/dialog/oauth?client_id={META_APP_ID}&display=page&redirect_uri={WEBHOOK_URL}/oauth&response_type=code&scope=instagram_business_basic%2Cinstagram_business_manage_messages%2Cinstagram_business_manage_comments%2Cpages_manage_metadata%2Cpages_show_list%2Cpages_messaging&state={user_id}"
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Instagramni Ulash (Rasmiy)", url=oauth_url)]
    ])
    
    info_text = "🔗 <b>Instagram Direct va Kommentariyalarga AIni ulash</b>\n\n" \
                "рџ’Ў <b>Xavfsizlik eslatmasi:</b> Pastdagi tugma sizni to'g'ridan-to'g'ri <b>Meta (Facebook) ning rasmiy saytiga</b> olib kiradi. "\
                "Biz sizning parolingizni so'ramaymiz, ko'rmaymiz va saqlamaymiz! Barcha ulanishlar Meta tomonidan 100% qonuniy va himoyalangan tarzda amalga oshiriladi (Firibgarlikdan xavotir olmang).\n\n"\
                "<b>Shartlar:</b>\n"\
                "1. Instagram profilingiz 'Biznes' yoki 'Kreator' bo'lishi kerak.\n"\
                "2. Instagramingiz Facebook sahifasiga (Page) ulangan bo'lishi kerak.\n\n"\
                "рџ‘‡ <b>Tugmani bosing va Facebook orqali ruxsat bering:</b>"
                
    await message.answer(info_text, reply_markup=markup, disable_web_page_preview=True)

async def btn_link_profile(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Check if already connected
    user = await get_user(user_id)
    if user and user.get('session_string'):
        try:
            from userbot_manager import active_userbots
            if user_id in active_userbots:
                await message.answer("✅ <b>Sizning profilingiz allaqachon botga muvaffaqiyatli ulangan!</b>\nAI hozir xabarlaringizga javob bermoqda.\n\nAgar boshqa raqam ulamoqchi bo'lsangiz yoki muammo bo'lsa, adminga murojaat qiling.")
                return
        except Exception:
            pass

    has_access, status_text, days_left, tariff = await check_user_access(user_id)
    
    if not has_access:
        text = f"""РІС™В РїС‘РЏ <b>Sinov muddatingiz yoki tarifingiz tugagan!</b>

AI yordamchisidan foydalanish va profilingizni ulash uchun quyidagi tariflardan birini tanlang:

СЂСџвЂњРЉ <b>1. STANDART TARIF</b> РІР‚вЂќ <code>{TARIFFS['standart']['price']:,} so'm/oy</code> (15 000 so'm)
РІР‚Сћ 24/7 AI mijozlarga avtomatik matnli javob
РІР‚Сћ Savdo, xizmatlar va mahsulotlar tavsifi

🚀 <b>2. SMM PRO TARIFI</b> РІР‚вЂќ <code>{TARIFFS['smm']['price']:,} so'm/oy</code> (25 000 so'm)
РІР‚Сћ STANDART tarifidagi barcha imkoniyatlar
РІР‚Сћ СЂСџР‹в„ў Ovozli xabarlarga ovoz bilan javob berish (Audio)
РІР‚Сћ 📊 SMM va reklama yuborish statistikasi

<i>To'lov qilish uchun pastdagi kerakli tarif tugmasini bosing:</i>"""
        await message.answer(text, reply_markup=get_tariffs_keyboard())
        return
        
    await message.answer("📱 <b>Telegram raqamingizni kiriting yoxud pastdagi tugmani bosing:</b>\n<i>Format: +998901234567</i>", reply_markup=get_contact_keyboard())
    await state.set_state(LoginState.waiting_for_phone)

def normalize_phone(phone_input: str) -> str:
    import re
    digits = re.sub(r'\D', '', str(phone_input or ''))
    if not digits:
        return ""
    if len(digits) == 9:
        return f"+998{digits}"
    elif len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    else:
        return f"+{digits}"

@dp.message(LoginState.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    if message.text in ['❌ Bekor qilish', '/cancel', 'cancel']:
        await state.clear()
        await message.answer('Bekor qilindi.', reply_markup=get_main_menu(message.from_user.id))
        return
    raw_phone = message.contact.phone_number if message.contact else message.text
    if not raw_phone:
        return
        
    phone = normalize_phone(raw_phone)
    if not phone or len(phone) < 10:
        await message.answer("❌ <b>Telefon raqam noto'g'ri kiritildi!</b>\n\nIltimos, qaytadan kiriting (Masalan: <code>+998901234567</code> yoki <code>901234567</code>):")
        return
        
    await message.answer(f"⏳ <i>Kutib turing, Telegram'dan tasdiqlash kodi so'ralmoqda (Raqam: <code>{phone}</code>)...</i>")
    
    success, result = await request_code(message.from_user.id, phone)
    if success:
        await state.update_data(phone=phone)
        await state.set_state(LoginState.waiting_for_code)
        await message.answer(
            f"🔒 <b>TELEGRAM TASDIQLASH KODI YUBORILDI!</b>\n\n"
            f"📱 Raqam: <code>{phone}</code>\n\n"
            "Iltimos, rasmiy <b>Telegram</b> ilovangizga (rasmiy Telegram xabarlariga) kelgan 5 xonali kodni kiriting:\n"
            "• Qanday yozsangiz ham qabul qilinadi: <code>32222</code> yoki <code>3 2 2 2 2</code>\n"
            "• Yoki xabarni to'g'ridan-to'g'ri forward qiling!",
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        await message.answer(f"❌ <b>Xatolik yuz berdi:</b>\n<code>{result}</code>\n\nIltimos, raqam to'g'riligini tekshiring va qayta urinib ko'ring.", reply_markup=get_main_menu(message.from_user.id))
        await state.clear()

@dp.message(LoginState.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
    raw_text = message.text or ""
    
    if raw_text in ['❌ Bekor qilish', '/cancel', 'cancel', 'bekor']:
        await state.clear()
        await message.answer('Bekor qilindi.', reply_markup=get_main_menu(message.from_user.id))
        return

    import re
    # 5 xonali raqamni topish yoki barcha raqamlarni tozalab olish
    match = re.search(r'\b\d{5}\b', raw_text)
    if match:
        code = match.group(0)
    else:
        digits = re.sub(r'\D', '', raw_text)
        code = digits[:5] if len(digits) >= 5 else digits

    if not code or len(code) < 4:
        await message.answer("❌ <b>Kodni aniqlab bo'lmadi!</b>\n\nIltimos, Telegramdan kelgan 5 xonali tasdiqlash parolini yuboring (Masalan: <code>32222</code> yoki <code>3 2 2 2 2</code>):")
        return

    user_id = message.from_user.id
    
    await message.answer("⏳ <i>Tekshirilmoqda...</i>")
    success, msg = await submit_code(user_id, code)
    
    if success:
        await message.answer("✅ <b>Muvaffaqiyatli ulandi!</b>\nEndi AI profilingiz nomidan mijozlaringizga javob qaytaradi.", reply_markup=get_main_menu(message.from_user.id))
        await state.clear()
    elif msg == "PASSWORD_NEEDED":
        await message.answer("🔒 <b>2-bosqichli parol (Two-Step Verification) o'rnatilgan ekan.</b>\n\nIltimos, parolingizni kiriting:")
        await state.set_state(LoginState.waiting_for_password)
    else:
        await message.answer(f"❌ Kod xato yoki eskirgan:\n<code>{msg}</code>", reply_markup=get_main_menu(message.from_user.id))
        await state.clear()

@dp.message(LoginState.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    pwd = message.text.strip()
    user_id = message.from_user.id
    
    await message.answer("⏳ <i>Tekshirilmoqda...</i>")
    success, msg = await submit_code(user_id, "", password=pwd)
    
    if success:
        await message.answer("✅ <b>Muvaffaqiyatli ulandi!</b>\nEndi AI profilingiz nomidan mijozlaringizga javob qaytaradi.", reply_markup=get_main_menu(message.from_user.id))
        await state.clear()
    else:
        await message.answer(f"❌ Parol xato:\n<code>{msg}</code>", reply_markup=get_main_menu(message.from_user.id))
        await state.clear()

@dp.callback_query(F.data == "set_biz_info")
async def cb_set_biz_info(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📝 <b>Sizning biznesingiz haqida ma'lumot kiriting:</b>\n\nMasalan:\n<i>Biz IT Academy o'quv markazimiz. Dasturlash kurslarimiz narxi 500 ming so'm. Hozirda 30% chegirma ketyapti. Manzilimiz Toshkent shahar...</i>\n\nIltimos, biznesingiz, narxlar va muhim yangiliklarni bitta xabarda batafsil yozib yuboring:")
    await state.set_state(LoginState.waiting_for_business_info)
    await callback.answer()

@dp.message(LoginState.waiting_for_business_info)
async def process_biz_info(message: types.Message, state: FSMContext):
    text = message.text.strip()
    await update_business_info(message.from_user.id, text)
    await message.answer("✅ <b>Biznesingiz haqidagi ma'lumotlar saqlandi!</b>\nEndi AI mijozlarga aynan shu ma'lumotlar asosida sotuv qiladi va xizmat ko'rsatadi.", reply_markup=get_main_menu(message.from_user.id))
    await state.clear()


@dp.callback_query(F.data.startswith("grp_toggle_"))
async def cb_grp_toggle(callback: CallbackQuery):
    user_id = callback.from_user.id
    new_val = 1 if callback.data == "grp_toggle_on" else 0
    await update_group_settings(user_id, group_reply_enabled=new_val)
    user = await get_user(user_id)
    await callback.message.edit_reply_markup(reply_markup=get_ai_settings_keyboard(user))
    await callback.answer("Guruh sozlamalari yangilandi!")

@dp.callback_query(F.data == "set_channel_link")
async def cb_set_link(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔗 <b>Sizning shaxsiy Kanalingiz yoki Guruhingiz linkini kiriting:</b>\n\n(Masalan: <i>https://t.me/mening_kanalim</i> yoki <i>@mening_kanalim</i>)\nAI bu linkdan foydalanib odamlarni o'sha yerga yo'naltiradi.")
    await state.set_state(LoginState.waiting_for_channel_link)
    await callback.answer()

@dp.message(LoginState.waiting_for_channel_link)
async def process_link(message: types.Message, state: FSMContext):
    link = message.text.strip()
    await update_group_settings(message.from_user.id, channel_link=link)
    await message.answer("✅ <b>Link muvaffaqiyatli saqlandi!</b>", reply_markup=get_main_menu(message.from_user.id))
    await state.clear()



@dp.callback_query(F.data == "set_client_broadcast")
async def cb_client_broadcast(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    has_access, _, _, tariff = await check_user_access(user_id)
    if tariff != 'smm':
        await callback.answer("РІС™В РїС‘РЏ Bu xususiyat faqat SMM PRO tarifida mavjud!", show_alert=True)
        return
        
    await callback.message.edit_text("📢 <b>O'z mijozlaringizga xabar tarqatish:</b>\n\nSizning ushbu akkauntingizga oldin yozgan barcha foydalanuvchilarga avtomatik xabar (matn yoki ovozli) tarqatamiz.\n\nIltimos, tarqatmoqchi bo'lgan xabaringizni yuboring (Yoki Bekor qilishni bosing):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="cancel_client_broadcast")]]))
    await state.set_state(LoginState.waiting_for_client_broadcast)
    await callback.answer()

@dp.callback_query(F.data == "show_my_stats")
async def cb_show_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    from database import db
    broadcasts = await db['broadcasts'].find({'user_id': user_id}).sort('date', -1).to_list(length=10)
    
    if not broadcasts:
        await callback.answer("Hali statistika yo'q. Oldin xabar tarqating!", show_alert=True)
        return
        
    text = "📊 <b>SMM YANGILIK TARQATISH STATISTIKASI:</b>\n\n"
    total_sent = 0
    for b in broadcasts:
        d_str = b['date'].strftime('%Y-%m-%d %H:%M')
        sc = b.get('sent_count', 0)
        total_sent += sc
        text += f"СЂСџвЂњвЂ¦ {d_str} - <b>{sc} ta</b> mijozga yetkazildi\n"
        
    text += f"\nСЂСџРЏвЂ  JAMI YETKAZILGAN XABARLAR: <b>{total_sent} ta</b>\n"
    text += "\n<i>Eslatma: Qiziqqan mijozlar bot orqali bevosita yozganda AI ular bilan savdo qilib yozishishda davom etadi.</i>"
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="cancel_client_broadcast")]]))

@dp.callback_query(F.data == "cancel_client_broadcast")
async def cb_cancel_client_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await get_user(callback.from_user.id)
    await callback.message.edit_text("СЂСџВ¤вЂ“ <b>AI Yordamchi Sozlamalari</b>", reply_markup=get_ai_settings_keyboard(user))

@dp.message(LoginState.waiting_for_client_broadcast)
async def process_client_broadcast(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id not in load_active_userbots.__globals__['active_userbots']:
        await message.answer("РІС™В РїС‘РЏ Sizning profilingiz hozircha ulanmagan. Iltimos oldin 'Profilni ulash' orqali ulaning.")
        await state.clear()
        return
        
    client = load_active_userbots.__globals__['active_userbots'][user_id]
    
    await message.answer("⏳ <i>Xabar barcha mijozlaringizga yuborilmoqda. Bu biroz vaqt olishi mumkin...</i>")
    
    import asyncio
    async def send_broadcast():
        try:
            sent_count = 0
            dialogs = await client.get_dialogs(limit=100)
            for d in dialogs:
                if d.is_user and not d.entity.bot and not d.entity.is_self:
                    try:
                        if message.voice:
                            await client.send_file(d.entity, message.voice.file_id, voice_note=True)
                        else:
                            await client.send_message(d.entity, message.text or message.caption or "...")
                        sent_count += 1
                        await asyncio.sleep(2) # Prevent spam limits
                    except:
                        pass
            await bot.send_message(user_id, f"✅ <b>Yangilik tarqatish yakunlandi!</b>\nJami {sent_count} ta mijozingizga xabar yetkazildi.")
        except Exception as e:
            await bot.send_message(user_id, f"❌ Tarqatishda xatolik: {e}")
            
    asyncio.create_task(send_broadcast())
    await state.clear()



# ============ ADMIN PANEL ============
def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="СЂСџвЂТђ Barcha Obunachilar", callback_data="admin_users")],
        [InlineKeyboardButton(text="⏳ Kutilyotgan To'lovlar", callback_data="admin_payments")],
        [InlineKeyboardButton(text="📢 Reklama Tarqatish", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="💰 Tarif Narxlari", callback_data="admin_prices")],
        [InlineKeyboardButton(text="📊 Umumiy Statistika", callback_data="admin_stats")]
    ])

@dp.message(F.text == "/admin")
async def cmd_admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("СЂСџвЂвЂ <b>Boshqaruv Paneliga Xush Kelibsiz!</b>\n\nQuyidagi menyudan kerakli bo'limni tanlang:", reply_markup=get_admin_keyboard())

@dp.callback_query(F.data.startswith("admin_"))
async def cb_admin_panel(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
        
    action = callback.data.split('_')[1]
    
    if action == "users":
        count = await users_col.count_documents({})
        active = len(load_active_userbots.__globals__['active_userbots'])
        await callback.message.edit_text(f"СЂСџвЂТђ <b>OBUNACHILAR:</b>\n\nUmumiy botdan foydalanganlar: <b>{count} ta</b>\nHozirda faol ulangan AI'lar: <b>{active} ta</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]]))
        
    elif action == "broadcast":
        await callback.message.edit_text("📢 <b>REKLAMA TARQATISH:</b>\n\nBotdagi barcha foydalanuvchilarga xabar tarqatish uchun xabaringizni yuboring (Rasm, Video yoki Matn):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_back")]]))
        await state.set_state(LoginState.waiting_for_admin_broadcast)
        
    elif action == "payments":
        pending = await db['payments'].find({'status': 'pending'}).to_list(length=10)
        if not pending:
            await callback.message.edit_text("✅ Ayni vaqtda kutilyotgan to'lovlar yo'q.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]]))
            return
            
        text = f"⏳ <b>KUTILYOTGAN TO'LOVLAR ({len(pending)} ta):</b>\n\n"
        for p in pending:
            text += f"💳 <b>ID:</b> #{p['id']}\nСЂСџвЂВ¤ <b>Foydalanuvchi:</b> <code>{p['user_id']}</code>\n💰 <b>Summa:</b> {p['amount']:,} so'm ({p['tariff_type'].upper()})\n\n"
            
        text += "<i>To'lovlarni tasdiqlash uchun oldin kelgan chek rasmiga qarang (Tasdiqlash tugmasi rasm tagida joylashgan). Yoki ID orqali tasdiqlang: /approve_ID</i>"
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]]))

    elif action == "prices":
        settings = await get_settings()
        sp = settings.get('standard_price', 150000)
        smm_p = settings.get('smm_price', 300000)
        await callback.message.edit_text(f"💰 <b>TARIF NARXLARI:</b>\n\n📦 Standart: <b>{sp:,} so'm</b>\n💎 SMM PRO: <b>{smm_p:,} so'm</b>\n\n<i>O'zgartirish uchun chatga yozing:</i>\n<code>/narx_standart 150000</code>\n<code>/narx_smm 300000</code>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]]))
        
    elif action == "stats":
        total_payments = await db['payments'].count_documents({'status': 'approved'})
        await callback.message.edit_text(f"📊 <b>TIZIM STATISTIKASI:</b>\n\nMuvaffaqiyatli to'lovlar: <b>{total_payments} ta</b>\nQolgan statistika tez orada qo'shiladi.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]]))
        
    elif action == "back":
        await callback.message.edit_text("СЂСџвЂвЂ <b>Boshqaruv Paneliga Xush Kelibsiz!</b>\n\nQuyidagi menyudan kerakli bo'limni tanlang:", reply_markup=get_admin_keyboard())

# Add new State for admin broadcast


@dp.message(LoginState.waiting_for_admin_broadcast)
async def process_admin_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    
    users = await users_col.find({}).to_list(length=10000)
    await message.answer(f"⏳ <i>Xabar {len(users)} ta foydalanuvchiga yuborilmoqda...</i>")
    
    sent = 0
    import asyncio
    for u in users:
        try:
            await message.copy_to(u['user_id'])
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
            
    await message.answer(f"✅ <b>REKLAMA TARQATILDI!</b>\n\nJami yetkazildi: <b>{sent} ta</b> foydalanuvchiga.", reply_markup=get_admin_keyboard())
    await state.clear()

# ============ TEXT MESSAGES (AI JAVOB) ============
@dp.message(F.text == "🔙 Bekor qilish")
async def btn_cancel_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Amal bekor qilindi.", reply_markup=get_main_menu(message.from_user.id))

@dp.message(F.text)
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # Admin approve / reject / broadcast
    if user_id == ADMIN_ID:
        if text.startswith('/narx_standart '):
            try:
                price = int(text.split(' ')[1].replace(',', '').replace('.', ''))
                await update_settings(standard_price=price)
                await message.answer(f"✅ Standart tarif narxi {price:,} so'm qilib belgilandi.")
            except:
                await message.answer("❌ Xato format. Namuna: /narx_standart 150000")
            return
            
        elif text.startswith('/narx_smm '):
            try:
                price = int(text.split(' ')[1].replace(',', '').replace('.', ''))
                await update_settings(smm_price=price)
                await message.answer(f"✅ SMM PRO tarif narxi {price:,} so'm qilib belgilandi.")
            except:
                await message.answer("❌ Xato format. Namuna: /narx_smm 300000")
            return
            
        if text.startswith('/approve_'):
            try:
                pid = int(text.split('_')[1])
                p = await get_payment_by_id(pid)
                if p and p['status'] == 'pending':
                    await update_payment_status(pid, 'approved')
                    await activate_tariff(p['user_id'], p['tariff_type'], days=30)
                    await bot.send_message(p['user_id'], f"СЂСџР‹вЂ° <b>TO'LOVINGIZ TASDIQLANDI!</b>\n\n📦 <b>{p['tariff_type'].upper()}</b> tarifi 30 kunga faollashtirildi!\nBarcha savollaringizga mamnuniyat bilan javob beraman.")
                    await message.answer(f"✅ <code>#{pid}</code> to'lov tasdiqlandi!")
                else:
                    await message.answer("❌ To'lov topilmadi yoki ko'rib chiqilgan.")
            except Exception as e:
                await message.answer(f"❌ Xato: {e}")
            return

        elif text.startswith('/reject_'):
            try:
                pid = int(text.split('_')[1])
                p = await get_payment_by_id(pid)
                if p:
                    await update_payment_status(pid, 'rejected')
                    await bot.send_message(p['user_id'], "❌ To'lov chekingiz tasdiqlanmadi. Iltimos, qayta to'lov qilib to'g'ri chekni yuboring.")
                    await message.answer(f"❌ <code>#{pid}</code> to'lov rad etildi.")
            except Exception as e:
                await message.answer(f"❌ Xato: {e}")
            return

        elif text.startswith('/broadcast'):
            msg = text.replace('/broadcast', '').strip()
            if not msg:
                await message.answer("❌ Xabar matnini kiriting: <code>/broadcast Salom!</code>")
                return
            cursor = users_col.find({})
            users = await cursor.to_list(length=5000)
            sent = 0
            for u in users:
                try:
                    await bot.send_message(u['user_id'], f"📢 <b>YANGILIK:</b>\n\n{msg}")
                    sent += 1
                    await asyncio.sleep(0.1)
                except Exception:
                    pass
            await message.answer(f"✅ Xabar {sent} ta foydalanuvchiga yuborildi.")
            return

    await add_user(user_id, message.from_user.username or "", message.from_user.full_name or "")

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(1.0)

    response = await get_ai_response(text, user_id)
    await message.answer(response)
    await save_message(user_id, text, response)

# ============ ISHGA TUSHIRISH (24/7 RESILIENT LOOP) ============
async def check_expired_trials_cron():
    """Har 15 daqiqada sinov muddati (3 kun) yoki tarifi tugagan foydalanuvchilarni tekshirib, eslatma yuboradi"""
    while True:
        try:
            now = datetime.now()
            # 1. Sinov muddati (3 kun) tugaganlarni tekshirish
            cursor = users_col.find({
                "tariff_type": "trial",
                "expired_notified": {"$ne": True}
            })
            users = await cursor.to_list(length=1000)
            for u in users:
                t_end = u.get("tariff_end")
                if t_end:
                    try:
                        end_dt = datetime.fromisoformat(t_end)
                        if now >= end_dt:
                            markup = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="💳 Tarif sotib olish", callback_data="btn_tariffs")]
                            ])
                            text = (
                                "⏳ <b>3 KUNLIK BEPUL SINOV MUDDATI TUGADI!</b>\n\n"
                                f"Hurmatli <b>{u.get('full_name', 'Foydalanuvchi')}</b>, profilingizga berilgan 3 kunlik sinov muddati yakuniga yetdi.\n\n"
                                "🚀 <b>AI xizmati uzilib qolmasligi uchun</b> quyidagi tugma orqali tarif xarid qiling va sun'iy intellektni faollashtiring!"
                            )
                            await bot.send_message(chat_id=u["user_id"], text=text, reply_markup=markup)
                            await users_col.update_one({"user_id": u["user_id"]}, {"$set": {"expired_notified": True, "ai_enabled": 0}})
                    except Exception:
                        pass

            # 2. Pullik tarif muddati (30 kun) tugaganlarni tekshirish
            paid_cursor = users_col.find({
                "tariff_type": {"$in": ["standart", "smm"]},
                "expired_notified": {"$ne": True}
            })
            paid_users = await paid_cursor.to_list(length=1000)
            for u in paid_users:
                t_end = u.get("tariff_end")
                if t_end:
                    try:
                        end_dt = datetime.fromisoformat(t_end)
                        if now >= end_dt:
                            markup = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="💳 Tarifni uzaytirish", callback_data="btn_tariffs")]
                            ])
                            text = (
                                "РІС™В РїС‘РЏ <b>TARIFINGIZ MUDDATI TUGADI!</b>\n\n"
                                f"Hurmatli <b>{u.get('full_name', 'Foydalanuvchi')}</b>, sizning 30 kunlik <b>{u.get('tariff_type', '').upper()}</b> tarifingiz muddati o'z nihoyasiga yetdi.\n\n"
                                "AI yordamchisi profilingizda ishlashni to'xtatdi. Xizmatni davom ettirish uchun tarifni yangilang!"
                            )
                            await bot.send_message(chat_id=u["user_id"], text=text, reply_markup=markup)
                            await users_col.update_one({"user_id": u["user_id"]}, {"$set": {"expired_notified": True, "ai_enabled": 0}})
                    except Exception:
                        pass

        except Exception as e:
            print(f"[Cron Error] {e}")
        await asyncio.sleep(900) # Har 15 daqiqada tekshiradi

async def start_polling_loop():
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, handle_signals=False)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Polling Ogohlantirish] {e}. 5 soniyadan so'ng qayta ulanadi...")
            await asyncio.sleep(5)

from web_server import start_web_server

async def main():
    print("[1/2] MongoDB Atlas bazasiga ulanmoqda...")
    await init_db()

    print("[2/2] Telegram Bot ishga tushmoqda...")
    bot_info = await bot.get_me()
    print(f"✅ BOT TAYYOR: @{bot_info.username} ({bot_info.first_name})")
    print(f"СЂСџвЂвЂ Admin ID: {ADMIN_ID}")
    print("СЂСџВ¤вЂ“ Xabarlar qabul qilinmoqda...")

    print("[3/3] Faol profil ulanishlari yuklanmoqda (SaaS)...")
    cursor = users_col.find({})
    await load_active_userbots(cursor)

    # Orqa fonda avtomatik eslatma cronini yoqish
    asyncio.create_task(check_expired_trials_cron())
    asyncio.create_task(start_web_server(bot))

    if os.environ.get("VERCEL"):
        # Vercel serverless РІР‚вЂќ faqat webhook orqali ishlaydi, polling yo'q
        print("СЂСџРЉС’ VERCEL MODE: Polling o'chirilgan, faqat webhook.")
        port = int(os.environ.get("PORT", 8080))
        try:
            from aiohttp import web as aio_web
            async def health(request):
                return aio_web.Response(text="OK")
            _app = aio_web.Application()
            _app.router.add_get("/", health)
            _runner = aio_web.AppRunner(_app)
            await _runner.setup()
            _site = aio_web.TCPSite(_runner, "0.0.0.0", port)
            await _site.start()
        except Exception as _e:
            print(f"[HTTP] {_e}")
        while True:
            await asyncio.sleep(3600)
    elif os.environ.get("USERBOTS_ONLY"):
        # Faqat userbot daemon rejimi (lokal kompyuter uchun)
        print("СЂСџВ¤вЂ“ USERBOT ONLY MODE: Polling o'chirilgan.")
        while True:
            await asyncio.sleep(3600)
    else:
        # To'liq rejim: Railway yoki lokal РІР‚вЂќ polling + userbotlar birga ishlaydi
        print("🚀 TO'LIQ REJIM: Bot polling + Userbotlar birga ishlamoqda.")
        await start_polling_loop()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot to'xtatildi!")
    except Exception as e:
        print(f"\nXatolik: {e}")






