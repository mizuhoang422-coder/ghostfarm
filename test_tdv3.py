"""Do cooldown claim + test header case + task names."""
import sys, os, time, asyncio
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
        url = res.url
        fr = url.split("#tgWebAppData=",1)[1].split("&tgWebAppVersion")[0]
        return unquote(fr)
    finally:
        await c.disconnect()

idata = asyncio.new_event_loop().run_until_complete(fetch_idata())
print(f"[+] idata len={len(idata)}")

# ===== 1. Test that su no header =====
print("\n=== 1. THAT SU no header ===")
import httpx
r = httpx.get(BASE+"/api/me", headers=UA, timeout=15)
print(f"    no X-Telegram-Init-Data: {r.status_code}  {r.text[:100]}")

r = httpx.get(BASE+"/api/me", headers={**UA, "X-Telegram-Init-Data": ""}, timeout=15)
print(f"    empty header:            {r.status_code}  {r.text[:100]}")

# ===== 2. Header case sensitivity =====
print("\n=== 2. Header variants ===")
for hname in ["X-Telegram-Init-Data", "x-telegram-init-data", "X-TELEGRAM-INIT-DATA",
              "X-Telegram-Initdata", "X-TelegramInitData", "X_Telegram_Init_Data"]:
    try:
        r = httpx.get(BASE+"/api/me", headers={**UA, hname: idata}, timeout=15)
        print(f"    {hname:<26} -> {r.status_code}")
    except Exception as e:
        print(f"    {hname:<26} -> err {e}")

# ===== 3. Claim cooldown =====
print("\n=== 3. CLAIM cooldown do ===")
H = {**UA, "X-Telegram-Init-Data": idata}
last_balance = None
for i in range(15):
    r = httpx.post(BASE+"/api/claim", headers=H, timeout=15)
    try: j = r.json()
    except: j = {}
    bal = j.get("balance")
    claimed = j.get("claimed")
    ok = j.get("ok")
    print(f"    #{i:2} t+{i*2:2}s  ok={ok}  claimed={claimed}  bal={bal}")
    time.sleep(2)

# ===== 4. Task names thu =====
print("\n=== 4. TASK names ===")
for t in ["facebook","telegram","youtube","tiktok","x","twitter","instagram","tiktok_1","yt","fb"]:
    r1 = httpx.post(BASE+"/api/task/start", json={"task":t}, headers=H, timeout=15)
    print(f"    start {t:<12} -> {r1.status_code}  {r1.text[:100]}")

# ===== 5. Task body variant =====
print("\n=== 5. TASK body variants ===")
for body in [{"task":"facebook"},{"name":"facebook"},{"id":"facebook"},
             {"task_type":"facebook"},{"task":"fb"}]:
    r = httpx.post(BASE+"/api/task/start", json=body, headers=H, timeout=15)
    print(f"    {body} -> {r.status_code}  {r.text[:120]}")

# ===== 6. Top type =====
print("\n=== 6. TOP types ===")
for t in ["gold","balance","referral","vnd","referrals","daily"]:
    r = httpx.get(BASE+f"/api/top?type={t}", headers=H, timeout=15)
    print(f"    type={t:<10} -> {r.status_code}  {r.text[:100]}")

# ===== 7. Final =====
print("\n=== 7. FINAL ===")
r = httpx.get(BASE+"/api/me", headers=H, timeout=15)
print(f"    {r.text[:400]}")
