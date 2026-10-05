"""Debug: click Xem roi xem SDK lam gi."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
import storage
storage.init()

target = [a for a in storage.list_accounts() if a.get("init_data")][0]
print(f"[+] {target['name']}")

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

    logs = []
    page.on("console", lambda m: logs.append(f"[{m.type}] {m.text[:200]}"))
    page.on("pageerror", lambda e: logs.append(f"[PAGEERR] {str(e)[:200]}"))
    page.on("request", lambda r: logs.append(f"[REQ] {r.method} {r.url[:120]}") if any(x in r.url for x in ("adsgram","onclck","sad.min","gigapub","monetag")) else None)

    page.goto("https://ghostfarm-k3m.pages.dev/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(10000)

    # click tab Nhiệm vụ
    page.evaluate("""() => {
        const cands = [];
        document.querySelectorAll('*').forEach(el => {
            const t = (el.innerText||'').trim();
            if (/^nhi[eệ]m\\s*v[uụ]/i.test(t) && t.length < 25) {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.width < 200) cands.push({el, a: r.width*r.height});
            }
        });
        cands.sort((a,b)=>a.a-b.a);
        if (cands[0]) cands[0].el.click();
    }""")
    page.wait_for_timeout(3000)

    # click Xem Adsgram
    page.evaluate("""() => {
        const c = [...document.querySelectorAll('.card.task.ad')].find(x => x.innerText.includes('Adsgram'));
        if (c) {
            const b = [...c.querySelectorAll('button,.btn')].find(x => /xem/i.test(x.innerText||''));
            if (b) b.click();
        }
    }""")
    print("[+] Clicked Adsgram Xem")
    page.wait_for_timeout(2000)

    # dump overlay / iframe moi
    dump = page.evaluate("""() => {
        return {
            iframes: [...document.querySelectorAll('iframe')].map(f => ({src: (f.src||'').slice(0,150), w: f.offsetWidth, h: f.offsetHeight})),
            videos: [...document.querySelectorAll('video')].map(v => ({src: (v.src||'').slice(0,100), w: v.offsetWidth})),
            modals: [...document.querySelectorAll('[class*="modal"], [class*="overlay"], [class*="popup"], [class*="reward"], [id*="ad"]')].map(e => ({tag: e.tagName, id: e.id, cls: (e.className||'').slice(0,60), visible: e.offsetWidth > 0})),
            bodyHTMLlen: document.body.innerHTML.length,
            scripts: [...document.querySelectorAll('script')].map(s => (s.src||'').slice(0,120)).filter(Boolean),
        };
    }""")
    print(f"[+] Dump sau click:")
    print(json.dumps(dump, ensure_ascii=False, indent=2)[:2500])

    page.wait_for_timeout(6000)
    shot = out / "after_click_xem.png"
    page.screenshot(path=str(shot), full_page=True)
    print(f"[+] Screenshot: {shot}")

    print(f"\n[+] Console logs ({len(logs)}):")
    for l in logs[-40:]:
        print(f"    {l}")

    browser.close()
