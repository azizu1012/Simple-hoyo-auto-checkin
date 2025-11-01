# bot.py
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

class HoyolabBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        from database import setup_db
        await setup_db()
        await self.load_extension("cogs.auto_tasks")  # ✅ Load auto_tasks để auto check-in và redeem
        await self.tree.sync()

    async def on_ready(self):
        print(f"[Bot] Đã đăng nhập: {self.user}")

bot = HoyolabBot()

# Lệnh /register để gửi link web login
@bot.tree.command(name="register", description="Bắt đầu đăng nhập qua web để bật auto check-in")
async def register(interaction: discord.Interaction):
    web_url = os.getenv("WEB_URL", "https://your-bot.onrender.com")
    link = f"{web_url}/hoyolab/login?user_id={interaction.user.id}"
    await interaction.response.send_message(
        f"🔗 Vui lòng truy cập để đăng nhập: [Đăng nhập HoYoLab]({link})",
        ephemeral=True
    )

# Lệnh /deregister để xóa dữ liệu (tùy chọn, giữ từ mã cũ của bạn)
@bot.tree.command(name="deregister", description="Tắt auto check-in")
async def deregister(interaction: discord.Interaction):
    from database import delete_user_data
    if await delete_user_data(interaction.user.id):
        await interaction.response.send_message("✅ Đã tắt auto check-in.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Bạn chưa đăng ký.", ephemeral=True)