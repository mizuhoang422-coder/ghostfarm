import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import storage
storage.init()
accs = storage.list_accounts()
target = accs[0]
print(f"[+] Test ad watcher tren {target['name']}")
from ad_watcher import watch_one_ad
def log(m): print(m, flush=True)
r = watch_one_ad(target["init_data"], log=log, max_wait=90)
print("=" * 50)
print(f"RESULT: {r}")
print("=" * 50)
