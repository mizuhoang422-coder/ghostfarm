"""Debug: chup screenshot + dump DOM."""
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
        "--no-sandbox","--disable-dev-shm-usage","--single-process",
        "--disable-gpu",
    ])
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        viewport={"width":393,"height":851},
        device_scale_factor=2.75,
        is_mobile=True, has_touch=True,
        locale="vi-VN",
    )
    # AP DUNG ROUTE HANDLER
    ctx.route("**/*", _route_handler)
    ctx.add_init_script(_inject_script(target["init_data"]))
    page = ctx.new_page()

    msgs = []
    page.on("console", lambda m: msgs.append(f"[{m.type}] {m.text[:200]}"))
    page.on("pageerror", lambda e: msgs.append(f"[PAGEERR] {str(e)[:200]}"))

    page.goto("https://ghostfarm-k3m.pages.dev/", wait_until="domcontentloaded", timeout=30000)
    print("[+] Loaded, waiting 10s...")
    page.wait_for_timeout(10000)

    shot = out / "page_loaded2.png"
    page.screenshot(path=str(shot), full_page=True)
    print(f"[+] Screenshot: {shot}")

    tg = page.evaluate("""() => {
        const t = window.Telegram;
        if (!t) return {state:"no_Telegram"};
        if (!t.WebApp) return {state:"no_WebApp"};
        return {
            state: "ok",
            hasInitData: !!t.WebApp.initData,
            initDataLen: (t.WebApp.initData||"").length,
            initDataHead: (t.WebApp.initData||"").slice(0,50),
            user: t.WebApp.initDataUnsafe?.user || null,
            platform: t.WebApp.platform,
            version: t.WebApp.version,
        };
    }""")
    print(f"[+] Telegram obj: {json.dumps(tg, ensure_ascii=False)}")

    dump = page.evaluate("""() => {
        return {
            bodyText: (document.body.innerText || "").slice(0, 400),
            cardCount: document.querySelectorAll('.card').length,
            taskAdCount: document.querySelectorAll('.card.task.ad').length,
        };
    }""")
    print(f"[+] DOM: {json.dumps(dump, ensure_ascii=False)}")

    print(f"\n[+] Console logs ({len(msgs)}):")
    for m in msgs[:25]:
        print(f"    {m}")

    browser.close()
