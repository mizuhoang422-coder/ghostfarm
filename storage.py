import sqlite3, json, os
from pathlib import Path

DB_PATH = Path(os.environ.get("DATA_DIR", "./data")) / "ghostfarm.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _c():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c

def init():
    with _c() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT, session TEXT, uid INTEGER, name TEXT,
            farm_running INTEGER DEFAULT 0,
            config TEXT DEFAULT '{}',
            bank_name TEXT, bank_ctk TEXT, bank_stk TEXT,
            last_state TEXT, created_at INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY, value TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS redeemed_codes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT, acc_id INTEGER, ok INTEGER, msg TEXT, ts INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS activity(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acc_id INTEGER, ts INTEGER, msg TEXT)""")

def add_account(phone, session, uid, name):
    with _c() as c:
        c.execute("INSERT INTO accounts(phone,session,uid,name,created_at) VALUES(?,?,?,?,?)",
                  (phone, session, uid, name, int(__import__("time").time())))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]

def list_accounts():
    with _c() as c:
        return [dict(r) for r in c.execute("SELECT * FROM accounts ORDER BY id").fetchall()]

def get_account(aid):
    with _c() as c:
        r = c.execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone()
        return dict(r) if r else None

def update_account(aid, **kw):
    if not kw: return
    sets = ",".join(f"{k}=?" for k in kw)
    vals = list(kw.values()) + [aid]
    with _c() as c:
        c.execute(f"UPDATE accounts SET {sets} WHERE id=?", vals)

def delete_account(aid):
    with _c() as c:
        c.execute("DELETE FROM accounts WHERE id=?", (aid,))

def log_activity(aid, msg):
    with _c() as c:
        c.execute("INSERT INTO activity(acc_id,ts,msg) VALUES(?,?,?)",
                  (aid, int(__import__("time").time()), msg))

def get_activity(aid, limit=20):
    with _c() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM activity WHERE acc_id=? ORDER BY id DESC LIMIT ?",
            (aid, limit)).fetchall()]

def set_setting(k, v):
    with _c() as c:
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (k, v))

def get_setting(k, d=None):
    with _c() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
        return r["value"] if r else d

def add_code(code, acc_id, ok, msg):
    with _c() as c:
        c.execute("INSERT INTO redeemed_codes(code,acc_id,ok,msg,ts) VALUES(?,?,?,?,?)",
                  (code, acc_id, 1 if ok else 0, msg, int(__import__("time").time())))

def list_codes(limit=50):
    with _c() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM redeemed_codes ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

def is_code_used(code, acc_id=None):
    with _c() as c:
        if acc_id:
            r = c.execute("SELECT 1 FROM redeemed_codes WHERE code=? AND acc_id=? AND ok=1 LIMIT 1",
                          (code, acc_id)).fetchone()
        else:
            r = c.execute("SELECT 1 FROM redeemed_codes WHERE code=? AND ok=1 LIMIT 1", (code,)).fetchone()
        return r is not None
