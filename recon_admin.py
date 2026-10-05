"""Recon admin/dev ThoDaoVang."""
import asyncio, sys, os, json, re
sys.path.insert(0, os.getcwd())
import storage
storage.init()
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest

fox = [a for a in storage.list_accounts() if a.get("uid") == 8249205817][0]

async def recon():
    c = TelegramClient(StringSession(fox["session"]), 2040, "b18441a1ff607e10a989891a5462e627")
    await c.connect()
    try:
        # Check @thodaovangfree
        for handle in ["@thodaovangfree", "@ThoDaoVangSupport"]:
            print(f"\n=== {handle} ===")
            try:
                ent = await c.get_entity(handle)
                print(f"    type: {type(ent).__name__}")
                print(f"    id: {ent.id}")
                print(f"    username: @{getattr(ent, 'username', None)}")
                print(f"    title/first_name: {getattr(ent, 'title', None) or getattr(ent, 'first_name', None)}")
                print(f"    last_name: {getattr(ent, 'last_name', None)}")
                print(f"    bot: {getattr(ent, 'bot', None)}")
                print(f"    verified: {getattr(ent, 'verified', None)}")
                # full info
                try:
                    full = await c(GetFullUserRequest(ent))
                    fu = full.full_user
                    print(f"    about: {getattr(fu, 'about', '')}")
                    print(f"    bot_info: {getattr(fu, 'bot_info', None)}")
                except: pass
                # Last messages neu la chat
                try:
                    async for m in c.iter_messages(ent, limit=5):
                        if m.text:
                            print(f"    msg: {m.text[:200]}")
                except: pass
            except Exception as e:
                print(f"    err: {e}")
    finally:
        await c.disconnect()

asyncio.run(recon())
