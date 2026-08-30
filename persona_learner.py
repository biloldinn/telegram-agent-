import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import asyncio
from telethon import TelegramClient
from groq import AsyncGroq
from config import GROQ_API_KEY, OWNER_NAME
from database import save_owner_persona, get_owner_persona

groq_client = AsyncGroq(api_key=GROQ_API_KEY)

async def learn_owner_style(client: TelegramClient, me_id: int):
    existing_persona = await get_owner_persona()
    if existing_persona:
        print("[AI Tahlil] Profil egasining xarakteri bazada mavjud.")
        return existing_persona

    print("[AI Tahlil] Profilingizdagi eski yozishmalaringiz va xarakteringiz o'rganilmoqda...")
    sample_messages = []
    
    try:
        dialogs = await client.get_dialogs(limit=30)
        for d in dialogs:
            if d.is_user and not d.entity.bot:
                async for msg in client.iter_messages(d.entity, limit=15):
                    if msg.out and msg.text and len(msg.text.strip()) > 3:
                        sample_messages.append(msg.text.strip())
                        if len(sample_messages) >= 80:
                            break
            if len(sample_messages) >= 80:
                break
    except Exception as e:
        print(f"[AI Tahlil] Xabarlarni o'qishda ogohlantirish: {e}")

    if not sample_messages:
        default_persona = f"Siz {OWNER_NAME}siz. Samimiy, o'zbekcha so'zlashuv tilida, xushmuomala, aniq va sotuvchi ohangda javob berasiz."
        await save_owner_persona(default_persona)
        return default_persona

    corpus = "\n---\n".join(sample_messages[:60])
    
    prompt = f"""Quyida Telegram akkaunt egasi ({OWNER_NAME}) tomonidan yozilgan haqiqiy xabarlar keltirilgan:
{corpus}

Vazifangiz:
Ushbu shaxsning yozish uslubini, nutq ohangini (Tone of Voice), salomlashish va xayrlashish qoidalarini, qaysi so'z va emojilarni ishlatishini tahlil qiling.
Natijada boshqa AI aynan shu shaxs kabi gapirishi uchun qisqa va mukammal 'System Persona' ko'rsatmasini tuzib bering.
Ko'rsatma o'zbek tilida bo'lsin."""

    try:
        completion = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=400
        )
        persona_result = completion.choices[0].message.content
        await save_owner_persona(persona_result)
        print("[AI Tahlil] Profil egasining shaxsiyati to'liq o'rganildi va MongoDB bazaga saqlandi!")
        return persona_result
    except Exception as e:
        print(f"[AI Tahlil] Xarakterni tahlil qilishda xatolik: {e}")
        return f"Siz {OWNER_NAME}siz. Samimiy va professional tarzda gapiring."
