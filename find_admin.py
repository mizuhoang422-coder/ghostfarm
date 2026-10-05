import httpx, re
UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"}

# Search ten admin
print("=== SEARCH HOANG DUC TRUNG ===")
for q in ['"HOANG DUC TRUNG" Timo', '"Hoàng Đức Trung" thodaovang', '"HOANG DUC TRUNG" 9021551342501', '"Hoàng Đức Trung" telegram']:
    print(f"\n[{q}]")
    for eng in [f"https://html.duckduckgo.com/html/?q={httpx.QueryParams({'q':q})}",
                f"https://www.bing.com/search?q={httpx.QueryParams({'q':q})}"]:
        try:
            r = httpx.get(eng, headers=UA, timeout=15)
            results = re.findall(r'<a[^>]*class="result__a"[^>]*>([^<]+)</a>', r.text)[:5]
            if not results:
                results = re.findall(r'<h2><a[^>]*>([^<]+)</a></h2>', r.text)[:5]
            for t in results:
                t = re.sub(r'<[^>]+>', '', t).strip()
                if t: print(f"    {t[:150]}")
        except: pass

# Search facebook share link pattern
print("\n=== FACEBOOK SHARE ===")
try:
    r = httpx.get("https://www.facebook.com/share/19RymsnLmi/", headers=UA, timeout=15, follow_redirects=True)
    # extract real url from meta
    for pat in [r'content="https://www\.facebook\.com/[^"]+"',
                r'"pageID":"(\d+)"',
                r'"entity_id":"(\d+)"']:
        for m in re.finditer(pat, r.text):
            print(f"    {m.group(0)[:150]}")
except Exception as e:
    print(f"    err: {e}")

# Try Facebook public page via graph
print("\n=== FB GRAPH ===")
for u in ["https://www.facebook.com/KenhThoDaoVang",
          "https://www.facebook.com/ThoDaoVangFree",
          "https://www.facebook.com/ThợĐàoVàng"]:
    try:
        r = httpx.get(u, headers=UA, follow_redirects=True, timeout=10)
        title = re.search(r'<title>([^<]+)</title>', r.text)
        print(f"    {u} -> {r.status_code}  {(title.group(1) if title else '')[:100]}")
    except Exception as e:
        print(f"    {u} -> err {str(e)[:60]}")
