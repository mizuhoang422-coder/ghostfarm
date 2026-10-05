"""Recon dev qua Telegram channels + support."""
import asyncio, sys, os, json, re
sys.path.insert(0, os.getcwd())
import storage
storage.init()
from telethon import TelegramClient
from telethon.sessions import StringSession

fox = [a for a in storage.list_accounts() if a.get("uid") == 8249205817][0]

async def recon():
    c = TelegramClient(StringSession(fox["session"]), 2040, "b18441a1ff607e10a989891a5462e627")
    await c.connect()
    try:
        # Kiem tra cac kenh
        for ch in ["@KenhThoDaoVang", "@ThoDaoVangSupport", "@ThoDaoVangRutTien"]:
            print(f"\n=== {ch} ===")
            try:
                ent = await c.get_entity(ch)
                print(f"    id: {ent.id}")
                print(f"    title: {getattr(ent, 'title', None)}")
                print(f"    username: @{getattr(ent, 'username', None)}")
                print(f"    about: {getattr(ent, 'about', '')}")
                print(f"    participants: {getattr(ent, 'participants_count', '?')}")
                # recent messages
                async for m in c.iter_messages(ent, limit=20):
                    if m.text:
                        t = m.text[:300].replace("\n", " ")
                        print(f"    [{m.date.strftime('%d/%m %H:%M') if m.date else '?'}] {t}")
                        # Tim user mention / admin
                        for u in re.findall(r"@[A-Za-z0-9_]{4,}", m.text):
                            print(f"        @{u}")
            except Exception as e:
                print(f"    err: {e}")
        
        # Tim qua Search
        print(f"\n=== Search messages 'ThoDaoVang' ===")
        try:
            from telethon.tl.functions.contacts import SearchRequest
            res = await c(SearchRequest(q="ThoDaoVang", limit=10))
            for chat in res.chats[:10]:
                print(f"    @{getattr(chat,'username',None)}  {getattr(chat,'title',None)}")
        except Exception as e:
            print(f"    err: {e}")
    finally:
        await c.disconnect()

asyncio.run(recon())
