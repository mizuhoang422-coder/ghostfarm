import os, time, json, asyncio, threading, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import storage
from ad_watcher import watch_one_ad
from farm_engine import (GF, farm_tick, task_tick, fetch_initdata_sync, get_me_sync,
                         st_init, st_set, st_get, CROPS, API_ID, API_HASH)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_UID = 8249205817
REF_CODE = os.environ.get("REF_CODE", "").strip()
IDATA_TTL = 12 * 3600

WORKERS = {}
CODE_RE = re.compile(r"FARM-[A-Z0-9]{3,}")
AS_STATE = {}
OTP_STATE = {}
UI_WAIT = {}

CROP_EMOJI = {"wheat":"🌾","barley":"🌿","corn":"🌽","tomato":"🍅","eggplant":"🍆","pumpkin":"🎃"}

def is_admin(uid): return uid == ADMIN_UID

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ OTP", callback_data="add_otp"),
         InlineKeyboardButton("🔑 Session", callback_data="add_session")],
        [InlineKeyboardButton("📋 Danh sách acc", callback_data="list")],
        [InlineKeyboardButton("📊 Xem trực tiếp", callback_data="live"),
         InlineKeyboardButton("🎁 Quản lý code", callback_data="codes")],
        [InlineKeyboardButton("▶️ Bật farm tất cả", callback_data="start_all"),
         InlineKeyboardButton("⏹ Tắt farm tất cả", callback_data="stop_all")],
        [InlineKeyboardButton("🌾 Chọn cây tất cả", callback_data="crop_bulk")],
        [InlineKeyboardButton("🔄 Refresh tất cả", callback_data="rf_all"),
         InlineKeyboardButton("🗑 Xoá acc", callback_data="del_list")],
    ])

def kb_acc(aid):
    a = storage.get_account(aid)
    if not a: return None
    run = a.get("farm_running")
    rb = (InlineKeyboardButton("⏹ Dừng farm", callback_data=f"stop:{aid}") if run
          else InlineKeyboardButton("▶️ Bật farm", callback_data=f"start:{aid}"))
    return InlineKeyboardMarkup([
        [rb],
        [InlineKeyboardButton("🌾 Chọn cây", callback_data=f"crop:{aid}")],
        [InlineKeyboardButton("💰 Rút VND", callback_data=f"wd:{aid}"),
         InlineKeyboardButton("💱 Coin→Gem", callback_data=f"cv:{aid}")],
        [InlineKeyboardButton("🏦 Cài bank", callback_data=f"bank:{aid}"),
         InlineKeyboardButton("🔄 Refresh", callback_data=f"rf:{aid}")],
        [InlineKeyboardButton("🗑 Xoá", callback_data=f"del:{aid}"),
         InlineKeyboardButton("⬅️ Quay lại", callback_data="list")],
    ])

def acc_text(aid):
    a = storage.get_account(aid)
    if not a: return "❌ Không tồn tại"
    prof = {}
    try:
        if a.get("last_state"): prof = json.loads(a["last_state"])
    except: pass
    run = "🟢 Đang farm" if a.get("farm_running") else "🔴 Dừng"
    txt = (f"👤 <b>{a.get('name','?')}</b>\n"
           f"📱 {a.get('phone','?')}\n"
           f"🆔 uid={a.get('uid','?')}\n"
           f"Trạng thái: {run}\n"
           f"━━━━━━━━━━━━━━━━\n")
    if prof:
        txt += (f"🪙 Coins: <b>{prof.get('coins',0):,}</b>\n"
                f"💎 Gems: <b>{prof.get('gems',0):,}</b>\n"
                f"💵 USDT: <b>{prof.get('usdt',0)}</b>\n"
                f"⭐ Lv {prof.get('level',1)}  XP {prof.get('xp',0)}/{prof.get('xpMax',0)}\n")
    txt += (f"━━━━━━━━━━━━━━━━\n"
            f"🏦 {a.get('bank_name','-')} | {a.get('bank_ctk','-')} | {a.get('bank_stk','-')}")
    return txt


# ============ CMD ============
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            f"⛔ Riêng tư. ID: <code>{update.effective_user.id}</code>",
            parse_mode="HTML"); return
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
    await update.message.reply_text(txt, parse_mode="HTML", reply_markup=kb_main())

async def cmd_cancel(update, ctx):
    u = update.effective_user.id
    AS_STATE.pop(u, None); OTP_STATE.pop(u, None); UI_WAIT.pop(u, None)
    await update.message.reply_text("✅ Đã huỷ.", reply_markup=kb_main())


# ============ CB ============
async def cb_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_admin(q.from_user.id):
        try: await q.answer("⛔")
        except: pass
        return
    try: await q.answer()
    except: pass
    try:
        await _cb_inner(q, q.data, ctx)
    except Exception as e:
        import traceback
        print(f"[CB ERR] {q.data}: {e}\n{traceback.format_exc()}")
        try:
            await q.edit_message_text(f"❌ Loi: <code>{str(e)[:200]}</code>", parse_mode="HTML")
        except: pass

async def _cb_inner(q, data, ctx):
    if data == "menu":
        accs = storage.list_accounts()
        running = sum(1 for a in accs if a.get("farm_running"))
        codes = storage.list_codes(999)
        txt = (f"🌾 <b>GHOSTFARM MANAGER</b>\n"
               f"━━━━━━━━━━━━━━━━\n"
               f"👤 {len(accs)} acc | ▶️ {running} farm\n"
               f"🎁 {len(codes)} code\n"
               f"<i>Chọn menu:</i>")
        await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb_main())
        return

    if data == "list":
        accs = storage.list_accounts()
        rows = []
        for a in accs:
            mark = "🟢" if a.get("farm_running") else "🔴"
            rows.append([InlineKeyboardButton(f"{mark} {a['name']} | uid={a.get('uid','?')}",
                                              callback_data=f"acc:{a['id']}")])
        rows.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")])
        await q.edit_message_text(f"📋 <b>DANH SÁCH ACC</b> ({len(accs)})",
                                   parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith("acc:"):
        aid = int(data.split(":")[1])
        await q.edit_message_text(acc_text(aid), parse_mode="HTML", reply_markup=kb_acc(aid))
        return

    if data.startswith("start:"):
        aid = int(data.split(":")[1])
        storage.update_account(aid, farm_running=1)
        start_worker(aid)
        await q.edit_message_text(acc_text(aid), parse_mode="HTML", reply_markup=kb_acc(aid))
        return

    if data.startswith("stop:"):
        aid = int(data.split(":")[1])
        storage.update_account(aid, farm_running=0)
        if aid in WORKERS:
            WORKERS[aid]["stop"] = True
        await q.edit_message_text(acc_text(aid), parse_mode="HTML", reply_markup=kb_acc(aid))
        return

    if data.startswith("rf:"):
        aid = int(data.split(":")[1])
        await q.edit_message_text("🔄 Đang làm mới...")
        ok = await asyncio.to_thread(refresh_idata, aid)
        if ok:
            a = storage.get_account(aid)
            try:
                gf = GF(a["init_data"])
                prof = gf.me()
                storage.update_account(aid, last_state=json.dumps(prof))
            except: pass
        await q.edit_message_text(acc_text(aid), parse_mode="HTML", reply_markup=kb_acc(aid))
        return

    if data.startswith("del:"):
        aid = int(data.split(":")[1])
        storage.delete_account(aid)
        if aid in WORKERS:
            WORKERS[aid]["stop"] = True
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
        await q.edit_message_text(f"✅ Đã bật farm {n} acc.", reply_markup=kb_main())
        return

    if data == "stop_all":
        n = 0
        for a in storage.list_accounts():
            storage.update_account(a["id"], farm_running=0)
            if a["id"] in WORKERS:
                WORKERS[a["id"]]["stop"] = True
                WORKERS.pop(a["id"], None)
            n += 1
        await q.edit_message_text(f"⏹ Đã tắt farm {n} acc.", reply_markup=kb_main())
        return

    if data == "rf_all":
        await q.edit_message_text("🔄 Đang refresh tất cả...")
        accs = storage.list_accounts()
        for a in accs:
            await asyncio.to_thread(refresh_idata, a["id"])
        await q.edit_message_text(f"✅ Đã refresh {len(accs)} acc.", reply_markup=kb_main())
        return

    if data == "live":
        await render_live(q)
        return

    if data == "codes":
        codes = storage.list_codes(60)
        lines = [f"🎁 <b>LỊCH SỬ CODE</b> ({len(codes)})", "━━━━━━━━━━━━━━━━"]
        if not codes: lines.append("<i>Trống.</i>")
        for r in codes[:40]:
            t = time.strftime("%d/%m %H:%M", time.localtime(r["ts"]))
            mark = "✅" if r["ok"] else "❌"
            lines.append(f"{mark} <code>{r['code']}</code> → acc#{r['acc_id']} {t}")
        await q.edit_message_text("\n".join(lines), parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")]]))
        return

    if data == "crop_bulk":
        accs = storage.list_accounts()
        if not accs:
            await q.edit_message_text("Chưa có acc."); return
        cur = storage.get_crop_pref(accs[0]["id"])
        if cur is None: cur = list(CROPS)
        rows = []; line = []
        for c in CROPS:
            mark = "✅" if c in cur else "⬜"
            line.append(InlineKeyboardButton(f"{mark}{CROP_EMOJI.get(c,'🌱')} {c}",
                                              callback_data=f"crop_bulk_tog:{c}"))
            if len(line) == 2: rows.append(line); line = []
        if line: rows.append(line)
        rows.append([InlineKeyboardButton("✅ Tất cả", callback_data="crop_bulk_all"),
                     InlineKeyboardButton("❌ Bỏ hết", callback_data="crop_bulk_none")])
        rows.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")])
        await q.edit_message_text(f"🌾 <b>CHỌN CÂY TẤT CẢ ACC</b> ({len(cur)}/{len(CROPS)})",
                                   parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith("crop_bulk_tog:"):
        c = data.split(":")[1]
        accs = storage.list_accounts()
        cur = storage.get_crop_pref(accs[0]["id"]) if accs else None
        if cur is None: cur = list(CROPS)
        if c in cur: cur.remove(c)
        else: cur.append(c)
        for a in accs:
            storage.set_crop_pref(a["id"], cur)
        rows = []; line = []
        for cc in CROPS:
            mark = "✅" if cc in cur else "⬜"
            line.append(InlineKeyboardButton(f"{mark}{CROP_EMOJI.get(cc,'🌱')} {cc}",
                                              callback_data=f"crop_bulk_tog:{cc}"))
            if len(line) == 2: rows.append(line); line = []
        if line: rows.append(line)
        rows.append([InlineKeyboardButton("✅ Tất cả", callback_data="crop_bulk_all"),
                     InlineKeyboardButton("❌ Bỏ hết", callback_data="crop_bulk_none")])
        rows.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")])
        await q.edit_message_text(f"🌾 <b>CHỌN CÂY TẤT CẢ ACC</b> ({len(cur)}/{len(CROPS)})",
                                   parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data == "crop_bulk_all":
        for a in storage.list_accounts():
            storage.set_crop_pref(a["id"], list(CROPS))
        await q.edit_message_text("✅ Set tất cả cây.", reply_markup=kb_main())
        return

    if data == "crop_bulk_none":
        for a in storage.list_accounts():
            storage.set_crop_pref(a["id"], [])
        await q.edit_message_text("❌ Bỏ hết cây.", reply_markup=kb_main())
        return

    if data.startswith("crop:"):
        aid = int(data.split(":")[1])
        await render_crop(q, aid)
        return

    if data.startswith("crop_tog:"):
        _, aid_s, c = data.split(":")
        aid = int(aid_s)
        allowed = storage.get_crop_pref(aid)
        if allowed is None: allowed = list(CROPS)
        if c in allowed: allowed.remove(c)
        else: allowed.append(c)
        storage.set_crop_pref(aid, allowed)
        await render_crop(q, aid)
        return

    if data.startswith("crop_all:"):
        aid = int(data.split(":")[1])
        storage.set_crop_pref(aid, list(CROPS))
        await render_crop(q, aid)
        return

    if data.startswith("crop_none:"):
        aid = int(data.split(":")[1])
        storage.set_crop_pref(aid, [])
        await render_crop(q, aid)
        return

    if data.startswith("bank:"):
        aid = int(data.split(":")[1])
        UI_WAIT[q.from_user.id] = {"type": "bank", "aid": aid}
        await q.edit_message_text(
            f"🏦 Cài bank acc #{aid}\nGửi theo mẫu:\n<code>Tên|CTK|STK</code>\nVD: <code>Vietcombank|NGUYEN VAN A|1234567890</code>",
            parse_mode="HTML")
        return

    if data.startswith("wd:"):
        aid = int(data.split(":")[1])
        a = storage.get_account(aid)
        if not a.get("bank_stk"):
            await q.edit_message_text("⚠️ Chưa cài bank. Bấm Cài bank trước.", reply_markup=kb_acc(aid))
            return
        UI_WAIT[q.from_user.id] = {"type": "wd", "aid": aid}
        await q.edit_message_text(f"💰 Nhập số <b>USDT</b> rút (acc {a['name']}):", parse_mode="HTML")
        return

    if data.startswith("cv:"):
        aid = int(data.split(":")[1])
        UI_WAIT[q.from_user.id] = {"type": "cv", "aid": aid}
        a = storage.get_account(aid)
        await q.edit_message_text(f"💱 Nhập số <b>coin</b> đổi (acc {a['name']}):", parse_mode="HTML")
        return

    if data == "add_session":
        AS_STATE[q.from_user.id] = {"step": "session"}
        await q.edit_message_text(
            "🔑 <b>THÊM ACC (SESSION)</b>\n\nGửi <b>StringSession</b> vào chat.\n\nGõ /cancel để huỷ.",
            parse_mode="HTML")
        return

    if data == "add_otp":
        OTP_STATE[q.from_user.id] = {"step": "name"}
        await q.edit_message_text(
            "📱 <b>THÊM ACC (OTP)</b>\n\nBước 1/3: Nhập <b>tên</b> acc (chữ/số/_).\n\nGõ /cancel để huỷ.",
            parse_mode="HTML")
        return


# ============ RENDER ============
async def render_live(q):
    accs = storage.list_accounts()
    parts = ["📊 <b>XEM TRỰC TIẾP</b>", "━" * 20]
    for a in accs:
        prof = {}
        try:
            if a.get("last_state"): prof = json.loads(a["last_state"])
        except: pass
        aid = a["id"]
        st = st_get(aid)
        mark = "🟢" if a.get("farm_running") else "🔴"
        parts.append("")
        parts.append(f"{mark} <b>{a['name']}</b>  🪙{prof.get('coins',0):,} 💎{prof.get('gems',0):,} ⭐Lv{prof.get('level',1)}")

        action = st.get("action") or "—"
        parts.append(f"   ⚙️ {action}")

        plots = st.get("plots") or []
        if plots:
            pl = []
            for p in plots:
                s = p.get("state","?"); idx = p.get("idx"); crop = p.get("crop") or "?"
                if s == "empty":
                    pl.append(f"{idx}:trống")
                elif s == "growing":
                    w = "💧" if p.get("watered") else ""
                    t = p.get("ready_in") or ""
                    pl.append(f"{idx}:{crop}{w}({t})" if t else f"{idx}:{crop}{w}")
                elif s == "ready":
                    pl.append(f"{idx}:{crop}✅")
                else:
                    pl.append(f"{idx}:{s}")
            parts.append(f"   🌾 {' '.join(pl)}")

        ads = st.get("ads") or {}
        if ads:
            parts.append(f"   📺 {' · '.join(f'{k}:{v}' for k,v in ads.items())}")

        tasks = st.get("tasks")
        if tasks: parts.append(f"   📋 {tasks}")

        tnow = st.get("task_now")
        if tnow: parts.append(f"   ⏳ {tnow}")

        code_last = st.get("code")
        if code_last: parts.append(f"   🎁 {code_last}")

    txt = "\n".join(parts)
    if len(txt) > 4000: txt = txt[:3900] + "..."
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Cập nhật", callback_data="live")],
        [InlineKeyboardButton("⬅️ Quay lại", callback_data="menu")]
    ])
    try:
        await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        if "not modified" in str(e).lower():
            try: await q.answer("Không có thay đổi mới")
            except: pass
        else:
            try:
                await q.edit_message_text(f"⚠️ {str(e)[:150]}\n\n{txt[:500]}", parse_mode="HTML", reply_markup=kb)
            except: pass

async def render_crop(q, aid):
    allowed = storage.get_crop_pref(aid)
    if allowed is None: allowed = list(CROPS)
    rows = []; line = []
    for c in CROPS:
        mark = "✅" if c in allowed else "⬜"
        line.append(InlineKeyboardButton(f"{mark}{CROP_EMOJI.get(c,'🌱')} {c}",
                                          callback_data=f"crop_tog:{aid}:{c}"))
        if len(line) == 2: rows.append(line); line = []
    if line: rows.append(line)
    rows.append([InlineKeyboardButton("✅ Tất cả", callback_data=f"crop_all:{aid}"),
                 InlineKeyboardButton("❌ Bỏ hết", callback_data=f"crop_none:{aid}")])
    rows.append([InlineKeyboardButton("⬅️ Quay lại", callback_data=f"acc:{aid}")])
    await q.edit_message_text(
        f"🌾 <b>CHỌN CÂY</b> (acc {aid})\nCho phép: <b>{len(allowed)}/{len(CROPS)}</b>",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


# ============ TEXT ============
async def text_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    txt = (update.message.text or "").strip()
    uid = update.effective_user.id

    # Session flow
    st = AS_STATE.get(uid)
    if st and st.get("step") == "session":
        try: await update.message.delete()
        except: pass
        if len(txt) < 100:
            await update.message.reply_text("Session quá ngắn. Nhập lại:"); return
        m = await update.message.reply_text("⏳ Đang kiểm tra...")
        info = await asyncio.to_thread(get_me_sync, txt)
        if not info:
            await m.edit_text("❌ Session không hợp lệ.")
            AS_STATE.pop(uid, None); return
        idata = await asyncio.to_thread(fetch_initdata_sync, txt)
        if not idata:
            await m.edit_text("❌ Không fetch được initData. Acc block bot?")
            AS_STATE.pop(uid, None); return
        aid = storage.add_account(info.get("username") or f"acc{info['uid']}",
                                   "?", txt, info["uid"])
        storage.update_account(aid, init_data=idata, init_ts=int(time.time()), farm_running=1)
        start_worker(aid)
        AS_STATE.pop(uid, None)
        await m.edit_text(f"✅ Đã thêm acc #{aid} — uid={info['uid']}", reply_markup=kb_main())
        return

    # OTP flow
    st = OTP_STATE.get(uid)
    if st:
        step = st.get("step")
        if step == "name":
            if not re.match(r"^[A-Za-z0-9_]{1,20}$", txt):
                await update.message.reply_text("Tên chữ/số/_, 1-20. Nhập lại:"); return
            st["name"] = txt; st["step"] = "phone"
            await update.message.reply_text("📱 Bước 2/3: Nhập SĐT (+84...):"); return
        if step == "phone":
            p = txt.replace(" ","").replace("-","")
            if not p.startswith("+"):
                await update.message.reply_text("SĐT dạng +84..."); return
            st["phone"] = p
            m = await update.message.reply_text("⏳ Đang gửi OTP...")
            try:
                from telethon import TelegramClient
                from telethon.sessions import StringSession
                async def _send():
                    c = TelegramClient(StringSession(), API_ID, API_HASH)
                    await c.connect()
                    sent = await c.send_code_request(p)
                    sess = c.session.save()
                    await c.disconnect()
                    return sess, sent.phone_code_hash
                temp, chash = await _send()
                st["temp"] = temp; st["chash"] = chash; st["step"] = "code"
                await m.edit_text(f"📨 Đã gửi OTP. Nhập code (bước 3/3):")
            except Exception as e:
                await m.edit_text(f"❌ Lỗi: {str(e)[:150]}")
                OTP_STATE.pop(uid, None)
            return
        if step == "code":
            code = txt.replace(" ","").replace("-","")
            try:
                from telethon import TelegramClient
                from telethon.sessions import StringSession
                from telethon.errors import SessionPasswordNeededError
                async def _sign():
                    c = TelegramClient(StringSession(st["temp"]), API_ID, API_HASH)
                    await c.connect()
                    try:
                        await c.sign_in(phone=st["phone"], code=code, phone_code_hash=st.get("chash"))
                    except SessionPasswordNeededError:
                        await c.disconnect(); return None, "2FA"
                    sess = c.session.save()
                    await c.disconnect()
                    return sess, "OK"
                new_sess, status = await _sign()
            except Exception as e:
                await update.message.reply_text(f"❌ {str(e)[:150]}"); return
            if status == "2FA":
                st["step"] = "2fa"
                await update.message.reply_text("🔐 Acc 2FA. Nhập mật khẩu:"); return
            if not new_sess:
                await update.message.reply_text("❌ OTP sai."); return
            idata = await asyncio.to_thread(fetch_initdata_sync, new_sess)
            info = await asyncio.to_thread(get_me_sync, new_sess)
            aid = storage.add_account(st["name"], st["phone"], new_sess, info["uid"] if info else 0)
            storage.update_account(aid, init_data=idata or "", init_ts=int(time.time()), farm_running=1)
            if idata: start_worker(aid)
            OTP_STATE.pop(uid, None)
            await update.message.reply_text(f"✅ Đã thêm acc <b>{st['name']}</b>", parse_mode="HTML", reply_markup=kb_main())
            return
        if step == "2fa":
            try:
                from telethon import TelegramClient
                from telethon.sessions import StringSession
                async def _sign2():
                    c = TelegramClient(StringSession(st["temp"]), API_ID, API_HASH)
                    await c.connect()
                    await c.sign_in(password=txt)
                    sess = c.session.save()
                    await c.disconnect()
                    return sess
                new_sess = await _sign2()
                idata = await asyncio.to_thread(fetch_initdata_sync, new_sess)
                info = await asyncio.to_thread(get_me_sync, new_sess)
                aid = storage.add_account(st["name"], st["phone"], new_sess, info["uid"] if info else 0)
                storage.update_account(aid, init_data=idata or "", init_ts=int(time.time()), farm_running=1)
                if idata: start_worker(aid)
                OTP_STATE.pop(uid, None)
                await update.message.reply_text(f"✅ Acc <b>{st['name']}</b> added.", parse_mode="HTML", reply_markup=kb_main())
            except Exception as e:
                await update.message.reply_text(f"❌ {str(e)[:150]}")
            return

    # UI_WAIT
    w = UI_WAIT.get(uid)
    if w:
        t = w.get("type"); aid = w.get("aid")
        UI_WAIT.pop(uid, None)
        a = storage.get_account(aid)
        if t == "bank":
            parts = txt.split("|")
            if len(parts) != 3:
                await update.message.reply_text("Sai format: `Tên|CTK|STK`"); return
            storage.update_account(aid, bank_name=parts[0].strip(),
                                    bank_ctk=parts[1].strip(), bank_stk=parts[2].strip())
            await update.message.reply_text(f"✅ Bank acc {a['name']} lưu."); return
        if t == "wd":
            try: amt = float(txt)
            except: await update.message.reply_text("Số không hợp lệ."); return
            if not a.get("init_data"):
                await update.message.reply_text("❌ Chưa có initData."); return
            try:
                gf = GF(a["init_data"])
                await asyncio.to_thread(gf.set_address, "VND", a["bank_stk"], "VND")
                s, j = await asyncio.to_thread(gf.withdraw, "VND", a["bank_stk"], amt)
                storage.log_activity(aid, f"Rút {amt} USDT -> {s}")
                await update.message.reply_text(f"💸 {s}\n<code>{json.dumps(j, ensure_ascii=False)[:200]}</code>",
                                                 parse_mode="HTML")
            except Exception as e:
                await update.message.reply_text(f"❌ {str(e)[:150]}")
            return
        if t == "cv":
            try: amt = int(txt)
            except: await update.message.reply_text("Số không hợp lệ."); return
            if not a.get("init_data"):
                await update.message.reply_text("❌ Chưa có initData."); return
            try:
                gf = GF(a["init_data"])
                s, j = await asyncio.to_thread(gf.convert, amt)
                storage.log_activity(aid, f"Convert {amt} -> {s}")
                await update.message.reply_text(f"💱 {s}\n<code>{json.dumps(j, ensure_ascii=False)[:200]}</code>",
                                                 parse_mode="HTML")
            except Exception as e:
                await update.message.reply_text(f"❌ {str(e)[:150]}")
            return

    await update.message.reply_text("Dùng menu 👇", reply_markup=kb_main())


# ============ WORKER ============
def refresh_idata(aid):
    a = storage.get_account(aid)
    if not a: return False
    try:
        fresh = fetch_initdata_sync(a["session"])
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
        st_set(aid, "action", "⏳ Worker khởi động...")
        last_refresh = 0
        while not holder["stop"]:
            try:
                a = storage.get_account(aid)
                if not a or not a.get("farm_running"): break
                idata = a.get("init_data")
                if not idata or (time.time() - (a.get("init_ts") or 0) > IDATA_TTL):
                    if not refresh_idata(aid):
                        storage.log_activity(aid, "initData fail"); time.sleep(60); continue
                    a = storage.get_account(aid); idata = a["init_data"]
                gf = GF(idata)
                try:
                    ts = task_tick(gf, {}, aid)
                    if ts["claims"]:
                        storage.log_activity(aid, f"task +{ts['reward']} ({ts['claims']})")
                except Exception as e:
                    storage.log_activity(aid, f"task err {str(e)[:60]}")

                # ---- AD WATCHER ----
                try:
                    tasks_now = gf.tasks()
                    ad_todo = [t for t in tasks_now
                               if (t.get("kind") or t.get("type")) == "ad"
                               and (t.get("progress") or 0) < (t.get("target") or 10)]
                    if ad_todo:
                        # Refresh initData
                        fresh = fetch_initdata_sync(a["session"])
                        if fresh:
                            idata = fresh
                            storage.update_account(aid, init_data=fresh, init_ts=int(time.time()))
                        t = ad_todo[0]
                        title = t.get("title", "ad")
                        prog = t.get("progress") or 0
                        target = t.get("target") or 10
                        st_set(aid, "ads_now", f"🎬 {title} {prog}/{target}")
                        storage.log_activity(aid, f"ad start {title} {prog}/{target}")
                        res = watch_one_ad(idata, log=lambda m: storage.log_activity(aid, f"ad {m}"), max_wait=90, task_name=title)
                        if res.get("ok"):
                            after = (res.get("progress_after") or {}).get(title, "?")
                            st_set(aid, "ads_now", f"✅ {title} {after}")
                            storage.log_activity(aid, f"✅ ad OK {title} {prog} -> {after}")
                        else:
                            err = res.get("err", "?")
                            st_set(aid, "ads_now", f"❌ {title}: {err}")
                            storage.log_activity(aid, f"❌ ad FAIL {title}: {err}")
                            # Notify admin neu fail 2 lan lien tiep
                            cnt = sum(1 for x in storage.get_activity(aid, 5) if "❌ ad FAIL" in x.get("msg", ""))
                            if cnt >= 2:
                                try:
                                    import asyncio as _a
                                    _a.run_coroutine_threadsafe(
                                        notify_admin("⚠️ <b>AD FAIL</b> acc <b>" + str(a['name']) + "</b>\nTask: " + str(title) + "\nLỗi: <code>" + str(err) + "</code>"),
                                        _bot_loop[0])
                                except Exception: pass
                except Exception as e:
                    storage.log_activity(aid, f"❌ ad err: {str(e)[:80]}")


                try:
                    fs = farm_tick(gf, {}, aid, storage.get_crop_pref(aid))
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
    holder["th"] = th
    WORKERS[aid] = holder
    th.start()

def resume_workers():
    for a in storage.list_accounts():
        if a.get("farm_running"):
            start_worker(a["id"])


# ============ WATCHER ============
def code_watcher_thread():
    """Async watcher — dung telethon async (khong .sync)."""
    def run():
        import asyncio
        from telethon import TelegramClient, events
        from telethon.sessions import StringSession

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _watch():
            time.sleep(20)
            while True:
                try:
                    accs = storage.list_accounts()
                    if not accs:
                        await asyncio.sleep(60); continue
                    sess = accs[0]["session"]
                    client = TelegramClient(StringSession(sess), API_ID, API_HASH)
                    await client.connect()
                    if not await client.is_user_authorized():
                        await client.disconnect()
                        await asyncio.sleep(120); continue
                    bot = await client.get_entity("ghostfarmx_bot")
                    print("[watcher] connected")

                    # Backfill 100 msg
                    codes = []
                    total = 0
                    async for msg in client.iter_messages(bot, limit=100):
                        total += 1
                        if not msg.text: continue
                        for c in CODE_RE.findall(msg.text):
                            if c not in codes: codes.append(c)
                    print(f"[watcher] backfill: {total} msg, {len(codes)} codes")
                    for c in codes:
                        if any(not storage.is_code_used(c, a["id"]) for a in storage.list_accounts()):
                            await asyncio.to_thread(process_code, c)

                    # Real-time listen
                    @client.on(events.NewMessage(chats=bot))
                    async def on_new(ev):
                        for c in CODE_RE.findall(ev.message.text or ""):
                            print(f"[watcher] NEW {c}")
                            await asyncio.to_thread(process_code, c)

                    print("[watcher] listening...")
                    await client.disconnected
                    await client.disconnect()
                except Exception as e:
                    print(f"[watcher] err: {e}")
                    await asyncio.sleep(60)

        loop.run_until_complete(_watch())

    import threading
    threading.Thread(target=run, daemon=True).start()




def process_code(code):
    all_accs = storage.list_accounts()
    accs = [a for a in all_accs if a.get("farm_running")] or all_accs
    if not accs:
        print(f"[code] {code}: no acc"); return
    print(f"[code] {code} -> {len(accs)} acc")
    ok_n = 0
    for a in accs:
        if storage.is_code_used(code, a["id"]): continue
        idata = a.get("init_data")
        if not idata or (time.time() - (a.get("init_ts") or 0) > IDATA_TTL):
            idata = fetch_initdata_sync(a["session"])
            if idata:
                storage.update_account(a["id"], init_data=idata, init_ts=int(time.time()))
        if not idata:
            storage.add_code(code, a["id"], False, "no_initdata"); continue
        try:
            gf = GF(idata)
            ok, msg = gf.claim_promo(code)
            storage.add_code(code, a["id"], ok, msg)
            storage.log_activity(a["id"], f"auto-code {code} {'OK' if ok else msg}")
            st_set(a["id"], "code", f"{code} {'✅' if ok else '❌'} ({time.strftime('%H:%M')})")
            print(f"[code] {code} {a['name']}: {'OK' if ok else msg}")
            if ok: ok_n += 1
        except Exception as e:
            storage.add_code(code, a["id"], False, str(e)[:80])
    print(f"[code] {code} done {ok_n}/{len(accs)}")


# ============ SEED ============
def seed_accounts():
    try:
        from seed_accounts import SEED
    except: return
    for s in SEED:
        if any(a.get("phone") == s.get("phone") for a in storage.list_accounts()): continue
        info = get_me_sync(s["session"])
        if not info:
            print(f"[seed] {s['name']} session dead"); continue
        aid = storage.add_account(s["name"], s.get("phone") or "?", s["session"], info["uid"])
        idata = fetch_initdata_sync(s["session"])
        if idata:
            storage.update_account(aid, init_data=idata, init_ts=int(time.time()), farm_running=1)
            start_worker(aid)
            print(f"[seed] {s['name']} OK + farm started")
        else:
            print(f"[seed] {s['name']} no initData")


# ============ BUILD ============
def build_app():
    storage.init()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CallbackQueryHandler(cb_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    return app

