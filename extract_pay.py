"""Extract payment call tu HTML."""
from pathlib import Path
import re

html = (Path.home() / ".tg_toolkit" / "thodaovang" / "index.html").read_text(encoding="utf-8", errors="ignore")

# Tim context xung quanh payment/next
print("=== payment/next context ===")
for m in re.finditer(r'.{400}/api/payment/next.{600}', html, re.DOTALL):
    print(m.group(0))
    print("\n" + "="*70 + "\n")

print("=== payment/confirm context ===")
for m in re.finditer(r'.{300}/api/payment/confirm.{600}', html, re.DOTALL):
    print(m.group(0))
    print("\n" + "="*70 + "\n")

print("=== packages context ===")
for m in re.finditer(r'.{200}/api/packages.{400}', html, re.DOTALL):
    print(m.group(0))
    print("\n" + "="*70 + "\n")

print("=== withdraw context ===")
for m in re.finditer(r'.{300}/api/withdraw.{400}', html, re.DOTALL):
    print(m.group(0))
    print("\n" + "="*70 + "\n")
