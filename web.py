# web.py
from flask import Flask, request, render_template_string
import asyncio
import aiosqlite
import genshin
import os

app = Flask(__name__)
DB_PATH = "hoyolab_auto_data.db"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/hoyolab/login')
def hoyolab_login():
    user_id = request.args.get('user_id')
    if not user_id:
        return "Thiếu user_id", 400

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>HoYoLab Auto Login</title></head>
    <body style="font-family: Arial; max-width: 800px; margin: 40px auto;">
        <h2>🔐 Đăng nhập HoYoLab để bật Auto Check-in</h2>
        <ol>
            <li>Mở tab mới → <a href="https://www.hoyolab.com" target="_blank">HoYoLab</a></li>
            <li>Đăng nhập (có thể cần 2FA)</li>
            <li>Nhấn F12 → Application → Cookies → <b>https://www.hoyolab.com</b></li>
            <li>Copy 3 giá trị từ dòng có <b>Domain = .hoyoverse.com</b>:</li>
            <ul>
                <li><b>ltuid_v2</b> (số)</li>
                <li><b>ltoken_v2</b> (chuỗi dài)</li>
                <li><b>cookie_token_v2</b> (chuỗi dài)</li>
            </ul>
        </ol>
        <form method="POST">
            <input type="hidden" name="user_id" value="{{ user_id }}">
            <p><label>ltuid_v2: <input name="ltuid" required></label></p>
            <p><label>ltoken_v2: <input name="ltoken" style="width:100%" required></label></p>
            <p><label>cookie_token_v2: <input name="cookie_token" style="width:100%" required></label></p>
            <button type="submit">✅ Gửi và Chọn Tài khoản</button>
        </form>
    </body>
    </html>
    """, user_id=user_id)

@app.route('/hoyolab/login', methods=['POST'])
async def handle_login():
    user_id = request.form['user_id']
    ltuid = request.form['ltuid']
    ltoken = request.form['ltoken']
    cookie_token = request.form['cookie_token']

    # Validate cookies
    try:
        client = genshin.Client(cookies={
            "ltuid_v2": ltuid,
            "ltoken_v2": ltoken,
            "cookie_token_v2": cookie_token
        })
        accounts = await client.get_game_accounts()
        if not accounts:
            return "Không tìm thấy tài khoản game.", 400

        # Hiển thị form chọn account
        account_options = ""
        for account in accounts:
            account_options += f'<option value="{account.uid}|{account.game_biz}">{account.nickname} ({account.game_biz})</option>'

        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head><title>Chọn tài khoản game</title></head>
        <body style="font-family: Arial; max-width: 800px; margin: 40px auto;">
            <h2>🎮 Chọn tài khoản game để auto check-in</h2>
            <form method="POST" action="/hoyolab/select_account">
                <input type="hidden" name="user_id" value="{{ user_id }}">
                <input type="hidden" name="ltuid" value="{{ ltuid }}">
                <input type="hidden" name="ltoken" value="{{ ltoken }}">
                <input type="hidden" name="cookie_token" value="{{ cookie_token }}">
                <p><label>Chọn tài khoản: 
                    <select name="account" required>
                        {{ account_options | safe }}
                    </select>
                </label></p>
                <button type="submit">✅ Xác nhận</button>
            </form>
        </body>
        </html>
        """, user_id=user_id, ltuid=ltuid, ltoken=ltoken, cookie_token=cookie_token, account_options=account_options)

    except Exception as e:
        return f"Lỗi xác thực: {e}", 400

@app.route('/hoyolab/select_account', methods=['POST'])
async def select_account():
    user_id = request.form['user_id']
    ltuid = request.form['ltuid']
    ltoken = request.form['ltoken']
    cookie_token = request.form['cookie_token']
    account = request.form['account']
    game_uid, game_biz = account.split('|')

    # Lưu vào DB (sử dụng hàm từ database.py)
    from database import save_user_data
    await save_user_data(user_id, ltuid, ltoken, cookie_token, game_uid, game_biz)

    return """
    <html>
    <head>
        <meta http-equiv="refresh" content="2;url=https://discord.com/channels/@me">
    </head>
    <body style="text-align:center; margin-top:100px;">
        <h2>✅ Đã chọn tài khoản thành công!</h2>
        <p>Đang quay lại Discord...</p>
        <a href="https://discord.com/channels/@me">Nhấn nếu không tự động chuyển</a>
    </body>
    </html>
    """