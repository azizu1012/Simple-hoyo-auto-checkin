# cogs/register.py
import discord
from discord.ext import commands
from discord import app_commands
import genshin
import hashlib
import uuid
import httpx
import json
from database import save_user_data

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36..."

class LoginError(Exception): pass
class VerificationRequired(LoginError): pass

async def get_login_ticket_and_cookies(username, password):
    hashed_password = hashlib.md5(password.encode()).hexdigest()
    device_id = str(uuid.uuid4()).upper()
    async with httpx.AsyncClient() as client:
        res = await client.post("https://webapi-os.account.mihoyo.com/Api/login_by_password", data={
            "account": username,
            "password": hashed_password,
            "device_id": device_id,
            "platform": 3,
            "scene": "login"
        }, headers={"User-Agent": USER_AGENT})
        data = res.json()
        if data["retcode"] == 0:
            ltuid = client.cookies.get("ltuid_v2") or client.cookies.get("ltuid")
            ltoken = client.cookies.get("ltoken_v2") or client.cookies.get("ltoken")
            return data["data"]["login_ticket"], {"ltuid": ltuid, "ltoken": ltoken}
        elif data["retcode"] == -202:
            raise VerificationRequired()
        else:
            raise LoginError(data.get("message", "Lỗi không xác định"))

async def verify_code_and_get_cookies(ticket, code):
    async with httpx.AsyncClient() as client:
        res = await client.post("https://webapi-os.account.mihoyo.com/Api/verify_login_ticket", data={
            "login_ticket": ticket,
            "auth_code": code,
            "uid": 1
        }, headers={"User-Agent": USER_AGENT})
        data = res.json()
        if data["retcode"] == 0:
            ltuid = client.cookies.get("ltuid_v2") or client.cookies.get("ltuid")
            ltoken = client.cookies.get("ltoken_v2") or client.cookies.get("ltoken")
            return {"ltuid": ltuid, "ltoken": ltoken}
        else:
            raise LoginError("Mã không hợp lệ")

class UIDSelectView(discord.ui.View):
    def __init__(self, user_id: int, client: genshin.Client, accounts: list):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.client = client
        self.accounts = accounts
        select_options = []
        for acc in accounts:
            if acc.game in [genshin.Game.GENSHIN, genshin.Game.STAR_RAIL]:
                label = f"[{acc.game.name} - {acc.server_name}] UID: {acc.uid}"
                select_options.append(discord.SelectOption(label=label, value=f"{acc.uid}:{acc.game.server}"))
        self.add_item(discord.ui.Select(
            placeholder="Chọn UID để auto check-in...",
            options=select_options,
            min_values=1,
            max_values=1
        ))

    @discord.ui.select()
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        uid, game_biz = select.values[0].split(':')
        ltuid = self.client.cookies.get("ltuid")
        ltoken = self.client.cookies.get("ltoken")
        await save_user_data(interaction.user.id, ltuid, ltoken, uid, game_biz)
        await interaction.edit_original_response(
            content=f"🎉 **Đã bật auto check-in cho UID {uid} ({game_biz})!**",
            view=None
        )

class VerificationCodeModal(discord.ui.Modal, title="Nhập mã 2FA"):
    def __init__(self, ticket: str):
        super().__init__()
        self.ticket = ticket
    code = discord.ui.TextInput(label="Mã 6 số", max_length=6)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            cookies = await verify_code_and_get_cookies(self.ticket, self.code.value)
            client = genshin.Client(cookies=cookies)
            accounts = await client.get_game_accounts()
            view = UIDSelectView(interaction.user.id, client, accounts)
            await interaction.followup.send("Chọn UID để bật auto check-in:", view=view, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}", ephemeral=True)

class RegisterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="register", description="Đăng nhập HoYoLab để bật auto check-in")
    @app_commands.describe(email="Email hoặc tên đăng nhập", password="Mật khẩu")
    async def register(self, interaction: discord.Interaction, email: str, password: str):
        await interaction.response.defer(ephemeral=True)
        try:
            ticket, cookies = await get_login_ticket_and_cookies(email, password)
            client = genshin.Client(cookies=cookies)
            accounts = await client.get_game_accounts()
            view = UIDSelectView(interaction.user.id, client, accounts)
            await interaction.followup.send("Chọn UID để bật auto check-in:", view=view, ephemeral=True)
        except VerificationRequired:
            await interaction.followup.send_modal(VerificationCodeModal(ticket))
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {e}", ephemeral=True)

    @app_commands.command(name="deregister", description="Tắt auto check-in")
    async def deregister(self, interaction: discord.Interaction):
        from ..database import delete_user_data
        if await delete_user_data(interaction.user.id):
            await interaction.response.send_message("✅ Đã tắt auto check-in.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Bạn chưa đăng ký.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(RegisterCog(bot))