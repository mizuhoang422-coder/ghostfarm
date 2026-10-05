"""Do cooldown claim + fuzz endpoint an + task telegram 401."""
import sys, os, time, asyncio, re
sys.path.insert(0, os.getcwd())
import httpx, storage
storage.init()
from pathlib import Path

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
H = {**UA, "X-Telegram-Init-Data": idata}

# ===== 1. Extract toan bo path tu HTML =====
print("=== 1. PATH tu HTML ===")
html = (Path.home() / ".tg_toolkit" / "thodaovang" / "index.html").read_text(encoding="utf-8", errors="ignore")
paths = set()
for m in re.finditer(r'''["'`](/[a-zA-Z0-9_\-/]+)["'`]''', html):
    p = m.group(1)
    if len(p) > 3 and not p.startswith("//"):
        paths.add(p)
for p in sorted(paths): print(f"    {p}")

# ===== 2. Task telegram 401 =====
print("\n=== 2. TASK telegram 401 ===")
for body in [{"task":"telegram"}, {"task":"telegram","task_type":"telegram"},
             {"task":"tg"}, {"task":"telegram_channel"},
             {"task":"telegram","started":True}]:
    r = httpx.post(BASE+"/api/task/start", json=body, headers=H, timeout=15)
    print(f"    {body} -> {r.status_code}  {r.text[:150]}")

# ===== 3. Cooldown claim chinh xac (wait longer) =====
print("\n=== 3. COOLDOWN claim (test 30-120s) ===")
r = httpx.post(BASE+"/api/claim", headers=H, timeout=15)
try:
    j = r.json()
    print(f"    initial: {r.status_code}  ok={j.get('ok')}  claimed={j.get('claimed')}")
except: pass

for secs in [30, 60, 90, 120]:
    print(f"    doi {secs}s...")
    time.sleep(secs)
    r = httpx.post(BASE+"/api/claim", headers=H, timeout=15)
    try:
        j = r.json()
        print(f"    t+{secs}s: ok={j.get('ok')}  claimed={j.get('claimed')}")
        if j.get("ok"): break
    except: print(f"    t+{secs}s: parse fail")

# ===== 4. Endpoint an =====
print("\n=== 4. FUZZ endpoint an ===")
guess = ["/api/mine", "/api/upgrade", "/api/shop", "/api/boost", "/api/spin",
         "/api/daily", "/api/box", "/api/vip", "/api/package", "/api/packages",
         "/api/multiplier", "/api/buy", "/api/sell", "/api/exchange",
         "/api/history", "/api/tasks/start", "/api/tasks/claim",
         "/api/referral", "/api/referrals", "/api/ref", "/api/config",
         "/api/info", "/api/user", "/api/profile", "/api/leaderboard",
         "/api/top", "/api/rank", "/api/stats", "/api/settings",
         "/api/payment/packages", "/api/payment/list", "/api/payments",
         "/api/admin", "/api/debug", "/api/version"]
for p in guess:
    try:
        r = httpx.get(BASE+p, headers=H, timeout=10)
        if r.status_code != 404:
            print(f"    GET  {p:<32} -> {r.status_code}  {r.text[:120]}")
    except Exception: pass
    try:
        r = httpx.post(BASE+p, json={}, headers=H, timeout=10)
        if r.status_code != 404 and r.status_code != 400:
            print(f"    POST {p:<32} -> {r.status_code}  {r.text[:120]}")
    except Exception: pass

# ===== 5. Self-referral bypass =====
print("\n=== 5. SELF-REFERRAL test ===")
me = httpx.get(BASE+"/api/me", headers=H).json()
ref_code = me.get("member_id") or me.get("ref_code")
print(f"    my member_id: {ref_code}")
# Thu cac endpoint ref
for path in ["/api/referral", "/api/referrals"]:
    r = httpx.get(BASE+path, headers=H, timeout=15)
    print(f"    GET {path} -> {r.status_code}  {r.text[:200]}")

# ===== 6. Payment package that =====
print("\n=== 6. PACKAGE IDs ===")
for pid in range(1, 11):
    r = httpx.post(BASE+"/api/payment/next", json={"package_id": pid}, headers=H, timeout=10)
    if r.status_code != 400 or "không hợp lệ" not in r.text:
        print(f"    id={pid} -> {r.status_code}  {r.text[:150]}")
# Thu pkg by name
for pid in ["pkg1","pkg2","basic1","goi1","package1","vip1","p1","GOLD1"]:
    r = httpx.post(BASE+"/api/payment/next", json={"package_id": pid}, headers=H, timeout=10)
    if r.status_code != 400:
        print(f"    id={pid} -> {r.status_code}  {r.text[:150]}")

# ===== 7. Method override =====
print("\n=== 7. HTTP method override ===")
for m in ["PUT", "PATCH", "DELETE", "OPTIONS"]:
    try:
        r = httpx.request(m, BASE+"/api/me", headers=H, timeout=10)
        print(f"    {m} /api/me -> {r.status_code}")
    except Exception: pass

# ===== 8. Final balance =====
print("\n=== 8. FINAL ===")
me = httpx.get(BASE+"/api/me", headers=H).json()
print(f"    balance: {me.get('balance')}  pending: {me.get('pending_gold')}")

