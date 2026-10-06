import asyncio, time, uuid, json, re, urllib.parse, threading
import httpx

API = "https://ghostfarm-api.nhathaybip2000.workers.dev/api"
ORIGIN = "https://ghostfarm-k3m.pages.dev"
BASE = "https://ghostfarm-k3m.pages.dev/"
UA = {"User-Agent":"Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36",
      "Origin":ORIGIN, "Referer":ORIGIN+"/", "content-type":"application/json"}
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
BOT_USER = "ghostfarmx_bot"

CROPS = ["pumpkin","eggplant","tomato","corn","barley","wheat"]
WATER_ERR = ("NO_WATER","WATER_EMPTY","ENERGY_LOW","INSUFFICIENT_WATER",
             "WATER_LOW","WATER_ADS_REQUIRED","BOOST_NEEDED","NO_ENERGY")

STATE = {}

def _fresh_state():
    return {"action":"","plots":[],"ads":{},"ads_now":"",
            "tasks":"","task_now":"","code":"","last":""}

def st_init(aid):
    cur = STATE.get(aid)
    if not isinstance(cur, dict):
        STATE[aid] = _fresh_state()
        return STATE[aid]
    for k, v in _fresh_state().items():
        if k not in cur:
            cur[k] = v
    return cur

def st_set(aid, key, val):
    if aid is None: return
    st = st_init(aid)
    st[key] = val
    st["last"] = time.strftime("%H:%M:%S")

def st_get(aid):
    return st_init(aid)


# ---------- Telethon ----------
async def _fetch_initdata_async(sess):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl import functions
    try:
        c = TelegramClient(StringSession(sess), API_ID, API_HASH)
        await c.connect()
        try:
            if not await c.is_user_authorized():
                return None
            bot = await c.get_entity(BOT_USER)
            for pl in ("android","web","ios"):
                try:
                    res = await c(functions.messages.RequestWebViewRequest(
                        peer=bot, bot=bot, platform=pl, url=BASE, from_bot_menu=False))
                    url = res.url
                    if "#tgWebAppData=" in url:
                        fr = url.split("#tgWebAppData=",1)[1]
                        raw = re.split(r"&tgWebAppVersion|&tgWebAppPlatform|&tgWebAppThemeParams", fr)[0]
                        return urllib.parse.unquote(raw)
                    if "tgWebAppData=" in url:
                        fr = url.split("tgWebAppData=",1)[1]
                        return urllib.parse.unquote(fr.split("&")[0])
                except Exception:
                    continue
            return None
        finally:
            try: await c.disconnect()
            except: pass
    except Exception as e:
        print(f"[fetch_initdata] {e}")
        return None


def _run_in_thread(coro):
    """Chay coroutine trong thread rieng co loop rieng — KHONG dung asyncio.run()."""
    result = [None]
    def _run():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result[0] = loop.run_until_complete(coro)
            finally:
                loop.close()
        except Exception as e:
            print(f"[thread_loop] {e}")
    t = threading.Thread(target=_run)
    t.start()
    t.join(timeout=90)
    return result[0]


def fetch_initdata_sync(sess):
    """LUON chay trong thread rieng - khong destroy main loop."""
    return _run_in_thread(_fetch_initdata_async(sess))


async def _get_me_async(sess):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    try:
        c = TelegramClient(StringSession(sess), API_ID, API_HASH)
        await c.connect()
        if not await c.is_user_authorized():
            await c.disconnect(); return None
        me = await c.get_me()
        await c.disconnect()
        return {"uid": me.id,
                "name": (me.first_name or "") + (" "+(me.last_name or "") if me.last_name else ""),
                "username": me.username}
    except Exception:
        return None


def get_me_sync(sess):
    return _run_in_thread(_get_me_async(sess))


# ---------- Game API ----------
class GF:
    def __init__(self, initdata):
        self.c = httpx.Client(timeout=25, headers=UA, follow_redirects=True)
        r = self.c.post(API+"/auth/telegram",
                        json={"initData":initdata,"deviceId":str(uuid.uuid4()),"fingerprint":{}})
        if r.status_code != 200:
            raise RuntimeError(f"auth {r.status_code}: {r.text[:100]}")
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
        s, j = self.get("/user/me"); return (j or {}).get("profile") or {}
    def farm_state(self):
        s, j = self.get("/farm"); return (j or {}).get("farm") or {}
    def tasks(self):
        s, j = self.get("/tasks"); return (j or {}).get("tasks") or []
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
        """Flow: lookup -> ad-session -> ads/complete -> redeem."""
        # 1. Lookup
        s, j = self.get("/promo/"+code)
        if s != 200:
            return False, f"lookup_{s}"
        promo = (j or {}).get("promo") or {}
        status = promo.get("status", "")
        if promo.get("redeemed"):
            return False, "already_redeemed"
        if status == "expired":
            return False, "expired"
        if status != "available" and status != "":
            return False, f"status_{status}"

        # 2. Ad session
        s, j = self.post(f"/promo/{code}/ad-session")
        if s != 200:
            return False, f"session_{s}"
        sid = (j or {}).get("sessionId")
        if not sid:
            return False, "no_session_id"

        # 3. Complete ad (backend auto accept)
        mws = j.get("minWatchSec", 6)
        time.sleep(mws + 1)
        s, j = self.post("/ads/complete", {"sessionId": sid, "slot": 0})
        if s != 200:
            return False, f"complete_{s}"

        # 4. Redeem
        s, j = self.post(f"/promo/{code}/redeem", {"adSessionId": sid})
        if s == 200 and (j or {}).get("ok"):
            coins = (j or {}).get("coins", 0)
            return True, f"ok +{coins}"
        code_err = (j or {}).get("code", "")
        if code_err == "PROMO_USED":
            return False, "already_redeemed"
        return False, f"redeem_{s}_{code_err}"



def farm_tick(gf, cfg, aid=None, allowed_crops=None):
    stats = {"planted":0,"watered":0,"harvested":0,"earned_gems":0}
    f = gf.farm_state()
    plots = f.get("plots") or []
    now = int(time.time()*1000)

    if aid:
        pdata = []
        for p in plots:
            idx = p.get("idx"); stat = p.get("state"); crop = p.get("crop")
            ready = p.get("readyAt")
            ready_in = ""
            if ready and ready > now:
                secs = (ready - now)//1000
                ready_in = f"{secs//60}m{secs%60}s" if secs > 60 else f"{secs}s"
            pdata.append({"idx":idx,"crop":crop or "","state":stat,
                          "ready_in":ready_in,"watered":p.get("watered",False)})
        st_set(aid, "plots", pdata)

    for p in plots:
        idx = p.get("idx"); stat = p.get("state"); ready = p.get("readyAt")
        if stat == "empty":
            if aid: st_set(aid, "action", f"🌱 Trồng plot {idx}")
            if gf.try_plant(idx, allowed_crops): stats["planted"] += 1
        elif stat in ("ready","harvestable","done"):
            if aid: st_set(aid, "action", f"🌾 Thu hoạch plot {idx}")
            s, j = gf.harvest_with_ad(idx)
            if s == 200:
                stats["harvested"] += 1
                stats["earned_gems"] += (j or {}).get("earned", 0)
        elif stat == "growing":
            if not p.get("watered"):
                if aid: st_set(aid, "action", f"💧 Tưới plot {idx}")
                if gf.water_or_refill(idx): stats["watered"] += 1
            if ready and ready <= now:
                if aid: st_set(aid, "action", f"🌾 Thu hoạch plot {idx} (chín)")
                s, j = gf.harvest_with_ad(idx)
                if s == 200:
                    stats["harvested"] += 1
                    stats["earned_gems"] += (j or {}).get("earned", 0)
    return stats


def task_tick(gf, cfg, aid=None):
    stats = {"claims":0,"reward":0}
    tasks = gf.tasks()
    if aid:
        ads = {}
        for t in tasks:
            if (t.get("kind") or t.get("type")) == "ad":
                ads[t.get("title","?")] = f"{t.get('progress') or 0}/{t.get('target') or 10}"
        st_set(aid, "ads", ads)
        link_done = sum(1 for t in tasks if (t.get("kind") or t.get("type"))=="link"
                        and (t.get("progress") or 0) >= (t.get("target") or 5))
        link_total = sum(1 for t in tasks if (t.get("kind") or t.get("type"))=="link")
        social_done = sum(1 for t in tasks if (t.get("kind") or t.get("type"))=="social"
                          and t.get("state") == "done")
        social_total = sum(1 for t in tasks if (t.get("kind") or t.get("type"))=="social")
        st_set(aid, "tasks", f"Smartlink {link_done}/{link_total} · Social {social_done}/{social_total}")

    started = [t for t in tasks if t.get("state")=="started"
               and (t.get("kind") or t.get("type"))=="link"]
    for t in started:
        if aid: st_set(aid, "task_now", f"Claim Smartlink {t.get('id')}")
        s, j = gf.post("/tasks/"+str(t["id"])+"/claim", {})
        if s == 200:
            rw = (j or {}).get("reward", 0)
            stats["claims"] += 1; stats["reward"] += rw
            if aid: st_set(aid, "task_now", f"✅ Smartlink {t.get('id')} +{rw}")
            return stats
    if started: return stats

    for t in tasks:
        kind = t.get("kind") or t.get("type")
        if kind == "ad": continue
        if t.get("state") != "open": continue
        prog = t.get("progress") or 0
        target = t.get("target") or 5
        if target - prog <= 0: continue
        tid = t.get("id")
        if aid: st_set(aid, "task_now", f"Smartlink {tid} bắt đầu ({prog}/{target})")
        s, j = gf.post("/tasks/"+str(tid)+"/start", {})
        code = (j or {}).get("code","")
        if s == 200:
            dwell = (t.get("dwellSec") or 8) + 2
            if aid: st_set(aid, "task_now", f"Smartlink {tid} chờ {dwell}s")
            time.sleep(dwell)
        elif code == "SMARLINK_PENDING":
            if aid: st_set(aid, "task_now", f"Smartlink {tid} pending")
            return stats
        else:
            continue
        s, j = gf.post("/tasks/"+str(tid)+"/claim", {})
        if s == 200:
            rw = (j or {}).get("reward", 0)
            stats["claims"] += 1; stats["reward"] += rw
            if aid: st_set(aid, "task_now", f"✅ Smartlink {tid} +{rw}")
            return stats
        time.sleep(0.5)
    return stats
