import os, time, json, asyncio, threading, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import storage
from ad_watcher import watch_one_ad
from farm_engine import (fetch_initdata_sync, GF, farm_tick, task_tick, fetch_initdata, fetch_initdata_with_ref, STATE, CROPS, st_set, st_get,
                         get_me_from_session, otp_send_code, otp_sign_in, otp_sign_in_2fa)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()



CROP_EMOJI = {"wheat":"\U0001f33e","barley":"\U0001f33f","corn":"\U0001f33d","tomato":"\U0001f345","eggplant":"\U0001f346","pumpkin":"\U0001f383"}

ADMIN_UID = 8249205817
REF_CODE = os.environ.get("REF_CODE", "").strip()
WORKERS = {}
WATCHER = {"stop": False}
AS_STATE = {}   # add session state
OTP_STATE = {}
UI_WAIT = {}    # input waiting flags
CODE_RE = re.compile(r"FARM-[A-Z0-9]{3,}")
IDATA_TTL = 12 * 3600

def is_admin(uid): return uid == ADMIN_UID

def kb_main(uid=None):
    rows = []
    rows.append([
        InlineKeyboardButton("➕ Thêm acc (OTP)", callback_data="add_otp"),
        InlineKeyboardButton("🔑 Thêm acc (Session)", callback_data="add_session"),
    ])
    rows.append([InlineKeyboardButton("📋 Danh sách acc", callback_data="list")])
    rows.append([
        InlineKeyboardButton("📊 Xem trực tiếp", callback_data="live"),
        InlineKeyboardButton("🎁 Quản lý code", callback_data="codes"),
    ])
    rows.append([
        InlineKeyboardButton("▶️ Bật farm tất cả", callback_data="start_all"),
        InlineKeyboardButton("⏹ Tắt farm tất cả", callback_data="stop_all"),
    ])
    rows.append([
        InlineKeyboardButton("🌾 Chọn cây tất cả acc", callback_data="crop_bulk"),
    ])
    rows.append([
        InlineKeyboardButton("🔄 Làm mới tất cả", callback_data="rf_all"),
        InlineKeyboardButton("🗑 Xoá acc", callback_data="del_list"),
    ])
    return InlineKeyboardMarkup(rows)

def kb_panel(aid, a):
    run = a.get("farm_running")
    rb = InlineKeyboardButton("⏹ Dừng farm", callback_data=f"stop:{aid}") if run else InlineKeyboardButton("▶️ Bật farm", callback_data=f"start:{aid}")
    return InlineKeyboardMarkup([
        [rb],
        [InlineKeyboardButton("💰 Rút VND", callback_data=f"wd:{aid}"),
         InlineKeyboardButton("💱 Coin→Gem", callback_data=f"cv:{aid}")],
        [InlineKeyboardButton("🏦 Cài bank", callback_data=f"bank:{aid}"),
         InlineKeyboardButton("🔄 Làm mới", callback_data=f"rf:{aid}")],
        [InlineKeyboardButton("🗑 Xoá", callback_data=f"del:{aid}"),
         InlineKeyboardButton("⬅️ Quay lại", callback_data="list")],
    ])

def panel_text(aid):
    a = storage.get_account(aid)
    if not a: return "❌ Không tồn tại"
    prof = {}
    try:
        if a.get("last_state"): prof = json.loads(a["last_state"])
    except: pass
    run = "🟢 ĐANG CHẠY" if a.get("farm_running") else "🔴 ĐANG DỪNG"
    txt = (f"👤 <b>{a.get('name','?')}</b>\n"
           f"📱 {a.get('phone','?')}\n"
           f"🆔 uid={a.get('uid','?')}\n"
           f"━━━━━━━━━━━━━━━━\n")
    if prof:
        txt += (f"🪙 Coins: <b>{prof.get('coins',0)}</b>\n"
                f"💎 Gems: <b>{prof.get('gems',0)}</b>\n"
                f"💵 USDT: <b>{prof.get('usdt',0)}</b>\n"
                f"⭐ Lv {prof.get('level',1)}  XP {prof.get('xp',0)}/{prof.get('xpMax',0)}\n")
    txt += (f"━━━━━━━━━━━━━━━━\n"
            f"🏦 {a.get('bank_name','-')} | {a.get('bank_ctk','-')} | {a.get('bank_stk','-')}\n"
            f"📊 Trạng thái: {run}")
    return txt

async def edit_or_send(update, ctx, text, kb=None):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
            return
        except Exception: pass
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u.id):
        await update.message.reply_text(f"⛔ Bot riêng tư.\nID của bạn: <code>{u.id}</code>", parse_mode="HTML")
        return
    accs = storage.list_accounts()
    running = sum(1 for a in accs if a.get("farm_running"))
    codes = storage.list_codes(999)
    txt = (f"🌾 <b>GHOSTFARM MANAGER</b>\n"
           f"━━━━━━━━━━━━━━━━\n"
           f"👤 Tài khoản: <b>{len(accs)}</b>\n"
           f"▶️ Đang farm: <b>{running}</b>\n"
           f"🎁 Code đã nhận: <b>{len(codes)}</b>\n"
           f"━━━━━━━━━━━━━━━━\n"
           f"<i>Chọn chức năng bên dưới</i>")
    await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_main(u.id))

async def cb_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_admin(q.from_user.id):
        try: await q.answer("⛔")
        except: pass
        return
    data = q.data
    try:
        await q.answer()
    except Exception:
        pass
    try:
        await _cb_router_inner(q, data, ctx)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[CB ERROR] data={data} err={e}\n{tb}")
        try:
            await q.edit_message_text(
                "❌ <b>LOI CALLBACK</b>\n"
                f"<code>data={data}</code>\n"
                f"<code>{str(e)[:300]}</code>\n\n"
                "Check Render logs.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Menu", callback_data="menu")]]))
        except Exception:
            pass


async def _cb_router_inner(q, data, ctx):

    if data == "menu":
        accs = storage.list_accounts()
        running = sum(1 for a in accs if a.get("farm_running"))
        codes = storage.list_codes(999)
        txt = (f"🌾 <b>GHOSTFARM MANAGER</b>\n"
               f"━━━━━━━━━━━━━━━━\n"
               f"👤 Tài khoản: <b>{len(accs)}</b>\n"
               f"▶️ Đang farm: <b>{running}</b>\n"
               f"🎁 Code đã nhận: <b>{len(codes)}</b>\n"
               f"━━━━━━━━━━━━━━━━\n"
               f"<i>Chọn chức năng bên dưới</i>")
        await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb_main(q.from_user.id))
        return

    if data == "list":
        accs = storage.list_accounts()
        rows = []
        for a in accs:
            mark = "🟢" if a.get("farm_running") else "🔴"
            rows.append([InlineKeyboardButton(f"{mark} {a.get('name','?')} | uid={a.get('uid','?')}",
                                              callback_data=f"acc:{a['id']}")])
        rows.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")])
        await q.edit_message_text(f"📋 <b>DANH SÁCH ACC</b> ({len(accs)})",
                                   parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith("acc:"):
        aid = int(data.split(":")[1])
        await q.edit_message_text(panel_text(aid), parse_mode="HTML",
                                   reply_markup=kb_panel(aid, storage.get_account(aid)))
        return

    if data.startswith("crop:"):
        aid = int(data.split(":")[1])
        await q.edit_message_text(crop_text(aid), parse_mode="HTML",
                                  reply_markup=kb_crop(aid))
        return

    if data.startswith("crop_tog:"):
        _, aid_s, crop = data.split(":")
        aid = int(aid_s)
        allowed = storage.get_crop_pref(aid)
        if allowed is None: allowed = list(CROPS)
        if crop in allowed:
            allowed.remove(crop)
        else:
            allowed.append(crop)
        storage.set_crop_pref(aid, allowed)
        await q.edit_message_text(crop_text(aid), parse_mode="HTML",
                                  reply_markup=kb_crop(aid))
        return

    if data.startswith("crop_all:"):
        aid = int(data.split(":")[1])
        storage.set_crop_pref(aid, list(CROPS))
        await q.edit_message_text(crop_text(aid), parse_mode="HTML",
                                  reply_markup=kb_crop(aid))
        return

    if data.startswith("crop_none:"):
        aid = int(data.split(":")[1])
        storage.set_crop_pref(aid, [])
        await q.edit_message_text(crop_text(aid), parse_mode="HTML",
                                  reply_markup=kb_crop(aid))
        return

    if data == "crop_bulk":
        # chon crop cho tat ca acc cung luc
        rows = []
        line = []
        # dung acc dau tien lam mau
        accs = storage.list_accounts()
        if not accs:
            await q.edit_message_text("Chưa có acc."); return
        # lay pref acc dau tien
        allowed = storage.get_crop_pref(accs[0]["id"])
        if allowed is None: allowed = list(CROPS)
        for crop in CROPS:
            mark = "✅" if crop in allowed else "⬜"
            line.append(InlineKeyboardButton(f"{mark}{CROP_EMOJI.get(crop,'🌱')} {crop}", callback_data=f"crop_bulk_tog:{crop}"))
            if len(line) == 2:
                rows.append(line); line = []
        if line: rows.append(line)
        rows.append([InlineKeyboardButton("✅ Chọn tất cả", callback_data="crop_bulk_all"),
                     InlineKeyboardButton("❌ Bỏ hết", callback_data="crop_bulk_none")])
        rows.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")])
        await q.edit_message_text(
            "🌾 <b>CHỌN CÂY CHO TẤT CẢ ACC</b>\nBot sẽ set cùng 1 loại cho mọi acc.",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith("crop_bulk_tog:"):
        crop = data.split(":")[1]
        accs = storage.list_accounts()
        if not accs: return
        cur = storage.get_crop_pref(accs[0]["id"]) or list(CROPS)
        if crop in cur: cur.remove(crop)
        else: cur.append(crop)
        for a in accs:
            storage.set_crop_pref(a["id"], cur)
        # re-render
        rows = []
        line = []
        for c in CROPS:
            mark = "✅" if c in cur else "⬜"
            line.append(InlineKeyboardButton(f"{mark}{CROP_EMOJI.get(c,'🌱')} {c}", callback_data=f"crop_bulk_tog:{c}"))
            if len(line) == 2:
                rows.append(line); line = []
        if line: rows.append(line)
        rows.append([InlineKeyboardButton("✅ Chọn tất cả", callback_data="crop_bulk_all"),
                     InlineKeyboardButton("❌ Bỏ hết", callback_data="crop_bulk_none")])
        rows.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")])
        await q.edit_message_text(
            f"🌾 <b>CHỌN CÂY CHO TẤT CẢ ACC</b>\nĐang cho phép: <b>{len(cur)}/{len(CROPS)}</b>",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data == "crop_bulk_all":
        for a in storage.list_accounts():
            storage.set_crop_pref(a["id"], list(CROPS))
        await q.edit_message_text("✅ Set tất cả cây cho mọi acc.", reply_markup=kb_main(q.from_user.id))
        return

    if data == "crop_bulk_none":
        for a in storage.list_accounts():
            storage.set_crop_pref(a["id"], [])
        await q.edit_message_text("❌ Bỏ hết cây cho mọi acc.", reply_markup=kb_main(q.from_user.id))
        return

    if data.startswith("start:"):
        aid = int(data.split(":")[1])
        storage.update_account(aid, farm_running=1)
        start_worker(aid)
        await q.edit_message_text(panel_text(aid), parse_mode="HTML",
                                   reply_markup=kb_panel(aid, storage.get_account(aid)))
        return

    if data.startswith("stop:"):
        aid = int(data.split(":")[1])
        storage.update_account(aid, farm_running=0)
        if aid in WORKERS:
            WORKERS[aid]["stop"] = True
        await q.edit_message_text(panel_text(aid), parse_mode="HTML",
                                   reply_markup=kb_panel(aid, storage.get_account(aid)))
        return

    if data.startswith("rf:"):
        aid = int(data.split(":")[1])
        await q.edit_message_text("🔄 Đang làm mới...", parse_mode="HTML")
        ok = await refresh_initdata(aid)
        if ok:
            a = storage.get_account(aid)
            try:
                gf = GF(a["init_data"])
                prof = await asyncio.to_thread(gf.me)
                storage.update_account(aid, last_state=json.dumps(prof))
            except Exception: pass
        await q.edit_message_text(panel_text(aid), parse_mode="HTML",
                                   reply_markup=kb_panel(aid, storage.get_account(aid)))
        return

    if data.startswith("del:"):
        aid = int(data.split(":")[1])
        storage.delete_account(aid)
        if aid in WORKERS: WORKERS[aid]["stop"] = True
        accs = storage.list_accounts()
        rows = [[InlineKeyboardButton(f"{'🟢' if a.get('farm_running') else '🔴'} {a['name']}",
                                       callback_data=f"acc:{a['id']}")] for a in accs]
        rows.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")])
        await q.edit_message_text(f"📋 <b>DANH SÁCH ACC</b> ({len(accs)})",
                                   parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data == "del_list":
        accs = storage.list_accounts()
        rows = [[InlineKeyboardButton(f"🗑 {a['name']}", callback_data=f"del:{a['id']}")] for a in accs]
        rows.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")])
        await q.edit_message_text("🗑 Chọn acc để xoá:", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data == "start_all":
        accs = storage.list_accounts()
        n = 0
        for a in accs:
            storage.update_account(a["id"], farm_running=1)
            start_worker(a["id"])
            n += 1
        await q.edit_message_text(f"✅ Đã bật farm {n} acc.", reply_markup=kb_main(q.from_user.id))
        return

    if data == "stop_all":
        accs = storage.list_accounts()
        n = 0
        for a in accs:
            storage.update_account(a["id"], farm_running=0)
            if a["id"] in WORKERS:
                WORKERS[a["id"]]["stop"] = True
                WORKERS.pop(a["id"], None)
            n += 1
        await q.edit_message_text(f"⏹ Đã tắt farm {n} acc.", reply_markup=kb_main(q.from_user.id))
        return

    if data == "rf_all":
        await q.edit_message_text("🔄 Đang refresh tất cả...")
        accs = storage.list_accounts()
        for a in accs:
            await refresh_initdata(a["id"])
        await q.edit_message_text(f"✅ Đã refresh {len(accs)} acc.", reply_markup=kb_main(q.from_user.id))
        return

    if data == "live":
        accs = storage.list_accounts()
        out_lines = ["📊 <b>XEM TRỰC TIẾP</b>", "━" * 16]
        now = time.time()
        for a in accs:
            prof = {}
            try:
                if a.get("last_state"): prof = json.loads(a["last_state"])
            except Exception: pass
            aid = a["id"]
            mark = "🟢" if a.get("farm_running") else "🔴"
            coins = prof.get("coins", 0)
            gems = prof.get("gems", 0)
            st = st_get(aid)
            acts = storage.get_activity(aid, 1)
            last_str = ""
            if acts:
                dt = int(now - acts[0]["ts"])
                if dt < 60: last_str = f"{dt}s"
                elif dt < 3600: last_str = f"{dt//60}p"
                else: last_str = f"{dt//3600}h"
            out_lines.append("")
            out_lines.append(f"{mark} <b>{a['name']}</b>  🪙{coins} 💎{gems}")
            if st.get("farm"): out_lines.append(f"   🌾 {st['farm']}")
            if st.get("tasks"): out_lines.append(f"   📋 {st['tasks']}")
            if st.get("ad"): out_lines.append(f"   🎬 {st['ad']}")
            if last_str: out_lines.append(f"   ⏱ {last_str} trước")
        txt = "\n".join(out_lines)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Cập nhật", callback_data="live")],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")]
        ])
        try:
            await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            await q.edit_message_text("⚠️ Loi live panel: " + str(e)[:100] + "\n\n" + txt[:500], reply_markup=kb)
        return

    if data == "codes":
        codes = storage.list_codes(60)
        lines = [f"🎁 <b>QUẢN LÝ CODE</b> ({len(codes)})", "━━━━━━━━━━━━━━━━"]
        if not codes: lines.append("<i>Trống.</i>")
        for r in codes[:40]:
            t = time.strftime("%d/%m %H:%M", time.localtime(r["ts"]))
            mark = "✅" if r["ok"] else "❌"
            lines.append(f"{mark} <code>{r['code']}</code> → acc#{r['acc_id']} {t}")
        await q.edit_message_text("\n".join(lines), parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")]]))
        return

    if data == "add_session":
        AS_STATE[q.from_user.id] = {"step": "name"}
        await q.edit_message_text(
            "🔑 <b>THÊM ACC (SESSION)</b>\n\n"
            "Bước 1/3: Nhập <b>tên</b> cho acc (chữ/số/gạch dưới, 1-20 ký tự).\n\n"
            "Gõ /cancel để huỷ.", parse_mode="HTML")
        return

    if data == "add_otp":
        OTP_STATE[q.from_user.id] = {"step": "name"}
        await q.edit_message_text(
            "📱 <b>THÊM ACC (OTP)</b>\n\n"
            "Bước 1/3: Nhập <b>tên</b> cho acc (chữ/số/gạch dưới).\n\n"
            "Gõ /cancel để huỷ.", parse_mode="HTML")
        return

    if data.startswith("wd:"):
        aid = int(data.split(":")[1])
        a = storage.get_account(aid)
        if not a.get("bank_stk"):
            await q.edit_message_text("⚠️ Chưa cài bank. Bấm 🏦 Cài bank trước.",
                                       reply_markup=kb_panel(aid, a))
            return
        UI_WAIT[q.from_user.id] = {"type": "wd", "aid": aid}
        await q.edit_message_text(f"💰 Nhập số <b>USDT</b> muốn rút (acc {a['name']}):", parse_mode="HTML")
        return

    if data.startswith("cv:"):
        aid = int(data.split(":")[1])
        UI_WAIT[q.from_user.id] = {"type": "cv", "aid": aid}
        a = storage.get_account(aid)
        await q.edit_message_text(f"💱 Nhập số <b>coin</b> muốn đổi sang gem (acc {a['name']}):", parse_mode="HTML")
        return

    if data.startswith("bank:"):
        aid = int(data.split(":")[1])
        UI_WAIT[q.from_user.id] = {"type": "bank", "aid": aid}
        await q.edit_message_text(f"🏦 Nhập bank theo mẫu:\n<code>Tên ngân hàng|CTK|STK</code>\nVD: <code>Vietcombank|NGUYEN VAN A|1234567890</code>",
                                   parse_mode="HTML")
        return
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not is_admin(u.id): return
    txt = (update.message.text or "").strip()

    # add session flow
    st = AS_STATE.get(u.id)
    if st:
        step = st.get("step")
        if step == "name":
            if not re.match(r"^[A-Za-z0-9_]{1,20}$", txt):
                await update.message.reply_text("Tên chỉ chữ/số/_, 1-20 ký tự. Nhập lại:"); return
            if storage.get_account_by_name(txt):
                await update.message.reply_text("Tên đã tồn tại. Nhập tên khác:"); return
            st["name"] = txt; st["step"] = "phone"
            await update.message.reply_text("📱 Bước 2/3: Nhập SĐT (+84...):"); return
        if step == "phone":
            p = txt.replace(" ","").replace("-","")
            if not p.startswith("+") or not p[1:].isdigit():
                await update.message.reply_text("SĐT phải dạng +84xxxxxxxxx. Nhập lại:"); return
            st["phone"] = p; st["step"] = "session"
            await update.message.reply_text("🔑 Bước 3/3: Paste <b>session string</b>:\n\n<i>Bot sẽ xoá tin này sau khi lưu.</i>", parse_mode="HTML")
            return
        if step == "session":
            try: await update.message.delete()
            except: pass
            if len(txt) < 100:
                await update.message.reply_text("Session quá ngắn. Nhập lại:"); return
            m = await update.message.reply_text("⏳ Đang kiểm tra session...")
            try: idata = await fetch_initdata_with_ref(txt, REF_CODE)
            except Exception: idata = None
            if not idata:
                await m.edit_text("❌ Session không hoạt động (không fetch được initData). Nhập lại hoặc /cancel:"); return
            info = await get_me_from_session(txt)
            name = st["name"]; phone = st["phone"]
            aid = storage.add_account(name, phone, txt, info["uid"] if info else 0)
            storage.update_account(aid, init_data=idata, init_ts=int(time.time()))
            AS_STATE.pop(u.id, None)
            await m.edit_text(f"✅ Đã thêm acc <b>{name}</b>\n📱 {phone}\n🔑 initData OK",
                              parse_mode="HTML", reply_markup=kb_main(u.id))
            return

    # OTP flow
    st = OTP_STATE.get(u.id)
    if st:
        step = st.get("step")
        if step == "name":
            if not re.match(r"^[A-Za-z0-9_]{1,20}$", txt):
                await update.message.reply_text("Tên chỉ chữ/số/_, 1-20. Nhập lại:"); return
            if storage.get_account_by_name(txt):
                await update.message.reply_text("Tên đã tồn tại:"); return
            st["name"] = txt; st["step"] = "phone"
            await update.message.reply_text("📱 Bước 2/3: Nhập SĐT (+84...):"); return
        if step == "phone":
            p = txt.replace(" ","").replace("-","")
            if not p.startswith("+") or not p[1:].isdigit():
                await update.message.reply_text("SĐT dạng +84xxxxxxxxx. Nhập lại:"); return
            st["phone"] = p
            m = await update.message.reply_text("⏳ Đang gửi OTP...")
            try:
                temp, chash = await otp_send_code(p)
                st["temp"] = temp; st["chash"] = chash; st["step"] = "code"
                await m.edit_text(f"📨 Đã gửi OTP tới {p}.\n\nBước 3/3: Nhập code OTP:", parse_mode="HTML")
            except Exception as e:
                await m.edit_text(f"❌ Gửi OTP fail: {str(e)[:150]}"); OTP_STATE.pop(u.id, None)
            return
        if step == "code":
            code = txt.replace(" ","").replace("-","")
            try:
                new_sess, status = await otp_sign_in(st["temp"], st["phone"], code, st.get("chash"))
            except Exception as e:
                await update.message.reply_text(f"❌ {str(e)[:150]}"); return
            if status == "2FA":
                st["step"] = "2fa"
                await update.message.reply_text("🔐 Acc có 2FA. Nhập mật khẩu 2FA:"); return
            if not new_sess:
                await update.message.reply_text(f"❌ OTP sai. Nhập lại code:"); return
            try:
                idata = await fetch_initdata_with_ref(new_sess, REF_CODE)
            except Exception: idata = None
            if not idata:
                await update.message.reply_text("❌ Không fetch được initData. Kiểm tra acc có block bot không."); OTP_STATE.pop(u.id, None); return
            info = await get_me_from_session(new_sess)
            aid = storage.add_account(st["name"], st["phone"], new_sess, info["uid"] if info else 0)
            storage.update_account(aid, init_data=idata, init_ts=int(time.time()))
            OTP_STATE.pop(u.id, None)
            await update.message.reply_text(f"✅ Đã thêm acc <b>{st['name']}</b>\n📱 {st['phone']}\n🔑 initData OK",
                                              parse_mode="HTML", reply_markup=kb_main(u.id))
            return
        if step == "2fa":
            try:
                new_sess, status = await otp_sign_in_2fa(st["temp"], txt)
            except Exception as e:
                await update.message.reply_text(f"❌ {str(e)[:150]}"); return
            if not new_sess:
                await update.message.reply_text("❌ 2FA sai. Nhập lại:"); return
            idata = await fetch_initdata_with_ref(new_sess, REF_CODE)
            info = await get_me_from_session(new_sess)
            aid = storage.add_account(st["name"], st["phone"], new_sess, info["uid"] if info else 0)
            storage.update_account(aid, init_data=idata, init_ts=int(time.time()), farm_running=1)
            try: start_worker(aid)
            except Exception: pass
            OTP_STATE.pop(u.id, None)
            await update.message.reply_text(f"✅ Đã thêm acc <b>{st['name']}</b> — farm đã bật", parse_mode="HTML", reply_markup=kb_main(u.id))
            return

    # UI_WAIT flows
    w = UI_WAIT.get(u.id)
    if w:
        t = w.get("type"); aid = w.get("aid")
        UI_WAIT.pop(u.id, None)
        a = storage.get_account(aid)
        if t == "bank":
            parts = txt.split("|")
            if len(parts) != 3:
                await update.message.reply_text("Sai format: `Tên|CTK|STK`", parse_mode="Markdown"); return
            storage.update_account(aid, bank_name=parts[0].strip(), bank_ctk=parts[1].strip(), bank_stk=parts[2].strip())
            await update.message.reply_text(f"✅ Bank acc {a['name']} lưu."); return
        if t == "wd":
            try: amt = float(txt)
            except: await update.message.reply_text("Số không hợp lệ."); return
            if not a.get("init_data"): await update.message.reply_text("❌ Acc chưa có initData. Refresh trước."); return
            try:
                gf = GF(a["init_data"])
                await asyncio.to_thread(gf.set_address, "VND", a["bank_stk"], "VND")
                s, j = await asyncio.to_thread(gf.withdraw, "VND", a["bank_stk"], amt)
                storage.log_activity(aid, f"Rút {amt} USDT -> {s}")
                await update.message.reply_text(f"💸 {s}\n<code>{json.dumps(j, ensure_ascii=False)[:200]}</code>", parse_mode="HTML")
            except Exception as e:
                await update.message.reply_text(f"❌ {str(e)[:150]}")
            return
        if t == "cv":
            try: amt = int(txt)
            except: await update.message.reply_text("Số không hợp lệ."); return
            if not a.get("init_data"): await update.message.reply_text("❌ Chưa có initData."); return
            try:
                gf = GF(a["init_data"])
                s, j = await asyncio.to_thread(gf.convert, amt)
                storage.log_activity(aid, f"Đổi {amt} coin -> {s}")
                await update.message.reply_text(f"💱 {s}\n<code>{json.dumps(j, ensure_ascii=False)[:200]}</code>", parse_mode="HTML")
            except Exception as e:
                await update.message.reply_text(f"❌ {str(e)[:150]}")
            return

    # default: show menu
    accs = storage.list_accounts()
    running = sum(1 for a in accs if a.get("farm_running"))
    txt2 = (f"🌾 <b>GHOSTFARM MANAGER</b>\n"
            f"👤 {len(accs)} acc | ▶️ {running} farm\n<i>Chọn menu:</i>")
    await update.message.reply_text(txt2, parse_mode="HTML", reply_markup=kb_main(u.id))

async def cmd_cancel(update, ctx):
    u = update.effective_user
    AS_STATE.pop(u.id, None); OTP_STATE.pop(u.id, None); UI_WAIT.pop(u.id, None)
    await update.message.reply_text("✅ Đã huỷ.", reply_markup=kb_main(u.id))

async def refresh_initdata(aid):
    a = storage.get_account(aid)
    if not a: return False
    try:
        fresh = await fetch_initdata_with_ref(a["session"], REF_CODE)
        if fresh:
            storage.update_account(aid, init_data=fresh, init_ts=int(time.time()))
            return True
    except Exception as e:
        storage.log_activity(aid, f"refresh fail: {str(e)[:60]}")
    return False

def start_worker(aid):
    if aid in WORKERS and WORKERS[aid]["th"].is_alive(): return
    holder = {"stop": False}
    def worker():
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        last_refresh = 0
        while not holder["stop"]:
            try:
                a = storage.get_account(aid)
                if not a or not a.get("farm_running"): break
                st_set(aid, "farm", "Bắt đầu tick...")
                idata = a.get("init_data")
                if not idata or (time.time() - (a.get("init_ts") or 0) > IDATA_TTL):
                    if not loop.run_until_complete(refresh_initdata(aid)):
                        storage.log_activity(aid, "initData fail"); time.sleep(60); continue
                    a = storage.get_account(aid); idata = a["init_data"]
                gf = GF(idata)
                try:
                    ts = task_tick(gf, {}, aid)
                    if ts["claims"]: storage.log_activity(aid, f"task +{ts['reward']} ({ts['claims']})")
                except Exception as e:
                    storage.log_activity(aid, f"task err {str(e)[:60]}")
                # ---- AD WATCHER ----
                try:
                    for _round in range(5):
                        tasks_now = gf.tasks()
                        ad_todo = [t for t in tasks_now
                                   if (t.get("kind") or t.get("type")) == "ad"
                                   and (t.get("progress") or 0) < (t.get("target") or 10)]
                        if not ad_todo:
                            break
                        t = ad_todo[_round % len(ad_todo)]
                        title = t.get("title", "ad")
                        prog = t.get("progress") or 0
                        target = t.get("target") or 10
                        st_set(aid, "ad", f"{title} {prog}/{target}")
                        storage.log_activity(aid, "ad " + title + " " + str(prog) + "/" + str(target))
                        res = watch_one_ad(idata, log=lambda m: None, max_wait=75, task_name=title)
                        if res.get("ok"):
                            after = (res.get("progress_after") or {}).get(title, "?")
                            st_set(aid, "ad", f"✅ {title} {after}")
                            storage.log_activity(aid, "ad OK " + title + " -> " + str(after))
                        else:
                            err = res.get("err", "?")
                            st_set(aid, "ad", f"⚠️ {title}: {err}")
                            storage.log_activity(aid, "ad fail " + title + ": " + str(err))
                    try:
                        prof = gf.me()
                        storage.update_account(aid, last_state=json.dumps(prof))
                    except Exception: pass
                except Exception as e:
                    storage.log_activity(aid, "ad err: " + str(e)[:80])

                try:
                    allowed = storage.get_crop_pref(aid)
                    fs = farm_tick(gf, {}, aid, allowed_crops=allowed)
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
        loop.close()
    th = threading.Thread(target=worker, daemon=True)
    holder["th"] = th; WORKERS[aid] = holder; th.start()

def resume_workers():
    for a in storage.list_accounts():
        if a.get("farm_running"): start_worker(a["id"])

def code_watcher_thread():
    """Listen @ghostfarmx_bot real-time. Code moi -> redeem ngay vao tat ca acc dang farm."""
    from telethon import events
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        time.sleep(15)
        while not WATCHER["stop"]:
            try:
                accs = storage.list_accounts()
                if not accs:
                    print("[watcher] no acc, wait 60s")
                    time.sleep(60); continue
                sess = accs[0]["session"]
                client = TelegramClient(StringSession(sess), 2040,
                                        "b18441a1ff607e10a989891a5462e627", loop=loop)
                client.connect()
                if not client.is_user_authorized():
                    print("[watcher] session dead, wait 120s")
                    client.disconnect(); time.sleep(120); continue

                bot = client.get_entity("ghostfarmx_bot")
                print(f"[watcher] connected, listening @{bot.username}")

                # 1. backfill - quet toan bo history
                async def scan():
                    total = 0
                    codes_found = []
                    async for msg in client.iter_messages(bot):
                        total += 1
                        if not msg.text: continue
                        for code in CODE_RE.findall(msg.text):
                            if code not in codes_found:
                                codes_found.append(code)
                    print(f"[watcher] backfill: {total} msg, {len(codes_found)} code unique: {codes_found}")
                    for code in codes_found:
                        # kiem tra co acc nao chua dung khong
                        needs = [a for a in storage.list_accounts()
                                 if not storage.is_code_used(code, a["id"])]
                        if needs:
                            print(f"[watcher] backfill redeem {code} -> {len(needs)} acc")
                            process_code(code)

                try:
                    loop.run_until_complete(scan())
                except Exception as e:
                    print(f"[watcher] scan err: {e}")

                # 2. listen real-time
                @client.on(events.NewMessage(chats=bot))
                async def on_new_msg(ev):
                    txt = ev.message.text or ""
                    if not txt:
                        # kiem tra caption (anh co code)
                        txt = getattr(ev.message, "message", "") or ""
                    codes = CODE_RE.findall(txt)
                    if not codes:
                        return
                    print(f"[watcher] 🔔 NEW message, codes={codes}")
                    for code in codes:
                        print(f"[watcher] processing {code}...")
                        process_code(code)

                @client.on(events.MessageEdited(chats=bot))
                async def on_edit(ev):
                    txt = ev.message.text or ""
                    codes = CODE_RE.findall(txt)
                    if codes:
                        print(f"[watcher] ✏️ edited message, codes={codes}")
                        for code in codes:
                            process_code(code)

                print("[watcher] listening real-time...")
                loop.run_until_complete(client.disconnected)
                print("[watcher] disconnected, reconnect...")
                try: client.disconnect()
                except: pass
            except Exception as e:
                print(f"[watcher] outer err: {e}")
                time.sleep(60)

    threading.Thread(target=run, daemon=True).start()

def process_code(code):
    """Redeem 1 code vao tat ca acc dang bat farm."""
    all_accs = storage.list_accounts()
    accs = [a for a in all_accs if a.get("farm_running")] or all_accs
    if not accs:
        print(f"[code] {code} -> no accounts")
        return
    print(f"[code] {code} -> redeem vao {len(accs)} acc")
    ok_count = 0
    for a in accs:
        if storage.is_code_used(code, a["id"]):
            continue
        idata = a.get("init_data")
        if not idata or (time.time() - (a.get("init_ts") or 0) > IDATA_TTL):
            try:
                idata = fetch_initdata_sync(a["session"])
                if idata:
                    storage.update_account(a["id"], init_data=idata, init_ts=int(time.time()))
            except Exception as e:
                print(f"[code] {code} acc {a['name']} refresh fail: {e}")
                idata = None
        if not idata:
            storage.add_code(code, a["id"], False, "no_initdata")
            print(f"[code] {code} acc {a['name']}: no initData")
            continue
        try:
            gf = GF(idata)
            ok, msg = gf.claim_promo(code)
            storage.add_code(code, a["id"], ok, msg)
            storage.log_activity(a["id"], f"auto-code {code} {'OK' if ok else msg}")
            print(f"[code] {code} acc {a['name']}: {'OK ' + msg if ok else 'FAIL ' + msg}")
            if ok: ok_count += 1
        except Exception as e:
            storage.add_code(code, a["id"], False, str(e)[:80])
            print(f"[code] {code} acc {a['name']}: err {str(e)[:60]}")
    print(f"[code] {code} done -- {ok_count}/{len(accs)} OK")




def seed_accounts():
    try:
        from seed_accounts import SEED
    except Exception:
        return
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl import functions
    existing = {a.get("phone") for a in storage.list_accounts()}
    for s in SEED:
        if s.get("phone") in existing: continue
        try:
            c = TelegramClient(StringSession(s["session"]), 2040, "b18441a1ff607e10a989891a5462e627")
            c.connect()
            if not c.is_user_authorized():
                c.disconnect(); continue
            me = c.get_me()
            c.disconnect()
            aid = storage.add_account(s["name"], s["phone"], s["session"], me.id)
            if aid: storage.log_activity(aid, f"seed uid={me.id}")
        except Exception as e:
            print(f"[seed] {s.get('name')}: {e}")


def scan_history_once():
    """Quet toan bo history bot, redeem code chua dung."""
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    accs = storage.list_accounts()
    if not accs:
        print("[scan] no accounts"); return
    try:
        c = TelegramClient(StringSession(accs[0]["session"]), 2040,
                           "b18441a1ff607e10a989891a5462e627")
        c.connect()
        if not c.is_user_authorized():
            print("[scan] session dead"); c.disconnect(); return
        bot = c.get_entity("ghostfarmx_bot")
        all_codes = []
        scanned = 0
        for msg in c.iter_messages(bot):
            scanned += 1
            if not msg.text: continue
            for code in CODE_RE.findall(msg.text):
                if code not in all_codes:
                    all_codes.append(code)
        c.disconnect()
        print(f"[scan] scanned {scanned} msg, {len(all_codes)} codes: {all_codes}")
        for code in all_codes:
            for a in storage.list_accounts():
                if storage.is_code_used(code, a["id"]): continue
                idata = a.get("init_data")
                if not idata or (time.time() - (a.get("init_ts") or 0) > IDATA_TTL):
                    try:
                        idata = fetch_initdata_sync(a["session"])
                        if idata:
                            storage.update_account(a["id"], init_data=idata, init_ts=int(time.time()))
                    except Exception as e:
                        print(f"[scan] refresh {a['name']}: {e}")
                        continue
                if not idata: continue
                try:
                    gf = GF(idata)
                    ok, msg = gf.claim_promo(code)
                    storage.add_code(code, a["id"], ok, msg)
                    storage.log_activity(a["id"], f"scan-code {code} {'OK' if ok else msg}")
                    print(f"[scan] {code} -> {a['name']}: {'OK' if ok else msg}")
                except Exception as e:
                    storage.add_code(code, a["id"], False, str(e)[:80])
        print(f"[scan] done")
    except Exception as e:
        print(f"[scan] err: {e}")




def build_app():
    storage.init()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CallbackQueryHandler(cb_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app











