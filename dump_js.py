from pathlib import Path
import re

html = (Path.home() / ".tg_toolkit" / "thodaovang" / "index.html").read_text(encoding="utf-8", errors="ignore")

# Extract all inline script content (khong src)
scripts = []
for m in re.finditer(r'<script(?![^>]*src)[^>]*>(.*?)</script>', html, re.DOTALL):
    scripts.append(m.group(1))

total = "\n\n/* ===== SCRIPT BLOCK ===== */\n\n".join(scripts)
print(f"[+] total JS: {len(total)} chars, {total.count(chr(10))} lines")

# Luu ra file de doc dan
out = Path.home() / ".tg_toolkit" / "thodaovang" / "inline.js"
out.write_text(total, encoding="utf-8")
print(f"[+] saved: {out}")

# In tung phan 150 dong
lines = total.split("\n")
n = len(lines)
step = 150
print(f"\n[+] total lines: {n}, in {step} dong/lan")
for i in range(0, n, step):
    print(f"\n========== PART {i//step + 1}/{(n+step-1)//step} (line {i+1}-{min(i+step,n)}) ==========")
    for j in range(i, min(i+step, n)):
        print(f"{j+1:5}: {lines[j]}")
