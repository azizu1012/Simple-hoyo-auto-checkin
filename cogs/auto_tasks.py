# cogs/auto_tasks.py
from discord.ext import commands, tasks
import aiosqlite
import genshin
import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Xử lý timezone

class AutoTasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.redeemed_codes_cache = {}  # {user_id: set(codes)} để tránh redeem lại
        self.daily_checkin.start()
        self.auto_redeem_codes.start()

    def cog_unload(self):
        self.daily_checkin.cancel()
        self.auto_redeem_codes.cancel()

    @tasks.loop(hours=24)
    async def daily_checkin(self):
        async with aiosqlite.connect("hoyolab_auto_data.db") as db:
            async with db.execute("SELECT user_id, ltuid, ltoken, cookie_token, game_uid, game_biz FROM users") as cursor:
                async for row in cursor:
                    user_id, ltuid, ltoken, cookie_token, game_uid, game_biz = row
                    try:
                        client = genshin.Client(cookies={
                            "ltuid_v2": ltuid,
                            "ltoken_v2": ltoken,
                            "cookie_token_v2": cookie_token
                        })
                        game = genshin.Game.GENSHIN if "genshin" in game_biz else genshin.Game.STARRAIL
                        reward = await client.claim_daily_reward(game=game, lang="vi-vn")  # Lang tiếng Việt nếu cần
                        user = self.bot.get_user(int(user_id))
                        if user:
                            await user.send(f"✅ Đã check-in HoYoLab thành công cho UID {game_uid} ({game.name}): {reward.amount}x {reward.name}")
                    except genshin.AlreadyClaimed:
                        if user:
                            await user.send(f"ℹ️ Đã check-in hôm nay cho UID {game_uid}.")
                    except genshin.InvalidCookies:
                        if user:
                            await user.send("⚠️ Cookies hết hạn. Vui lòng /register lại.")
                    except Exception as e:
                        print(f"Lỗi check-in cho user {user_id}: {e}")
                        if user:
                            await user.send(f"❌ Lỗi check-in cho UID {game_uid}: {e}")

    @daily_checkin.before_loop
    async def before_daily_checkin(self):
        await self.bot.wait_until_ready()
        tz = ZoneInfo("Asia/Bangkok")  # UTC+7
        now = datetime.now(tz)
        next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        delay = (next_run - now).total_seconds()
        print(f"Chờ {delay} giây đến 3:00 AM UTC+7 cho check-in.")
        await asyncio.sleep(delay)

    @tasks.loop(hours=6)  # Chạy mỗi 6 giờ để check codes mới
    async def auto_redeem_codes(self):
        # Fetch codes động từ nguồn (Pocket Tactics cho Genshin và Star Rail)
        genshin_codes = await self.fetch_codes("genshin")
        starrail_codes = await self.fetch_codes("starrail")

        async with aiosqlite.connect("hoyolab_auto_data.db") as db:
            async with db.execute("SELECT user_id, ltuid, ltoken, cookie_token, game_uid, game_biz FROM users") as cursor:
                async for row in cursor:
                    user_id, ltuid, ltoken, cookie_token, game_uid, game_biz = row
                    codes = genshin_codes if "genshin" in game_biz else starrail_codes
                    if user_id not in self.redeemed_codes_cache:
                        self.redeemed_codes_cache[user_id] = set()

                    try:
                        client = genshin.Client(cookies={
                            "ltuid_v2": ltuid,
                            "ltoken_v2": ltoken,
                            "cookie_token_v2": cookie_token
                        })
                        game = genshin.Game.GENSHIN if "genshin" in game_biz else genshin.Game.STARRAIL
                        user = self.bot.get_user(int(user_id))
                        for code in codes:
                            if code in self.redeemed_codes_cache[user_id]:
                                continue
                            try:
                                reward = await client.redeem_code(code, uid=int(game_uid), game=game)
                                if user:
                                    await user.send(f"🎁 Redeem code thành công cho UID {game_uid} ({game.name}): {code} - {reward}")
                                self.redeemed_codes_cache[user_id].add(code)
                            except (genshin.RedemptionClaimed, genshin.RedemptionInvalid):
                                self.redeemed_codes_cache[user_id].add(code)
                            except Exception as e:
                                print(f"Lỗi redeem {code} cho user {user_id}: {e}")
                    except genshin.InvalidCookies:
                        if user:
                            await user.send("⚠️ Cookies hết hạn. Vui lòng /register lại.")
                    except Exception as e:
                        print(f"Lỗi xử lý user {user_id}: {e}")

    async def fetch_codes(self, game_type: str):
        url = "https://www.pockettactics.com/genshin-impact/codes" if game_type == "genshin" else "https://www.pockettactics.com/honkai-star-rail/codes"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            codes = []
            # Logic parse (dựa trên cấu trúc trang, có thể cần điều chỉnh nếu trang thay đổi)
            for elem in soup.find_all("li", string=lambda t: t and len(t.strip()) > 5 and t.strip().isupper()):  # Giả định codes là uppercase
                code = elem.text.strip()
                if code:
                    codes.append(code)
            return codes  # Trả về list codes active từ trang

async def setup(bot):
    await bot.add_cog(AutoTasks(bot))