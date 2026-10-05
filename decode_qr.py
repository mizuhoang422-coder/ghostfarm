import httpx, re, json
from pathlib import Path
UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"}

# Decode QR
print("=== VIETQR DECODE ===")
qr_path = Path.home() / ".tg_toolkit" / "thodaovang" / "vietqr.png"
if qr_path.exists():
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode
        img = Image.open(qr_path)
        codes = decode(img)
        for cd in codes:
            data = cd.data.decode("utf-8")
            print(f"    QR DATA: {data}")
    except Exception as e:
        print(f"    decode err: {e}")
        # Fallback: dung opencv
        try:
            import cv2
            from pyzbar.pyzbar import decode
            img = cv2.imread(str(qr_path))
            codes = decode(img)
            for cd in codes:
                print(f"    QR DATA: {cd.data.decode('utf-8')}")
        except Exception as e2:
            print(f"    cv2 fallback err: {e2}")

# YouTube channel
print("\n=== YOUTUBE CHANNEL ===")
r = httpx.get("https://www.youtube.com/@Th%E1%BB%A3%C4%90%C3%A0oV%C3%A0ngFree",
              headers=UA, timeout=20, follow_redirects=True)
print(f"    status: {r.status_code}  len={len(r.text)}")
# Extract channel data
patterns = [
    (r'"channelId":"(UC[^"]+)"', "channel_id"),
    (r'"externalId":"(UC[^"]+)"', "external_id"),
    (r'"vanityChannelUrl":"([^"]+)"', "vanity"),
    (r'"ownerChannelName":"([^"]+)"', "owner"),
    (r'"description":"([^"]{20,300})"', "description"),
    (r'"subscriberCountText":\{"simpleText":"([^"]+)"\}', "subs"),
    (r'"viewCountText":\{"simpleText":"([^"]+)"\}', "views"),
    (r'"joinedDateText":\{"content":"([^"]+)"\}', "joined"),
    (r'"country":\{"simpleText":"([^"]+)"\}', "country"),
]
for pat, name in patterns:
    found = re.findall(pat, r.text)
    if found:
        print(f"    {name}: {found[0][:200]}")

# Video IDs
vids = list(dict.fromkeys(re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', r.text)))[:10]
print(f"    videos: {vids}")

# Title
title = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
if title: print(f"    title: {title.group(1)}")

# Description
desc = re.search(r'<meta name="description" content="([^"]+)"', r.text)
if desc: print(f"    meta desc: {desc.group(1)[:300]}")

# Links
links = re.findall(r'https?://(?:www\.)?(?:facebook|tiktok|instagram|telegram|t\.me)\.com/[A-Za-z0-9_.\-/@]+', r.text)
print(f"    social links:")
for l in list(dict.fromkeys(links))[:15]:
    print(f"      {l}")
