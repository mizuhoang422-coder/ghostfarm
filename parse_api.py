"""Extract api() function + test endpoint voi initData FOX."""
from pathlib import Path
import re, json

html = (Path.home() / ".tg_toolkit" / "thodaovang" / "index.html").read_text(encoding="utf-8", errors="ignore")

# Tim dinh nghia ham api()
print("=== HAM api() ===")
for m in re.finditer(r'(?:async\s+)?function\s+api\s*\([^)]*\)\s*\{', html):
    start = m.start()
    # dem ngoac
    depth = 0
    i = m.end() - 1
    while i < len(html):
        if html[i] == "{": depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                print(html[start:i+1])
                print("---")
                break
        i += 1

# Tim arrow function api = async
for m in re.finditer(r'(?:const|let|var)\s+api\s*=\s*async\s*\([^)]*\)\s*=>\s*\{', html):
    start = m.start()
    depth = 0
    i = m.end() - 1
    while i < len(html):
        if html[i] == "{": depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                print(html[start:i+1])
                print("---")
                break
        i += 1

# Tim header / Authorization / init-data
print("\n=== HEADER / AUTH ===")
for pat in [r'Authorization["\']?\s*[:=]\s*["\']([^"\']+)',
            r'[Xx]-[Ii]nit-?[Dd]ata["\']?\s*[:=]\s*["\']([^"\']+)',
            r'[Xx]-[Tt]elegram-?[Ii]nit-?[Dd]ata',
            r'headers\s*[:=]\s*\{[^}]+\}',
            r'initData']:
    for m in re.finditer(pat, html):
        s = m.group(0)[:200].replace("\n"," ")
        print(f"    {s}")

# Tim endpoint base
print("\n=== BASE URL ===")
for m in re.finditer(r'["\'](/api/[a-z/]+)["\']', html):
    print(f"    {m.group(1)}")

# Tim API_BASE
for m in re.finditer(r'(?:API|api|base|BASE|url|URL)[A-Za-z_]*\s*[:=]\s*["\']([^"\']+)["\']', html):
    print(f"    {m.group(0)[:150]}")
