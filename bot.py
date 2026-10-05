import os, time, json, asyncio, threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import storage
from farm_engine import GF, get_initdata_from_session, get_me_from_session, farm_tick, task_tick

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_UID = 8249205817
REF_CODE = os.environ.get("REF_CODE", "").strip()

FARM_THREADS = {}
WATCHER = {"thread": None, "stop": False}

def is_admin(update):
    return update.effective_user and update.effective_user.id == ADMIN_UID

def main_kb():
    return ReplyKeyboardMarkup([
        ["👤 Tài khoản", "🌾 Farm"],
        ["💰 Ví", "📊 Hoạt động"],
        ["🎁 Code", "⚙️ Cài đặt"],
    ], resize_keyboard=True)

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Bot riêng tư.")
        return
    await update.message.reply_text(
        "🌾 *GhostFarm Manager*\nChọn menu bên dưới 👇",
        parse_mode="Markdown", reply_markup=main_kb())

# ---------------- ACCOUNTS ----------------
async def accounts_panel(update, ctx):
    accs = storage.list_accounts()
    kb = []
    for a in accs:
        run = "▶️" if a.get("farm_running") else "⏸"
        kb.append([InlineKeyboardButton(f"{run} #{a['id']} {a.get('name','?')[:22]}",
                                        callback_data=f"acc:{a['id']}")])
    kb.append([InlineKeyboardButton("➕ Thêm acc (session)", callback_data="acc_add:session")])
    text = f"👤 *Tài khoản* — {len(accs)} acc"
    if not accs: text += "\n_Chưa có acc. Bấm thêm acc._"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown",
                                                      reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(kb))

async def acc_list_cb(update, ctx):
    q = update.callback_query; await q.answer()
    await accounts_panel(update, ctx)

async def acc_detail(q, aid):
    a = storage.get_account(aid)
    if not a:
        await q.edit_message_text("❌ Acc không tồn tại"); return
    prof = {}
    try:
        if a.get("last_state"):
            prof = json.loads(a["last_state"])
    except: pass
    run = "▶️ Đang farm" if a.get("farm_running") else "⏸ Dừng"
    text = (f"👤 *Acc #{aid}* — {a.get('name','?')}\n"
            f"UID: `{a.get('uid')}`\n"
            f"Trạng thái: {run}\n")
    if prof:
        text += (f"🪙 Coins: `{prof.get('coins',0)}`  💎 Gems: `{prof.get('gems',0)}`\n"
                 f"💵 USDT: `{prof.get('usdt',0)}`  Lv: {prof.get('level',1)}\n"
                 f"XP: {prof.get('xp',0)}/{prof.get('xpMax',0)}\n")
    bank = a.get('bank_name') or "-"
    stk = a.get('bank_stk') or "-"
    ctk = a.get('bank_ctk') or "-"
    text += f"\n🏦 Bank: `{bank}` | `{ctk}` | `{stk}`"
    kb = [
        [InlineKeyboardButton(("⏸ Dừng farm" if a.get("farm_running") else "▶️ Bật farm"),
                              callback_data=f"acc_toggle:{aid}"),
         InlineKeyboardButton("🔄 Refresh", callback_data=f"acc_refresh:{aid}")],
        [InlineKeyboardButton("💰 Rút USDT", callback_data=f"acc_wd_do:{aid}"),
         InlineKeyboardButton("💱 Đổi coin→gem", callback_data=f"acc_cv:{aid}")],
        [InlineKeyboardButton("🏦 Cài bank", callback_data=f"acc_bank:{aid}"),
         InlineKeyboardButton("🗑 Xoá", callback_data=f"acc_del:{aid}")],
        [InlineKeyboardButton("🔙 Danh sách", callback_data="acc_list")],
    ]
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def acc_cb(update, ctx):
    q = update.callback_query; await q.answer()
    data = q.data
    if data.startswith("acc_add:"):
        mode = data.split(":")[1]
        ctx.user_data["add_step"] = "session"
        await q.edit_message_text("📥 Gửi *StringSession* vào chat.\n"
                                  "Bot sẽ lưu và tự đăng nhập.", parse_mode="Markdown")
        return
    aid = int(data.split(":")[1])
    await acc_detail(q, aid)

async def acc_refresh_cb(update, ctx):
    q = update.callback_query; await q.answer("Đang refresh...")
    aid = int(q.data.split(":")[1])
    a = storage.get_account(aid)
    try:
        initdata = await _run_sync(get_initdata_from_session, a["session"], ref=REF_CODE)
        if initdata:
            gf = GF(initdata)
            prof = gf.me()
            storage.update_account(aid, last_state=json.dumps(prof))
    except Exception as e:
        await q.edit_message_text(f"❌ Refresh fail: {str(e)[:150]}")
        return
    await acc_detail(q, aid)

async def acc_toggle_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    a = storage.get_account(aid)
    new = 0 if a.get("farm_running") else 1
    storage.update_account(aid, farm_running=new)
    if new: start_farm_thread(aid)
    else:
        if aid in FARM_THREADS:
            FARM_THREADS[aid]["stop"] = True
            FARM_THREADS.pop(aid, None)
    await acc_detail(q, aid)

async def acc_del_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    storage.delete_account(aid)
    if aid in FARM_THREADS:
        FARM_THREADS[aid]["stop"] = True
        FARM_THREADS.pop(aid, None)
    await acc_list_cb(update, ctx)

async def acc_bank_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    ctx.user_data["bank_for"] = aid
    await q.edit_message_text(
        f"🏦 *Cài Bank cho acc #{aid}*\n\nGửi theo mẫu:\n"
        "`Tên ngân hàng|CTK|STK`\n"
        "Ví dụ: `Vietcombank|NGUYEN VAN A|1234567890`",
        parse_mode="Markdown")

async def acc_wd_do_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    a = storage.get_account(aid)
    if not a.get("bank_stk"):
        await q.edit_message_text("⚠️ Chưa cài bank. Bấm Cài bank trước."); return
    ctx.user_data["wd_for"] = aid
    await q.edit_message_text(
        f"💸 Nhập số *USDT* muốn rút từ acc #{aid}.",
        parse_mode="Markdown")

async def acc_cv_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    ctx.user_data["cv_for"] = aid
    await q.edit_message_text(
        f"💱 Nhập số *coin* muốn đổi sang *gem* (acc #{aid}).",
        parse_mode="Markdown")

# ---------------- FARM ----------------
async def farm_panel(update, ctx):
    accs = storage.list_accounts()
    running = sum(1 for a in accs if a.get("farm_running"))
    kb = [
        [InlineKeyboardButton("▶️ Bật tất cả", callback_data="farm_all:1"),
         InlineKeyboardButton("⏸ Dừng tất cả", callback_data="farm_all:0")],
    ]
    txt = f"🌾 *Farm* — {running}/{len(accs)} đang chạy"
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, parse_mode="Markdown",
                                                      reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(txt, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(kb))

async def farm_cb(update, ctx):
    q = update.callback_query; await q.answer()
    action = q.data.split(":")[1]
    for a in storage.list_accounts():
        if action == "1":
            storage.update_account(a["id"], farm_running=1)
            start_farm_thread(a["id"])
        else:
            storage.update_account(a["id"], farm_running=0)
            if a["id"] in FARM_THREADS:
                FARM_THREADS[a["id"]]["stop"] = True
                FARM_THREADS.pop(a["id"], None)
    await q.edit_message_text(f"✅ {'Bật' if action=='1' else 'Dừng'} farm tất cả.")

# ---------------- WALLET ----------------
async def wallet_panel(update, ctx):
    accs = storage.list_accounts()
    kb = [[InlineKeyboardButton(f"💰 #{a['id']} {a.get('name','?')[:20]}",
                                callback_data=f"acc:{a['id']}")] for a in accs]
    if not accs:
        await update.message.reply_text("Chưa có acc."); return
    if update.callback_query:
        await update.callback_query.edit_message_text("💰 *Ví* — chọn acc:",
                                                      parse_mode="Markdown",
                                                      reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text("💰 *Ví* — chọn acc:",
                                        parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(kb))

# ---------------- ACTIVITY ----------------
async def activity_panel(update, ctx):
    accs = storage.list_accounts()
    kb = [[InlineKeyboardButton(f"📊 #{a['id']} {a.get('name','?')[:20]}",
                                callback_data=f"act:{a['id']}")] for a in accs]
    if not accs:
        await update.message.reply_text("Chưa có acc."); return
    if update.callback_query:
        await update.callback_query.edit_message_text("📊 *Hoạt động*",
                                                      parse_mode="Markdown",
                                                      reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text("📊 *Hoạt động*",
                                        parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(kb))

async def act_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    acts = storage.get_activity(aid, 25)
    lines = [f"📊 *Acc #{aid}*"]
    if not acts: lines.append("_Chưa có hoạt động._")
    for r in acts:
        t = time.strftime("%d/%m %H:%M", time.localtime(r["ts"]))
        lines.append(f"`{t}` {r['msg'][:80]}")
    await q.edit_message_text("\n".join(lines), parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="act_list")]]))

async def act_list_cb(update, ctx):
    q = update.callback_query; await q.answer()
    await activity_panel(update, ctx)

# ---------------- CODES ----------------
async def codes_panel(update, ctx):
    codes = storage.list_codes(60)
    lines = [f"🎁 *Lịch sử nhập code* ({len(codes)})"]
    if not codes: lines.append("_Chưa có code nào._")
    for r in codes:
        t = time.strftime("%d/%m %H:%M", time.localtime(r["ts"]))
        mark = "✅" if r["ok"] else "❌"
        lines.append(f"{mark} `{r['code']}` → acc#{r['acc_id']} `{t}` {r['msg'][:40]}")
    if update.callback_query:
        await update.callback_query.edit_message_text("\n".join(lines), parse_mode="Markdown")
    else:
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ---------------- SETTINGS ----------------
async def settings_panel(update, ctx):
    kb = [[InlineKeyboardButton("📋 Danh sách acc", callback_data="set_list")]]
    if update.callback_query:
        await update.callback_query.edit_message_text("⚙️ *Cài đặt*", parse_mode="Markdown",
                                                      reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text("⚙️ *Cài đặt*", parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(kb))

async def set_cb(update, ctx):
    q = update.callback_query; await q.answer()
    if q.data == "set_list":
        accs = storage.list_accounts()
        lines = ["📋 *Danh sách acc*"]
        for a in accs:
            lines.append(f"#{a['id']} | uid={a.get('uid')} | {a.get('name','?')} | bank={a.get('bank_stk','-')}")
        await q.edit_message_text("\n".join(lines), parse_mode="Markdown")

# ---------------- TEXT ROUTER ----------------
async def text_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Bot riêng tư."); return
    txt = (update.message.text or "").strip()

    # menu
    if txt == "👤 Tài khoản": await accounts_panel(update, ctx); return
    if txt == "🌾 Farm": await farm_panel(update, ctx); return
    if txt == "💰 Ví": await wallet_panel(update, ctx); return
    if txt == "📊 Hoạt động": await activity_panel(update, ctx); return
    if txt == "🎁 Code": await codes_panel(update, ctx); return
    if txt == "⚙️ Cài đặt": await settings_panel(update, ctx); return

    # add account flow
    step = ctx.user_data.get("add_step")
    if step == "session":
        session = txt
        try:
            info = await _run_sync(get_me_from_session, session)
        except Exception as e:
            await update.message.reply_text(f"❌ Session lỗi: {str(e)[:150]}")
            ctx.user_data.pop("add_step", None); return
        if not info:
            await update.message.reply_text("❌ Session không hợp lệ.")
            ctx.user_data.pop("add_step", None); return
        aid = storage.add_account(info.get("username") or "?", session, info["uid"], info.get("name") or f"acc{info['uid']}")
        ctx.user_data.pop("add_step", None)
        await update.message.reply_text(f"✅ Đã thêm acc #{aid} — uid={info['uid']}")
        await accounts_panel(update, ctx)
        return

    # bank setup
    if ctx.user_data.get("bank_for"):
        aid = ctx.user_data.pop("bank_for")
        parts = txt.split("|")
        if len(parts) != 3:
            await update.message.reply_text("Sai format. Dùng: `Tên|CTK|STK`", parse_mode="Markdown"); return
        storage.update_account(aid,
                               bank_name=parts[0].strip(),
                               bank_ctk=parts[1].strip(),
                               bank_stk=parts[2].strip())
        await update.message.reply_text(f"✅ Đã cài bank cho acc #{aid}.")
        return

    # withdraw
    if ctx.user_data.get("wd_for"):
        aid = ctx.user_data.pop("wd_for")
        try: amt = float(txt)
        except: await update.message.reply_text("Số không hợp lệ."); return
        a = storage.get_account(aid)
        try:
            initdata = await _run_sync(get_initdata_from_session, a["session"], ref=REF_CODE)
            gf = GF(initdata)
            gf.set_address("VND", a.get("bank_stk",""), network="VND")
            s, j = gf.withdraw("VND", a.get("bank_stk",""), amt)
            storage.log_activity(aid, f"Rút {amt} USDT -> {s}")
            await update.message.reply_text(f"💸 Rút -> {s}\n`{json.dumps(j, ensure_ascii=False)[:200]}`",
                                            parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ {str(e)[:150]}")
        return

    # convert
    if ctx.user_data.get("cv_for"):
        aid = ctx.user_data.pop("cv_for")
        try: amt = int(txt)
        except: await update.message.reply_text("Số không hợp lệ."); return
        a = storage.get_account(aid)
        try:
            initdata = await _run_sync(get_initdata_from_session, a["session"], ref=REF_CODE)
            gf = GF(initdata)
            s, j = gf.convert(amt)
            storage.log_activity(aid, f"Đổi {amt} coin -> gem: {s}")
            await update.message.reply_text(f"💱 -> {s}\n`{json.dumps(j, ensure_ascii=False)[:200]}`",
                                            parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ {str(e)[:150]}")
        return

    await update.message.reply_text("Chọn menu bên dưới 👇", reply_markup=main_kb())

# ---------------- FARM WORKER ----------------
def start_farm_thread(aid):
    if aid in FARM_THREADS and FARM_THREADS[aid]["th"].is_alive(): return
    holder = {"stop": False}
    def worker():
        last_refresh = 0
        while not holder["stop"]:
            try:
                a = storage.get_account(aid)
                if not a or not a.get("farm_running"): break
                initdata = get_initdata_from_session(a["session"], ref=REF_CODE)
                if not initdata:
                    storage.log_activity(aid, "initData fail")
                    time.sleep(60); continue
                gf = GF(initdata)
                try:
                    ts = task_tick(gf, {})
                    if ts["claims"]:
                        storage.log_activity(aid, f"task +{ts['reward']} ({ts['claims']})")
                except Exception as e:
                    storage.log_activity(aid, f"task err {str(e)[:60]}")
                try:
                    fs = farm_tick(gf, {})
                    if fs["planted"] or fs["harvested"]:
                        storage.log_activity(aid, f"farm P{fs['planted']} H{fs['harvested']} +{fs['earned_gems']}g")
                except Exception as e:
                    storage.log_activity(aid, f"farm err {str(e)[:60]}")
                if time.time() - last_refresh > 300:
                    try:
                        prof = gf.me()
                        storage.update_account(aid, last_state=json.dumps(prof))
                        last_refresh = time.time()
                    except: pass
            except Exception as e:
                storage.log_activity(aid, f"worker err {str(e)[:80]}")
            for _ in range(30):
                if holder["stop"]: break
                time.sleep(1)
    th = threading.Thread(target=worker, daemon=True)
    holder["th"] = th
    FARM_THREADS[aid] = holder
    th.start()

def resume_farms():
    for a in storage.list_accounts():
        if a.get("farm_running"):
            start_farm_thread(a["id"])

# ---------------- CODE WATCHER (auto redeem) ----------------
CODE_RE = __import__("re").compile(r"FARM-[A-Z0-9]{3,}")

def code_watcher_thread():
    from telethon import events
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    import asyncio as _a
    def run():
        time.sleep(15)
        while not WATCHER["stop"]:
            try:
                accs = storage.list_accounts()
                if not accs:
                    time.sleep(60); continue
                # dung session cua acc dau tien de listen
                sess = accs[0]["session"]
                client = TelegramClient(StringSession(sess), 2040, "b18441a1ff607e10a989891a5462e627")
                client.connect()
                if not client.is_user_authorized():
                    client.disconnect(); time.sleep(120); continue
                bot = client.get_entity("ghostfarmx_bot")
                # backfill 30 msg
                for msg in client.iter_messages(bot, limit=30):
                    if not msg.text: continue
                    for code in CODE_RE.findall(msg.text):
                        process_code(code)
                @client.on(events.NewMessage(chats=bot))
                async def on_msg(ev):
                    txt = ev.message.text or ""
                    for code in CODE_RE.findall(txt):
                        process_code(code)
                client.loop.run_until_complete(client.disconnected)
                client.disconnect()
            except Exception as e:
                print(f"[watcher] {e}")
                time.sleep(60)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    WATCHER["thread"] = t

def process_code(code):
    """redeem code vao tat ca acc dang farm"""
    accs = [a for a in storage.list_accounts() if a.get("farm_running")]
    if not accs: return
    for a in accs:
        if storage.is_code_used(code, a["id"]): continue
        try:
            initdata = get_initdata_from_session(a["session"], ref=REF_CODE)
            if not initdata: continue
            gf = GF(initdata)
            ok, msg = gf.claim_promo(code)
            storage.add_code(code, a["id"], ok, msg)
            storage.log_activity(a["id"], f"auto-code {code} {'OK' if ok else msg}")
        except Exception as e:
            storage.add_code(code, a["id"], False, str(e)[:80])

# ---------------- BOOTSTRAP ----------------
def build_app():
    storage.init()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    # callbacks
    app.add_handler(CallbackQueryHandler(acc_list_cb, pattern=r"^acc_list$"))
    app.add_handler(CallbackQueryHandler(acc_refresh_cb, pattern=r"^acc_refresh:"))
    app.add_handler(CallbackQueryHandler(acc_toggle_cb, pattern=r"^acc_toggle:"))
    app.add_handler(CallbackQueryHandler(acc_del_cb, pattern=r"^acc_del:"))
    app.add_handler(CallbackQueryHandler(acc_bank_cb, pattern=r"^acc_bank:"))
    app.add_handler(CallbackQueryHandler(acc_wd_do_cb, pattern=r"^acc_wd_do:"))
    app.add_handler(CallbackQueryHandler(acc_cv_cb, pattern=r"^acc_cv:"))
    app.add_handler(CallbackQueryHandler(acc_cb, pattern=r"^acc(_add)?:"))
    app.add_handler(CallbackQueryHandler(farm_cb, pattern=r"^farm_all:"))
    app.add_handler(CallbackQueryHandler(act_cb, pattern=r"^act:"))
    app.add_handler(CallbackQueryHandler(act_list_cb, pattern=r"^act_list$"))
    app.add_handler(CallbackQueryHandler(set_cb, pattern=r"^set_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    return app

