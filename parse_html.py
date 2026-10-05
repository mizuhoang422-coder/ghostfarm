"""Parse inline JS trong index.html."""
from pathlib import Path
import re, json

html = Path.home() / ".tg_toolkit" / "thodaovang" / "index.html"
txt = html.read_text(encoding="utf-8", errors="ignore")
print(f"[*] HTML len: {len(txt)}")

# 1. Fetch / api endpoint trong inline JS
print("\n=== FETCH / AXIOS / API CALLS ===")
for pat in [r'fetch\s*\(\s*["\']([^"\']+)["\']', r'fetch\s*\(\s*`([^`]+)`',
            r'axios\.[a-z]+\s*\(\s*["\']([^"\']+)["\']',
            r'\.post\s*\(\s*["\']([^"\']+)["\']',
            r'\.get\s*\(\s*["\']([^"\']+)["\']',
            r'https?://[A-Za-z0-9._\-:/?=&%]+',
            r'wss?://[A-Za-z0-9._\-:/?=&%]+']:
    hits = set(re.findall(pat, txt))
    if hits:
        print(f"\n  {pat[:50]}")
        for h in sorted(hits)[:30]:
            print(f"    {h}")

# 2. Path strings
print("\n=== PATH STRINGS ===")
for m in re.finditer(r'["\'](/(?:api|v\d|user|auth|mine|withdraw|deposit|task|refer|spin|daily|claim|box|upgrade|shop)[A-Za-z0-9_/\-\{\}\$]*)["\']', txt):
    print(f"    {m.group(1)}")

# 3. Socket / WS events
print("\n=== SOCKET EVENTS ===")
for m in re.finditer(r'socket\.on\s*\(\s*["\']([^"\']+)["\']', txt):
    print(f"    on: {m.group(1)}")
for m in re.finditer(r'socket\.emit\s*\(\s*["\']([^"\']+)["\']', txt):
    print(f"    emit: {m.group(1)}")

# 4. Config / const variables
print("\n=== CONFIG / API BASE ===")
for m in re.finditer(r'(?:API_BASE|BASE_URL|SERVER_URL|apiBase|baseUrl|WS_URL|SOCKET_URL|host|endpoint)\s*[:=]\s*["\']([^"\']+)["\']', txt):
    print(f"    {m.group(0)[:120]}")

# 5. Telegram WebApp initData usage
print("\n=== INITDATA USAGE ===")
for m in re.finditer(r'initData[A-Za-z_]*', txt):
    print(f"    {m.group(0)}")

# 6. API key / token patterns
print("\n=== TOKENS / KEYS ===")
for m in re.finditer(r'["\']([A-Za-z0-9_\-]{32,})["\']', txt):
    v = m.group(1)
    if "jsdelivr" not in v and not v.startswith("http"):
        print(f"    {v[:80]}")

# 7. Extract unique strings around "api"
print("\n=== CONTEXT AROUND 'api' ===")
seen = set()
for m in re.finditer(r'.{0,40}/api.{0,80}', txt):
    s = m.group(0).replace("\n"," ")[:150]
    if s not in seen:
        seen.add(s)
        print(f"    {s}")
        if len(seen) > 20: break
