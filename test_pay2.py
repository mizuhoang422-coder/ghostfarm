"""Test payment/confirm voi field dung."""
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

# Test payment/next
print("=== PAYMENT/NEXT ===")
for body in [
    {"package":"I","amount":25000},
    {"package":"II","amount":100000},
    {"package":"V","amount":5000000},
    {"package":"I","amount":0},
    {"package":"I","amount":1},
    {"package":"I","amount":999999999},
]:
    r = httpx.post(BASE+"/api/payment/next", json=body, headers=H, timeout=15)
    print(f"    {body} -> {r.status_code}  {r.text[:200]}")

# Test payment/confirm
print("\n=== PAYMENT/CONFIRM ===")
for body in [
    {"package":"I","amount":25000},
    {"package":"V","amount":5000000},
    {"package":"I","amount":0},
    {"package":"I","amount":1},
    {"package":"I","amount":-25000},
    {"package":"","amount":0},
]:
    r = httpx.post(BASE+"/api/payment/confirm", json=body, headers=H, timeout=15)
    print(f"    {body} -> {r.status_code}  {r.text[:200]}")

# Test withdraw gate
print("\n=== WITHDRAW gate ===")
me = httpx.get(BASE+"/api/me", headers=H, timeout=15).json()
bal = me.get("balance", 0)
print(f"    my balance: {bal}")
for amt in [2000, 5000, 50000, 200000]:
    r = httpx.post(BASE+"/api/withdraw", json={"amount":amt}, headers=H, timeout=15)
    print(f"    {amt} -> {r.status_code}  {r.text[:200]}")

# Check profile after
print("\n=== ME after all ===")
me = httpx.get(BASE+"/api/me", headers=H, timeout=15).json()
print(f"    package_multiplier: {me.get('package_multiplier')}")
print(f"    multiplier: {me.get('multiplier')}")
print(f"    balance: {me.get('balance')}")
