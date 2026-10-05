"""Playwright module — tu dong xem quang cao Adsgram/Monetag/Gigapub trong WebView."""
import time, json, re, urllib.parse

BASE = "https://ghostfarm-k3m.pages.dev/"

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
            initDataUnsafe: {
                user: user,
                auth_date: pairs.auth_date,
                hash: pairs.hash,
                query_id: pairs.query_id,
                start_param: pairs.start_param,
            },
            ready: () => {},
            expand: () => {},
            close: () => {},
            onEvent: () => {},
            offEvent: () => {},
            sendData: () => {},
            openLink: (u) => window.open(u, '_blank'),
            openTelegramLink: (u) => window.open(u, '_blank'),
            isExpanded: true,
            viewportHeight: 851,
            viewportWidth: 393,
            colorScheme: 'dark',
            themeParams: {},
            MainButton: { show:()=>{}, hide:()=>{}, setText:()=>{}, onClick:()=>{}, offClick:()=>{}, enable:()=>{}, disable:()=>{} },
            BackButton: { show:()=>{}, hide:()=>{}, onClick:()=>{}, offClick:()=>{} },
            HapticFeedback: { impactOccurred:()=>{}, notificationOccurred:()=>{}, selectionChanged:()=>{} },
            showAlert: () => {},
            showConfirm: () => {},
            version: '7.0',
            platform: 'android',
        }
    };
})();
"""

def watch_one_ad(initdata, log=print, max_wait=120):
    """Mo miniapp bang Playwright, click task ad dau tien, cho provider callback.
    Return dict {ok, reward_text, progress}"""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        log(f"[ad] playwright not installed: {e}")
        return {"ok": False, "err": "no_playwright"}

    result = {"ok": False, "progress_before": None, "progress_after": None, "err": None}
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True, args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox", "--disable-dev-shm-usage",
                "--disable-gpu", "--single-process",
            ])
        except Exception as e:
            log(f"[ad] launch fail: {e}")
            return {"ok": False, "err": f"launch: {e}"}
        try:
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
                viewport={"width": 393, "height": 851},
                locale="vi-VN",
                timezone_id="Asia/Ho_Chi_Minh",
            )
            ctx.add_init_script(_inject_script(initdata))
            page = ctx.new_page()
            page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
            log("[ad] page loaded, waiting boot")
            page.wait_for_timeout(7000)

            # click tab Nhiệm vụ
            page.evaluate("""() => {
                const btns = [...document.querySelectorAll('a, button, div[role=button], div')];
                const t = btns.find(b => /Nhiệm vụ|Nhiem vu/.test(b.textContent || ''));
                if (t) t.click();
            }""")
            page.wait_for_timeout(3500)

            # doc progress truoc
            prog0 = page.evaluate("""() => {
                const subs = [...document.querySelectorAll('.card.task.ad .sub')];
                return subs.map(s => s.textContent.trim()).filter(t => /\\d+\\/\\d+/.test(t)).join('|');
            }""")
            result["progress_before"] = prog0
            log(f"[ad] progress before: {prog0}")

            # tim nut Xem dau tien chua xong
            clicked = page.evaluate("""() => {
                const cards = [...document.querySelectorAll('.card.task.ad')];
                for (const c of cards) {
                    const prog = c.querySelector('.sub');
                    const txt = prog ? prog.textContent : '';
                    const m = txt.match(/(\\d+)\\/(\\d+)/);
                    if (m && parseInt(m[1]) >= parseInt(m[2])) continue;
                    const btn = c.querySelector('button.btn.btn-gold.btn-sm');
                    if (btn && /Xem/i.test(btn.textContent)) { btn.click(); return c.querySelector('.ttl')?.textContent || 'unknown'; }
                }
                return null;
            }""")
            if not clicked:
                log("[ad] no watchable ad")
                result["err"] = "no_ad"
                return result
            log(f"[ad] clicked: {clicked}, waiting video")

            # cho ad SDK chay
            deadline = time.time() + max_wait
            while time.time() < deadline:
                page.wait_for_timeout(3000)
                prog1 = page.evaluate("""() => {
                    const subs = [...document.querySelectorAll('.card.task.ad .sub')];
                    return subs.map(s => s.textContent.trim()).filter(t => /\\d+\\/\\d+/.test(t)).join('|');
                }""")
                result["progress_after"] = prog1
                if prog1 != prog0:
                    log(f"[ad] progress changed: {prog0} -> {prog1}")
                    result["ok"] = True
                    return result
            log(f"[ad] timeout, no progress change")
            return result
        except Exception as e:
            log(f"[ad] err: {type(e).__name__}: {str(e)[:150]}")
            result["err"] = str(e)[:120]
            return result
        finally:
            try: browser.close()
            except: pass
