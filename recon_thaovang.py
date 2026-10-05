"""Recon thodaovang.com — fetch bundle, extract endpoint."""
import httpx, re, json
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE = "https://result-gotta-responsibility-firewire.trycloudflare.com/"
OUT = Path.home() / ".tg_toolkit" / "thodaovang"
OUT.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36",
      "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8"}

API_RE = re.compile(r'''["'`]((?:/api|/v\d+|/graphql|/trpc|/rpc|/rest)[A-Za-z0-9_/\-{}.$]*)["'`]''')
ABS_RE = re.compile(r'https?://[A-Za-z0-9._\-]+(?:\.workers\.dev|\.pages\.dev|\.vercel\.app|\.netlify\.app|\.fly\.dev|\.railway\.app|\.onrender\.com|\.trycloudflare\.com)[A-Za-z0-9_/\-?.=&%]*')
WS_RE  = re.compile(r'wss?://[A-Za-z0-9._\-]+[A-Za-z0-9_/\-?.=&%]*')
SOCK_RE = re.compile(r'''["'`]([A-Za-z0-9_\-]+\.(?:on|emit|emit|send|fire|trigger)|[a-z]+:[a-z_]+)["'`]''')

with httpx.Client(follow_redirects=True, timeout=25) as c:
    print(f"[*] Fetch {BASE}")
    r = c.get(BASE, headers=UA)
    print(f"    status={r.status_code}  len={len(r.text)}  ct={r.headers.get('content-type','')[:40]}")
    (OUT / "index.html").write_text(r.text, encoding="utf-8")

    # Tim script src + link
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', r.text)
    links   = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', r.text)
    print(f"    scripts: {len(scripts)}  links: {len(links)}")

    all_assets = set()
    for s in scripts + links:
        if s.startswith("data:"): continue
        all_assets.add(urljoin(BASE, s))

    # Them guess
    for g in ["/app.js","/main.js","/bundle.js","/assets/index.js","/assets/main.js",
              "/_next/static/chunks/main.js","/static/js/main.js","/js/app.js"]:
        u = urljoin(BASE, g)
        try:
            rr = c.head(u, headers=UA)
            if rr.status_code == 200:
                all_assets.add(u)
        except Exception: pass

    print(f"\n[*] Fetch {len(all_assets)} assets...")
    all_js = []
    endpoints = set()
    abs_urls = set()
    ws_urls = set()

    for u in sorted(all_assets):
        try:
            rr = c.get(u, headers=UA)
            if rr.status_code != 200: continue
            name = Path(urlparse(u).path).name or f"asset_{len(all_js)}.txt"
            (OUT / name).write_text(rr.text, encoding="utf-8", errors="ignore")
            ct = rr.headers.get("content-type","")
            print(f"    [{rr.status_code}] {u}  len={len(rr.text)}  ct={ct[:30]}")
            if "javascript" in ct or u.endswith(".js") or ".mjs" in u:
                all_js.append(rr.text)
                endpoints.update(API_RE.findall(rr.text))
                abs_urls.update(ABS_RE.findall(rr.text))
                ws_urls.update(WS_RE.findall(rr.text))
        except Exception as e:
            print(f"    [ERR] {u}: {str(e)[:80]}")

    if all_js:
        (OUT / "all.js").write_text("\n/* --- */\n".join(all_js), encoding="utf-8")
        print(f"\n[+] Combined all.js: {sum(len(x) for x in all_js)} chars")

    print(f"\n=== API ENDPOINTS ===")
    for ep in sorted(endpoints): print(f"    {ep}")

    print(f"\n=== ABSOLUTE URLS ===")
    for u in sorted(abs_urls): print(f"    {u}")

    print(f"\n=== WS URLS ===")
    for u in sorted(ws_urls): print(f"    {u}")

    # Dong bo endpoint co dau cua API base
    print(f"\n=== SEARCH 'api' keywords in JS ===")
    for js in all_js:
        for m in re.finditer(r'["\']((?:https?://)?[A-Za-z0-9_\-\.]+/[a-zA-Z0-9_\-/]+)["\']', js):
            u = m.group(1)
            if "/api/" in u or "socket" in u.lower() or "ws" in u.lower():
                print(f"    {u}")

