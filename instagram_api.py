import os
import aiohttp
import asyncio
from aiohttp import web
import httpx
from config import META_APP_ID, META_APP_SECRET, WEBHOOK_VERIFY_TOKEN, WEBHOOK_URL, ADMIN_ID, GROQ_API_KEY
from database import users_col, get_user
import json

routes = web.RouteTableDef()
bot = None

async def generate_groq_response(prompt: str, system_prompt: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"]
    return "Xatolik yuz berdi."

@routes.get('/webhook')
async def verify_webhook(request):
    mode = request.query.get('hub.mode')
    token = request.query.get('hub.verify_token')
    challenge = request.query.get('hub.challenge')
    if mode == 'subscribe' and token == WEBHOOK_VERIFY_TOKEN:
        return web.Response(text=challenge)
    return web.Response(status=403, text="Forbidden")

@routes.post('/webhook')
async def handle_webhook(request):
    try:
        data = await request.json()
        print(f"[Instagram Webhook] {json.dumps(data)}")
        
        if data.get("object") == "instagram":
            for entry in data.get("entry", []):
                
                # Check DM
                if "messaging" in entry:
                    for messaging_event in entry["messaging"]:
                        if "message" in messaging_event and not messaging_event["message"].get("is_echo"):
                            sender_id = messaging_event["sender"]["id"]
                            recipient_id = messaging_event["recipient"]["id"] 
                            message_text = messaging_event["message"].get("text", "")
                            
                            if message_text:
                                user = await users_col.find_one({"instagram_account_id": recipient_id})
                                if user and user.get("ai_enabled", 1) == 1:
                                    telegram_user_id = user["user_id"]
                                    user_data = await get_user(telegram_user_id)
                                    persona = user_data.get('business_persona', '')
                                    system_prompt = f"Sen kompaniyaning menejerisan. Kompaniya haqida: {persona}\nQoidalar: Qisqa va samimiy javob ber."
                                    reply_text = await generate_groq_response(message_text, system_prompt)
                                    await send_instagram_message(user.get("instagram_token"), sender_id, reply_text)
                
                # Check Comments
                if "changes" in entry:
                    for change in entry["changes"]:
                        if change.get("field") == "comments":
                            comment_data = change["value"]
                            if comment_data.get("from", {}).get("id") != entry.get("id"):
                                comment_id = comment_data.get("id")
                                comment_text = comment_data.get("text", "")
                                recipient_id = entry.get("id")
                                
                                user = await users_col.find_one({"instagram_account_id": recipient_id})
                                if user and user.get("ai_enabled", 1) == 1:
                                    telegram_user_id = user["user_id"]
                                    user_data = await get_user(telegram_user_id)
                                    persona = user_data.get('business_persona', '')
                                    
                                    system_prompt = f"Sen kompaniyaning menejerisan. Kompaniya haqida: {persona}\nQoidalar: Instagramdagi izohga (comment) juda qisqa, samimiy javob yoz. Mijozni 'Siz' deb hurmat bilan chaqir."
                                    reply_text = await generate_groq_response(comment_text, system_prompt)
                                    await reply_to_instagram_comment(user.get("instagram_token"), comment_id, reply_text)
                                    
                                    dm_prompt = f"Sen menejersan. Kompaniya: {persona}\nQoida: Izoh qoldirgan mijozning shaxsiy lichkasiga o'tib, unga ma'lumot va narxlarni taklif qil."
                                    dm_text = await generate_groq_response(comment_text, dm_prompt)
                                    sender_id = comment_data.get("from", {}).get("id")
                                    await send_instagram_message(user.get("instagram_token"), sender_id, dm_text)
                                    
        return web.Response(status=200, text="OK")
    except Exception as e:
        print(f"[Webhook Error] {e}")
        return web.Response(status=500, text="Error")

async def send_instagram_message(access_token, recipient_id, message_text):
    if not access_token: return
    url = f"https://graph.facebook.com/v19.0/me/messages"
    params = {"access_token": access_token}
    payload = {"recipient": {"id": recipient_id}, "message": {"text": message_text}}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, json=payload) as resp:
            print(f"[IG Send MSG] {resp.status}")

async def reply_to_instagram_comment(access_token, comment_id, message_text):
    if not access_token: return
    url = f"https://graph.facebook.com/v19.0/{comment_id}/replies"
    params = {"access_token": access_token}
    payload = {"message": message_text}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, json=payload) as resp:
            print(f"[IG Reply Comment] {resp.status}")

@routes.get('/oauth')
async def facebook_oauth_callback(request):
    code = request.query.get('code')
    state = request.query.get('state') 
    
    if not code or not state:
        return web.Response(text="Xatolik: Ulanish kodi yoki ID topilmadi.")
        
    try:
        user_id = int(state)
        url = f"https://graph.facebook.com/v19.0/oauth/access_token"
        params = {
            "client_id": META_APP_ID,
            "redirect_uri": f"{WEBHOOK_URL}/oauth",
            "client_secret": META_APP_SECRET,
            "code": code
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if "access_token" in data:
                    user_token = data["access_token"]
                    
                    long_url = f"https://graph.facebook.com/v19.0/oauth/access_token"
                    long_params = {
                        "grant_type": "fb_exchange_token",
                        "client_id": META_APP_ID,
                        "client_secret": META_APP_SECRET,
                        "fb_exchange_token": user_token
                    }
                    async with session.get(long_url, params=long_params) as lresp:
                        ldata = await lresp.json()
                        if "access_token" in ldata:
                            user_token = ldata["access_token"]
                            
                    me_url = f"https://graph.facebook.com/v19.0/me/accounts"
                    async with session.get(me_url, params={"access_token": user_token}) as meresp:
                        me_data = await meresp.json()
                        ig_account_id, page_token = None, None
                        
                        if "data" in me_data:
                            for page in me_data["data"]:
                                page_id = page["id"]
                                pt = page["access_token"]
                                ig_url = f"https://graph.facebook.com/v19.0/{page_id}?fields=instagram_business_account"
                                async with session.get(ig_url, params={"access_token": pt}) as igresp:
                                    ig_data = await igresp.json()
                                    if "instagram_business_account" in ig_data:
                                        ig_account_id = ig_data["instagram_business_account"]["id"]
                                        page_token = pt
                                        break
                                        
                        if ig_account_id and page_token:
                            existing_ig = await users_col.find_one({"instagram_account_id": ig_account_id, "user_id": {"$ne": user_id}})
                            if existing_ig:
                                return web.Response(text="❌ XATOLIK: Ushbu Instagram profil allaqachon boshqa Telegram akkauntga ulangan! Bepul sinov muddatini qayta ishlatish taqiqlanadi.", content_type="text/html")
                            
                            await users_col.update_one(
                                {"user_id": user_id},
                                {"$set": {"instagram_token": page_token, "instagram_account_id": ig_account_id, "ai_enabled": 1}}
                            )
                            if bot:
                                await bot.send_message(user_id, "✅ <b>Instagram akkauntingiz ulandi!</b>\nEndi AI Instagram Direct va Kommentariyalarga javob beradi!")
                            return web.Response(text="Muvaffaqiyatli ulandi! Telegram botga qaytishingiz mumkin.", content_type="text/html")
                        else:
                            return web.Response(text="Xatolik: Facebook sahifangizga ulangan Instagram Professional akkaunt topilmadi.")
        return web.Response(text="Xatolik yuz berdi.")
    except Exception as e:
        return web.Response(text=f"Tizim xatosi: {e}")

async def start_web_server(b):
    global bot
    bot = b
    app = web.Application()
    app.add_routes(routes)
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Web server started on port {port}")
