import sys, os, time
sys.path.insert(0, os.getcwd())
import storage
storage.init()

from ad_watcher import watch_one_ad

accs = storage.list_accounts()
print(f"[+] {len(accs)} acc")

for a in accs:
    if not a.get("init_data"):
        print(f"[!] {a['name']}: khong co init_data, bo qua")
        continue
    print(f"\n{'='*50}")
    print(f"[*] Test acc {a['name']} (uid={a.get('uid')})")
    print(f"{'='*50}")
    def log(m): print(f"  [{a['name']}] {m}", flush=True)
    # Thu xem Gigapub
    r = watch_one_ad(a["init_data"], log=log, max_wait=90, task_name="Gigapub")
    print(f"  RESULT: {r}")
    if r.get("ok"):
        print(f"  ✅ THANH CONG")
        break
    else:
        print(f"  ❌ FAIL: {r.get('err')}")
