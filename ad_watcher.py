"""Playwright ad watcher — inject Telegram WebView fake de Adsgram/Monetag chay."""
import time, json, threading

BASE = "https://ghostfarm-k3m.pages.dev/"
_AD_LOCK = threading.Lock()


def _inject_script(initdata):
    safe = initdata.replace("\\", "\\\\").replace("`", "\\`")
    return r"""
(function(){
    const idata = `__IDATA__`;
    const pairs = Object.fromEntries(idata.split('&').map(p => {
        const i = p.indexOf('=');
        return [p.slice(0, i), p.slice(i + 1)];
    }).map(([k, v]) => [k, decodeURIComponent(v || '')]));
    let user = {};
    try { user = JSON.parse(pairs.user || '{}'); } catch(e){}

    const themeParams = {
        bg_color: '#0f0f1a', text_color: '#ffffff', hint_color: '#999999',
        link_color: '#6ab3f3', button_color: '#6ab3f3', button_text_color: '#ffffff',
        secondary_bg_color: '#1a1a2e'
    };

    try {
        Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 5 });
        Object.defineProperty(navigator, 'platform', { get: () => 'Linux armv8l' });
    } catch(e){}

    const webApp = {
        initData: idata,
        initDataUnsafe: {
            user: user,
            auth_date: parseInt(pairs.auth_date||'0'),
            hash: pairs.hash || '',
            query_id: pairs.query_id || '',
            start_param: pairs.start_param || ''
        },
        ready: () => {}, expand: () => {}, close: () => {},
        onEvent: () => {}, offEvent: () => {}, sendData: () => {},
        openLink: (u) => { window.location.href = u; },
        openTelegramLink: (u) => { window.location.href = u; },
        openInvoice: (url, cb) => { if (cb) setTimeout(()=>cb('cancelled'), 100); },
        showPopup: (p, cb) => { if (cb) setTimeout(()=>cb('closed'), 100); },
        showAlert: (m, cb) => { if (cb) setTimeout(()=>cb(), 100); },
        showConfirm: (m, cb) => { if (cb) setTimeout(()=>cb(true), 100); },
        isExpanded: true, viewportHeight: 851, viewportStableHeight: 851, viewportWidth: 393,
        colorScheme: 'dark', themeParams: themeParams, version: '7.0', platform: 'android',
        headerColor: '#0f0f1a', backgroundColor: '#0f0f1a',
        MainButton: { text:'', color:'#6ab3f3', textColor:'#ffffff', isVisible:false, isActive:true,
            show:()=>{}, hide:()=>{}, setText:()=>{}, setParams:()=>{}, onClick:()=>{}, offClick:()=>{}, enable:()=>{}, disable:()=>{}, showProgress:()=>{}, hideProgress:()=>{} },
        BackButton: { isVisible:false, show:()=>{}, hide:()=>{}, onClick:()=>{}, offClick:()=>{} },
        HapticFeedback: { impactOccurred:()=>{}, notificationOccurred:()=>{}, selectionChanged:()=>{} },
        CloudStorage: { setItem:()=>{}, getItem:(k,cb)=>setTimeout(()=>cb(null,null),0), removeItem:()=>{}, getItems:(k,cb)=>setTimeout(()=>cb(null,{}),0) },
        isVersionAtLeast: () => true,
        setHeaderColor: () => {}, setBackgroundColor: () => {},
        enableClosingConfirmation: () => {}, disableClosingConfirmation: () => {},
        enableVerticalSwipes: () => {}, disableVerticalSwipes: () => {},
        requestWriteAccess: (cb) => { if (cb) setTimeout(()=>cb(true), 100); },
        requestContact: (cb) => { if (cb) setTimeout(()=>cb(false), 100); },
        shareToStory: () => {},
        readTextFromClipboard: (cb) => { if (cb) setTimeout(()=>cb(''), 100); }
    };

    const initParams = {
        tgWebAppData: idata,
        tgWebAppVersion: '7.0',
        tgWebAppPlatform: 'android',
        tgWebAppThemeParams: JSON.stringify(themeParams),
        tgWebAppStartParam: pairs.start_param || ''
    };

    const webView = {
        initParams: initParams,
        postEvent: (type, data) => { console.log('[WebView] postEvent', type, data); },
        receiveEvent: (type, data) => {},
        isIframe: false, isFullscreen: true,
        onEvent: () => {}, offEvent: () => {}, callbacks: {}
    };

    const proxy = {
        postEvent: (type, data) => { console.log('[Proxy] postEvent', type, data); }
    };

    const tgObj = { WebApp: webApp, WebView: webView, Utils: {} };

    try {
        Object.defineProperty(window, 'Telegram', {
            configurable: false, enumerable: true,
            get: () => tgObj, set: () => {}
        });
    } catch(e) { window.Telegram = tgObj; }

    try {
        Object.defineProperty(window, 'TelegramWebviewProxy', {
            configurable: false, enumerable: true,
            get: () => proxy, set: () => {}
        });
    } catch(e) { window.TelegramWebviewProxy = proxy; }

    if (!window.external) window.external = { notify: (d) => { console.log('[external]', d); } };
    else if (!window.external.notify) window.external.notify = (d) => { console.log('[external]', d); };

    if (!location.hash || location.hash.indexOf('tgWebAppData=') < 0) {
        const frag = 'tgWebAppData=' + encodeURIComponent(idata) +
                     '&tgWebAppVersion=7.0&tgWebAppPlatform=android' +
                     '&tgWebAppThemeParams=' + encodeURIComponent(JSON.stringify(themeParams));
        try { history.replaceState(null, '', location.pathname + location.search + '#' + frag); } catch(e){}
    }
})();
""".replace("__IDATA__", safe)


def watch_one_ad(initdata, log=print, max_wait=90, task_name=None):
    # Doi lock toi 180s thay vi fail ngay
    if not _AD_LOCK.acquire(timeout=180):
        log("[ad] lock timeout 180s")
        return {"ok": False, "err": "busy"}
    try:
        return _watch_inner(initdata, log, max_wait, task_name)
    finally:
        _AD_LOCK.release()


def _watch_inner(initdata, log, max_wait, task_name):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        log(f"[ad] no playwright: {e}")
        return {"ok": False, "err": "no_playwright"}

    result = {"ok": False, "progress_before": None, "progress_after": None, "err": None, "task": task_name}
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox", "--disable-dev-shm-usage",
                    "--disable-gpu", "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-default-apps",
                    "--disable-features=Translate,site-per-process",
                ],
                chromium_sandbox=False,
            )
        except Exception as e:
            log(f"[ad] launch fail: {e}")
            return {"ok": False, "err": f"launch: {str(e)[:80]}"}

        try:
            ctx = browser.new_context(
                user_agent=("Mozilla/5.0 (Linux; Android 13; SM-S918B) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0.0.0 Mobile Safari/537.36"),
                viewport={"width":393,"height":851},
                device_scale_factor=2.75,
                is_mobile=True, has_touch=True,
                locale="vi-VN",
                timezone_id="Asia/Ho_Chi_Minh",
                java_script_enabled=True,
                service_workers="block",
            )
            ctx.route("**/*", _route_handler)
            ctx.add_init_script(_inject_script(initdata))

            page = ctx.new_page()
            page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
            log("[ad] page load")

            # Cho app boot — doi text khong con "Đang tải"
            booted = False
            for i in range(20):
                page.wait_for_timeout(2000)
                txt = page.evaluate("() => (document.body.innerText||'').slice(0,300)")
                if "Đang tải" not in txt and "Chỉ dành cho" not in txt and "Đang gieo" not in txt:
                    booted = True
                    log(f"[ad] app booted after {(i+1)*2}s")
                    break
            if not booted:
                log(f"[ad] boot timeout (40s): {txt[:150]}")
                if "Chỉ dành cho" in txt or "điện thoại" in txt.lower():
                    result["err"] = "phone_check_fail"
                else:
                    result["err"] = "no_boot"
                return result

            page.wait_for_timeout(2500)

            # Buoc 0: Check force-join gate (Tham gia kenh)
            for _fj in range(3):
                page.wait_for_timeout(2000)
                joined = page.evaluate("""() => {
                    const txt = document.body.innerText || '';
                    if (/Tôi đã tham gia|Đã tham gia|I've joined|I have joined/i.test(txt)) {
                        // Tim nut
                        const btns = [...document.querySelectorAll('button, .btn, a, div[role=button]')];
                        for (const b of btns) {
                            if (/Tôi đã tham gia|Đã tham gia|I've joined/i.test(b.innerText || '')) {
                                b.click();
                                return true;
                            }
                        }
                    }
                    return false;
                }""")
                if joined:
                    print("[ad] force-join: clicked 'Tôi đã tham gia'")
                    page.wait_for_timeout(3000)
                    break

            # Buoc 1: Doi app boot xong (co card task hoac nav)
            print("[ad] doi app render...")
            try:
                page.wait_for_selector(".card, nav, [class*='card'], [class*='task']", timeout=30000)
                print("[ad] card/nav xuat hien")
            except Exception:
                print("[ad] khong thay card, thu click tab van")

            page.wait_for_timeout(3000)

            # Buoc 2: Retry click tab 15 lan
            clicked_tab = False
            for _try in range(15):
                # Kiem tra da click chua (task card visible)
                has_card = page.evaluate("""() => {
                    return document.querySelectorAll('.card.task.ad, .card.task').length > 0;
                }""")
                if has_card:
                    clicked_tab = True
                    print(f"[ad] task card visible (try {_try})")
                    break

                # Thu click
                clicked_tab = page.evaluate("""() => {
                    // Cach 1: text "Nhiệm vụ"
                    const cands = [];
                    document.querySelectorAll('*').forEach(el => {
                        const t = (el.innerText || '').trim();
                        if (/^nhi[eệ]m\\s*v[uụ]/i.test(t) && t.length < 25) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.width < 200 && r.height > 0) {
                                cands.push({el, a: r.width*r.height});
                            }
                        }
                    });
                    cands.sort((a,b) => a.a - b.a);
                    if (cands.length > 0) {
                        const el = cands[0].el;
                        el.scrollIntoView({block:'center'});
                        el.click();
                        let p = el.parentElement;
                        for (let i = 0; i < 3 && p; i++) { p.click(); p = p.parentElement; }
                        return true;
                    }
                    // Cach 2: nav bar
                    const navs = document.querySelectorAll('nav, [role=tablist], .nav, .tabbar, .bottom-nav, .tabs');
                    for (const n of navs) {
                        for (const k of n.children) {
                            if (/nhi[eệ]m/i.test(k.innerText || '')) { k.click(); return true; }
                        }
                    }
                    // Cach 3: button
                    const btns = [...document.querySelectorAll('button')];
                    for (const b of btns) {
                        if (/nhi[eệ]m/i.test(b.innerText || '')) { b.click(); return true; }
                    }
                    return false;
                }""")
                if clicked_tab:
                    # Doi 2s sau click
                    page.wait_for_timeout(2000)
                    # Kiem tra lai
                    has_card2 = page.evaluate("""() => document.querySelectorAll('.card.task.ad, .card.task').length > 0""")
                    if has_card2:
                        print(f"[ad] card visible after click (try {_try})")
                        break

                page.wait_for_timeout(1500)

            if not clicked_tab:
                # Screenshot debug
                try:
                    from pathlib import Path as _P
                    dbg = _P.home() / ".tg_toolkit" / "ad_debug"
                    dbg.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(dbg / "no_tab.png"), full_page=True)
                    # Dump text
                    body_txt = page.evaluate("() => (document.body.innerText || '').slice(0, 300)")
                    print(f"[ad] no_tab dump: {body_txt}")
                except Exception: pass
            if not clicked_tab:
                # Screenshot debug
                try:
                    from pathlib import Path as _P
                    dbg = _P.home() / ".tg_toolkit" / "ad_debug"
                    dbg.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(dbg / "no_tab.png"), full_page=True)
                    print(f"[ad] screenshot saved: {dbg / 'no_tab.png'}")
                except Exception: pass
            if not clicked_tab:
                result["err"] = "no_tab"
                return result
            log("[ad] tab Nhiệm vụ clicked")
            page.wait_for_timeout(3000)

            prog_map = _read_progress_map(page)
            result["progress_before"] = prog_map
            log(f"[ad] progress: {prog_map}")

            target_info = page.evaluate("""(name) => {
                const cards = [...document.querySelectorAll('.card.task.ad, .card.task')];
                for (const c of cards) {
                    const txt = c.innerText || '';
                    if (name && txt.indexOf(name) < 0) continue;
                    const m = txt.match(/(\\d+)\\/(\\d+)/);
                    if (m && parseInt(m[1]) >= parseInt(m[2])) continue;
                    const title = txt.split('\\n')[0].trim();
                    const btn = [...c.querySelectorAll('button, .btn')].find(b => /xem|watch/i.test(b.innerText || ''));
                    if (!btn) continue;
                    return {title, progress: m ? m[0] : '', found: true};
                }
                return {found: false};
            }""", task_name)

            if not target_info.get("found"):
                result["err"] = "no_watch_btn"
                log(f"[ad] no watchable task")
                return result

            log(f"[ad] target: {target_info.get('title')} ({target_info.get('progress')})")

            clicked = page.evaluate("""(name) => {
                const cards = [...document.querySelectorAll('.card.task.ad, .card.task')];
                for (const c of cards) {
                    const txt = c.innerText || '';
                    if (name && txt.indexOf(name) < 0) continue;
                    const m = txt.match(/(\\d+)\\/(\\d+)/);
                    if (m && parseInt(m[1]) >= parseInt(m[2])) continue;
                    const btn = [...c.querySelectorAll('button, .btn')].find(b => /xem|watch/i.test(b.innerText || ''));
                    if (btn) { btn.scrollIntoView({block:'center'}); btn.click(); return true; }
                }
                return false;
            }""", task_name)

            if not clicked:
                result["err"] = "no_watch_btn"
                return result
            log("[ad] Xem clicked, waiting provider...")

            deadline = time.time() + max_wait
            tick = 0
            confirmed = False
            while time.time() < deadline:
                page.wait_for_timeout(3000)
                tick += 1
                cur_map = _read_progress_map(page)
                # CHI coi la thanh cong khi dict khong rong VA co it nhat 1 gia tri tang
                if cur_map and cur_map != prog_map:
                    # kiem tra co task nao tang that khong
                    for k, v in cur_map.items():
                        old = prog_map.get(k, "0/0")
                        try:
                            old_n = int(old.split("/")[0])
                            new_n = int(v.split("/")[0])
                            if new_n > old_n:
                                result["progress_after"] = cur_map
                                result["ok"] = True
                                log(f"[ad] progress TANG: {k} {old} -> {v}")
                                confirmed = True
                                break
                        except Exception:
                            pass
                    if confirmed:
                        # doi them 8s cho provider callback ve backend
                        log("[ad] chờ provider callback (8s)...")
                        page.wait_for_timeout(8000)
                        # doc lai lan cuoi
                        final_map = _read_progress_map(page)
                        if final_map:
                            result["progress_after"] = final_map
                        return result
                if tick % 5 == 0:
                    log(f"[ad] waiting ({tick*3}s) prog={cur_map}")
            result["err"] = "timeout"
            log(f"[ad] timeout after {max_wait}s, final={_read_progress_map(page)}")
            return result
        except Exception as e:
            result["err"] = str(e)[:100]
            log(f"[ad] {type(e).__name__}: {str(e)[:150]}")
            return result
        finally:
            try: browser.close()
            except: pass


def _read_progress_map(page):
    try:
        return page.evaluate("""() => {
            const out = {};
            document.querySelectorAll('.card.task.ad, .card.task').forEach(c => {
                const txt = c.innerText || '';
                const title = txt.split('\\n')[0].trim();
                const m = txt.match(/(\\d+)\\/(\\d+)/);
                if (title && m) out[title] = m[0];
            });
            return out;
        }""")
    except Exception:
        return {}


def _route_handler(route):
    try:
        u = route.request.url
        if "telegram.org" in u and "telegram-web-app.js" in u:
            route.fulfill(status=200, content_type="application/javascript", body="// blocked")
            return
        route.continue_()
    except:
        try: route.continue_()
        except: pass



