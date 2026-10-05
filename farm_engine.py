import time, uuid, json, re
from urllib.parse import parse_qsl, unquote, urlparse
import httpx
import asyncio

def _ensure_loop():
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

API = "https://ghostfarm-api.nhathaybip2000.workers.dev/api"
ORIGIN = "https://ghostfarm-k3m.pages.dev"
UA = {"User-Agent":"Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36",
      "Origin":ORIGIN,"Referer":ORIGIN+"/","content-type":"application/json"}

CROPS = ["pumpkin","eggplant","tomato","corn","barley","wheat"]
WATER_ERR = ("NO_WATER","WATER_EMPTY","ENERGY_LOW","INSUFFICIENT_WATER","WATER_LOW","WATER_ADS_REQUIRED","BOOST_NEEDED","NO_ENERGY")

def get_initdata_from_session(session_str, api_id=2040, api_hash="b18441a1ff607e10a989891a5462e627", ref="", bot="ghostfarmx_bot", web_url="https://ghostfarm-k3m.pages.dev/"):
    _ensure_loop()
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.functions.messages import RequestWebViewRequest
    c = TelegramClient(StringSession(session_str), api_id, api_hash)
    c.connect()
    try:
        b = c.get_entity(bot)
        urls = [web_url+"?startapp="+ref, web_url] if ref else [web_url]
        for u in urls:
            for plat in ["android","ios","web"]:
                try:
                    res = c(RequestWebViewRequest(peer=b, bot=b, platform=plat, url=u, from_bot_menu=True, compact=True))
                    url = getattr(res,"url",None)
                    if not url: continue
                    frag = urlparse(url).fragment or url.split("#",1)[-1]
                    q = dict(parse_qsl(frag))
                    idata = q.get("tgWebAppData")
                    if not idata:
                        q2 = dict(parse_qsl(urlparse(url).query))
                        idata = q2.get("tgWebAppData")
                    if idata: return unquote(idata)
                except Exception: continue
    finally:
        c.disconnect()
    return None

def get_me_from_session(session_str, api_id=2040, api_hash="b18441a1ff607e10a989891a5462e627"):
    _ensure_loop()
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    c = TelegramClient(StringSession(session_str), api_id, api_hash)
    c.connect()
    if not c.is_user_authorized():
        c.disconnect(); return None
    me = c.get_me()
    c.disconnect()
    return {"uid": me.id, "name": (me.first_name or "") + (" "+(me.last_name or "") if me.last_name else ""), "username": me.username}

class GF:
    def __init__(self, initdata):
        self.c = httpx.Client(timeout=25, headers=UA, follow_redirects=True)
        r = self.c.post(API+"/auth/telegram", json={"initData":initdata,"deviceId":str(uuid.uuid4()),"fingerprint":{}})
        if r.status_code != 200:
            raise RuntimeError(f"auth fail {r.status_code}: {r.text[:150]}")
        j = r.json()
        self.token = j["token"]
        self.profile = j.get("profile") or {}
        self.c.headers["authorization"] = "Bearer " + self.token
        self.c.headers["x-farm-fp"] = "{}"

    def call(self, m, p, b=None):
        try:
            r = self.c.request(m, API+p, json=b)
            try: return r.status_code, r.json()
            except: return r.status_code, {}
        except Exception as e:
            return 0, {"_err": str(e)}

    def get(self, p): return self.call("GET", p)
    def post(self, p, b=None): return self.call("POST", p, b)

    def me(self):
        s, j = self.get("/user/me")
        return (j or {}).get("profile") or {}

    def referral(self):
        s, j = self.get("/referral")
        return (j or {}).get("referral") or {}

    def history(self, limit=20):
        s, j = self.get(f"/user/history?limit={limit}")
        return (j or {}).get("items") or []

    def farm_state(self):
        s, j = self.get("/farm")
        return (j or {}).get("farm") or {}

    def tasks(self):
        s, j = self.get("/tasks")
        return (j or {}).get("tasks") or []

    def wallet(self):
        s, j = self.get("/wallet")
        return (j or {}).get("wallet") or {}

    def convert(self, amount):
        return self.post("/wallet/convert", {"amount": amount})

    def withdraw(self, method, address, amount):
        return self.post("/wallet/withdraw", {"method": method, "address": address, "amount": amount})

    def set_address(self, method, address, network=None):
        body = {"method": method, "address": address}
        if network: body["network"] = network
        return self.post("/wallet/address", body)

    # farm operations
    def plant(self, idx, crop):
        return self.post("/farm/plant", {"idx": idx, "crop": crop})

    def water(self, idx):
        return self.post("/farm/water", {"idx": idx})

    def harvest(self, idx=None):
        return self.post("/farm/harvest", {"idx": idx})

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

    def try_plant(self, idx):
        for crop in CROPS:
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
            self.refill_water(idx)
            time.sleep(1)
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

# farm tick — returns summary
def farm_tick(gf, cfg):
    stats = {"planted":0,"watered":0,"harvested":0,"earned_gems":0}
    f = gf.farm_state()
    plots = f.get("plots") or []
    now = int(time.time()*1000)
    for p in plots:
        idx = p.get("idx"); stat = p.get("state"); ready = p.get("readyAt")
        if stat == "empty":
            r = gf.try_plant(idx)
            if r: stats["planted"] += 1
        elif stat in ("ready","harvestable","done"):
            s, j = gf.harvest_with_ad(idx)
            if s == 200:
                stats["harvested"] += 1
                stats["earned_gems"] += (j or {}).get("earned", 0) or (j or {}).get("gems", 0)
        elif stat == "growing":
            if not p.get("watered"):
                if gf.water_or_refill(idx): stats["watered"] += 1
            if ready and ready <= now:
                s, j = gf.harvest_with_ad(idx)
                if s == 200:
                    stats["harvested"] += 1
                    stats["earned_gems"] += (j or {}).get("earned", 0)
    return stats

def task_tick(gf, cfg):
    stats = {"claims":0,"reward":0}
    tasks = gf.tasks()
    # started links first
    started = [t for t in tasks if t.get("state")=="started" and (t.get("kind") or t.get("type"))=="link"]
    for t in started:
        s, j = gf.post("/tasks/"+str(t["id"])+"/claim", {})
        if s == 200:
            stats["claims"] += 1
            stats["reward"] += (j or {}).get("reward", 0)
            return stats
    if started: return stats
    for t in tasks:
        if (t.get("kind") or t.get("type")) == "ad": continue
        if t.get("state") != "open": continue
        prog = t.get("progress") or 0
        target = t.get("target") or 5
        if target - prog <= 0: continue
        s, j = gf.post("/tasks/"+str(t["id"])+"/start", {})
        code = (j or {}).get("code","")
        if s == 200:
            time.sleep((t.get("dwellSec") or 8) + 2)
        elif code == "SMARLINK_PENDING":
            return stats
        else:
            continue
        s, j = gf.post("/tasks/"+str(t["id"])+"/claim", {})
        if s == 200:
            stats["claims"] += 1
            stats["reward"] += (j or {}).get("reward", 0)
        time.sleep(0.5)
    return stats

