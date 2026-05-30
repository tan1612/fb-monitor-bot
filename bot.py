import asyncio
import logging
import sqlite3
import httpx
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from config import BOT_TOKEN, CHECK_INTERVAL, ADMIN_IDS
from database import Database
from checker import FacebookChecker

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

db = Database()
checker = FacebookChecker()


# ─── HELPERS ────────────────────────────────────────────────────────────────

def status_emoji(status: str) -> str:
    return "🟢" if status == "live" else "🔴"


def is_admin(user_id: int) -> bool:
    return not ADMIN_IDS or user_id in ADMIN_IDS


# ─── COMMANDS ───────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👁 *FB Monitor Bot*\n\n"
        "Bot theo dõi trạng thái tài khoản Facebook theo thời gian thực.\n\n"
        "*Lệnh:*\n"
        "• `/add <id_hoac_url>` — Thêm ID vào danh sách theo dõi\n"
        "• `/remove <id>` — Xóa ID khỏi danh sách\n"
        "• `/list` — Xem danh sách đang theo dõi\n"
        "• `/check <id>` — Kiểm tra ngay một ID\n"
        "• `/checkall` — Kiểm tra tất cả ngay\n"
        "• `/status` — Thống kê tổng quan\n"
        "• `/help` — Hiển thị trợ giúp\n\n"
        f"⏱ Tự động check mỗi *{CHECK_INTERVAL // 60} phút*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Cú pháp: `/add <facebook_id_hoac_url>`\n\n"
            "Ví dụ:\n"
            "• `/add 100012345678`\n"
            "• `/add zuck`\n"
            "• `/add https://facebook.com/zuck`",
            parse_mode="Markdown"
        )
        return

    raw = context.args[0].strip()
    fb_id = checker.extract_id(raw)

    if not fb_id:
        await update.message.reply_text("❌ Không thể đọc được ID/URL này. Vui lòng thử lại.")
        return

    user_id = update.effective_user.id
    msg = await update.message.reply_text(f"🔍 Đang kiểm tra `{fb_id}`...", parse_mode="Markdown")

    status, display_name = await checker.check(fb_id)

    if db.add_account(fb_id, display_name, status, user_id):
        emoji = status_emoji(status)
        await msg.edit_text(
            f"✅ Đã thêm vào danh sách theo dõi!\n\n"
            f"{emoji} `{fb_id}` — *{display_name}*\n"
            f"Trạng thái hiện tại: *{'LIVE' if status == 'live' else 'DIE'}*",
            parse_mode="Markdown"
        )
    else:
        await msg.edit_text(f"⚠️ `{fb_id}` đã có trong danh sách theo dõi rồi.", parse_mode="Markdown")


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Cú pháp: `/remove <facebook_id>`", parse_mode="Markdown")
        return

    fb_id = context.args[0].strip()
    user_id = update.effective_user.id

    if db.remove_account(fb_id, user_id):
        await update.message.reply_text(f"🗑 Đã xóa `{fb_id}` khỏi danh sách.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Không tìm thấy `{fb_id}` trong danh sách của bạn.", parse_mode="Markdown")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    accounts = db.get_accounts(user_id)

    if not accounts:
        await update.message.reply_text(
            "📭 Danh sách trống.\n\nDùng `/add <id>` để thêm tài khoản theo dõi.",
            parse_mode="Markdown"
        )
        return

    lines = ["📋 *Danh sách theo dõi:*\n"]
    for acc in accounts:
        fb_id, name, status, last_check, added_at = acc
        emoji = status_emoji(status)
        last = last_check[:16] if last_check else "Chưa check"
        lines.append(f"{emoji} `{fb_id}` — *{name or fb_id}*\n   └ Check lúc: {last}")

    lines.append(f"\n_Tổng: {len(accounts)} tài khoản_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Cú pháp: `/check <facebook_id>`", parse_mode="Markdown")
        return

    raw = context.args[0].strip()
    fb_id = checker.extract_id(raw)

    if not fb_id:
        await update.message.reply_text("❌ ID không hợp lệ.")
        return

    msg = await update.message.reply_text(f"🔍 Đang kiểm tra `{fb_id}`...", parse_mode="Markdown")
    status, display_name = await checker.check(fb_id)
    emoji = status_emoji(status)

    await msg.edit_text(
        f"{emoji} *{display_name or fb_id}*\n"
        f"ID: `{fb_id}`\n"
        f"Trạng thái: *{'✅ LIVE' if status == 'live' else '❌ DIE'}*\n"
        f"Thời gian: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}",
        parse_mode="Markdown"
    )


async def cmd_checkall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    accounts = db.get_accounts(user_id)

    if not accounts:
        await update.message.reply_text("📭 Danh sách trống.")
        return

    msg = await update.message.reply_text(f"🔄 Đang kiểm tra {len(accounts)} tài khoản...")

    results = []
    for acc in accounts:
        fb_id, name, old_status, *_ = acc
        status, display_name = await checker.check(fb_id)
        changed = status != old_status
        db.update_status(fb_id, status, display_name)
        results.append((fb_id, display_name or name or fb_id, status, changed))
        await asyncio.sleep(0.5)

    lines = ["📊 *Kết quả kiểm tra:*\n"]
    for fb_id, name, status, changed in results:
        emoji = status_emoji(status)
        change_tag = " _(đổi)_" if changed else ""
        lines.append(f"{emoji} `{fb_id}` — {name}{change_tag}")

    lines.append(f"\n_Cập nhật lúc: {datetime.now().strftime('%H:%M %d/%m/%Y')}_")
    await msg.edit_text("\n".join(lines), parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    total, live, die = db.get_stats(user_id)

    await update.message.reply_text(
        f"📈 *Thống kê của bạn:*\n\n"
        f"📋 Tổng theo dõi: *{total}*\n"
        f"🟢 Live: *{live}*\n"
        f"🔴 Die: *{die}*\n\n"
        f"⏱ Check interval: *{CHECK_INTERVAL // 60} phút*",
        parse_mode="Markdown"
    )


# ─── BACKGROUND MONITOR ─────────────────────────────────────────────────────

async def monitor_loop(app: Application):
    """Chạy ngầm, check tất cả accounts mỗi CHECK_INTERVAL giây."""
    logger.info("Monitor loop started")
    await asyncio.sleep(10)  # chờ bot khởi động xong

    while True:
        try:
            accounts = db.get_all_accounts()
            logger.info(f"Checking {len(accounts)} accounts...")

            for fb_id, name, old_status, user_id in accounts:
                try:
                    new_status, display_name = await checker.check(fb_id)

                    if new_status != old_status:
                        # Trạng thái thay đổi → thông báo
                        db.update_status(fb_id, new_status, display_name)
                        db.log_change(fb_id, old_status, new_status)

                        emoji = status_emoji(new_status)
                        arrow = "🟢 LIVE" if new_status == "live" else "🔴 DIE"
                        old_arrow = "🟢 LIVE" if old_status == "live" else "🔴 DIE"

                        text = (
                            f"🔔 *Cảnh báo thay đổi trạng thái!*\n\n"
                            f"👤 *{display_name or name or fb_id}*\n"
                            f"🆔 `{fb_id}`\n\n"
                            f"{old_arrow} → {arrow}\n\n"
                            f"🕐 {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}"
                        )

                        await app.bot.send_message(
                            chat_id=user_id,
                            text=text,
                            parse_mode="Markdown"
                        )
                        logger.info(f"Status change: {fb_id} {old_status} -> {new_status}")
                    else:
                        db.update_last_check(fb_id)

                    await asyncio.sleep(1)  # tránh spam request

                except Exception as e:
                    logger.error(f"Error checking {fb_id}: {e}")
                    await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Monitor loop error: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    db.init()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("checkall", cmd_checkall))
    app.add_handler(CommandHandler("status", cmd_status))

    loop = asyncio.get_event_loop()
    loop.create_task(monitor_loop(app))

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
