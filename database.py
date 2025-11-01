# database.py
import aiosqlite

DB_NAME = "hoyolab_auto_data.db"

async def setup_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                ltuid TEXT NOT NULL,
                ltoken TEXT NOT NULL,
                cookie_token TEXT NOT NULL,
                game_uid TEXT,
                game_biz TEXT
            )
        """)
        await db.commit()

async def save_user_data(user_id, ltuid, ltoken, cookie_token, game_uid, game_biz):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, ltuid, ltoken, cookie_token, game_uid, game_biz)
        )
        await db.commit()

async def delete_user_data(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()
        return db.changes > 0  # Trả về True nếu xóa thành công