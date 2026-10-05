import asyncio, time, uuid, json, re, urllib.parse
from urllib.parse import parse_qsl, unquote, urlparse
import httpx

API = "https://ghostfarm-api.nhathaybip2000.workers.dev/api"
ORIGIN = "https://ghostfarm-k3m.pages.dev"
BASE = "https://ghostfarm-k3m.pages.dev/"
UA = {"User-Agent":"Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36","Origin":ORIGIN,"Referer":ORIGIN+"/","content-type":"application/json"}
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
BOT_USER = "ghostfarmx_bot"

STATE = {}  # aid -> text trang thai


def st_set(aid, key, val):
    if aid is None: return
    if aid not in STATE:
        STATE[aid] = {"farm": "", "tasks": "", "ad": "", "promo": "", "last": ""}
    STATE[aid][key] = str(val)[:200]
    import time as _t
    STATE[aid]["last"] = _t.strftime("%H:%M:%S")


def st_get(aid):
    return STATE.get(aid, {"farm": "Chua chay", "tasks": "", "ad": "", "promo": "", "last": ""})

CROPS = ["pumpkin","eggplant","tomato","corn","barley","wheat"]
WATER_ERR = ("NO_WATER","WATER_EMPTY","ENERGY_LOW","INSUFFICIENT_WATER","WATER_LOW","WATER_ADS_REQUIRED","BOOST_NEEDED","NO_ENERGY")


async def fetch_initdata(sess):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl import functions
    client = TelegramClient(StringSession(sess), API_ID, API_HASH)
    await client.connect()
    try:
        if not await client.is_user_authorized(): return None
        bot = await client.get_entity(BOT_USER)
        for pl in ("android", "web", "ios"):
            try:
                res = await client(functions.messages.RequestWebViewRequest(
                    peer=bot, bot=bot, platform=pl, url=BASE, from_bot_menu=False))
                url = res.url
                if "#tgWebAppData=" in url:
                    fr = url.split("#tgWebAppData=", 1)[1]
                    raw = re.split(r"&tgWebAppVersion|&tgWebAppPlatform|&tgWebAppThemeParams", fr)[0]
                    return urllib.parse.unquote(raw)
                if "tgWebAppData=" in url:
                    fr = url.split("tgWebAppData=", 1)[1]
                    return urllib.parse.unquote(fr.split("&")[0])
            except Exception:
                pass
        return None
    finally:
        try: await client.disconnect()
        except Exception: pass


async def fetch_initdata_with_ref(sess, ref=""):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl import functions
    client = TelegramClient(StringSession(sess), API_ID, API_HASH)
    await client.connect()
    try:
        if not await client.is_user_authorized(): return None
        bot = await client.get_entity(BOT_USER)
        url_base = BASE + ("?startapp=" + ref if ref else "")
        for pl in ("android", "web", "ios"):
            try:
                res = await client(functions.messages.RequestWebViewRequest(
                    peer=bot, bot=bot, platform=pl, url=url_base, from_bot_menu=False))
                url = res.url
                if "#tgWebAppData=" in url:
                    fr = url.split("#tgWebAppData=", 1)[1]
                    raw = re.split(r"&tgWebAppVersion|&tgWebAppPlatform|&tgWebAppThemeParams", fr)[0]
                    return urllib.parse.unquote(raw)
                if "tgWebAppData=" in url:
                    fr = url.split("tgWebAppData=", 1)[1]
                    return urllib.parse.unquote(fr.split("&")[0])
            except Exception:
                pass
        return None
    finally:
        try: await client.disconnect()
        except Exception: pass


async def get_me_from_session(sess):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    c = TelegramClient(StringSession(sess), API_ID, API_HASH)
    await c.connect()
    if not await c.is_user_authorized():
        await c.disconnect(); return None
    me = await c.get_me()
    await c.disconnect()
    return {"uid": me.id,
            "name": (me.first_name or "") + (" "+(me.last_name or "") if me.last_name else ""),
            "username": me.username}


async def otp_send_code(phone):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    c = TelegramClient(StringSession(), API_ID, API_HASH)
    await c.connect()
    sent = await c.send_code_request(phone)
    sess = c.session.save()
    await c.disconnect()
    return sess, sent.phone_code_hash


async def otp_sign_in(temp_session, phone, code, phone_code_hash=None):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError
    c = TelegramClient(StringSession(temp_session), API_ID, API_HASH)
    await c.connect()
    try:
        await c.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
    except SessionPasswordNeededError:
        await c.disconnect(); return None, "2FA"
    except Exception as e:
        await c.disconnect(); return None, str(e)[:120]
    sess = c.session.save()
    await c.disconnect()
    return sess, "OK"


async def otp_sign_in_2fa(temp_session, password):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    c = TelegramClient(StringSession(temp_session), API_ID, API_HASH)
    await c.connect()
    try:
        await c.sign_in(password=password)
    except Exception as e:
        await c.disconnect(); return None, str(e)[:120]
    sess = c.session.save()
    await c.disconnect()
    return sess, "OK"


class GF:
    def __init__(self, initdata):
        self.c = httpx.Client(timeout=25, headers=UA, follow_redirects=True)
        r = self.c.post(API+"/auth/telegram", json={"initData":initdata,"deviceId":str(uuid.uuid4()),"fingerprint":{}})
        if r.status_code != 200: raise RuntimeError(f"auth {r.status_code}: {r.text[:100]}")
        self.token = r.json()["token"]
        self.profile = r.json().get("profile") or {}
        self.c.headers["authorization"] = "Bearer " + self.token
        self.c.headers["x-farm-fp"] = "{}"
    def call(self, m, p, b=None):
        try:
            r = self.c.request(m, API+p, json=b)
            try: return r.status_code, r.json()
            except: return r.status_code, {}
        except Exception as e: return 0, {"_err": str(e)}
    def get(self, p): return self.call("GET", p)
    def post(self, p, b=None): return self.call("POST", p, b)
    def me(self):
        s, j = self.get("/user/me"); return (j or {}).get("profile") or {}
    def farm_state(self):
        s, j = self.get("/farm"); return (j or {}).get("farm") or {}
    def tasks(self):
        s, j = self.get("/tasks"); return (j or {}).get("tasks") or []
    def wallet(self):
        s, j = self.get("/wallet"); return (j or {}).get("wallet") or {}
    def history(self, limit=20):
        s, j = self.get(f"/user/history?limit={limit}"); return (j or {}).get("items") or []
    def referral(self):
        s, j = self.get("/referral"); return (j or {}).get("referral") or {}
    def convert(self, amount): return self.post("/wallet/convert", {"amount": amount})
    def withdraw(self, method, address, amount): return self.post("/wallet/withdraw", {"method": method, "address": address, "amount": amount})
    def set_address(self, method, address, network=None):
        b = {"method": method, "address": address}
        if network: b["network"] = network
        return self.post("/wallet/address", b)
    def plant(self, idx, crop): return self.post("/farm/plant", {"idx": idx, "crop": crop})
    def water(self, idx): return self.post("/farm/water", {"idx": idx})
    def harvest(self, idx=None): return self.post("/farm/harvest", {"idx": idx})
    def refill_water(self, idx):
        s, j = self.post("/ads/farm/session", {"idx": idx})
        if s != 200 or not (j or {}).get("sessionId"): return False
        sid = j["sessionId"]; mws = j.get("minWatchSec", 6)
        time.sleep(mws+1)
        for slot in range(5):
            s2, _ = self.post("/ads/farm/complete", {"sessionId":sid,"slot":slot})
            if s2 != 200: break
            time.sleep(0.5)
        return True
    def harvest_with_ad(self, idx):
        s, j = self.post("/ads/harvest/session", {"idx": idx})
        if s == 200 and (j or {}).get("sessionId"):
            sid = j["sessionId"]; mws = j.get("minWatchSec", 6)
            time.sleep(mws+1)
            for slot in range(5):
                s2, _ = self.post("/ads/harvest/complete", {"sessionId":sid,"slot":slot})
                if s2 != 200: break
                time.sleep(0.5)
        return self.harvest(idx)
    def try_plant(self, idx, allowed_crops=None):
        crops = allowed_crops if allowed_crops else CROPS
        for crop in crops:
            s, j = self.post("/farm/plant", {"idx": idx, "crop": crop})
            code = (j or {}).get("code", "")
            if s == 200: return crop
            if code == "PLOT_BUSY": return None
            if code in ("NOT_ENOUGH_COINS","CROP_GROWING","PLOT_LOCKED","CROP_LOCKED"): continue
        return None
    def water_or_refill(self, idx):
        s, j = self.post("/farm/water", {"idx": idx})
        if s == 200: return True
        if (j or {}).get("code","") in WATER_ERR:
            self.refill_water(idx); time.sleep(1)
            s2, _ = self.post("/farm/water", {"idx": idx})
            return s2 == 200
        return False
    def claim_promo(self, code):
        s, j = self.get("/promo/"+code)
        if s != 200: return False, "info fail"
        for path, body in [("/promo/"+code+"/claim",{}),("/promo/redeem",{"code":code}),("/promo/claim",{"code":code})]:
            s2, j2 = self.post(path, body)
            if s2 == 200 and (j2 or {}).get("ok"):
                sid = (j2 or {}).get("sessionId")
                if sid:
                    time.sleep(7)
                    self.post("/ads/complete", {"sessionId":sid,"slot":0})
                    s3, j3 = self.post(path, body)
                    if s3 == 200 and (j3 or {}).get("ok"): return True, "ok+ad"
                return True, "ok"
        return False, "claim fail"


def farm_tick(gf, cfg, aid=None, allowed_crops=None):
    stats = {"planted":0,"watered":0,"harvested":0,"earned_gems":0}
    f = gf.farm_state(); plots = f.get("plots") or []
    now = int(time.time()*1000)
    for p in plots:
        idx = p.get("idx"); stat = p.get("state"); ready = p.get("readyAt")
        if stat == "empty":
            if gf.try_plant(idx): stats["planted"] += 1
        elif stat in ("ready","harvestable","done"):
            s, j = gf.harvest_with_ad(idx)
            if s == 200:
                stats["harvested"] += 1
                stats["earned_gems"] += (j or {}).get("earned", 0)
        elif stat == "growing":
            if not p.get("watered"):
                if gf.water_or_refill(idx): stats["watered"] += 1
            if ready and ready <= now:
                s, j = gf.harvest_with_ad(idx)
                if s == 200:
                    stats["harvested"] += 1
                    stats["earned_gems"] += (j or {}).get("earned", 0)
    return stats


def task_tick(gf, cfg, aid=None):
    stats = {"claims":0,"reward":0}
    tasks = gf.tasks()
    # ----- AD tasks: xem quang cao -----
    for t in tasks:
        if (t.get("kind") or t.get("type")) != "ad": continue
        tid = t.get("id")
        prog = t.get("progress") or 0
        target = t.get("target") or 10
        if prog >= target: continue
        if aid: STATE[aid] = f"👀 Xem ad task {tid} ({prog}/{target})"
        # mo session
        s, j = gf.post("/ads/session", {"taskId": tid})
        code = (j or {}).get("code", "")
        if s != 200:
            if aid: STATE[aid] = f"⚠️ Ad task {tid} fail: {code}"
            continue
        sid = (j or {}).get("sessionId")
        if not sid: continue
        mws = j.get("minWatchSec", 6)
        if aid: STATE[aid] = f"⏳ Chờ ad task {tid} ({mws}s)"
        time.sleep(mws + 1)
        if aid: STATE[aid] = f"🎬 Complete ad task {tid}"
        for slot in range(min(target - prog, 5)):
            s2, j2 = gf.post("/ads/complete", {"sessionId": sid, "slot": prog + slot})
            if s2 != 200: break
            time.sleep(0.5)
        # claim
        s3, j3 = gf.post(f"/tasks/{tid}/claim", {})
        if s3 == 200:
            rw = (j3 or {}).get("reward", 0)
            stats["claims"] += 1
            stats["reward"] += rw
            if aid: STATE[aid] = f"✅ Task {tid} +{rw} coin"
    # ----- LINK tasks -----
    started = [t for t in tasks if t.get("state")=="started" and (t.get("kind") or t.get("type"))=="link"]
    for t in started:
        s, j = gf.post("/tasks/"+str(t["id"])+"/claim", {})
        if s == 200:
            stats["claims"] += 1; stats["reward"] += (j or {}).get("reward", 0); return stats
    if started: return stats
    for t in tasks:
        if (t.get("kind") or t.get("type")) == "ad": continue
        if t.get("state") != "open": continue
        prog = t.get("progress") or 0; target = t.get("target") or 5
        if target - prog <= 0: continue
        s, j = gf.post("/tasks/"+str(t["id"])+"/start", {})
        code = (j or {}).get("code","")
        if s == 200: time.sleep((t.get("dwellSec") or 8) + 2)
        elif code == "SMARLINK_PENDING": return stats
        else: continue
        s, j = gf.post("/tasks/"+str(t["id"])+"/claim", {})
        if s == 200:
            stats["claims"] += 1; stats["reward"] += (j or {}).get("reward", 0)
        time.sleep(0.5)
    return stats



