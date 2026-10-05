"""Playwright toi uu — chromium-headless-shell, 1 process, RAM thap."""
import time, json, urllib.parse, threading

BASE = "https://ghostfarm-k3m.pages.dev/"
# Lock: chi 1 ad session 1 thoi diem
_AD_LOCK = threading.Lock()

def _inject_script(initdata):
    return """
(function(){
    const idata = `""" + initdata + """`;
    const pairs = Object.fromEntries(idata.split('&').map(p => {
        const i = p.indexOf('=');
        return [p.slice(0, i), p.slice(i + 1)];
    }).map(([k, v]) => [k, decodeURIComponent(v || '')]));
    let user = {};
    try { user = JSON.parse(pairs.user || '{}'); } catch(e){}
    window.Telegram = {
        WebApp: {
            initData: idata,
            initDataUnsafe: { user: user, auth_date: pairs.auth_date, hash: pairs.hash, query_id: pairs.query_id, start_param: pairs.start_param },
            ready: () => {}, expand: () => {}, close: () => {},
            onEvent: () => {}, offEvent: () => {}, sendData: () => {},
            openLink: (u) => window.open(u, '_blank'),
            openTelegramLink: (u) => window.open(u, '_blank'),
            isExpanded: true, viewportHeight: 851, viewportWidth: 393,
            colorScheme: 'dark', themeParams: {}, version: '7.0', platform: 'android',
            MainButton: { show:()=>{}, hide:()=>{}, setText:()=>{}, onClick:()=>{}, offClick:()=>{}, enable:()=>{}, disable:()=>{} },
            BackButton: { show:()=>{}, hide:()=>{}, onClick:()=>{}, offClick:()=>{} },
            HapticFeedback: { impactOccurred:()=>{}, notificationOccurred:()=>{}, selectionChanged:()=>{} },
            showAlert: () => {}, showConfirm: () => {}
        }
    };
})();
"""

def watch_one_ad(initdata, log=print, max_wait=90):
    if not _AD_LOCK.acquire(blocking=False):
        log("[ad] co session khac dang chay, skip")
        return {"ok": False, "err": "busy"}
    try:
        return _watch_inner(initdata, log, max_wait)
    finally:
        _AD_LOCK.release()

def _watch_inner(initdata, log, max_wait):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        log(f"[ad] no playwright: {e}")
        return {"ok": False, "err": "no_playwright"}

    result = {"ok": False, "progress_before": None, "progress_after": None, "err": None}
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--single-process",              # giam RAM manh
                    "--no-zygote",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-sync",
                    "--disable-default-apps",
                    "--disable-features=Translate,site-per-process",
                    "--js-flags=--max-old-space-size=180",
                ],
                chromium_sandbox=False,
            )
        except Exception as e:
            log(f"[ad] launch fail: {e}")
            return {"ok": False, "err": f"launch: {str(e)[:80]}"}
        try:
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
                viewport={"width": 393, "height": 851},
                locale="vi-VN", timezone_id="Asia/Ho_Chi_Minh",
                java_script_enabled=True,
                service_workers="block",   # tiet kiem RAM
            )
            ctx.add_init_script(_inject_script(initdata))
            page = ctx.new_page()
            page.route("**/*", _block_heavy)
            page.goto(BASE, wait_until="domcontentloaded", timeout=25000)
            log("[ad] page load")
            page.wait_for_timeout(6000)

            page.evaluate("""() => { const b=[...document.querySelectorAll('a,button,div')].find(x=>/Nhiệm vụ/.test(x.textContent||'')); if(b)b.click(); }""")
            page.wait_for_timeout(2500)

            prog0 = _read_prog(page)
            result["progress_before"] = prog0
            log(f"[ad] prog={prog0}")

            clicked = page.evaluate("""() => {
                const cards=[...document.querySelectorAll('.card.task.ad')];
                for(const c of cards){
                    const sub=c.querySelector('.sub'); const m=(sub?.textContent||'').match(/(\\d+)\\/(\\d+)/);
                    if(m && parseInt(m[1])>=parseInt(m[2])) continue;
                    const btn=c.querySelector('button.btn.btn-gold.btn-sm, .adsgram-slot-btn');
                    if(btn && /Xem/i.test(btn.textContent)){ btn.click(); return true; }
                } return false;
            }""")
            if not clicked:
                result["err"] = "no_ad"; return result

            deadline = time.time() + max_wait
            while time.time() < deadline:
                page.wait_for_timeout(3000)
                p1 = _read_prog(page)
                if p1 != prog0:
                    result["progress_after"] = p1
                    result["ok"] = True
                    log(f"[ad] {prog0} -> {p1}")
                    return result
            result["err"] = "timeout"; return result
        except Exception as e:
            result["err"] = str(e)[:100]
            log(f"[ad] {type(e).__name__}: {str(e)[:120]}")
            return result
        finally:
            try: browser.close()
            except: pass

def _read_prog(page):
    try:
        return page.evaluate("""() => [...document.querySelectorAll('.card.task.ad .sub')].map(s=>s.textContent.trim()).filter(t=>/\\d+\\/\\d+/.test(t)).join('|')""")
    except: return ""

def _block_heavy(route):
    """Chan resource nang — anh, video, font"""
    try:
        t = route.request.resource_type
        u = route.request.url
        if t in ("image", "media", "font", "stylesheet"): route.abort(); return
        if any(x in u for x in ("google", "facebook", "doubleclick", "analytics")): route.abort(); return
        route.continue_()
    except: route.continue_()
