# web.py
from flask import Flask, request, render_template_string, Response
import httpx
import re
import asyncio
import aiosqlite
import genshin
import os
from urllib.parse import urljoin, urlparse

app = Flask(__name__)
DB_PATH = "hoyolab_auto_data.db"
HOYOLAB_BASE = "https://www.hoyolab.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"

# Hàm proxy chung: Fetch từ Hoyolab và rewrite URLs
async def proxy_request(path, method='GET', body=None):
    url = urljoin(HOYOLAB_BASE, path)
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': request.headers.get('Accept', '*/*'),
        'Referer': HOYOLAB_BASE,
        # Forward cookies nếu có (từ user session)
        'Cookie': request.headers.get('Cookie', '')
    }
    async with httpx.AsyncClient() as client:
        if method == 'POST':
            resp = await client.post(url, headers=headers, data=body or request.form, cookies=dict(request.cookies))
        else:
            resp = await client.get(url, headers=headers, cookies=dict(request.cookies))
        
        # Capture Set-Cookie từ response
        cookies = {}
        for cookie in resp.cookies:
            if 'ltuid_v2' in cookie.key or 'ltoken_v2' in cookie.key or 'cookie_token_v2' in cookie.key:
                cookies[cookie.key] = cookie.value
        
        # Rewrite HTML: Thay relative URLs thành proxy URLs
        content = resp.text
        if 'text/html' in resp.headers.get('content-type', ''):
            content = re.sub(r'(src|href|action)=["\']([^"\']+)["\']', lambda m: f'{m.group(1)}="/hoyolab-proxy\\{m.group(2)}"', content)
            content = re.sub(r'(url\()([^)]+)\)', lambda m: f'{m.group(1)}"/hoyolab-proxy{m.group(2)}"', content)
        
        return content, resp.status_code, dict(resp.headers), cookies

@app.route('/health')
def health():
    return "OK", 200

@app.route('/hoyolab/login')
def hoyolab_login():
    user_id = request.args.get('user_id')
    if not user_id:
        return "Thiếu user_id", 400
    # Redirect đến proxy login page
    return f'<meta http-equiv="refresh" content="0;url=/hoyolab-proxy/home"> <script>window.location.href="/hoyolab-proxy/home?user_id={user_id}";</script>'

# Proxy route cho tất cả paths của Hoyolab
@app.route('/hoyolab-proxy/<path:path>', methods=['GET', 'POST'])
async def hoyolab_proxy(path):
    user_id = request.args.get('user_id')
    method = request.method
    body = request.form if method == 'POST' else None
    
    content, status, headers, captured_cookies = await proxy_request(path, method, body)
    
    # Nếu là POST login (detect bằng path chứa 'login'), capture cookies và lưu DB
    if method == 'POST' and ('login' in path or 'auth' in path) and captured_cookies:
        ltuid = captured_cookies.get('ltuid_v2', '')
        ltoken = captured_cookies.get('ltoken_v2', '')
        cookie_token = captured_cookies.get('cookie_token_v2', '')
        if all([ltuid, ltoken, cookie_token]):
            try:
                client = genshin.Client(cookies=captured_cookies)
                accounts = await client.get_game_accounts()
                if accounts:
                    # Hiển thị form chọn account ngay trong response (thay vì redirect)
                    account_options = ""
                    for account in accounts:
                        if "genshin" in account.game_biz or "hkrpg" in account.game_biz:
                            account_options += f'<option value="{account.uid}|{account.game_biz}">{account.nickname} ({account.game_biz})</option>'
                    
                    content = f"""
                    <html>
                    <body style="font-family: Arial; max-width: 800px; margin: 40px auto;">
                        <h2>✅ Đăng nhập thành công! Chọn tài khoản game:</h2>
                        <form method="POST" action="/hoyolab/select_account">
                            <input type="hidden" name="user_id" value="{user_id}">
                            <input type="hidden" name="ltuid" value="{ltuid}">
                            <input type="hidden" name="ltoken" value="{ltoken}">
                            <input type="hidden" name="cookie_token" value="{cookie_token}">
                            <p><label>Chọn tài khoản: 
                                <select name="account" required>
                                    {account_options}
                                </select>
                            </label></p>
                            <button type="submit">✅ Xác nhận</button>
                        </form>
                        <p><a href="javascript:window.close()">Đóng tab và quay lại Discord</a></p>
                    </body>
                    </html>
                    """
                    status = 200
            except Exception as e:
                content += f"<p>Lỗi lấy accounts: {e}</p>"
    
    response = Response(content, status=status)
    for k, v in headers.items():
        if k.lower() not in ['content-encoding', 'transfer-encoding']:
            response.headers[k] = v
    
    # Set captured cookies cho client (nếu cần)
    for k, v in captured_cookies.items():
        response.set_cookie(k, v, domain='localhost')  # Adjust domain for Render
    
    return response

# Route chọn account (giữ nguyên)
@app.route('/hoyolab/select_account', methods=['POST'])
async def select_account():
    # Code giữ nguyên từ trước
    user_id = request.form['user_id']
    ltuid = request.form['ltuid']
    ltoken = request.form['ltoken']
    cookie_token = request.form['cookie_token']
    account = request.form['account']
    game_uid, game_biz = account.split('|')
    from database import save_user_data
    await save_user_data(user_id, ltuid, ltoken, cookie_token, game_uid, game_biz)
    return """
    <html>
    <head><meta http-equiv="refresh" content="2;url=https://discord.com/channels/@me"></head>
    <body style="text-align:center; margin-top:100px;">
        <h2>✅ Thành công! Quay lại Discord để kích hoạt auto check-in.</h2>
        <p><a href="javascript:window.close()">Đóng tab</a></p>
    </body>
    </html>
    """