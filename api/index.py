import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from aiogram import types
from main import bot, dp, init_db
import asyncio

app = FastAPI(title="Telegram AI Agent Webhook")

@app.on_event("startup")
async def on_startup():
    try:
        await init_db()
    except Exception as e:
        print(f"[DB Startup Error] {e}")

@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Telegram AI Bot (Vercel Webhook Active)",
        "docs": "To set webhook visit: /set-webhook?url=https://YOUR_VERCEL_DOMAIN/webhook"
    }

@app.get("/set-webhook")
async def setup_webhook(url: str = None):
    if not url:
        return {"error": "Iltimos Vercel havolangizni kiriting: /set-webhook?url=https://your-project.vercel.app/webhook"}
    try:
        await bot.set_webhook(url, drop_pending_updates=True)
        return {"status": "success", "message": f"Webhook muvaffaqiyatli ulandi: {url}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/")
@app.post("/webhook")
@app.post("/api")
@app.post("/api/webhook")
@app.post("/api/index")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        print(f"[Webhook Error] {e}")
        return {"ok": False, "error": str(e)}

handler = app
app_instance = app
application = app
