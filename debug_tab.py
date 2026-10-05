"""Debug buoc 2 — click tab Nhiệm vụ, dump truoc/sau."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
import storage
storage.init()

accs = storage.list_accounts()
target = accs[0]
print(f"[+] Target: {target['name']}")

out = Path.home() / ".tg_toolkit" / "ad_debug"
out.mkdir(parents=True, exist_ok=True)

from ad_watcher import _inject_script, _route_handler

from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=[
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox","--disable-dev-shm-usage","--single-process","--disable-gpu",
    ])
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        viewport={"width":393,"height":851}, device_scale_factor=2.75,
        is_mobile=True, has_touch=True, locale="vi-VN",
    )
    ctx.route("**/*", _route_handler)
    ctx.add_init_script(_inject_script(target["init_data"]))
    page = ctx.new_page()

    page.goto("https://ghostfarm-k3m.pages.dev/", wait_until="domcontentloaded", timeout=30000)
    print("[+] Loaded, wait 10s")
    page.wait_for_timeout(10000)
    page.screenshot(path=str(out / "1_home.png"))

    # Tim tab Nhiệm vụ - dump tat ca clickable
    tabs = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('*').forEach(el => {
            const t = (el.innerText || '').trim();
            if (/nhi[eệ]m/i.test(t) && t.length < 30) {
                const r = el.getBoundingClientRect();
                out.push({tag: el.tagName, cls: (el.className||'').slice(0,60), text: t, w: r.width, h: r.height, x: r.x, y: r.y, visible: r.width > 0 && r.height > 0});
            }
        });
        return out;
    }""")
    print(f"[+] Tab candidates: {json.dumps(tabs, ensure_ascii=False)[:800]}")

    # Click tab (chon phan tu nho nhat, visible)
    clicked = page.evaluate("""() => {
        const cands = [];
        document.querySelectorAll('*').forEach(el => {
            const t = (el.innerText || '').trim();
            if (/^nhi[eệ]m\\s*v[uụ]/i.test(t) && t.length < 25) {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && r.width < 200) {
                    cands.push({el, area: r.width * r.height});
                }
            }
        });
        cands.sort((a,b) => a.area - b.area);
        if (cands.length === 0) return null;
        const el = cands[0].el;
        el.scrollIntoView({block:'center'});
        el.click();
        // click ca parent neu can
        let p = el.parentElement;
        for (let i = 0; i < 3 && p; i++) {
            p.click();
            p = p.parentElement;
        }
        return el.tagName + '.' + (el.className||'').slice(0,40) + ' | ' + el.innerText;
    }""")
    print(f"[+] Clicked: {clicked}")
    page.wait_for_timeout(4000)
    page.screenshot(path=str(out / "2_after_click.png"))

    dump = page.evaluate("""() => {
        return {
            url: location.href,
            bodyText: (document.body.innerText || "").slice(0, 600),
            cardAdCount: document.querySelectorAll('.card.task.ad').length,
            allCards: [...document.querySelectorAll('.card')].length,
            tasks: [...document.querySelectorAll('.card.task, .card')].slice(0,8).map(c => ({
                cls: (c.className||'').slice(0,60),
                text: (c.innerText||'').slice(0,80),
            })),
            buttons: [...document.querySelectorAll('button, .btn')].slice(0,20).map(b => b.innerText.trim()).filter(Boolean),
        };
    }""")
    print(f"[+] DOM after click:")
    print(json.dumps(dump, ensure_ascii=False, indent=2)[:2000])

    browser.close()
