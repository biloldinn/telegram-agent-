import asyncio
import os
import time
import tempfile
import httpx
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.tl.types import UpdatePhoneCall, PhoneCallDiscardReasonBusy
from telethon.tl.functions.phone import DiscardCallRequest
from config import GROQ_API_KEY, GROQ_API_KEY_BACKUP, GEMINI_API_KEY, API_ID, API_HASH
from database import get_user, update_user_api, users_col, check_user_access
from groq import AsyncGroq
import google.generativeai as genai
import edge_tts

groq_client = AsyncGroq(api_key=GROQ_API_KEY)
groq_backup = AsyncGroq(api_key=GROQ_API_KEY_BACKUP)
genai.configure(api_key=GEMINI_API_KEY)

active_userbots = {}
owner_last_active = {}
MAX_SILENCE = 120

def dlog(msg):
    print(f"[Telethon] {msg}")

async def transcribe_audio_groq(file_path):
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "audio/ogg"), "model": (None, "whisper-large-v3")}
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, files=files, timeout=60.0)
                if resp.status_code == 200:
                    return resp.json().get("text", "")
                else:
                    dlog(f"Groq STT Error: {resp.text}")
    except Exception as e:
        dlog(f"STT Exception: {e}")
    return ""

async def generate_speech(text, output_file):
    try:
        # Tildan kelib chiqib ovozni tanlash
        voice = "uz-UZ-MadinaNeural"
        
        import re
        cyrillic_chars = len(re.findall(r'[а-яА-ЯёЁ]', text))
        if cyrillic_chars > len(text) * 0.2:
            # Matnda yetarlicha ruscha (kirillcha) harflar bo'lsa
            voice = "ru-RU-SvetlanaNeural" 
            
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        return True
    except Exception as e:
        dlog(f"TTS Error: {e}")
        return False

async def get_ai_reply(prompt, persona_text):
    sys_prompt = (
        "Sen aqlli sotuvchi va xizmat ko'rsatish menejerisan. "
        "QOIDALAR:\n"
        "1. Mijoz qaysi tilda yozsa, sening ham javobing xuddi shu tilda bo'lsin (ruscha yozsa ruscha, inglizcha yozsa inglizcha, o'zbekcha yozsa o'zbekcha).\n"
        "2. Agar o'zbek tilida javob bersang, sof, tabiiy o'zbekcha so'zlashuv tilida, xuddi mahalliy insonlardek (aksentlarsiz va kitobiy bo'lmagan uslubda) javob qaytar.\n"
        "3. Javoblaring qisqa, aniq va xaridorga qulay bo'lsin.\n\n"
        f"Kompaniya/Sotuvchi haqida: {persona_text}"
    )
    
    try:
        resp = await groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3, max_tokens=1024
        )
        return resp.choices[0].message.content
    except Exception as e1:
        try:
            resp = await groq_backup.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3, max_tokens=1024
            )
            return resp.choices[0].message.content
        except Exception as e2:
            try:
                model = genai.GenerativeModel("gemini-1.5-flash")
                resp = await model.generate_content_async(sys_prompt + "\n\nSavol: " + prompt)
                return resp.text
            except Exception as e3:
                return "Kechirasiz, hozir javob bera olmayman (Texnik xatolik)."

async def on_outgoing_message(event):
    owner_id = getattr(event.client, 'owner_id', None)
    if owner_id:
        owner_last_active[(owner_id, event.chat_id)] = time.time()

message_queue = asyncio.Queue()

async def userbot_queue_worker():
    dlog("Navbat tizimi ishga tushdi (Navbatma-navbat ishlash yuboruvchisi).")
    while True:
        try:
            # Kutamiz, navbatdagi xabar kelguncha
            event, owner_id, sender_id, persona, is_audio, prompt = await message_queue.get()
            
            # Anti-spam: Har bir xabarga o'tishdan oldin qo'shimcha pauza
            await asyncio.sleep(1.5)
            
            # O'qilgan qilish (ko'k ptichka)
            try:
                await event.client.send_read_acknowledge(event.chat_id)
            except Exception as e:
                pass
                
            action = 'record-audio' if is_audio else 'typing'
            async with event.client.action(sender_id, action):
                
                # Insoniylik effekti, yozishdan oldin biroz o'ylaydi
                await asyncio.sleep(2.0)
                
                # AI dan javob olish
                reply_text = await get_ai_reply(prompt, persona)
                
                # Yozish simulyatsiyasi (matn uzunligiga qarab)
                kutish_vaqti = min(len(reply_text) / 20, 5)
                await asyncio.sleep(kutish_vaqti)
                
                if is_audio:
                    tmp_out = f"temp_audio/out_{sender_id}_{int(time.time())}.ogg"
                    success = await generate_speech(reply_text, tmp_out)
                    if success:
                        await event.client.send_file(sender_id, tmp_out, voice_note=True)
                        try: os.remove(tmp_out)
                        except: pass
                    else:
                        await event.reply(reply_text)
                else:
                    await event.reply(reply_text)
                    
            # API ishlaganini sanash
            await update_user_api(owner_id, 1)
            
            # Bitta profil bo'yicha javob berilgandan keyin umumiy tizim 2 soniya dam oladi 
            # (parallel emas, faqat navbat bilan ishlashi uchun)
            await asyncio.sleep(2)
            
        except Exception as e:
            dlog(f"Queue worker error: {e}")
        finally:
            message_queue.task_done()

async def on_new_userbot_message(event):
    if not event.is_private: return
    owner_id = getattr(event.client, 'owner_id', None)
    if not owner_id: return

    sender = await event.get_sender()
    if not sender or sender.bot or sender.is_self: return
    
    sender_id = sender.id
    
    # 2 daqiqa pauza tekshiruvi (Sotuvchi o'zi gaplashayotgan bo'lsa xalaqit bermaslik)
    last_act = owner_last_active.get((owner_id, sender_id), 0)
    if time.time() - last_act < MAX_SILENCE:
        return
        
    user_data = await get_user(owner_id)
    if not user_data or user_data.get("ai_enabled", 1) == 0:
        return
        
    has_access, tariff_name, _, _ = await check_user_access(owner_id)
    if not has_access:
        return
        
    persona = user_data.get('business_persona', 'Biz mijozlarga xizmat ko\'rsatamiz.')
    
    # Audio tekshiruvi
    is_audio = False
    if event.message.voice or (getattr(event.message.media, "document", None) and event.message.media.document.mime_type.startswith("audio")):
        is_audio = True
        
    prompt = ""
    if is_audio:
        if tariff_name != "smm":
            return
            
        async with event.client.action(sender_id, 'record-audio'):
            tmp_dir = "temp_audio"
            os.makedirs(tmp_dir, exist_ok=True)
            audio_path = await event.message.download_media(file=tmp_dir)
            if not audio_path: return
            
            prompt = await transcribe_audio_groq(audio_path)
            try: os.remove(audio_path)
            except: pass
            
            if not prompt:
                await event.reply("Kechirasiz, ovozingizni tushuna olmadim. Yozib yuboring.")
                return
    else:
        prompt = event.message.text
        
    if not prompt: return
    
    # To'g'ridan-to'g'ri javob bermasdan xabarni NAVBATGA qo'shamiz
    await message_queue.put((event, owner_id, sender_id, persona, is_audio, prompt))

async def on_incoming_call(event):
    if not isinstance(event, UpdatePhoneCall):
        return
    owner_id = getattr(event.client, 'owner_id', None)
    if not owner_id: return
    
    try:
        caller_id = getattr(event.phone_call, 'participant_id', getattr(event.phone_call, 'admin_id', None))
        if caller_id and caller_id != owner_id:
            await event.client.send_message(caller_id, "Hozircha qo'ng'iroqlarga javob bera olmayman рџ“µ\nIltimos, yozma ravishda yoki ovozli xabar qoldiring.")
            
            await event.client(DiscardCallRequest(
                peer=event.phone_call,
                duration=0,
                reason=PhoneCallDiscardReasonBusy(),
                connection_id=0
            ))
    except Exception as e:
        dlog(f"Call handling error: {e}")

async def start_userbot_from_session(user_id, session_string):
    client = TelegramClient(StringSession(session_string), API_ID, API_HASH,
                            device_model="Desktop", system_version="Windows 11",
                            app_version="4.16.8", lang_code="en", system_lang_code="en-US")
    try:
        await client.connect()
        if await client.is_user_authorized():
            client.owner_id = user_id
            client.add_event_handler(on_new_userbot_message, events.NewMessage(incoming=True))
            client.add_event_handler(on_outgoing_message, events.NewMessage(outgoing=True))
            client.add_event_handler(on_incoming_call, events.Raw())
            active_userbots[user_id] = client
            dlog(f"[{user_id}] Bot faol!")
        else:
            await client.disconnect()
    except Exception as e:
        dlog(f"[{user_id}] Start userbot error: {e}")

# Global worker ishga tushirilganini tekshirish uchun bayroq
worker_started = False

async def load_active_userbots(users_cursor):
    global worker_started
    if not worker_started:
        asyncio.create_task(userbot_queue_worker())
        worker_started = True

    dlog("Faol userbotlar yuklanmoqda...")
    users = await users_cursor.to_list(length=1000)
    for u in users:
        user_id = u.get("user_id")
        session_str = u.get("telethon_session")
        if not user_id or not session_str: continue
        
        has_access, _, _, _ = await check_user_access(user_id)
        if has_access and u.get("ai_enabled", 1) == 1:
            asyncio.create_task(start_userbot_from_session(user_id, session_str))

