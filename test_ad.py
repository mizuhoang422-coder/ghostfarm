"""Test ad_watcher local — inject session roi test."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
import storage

storage.init()

# 4 session Kovak da cung cap
SEEDS = [
    ("FOX",    "+84837258569", "1BVtsOIcBu7ViVQ5BLPvVOFaILHfkWyScKtjbc-NoNQczQfBel5g_hBFUZERD6o_QgKZny-m1VWTppESH7XsILIf4t0dmoyKtgUCK-XVPzlJo_PKkdmAMFMB1_O3qEN5KDZGMif-CJZUoOjZcnTX_kNCrTLEzMgoBfdEhXhwB0vn6zpWT8SGjgAV0f1fg-M-v-sXTw8cSxQaKSI4Px9LmDqHXXNQKnH_oUoieR2xLpXGcom8At1mhIms5fZ2XotV-zu9T0IYT9ntpgLXxD9dHxMWldfzxqxYGJCQBTiMdRXe6pBcyJEPPua1nvPL1iwXkDePyRO-WRyos4Ulg3aWDc1iC9rLWMvw="),
    ("A1ztus", "+84911404475", "1BVtsOIcBu5fNmr6DZEiB_Yn96f2xGzgcxGrUtiIr5F3MAln2nGfGKi_TffP_jLxDkCP91VBq1m04Kmr4mSKuZD0FZ5GTAklzNefEpkJqJowGvEd1YU0VAXPnprVI9vmvaxRApceiMWmFpvle2O3C_arTZv5L_Fr2Ip4vw65tOymyxpMlEfEtb94Lgi1u5CzmGtBi3qFRvHa5TQruq1I_lhPgV3wGY1p4Q0rPPDt2dj_rEWs_uhzVv0lvOp7KyTS9Ye059Fb34HG5f3QFV0BznuLvXCoe7pzdkpOPn53qlWivThPfU8bMlgPuc5UUGtLVDaCTRLP_zS6HlcNeEtXSVgnvWOg9Z3k="),
    ("Henri",  "+84382061412", "1BVtsOIcBu2Jv9WBQqcs5qHqdj4bDlh_gxJDwSOnFz8RxtR8bFtvB0emf-UehU_3GeHjVJop7iRUgPI5GKL6jizQlm-yoZ1THF0-p7rWIamvA0BuYVYM2AZUg6wsR1I96p6NNz4FEGk94MI6fk_xFNpe6ih9JUSkgdejsg4sj4AMpR5NDqhcIJOrcxGJzsamsNdSBMqVdd-5dEQYs0KDHoD7CZweJ5u59zkHu4_F_q_7g9_U2JbU0iG7wDJe4gs2q-xLVdCVOpppqExQsNvw7U9MtNfTG9FcYNYg5Fp1wW6rYVc5N_H5_rZ-C2PHOOU-b0e1zI17i7a22S5mark7lDC4vdMwivuk="),
]

# Them vao DB local
existing = {a["name"] for a in storage.list_accounts()}
for name, phone, sess in SEEDS:
    if name in existing:
        print(f"[=] {name} da co")
        continue
    # lay uid
    try:
        import asyncio
        from farm_engine import get_me_from_session
        loop = asyncio.new_event_loop()
        info = loop.run_until_complete(get_me_from_session(sess))
        loop.close()
        if not info:
            print(f"[!] {name} session invalid")
            continue
        aid = storage.add_account(name, phone, sess, info["uid"])
        print(f"[+] {name} added id={aid} uid={info['uid']}")
    except Exception as e:
        print(f"[!] {name}: {e}")

print()
print("[+] Acc trong DB:")
for a in storage.list_accounts():
    print(f"    #{a['id']} {a['name']} uid={a.get('uid')} init_data={'YES' if a.get('init_data') else 'NO'}")

# Chon acc dau tien, refresh initData
accs = storage.list_accounts()
if not accs:
    print("[!] Khong co acc"); sys.exit(1)

target = accs[0]
print(f"\n[*] Target: {target['name']} (id={target['id']})")

# Neu chua co initData, fetch
if not target.get("init_data"):
    print("[*] Fetching initData...")
    import asyncio
    from farm_engine import fetch_initdata_with_ref
    loop = asyncio.new_event_loop()
    idata = loop.run_until_complete(fetch_initdata_with_ref(target["session"], "GF8249205817"))
    loop.close()
    if not idata:
        print("[!] Khong fetch duoc initData")
        sys.exit(1)
    storage.update_account(target["id"], init_data=idata, init_ts=int(time.time()))
    print(f"[+] initData len={len(idata)}")
    target = storage.get_account(target["id"])

# Check playwright
try:
    from playwright.sync_api import sync_playwright
    print("[+] Playwright OK")
except Exception as e:
    print(f"[!] Playwright NOT installed: {e}")
    sys.exit(1)

try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--no-sandbox","--single-process"])
        b.close()
    print("[+] Chromium OK")
except Exception as e:
    print(f"[!] Chromium launch fail: {str(e)[:200]}")
    print("    Chay: python -m playwright install chromium-headless-shell")
    sys.exit(1)

# Chay ad watcher
print("\n[*] Bat dau test ad watcher (max 60s)...")
from ad_watcher import watch_one_ad
def log(m): print(m, flush=True)

result = watch_one_ad(target["init_data"], log=log, max_wait=60)
print()
print("=" * 50)
print(f"RESULT: {result}")
print("=" * 50)
