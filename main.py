# main.py
import threading
import asyncio
from bot import bot
from web import app
import os
from dotenv import load_dotenv

load_dotenv()

# --- Chạy Flask trong thread riêng ---
def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

# --- Chạy Discord bot trong event loop chính ---
async def run_bot():
    await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    # Bắt đầu Flask trong background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Chạy bot Discord trong main thread (async)
    asyncio.run(run_bot())