import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
from config import BOT_TOKEN, CHECK_INTERVAL, ADMIN_IDS
from database import Database
from checker import FacebookChecker
from ui import (
    format_account_card, account_keyboard, list_keyboard,
    main_menu_keyboard, status_emoji, status_label
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

db = Database()
checker = FacebookChecker()

# user_data state keys
WAITING_ADD    = "waiting_add"
WAITING_UPDATE = "waiting_update"


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def is_allowed(user_id: int) -> bool:
    return not ADMIN_IDS or user_id in ADMIN_IDS


async def send_account_card(bot, chat_id, acc, photo_url=None):
    text = format_account_card(acc)
    keyboard = account_keyboard(acc["id"], bool(acc["monitoring"]), bool(acc["done"]))
    if photo_url:
        try:
            await bot.send_photo(
                chat_id=chat_id, photo=photo_url,
                caption=text, parse_mode=ParseMode.HTML, reply_markup=keyboard
            )
            return
        except Exception:
            pass
    await bot.send_message(
        chat_id=chat_id, text=text,
        parse_mode=ParseMode.HTML, reply_markup=keyboard
    )


async def process_add(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str):
    """Xử lý thêm UID từ chuỗi raw."""
    parts = [p.strip() for p in raw.split("|")]
    fb_raw   = parts[0]
    note     = parts[1] if len(parts) > 1 else ""
    price    = parts[2] if len(parts) > 2 else ""
    deadline = parts[3] if len(parts) > 3 else "Vĩnh viễn"

    fb_id = checker.extract_id(fb_raw)
    if not fb_id:
        await update.message.reply_text(
            "❌ UID/URL không hợp lệ.\n\n"
            "Ví dụ đúng:\n"
            "<code>100012345678 | Khánh | 500000 | 1d</code>",
            parse_mode=ParseMode.HTML
        )
        return

    user_id = update.effective_user.id
    msg = await update.message.reply_text(
        f"🔍 Đang kiểm tra <code>{fb_id}</code>...", parse_mode=ParseMode.HTML
    )

    status, name = await checker.check(fb_id)

    added = db.add_account(fb_id, user_id, note, price, deadline, status)
    if not added:
        await msg.edit_text(
            f"⚠️ <code>{fb_id}</code> đã có trong danh sách rồi.",
            parse_mode=ParseMode.HTML
        )
        return

    acc = db.get_account(fb_id, user_id)
    if name:
        db.update_account(acc["id"], status=status)
        acc = db.get_account(fb_id, user_id)

    await msg.delete()
    avatar_url = await checker.get_avatar_url(fb_id)
    await send_account_card(context.bot, update.effective_chat.id, acc, photo_url=avatar_url)


# ─── COMMANDS ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("❌ Bạn không có quyền dùng bot này.")
        return
    context.user_data.clear()
    await update.message.reply_text(
        "👁 <b>FB Monitor Bot</b>\n\n"
        "Bot theo dõi trạng thái tài khoản Facebook 24/7.\n"
        "Tự động thông báo khi Live ↔ Die.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard()
    )


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    # /add với args inline: /add 100012345678 | Khánh | 500000 | 1d
    if context.args:
        raw = " ".join(context.args)
        await process_add(update, context, raw)
        return

    # Không có args → hỏi user nhập
    context.user_data[WAITING_ADD] = True
    await update.message.reply_text(
        "👤 <b>Thêm Profile Facebook</b>\n\n"
        "Nhập theo định dạng:\n"
        "<code>UID | Ghi chú | Giá | Thời hạn</code>\n\n"
        "<b>Thời hạn:</b> <code>30p</code> (phút), <code>7d</code> (ngày)\n"
        "Không nhập = vĩnh viễn\n\n"
        "<b>Ví dụ:</b>\n"
        "<code>100012345678 | Khánh | 500000 | 1d</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")
        ]])
    )


# ─── MESSAGE HANDLER ──────────────────────────────────────────────────────────

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_data = context.user_data

    # Đang chờ nhập UID
    if user_data.get(WAITING_ADD):
        user_data.pop(WAITING_ADD, None)
        await process_add(update, context, update.message.text.strip())
        return

    # Đang chờ cập nhật
    if user_data.get(WAITING_UPDATE):
        account_id = user_data.pop(WAITING_UPDATE)
        acc = db.get_account_by_id(account_id)
        if not acc:
            await update.message.reply_text("❌ Không tìm thấy account.")
            return
        parts = [p.strip() for p in update.message.text.split("|")]
        note     = parts[0] if len(parts) > 0 and parts[0] else acc["note"]
        price    = parts[1] if len(parts) > 1 and parts[1] else acc["price"]
        deadline = parts[2] if len(parts) > 2 and parts[2] else acc["deadline"]
        db.update_account(account_id, note=note, price=price, deadline=deadline)
        acc = db.get_account_by_id(account_id)
        await update.message.reply_text("✅ Đã cập nhật!")
        await send_account_card(context.bot, update.effective_chat.id, acc)
        return


# ─── CALLBACK QUERIES ─────────────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    user_id = update.effective_user.id

    if data == "menu":
        context.user_data.clear()
        await query.message.reply_text(
            "👁 <b>FB Monitor Bot</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard()
        )

    elif data == "cancel_add":
        context.user_data.clear()
        await query.message.edit_text(
            "❌ Đã hủy.", reply_markup=main_menu_keyboard()
        )

    elif data == "list":
        accounts = db.get_accounts(user_id)
        if not accounts:
            await query.message.reply_text(
                "📭 Danh sách trống.\nDùng /add để thêm.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("➕ Thêm UID", callback_data="add_new")
                ]])
            )
            return
        await query.message.reply_text(
            f"📋 <b>Danh sách UID</b> ({len(accounts)} tài khoản)",
            parse_mode=ParseMode.HTML,
            reply_markup=list_keyboard(accounts)
        )

    elif data == "add_new":
        context.user_data[WAITING_ADD] = True
        await query.message.reply_text(
            "👤 <b>Thêm Profile Facebook</b>\n\n"
            "Nhập theo định dạng:\n"
            "<code>UID | Ghi chú | Giá | Thời hạn</code>\n\n"
            "<b>Ví dụ:</b>\n"
            "<code>100012345678 | Khánh | 500000 | 1d</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")
            ]])
        )

    elif data.startswith("view:"):
        account_id = int(data.split(":")[1])
        acc = db.get_account_by_id(account_id)
        if not acc or acc["user_id"] != user_id:
            await query.message.reply_text("❌ Không tìm thấy.")
            return
        await send_account_card(context.bot, update.effective_chat.id, acc)

    elif data.startswith("toggle_mon:"):
        account_id = int(data.split(":")[1])
        acc = db.get_account_by_id(account_id)
        if not acc or acc["user_id"] != user_id:
            return
        new_state = db.toggle_monitoring(account_id)
        acc = db.get_account_by_id(account_id)
        await query.answer("▶️ Đã BẬT theo dõi" if new_state else "⏸ Đã TẮT theo dõi", show_alert=True)
        try:
            await query.edit_message_caption(
                caption=format_account_card(acc), parse_mode=ParseMode.HTML,
                reply_markup=account_keyboard(acc["id"], bool(acc["monitoring"]), bool(acc["done"]))
            )
        except Exception:
            try:
                await query.edit_message_text(
                    text=format_account_card(acc), parse_mode=ParseMode.HTML,
                    reply_markup=account_keyboard(acc["id"], bool(acc["monitoring"]), bool(acc["done"]))
                )
            except Exception:
                pass

    elif data.startswith("toggle_done:"):
        account_id = int(data.split(":")[1])
        acc = db.get_account_by_id(account_id)
        if not acc or acc["user_id"] != user_id:
            return
        new_done = not bool(acc["done"])
        db.set_done(account_id, new_done)
        acc = db.get_account_by_id(account_id)
        await query.answer("✅ Done!" if new_done else "↩️ Bỏ Done", show_alert=True)
        try:
            await query.edit_message_caption(
                caption=format_account_card(acc), parse_mode=ParseMode.HTML,
                reply_markup=account_keyboard(acc["id"], bool(acc["monitoring"]), bool(acc["done"]))
            )
        except Exception:
            try:
                await query.edit_message_text(
                    text=format_account_card(acc), parse_mode=ParseMode.HTML,
                    reply_markup=account_keyboard(acc["id"], bool(acc["monitoring"]), bool(acc["done"]))
                )
            except Exception:
                pass

    elif data.startswith("info:"):
        account_id = int(data.split(":")[1])
        acc = db.get_account_by_id(account_id)
        if not acc or acc["user_id"] != user_id:
            return
        await query.answer("🔍 Đang lấy thông tin...", show_alert=False)
        status, name = await checker.check(acc["fb_id"])
        avatar_url = await checker.get_avatar_url(acc["fb_id"])
        db.update_account(account_id, status=status, last_check=datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        acc = db.get_account_by_id(account_id)
        await send_account_card(context.bot, update.effective_chat.id, acc, photo_url=avatar_url)

    elif data.startswith("update:"):
        account_id = int(data.split(":")[1])
        acc = db.get_account_by_id(account_id)
        if not acc or acc["user_id"] != user_id:
            return
        context.user_data[WAITING_UPDATE] = account_id
        await query.message.reply_text(
            f"✏️ <b>Cập nhật:</b> <code>{acc['fb_id']}</code>\n\n"
            "Nhập thông tin mới:\n"
            "<code>Ghi chú | Giá | Thời hạn</code>\n\n"
            "Bỏ trống = giữ nguyên\n"
            f"Hiện tại: <code>{acc['note']} | {acc['price']} | {acc['deadline']}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Hủy", callback_data=f"view:{account_id}")
            ]])
        )

    elif data.startswith("remove:"):
        account_id = int(data.split(":")[1])
        acc = db.get_account_by_id(account_id)
        if not acc or acc["user_id"] != user_id:
            return
        await query.message.reply_text(
            f"⚠️ Xác nhận xóa <code>{acc['fb_id']}</code>?",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Xóa", callback_data=f"confirm_remove:{account_id}"),
                InlineKeyboardButton("❌ Hủy", callback_data=f"view:{account_id}"),
            ]])
        )

    elif data.startswith("confirm_remove:"):
        account_id = int(data.split(":")[1])
        acc = db.get_account_by_id(account_id)
        if not acc or acc["user_id"] != user_id:
            return
        db.remove_account(acc["fb_id"], user_id)
        await query.message.reply_text(
            f"🗑 Đã xóa <code>{acc['fb_id']}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard()
        )

    elif data == "stats":
        s = db.get_stats(user_id)
        await query.message.reply_text(
            f"📊 <b>Thống kê của bạn</b>\n\n"
            f"📋 Tổng UID: <b>{s['total']}</b>\n"
            f"🟢 Live: <b>{s['live']}</b>\n"
            f"🔴 Die: <b>{s['die']}</b>\n"
            f"✅ Done: <b>{s['done']}</b>\n"
            f"🔄 Đang theo dõi: <b>{s['monitoring']}</b>\n\n"
            f"⏱ Check interval: <b>{CHECK_INTERVAL // 60} phút</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard()
        )

    elif data == "checkall":
        accounts = db.get_accounts(user_id)
        if not accounts:
            await query.message.reply_text("📭 Danh sách trống.")
            return
        msg = await query.message.reply_text(f"🔄 Đang kiểm tra {len(accounts)} tài khoản...")
        results = []
        for acc in accounts:
            status, name = await checker.check(acc["fb_id"])
            changed = status != acc["status"] and status != "unknown"
            db.update_account(acc["id"], status=status, last_check=datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            results.append((acc["fb_id"], acc["note"], status, changed))
            await asyncio.sleep(0.5)
        lines = ["📊 <b>Kết quả kiểm tra:</b>\n"]
        for fb_id, note, status, changed in results:
            e = status_emoji(status)
            tag = " <i>(đổi)</i>" if changed else ""
            lines.append(f"{e} <code>{fb_id}</code> {note}{tag}")
        lines.append(f"\n<i>{datetime.now().strftime('%H:%M %d/%m/%Y')}</i>")
        await msg.edit_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard())


# ─── MONITOR LOOP ─────────────────────────────────────────────────────────────

async def monitor_loop(app: Application):
    logger.info("Monitor loop started")
    await asyncio.sleep(15)
    while True:
        try:
            accounts = db.get_all_monitoring()
            logger.info(f"Checking {len(accounts)} accounts...")
            for acc in accounts:
                try:
                    new_status, name = await checker.check(acc["fb_id"])
                    if new_status == "unknown":
                        await asyncio.sleep(1)
                        continue
                    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    if new_status != acc["status"]:
                        db.update_account(acc["id"], status=new_status, last_check=now)
                        db.log_change(acc["fb_id"], acc["user_id"], acc["status"], new_status)
                        old_e = status_emoji(acc["status"])
                        new_e = status_emoji(new_status)
                        text = (
                            f"🔔 <b>Thay đổi trạng thái!</b>\n\n"
                            f"👤 <a href=\"https://facebook.com/{acc['fb_id']}\">"
                            f"{name or acc['note'] or acc['fb_id']}</a>\n"
                            f"🆔 <code>{acc['fb_id']}</code>\n"
                            f"📝 {acc['note'] or '—'}\n\n"
                            f"{old_e} <b>{status_label(acc['status'])}</b> → "
                            f"{new_e} <b>{status_label(new_status)}</b>\n\n"
                            f"🕐 {now}"
                        )
                        avatar_url = await checker.get_avatar_url(acc["fb_id"])
                        try:
                            await app.bot.send_photo(
                                chat_id=acc["user_id"], photo=avatar_url,
                                caption=text, parse_mode=ParseMode.HTML
                            )
                        except Exception:
                            await app.bot.send_message(
                                chat_id=acc["user_id"], text=text, parse_mode=ParseMode.HTML
                            )
                    else:
                        db.update_account(acc["id"], last_check=now)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Error checking {acc['fb_id']}: {e}")
                    await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
        await asyncio.sleep(CHECK_INTERVAL)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    db.init()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("menu",   cmd_start))
    app.add_handler(CommandHandler("add",    cmd_add))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    loop = asyncio.get_event_loop()
    loop.create_task(monitor_loop(app))

    logger.info("🤖 Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
