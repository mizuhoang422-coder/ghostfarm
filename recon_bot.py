"""Recon @ThoDaoVang_bot bang session FOX."""
import asyncio, sys, os, json, re
sys.path.insert(0, os.getcwd())
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.messages import RequestWebViewRequest

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
TARGET = "ThoDaoVang_bot"

# Lay session FOX tu storage
import storage
storage.init()
fox = None
for a in storage.list_accounts():
    if a.get("uid") == 8249205817 or "FOX" in (a.get("name") or ""):
        fox = a
        break
if not fox:
    print("[!] Khong tim thay session FOX trong DB")
    print("    Cac acc hien co:")
    for a in storage.list_accounts():
        print(f"      #{a['id']} {a.get('name')} uid={a.get('uid')}")
    sys.exit(1)

SESSION = fox["session"]
print(f"[+] Dung acc: {fox.get('name')} uid={fox.get('uid')}")

async def main():
    c = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
    await c.connect()
    me = await c.get_me()
    print(f"[+] Logged in: {me.id} @{me.username} {me.first_name}")
    print()

    # 1. Resolve bot
    try:
        bot = await c.get_entity(TARGET)
    except Exception as e:
        print(f"[!] Khong tim thay bot: {e}")
        return
    print(f"=== BOT INFO ===")
    print(f"    id:         {bot.id}")
    print(f"    username:   @{bot.username}")
    print(f"    name:       {bot.first_name}")
    print(f"    is_bot:     {getattr(bot, 'bot', False)}")

    # 2. Full user -> bot_info -> menu_button
    try:
        full = await c(GetFullUserRequest(bot))
        fu = full.full_user
        bi = getattr(fu, "bot_info", None)
        if bi:
            print(f"\n=== BOT INFO ===")
            print(f"    description:  {str(getattr(bi, 'description', ''))[:300]}")
            mb = getattr(bi, "menu_button", None)
            if mb:
                print(f"    menu_button:")
                print(f"        text: {getattr(mb, 'text', '')}")
                print(f"        url:  {getattr(mb, 'url', '')}")
                print(f"        type: {type(mb).__name__}")
            cmds = getattr(bi, "commands", None)
            if cmds:
                print(f"    commands ({len(cmds)}):")
                for cmd in cmds:
                    print(f"        /{cmd.command} — {cmd.description}")
    except Exception as e:
        print(f"[!] GetFullUser fail: {e}")

    # 3. Recent messages
    print(f"\n=== RECENT MESSAGES (15 cuoi) ===")
    count = 0
    async for msg in c.iter_messages(bot, limit=15):
        count += 1
        if not msg.text and not msg.message:
            t = f"[media type: {type(msg.media).__name__ if msg.media else 'unknown'}]"
        else:
            t = (msg.text or msg.message or "")[:200].replace("\n", " ")
        d = msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else "?"
        print(f"    [{d}] {t}")
        # buttons
        if msg.buttons:
            for row in msg.buttons:
                for b in row:
                    print(f"        BTN: {b.text}  url={getattr(b,'url',None)}  data={getattr(b,'data',None)}")
    if count == 0:
        print("    (chua co message nao)")

    # 4. Thu mo WebView
    print(f"\n=== TRY RequestWebView ===")
    for plat in ["android", "ios", "web"]:
        try:
            res = await c(RequestWebViewRequest(
                peer=bot, bot=bot, platform=plat,
                url="https://thodaovang.com/",  # doan URL
                from_bot_menu=True, compact=True))
            url = res.url
            print(f"    [{plat}] OK len={len(url) if url else 0}")
            if url:
                print(f"        url: {url[:300]}")
        except Exception as e:
            print(f"    [{plat}] fail: {type(e).__name__}: {str(e)[:120]}")

    # 5. Gui /start
    print(f"\n=== GUI /start ===")
    try:
        await c.send_message(bot, "/start")
        print("[+] Da gui /start, doi 3s...")
        await asyncio.sleep(3)
        async for msg in c.iter_messages(bot, limit=2):
            t = (msg.text or msg.message or "")[:400].replace("\n", " ")
            print(f"    [{msg.date.strftime('%H:%M:%S')}] {t}")
            if msg.buttons:
                for row in msg.buttons:
                    for b in row:
                        print(f"        BTN: {b.text}  url={getattr(b,'url',None)}")
            break
    except Exception as e:
        print(f"[!] send /start fail: {e}")

    await c.disconnect()

asyncio.run(main())
