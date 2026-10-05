"""Test API ThoDaoVang voi initData FOX."""
import sys, os, json, time, asyncio
sys.path.insert(0, os.getcwd())
import httpx, storage
storage.init()

from farm_engine import fetch_initdata_with_ref

BASE = "https://result-gotta-responsibility-firewire.trycloudflare.com"

# Lay session FOX
fox = None
for a in storage.list_accounts():
    if a.get("uid") == 8249205817:
        fox = a; break
if not fox:
    print("[!] Khong co acc FOX"); sys.exit(1)

# Fetch initData
print("[*] Fetch initData tu @ThoDaoVang_bot...")
BOT = "ThoDaoVang_bot"
# Tam thoi set BOT
from farm_engine import API_ID, API_HASH
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest
from urllib.parse import urlparse, parse_qsl, unquote

async def fetch():
    c = TelegramClient(StringSession(fox["session"]), API_ID, API_HASH)
    await c.connect()
    try:
        bot = await c.get_entity(BOT)
        for plat in ["android","ios","web"]:
            try:
                res = await c(RequestWebViewRequest(peer=bot, bot=bot, platform=plat,
                    url="https://result-gotta-responsibility-firewire.trycloudflare.com/",
                    from_bot_menu=True, compact=True))
                url = res.url
                if "#tgWebAppData=" in url:
                    fr = url.split("#tgWebAppData=", 1)[1]
                    raw = fr.split("&tgWebAppVersion")[0]
                    return unquote(raw)
            except Exception as e:
                print(f"    [{plat}] {type(e).__name__}: {str(e)[:100]}")
        return None
    finally:
        await c.disconnect()

idata = asyncio.new_event_loop().run_until_complete(fetch())
if not idata:
    print("[!] Khong lay duoc initData"); sys.exit(1)
print(f"[+] initData: {len(idata)} chars")
print(f"    head: {idata[:100]}")

UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36",
      "Accept": "application/json, text/plain, */*",
      "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
      "Origin": "https://result-gotta-responsibility-firewire.trycloudflare.com",
      "Referer": "https://result-gotta-responsibility-firewire.trycloudflare.com/"}

H = {**UA, "X-Telegram-Init-Data": idata}

with httpx.Client(timeout=20, follow_redirects=True, headers=H) as c:
    # GET endpoints
    print("\n=== GET ===")
    for path in ["/api/me", "/api/bank", "/api/tasks", "/api/withdraw/history", "/api/top?type=gold"]:
        try:
            r = c.get(BASE + path)
            body = r.text[:500]
            print(f"    {path}")
            print(f"    -> {r.status_code}  {body[:400]}")
        except Exception as e:
            print(f"    {path} ERR: {e}")

    # Test claim
    print("\n=== POST /api/claim ===")
    try:
        r = c.post(BASE + "/api/claim")
        print(f"    {r.status_code}  {r.text[:400]}")
    except Exception as e:
        print(f"    err: {e}")

    # Referral claim
    print("\n=== POST /api/referral/claim ===")
    try:
        r = c.post(BASE + "/api/referral/claim", json={})
        print(f"    {r.status_code}  {r.text[:400]}")
    except Exception as e:
        print(f"    err: {e}")

    # Bank
    print("\n=== POST /api/bank (empty) ===")
    try:
        r = c.post(BASE + "/api/bank", json={})
        print(f"    {r.status_code}  {r.text[:400]}")
    except Exception as e:
        print(f"    err: {e}")

    # Withdraw
    print("\n=== POST /api/withdraw (empty) ===")
    try:
        r = c.post(BASE + "/api/withdraw", json={})
        print(f"    {r.status_code}  {r.text[:400]}")
    except Exception as e:
        print(f"    err: {e}")

    # Task start
    print("\n=== POST /api/task/start (empty) ===")
    try:
        r = c.post(BASE + "/api/task/start", json={})
        print(f"    {r.status_code}  {r.text[:400]}")
    except Exception as e:
        print(f"    err: {e}")

    # Task claim
    print("\n=== POST /api/task/claim (empty) ===")
    try:
        r = c.post(BASE + "/api/task/claim", json={})
        print(f"    {r.status_code}  {r.text[:400]}")
    except Exception as e:
        print(f"    err: {e}")

    # Payment
    print("\n=== POST /api/payment/next (empty) ===")
    try:
        r = c.post(BASE + "/api/payment/next", json={})
        print(f"    {r.status_code}  {r.text[:400]}")
    except Exception as e:
        print(f"    err: {e}")

    print("\n=== POST /api/payment/confirm (empty) ===")
    try:
        r = c.post(BASE + "/api/payment/confirm", json={})
        print(f"    {r.status_code}  {r.text[:400]}")
    except Exception as e:
        print(f"    err: {e}")
