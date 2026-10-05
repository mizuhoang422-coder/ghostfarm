import sys, asyncio, json
sys.path.insert(0, r"C:\Users\anhnh\ghostfarm")
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
BOT = "ghostfarmx_bot"
WEB_URL = "https://ghostfarm-k3m.pages.dev/"

SEEDS = [
    ("FOX",    "+84837258569", "1BVtsOIcBu7ViVQ5BLPvVOFaILHfkWyScKtjbc-NoNQczQfBel5g_hBFUZERD6o_QgKZny-m1VWTppESH7XsILIf4t0dmoyKtgUCK-XVPzlJo_PKkdmAMFMB1_O3qEN5KDZGMif-CJZUoOjZcnTX_kNCrTLEzMgoBfdEhXhwB0vn6zpWT8SGjgAV0f1fg-M-v-sXTw8cSxQaKSI4Px9LmDqHXXNQKnH_oUoieR2xLpXGcom8At1mhIms5fZ2XotV-zu9T0IYT9ntpgLXxD9dHxMWldfzxqxYGJCQBTiMdRXe6pBcyJEPPua1nvPL1iwXkDePyRO-WRyos4Ulg3aWDc1iC9rLWMvw="),
    ("A1ztus", "+84911404475", "1BVtsOIcBu5fNmr6DZEiB_Yn96f2xGzgcxGrUtiIr5F3MAln2nGfGKi_TffP_jLxDkCP91VBq1m04Kmr4mSKuZD0FZ5GTAklzNefEpkJqJowGvEd1YU0VAXPnprVI9vmvaxRApceiMWmFpvle2O3C_arTZv5L_Fr2Ip4vw65tOymyxpMlEfEtb94Lgi1u5CzmGtBi3qFRvHa5TQruq1I_lhPgV3wGY1p4Q0rPPDt2dj_rEWs_uhzVv0lvOp7KyTS9Ye059Fb34HG5f3QFV0BznuLvXCoe7pzdkpOPn53qlWivThPfU8bMlgPuc5UUGtLVDaCTRLP_zS6HlcNeEtXSVgnvWOg9Z3k="),
    ("Henri",  "+84382061412", "1BVtsOIcBu2Jv9WBQqcs5qHqdj4bDlh_gxJDwSOnFz8RxtR8bFtvB0emf-UehU_3GeHjVJop7iRUgPI5GKL6jizQlm-yoZ1THF0-p7rWIamvA0BuYVYM2AZUg6wsR1I96p6NNz4FEGk94MI6fk_xFNpe6ih9JUSkgdejsg4sj4AMpR5NDqhcIJOrcxGJzsamsNdSBMqVdd-5dEQYs0KDHoD7CZweJ5u59zkHu4_F_q_7g9_U2JbU0iG7wDJe4gs2q-xLVdCVOpppqExQsNvw7U9MtNfTG9FcYNYg5Fp1wW6rYVc5N_H5_rZ-C2PHOOU-b0e1zI17i7a22S5mark7lDC4vdMwivuk="),
    ("MINH",   "+84983733025", "1BVtsOIcBu55FrTOB2sjs9LRTGKpa0giCk2iG2hdIYZECV51H4zkfegOsIgSUmCAgw2Eb-KKlVO-x4V29v1ubeRIbFEKOsLTaX5ZdMI8Ih9LwWEVuh89wSGovAzp4z4PvP-XdJvwdi9YggBulVtwonksBGIkX0poVDOTLKNMbvd8YyMvruNydacWOVD3gT6tLj7C6s95-leqROmChG8MVkWm-hm6oJ7TW85v2vUPWCt-jCLGf_KIOSKhm18SXUTKfexAcu_mNR0BNmrmzqFhJIVuRUC9EPsZHu70VBXX2dK8Dmz4L2cNVJ75LbZGfDjhkCO0GCgBRveKqVVxua4StGikM9l0LQlc="),
]

async def check(name, phone, sess):
    print("=" * 60)
    print(f"[{name}] {phone}")
    try:
        c = TelegramClient(StringSession(sess), API_ID, API_HASH)
        await c.connect()
        auth = await c.is_user_authorized()
        print(f"  authorized: {auth}")
        if not auth:
            await c.disconnect(); return
        me = await c.get_me()
        print(f"  uid={me.id}  @{me.username}  name={me.first_name} {me.last_name or ''}")
        # thu mo web view
        try:
            b = await c.get_entity(BOT)
            ok = False
            for plat in ["android","ios","web"]:
                try:
                    res = await c(RequestWebViewRequest(peer=b, bot=b, platform=plat, url=WEB_URL, from_bot_menu=True, compact=True))
                    u = getattr(res,"url",None)
                    if u:
                        print(f"  webview OK ({plat}) url_len={len(u)}")
                        ok = True
                        break
                except Exception as e:
                    print(f"  webview {plat} FAIL: {type(e).__name__}: {str(e)[:120]}")
            if not ok:
                # check xem da start bot chua
                try:
                    msgs = []
                    async for m in c.iter_messages(b, limit=1):
                        msgs.append(m.id)
                    print(f"  da tung nhan tin bot: {bool(msgs)}")
                except Exception as e:
                    print(f"  iter bot fail: {str(e)[:100]}")
        except Exception as e:
            print(f"  get_entity({BOT}) FAIL: {str(e)[:150]}")
        await c.disconnect()
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {str(e)[:200]}")

async def main():
    for name, phone, sess in SEEDS:
        await check(name, phone, sess)

if __name__ == "__main__":
    asyncio.run(main())
