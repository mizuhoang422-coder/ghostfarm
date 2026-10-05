#!/usr/bin/env python3
"""vuadaomo.py - A1ZTUS BYPASS v5"""
import os, sys, json, re, time, threading, asyncio, urllib.parse, io
from pathlib import Path
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, TypeHandler, ApplicationHandlerStop)
from telethon import TelegramClient, functions, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN: sys.exit("BOT_TOKEN missing")
API_ID = int(os.environ.get("API_ID", "0"))
if not API_ID: sys.exit("API_ID missing")
API_HASH = os.environ.get("API_HASH")
if not API_HASH: sys.exit("API_HASH missing")
ADMINS = [int(x) for x in os.environ.get("ALLOWED_USERS", "").split(",") if x.strip()]
BASE = "https://vdm.builderminiapp.online"
BOT_USER = "Vua_dau_mo_bot"
CHANNELS = ["tinggg999", "chat_daumo99"]
MIN_EX = 100000
TTL = 12 * 3600
GIF_URL = os.environ.get("GIF_URL", "").strip()
DATA_DIR = Path(os.environ.get("DATA_DIR", "/tmp/vdm_bot"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
ACC_FILE = DATA_DIR / "accs.json"
CODE_FILE = DATA_DIR / "codes.json"
APPR_FILE = DATA_DIR / "approved.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36",
    "Origin": "https://web.telegram.org",
    "Referer": "https://web.telegram.org/",
    "Content-Type": "application/json",
    "Accept": "application/json, */*",
}
_lock = threading.Lock()

def _load(p, d):
    if p.exists():
        try: return json.loads(p.read_text())
        except: pass
    return d

def _save(p, v):
    with _lock:
        p.write_text(json.dumps(v, indent=2, ensure_ascii=False))

import os as _os_clear
if _os_clear.environ.get('CLEAR_ACCS') == '1':
    try:
        if ACC_FILE.exists(): ACC_FILE.unlink()
        print('[clear] da xoa accs.json cu')
    except Exception as _e:
        print('[clear] ' + str(_e))
ACCS = _load(ACC_FILE, {})
_rc = _load(CODE_FILE, {})
if isinstance(_rc, list):
    _rc = {c: [] for c in _rc}
    _save(CODE_FILE, _rc)
REDEEMED = _rc
APPROVED = set(_load(APPR_FILE, []))
PENDING_USERS = {}
PEND = {}
WD_WAIT = {}
WORKERS = {}
STOP = {}
WATCH = None
AS_STATE = {}
USER_META = _load(DATA_DIR / 'user_meta.json', {})
def save_user_meta(): _save(DATA_DIR / 'user_meta.json', USER_META)
BROADCAST_WAIT = {}
OTP_STATE = {}

_sj = os.environ.get("SESSIONS_JSON", "").strip()
if _sj:
    try:
        _d = json.loads(_sj)
        _n = 0
        for _k, _v in _d.items():
            if _k in ACCS: continue
            if not _v.get("session"): continue
            ACCS[_k] = {
                "phone": _v.get("phone", ""),
                "session_string": _v["session"],
                "owner": _v.get("owner", 0),
                "created": datetime.now().isoformat(),
                "flags": {"mine": False, "claim": False, "watch": False, "box": False,
                          "craft": False, "spin": False, "exchange": False, "upgrade": False},
                "user": {}, "stats": {}, "cd": {},
            }
            _n += 1
        if _n: print("[env] loaded " + str(_n))
    except Exception as _e:
        print("[env] error: " + str(_e))

def is_admin(uid):
    return uid in ADMINS if ADMINS else False

def is_approved(uid):
    return is_admin(uid) or uid in APPROVED

def is_owner(uid, name):
    a = ACCS.get(name, {})
    if is_admin(uid): return True
    if a.get("owner") == uid: return True
    if a.get("assigned_to") == uid: return True
    return False


def user_accs(uid):
    if is_admin(uid): return list(ACCS.keys())
    return [n for n, a in ACCS.items() if a.get("assigned_to") == uid or a.get("owner") == uid]

def pool_accs():
    return [n for n, a in ACCS.items() if not a.get("assigned_to")]

def admin_accs():
    return [n for n, a in ACCS.items() if a.get("owner") in ADMINS]


def save_approved():
    _save(APPR_FILE, list(APPROVED))

def fmt(x, p=2):
    try: return "{:,.{}f}".format(float(x), p)
    except: return str(x)

def api(name, ep, extra=None, timeout=12):
    a = ACCS.get(name)
    if not a: return None
    idata = a.get("init_data")
    if not idata: return None
    body = {"initData": idata}
    if extra: body.update(extra)
    try:
        r = requests.post(BASE + ep, headers=HEADERS, json=body, timeout=timeout)
        rem = r.headers.get("RateLimit-Remaining")
        if rem and int(rem) <= 2: time.sleep(1.5)
        return r
    except Exception as e:
        print("[api " + name + "] " + str(e))
        return None

def parse_wait(msg):
    if not msg: return 30
    m = re.search(r"(\d+)\s*ph[u\u00fa]t", msg)
    if m: return int(m.group(1)) * 60 + 5
    m = re.search(r"(\d+)\s*gi[a\u00e2]y", msg)
    if m: return int(m.group(1)) + 2
    if "qu\u00e1 nhanh" in msg or "qu\u00e1 nhi\u1ec1u" in msg: return 30
    return 60

async def fetch_initdata(sess):
    client = TelegramClient(StringSession(sess), API_ID, API_HASH)
    await client.connect()
    try:
        if not await client.is_user_authorized(): return None
        bot = await client.get_entity(BOT_USER)
        for pl in ("android", "web", "ios"):
            try:
                res = await client(functions.messages.RequestWebViewRequest(
                    peer=bot, bot=bot, platform=pl, url=BASE + "/", from_bot_menu=False))
                url = res.url
                if "#tgWebAppData=" in url:
                    fr = url.split("#tgWebAppData=", 1)[1]
                    raw = re.split(r"&tgWebAppVersion|&tgWebAppPlatform|&tgWebAppThemeParams", fr)[0]
                    return urllib.parse.unquote(raw)
                if "tgWebAppData=" in url:
                    fr = url.split("tgWebAppData=", 1)[1]
                    return urllib.parse.unquote(fr.split("&")[0])
            except: pass
        return None
    finally:
        try: await client.disconnect()
        except: pass

async def refresh_idata(name):
    a = ACCS.get(name)
    if not a: return False
    try:
        fresh = await fetch_initdata(a["session_string"])
        if fresh:
            a["init_data"] = fresh
            a["init_ts"] = time.time()
            _save(ACC_FILE, ACCS)
            return True
    except Exception as e:
        print("[refresh " + name + "] " + str(e))
    return False
async def do_task(name, task, ep, extra=None, cd_key=None, cd_secs=0):
    a = ACCS.get(name)
    if not a: return None
    cd = a.setdefault("cd", {})
    now = time.time()
    if cd_key and cd.get(cd_key, 0) > now: return None
    r = await asyncio.to_thread(api, name, ep, extra)
    if not r: return None
    try: j = r.json()
    except: return None
    if j.get("success"):
        st = a.setdefault("stats", {})
        st[task] = st.get(task, 0) + 1
        if cd_secs: cd[cd_key or task] = now + cd_secs
        _save(ACC_FILE, ACCS)
        return j
    msg = j.get("error") or j.get("message") or ""
    if msg: cd[cd_key or task] = now + parse_wait(msg)
    return None

async def farm_loop(name):
    ev = STOP[name]
    if not ACCS[name].get("init_data"):
        await refresh_idata(name)
    while not ev.is_set():
        try:
            a = ACCS.get(name)
            if not a: break
            if time.time() - a.get("init_ts", 0) > TTL:
                await refresh_idata(name)
            r = await asyncio.to_thread(api, name, "/api/login")
            if not r or r.status_code != 200:
                await asyncio.sleep(30); continue
            try:
                u = r.json().get("user", {})
                a["user"] = u
            except: u = a.get("user", {})
            oil = u.get("oil_balance", 0)
            f = a.get("flags", {})
            if f.get("mine") and not u.get("is_mining"):
                await do_task(name, "mine", "/api/start-mine", cd_key="mine", cd_secs=30)
            if f.get("claim"):
                await do_task(name, "claim", "/api/claim", cd_key="claim", cd_secs=45)
            if f.get("watch"):
                await do_task(name, "watch", "/api/watch-video", cd_key="watch", cd_secs=15*60+10)
            if f.get("box") and u.get("mystery_boxes", 0) > 0:
                await do_task(name, "box", "/api/open-box-all", cd_key="box", cd_secs=5)
            if f.get("craft") and u.get("shards", 0) >= 10 and u.get("tickets", 0) < 50:
                await do_task(name, "craft", "/api/craft-ticket", cd_key="craft", cd_secs=3)
            if f.get("spin") and u.get("tickets", 0) > 0:
                await do_task(name, "spin", "/api/spin", cd_key="spin", cd_secs=4)
            if f.get("exchange") and oil >= MIN_EX:
                await do_task(name, "exchange", "/api/exchange", extra={"oilAmount": MIN_EX}, cd_key="exchange", cd_secs=10)
            if f.get("upgrade") and oil >= 50000:
                for t in ("speed", "capacity"):
                    j = await do_task(name, "upgrade", "/api/upgrade", extra={"type": t}, cd_key="upg_" + t, cd_secs=15)
                    if j: break
            if REDEEMED:
                rn = 0
                for code, accs in list(REDEEMED.items()):
                    if name in accs: continue
                    try:
                        rr = await asyncio.to_thread(api, name, "/api/redeem-code", {"code": code})
                        if rr and rr.status_code == 200:
                            jj = rr.json()
                            if jj.get("success"):
                                accs.append(name)
                                _save(CODE_FILE, REDEEMED)
                                st = a.setdefault("stats", {})
                                st["redeem"] = st.get("redeem", 0) + 1
                                _save(ACC_FILE, ACCS)
                    except: pass
                    rn += 1
                    if rn >= 5: break
            await asyncio.sleep(20)
        except asyncio.CancelledError: break
        except Exception as e:
            print("[farm " + name + "] " + str(e))
            await asyncio.sleep(20)
    WORKERS.pop(name, None)

def start_farm(app, name):
    if name in WORKERS and not WORKERS[name].done(): return False
    ev = threading.Event()
    STOP[name] = ev
    WORKERS[name] = asyncio.create_task(farm_loop(name))
    return True

def stop_farm(name):
    ev = STOP.get(name)
    if ev: ev.set()
    t = WORKERS.get(name)
    if t and not t.done(): t.cancel()

def _admin_session_acc():
    for n, a in ACCS.items():
        if a.get("owner") in ADMINS and a.get("session_string"):
            return n
    return None

async def watcher_loop(app):
    if not ACCS: return
    fn = _admin_session_acc()
    if not fn:
        print("[watcher] khong co session admin")
        return
    print("[watcher] dung session admin: " + fn)
    client = None
    try:
        client = TelegramClient(StringSession(ACCS[fn]["session_string"]), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            print("[watcher] admin session het han")
            await client.disconnect(); return
        ents = []
        for ch in CHANNELS:
            try:
                e = await client.get_entity(ch)
                ents.append(e)
                print("[watcher] joined " + ch)
            except Exception as ex:
                print("[watcher] skip " + ch + ": " + str(ex))
        if not ents:
            await client.disconnect(); return
    except Exception as e:
        print("[watcher] " + str(e))
        if client:
            try: await client.disconnect()
            except: pass
        return

    @client.on(events.NewMessage(chats=ents))
    async def on_msg(ev):
        text = ev.message.message or ""
        for code in re.findall(r"VUADAUMO_[A-Z0-9]{5,}", text.upper()):
            already = REDEEMED.setdefault(code, [])
            todo = [n for n in list(ACCS.keys()) if n not in already]
            if not todo: continue
            print("[watcher] " + code + " -> " + str(len(todo)))
            for nm in todo:
                r = await asyncio.to_thread(api, nm, "/api/redeem-code", {"code": code})
                if r and r.status_code == 200:
                    try:
                        j = r.json()
                        if j.get("success"):
                            already.append(nm); _save(CODE_FILE, REDEEMED)
                            st = ACCS[nm].setdefault("stats", {})
                            st["redeem"] = st.get("redeem", 0) + 1
                            _save(ACC_FILE, ACCS)
                    except: pass
    print("[watcher] listening " + ", ".join(CHANNELS))
    await client.run_until_disconnected()

async def scan_history(limit=800):
    if not ACCS: return {}
    fn = _admin_session_acc()
    if not fn: return {}
    client = TelegramClient(StringSession(ACCS[fn]["session_string"]), API_ID, API_HASH)
    await client.connect()
    found = {}
    try:
        if not await client.is_user_authorized(): return {}
        for ch in CHANNELS:
            try:
                entity = await client.get_entity(ch)
                async for msg in client.iter_messages(entity, limit=limit):
                    text = msg.message or ""
                    for code in re.findall(r"VUADAUMO_[A-Z0-9]{5,}", text.upper()):
                        if code not in found:
                            found[code] = msg.id
            except Exception as e:
                print("[scan] " + ch + ": " + str(e))
    finally:
        try: await client.disconnect()
        except: pass
    return found
def main_caption(uid=None):
    names = user_accs(uid) if uid else list(ACCS.keys())
    nn = len(names); on = 0
    for nm in names:
        w = WORKERS.get(nm)
        try:
            if w and not w.done(): on += 1
        except: pass
    try: wr = "\u0110ANG B\u1eacT" if (WATCH and not WATCH.done()) else "\u0110ANG T\u1eaeT"
    except: wr = "\u0110ANG T\u1eaeT"
    code_cnt = sum(1 for c_, accs in REDEEMED.items() if any(n in accs for n in names))
    return (
        "<b>\U0001f525 A1ZTUS BYPASS</b>\n"
        "<i>\u26a1 Trung t\u00e2m \u0111i\u1ec1u khi\u1ec3n</i>\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "<b>\U0001f4ca T\u1ed4NG QUAN</b>\n"
        "\U0001f465 T\u00e0i kho\u1ea3n: <b>" + str(nn) + "</b>\n"
        "\u25b6\ufe0f \u0110ang farm: <b>" + str(on) + "</b>\n"
        "\U0001f381 Code \u0111\u00e3 nh\u1eadn: <b>" + str(code_cnt) + "</b>\n"
        "\U0001f4e1 Theo d\u00f5i code: <b>" + wr + "</b>\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "<i>\U0001f4a1 Ch\u1ecdn ch\u1ee9c n\u0103ng b\u00ean d\u01b0\u1edbi</i>"
    )


def kb_main(uid=None):
    rows = []
    if uid and is_admin(uid):
        rows.append([InlineKeyboardButton("\U0001f4c1  Th\u00eam acc (file txt)", callback_data="admin_add")])
    rows.append([
        InlineKeyboardButton("\u2795  Th\u00eam acc (OTP)", callback_data="add"),
        InlineKeyboardButton("\U0001f511  Th\u00eam acc (Session)", callback_data="add_session"),
    ])
    rows.append([InlineKeyboardButton("\U0001f4cb  Danh s\u00e1ch acc", callback_data="panel_list")])
    rows.append([
        InlineKeyboardButton("\U0001f4ca  Xem tr\u1ef1c ti\u1ebfp", callback_data="live"),
        InlineKeyboardButton("\U0001f381  Qu\u1ea3n l\u00fd code", callback_data="code_menu"),
    ])
    rows.append([
        InlineKeyboardButton("\U0001f504  L\u00e0m m\u1edbi", callback_data="rf_all"),
        InlineKeyboardButton("\U0001f5d1  X\u00f3a acc", callback_data="del_list"),
    ])
    rows.append([
        InlineKeyboardButton("\U0001f517  Chia s\u1ebb bot", callback_data="share_help"),
        InlineKeyboardButton("\U0001f194  ID c\u1ee7a t\u00f4i", callback_data="myid_help"),
    ])
    if uid and is_admin(uid):
        rows.append([InlineKeyboardButton("\U0001f465  Qu\u1ea3n l\u00fd ng\u01b0\u1eddi d\u00f9ng", callback_data="users_panel")])
        rows.append([InlineKeyboardButton("\U0001f3af  G\u00e1n acc cho user", callback_data="assign_menu")])
    return InlineKeyboardMarkup(rows)


def kb_panel(n, f, run):
    def b(k, lb):
        v = f.get(k, False)
        mark = "\U0001f7e2" if v else "\U0001f534"
        return InlineKeyboardButton(mark + " " + lb, callback_data="tog:" + n + ":" + k)
    rb = (InlineKeyboardButton("\u23f9  D\u1eebng farm", callback_data="stop:" + n) if run
          else InlineKeyboardButton("\u25b6\ufe0f  B\u1eaft \u0111\u1ea7u farm", callback_data="start:" + n))
    return InlineKeyboardMarkup([
        [b("mine", "\u0110\u00e0o m\u1ecf"), b("claim", "Thu ho\u1ea1ch")],
        [b("watch", "Xem video"), b("box", "M\u1edf h\u1ed9p")],
        [b("craft", "Gh\u00e9p v\u00e9"), b("spin", "V\u00f2ng quay")],
        [b("exchange", "\u0110\u1ed5i VND"), b("upgrade", "N\u00e2ng c\u1ea5p")],
        [rb],
        [InlineKeyboardButton("\U0001f4b0  R\u00fat ti\u1ec1n", callback_data="wd:" + n),
         InlineKeyboardButton("\u2b06\ufe0f  N\u00e2ng c\u1ea5p", callback_data="up:" + n)],
        [InlineKeyboardButton("\U0001f504  L\u00e0m m\u1edbi", callback_data="rf:" + n),
         InlineKeyboardButton("\U0001f519  Quay l\u1ea1i", callback_data="menu")],
    ])

def panel_text(n):
    a = ACCS.get(n, {}); u = a.get("user", {})
    try: run = n in WORKERS and not WORKERS[n].done()
    except: run = False
    st = "\U0001f7e2 <b>\u0110ANG CH\u1ea0Y</b>" if run else "\U0001f534 <b>\u0110ANG D\u1eeaNG</b>"
    s = a.get("stats", {})
    if u.get("_error"):
        err_line = "\u26a0\ufe0f <b>L\u1ed6I:</b> " + str(u["_error"])[:100] + "\n\n"
    else:
        err_line = ""
    return (
        "\U0001f464 <b>" + n.upper() + "</b>\n"
        "\U0001f4f1 " + str(a.get("phone", "?")) + "\n"
        "\U0001f194 @" + str(u.get("username", "?")) + "\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\U0001f4b0 D\u1ea7u: <b>" + fmt(u.get("oil_balance", 0)) + "</b>\n"
        "\U0001f4b5 VND: <b>" + str(u.get("vnd_balance", 0)) + "</b>\n"
        "\u26a1 T\u1ed1c \u0111\u1ed9: <b>" + str(u.get("speed_lvl", 0)) + "</b>   "
        "\U0001f4e6 S\u1ee9c ch\u1ee9a: <b>" + str(u.get("capacity_lvl", 0)) + "</b>\n"
        "\U0001f3ab V\u00e9: <b>" + str(u.get("tickets", 0)) + "</b>   "
        "\U0001f48e M\u1ea3nh: <b>" + str(u.get("shards", 0)) + "</b>   "
        "\U0001f381 H\u1ed9p: <b>" + str(u.get("mystery_boxes", 0)) + "</b>\n" +
        err_line +
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n" + st + "\n"
        "<i>\U0001f4ca " + str(s.get("claim", 0)) + " thu \u00b7 "
        + str(s.get("watch", 0)) + " video \u00b7 "
        + str(s.get("box", 0)) + " h\u1ed9p \u00b7 "
        + str(s.get("spin", 0)) + " quay \u00b7 "
        + str(s.get("exchange", 0)) + " \u0111\u1ed5i \u00b7 "
        + str(s.get("redeem", 0)) + " code</i>"
    )

async def edit_msg(q, txt, kb):
    m = q.message
    try:
        if m.animation or m.photo:
            await q.edit_message_caption(caption=txt, parse_mode=ParseMode.HTML, reply_markup=kb)
            return
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception as e:
        if "message is not modified" in str(e): return
        try:
            if GIF_URL:
                await q.get_bot().send_animation(q.message.chat_id, GIF_URL,
                    caption=txt, parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await q.get_bot().send_message(q.message.chat_id, txt,
                    parse_mode=ParseMode.HTML, reply_markup=kb)
        except: pass



async def cb_assign_menu(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer()
    rows = []
    for uid in list(APPROVED):
        meta = USER_META.get(str(uid), {})
        cnt = len([n for n, a in ACCS.items() if a.get("assigned_to") == uid])
        rows.append([InlineKeyboardButton(
            "\U0001f464 @" + (meta.get("username") or str(uid)) + "  (" + str(cnt) + " acc)",
            callback_data="assign_user:" + str(uid))])
    if not rows:
        rows.append([InlineKeyboardButton("Ch\u01b0a c\u00f3 user duy\u1ec7t", callback_data="menu")])
    rows.append([InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="menu")])
    await edit_msg(q, "\U0001f3af <b>G\u00c1N ACC CHO USER</b>\n\nCh\u1ecdn user \u0111\u1ec3 g\u00e1n/thu h\u1ed3i:", InlineKeyboardMarkup(rows))

async def cb_assign_user(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer()
    try: uid = int(q.data.split(":", 1)[1])
    except: await q.answer("L\u1ed7i"); return
    meta = USER_META.get(str(uid), {})
    assigned = [n for n, a in ACCS.items() if a.get("assigned_to") == uid]
    pool = [n for n, a in ACCS.items() if not a.get("assigned_to")]
    txt = ("<b>G\u00c1N ACC CHO " + str(uid) + "</b>\n"
           "@" + (meta.get("username") or "?") + "\n"
           "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
           "\u0110\u00e3 g\u00e1n: " + str(len(assigned)) + "\n"
           "Acc admin pool: " + str(len(pool)) + "\n\n")
    if assigned:
        txt += "<b>Acc \u0111ang g\u00e1n:</b>\n"
    rows = []
    for n in assigned:
        rows.append([InlineKeyboardButton("\u274c Thu h\u1ed3i: " + n, callback_data="unassign:" + str(uid) + ":" + n)])
    if pool:
        txt += "\n<b>Ch\u1ecdn acc t\u1eeb pool \u0111\u1ec3 g\u00e1n:</b>\n"
        for n in pool[:15]:
            rows.append([InlineKeyboardButton("\u2795 " + n, callback_data="assign:" + str(uid) + ":" + n)])
    rows.append([InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="assign_menu")])
    await edit_msg(q, txt, InlineKeyboardMarkup(rows))

async def cb_assign(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    parts = q.data.split(":", 2)
    try: uid = int(parts[1])
    except: await q.answer("L\u1ed7i"); return
    name = parts[2]
    if name not in ACCS: await q.answer("Kh\u00f4ng t\u00ecm th\u1ea5y acc"); return
    ACCS[name]["assigned_to"] = uid
    _save(ACC_FILE, ACCS)
    await q.answer("\u0110\u00e3 g\u00e1n " + name + " cho " + str(uid), show_alert=True)
    try: await c.bot.send_message(uid, "\U0001f3af Admin \u0111\u00e3 g\u00e1n acc <b>" + name + "</b> cho b\u1ea1n", parse_mode=ParseMode.HTML)
    except: pass
    await cb_assign_user(u, c)

async def cb_unassign(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    parts = q.data.split(":", 2)
    try: uid = int(parts[1])
    except: await q.answer("L\u1ed7i"); return
    name = parts[2]
    if name not in ACCS: await q.answer("Kh\u00f4ng t\u00ecm th\u1ea5y acc"); return
    ACCS[name].pop("assigned_to", None)
    _save(ACC_FILE, ACCS)
    await q.answer("\u0110\u00e3 thu h\u1ed3i " + name, show_alert=True)
    await cb_assign_user(u, c)

# Upload file .txt de add nhieu acc
async def cmd_addacc(u, c):
    if not is_admin(u.effective_user.id):
        await u.message.reply_text("Kh\u00f4ng c\u00f3 quy\u1ec1n"); return
    AS_STATE[u.effective_user.id] = {"step": "file"}
    await u.message.reply_text(
        "\U0001f4c1 <b>TH\u00caM ACC T\u1eea FILE</b>\n\n"
        "G\u1eedi file .txt v\u1edbi format m\u1ed7i acc 3 d\u00f2ng:\n"
        "<code>T\u00ean\nS\u0110T\nSession_string</code>\n\n"
        "C\u00e1c acc c\u00e1ch nhau 1 d\u00f2ng tr\u1ed1ng.\n\n"
        "VD:\n"
        "<code>ACC1\n+84999999999\n1BVtsOIcBu7ViVQ...</code>\n\n"
        "<code>ACC2\n+84988888888\n1BVtsOIcBu5f...</code>",
        parse_mode=ParseMode.HTML)

async def handle_doc(u, c):
    uid = u.effective_user.id
    if not is_admin(uid): return
    st = AS_STATE.get(uid)
    if not st or st.get("step") != "file":
        return
    try: await u.message.delete()
    except: pass
    doc = u.message.document
    if not doc.file_name.lower().endswith(".txt"):
        await u.message.reply_text("Ch\u1ec9 nh\u1eadn file .txt"); return
    m = await u.message.reply_text("\u0110ang t\u1ea3i file...")
    try:
        f = await doc.get_file()
        data = await f.download_as_bytearray()
        text = data.decode("utf-8")
    except Exception as e:
        await m.edit_text("\u2717 Kh\u00f4ng \u0111\u1ecdc \u0111\u01b0\u1ee3c file: " + str(e)); return

    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    added = 0; failed = 0; details = []
    for b in blocks:
        lines = [l.strip() for l in b.split("\n") if l.strip()]
        if len(lines) < 3:
            failed += 1; details.append("\u2717 Block thi\u1ebfu d\u00f2ng"); continue
        name = lines[0]
        phone = lines[1]
        sess = lines[2]
        if not re.match(r"^[A-Za-z0-9_]{1,20}$", name):
            failed += 1; details.append("\u2717 " + name + ": t\u00ean sai"); continue
        if name in ACCS:
            failed += 1; details.append("\u2717 " + name + ": \u0111\u00e3 t\u1ed3n t\u1ea1i"); continue
        try:
            test = await fetch_initdata(sess)
        except Exception as e:
            failed += 1; details.append("\u2717 " + name + ": session l\u1ed7i"); continue
        if not test:
            failed += 1; details.append("\u2717 " + name + ": session kh\u00f4ng ho\u1ea1t \u0111\u1ed9ng"); continue
        ACCS[name] = {
            "phone": phone, "session_string": sess, "owner": uid,
            "created": datetime.now().isoformat(),
            "flags": {"mine": False, "claim": False, "watch": False, "box": False,
                      "craft": False, "spin": False, "exchange": False, "upgrade": False},
            "user": {}, "stats": {}, "cd": {},
            "init_data": test, "init_ts": time.time(),
        }
        added += 1
        details.append("\u2713 " + name)
    _save(ACC_FILE, ACCS)
    AS_STATE.pop(uid, None)
    out = "\U0001f4c1 <b>K\u1ebeT QU\u1ea2 TH\u00caM FILE</b>\n"
    out += "Th\u00eam: <b>" + str(added) + "</b>\n"
    out += "L\u1ed7i: <b>" + str(failed) + "</b>\n\n"
    out += "\n".join(details[:20])
    await m.edit_text(out, parse_mode=ParseMode.HTML, reply_markup=kb_main(uid))



async def cb_kick_user(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    try: uid = int(q.data.split(":", 1)[1])
    except: await q.answer("L\u1ed7i"); return
    APPROVED.discard(uid); save_approved()
    USER_META.setdefault(str(uid), {})["kicked"] = True
    save_user_meta()
    await q.answer("\u0110\u00e3 kick", show_alert=True)
    try: await c.bot.send_message(uid, "\U0001f6ab B\u1ea1n \u0111\u00e3 b\u1ecb kick kh\u1ecfi bot.")
    except: pass

async def cb_user_detail(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer()
    try: uid = int(q.data.split(":", 1)[1])
    except: await q.answer("L\u1ed7i"); return
    names = [n for n, a in ACCS.items() if a.get("assigned_to") == uid or a.get("owner") == uid]
    meta = USER_META.get(str(uid), {})
    txt = ("<b>\U0001f464 TH\u00d4NG TIN USER</b>\n"
           "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
           "ID: <code>" + str(uid) + "</code>\n"
           "Username: @" + str(meta.get("username") or "?") + "\n"
           "T\u00ean: " + str(meta.get("first_name") or "?") + "\n"
           "Ng\u00e0y tham gia: " + str(meta.get("first_seen") or "?") + "\n"
           "Min ng\u00e0y: " + str(meta.get("min_days") or 0) + "\n"
           "B\u1ecb kick: " + ("C\u00f3" if meta.get("kicked") else "Kh\u00f4ng") + "\n"
           "S\u1ed1 acc g\u00e1n: <b>" + str(len(names)) + "</b>\n")
    if names:
        txt += "\n<i>" + ", ".join(names[:15]) + "</i>"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f4e9 G\u1eedi tin", callback_data="msg_user:" + str(uid))],
        [InlineKeyboardButton("\u23f1 \u0110\u1eb7t min ng\u00e0y", callback_data="set_min:" + str(uid))],
        [InlineKeyboardButton("\U0001f3af G\u00e1n acc", callback_data="assign_user:" + str(uid))],
        [InlineKeyboardButton("\U0001f6ab Kick", callback_data="kick:" + str(uid)),
         InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="users_panel")]])
    await edit_msg(q, txt, kb)

async def cb_msg_user(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer()
    try: uid = int(q.data.split(":", 1)[1])
    except: await q.answer("L\u1ed7i"); return
    BROADCAST_WAIT[u.effective_user.id] = {"target": uid}
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 H\u1ee7y", callback_data="users_panel")]])
    await edit_msg(q, "\U0001f4e9 Nh\u1eadp tin nh\u1eafn g\u1eedi user " + str(uid), kb)

async def cb_set_min(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer()
    try: uid = int(q.data.split(":", 1)[1])
    except: await q.answer("L\u1ed7i"); return
    BROADCAST_WAIT[u.effective_user.id] = {"set_min": uid}
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 H\u1ee7y", callback_data="users_panel")]])
    await edit_msg(q, "\u23f1 Nh\u1eadp s\u1ed1 ng\u00e0y t\u1ed1i thi\u1ec3u (0 = b\u1ecf gi\u1edbi h\u1ea1n):", kb)

async def cb_broadcast_all(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer()
    BROADCAST_WAIT[u.effective_user.id] = {"broadcast": True}
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 H\u1ee7y", callback_data="users_panel")]])
    await edit_msg(q, "\U0001f4e2 Nh\u1eadp tin nh\u1eafn broadcast \u0111\u1ebfn t\u1ea5t c\u1ea3 user \u0111\u00e3 duy\u1ec7t:", kb)

async def _send_broadcast(c, target, text):
    try:
        await c.bot.send_message(target, "\U0001f4e9 <b>Th\u00f4ng b\u00e1o t\u1eeb admin:</b>\n\n" + text, parse_mode=ParseMode.HTML)
        return True
    except: return False

async def broadcast_flow(u, c):
    uid = u.effective_user.id
    st = BROADCAST_WAIT.get(uid)
    if not st: return False
    txt = (u.message.text or "").strip()
    try: await u.message.delete()
    except: pass
    if "target" in st:
        okk = await _send_broadcast(c, st["target"], txt)
        BROADCAST_WAIT.pop(uid, None)
        await u.message.reply_text("\u2705 \u0110\u00e3 g\u1eedi" if okk else "\u2717 G\u1eedi th\u1ea5t b\u1ea1i")
        return True
    if "set_min" in st:
        try: n = int(txt)
        except: await u.message.reply_text("S\u1ed1 nguy\u00ean. Nh\u1eadp l\u1ea1i:"); return True
        tgt = st["set_min"]
        USER_META.setdefault(str(tgt), {})["min_days"] = n
        save_user_meta()
        BROADCAST_WAIT.pop(uid, None)
        await u.message.reply_text("\u2705 \u0110\u00e3 \u0111\u1eb7t min " + str(n) + " ng\u00e0y")
        return True
    if st.get("broadcast"):
        sent = 0; fail = 0
        for a in list(APPROVED):
            if await _send_broadcast(c, a, txt): sent += 1
            else: fail += 1
        BROADCAST_WAIT.pop(uid, None)
        await u.message.reply_text("\u2705 G\u1eedi: " + str(sent) + " - L\u1ed7i: " + str(fail))
        return True
    return False



async def cb_admin_add(u, c):
    q = u.callback_query
    await q.answer()
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    AS_STATE[u.effective_user.id] = {"step": "file"}
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 H\u1ee7y", callback_data="menu")]])
    txt = ("\U0001f4c1 <b>TH\u00caM ACC T\u1eea FILE</b>\n\n"
           "G\u1eedi file .txt v\u1edbi format m\u1ed7i acc 3 d\u00f2ng:\n"
           "<code>T\u00ean\nS\u0110T\nSession_string</code>\n\n"
           "Acc c\u00e1ch nhau 1 d\u00f2ng tr\u1ed1ng.\n\n"
           "VD:\n"
           "<code>ACC1\n+84999999999\n1BVtsOIcBu7ViVQ...</code>\n\n"
           "<code>ACC2\n+84988888888\n1BVtsOIcBu5f...</code>")
    try: await q.edit_message_caption(caption=txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    except:
        try: await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        except: await q.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)



async def cmd_wipe(u, c):
    if not is_admin(u.effective_user.id):
        await u.message.reply_text("Kh\u00f4ng c\u00f3 quy\u1ec1n"); return
    for n in list(WORKERS.keys()):
        try: stop_farm(n)
        except: pass
    ACCS.clear()
    try: _save(ACC_FILE, ACCS)
    except: pass
    await u.message.reply_text(
        "\U0001f9f9 \u0110\u00e3 x\u00f3a s\u1ea1ch <b>" + str(len(ACCS)) + "</b> acc trong runtime.\n"
        "B\u1ea5m /start \u0111\u1ec3 xem l\u1ea1i.",
        parse_mode=ParseMode.HTML)

async def cmd_start(u, c):
    cap = main_caption(u.effective_user.id); kb = kb_main(u.effective_user.id)
    if GIF_URL:
        try:
            await u.message.reply_animation(GIF_URL, caption=cap, parse_mode=ParseMode.HTML, reply_markup=kb)
            return
        except: pass
    await u.message.reply_text(cap, parse_mode=ParseMode.HTML, reply_markup=kb)

async def cmd_share(u, c):
    bi = await c.bot.get_me()
    link = "https://t.me/" + bi.username
    await u.message.reply_text("\U0001f517 <b>CHIA S\u1eba BOT</b>\n\n\U0001f449 " + link,
        parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def cmd_myid(u, c):
    uid = u.effective_user.id
    role = "QU\u1ea2N TR\u1eca VI\u00caN" if is_admin(uid) else ("\u0110\u00c3 DUY\u1ec6T" if uid in APPROVED else "CH\u1edc DUY\u1ec6T")
    await u.message.reply_text("\U0001f194 <b>ID:</b> <code>" + str(uid) + "</code>\n\U0001f464 <b>Vai tr\u00f2:</b> " + role,
        parse_mode=ParseMode.HTML)

async def cb_menu(u, c):
    q = u.callback_query; await q.answer()
    await edit_msg(q, main_caption(u.effective_user.id), kb_main(u.effective_user.id))

async def cb_share_help(u, c):
    q = u.callback_query; await q.answer()
    bi = await c.bot.get_me()
    link = "https://t.me/" + bi.username
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="menu")]])
    await edit_msg(q, "\U0001f517 <b>CHIA S\u1eba BOT</b>\n\n\U0001f449 " + link, kb)

async def cb_myid_help(u, c):
    q = u.callback_query; await q.answer()
    uid = u.effective_user.id
    role = "QU\u1ea2N TR\u1eca VI\u00caN" if is_admin(uid) else ("\u0110\u00c3 DUY\u1ec6T" if uid in APPROVED else "CH\u1edc DUY\u1ec6T")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="menu")]])
    await edit_msg(q, "\U0001f194 <b>ID:</b> <code>" + str(uid) + "</code>\n\U0001f464 <b>Vai tr\u00f2:</b> " + role, kb)

async def cb_panel_list(u, c):
    q = u.callback_query; await q.answer()
    names = user_accs(u.effective_user.id)
    if not names:
        await edit_msg(q, "\U0001f4ed <b>B\u1ea1n ch\u01b0a c\u00f3 t\u00e0i kho\u1ea3n n\u00e0o</b>", kb_main(u.effective_user.id))
        return
    rows = [[InlineKeyboardButton("\U0001f464 " + n, callback_data="panel:" + n)] for n in names]
    rows.append([InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="menu")])
    await edit_msg(q, "\U0001f4cb <b>CH\u1eccN T\u00c0I KHO\u1ea2N</b>", InlineKeyboardMarkup(rows))

async def cb_panel(u, c):
    q = u.callback_query; await q.answer()
    n = q.data.split(":", 1)[1]
    if n not in ACCS:
        await q.answer("Kh\u00f4ng t\u00ecm th\u1ea5y", show_alert=True); return
    if not is_owner(u.effective_user.id, n):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    # Fetch user data neu chua co hoac qua 30s
    a = ACCS[n]
    last = a.get("last_fetch", 0)
    need = (not a.get("user")) or (time.time() - last > 30)
    if need:
        try:
            r = await asyncio.to_thread(api, n, "/api/login")
            if r and r.status_code == 200:
                j = r.json()
                if j.get("success"):
                    a["user"] = j.get("user", {})
                    a["last_fetch"] = time.time()
                    _save(ACC_FILE, ACCS)
                else:
                    if not a.get("user"):
                        a["user"] = {"_error": j.get("error") or j.get("message") or "login fail"}
        except Exception as e:
            print("[panel " + n + "] " + str(e))
    try: run = n in WORKERS and not WORKERS[n].done()
    except: run = False
    await edit_msg(q, panel_text(n), kb_panel(n, ACCS[n].get("flags", {}), run))


async def cb_tog(u, c):
    q = u.callback_query
    _, n, k = q.data.split(":", 2)
    if n not in ACCS or not is_owner(u.effective_user.id, n):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    f = ACCS[n].setdefault("flags", {})
    f[k] = not f.get(k, False); _save(ACC_FILE, ACCS)
    await q.answer(("B\u1eacT " if f[k] else "T\u1eaeT ") + k)
    # Fetch user neu can
    a = ACCS[n]
    if not a.get("user"):
        try:
            r = await asyncio.to_thread(api, n, "/api/login")
            if r and r.status_code == 200:
                j = r.json()
                if j.get("success"):
                    a["user"] = j.get("user", {})
                    a["last_fetch"] = time.time()
                    _save(ACC_FILE, ACCS)
        except: pass
    try: run = n in WORKERS and not WORKERS[n].done()
    except: run = False
    await edit_msg(q, panel_text(n), kb_panel(n, f, run))


async def cb_start_acc(u, c):
    q = u.callback_query; n = q.data.split(":", 1)[1]
    if n not in ACCS or not is_owner(u.effective_user.id, n):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    okk = start_farm(c.application, n)
    await q.answer("\u0110\u00e3 b\u1eadt" if okk else "\u0110ang ch\u1ea1y"); await cb_panel(u, c)

async def cb_stop_acc(u, c):
    q = u.callback_query; n = q.data.split(":", 1)[1]
    if n not in ACCS or not is_owner(u.effective_user.id, n):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    stop_farm(n); await q.answer("\u0110\u00e3 d\u1eebng"); await cb_panel(u, c)

async def cb_start_all(u, c):
    q = u.callback_query; cnt = 0
    for n in user_accs(u.effective_user.id):
        if start_farm(c.application, n): cnt += 1
    await q.answer("\u0110\u00e3 b\u1eadt " + str(cnt), show_alert=True); await cb_menu(u, c)

async def cb_stop_all(u, c):
    q = u.callback_query
    for n in user_accs(u.effective_user.id): stop_farm(n)
    await q.answer("\u0110\u00e3 t\u1eaft t\u1ea5t c\u1ea3", show_alert=True); await cb_menu(u, c)

async def cb_rf_all(u, c):
    q = u.callback_query
    await q.answer("\u0110ang l\u00e0m m\u1edbi...")
    for n in user_accs(u.effective_user.id): await refresh_idata(n)
    await q.answer("Xong", show_alert=True); await cb_menu(u, c)

async def cb_rf(u, c):
    q = u.callback_query; n = q.data.split(":", 1)[1]
    if n not in ACCS or not is_owner(u.effective_user.id, n):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer("\u0110ang l\u00e0m m\u1edbi...")
    okk = await refresh_idata(n)
    await q.answer("OK" if okk else "Th\u1ea5t b\u1ea1i", show_alert=True); await cb_panel(u, c)

async def cb_wd(u, c):
    q = u.callback_query; n = q.data.split(":", 1)[1]
    if n not in ACCS or not is_owner(u.effective_user.id, n):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer()
    WD_WAIT[u.effective_user.id] = n
    a = ACCS.get(n, {}); uu = a.get("user", {})
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 H\u1ee7y", callback_data="panel:" + n)]])
    txt = ("\U0001f4b0 <b>R\u00daT TI\u1ec0N \u2014 " + n.upper() + "</b>\n"
        "\U0001f4b5 VND: <b>" + str(uu.get("vnd_balance", 0)) + "</b>\n"
        "\U0001f3e6 Ng\u00e2n h\u00e0ng: " + str(uu.get("bank_name", "?")) + "\n"
        "\U0001f464 Ch\u1ee7 TK: " + str(uu.get("bank_holder", "?")) + "\n"
        "\U0001f4b3 STK: " + str(uu.get("bank_account", "?")) + "\n\n"
        "<i>G\u1eedi s\u1ed1 VND mu\u1ed1n r\u00fat</i>")
    await edit_msg(q, txt, kb)

async def cb_up(u, c):
    q = u.callback_query; n = q.data.split(":", 1)[1]
    if n not in ACCS or not is_owner(u.effective_user.id, n):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("\u26a1  N\u00e2ng t\u1ed1c \u0111\u1ed9", callback_data="upgo:" + n + ":speed")],
        [InlineKeyboardButton("\U0001f4e6  N\u00e2ng s\u1ee9c ch\u1ee9a", callback_data="upgo:" + n + ":capacity")],
        [InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="panel:" + n)]])
    await edit_msg(q, "\u2b06\ufe0f <b>N\u00c2NG C\u1ea4P \u2014 " + n.upper() + "</b>", kb)

async def cb_upgo(u, c):
    q = u.callback_query; _, n, t = q.data.split(":", 2)
    if n not in ACCS or not is_owner(u.effective_user.id, n):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer("\u0110ang n\u00e2ng c\u1ea5p...")
    r = await asyncio.to_thread(api, n, "/api/upgrade", {"type": t})
    if r and r.status_code == 200:
        try:
            j = r.json()
            if j.get("success"):
                ACCS[n]["user"] = j.get("user", {}); _save(ACC_FILE, ACCS)
                await q.answer("\u2713 " + str(j.get("message")), show_alert=True)
            else:
                await q.answer("\u2717 " + str(j.get("error") or j.get("message")), show_alert=True)
        except: pass
    await cb_panel(u, c)

async def cb_del_list(u, c):
    q = u.callback_query; await q.answer()
    names = user_accs(u.effective_user.id)
    if not names:
        await q.answer("B\u1ea1n ch\u01b0a c\u00f3 t\u00e0i kho\u1ea3n n\u00e0o", show_alert=True); return
    rows = [[InlineKeyboardButton("\U0001f5d1 " + n, callback_data="del:" + n)] for n in names]
    rows.append([InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="menu")])
    await edit_msg(q, "\U0001f5d1 <b>CH\u1eccN T\u00c0I KHO\u1ea2N \u0110\u1ec2 X\u00d3A</b>", InlineKeyboardMarkup(rows))

async def cb_del(u, c):
    q = u.callback_query; n = q.data.split(":", 1)[1]
    if n not in ACCS or not is_owner(u.effective_user.id, n):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    if n in WORKERS: stop_farm(n)
    ACCS.pop(n, None); _save(ACC_FILE, ACCS)
    await q.answer("\u0110\u00e3 x\u00f3a " + n, show_alert=True); await cb_menu(u, c)

async def cb_live(u, c):
    q = u.callback_query; await q.answer()
    uid = u.effective_user.id
    names = user_accs(uid)
    lines = ["\U0001f4ca <b>XEM TR\u1ef0C TI\u1ebeP</b>", "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"]
    any_run = False
    for nm in names:
        t = WORKERS.get(nm)
        if not t: continue
        try:
            if t.done(): continue
        except: continue
        any_run = True
        a = ACCS.get(nm, {}); uu = a.get("user", {}); s = a.get("stats", {})
        lines.append("")
        lines.append("\U0001f7e2 <b>" + nm + "</b>")
        lines.append("\U0001f4b0 " + fmt(uu.get("oil_balance", 0)) + " d\u1ea7u \u00b7 \U0001f4b5 " + str(uu.get("vnd_balance", 0)) + " VND")
        lines.append("\U0001f4ca " + str(s.get("claim", 0)) + " thu \u00b7 " + str(s.get("watch", 0)) + " video \u00b7 " + str(s.get("box", 0)) + " h\u1ed9p")
    if not any_run:
        lines.append("")
        lines.append("<i>Ch\u01b0a c\u00f3 t\u00e0i kho\u1ea3n n\u00e0o \u0111ang farm</i>")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f504 L\u00e0m m\u1edbi", callback_data="live"),
                                 InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="menu")]])
    await edit_msg(q, "\n".join(lines), kb)
async def cb_code_menu(u, c):
    q = u.callback_query; await q.answer()
    uid = u.effective_user.id
    names = user_accs(uid)
    pending = 0
    for code, accs in REDEEMED.items():
        for n in names:
            if n not in accs:
                pending += 1; break
    txt = ("\U0001f4dc <b>QU\u1ea2N L\u00dd CODE</b>\n"
           "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
           "T\u1ed5ng code: <b>" + str(len(REDEEMED)) + "</b>\n"
           "Acc c\u1ee7a b\u1ea1n: <b>" + str(len(names)) + "</b>\n"
           "Code ch\u01b0a nh\u1eadp h\u1ebft: <b>" + str(pending) + "</b>\n"
           "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n")
    recent = list(REDEEMED.items())[-15:]
    if recent:
        txt += "\n<b>15 code g\u1ea7n nh\u1ea5t:</b>\n"
        for code, accs in reversed(recent):
            txt += "<code>" + code + "</code> \u2192 " + str(len(accs)) + " acc\n"
    else:
        txt += "\n<i>Ch\u01b0a c\u00f3 code n\u00e0o</i>"
    try: on = bool(WATCH and not WATCH.done())
    except: on = False
    wlabel = "\u23f9 T\u1eaft theo d\u00f5i" if on else "\u25b6\ufe0f B\u1eadt theo d\u00f5i"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(wlabel, callback_data="code_tog")],
        [InlineKeyboardButton("\U0001f50d Qu\u00e9t l\u1ea1i to\u00e0n b\u1ed9 nh\u00f3m", callback_data="scan_hist")],
        [InlineKeyboardButton("\U0001f504 Nh\u1eadp l\u1ea1i code c\u00f2n thi\u1ebfu", callback_data="code_retry")],
        [InlineKeyboardButton("\U0001f4e4 Xu\u1ea5t backup", callback_data="code_export")],
        [InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="menu")],
    ])
    await edit_msg(q, txt, kb)

async def cb_code_tog(u, c):
    global WATCH
    q = u.callback_query
    if WATCH and not WATCH.done():
        WATCH.cancel(); WATCH = None
        await q.answer("\u0110\u00e3 T\u1eaeT theo d\u00f5i code", show_alert=True)
    else:
        if not _admin_session_acc():
            await q.answer("C\u1ea7n session admin \u0111\u1ec3 theo d\u00f5i", show_alert=True); return
        try:
            WATCH = asyncio.create_task(watcher_loop(c.application))
            await q.answer("\u0110\u00e3 B\u1eacT theo d\u00f5i code", show_alert=True)
        except Exception as e:
            await q.answer("L\u1ed7i: " + str(e), show_alert=True)
    await cb_code_menu(u, c)

async def cb_code_retry(u, c):
    q = u.callback_query
    await q.answer("\u0110ang th\u1eed l\u1ea1i...")
    names = user_accs(u.effective_user.id)
    if not names:
        await q.answer("Ch\u01b0a c\u00f3 acc", show_alert=True); return
    ok_n = 0; fail_n = 0; tried = 0
    for code, accs in list(REDEEMED.items()):
        for n in names:
            if n in accs: continue
            tried += 1
            try:
                r = await asyncio.to_thread(api, n, "/api/redeem-code", {"code": code})
                if r and r.status_code == 200:
                    j = r.json()
                    if j.get("success"):
                        accs.append(n); _save(CODE_FILE, REDEEMED)
                        st = ACCS[n].setdefault("stats", {})
                        st["redeem"] = st.get("redeem", 0) + 1
                        _save(ACC_FILE, ACCS)
                        ok_n += 1
                    else: fail_n += 1
                else: fail_n += 1
            except: fail_n += 1
    await q.answer("Th\u1eed " + str(tried) + " - OK " + str(ok_n) + " - L\u1ed7i " + str(fail_n), show_alert=True)
    await cb_code_menu(u, c)

async def cb_code_export(u, c):
    q = u.callback_query; await q.answer("\u0110ang t\u1ea1o...")
    data = json.dumps(REDEEMED, indent=2, ensure_ascii=False)
    bio = io.BytesIO(data.encode("utf-8"))
    bio.name = "codes_backup.json"
    try:
        await c.bot.send_document(q.message.chat_id, bio, caption="\U0001f4e4 Backup codes")
    except Exception as e:
        await q.answer("L\u1ed7i: " + str(e), show_alert=True)

async def cmd_codes(u, c):
    names = user_accs(u.effective_user.id)
    if not REDEEMED:
        await u.message.reply_text("Ch\u01b0a c\u00f3 code n\u00e0o"); return
    lines = ["\U0001f4dc L\u1ecaCH S\u1eec CODE", "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501", ""]
    for code, accs in list(REDEEMED.items())[-30:]:
        chua = [n for n in names if n not in accs]
        mk = "" if not chua else "  (c\u00f2n " + str(len(chua)) + " acc)"
        lines.append(code + " \u2192 " + str(len(accs)) + " acc" + mk)
    await u.message.reply_text("\n".join(lines))

async def cmd_redeem(u, c):
    parts = (u.message.text or "").strip().split(" ", 1)
    if len(parts) < 2:
        await u.message.reply_text("C\u00fa ph\u00e1p: /redeem VUADAUMO_XXXXX"); return
    code = parts[1].strip().upper()
    if not re.match(r"^VUADAUMO_[A-Z0-9]{5,}$", code):
        await u.message.reply_text("Format sai"); return
    names = user_accs(u.effective_user.id)
    if not names:
        await u.message.reply_text("Ch\u01b0a c\u00f3 acc"); return
    already = REDEEMED.setdefault(code, [])
    todo = [n for n in names if n not in already]
    if not todo:
        await u.message.reply_text("T\u1ea5t c\u1ea3 acc \u0111\u00e3 nh\u1eadp code n\u00e0y"); return
    msg = await u.message.reply_text("\u0110ang nh\u1eadp " + code + " cho " + str(len(todo)) + " acc...")
    ok_n = 0; fail_n = 0
    for n in todo:
        try:
            r = await asyncio.to_thread(api, n, "/api/redeem-code", {"code": code})
            if r and r.status_code == 200:
                j = r.json()
                if j.get("success"):
                    already.append(n); _save(CODE_FILE, REDEEMED)
                    st = ACCS[n].setdefault("stats", {})
                    st["redeem"] = st.get("redeem", 0) + 1
                    _save(ACC_FILE, ACCS)
                    ok_n += 1
                else: fail_n += 1
            else: fail_n += 1
        except: fail_n += 1
    await msg.edit_text("\u2713 OK " + str(ok_n) + " / \u2717 L\u1ed7i " + str(fail_n), reply_markup=kb_main(u.effective_user.id))

async def cb_scan(u, c):
    q = u.callback_query
    await q.answer("\u0110ang qu\u00e9t...")
    uid = u.effective_user.id
    names = user_accs(uid)
    if not names:
        await q.answer("Ch\u01b0a c\u00f3 acc", show_alert=True); return
    if not _admin_session_acc():
        await q.answer("C\u1ea7n session admin", show_alert=True); return
    status = await c.bot.send_message(q.message.chat_id, "\U0001f50d \u0110ang qu\u00e9t l\u1ecbch s\u1eed 2 nh\u00f3m...")
    try:
        found = await scan_history(limit=800)
    except Exception as e:
        await status.edit_text("L\u1ed7i: " + str(e)); return
    total = len(found)
    new_r = 0; fail = 0; already_n = 0
    for code in found:
        REDEEMED.setdefault(code, [])
    for name in names:
        for code in found:
            if name in REDEEMED[code]:
                already_n += 1; continue
            try:
                r = await asyncio.to_thread(api, name, "/api/redeem-code", {"code": code})
                if r and r.status_code == 200:
                    j = r.json()
                    if j.get("success"):
                        REDEEMED[code].append(name); new_r += 1
                    else: fail += 1
                else: fail += 1
            except: fail += 1
    _save(CODE_FILE, REDEEMED)
    lines = ["<b>\U0001f4ca K\u1ebeT QU\u1ea2 QU\u00c9T</b>",
             "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
             "K\u00eanh: " + ", ".join(CHANNELS),
             "T\u00ecm th\u1ea5y: <b>" + str(total) + "</b> code",
             "Nh\u1eadp m\u1edbi: <b>" + str(new_r) + "</b>",
             "\u0110\u00e3 nh\u1eadp tr\u01b0\u1edbc: <b>" + str(already_n) + "</b>",
             "L\u1ed7i: <b>" + str(fail) + "</b>",
             "",
             "<b>Chi ti\u1ebft t\u1eebng acc:</b>"]
    for name in names:
        ok_n = sum(1 for c_ in found if name in REDEEMED.get(c_, []))
        miss = total - ok_n
        lines.append("\U0001f464 " + name + ": " + str(ok_n) + "/" + str(total) + " (" + str(miss) + " ch\u01b0a)")
    await status.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)

async def approval_gate(u, c):
    if not u.effective_user: return
    uid = u.effective_user.id
    if is_approved(uid): return
    if u.callback_query:
        try: await u.callback_query.answer("T\u00e0i kho\u1ea3n ch\u01b0a \u0111\u01b0\u1ee3c duy\u1ec7t", show_alert=True)
        except: pass
    else:
        try: await u.message.reply_text("\U0001f512 T\u00e0i kho\u1ea3n c\u1ee7a b\u1ea1n \u0111ang ch\u1edd admin duy\u1ec7t.")
        except: pass
    if uid not in PENDING_USERS and ADMINS:
        PENDING_USERS[uid] = {
            "username": u.effective_user.username or "",
            "first_name": u.effective_user.first_name or "",
        }
        txt = ("<b>\U0001f514 Y\u00caU C\u1ea6U TRUY C\u1eacP M\u1edaI</b>\n\n"
               "ID: <code>" + str(uid) + "</code>\n"
               "T\u00ean: " + (u.effective_user.first_name or "") + "\n"
               "Username: @" + (u.effective_user.username or "kh\u00f4ng c\u00f3"))
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("\u2705 Duy\u1ec7t", callback_data="appr_ok:" + str(uid)),
            InlineKeyboardButton("\u274c T\u1eeb ch\u1ed1i", callback_data="appr_no:" + str(uid))]])
        for a in ADMINS:
            try: await c.bot.send_message(a, txt, parse_mode=ParseMode.HTML, reply_markup=kb)
            except: pass
    raise ApplicationHandlerStop

async def cb_appr_ok(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    try: uid = int(q.data.split(":", 1)[1])
    except: await q.answer("L\u1ed7i"); return
    APPROVED.add(uid); save_approved()
    if str(uid) not in USER_META:
        info = PENDING_USERS.get(uid, {})
        USER_META[str(uid)] = {"first_seen": datetime.now().isoformat(),
            "username": info.get("username", ""), "first_name": info.get("first_name", "")}
        save_user_meta()
    await q.answer("\u0110\u00e3 duy\u1ec7t")
    try: await q.edit_message_text("\u2705 \u0110\u00e3 DUY\u1ec6T user " + str(uid))
    except: pass
    try: await c.bot.send_message(uid, "\u2705 T\u00e0i kho\u1ea3n \u0111\u00e3 \u0111\u01b0\u1ee3c duy\u1ec7t. G\u00f5 /start.")
    except: pass

async def cb_appr_no(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    try: uid = int(q.data.split(":", 1)[1])
    except: await q.answer("L\u1ed7i"); return
    APPROVED.discard(uid); save_approved()
    await q.answer("\u0110\u00e3 t\u1eeb ch\u1ed1i")
    try: await q.edit_message_text("\u274c \u0110\u00e3 T\u1eea CH\u1ed0I user " + str(uid))
    except: pass

async def cmd_approve(u, c):
    if not is_admin(u.effective_user.id):
        await u.message.reply_text("Kh\u00f4ng c\u00f3 quy\u1ec1n"); return
    parts = (u.message.text or "").split()
    if len(parts) < 2:
        await u.message.reply_text("C\u00fa ph\u00e1p: /approve ID"); return
    try: uid = int(parts[1])
    except: await u.message.reply_text("ID ph\u1ea3i l\u00e0 s\u1ed1"); return
    APPROVED.add(uid); save_approved()
    await u.message.reply_text("\u0110\u00e3 duy\u1ec7t " + str(uid))
    try: await c.bot.send_message(uid, "\u2705 T\u00e0i kho\u1ea3n \u0111\u00e3 \u0111\u01b0\u1ee3c duy\u1ec7t. G\u00f5 /start.")
    except: pass

async def cmd_reject(u, c):
    if not is_admin(u.effective_user.id):
        await u.message.reply_text("Kh\u00f4ng c\u00f3 quy\u1ec1n"); return
    parts = (u.message.text or "").split()
    if len(parts) < 2:
        await u.message.reply_text("C\u00fa ph\u00e1p: /reject ID"); return
    try: uid = int(parts[1])
    except: await u.message.reply_text("ID ph\u1ea3i l\u00e0 s\u1ed1"); return
    APPROVED.discard(uid); save_approved()
    await u.message.reply_text("\u0110\u00e3 t\u1eeb ch\u1ed1i " + str(uid))

async def cb_users_panel(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer()
    pending = [uid for uid in PENDING_USERS if uid not in APPROVED]
    approved_list = list(APPROVED)
    txt = ("<b>\U0001f465 QU\u1ea2N L\u00dd NG\u01af\u1edcI D\u00d9NG</b>\n"
           "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
           "\u0110\u00e3 duy\u1ec7t: <b>" + str(len(approved_list)) + "</b>\n"
           "Ch\u1edd duy\u1ec7t: <b>" + str(len(pending)) + "</b>\n\n"
           "<i>B\u1ea5m v\u00e0o user \u0111\u1ec3 xem chi ti\u1ebft</i>")
    rows = []
    for uid in approved_list[:15]:
        meta = USER_META.get(str(uid), {})
        cnt = len([n for n, a in ACCS.items() if a.get("assigned_to") == uid or a.get("owner") == uid])
        rows.append([InlineKeyboardButton(
            "\U0001f464 @" + (meta.get("username") or str(uid)) + "  (" + str(cnt) + " acc)",
            callback_data="udetail:" + str(uid))])
    if pending:
        rows.append([InlineKeyboardButton("\U0001f514 " + str(len(pending)) + " user ch\u1edd duy\u1ec7t", callback_data="pending_list")])
    rows.append([InlineKeyboardButton("\U0001f4e2 Broadcast t\u1ea5t c\u1ea3", callback_data="broadcast_all")])
    rows.append([InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="menu")])
    await edit_msg(q, txt, InlineKeyboardMarkup(rows))

async def cb_pending_list(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    await q.answer()
    pending = [uid for uid in PENDING_USERS if uid not in APPROVED]
    if not pending:
        await edit_msg(q, "Kh\u00f4ng c\u00f3 user ch\u1edd duy\u1ec7t", InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="users_panel")]])); return
    rows = []
    for uid in pending[:20]:
        info = PENDING_USERS[uid]
        rows.append([
            InlineKeyboardButton("\u2705 " + str(uid) + " @" + (info.get("username") or "?"), callback_data="appr_ok:" + str(uid)),
            InlineKeyboardButton("\u274c", callback_data="appr_no:" + str(uid))])
    rows.append([InlineKeyboardButton("\u2705 Duy\u1ec7t t\u1ea5t c\u1ea3", callback_data="appr_all")])
    rows.append([InlineKeyboardButton("\U0001f519 Quay l\u1ea1i", callback_data="users_panel")])
    await edit_msg(q, "\U0001f514 <b>" + str(len(pending)) + " user ch\u1edd duy\u1ec7t</b>", InlineKeyboardMarkup(rows))


async def cb_appr_all(u, c):
    q = u.callback_query
    if not is_admin(u.effective_user.id):
        await q.answer("Kh\u00f4ng c\u00f3 quy\u1ec1n", show_alert=True); return
    n = 0
    for uid in list(PENDING_USERS.keys()):
        if uid not in APPROVED:
            APPROVED.add(uid); n += 1
            try: await c.bot.send_message(uid, "\u2705 T\u00e0i kho\u1ea3n \u0111\u00e3 \u0111\u01b0\u1ee3c duy\u1ec7t. G\u00f5 /start.")
            except: pass
    save_approved()
    await q.answer("\u0110\u00e3 duy\u1ec7t " + str(n) + " ng\u01b0\u1eddi", show_alert=True)
    await cb_users_panel(u, c)

async def cb_add_session(u, c):
    q = u.callback_query
    await q.answer()
    uid = u.effective_user.id
    AS_STATE[uid] = {"step": "name", "name": None, "phone": None}
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 H\u1ee7y", callback_data="menu")]])
    txt = ("\U0001f511 <b>TH\u00caM ACC B\u1eb0NG SESSION</b>\n\n"
           "B\u01b0\u1edbc 1/3: Nh\u1eadp <b>t\u00ean acc</b> (vd: FOX)")
    try: await q.edit_message_caption(caption=txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    except:
        try: await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        except: await q.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

async def cmd_addsession(u, c):
    uid = u.effective_user.id
    AS_STATE[uid] = {"step": "name", "name": None, "phone": None}
    await u.message.reply_text(
        "\U0001f511 <b>TH\u00caM ACC B\u1eb0NG SESSION</b>\n\n"
        "B\u01b0\u1edbc 1/3: Nh\u1eadp <b>t\u00ean acc</b> (vd: FOX)",
        parse_mode=ParseMode.HTML)

async def add_session_flow(u, c):
    uid = u.effective_user.id
    st = AS_STATE.get(uid)
    if not st: return False
    txt = (u.message.text or "").strip()
    try: await u.message.delete()
    except: pass
    step = st.get("step")
    if step == "name":
        if not txt or not re.match(r"^[A-Za-z0-9_]{1,20}$", txt):
            await u.message.reply_text("T\u00ean ch\u1ec9 g\u1ed3m ch\u1eef/s\u1ed1/g\u1ea1ch d\u01b0\u1edbi (1-20). Nh\u1eadp l\u1ea1i:")
            return True
        if txt in ACCS:
            await u.message.reply_text("T\u00ean \u0111\u00e3 t\u1ed3n t\u1ea1i. Nh\u1eadp t\u00ean kh\u00e1c:")
            return True
        st["name"] = txt
        st["step"] = "phone"
        await u.message.reply_text("\U0001f4f1 B\u01b0\u1edbc 2/3: Nh\u1eadp <b>S\u0110T</b> (+84...):", parse_mode=ParseMode.HTML)
        return True
    if step == "phone":
        p_clean = txt.replace(" ", "").replace("-", "")
        if not p_clean.startswith("+") or not p_clean[1:].isdigit() or len(p_clean) < 10:
            await u.message.reply_text("S\u0110T ph\u1ea3i d\u1ea1ng +84xxxxxxxxx. Nh\u1eadp l\u1ea1i:")
            return True
        st["phone"] = p_clean
        st["step"] = "sess"
        msg = ("\U0001f4cb B\u01b0\u1edbc 3/3: Paste <b>session string</b> v\u00e0o \u0111\u00e2y.\n\n"
               "<i>L\u1ea5y session b\u1eb1ng get_session.py tr\u00ean m\u00e1y t\u00ednh. Chu\u1ed7i b\u1eaft \u0111\u1ea7u 1BV...</i>\n\n"
               "Bot s\u1ebd X\u00d3A tin n\u00e0y sau khi l\u01b0u. G\u00f5 /cancel \u0111\u1ec3 h\u1ee7y.")
        await u.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return True
    if step == "sess":
        if not txt or len(txt) < 100:
            await u.message.reply_text("Session qu\u00e1 ng\u1eafn (>100 k\u00fd t\u1ef1). Nh\u1eadp l\u1ea1i:")
            return True
        name = st.get("name"); phone = st.get("phone")
        m = await u.message.reply_text("\u0110ang ki\u1ec3m tra session...")
        try: test = await fetch_initdata(txt)
        except: test = None
        if not test:
            await m.edit_text("Session kh\u00f4ng ho\u1ea1t \u0111\u1ed9ng. Nh\u1eadp l\u1ea1i ho\u1eb7c /cancel:")
            return True
        ACCS[name] = {
            "phone": phone, "session_string": txt, "owner": uid,
            "created": datetime.now().isoformat(),
            "flags": {"mine": False, "claim": False, "watch": False, "box": False,
                      "craft": False, "spin": False, "exchange": False, "upgrade": False},
            "user": {}, "stats": {}, "cd": {},
            "init_data": test, "init_ts": time.time(),
        }
        _save(ACC_FILE, ACCS)
        AS_STATE.pop(uid, None)
        done = ("\u2705 \u0110\u00e3 th\u00eam acc <b>" + name + "</b>\n\n"
                "S\u0110T: " + phone + "\nInit data: OK")
        await m.edit_text(done, parse_mode=ParseMode.HTML, reply_markup=kb_main(uid))
        return True
    return False

async def cmd_cancel_addsession(u, c):
    uid = u.effective_user.id
    AS_STATE.pop(uid, None)
    OTP_STATE.pop(uid, None)
    WD_WAIT.pop(uid, None)
    p = PEND.pop(uid, None)
    if p:
        try: await p["client"].disconnect()
        except: pass
    await u.message.reply_text("H\u1ee7y.")

async def handle_text(u, c):
    if u.effective_user.id in AS_STATE:
        if await add_session_flow(u, c): return
    if u.effective_user.id in OTP_STATE:
        if await otp_flow(u, c): return
    if u.effective_user.id in BROADCAST_WAIT:
        if await broadcast_flow(u, c): return
    n = WD_WAIT.pop(u.effective_user.id, None)
    if not n:
        return
    try: amt = float(u.message.text.strip().replace(",", "").replace(".", ""))
    except: await u.message.reply_text("S\u1ed1 kh\u00f4ng h\u1ee3p l\u1ec7."); return
    r = await asyncio.to_thread(api, n, "/api/withdraw", {"amount": amt})
    if r and r.status_code == 200:
        try:
            j = r.json()
            if j.get("success"): await u.message.reply_text("\u2705 " + str(j.get("message")), reply_markup=kb_main(u.effective_user.id))
            else: await u.message.reply_text("\u2717 " + str(j.get("error") or j.get("message")), reply_markup=kb_main(u.effective_user.id))
        except: await u.message.reply_text(r.text[:200], reply_markup=kb_main(u.effective_user.id))
    else:
        await u.message.reply_text("G\u1eedi l\u1ec7nh th\u1ea5t b\u1ea1i.", reply_markup=kb_main(u.effective_user.id))

async def cmd_add_otp(u, c):
    uid = u.effective_user.id
    OTP_STATE[uid] = {"step": "name", "name": None, "phone": None, "client": None, "hash": None}
    await u.message.reply_text(
        "\u2795 <b>TH\u00caM ACC B\u1eb0NG OTP</b>\n\n"
        "B\u01b0\u1edbc 1/3: Nh\u1eadp <b>t\u00ean acc</b> (vd: FOX)",
        parse_mode=ParseMode.HTML)

async def otp_flow(u, c):
    uid = u.effective_user.id
    st = OTP_STATE.get(uid)
    if not st: return False
    txt = (u.message.text or "").strip()
    try: await u.message.delete()
    except: pass
    step = st.get("step")
    if step == "name":
        if not txt or not re.match(r"^[A-Za-z0-9_]{1,20}$", txt):
            await u.message.reply_text("T\u00ean ch\u1ec9 ch\u1eef/s\u1ed1/g\u1ea1ch, 1-20. Nh\u1eadp l\u1ea1i:")
            return True
        if txt in ACCS:
            await u.message.reply_text("T\u00ean t\u1ed3n t\u1ea1i. Nh\u1eadp kh\u00e1c:")
            return True
        st["name"] = txt
        st["step"] = "phone"
        await u.message.reply_text("\U0001f4f1 B\u01b0\u1edbc 2/3: Nh\u1eadp <b>S\u0110T</b> (+84...):", parse_mode=ParseMode.HTML)
        return True
    if step == "phone":
        p_clean = txt.replace(" ", "").replace("-", "")
        if not p_clean.startswith("+") or not p_clean[1:].isdigit() or len(p_clean) < 10:
            await u.message.reply_text("S\u0110T ph\u1ea3i +84xxxxxxxxx. Nh\u1eadp l\u1ea1i:")
            return True
        try:
            cl = TelegramClient(StringSession(), API_ID, API_HASH)
            await cl.connect()
            sent = await cl.send_code_request(p_clean)
        except Exception as e:
            await u.message.reply_text("\u2717 L\u1ed7i: " + str(e)); return True
        st["phone"] = p_clean
        st["client"] = cl
        st["hash"] = sent.phone_code_hash
        st["step"] = "otp"
        await u.message.reply_text("\U0001f4e8 OTP \u0111\u00e3 g\u1eedi (app Telegram ho\u1eb7c SMS). Nh\u1eadp OTP:")
        return True
    if step == "otp":
        try:
            await st["client"].sign_in(phone=st["phone"], code=txt, phone_code_hash=st["hash"])
        except SessionPasswordNeededError:
            st["step"] = "pwd"
            await u.message.reply_text("\U0001f510 C\u00f3 2FA. Nh\u1eadp m\u1eadt kh\u1ea9u:")
            return True
        except Exception as e:
            await u.message.reply_text("\u2717 " + str(e) + "\n\nNh\u1eadp l\u1ea1i OTP:")
            return True
        return await _finalize_otp(u, c)
    if step == "pwd":
        try:
            await st["client"].sign_in(password=txt)
        except Exception as e:
            await u.message.reply_text("\u2717 " + str(e) + "\n\nNh\u1eadp l\u1ea1i m\u1eadt kh\u1ea9u:")
            return True
        return await _finalize_otp(u, c)
    return True

async def _finalize_otp(u, c):
    uid = u.effective_user.id
    st = OTP_STATE.get(uid)
    if not st: return True
    try:
        sess = st["client"].session.save()
        me = await st["client"].get_me()
        await st["client"].disconnect()
    except:
        sess = ""; me = None
    if not sess:
        await u.message.reply_text("\u2717 Kh\u00f4ng l\u1ea5y \u0111\u01b0\u1ee3c session. Th\u1eed l\u1ea1i.")
        OTP_STATE.pop(uid, None)
        return True
    ACCS[st["name"]] = {
        "phone": st["phone"], "session_string": sess, "owner": uid,
        "created": datetime.now().isoformat(),
        "flags": {"mine": False, "claim": False, "watch": False, "box": False,
                  "craft": False, "spin": False, "exchange": False, "upgrade": False},
        "user": {}, "stats": {}, "cd": {},
    }
    _save(ACC_FILE, ACCS)
    OTP_STATE.pop(uid, None)
    uname = me.username if me and me.username else (me.first_name if me else "?")
    m = await u.message.reply_text("\u0110ang l\u1ea5y initData...")
    okk = await refresh_idata(st["name"])
    done = ("\u2705 \u0110\u00e3 th\u00eam <b>" + st["name"] + "</b>\n\n"
            "\U0001f464 @" + str(uname) + "\n"
            "\U0001f4e1 initData: " + ("OK" if okk else "L\u1ed6I"))
    await m.edit_text(done, parse_mode=ParseMode.HTML, reply_markup=kb_main(uid))
    return True

async def cb_add_start(u, c):
    q = u.callback_query
    await q.answer()
    uid = u.effective_user.id
    OTP_STATE[uid] = {"step": "name", "name": None, "phone": None, "client": None, "hash": None}
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f519 H\u1ee7y", callback_data="menu")]])
    txt = ("\u2795 <b>TH\u00caM ACC B\u1eb0NG OTP</b>\n\n"
           "B\u01b0\u1edbc 1/3: Nh\u1eadp <b>t\u00ean acc</b> (vd: FOX)")
    try: await q.edit_message_caption(caption=txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    except:
        try: await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        except: await q.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

def start_health():
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"A1ZTUS BYPASS alive")
        def do_HEAD(self):
            self.send_response(200); self.end_headers()
        def log_message(self, *a): pass
    port = int(os.environ.get("PORT", 8080))
    try:
        srv = HTTPServer(("0.0.0.0", port), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print("[+] health :" + str(port))
    except Exception as e:
        print("[!] health: " + str(e))

async def post_init(app):
    print("[+] bot ready")

def main():
    start_health()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(TypeHandler(Update, approval_gate), group=-1)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("share", cmd_share))
    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CommandHandler("codes", cmd_codes))
    app.add_handler(CommandHandler("redeem", cmd_redeem))
    app.add_handler(CommandHandler("addsession", cmd_addsession))
    app.add_handler(CommandHandler("addotp", cmd_add_otp))
    app.add_handler(CommandHandler("cancel", cmd_cancel_addsession))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("scan", cb_scan))
    app.add_handler(CallbackQueryHandler(cb_menu, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(cb_share_help, pattern="^share_help$"))
    app.add_handler(CallbackQueryHandler(cb_myid_help, pattern="^myid_help$"))
    app.add_handler(CallbackQueryHandler(cb_panel_list, pattern="^panel_list$"))
    app.add_handler(CallbackQueryHandler(cb_panel, pattern=r"^panel:"))
    app.add_handler(CallbackQueryHandler(cb_tog, pattern=r"^tog:"))
    app.add_handler(CallbackQueryHandler(cb_start_acc, pattern=r"^start:"))
    app.add_handler(CallbackQueryHandler(cb_stop_acc, pattern=r"^stop:"))
    app.add_handler(CallbackQueryHandler(cb_start_all, pattern="^start_all$"))
    app.add_handler(CallbackQueryHandler(cb_stop_all, pattern="^stop_all$"))
    app.add_handler(CallbackQueryHandler(cb_rf_all, pattern="^rf_all$"))
    app.add_handler(CallbackQueryHandler(cb_rf, pattern=r"^rf:"))
    app.add_handler(CallbackQueryHandler(cb_wd, pattern=r"^wd:"))
    app.add_handler(CallbackQueryHandler(cb_up, pattern=r"^up:"))
    app.add_handler(CallbackQueryHandler(cb_upgo, pattern=r"^upgo:"))
    app.add_handler(CallbackQueryHandler(cb_live, pattern="^live$"))
    app.add_handler(CallbackQueryHandler(cb_del_list, pattern="^del_list$"))
    app.add_handler(CallbackQueryHandler(cb_del, pattern=r"^del:"))
    app.add_handler(CallbackQueryHandler(cb_code_menu, pattern="^code_menu$"))
    app.add_handler(CallbackQueryHandler(cb_code_tog, pattern="^code_tog$"))
    app.add_handler(CallbackQueryHandler(cb_code_retry, pattern="^code_retry$"))
    app.add_handler(CallbackQueryHandler(cb_code_export, pattern="^code_export$"))
    app.add_handler(CallbackQueryHandler(cb_scan, pattern="^scan_hist$"))
    app.add_handler(CallbackQueryHandler(cb_users_panel, pattern="^users_panel$"))
    app.add_handler(CallbackQueryHandler(cb_appr_all, pattern="^appr_all$"))
    app.add_handler(CallbackQueryHandler(cb_appr_ok, pattern=r"^appr_ok:"))
    app.add_handler(CallbackQueryHandler(cb_appr_no, pattern=r"^appr_no:"))
    app.add_handler(CallbackQueryHandler(cb_add_session, pattern="^add_session$"))
    app.add_handler(CallbackQueryHandler(cb_add_start, pattern="^add$"))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CommandHandler("addacc", cmd_addacc))
    app.add_handler(CallbackQueryHandler(cb_assign_menu, pattern="^assign_menu$"))
    app.add_handler(CallbackQueryHandler(cb_assign_user, pattern=r"^assign_user:"))
    app.add_handler(CallbackQueryHandler(cb_assign, pattern=r"^assign:"))
    app.add_handler(CallbackQueryHandler(cb_unassign, pattern=r"^unassign:"))
    app.add_handler(CallbackQueryHandler(cb_kick_user, pattern=r"^kick:"))
    app.add_handler(CallbackQueryHandler(cb_user_detail, pattern=r"^udetail:"))
    app.add_handler(CallbackQueryHandler(cb_msg_user, pattern=r"^msg_user:"))
    app.add_handler(CallbackQueryHandler(cb_set_min, pattern=r"^set_min:"))
    app.add_handler(CallbackQueryHandler(cb_broadcast_all, pattern="^broadcast_all$"))
    app.add_handler(CallbackQueryHandler(cb_pending_list, pattern="^pending_list$"))
    app.add_handler(CallbackQueryHandler(cb_assign_menu, pattern="^assign_menu$"))
    app.add_handler(CallbackQueryHandler(cb_assign_user, pattern=r"^assign_user:"))
    app.add_handler(CallbackQueryHandler(cb_assign, pattern=r"^assign:"))
    app.add_handler(CallbackQueryHandler(cb_unassign, pattern=r"^unassign:"))
    app.add_handler(CommandHandler("addacc", cmd_addacc))
    app.add_handler(CallbackQueryHandler(cb_admin_add, pattern="^admin_add$"))
    app.add_handler(CommandHandler("wipe", cmd_wipe))
    print("[*] polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
