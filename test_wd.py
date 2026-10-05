"""Test withdraw 1 lan + task race + claim cooldown."""
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

# 1. Bank hien tai
print("=== 1. BANK HIEN TAI ===")
bank = httpx.get(BASE+"/api/bank", headers=H, timeout=15).json()
print(f"    {bank}")

# 2. Me
me = httpx.get(BASE+"/api/me", headers=H, timeout=15).json()
bal = me.get("balance", 0)
refs = me.get("referrals", 0)
print(f"\n=== 2. ME ===")
print(f"    balance: {bal:,.0f} gold")
print(f"    referrals: {refs}")
print(f"    required: 20")

# 3. WITHDRAW — chi 1 request duy nhat, so 2.000.000 gold = 2.000 VND
print(f"\n=== 3. WITHDRAW 2,000,000 GOLD = 2,000 VND ===")
r = httpx.post(BASE+"/api/withdraw", json={"amount":2000000}, headers=H, timeout=20)
print(f"    status: {r.status_code}")
print(f"    body: {r.text[:500]}")

if r.status_code == 200:
    try:
        j = r.json()
        if j.get("ok"):
            print(f"\n    ✅ RUT THANH CONG")
            print(f"    request_id: {j.get('request_id')}")
        else:
            print(f"\n    ❌ {j.get('error')}")
    except Exception as e:
        print(f"    parse fail: {e}")

# 4. Check lai me sau withdraw
print(f"\n=== 4. SAU WITHDRAW ===")
me2 = httpx.get(BASE+"/api/me", headers=H, timeout=15).json()
print(f"    balance: {me2.get('balance'):,.0f}  (chenh {bal - me2.get('balance', 0):,.0f})")
hist = httpx.get(BASE+"/api/withdraw/history", headers=H, timeout=15).json()
print(f"    history: {json.dumps(hist, ensure_ascii=False)[:400]}")

# 5. Task race
print(f"\n=== 5. TASK RACE ===")
from concurrent.futures import ThreadPoolExecutor, as_completed
def tc(i):
    try:
        r1 = httpx.post(BASE+"/api/task/start", json={"task":"facebook"}, headers=H, timeout=10)
        r2 = httpx.post(BASE+"/api/task/claim", json={"task":"facebook"}, headers=H, timeout=10)
        return r1.status_code, r2.status_code, r2.text[:100]
    except Exception as e:
        return 0, 0, str(e)[:60]
with ThreadPoolExecutor(max_workers=10) as ex:
    res = [f.result() for f in as_completed([ex.submit(tc,i) for i in range(10)])]
for s1, s2, t in res[:3]:
    print(f"    start={s1} claim={s2}  {t}")

# 6. Cooldown claim
print(f"\n=== 6. CLAIM cooldown ===")
for secs in [60, 180, 300]:
    print(f"    doi {secs}s...")
    time.sleep(secs)
    r = httpx.post(BASE+"/api/claim", headers=H, timeout=15)
    try:
        j = r.json()
        print(f"    t+{secs}s: ok={j.get('ok')}  claimed={j.get('claimed')}  bal={j.get('balance')}")
        if j.get("ok"): break
    except: pass
