"""Recon dev: expand FB, check YT, search account number."""
import httpx, re, json

UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}

# 1. Expand FB share link
print("=== 1. FACEBOOK EXPAND ===")
try:
    r = httpx.get("https://www.facebook.com/share/19RymsnLmi/", headers=UA, follow_redirects=True, timeout=20)
    print(f"    final: {r.url}")
    print(f"    status: {r.status_code}")
    # Extract og:title, og:url
    for pat in [r'og:title["\']\s*content=["\']([^"\']+)', r'og:url["\']\s*content=["\']([^"\']+)',
                r'<title>([^<]+)</title>', r'canonical["\']\s+href=["\']([^"\']+)']:
        for m in re.finditer(pat, r.text):
            print(f"    {m.group(1)[:200]}")
except Exception as e:
    print(f"    err: {e}")

# 2. YouTube channel
print("\n=== 2. YOUTUBE CHANNEL ===")
try:
    r = httpx.get("https://www.youtube.com/@Th%E1%BB%A3%C4%90%C3%A0oV%C3%A0ngFree", headers=UA, follow_redirects=True, timeout=20)
    print(f"    status: {r.status_code}")
    for pat in [r'"channelId":"(UC[^"]+)"', r'<meta property="og:title" content="([^"]+)',
                r'<meta property="og:description" content="([^"]+)',
                r'"subscriberCountText":\{"simpleText":"([^"]+)"']:
        for m in re.finditer(pat, r.text):
            print(f"    {m.group(1)[:200]}")

    # Extract video list
    ids = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', r.text)[:5]
    print(f"    recent videos: {ids}")
except Exception as e:
    print(f"    err: {e}")

# 3. Search account number
print("\n=== 3. SEARCH STK 9021551342501 ===")
for engine in [
    f"https://www.google.com/search?q=9021551342501",
    f"https://www.bing.com/search?q=9021551342501",
    f"https://duckduckgo.com/html/?q=9021551342501",
]:
    try:
        r = httpx.get(engine, headers=UA, timeout=15)
        # Extract snippets
        texts = re.findall(r'<a[^>]*>([^<]{20,200})</a>', r.text)
        for t in texts[:8]:
            t = re.sub(r'<[^>]+>', '', t).strip()
            if "9021551342501" in t or "thodaovang" in t.lower():
                print(f"    [{engine.split('//')[1].split('/')[0]}] {t[:200]}")
    except Exception as e:
        print(f"    {engine} err: {str(e)[:80]}")

# 4. Bank code lookup
print("\n=== 4. BANK CODE 963388 ===")
# VietQR bank codes — 963388 khong chuan. Thu lookup
for url in [
    "https://api.vietqr.io/v2/banks",
]:
    try:
        r = httpx.get(url, headers=UA, timeout=15)
        data = r.json()
        if "data" in data:
            for b in data["data"]:
                if "963388" in str(b.get("bin","")) or b.get("bin") == "963388":
                    print(f"    BANK FOUND: {b}")
            # In cac bank co bin gan giong
            print(f"    total banks: {len(data['data'])}")
    except Exception as e:
        print(f"    err: {e}")

# 5. Download VietQR image
print("\n=== 5. VIETQR IMAGE ===")
try:
    r = httpx.get("https://img.vietqr.io/image/963388-9021551342501-compact2.png", headers=UA, timeout=15)
    print(f"    status: {r.status_code}  size={len(r.content)}")
    # Neu la QR code, co the decode bang pyzbar
    if r.status_code == 200 and len(r.content) > 1000:
        from pathlib import Path
        out = Path.home() / ".tg_toolkit" / "thodaovang" / "vietqr.png"
        out.write_bytes(r.content)
        print(f"    saved: {out}")
        # Try decode QR
        try:
            from PIL import Image
            from pyzbar.pyzbar import decode
            img = Image.open(out)
            codes = decode(img)
            for cd in codes:
                print(f"    QR DATA: {cd.data.decode('utf-8')}")
        except ImportError:
            print("    (install pillow + pyzbar de decode)")
        except Exception as e:
            print(f"    decode err: {e}")
except Exception as e:
    print(f"    err: {e}")
