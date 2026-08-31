import asyncio
from telethon import TelegramClient, events
import datetime

def dlog(msg):
    with open('debug.log', 'a', encoding='utf-8') as f:
        f.write(f"{datetime.datetime.now()} - {msg}\n")

from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError
from database import update_user_persona, get_user, check_user_access, get_user_messages, save_message
from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_API_KEY_BACKUP
import os

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
groq_backup_client = AsyncGroq(api_key=GROQ_API_KEY_BACKUP) if GROQ_API_KEY_BACKUP else None

# Xotirada ishlayotgan userbotlar ro'yxati
active_userbots = {}
# Log in jarayonidagi mijozlar
login_clients = {}

async def get_ai_reply(text: str, user_id: int, user_info: dict, sender_name: str, tariff: str, chat_id: int = None) -> str:
    has_access, status, days, tariff = await check_user_access(user_id)
    if not has_access:
        return "" # Tarif tugasa javob bermaydi

    history = await get_user_messages(user_id, chat_id=chat_id, limit=8)
    history_text = "\n".join([f"{h.get('sender_name', 'Mijoz')}: {h['message']}\nSiz: {h['response']}" for h in history])
    owner_name = user_info.get("full_name", "Men")

    biz_info = user_info.get('business_info', 'Hozircha ma\'lumot kiritilmagan.')
    channel_link = user_info.get('channel_link', '')
    persona_text = user_info.get('persona', '')
    channel_text = f"Mijozga kerak bo'lsa ushbu kanalimiz/guruhimiz linkini bering: {channel_link}" if channel_link else ""
    
    system_prompt = f"""Siz {owner_name} ning shaxsiy yordamchisisiz. Siz SMM menejer, sotuvchi va konsultantsiz.
SIZNING SHAXSIY XARAKTERINGIZ VA GAPIRISH USLUBINGIZ (Bunga qat'iy amal qiling):
{persona_text}

Mijozning ismi: {sender_name}. Agar birinchi marta salomlashayotgan bo'lsangiz albatta uning ismini aytib "Salom {sender_name}, yordam kerakmi?" deb tabiiy so'rang. 
Hadeb "Qanday yordam beray?" demang. Har xil, tabiiy jumlalarni ("Ma'lumotlarimiz yoqdimi?", "Yana qanday yordam bera olaman?" kabi) ishlating.

Sizning BIZNESINGIZ (Mahsulotlar, Narxlar, Yangiliklar) HAQIDA TO'LIQ MA'LUMOT:
{biz_info}

VAZIFA:
1. Aynan yuqoridagi BIZNES ma'lumotlaridan foydalanib mijozga urg'u bering (reklama qiling, soting).
2. MUHIM - TIL VA ALIFBO: Mijoz sizga qaysi tilda (Inglizcha, Ruscha, O'zbekcha) yozsa AYNAN O'SHA TILDA javob bering! Agar mijoz Krill alifbosida yozsa, SIZ HAM KRILLDA yozing. Agar Lotinda yozsa, Lotinda yozing!
3. {channel_text}
4. Mijozga aslo "Men AI botman" demang. Siz odamsiz.
5. Oldingi suhbat tarixini eslab qoling va mijoz so'ragan narsalarni doim xotirada tuting.

SUHBAT TARIXI (Ushbu mijoz bilan):
{history_text}"""

    # 1. Try primary Groq
    if groq_client:
        try:
            resp = await groq_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.6,
                max_tokens=250
            )
            return resp.choices[0].message.content
        except Exception as e:
            dlog(f"Primary Groq Xatosi: {e}")

    # 2. Try backup Groq
    if groq_backup_client:
        try:
            resp = await groq_backup_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.6,
                max_tokens=250
            )
            return resp.choices[0].message.content
        except Exception as e:
            dlog(f"Backup Groq Xatosi: {e}")

    # 3. Try Gemini as final fallback
    try:
        import google.generativeai as genai
        from config import GEMINI_API_KEY
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-pro")
            full_prompt = f"{system_prompt}\n\nMijoz: {text}\nSiz:"
            res = model.generate_content(full_prompt)
            return res.text
    except Exception as e2:
        dlog(f"Gemini API Xatosi: {e2}")

    return ""

async def on_new_userbot_message(event):
    me = await event.client.get_me()
    owner_id = getattr(event.client, 'owner_id', None)
    if not owner_id:
        return

    user_info = await get_user(owner_id)
    if not user_info:
        return

    # Check if group reply is allowed
    is_group = not event.is_private
    if is_group:
        if not user_info.get("group_reply_enabled", 0):
            return
        if not event.mentioned:
            return

    sender = await event.get_sender()
    
    if sender.id == me.id or sender.bot:
        return

    text = event.raw_text or ""
    
    # Check for Voice or Video Note
    if getattr(event, 'voice', None) or getattr(event, 'video_note', None):
        try:
            import os, uuid
            media_path = await event.download_media(file=f"temp_audio_{uuid.uuid4().hex}.ogg")
            if media_path:
                with open(media_path, "rb") as file:
                    transcription = await groq_client.audio.transcriptions.create(
                        file=(media_path, file.read()),
                        model="whisper-large-v3",
                        response_format="text",
                        language="uz"
                    )
                text = str(transcription)
                os.remove(media_path)
        except Exception as e:
            dlog(f"Audio/Video transcription xatosi: {e}")

    if not text:
        return

    # User_id ni topish (qaysi klient bu userbot egasi)
    owner_id = getattr(event.client, 'owner_id', None)
    if not owner_id:
        return

    # Tarifni tekshirish
    user_info = await get_user(owner_id)
    if not user_info or not user_info.get("ai_enabled", 1):
        return

    has_access, status_text, days_left, tariff = await check_user_access(owner_id)
    if not has_access:
        from database import users_col
        u = await users_col.find_one({"user_id": owner_id})
        if u and not u.get('expired_notified'):
            from main import bot
            try:
                await bot.send_message(
                    owner_id,
                    "⚠️ <b>Diqqat!</b>\n\nSizning 3 kunlik sinov muddatingiz yoki tarifingiz o'z nihoyasiga yetdi. AI avtomatik ravishda to'xtatildi.\n\nIltimos, AI xizmatidan uzluksiz foydalanish uchun <b>💳 Tariflar</b> bo'limidan mos tarifni xarid qiling!"
                )
                await users_col.update_one({'user_id': owner_id}, {'$set': {'expired_notified': True}})
            except Exception:
                pass
        return

    dlog(f"[{owner_id}] Yangi xabar keldi: {text}")
    
    # Check if owner is online/active IN THIS EXACT CHAT
    last_active = owner_last_active.get((owner_id, event.chat_id), 0)
    if time.time() - last_active < 30: # 30 seconds pause if owner is chatting in this dialogue
        dlog(f"[{owner_id}] Egasi ushbu chatda onlayn (oxirgi marta {int(time.time() - last_active)}s oldin yozdi). AI aralashmaydi.")
        return
        
    # Check access again for tariff logic inside the event
    has_access, _, _, tariff = await check_user_access(owner_id)
    if not has_access: return
    
    sender_name = getattr(sender, 'first_name', 'Mijoz') or 'Mijoz'
    
    async with event.client.action(event.chat_id, 'typing'):
        reply = await get_ai_reply(text, owner_id, user_info, sender_name, tariff, chat_id=event.chat_id)
        
    dlog(f"[{owner_id}] AI javobi: {reply}")
    if reply:
        await event.reply(reply)
        
        # OVOZLI XABAR SMM TARIFIDA VA FAQAT MIJOZ GOLOS/VIDEO TASHlasa YOQILADI
        is_voice_req = bool(getattr(event, 'voice', None) or getattr(event, 'video_note', None))
        if tariff == 'smm' and is_voice_req:
            try:
                import edge_tts
                import uuid
                import os
                voice_file = f"voice_{uuid.uuid4().hex}.ogg"
                communicate = edge_tts.Communicate(reply, 'uz-UZ-SardorNeural')
                await communicate.save(voice_file)
                await event.client.send_file(event.chat_id, voice_file, voice_note=True)
                if os.path.exists(voice_file):
                    os.remove(voice_file)
            except Exception as e:
                dlog(f"Golos xatosi: {e}")
                
        await save_message(owner_id, text, reply, chat_id=event.chat_id, sender_name=sender_name)
    else:
        dlog(f"[{owner_id}] AI bo'sh javob qaytardi, xabar yuborilmadi.")

async def request_code(user_id: int, phone: str):
    session_path = f"sessions/{user_id}"
    
    # Stale sessiyalarni tozalash
    if user_id in login_clients:
        try:
            await login_clients[user_id]['client'].disconnect()
        except Exception:
            pass
        login_clients.pop(user_id, None)

    if user_id in active_userbots:
        try:
            await active_userbots[user_id].disconnect()
        except Exception:
            pass
        active_userbots.pop(user_id, None)

    # Yangi login boshlanayotganda eskirgan yarim-chala sessiyani tozalash
    for ext in [".session", ".session-journal"]:
        f_p = f"sessions/{user_id}{ext}"
        if os.path.exists(f_p):
            try:
                os.remove(f_p)
            except Exception:
                pass

    os.makedirs("sessions", exist_ok=True)
    client = TelegramClient(session_path, API_ID, API_HASH)
    
    try:
        # 15 soniya timeout bilan ulanish
        await asyncio.wait_for(client.connect(), timeout=15.0)
        
        if not client.is_connected():
            return False, "Telegram serveriga ulanib bo'lmadi. Qayta urinib ko'ring."

        try:
            # 20 soniya timeout bilan kod so'rash
            result = await asyncio.wait_for(
                client.send_code_request(phone),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            await client.disconnect()
            return False, "Telegram javob bermadi (timeout). Qayta urinib ko'ring."
        except Exception as e_req:
            if "AuthRestart" in str(e_req) or "restart" in str(e_req).lower():
                await asyncio.sleep(1)
                result = await asyncio.wait_for(
                    client.send_code_request(phone),
                    timeout=20.0
                )
            else:
                raise e_req

        login_clients[user_id] = {
            'client': client,
            'phone': phone,
            'phone_code_hash': getattr(result, 'phone_code_hash', None)
        }
        return True, "Kod yuborildi"
    except asyncio.TimeoutError:
        try:
            await client.disconnect()
        except Exception:
            pass
        return False, "Ulanish vaqti tugadi (timeout). Internet aloqangizni tekshiring."
    except FloodWaitError as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return False, f"Ko'p urinish. {e.seconds} soniya kuting."
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return False, str(e)


async def submit_code(user_id: int, code: str, password: str = None):
    if user_id not in login_clients:
        return False, "Sessiya topilmadi. Qaytadan urinib ko'ring."
    
    data = login_clients[user_id]
    client: TelegramClient = data['client']
    phone = data['phone']
    phone_code_hash = data.get('phone_code_hash')
    
    try:
        if not client.is_connected():
            await client.connect()
            
        if password:
            await client.sign_in(password=password)
        else:
            if phone_code_hash:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            else:
                await client.sign_in(phone=phone, code=code)
            
        me = await client.get_me()
        
        # Userbot muvaffaqiyatli ishga tushdi
        client.owner_id = user_id
        client.add_event_handler(on_new_userbot_message, events.NewMessage(incoming=True))
        client.add_event_handler(on_outgoing_message, events.NewMessage(outgoing=True))
        client.add_event_handler(on_incoming_call, events.Raw())
        
        active_userbots[user_id] = client
        login_clients.pop(user_id, None)
        
        asyncio.create_task(extract_and_save_persona(client, user_id))
        
        return True, "Success"
    except SessionPasswordNeededError:
        return False, "PASSWORD_NEEDED"
    except PhoneCodeInvalidError:
        return False, "Noto'g'ri kod."
    except Exception as e:
        return False, str(e)


async def extract_and_save_persona(client, user_id):
    try:
        sample_messages = []
        dialogs = await client.get_dialogs(limit=20)
        for d in dialogs:
            if d.is_user and not d.entity.bot:
                async for msg in client.iter_messages(d.entity, limit=15):
                    if msg.out and msg.text and len(msg.text.strip()) > 3:
                        sample_messages.append(msg.text.strip())
                        if len(sample_messages) >= 60: break
            if len(sample_messages) >= 60: break
            
        if sample_messages:
            corpus = "\n".join(sample_messages[:60])
            prompt = f"Quyida foydalanuvchining haqiqiy yozishmalari keltirilgan:\n{corpus}\n\nUning gapirish uslubi, so'z boyligi, xarakterini tahlil qiling va qisqacha System Prompt yozing (Masalan: 'Sizning uslubingiz qisqa, hazilkash va samimiy. Siz odatda ... so'zlarini ishlatasiz')."
            
            resp = await groq_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            persona = resp.choices[0].message.content
            await update_user_persona(user_id, persona)
            dlog(f"[{user_id}] Persona yaratildi: {persona}")
    except Exception as e:
        dlog(f"[{user_id}] Persona yaratishda xato: {e}")


import time
from telethon.tl.types import UpdatePhoneCall
from telethon import events

owner_last_active = {}

async def on_outgoing_message(event):
    owner_id = getattr(event.client, 'owner_id', None)
    if owner_id:
        owner_last_active[(owner_id, event.chat_id)] = time.time()
        
async def on_incoming_call(event):
    from telethon.tl.types import UpdatePhoneCall
    from telethon.tl.functions.phone import DiscardCallRequest
    from telethon.tl.types import PhoneCallDiscardReasonBusy

    if not isinstance(event, UpdatePhoneCall):
        return
        
    owner_id = getattr(event.client, 'owner_id', None)
    if not owner_id: return
    
    try:
        # Check if it's a requested/incoming call
        if hasattr(event.phone_call, 'participant_id'):
            caller_id = event.phone_call.participant_id
        else:
            caller_id = getattr(event.phone_call, 'admin_id', None)
            
        if caller_id and caller_id != owner_id:
            # Send message
            await event.client.send_message(caller_id, "Hozircha qo'ng'iroqlarga javob bera olmayman 📵\nIltimos, nima masala ekanligini yozma ravishda yoki ovozli xabar orqali qoldiring.")
            dlog(f"[{owner_id}] Qong'iroqqa avtomatik javob yuborildi (Caller: {caller_id}).")
            
            # Reject call
            try:
                await event.client(DiscardCallRequest(
                    peer=event.phone_call,
                    duration=0,
                    reason=PhoneCallDiscardReasonBusy(),
                    connection_id=0
                ))
                dlog(f"[{owner_id}] Qong'iroq rad etildi (Busy).")
            except Exception as e2:
                dlog(f"Go'shakni qo'yishda xato: {e2}")
                
    except Exception as e:
        dlog(f"Qong'iroq xatosi: {e}")

async def load_active_userbots(users_cursor):
    """Bot qayta yonganda barcha aktiv userbotlarni ishga tushirish"""
    print("Userbotlar tekshirilmoqda...")
    try:
        users = await users_cursor.to_list(length=1000)
    except Exception as e:
        print(f"[load_active_userbots] DB Cursor Error: {e}")
        return

    for u in users:
        user_id = u.get('user_id')
        if not user_id:
            continue
        session_path = f"sessions/{user_id}.session"
        if os.path.exists(session_path):
            try:
                has_access, _, _, _ = await check_user_access(user_id)
                if has_access and u.get("ai_enabled", 1):
                    client = TelegramClient(f"sessions/{user_id}", API_ID, API_HASH)
                    try:
                        await asyncio.wait_for(client.connect(), timeout=3.0)
                    except Exception:
                        continue
                    if await client.is_user_authorized():
                        client.owner_id = user_id
                        client.add_event_handler(on_new_userbot_message, events.NewMessage(incoming=True))
                        client.add_event_handler(on_outgoing_message, events.NewMessage(outgoing=True))
                        client.add_event_handler(on_incoming_call, events.Raw())
                        active_userbots[user_id] = client
                        print(f"[Userbot] {user_id} - faol.")
                    else:
                        await client.disconnect()
            except Exception as e:
                print(f"[Userbot] {user_id} xatolik: {e}")
