import os
import asyncio
from aiohttp import web
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import WEBHOOK_URL, API_ID, API_HASH
from database import users_col, get_user

routes = web.RouteTableDef()
bot = None

pending_logins = {}

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Profilni Ulash</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background-color: var(--tg-theme-bg-color, #ffffff); color: var(--tg-theme-text-color, #000000); padding: 20px; text-align: center; }
        input { width: 90%; padding: 12px; margin: 10px 0; border: 1px solid var(--tg-theme-hint-color, #ccc); border-radius: 8px; font-size: 16px; background-color: var(--tg-theme-bg-color, #fff); color: var(--tg-theme-text-color, #000); }
        button { width: 95%; padding: 14px; background-color: var(--tg-theme-button-color, #3390ec); color: var(--tg-theme-button-text-color, #fff); border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 15px; }
        .hidden { display: none; }
        #status { margin-top: 15px; font-size: 14px; color: #ff3b30; }
    </style>
</head>
<body>
    <h2>Telegramni Ulash</h2>
    <p>Raqamingizni kiritib ulanish tugmasini bosing.</p>
    
    <div id="step1">
        <input type="tel" id="phone" placeholder="+998901234567" />
        <button onclick="sendCode()" id="btnSend">Kodni olish</button>
    </div>
    
    <div id="step2" class="hidden">
        <p>Telegramdan kelgan 5 xonali kodni kiriting:</p>
        <input type="number" id="code" placeholder="12345" />
        <button onclick="submitCode()" id="btnSubmit">Ulanish</button>
    </div>
    
    <div id="status"></div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        
        let userId = tg.initDataUnsafe?.user?.id;
        
        if (!userId) {
            const urlParams = new URLSearchParams(window.location.search);
            userId = urlParams.get('user_id');
        }

        async function sendCode() {
            const phone = document.getElementById('phone').value;
            if(!phone) return alert('Raqamni kiriting');
            if(!userId) return alert('Telegram orqali kiring');
            
            document.getElementById('btnSend').innerText = 'Kutilmoqda...';
            document.getElementById('btnSend').disabled = true;
            
            try {
                const res = await fetch('/api/send_code', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({phone: phone, user_id: userId})
                });
                const data = await res.json();
                if(data.success) {
                    document.getElementById('step1').classList.add('hidden');
                    document.getElementById('step2').classList.remove('hidden');
                    document.getElementById('status').innerText = '';
                } else {
                    document.getElementById('status').innerText = data.error || 'Xatolik yuz berdi';
                    document.getElementById('btnSend').innerText = 'Kodni olish';
                    document.getElementById('btnSend').disabled = false;
                }
            } catch (e) {
                document.getElementById('status').innerText = 'Tarmoq xatosi';
                document.getElementById('btnSend').innerText = 'Kodni olish';
                document.getElementById('btnSend').disabled = false;
            }
        }

        async function submitCode() {
            const code = document.getElementById('code').value;
            if(!code) return alert('Kodni kiriting');
            
            document.getElementById('btnSubmit').innerText = 'Ulanmoqda...';
            document.getElementById('btnSubmit').disabled = true;
            
            try {
                const res = await fetch('/api/submit_code', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({code: code, user_id: userId})
                });
                const data = await res.json();
                if(data.success) {
                    document.getElementById('step2').innerHTML = '<h3>✅ Muvaffaqiyatli ulandi!</h3><p>Ushbu oynani yopishingiz mumkin.</p>';
                    setTimeout(() => tg.close(), 3000);
                } else {
                    document.getElementById('status').innerText = data.error || 'Kod xato';
                    document.getElementById('btnSubmit').innerText = 'Ulanish';
                    document.getElementById('btnSubmit').disabled = false;
                }
            } catch (e) {
                document.getElementById('status').innerText = 'Tarmoq xatosi';
                document.getElementById('btnSubmit').innerText = 'Ulanish';
                document.getElementById('btnSubmit').disabled = false;
            }
        }
    </script>
</body>
</html>
"""

@routes.get('/')
async def webapp_page(request):
    return web.Response(text=HTML_PAGE, content_type='text/html')

@routes.post('/api/send_code')
async def api_send_code(request):
    data = await request.json()
    phone = data.get('phone')
    user_id = data.get('user_id')
    
    if not phone or not user_id:
        return web.json_response({"success": False, "error": "Ma'lumot to'liq emas"})
        
    user_id = int(user_id)
    if user_id in pending_logins:
        try:
            await pending_logins[user_id]['client'].disconnect()
        except: pass
            
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
        pending_logins[user_id] = {"client": client, "phone": phone, "hash": sent.phone_code_hash}
        return web.json_response({"success": True})
    except Exception as e:
        await client.disconnect()
        return web.json_response({"success": False, "error": str(e)})

@routes.post('/api/submit_code')
async def api_submit_code(request):
    data = await request.json()
    code = data.get('code')
    user_id = data.get('user_id')
    
    if not code or not user_id:
        return web.json_response({"success": False, "error": "Kod kiritilmadi"})
        
    user_id = int(user_id)
    if user_id not in pending_logins:
        return web.json_response({"success": False, "error": "Sessiya topilmadi. Qaytadan urinib ko'ring."})
        
    login_data = pending_logins[user_id]
    client = login_data['client']
    try:
        await client.sign_in(phone=login_data['phone'], code=code, phone_code_hash=login_data['hash'])
        session_string = client.session.save()
        await client.disconnect()
        del pending_logins[user_id]
        
        await users_col.update_one({"user_id": user_id}, {"$set": {"telethon_session": session_string, "ai_enabled": 1}})
        
        if bot:
            from userbot_manager import start_userbot_from_session
            asyncio.create_task(start_userbot_from_session(user_id, session_string))
            await bot.send_message(user_id, "✅ **Telegram profilingiz muvaffaqiyatli ulandi!**\nAI endi lichkangizdagi xabarlarga javob beradi.", parse_mode="Markdown")
            
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)})

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
