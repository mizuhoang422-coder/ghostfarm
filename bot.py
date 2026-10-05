import os, time, json, asyncio, threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import storage
from farm_engine import GF, get_initdata_from_session, get_me_from_session, farm_tick, task_tick

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_PASS = os.environ.get("ADMIN_PASS", "ghostfarm2026").strip()
REF_CODE = os.environ.get("REF_CODE", "").strip()

FARM_THREADS = {}

def is_authed(ctx):
    return ctx.user_data.get("authed") is True

def auth_kb():
    return ReplyKeyboardMarkup([["🔑 Nhập key"]], resize_keyboard=True)

def main_kb():
    return ReplyKeyboardMarkup([
        ["👤 Tài khoản", "🌾 Farm"],
        ["💰 Ví", "📊 Hoạt động"],
        ["🎁 Mã code", "⚙️ Cài đặt"],
    ], resize_keyboard=True)

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authed(ctx):
        await update.message.reply_text(
            "🌾 *GhostFarm Manager*\n\n"
            "Bot này yêu cầu key để sử dụng.\n"
            "Nhập /key <password> hoặc bấm nút dưới.",
            parse_mode="Markdown", reply_markup=auth_kb())
        return
    await update.message.reply_text("🌾 Menu chính", reply_markup=main_kb())

async def cmd_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    pwd = args[0] if args else ""
    if not pwd:
        await update.message.reply_text("Dùng: `/key ghostfarm2026`", parse_mode="Markdown")
        return
    if pwd != ADMIN_PASS:
        await update.message.reply_text("❌ Sai key.")
        return
    ctx.user_data["authed"] = True
    await update.message.reply_text("✅ Đã mở khoá.", reply_markup=main_kb())

async def msg_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = (update.message.text or "").strip()
    if txt == "🔑 Nhập key":
        await update.message.reply_text("Nhập: `/key <password>`", parse_mode="Markdown")
        return
    if is_authed(ctx):
        await handle_menu(update, ctx, txt)
        return
    await update.message.reply_text("Cần nhập key: `/key <password>`", parse_mode="Markdown")

async def handle_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE, txt):
    if txt == "👤 Tài khoản":
        await accounts_panel(update, ctx)
    elif txt == "🌾 Farm":
        await farm_panel(update, ctx)
    elif txt == "💰 Ví":
        await wallet_panel(update, ctx)
    elif txt == "📊 Hoạt động":
        await activity_panel(update, ctx)
    elif txt == "🎁 Mã code":
        await promo_panel(update, ctx)
    elif txt == "⚙️ Cài đặt":
        await settings_panel(update, ctx)

# ---------- accounts ----------
async def accounts_panel(update, ctx):
    accs = storage.list_accounts()
    kb = []
    for a in accs:
        run = "▶️" if a.get("farm_running") else "⏸"
        kb.append([InlineKeyboardButton(f"{run} #{a['id']} {a.get('name','?')[:20]}", callback_data=f"acc:{a['id']}")])
    kb.append([InlineKeyboardButton("➕ Thêm acc (session)", callback_data="acc_add:session")])
    kb.append([InlineKeyboardButton("➕ Thêm acc (OTP)", callback_data="acc_add:otp")])
    text = f"👤 *Tài khoản* ({len(accs)})\n"
    if not accs: text += "\n_Chưa có acc nào._"
    await update.message.reply_text(text, parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(kb))

async def acc_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    data = q.data
    if data.startswith("acc:"):
        aid = int(data.split(":")[1])
        await acc_detail(q, aid)
    elif data.startswith("acc_add:"):
        mode = data.split(":")[1]
        ctx.user_data["add_mode"] = mode
        ctx.user_data["add_step"] = "session" if mode=="session" else "phone"
        if mode == "session":
            await q.edit_message_text("📥 Gửi *StringSession* vào chat.\n"
                                      "Lấy từ: `python get_session.py` hoặc tool của bạn.",
                                      parse_mode="Markdown")
        else:
            await q.edit_message_text("📱 Gửi số điện thoại dạng `+84xxxxxxxxx`", parse_mode="Markdown")

async def acc_detail(q, aid):
    a = storage.get_account(aid)
    if not a:
        await q.edit_message_text("❌ Acc không tồn tại"); return
    try:
        initdata = await asyncio.to_thread(get_initdata_from_session, a["session"], ref=REF_CODE)
        gf = GF(initdata) if initdata else None
    except Exception as e:
        gf = None
    prof = gf.me() if gf else {}
    run = "▶️ Đang farm" if a.get("farm_running") else "⏸ Dừng"
    text = (f"👤 *Acc #{a['id']}* — {a.get('name','?')}\n"
            f"UID: `{a.get('uid')}`\n"
            f"Trạng thái: {run}\n")
    if prof:
        text += (f"🪙 Coins: `{prof.get('coins',0)}`  💎 Gems: `{prof.get('gems',0)}`\n"
                 f"💵 USDT: `{prof.get('usdt',0)}`\n"
                 f"Lv: {prof.get('level',1)}  XP: {prof.get('xp',0)}/{prof.get('xpMax',0)}\n")
    kb = [
        [InlineKeyboardButton(("⏸ Dừng farm" if a.get("farm_running") else "▶️ Bật farm"),
                              callback_data=f"acc_toggle:{aid}")],
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"acc:{aid}"),
         InlineKeyboardButton("🗑 Xoá", callback_data=f"acc_del:{aid}")],
        [InlineKeyboardButton("💰 Rút USDT", callback_data=f"acc_wd:{aid}"),
         InlineKeyboardButton("💱 Đổi coin→gem", callback_data=f"acc_cv:{aid}")],
        [InlineKeyboardButton("🏦 Cài bank", callback_data=f"acc_bank:{aid}")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="acc_list")],
    ]
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def acc_list_cb(update, ctx):
    q = update.callback_query; await q.answer()
    accs = storage.list_accounts()
    kb = []
    for a in accs:
        run = "▶️" if a.get("farm_running") else "⏸"
        kb.append([InlineKeyboardButton(f"{run} #{a['id']} {a.get('name','?')[:20]}", callback_data=f"acc:{a['id']}")])
    kb.append([InlineKeyboardButton("➕ Thêm acc (session)", callback_data="acc_add:session")])
    kb.append([InlineKeyboardButton("➕ Thêm acc (OTP)", callback_data="acc_add:otp")])
    await q.edit_message_text(f"👤 *Tài khoản* ({len(accs)})", parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup(kb))

async def acc_toggle_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    a = storage.get_account(aid)
    new = 0 if a.get("farm_running") else 1
    storage.update_account(aid, farm_running=new)
    if new:
        start_farm_thread(aid)
    await acc_detail(q, aid)

async def acc_del_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    storage.delete_account(aid)
    if aid in FARM_THREADS:
        FARM_THREADS[aid]["stop"] = True
        FARM_THREADS.pop(aid, None)
    await acc_list_cb(update, ctx)

# ---------- farm ----------
async def farm_panel(update, ctx):
    accs = storage.list_accounts()
    running = sum(1 for a in accs if a.get("farm_running"))
    kb = [
        [InlineKeyboardButton("▶️ Bật tất cả", callback_data="farm_all:1"),
         InlineKeyboardButton("⏸ Dừng tất cả", callback_data="farm_all:0")],
        [InlineKeyboardButton("📊 Trạng thái farm", callback_data="farm_status")],
    ]
    await update.message.reply_text(
        f"🌾 *Farm Panel*\nTổng acc: {len(accs)}\nĐang farm: {running}",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def farm_cb(update, ctx):
    q = update.callback_query; await q.answer()
    if q.data == "farm_all:1":
        for a in storage.list_accounts():
            storage.update_account(a["id"], farm_running=1)
            start_farm_thread(a["id"])
        await q.edit_message_text("✅ Đã bật farm tất cả acc.")
    elif q.data == "farm_all:0":
        for a in storage.list_accounts():
            storage.update_account(a["id"], farm_running=0)
            if a["id"] in FARM_THREADS:
                FARM_THREADS[a["id"]]["stop"] = True
                FARM_THREADS.pop(a["id"], None)
        await q.edit_message_text("⏸ Đã dừng farm tất cả.")
    elif q.data == "farm_status":
        accs = storage.list_accounts()
        lines = ["🌾 *Farm Status*"]
        for a in accs:
            st = "▶️" if a.get("farm_running") else "⏸"
            lines.append(f"{st} #{a['id']} {a.get('name','?')[:18]}")
        await q.edit_message_text("\n".join(lines), parse_mode="Markdown")

# ---------- wallet ----------
async def wallet_panel(update, ctx):
    accs = storage.list_accounts()
    kb = []
    for a in accs:
        kb.append([InlineKeyboardButton(f"💰 #{a['id']} {a.get('name','?')[:18]}", callback_data=f"acc_wd:{a['id']}")])
    if not accs:
        await update.message.reply_text("Chưa có acc nào.")
        return
    await update.message.reply_text("💰 *Ví* — chọn acc:", parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(kb))

async def acc_wd_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    a = storage.get_account(aid)
    bank = f"{a.get('bank_name','-')} | {a.get('bank_ctk','-')} | {a.get('bank_stk','-')}"
    kb = [
        [InlineKeyboardButton("🏦 Cài bank", callback_data=f"acc_bank:{aid}")],
        [InlineKeyboardButton("💸 Rút USDT", callback_data=f"acc_wd_do:{aid}")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data=f"acc:{aid}")],
    ]
    await q.edit_message_text(
        f"💰 *Ví acc #{aid}*\n"
        f"Bank: `{bank}`\n\nChọn hành động:",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def acc_bank_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    ctx.user_data["bank_for"] = aid
    ctx.user_data["bank_step"] = "name"
    ctx.user_data["bank_data"] = {}
    await q.edit_message_text(
        f"🏦 *Cài Bank cho acc #{aid}*\n\nGửi lần lượt theo mẫu:\n"
        "`Tên ngân hàng|CTK|STK`\n"
        "Ví dụ: `Vietcombank|NGUYEN VAN A|1234567890`",
        parse_mode="Markdown")

async def acc_wd_do_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    a = storage.get_account(aid)
    if not a.get("bank_stk"):
        await q.edit_message_text("⚠️ Chưa cài bank. Bấm Cài bank trước.")
        return
    ctx.user_data["wd_for"] = aid
    ctx.user_data["wd_step"] = "amount"
    await q.edit_message_text(
        f"💸 Nhập số *USDT* muốn rút từ acc #{aid}.\nSố dư hiện có — bấm Refresh để xem trước.",
        parse_mode="Markdown")

async def acc_cv_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    ctx.user_data["cv_for"] = aid
    ctx.user_data["cv_step"] = "amount"
    await q.edit_message_text(
        f"💱 Nhập số *coin* muốn đổi sang *gem* (acc #{aid}).",
        parse_mode="Markdown")

# ---------- activity ----------
async def activity_panel(update, ctx):
    accs = storage.list_accounts()
    kb = []
    for a in accs:
        kb.append([InlineKeyboardButton(f"📊 #{a['id']} {a.get('name','?')[:18]}", callback_data=f"act:{a['id']}")])
    if not accs:
        await update.message.reply_text("Chưa có acc nào.")
        return
    await update.message.reply_text("📊 *Hoạt động* — chọn acc:", parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(kb))

async def act_cb(update, ctx):
    q = update.callback_query; await q.answer()
    aid = int(q.data.split(":")[1])
    acts = storage.get_activity(aid, 20)
    lines = [f"📊 *Acc #{aid} — 20 hoạt động gần nhất*"]
    if not acts:
        lines.append("_Chưa có hoạt động._")
    for r in acts:
        t = time.strftime("%H:%M:%S", time.localtime(r["ts"]))
        lines.append(f"`{t}` {r['msg']}")
    await q.edit_message_text("\n".join(lines), parse_mode="Markdown",
                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="act_list")]]))

async def act_list_cb(update, ctx):
    q = update.callback_query; await q.answer()
    accs = storage.list_accounts()
    kb = [[InlineKeyboardButton(f"📊 #{a['id']} {a.get('name','?')[:18]}", callback_data=f"act:{a['id']}")] for a in accs]
    await q.edit_message_text("📊 Chọn acc:", reply_markup=InlineKeyboardMarkup(kb))

# ---------- promo ----------
async def promo_panel(update, ctx):
    ctx.user_data["promo_wait"] = True
    await update.message.reply_text(
        "🎁 *Nhập mã code* (vd FARM-4XT5).\nBot sẽ tự redeem vào tất cả acc đang bật farm.",
        parse_mode="Markdown")

# ---------- settings ----------
async def settings_panel(update, ctx):
    kb = [
        [InlineKeyboardButton("🔑 Đổi key bot", callback_data="set_key")],
        [InlineKeyboardButton("📋 List acc IDs", callback_data="set_list")],
    ]
    await update.message.reply_text("⚙️ *Cài đặt*", parse_mode="Markdown",
                                    reply_markup=InlineKeyboardMarkup(kb))

async def set_cb(update, ctx):
    q = update.callback_query; await q.answer()
    if q.data == "set_key":
        ctx.user_data["change_key"] = True
        await q.edit_message_text("Gửi key mới dạng: `/newkey <password>`")
    elif q.data == "set_list":
        accs = storage.list_accounts()
        lines = ["📋 *Acc IDs*"]
        for a in accs:
            lines.append(f"#{a['id']} | uid={a.get('uid')} | {a.get('name','?')}")
        await q.edit_message_text("\n".join(lines), parse_mode="Markdown")

# ---------- text router ----------
async def text_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = (update.message.text or "").strip()
    if not is_authed(ctx):
        if txt == "🔑 Nhập key":
            await update.message.reply_text("Dùng: `/key <password>`", parse_mode="Markdown")
            return
        await update.message.reply_text("Cần `/key <password>` để mở khoá.", parse_mode="Markdown")
        return

    # menu buttons
    menu = {"👤 Tài khoản","🌾 Farm","💰 Ví","📊 Hoạt động","🎁 Mã code","⚙️ Cài đặt"}
    if txt in menu:
        await handle_menu(update, ctx, txt)
        return

    # add account flows
    step = ctx.user_data.get("add_step")
    if step == "session":
        ctx.user_data["pending_session"] = txt
        ctx.user_data["add_step"] = "name"
        await update.message.reply_text("Đã nhận session. Gửi *tên gợi nhớ* cho acc này:", parse_mode="Markdown")
        return
    if step == "name":
        session = ctx.user_data.pop("pending_session", "")
        name = txt[:40]
        try:
            info = await asyncio.to_thread(get_me_from_session, session)
        except Exception as e:
            await update.message.reply_text(f"❌ Session lỗi: {e}")
            ctx.user_data.pop("add_step", None)
            return
        if not info:
            await update.message.reply_text("❌ Session không hợp lệ.")
            ctx.user_data.pop("add_step", None)
            return
        aid = storage.add_account(info.get("username") or "?", session, info["uid"], name)
        ctx.user_data.pop("add_step", None)
        await update.message.reply_text(f"✅ Đã thêm acc #{aid} — uid={info['uid']}", reply_markup=main_kb())
        return
    if step == "phone":
        phone = txt
        ctx.user_data["pending_phone"] = phone
        await update.message.reply_text(
            "📱 Gửi OTP sẽ được gửi tới Telegram của số này.\n"
            "*Lưu ý:* flow OTP cần chạy qua Telethon tương tác — trên bot Render không hỗ trợ.\n"
            "Vui lòng dùng session. Hoặc reply `skip` để huỷ.",
            parse_mode="Markdown")
        ctx.user_data.pop("add_step", None)
        return

    # bank setup
    if ctx.user_data.get("bank_for"):
        aid = ctx.user_data.pop("bank_for")
        parts = txt.split("|")
        if len(parts) != 3:
            await update.message.reply_text("Sai format. Dùng: `Tên|CTK|STK`", parse_mode="Markdown")
            return
        storage.update_account(aid, bank_name=parts[0].strip(), bank_ctk=parts[1].strip(), bank_stk=parts[2].strip())
        await update.message.reply_text(f"✅ Đã cài bank cho acc #{aid}.")
        return

    # withdraw
    if ctx.user_data.get("wd_for"):
        aid = ctx.user_data.pop("wd_for")
        try: amt = float(txt)
        except: await update.message.reply_text("Số không hợp lệ."); return
        a = storage.get_account(aid)
        initdata = await asyncio.to_thread(get_initdata_from_session, a["session"], ref=REF_CODE)
        if not initdata: await update.message.reply_text("❌ initData fail."); return
        gf = GF(initdata)
        # set bank first
        gf.set_address("VND", a.get("bank_stk",""), network="VND")
        s, j = gf.withdraw("VND", a.get("bank_stk",""), amt)
        storage.log_activity(aid, f"Rút {amt} USDT -> {s} {json.dumps(j, ensure_ascii=False)[:100]}")
        await update.message.reply_text(f"💸 Rút -> {s}\n`{json.dumps(j, ensure_ascii=False)[:200]}`", parse_mode="Markdown")
        return

    # convert
    if ctx.user_data.get("cv_for"):
        aid = ctx.user_data.pop("cv_for")
        try: amt = int(txt)
        except: await update.message.reply_text("Số không hợp lệ."); return
        a = storage.get_account(aid)
        initdata = await asyncio.to_thread(get_initdata_from_session, a["session"], ref=REF_CODE)
        if not initdata: await update.message.reply_text("❌ initData fail."); return
        gf = GF(initdata)
        s, j = gf.convert(amt)
        storage.log_activity(aid, f"Convert {amt} coins -> {s}")
        await update.message.reply_text(f"💱 Convert -> {s}\n`{json.dumps(j, ensure_ascii=False)[:200]}`", parse_mode="Markdown")
        return

    # promo
    if ctx.user_data.pop("promo_wait", False):
        code = txt.strip().upper()
        accs = [a for a in storage.list_accounts() if a.get("farm_running")]
        if not accs:
            await update.message.reply_text("Không có acc nào đang farm.")
            return
        results = []
        for a in accs:
            try:
                initdata = await asyncio.to_thread(get_initdata_from_session, a["session"], ref=REF_CODE)
                if not initdata: results.append(f"#{a['id']} initData fail"); continue
                gf = GF(initdata)
                ok, msg = gf.claim_promo(code)
                results.append(f"#{a['id']} {'✅' if ok else '❌'} {msg}")
                storage.log_activity(a["id"], f"Promo {code}: {'ok' if ok else msg}")
            except Exception as e:
                results.append(f"#{a['id']} err {str(e)[:40]}")
        await update.message.reply_text("🎁 Promo:\n" + "\n".join(results))
        return

    await update.message.reply_text("Dùng menu hoặc /start.")

# ---------- farm threads ----------
def start_farm_thread(aid):
    if aid in FARM_THREADS and FARM_THREADS[aid]["th"].is_alive():
        return
    holder = {"stop": False}
    def worker():
        last_refresh = 0
        while not holder["stop"]:
            try:
                a = storage.get_account(aid)
                if not a or not a.get("farm_running"):
                    break
                initdata = get_initdata_from_session(a["session"], ref=REF_CODE)
                if not initdata:
                    storage.log_activity(aid, "initData fail")
                    time.sleep(60); continue
                gf = GF(initdata)
                # task tick
                try:
                    ts = task_tick(gf, a.get("config") or {})
                    if ts["claims"]: storage.log_activity(aid, f"tasks: +{ts['reward']} coin ({ts['claims']} claim)")
                except Exception as e:
                    storage.log_activity(aid, f"task err {str(e)[:60]}")
                # farm tick
                try:
                    fs = farm_tick(gf, a.get("config") or {})
                    if fs["planted"] or fs["harvested"]:
                        storage.log_activity(aid, f"farm: plant {fs['planted']} harvest {fs['harvested']} +{fs['earned_gems']} gems")
                except Exception as e:
                    storage.log_activity(aid, f"farm err {str(e)[:60]}")
                # refresh profile every 5min
                if time.time() - last_refresh > 300:
                    try:
                        prof = gf.me()
                        storage.update_account(aid, last_state=json.dumps(prof))
                        last_refresh = time.time()
                    except: pass
            except Exception as e:
                storage.log_activity(aid, f"worker err {str(e)[:80]}")
            # sleep 30s or until stop
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

# ---------- app bootstrap ----------
def build_app():
    storage.init()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("key", cmd_key))
    app.add_handler(CallbackQueryHandler(acc_cb, pattern=r"^acc:"))
    app.add_handler(CallbackQueryHandler(acc_list_cb, pattern=r"^acc_list$"))
    app.add_handler(CallbackQueryHandler(acc_toggle_cb, pattern=r"^acc_toggle:"))
    app.add_handler(CallbackQueryHandler(acc_del_cb, pattern=r"^acc_del:"))
    app.add_handler(CallbackQueryHandler(acc_wd_cb, pattern=r"^acc_wd:"))
    app.add_handler(CallbackQueryHandler(acc_wd_do_cb, pattern=r"^acc_wd_do:"))
    app.add_handler(CallbackQueryHandler(acc_bank_cb, pattern=r"^acc_bank:"))
    app.add_handler(CallbackQueryHandler(acc_cv_cb, pattern=r"^acc_cv:"))
    app.add_handler(CallbackQueryHandler(farm_cb, pattern=r"^farm_"))
    app.add_handler(CallbackQueryHandler(act_cb, pattern=r"^act:"))
    app.add_handler(CallbackQueryHandler(act_list_cb, pattern=r"^act_list$"))
    app.add_handler(CallbackQueryHandler(set_cb, pattern=r"^set_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    return app
