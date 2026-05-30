from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime


def status_emoji(status: str) -> str:
    return {
        "live": "🟢",
        "die":  "🔴",
    }.get(status, "⚪")


def status_label(status: str) -> str:
    return {
        "live": "LIVE",
        "die":  "DIE",
    }.get(status, "UNKNOWN")


def monitoring_emoji(monitoring: bool) -> str:
    return "🔄" if monitoring else "⏸"


def format_account_card(acc: dict) -> str:
    """Format thông tin 1 account dạng card đẹp."""
    s_emoji = status_emoji(acc["status"])
    s_label = status_label(acc["status"])
    mon_emoji = monitoring_emoji(bool(acc["monitoring"]))
    done_tag = " ✅ Done" if acc.get("done") else ""

    lines = [
        f"{s_emoji} <a href=\"https://facebook.com/{acc['fb_id']}\">{acc['fb_id']}</a> - <b>{s_label}</b> {s_emoji}{done_tag}",
        "",
        f"📝 Ghi chú: {acc['note'] or '—'}",
        f"💰 Giá: {acc['price'] or '—'}",
        f"⏳ Tiến trình: {'Đã tắt theo dõi' if not acc['monitoring'] else 'Đang theo dõi'} {mon_emoji}",
        f"🎯 Hạn trả kèo: {acc['deadline'] or 'Vĩnh viễn'}",
        f"📅 Ngày thêm: {acc['added_at']}",
        f"🔄 Cập nhật cuối: {acc['last_check'] or acc['added_at']}",
    ]
    return "\n".join(lines)


def account_keyboard(account_id: int, monitoring: bool, done: bool) -> InlineKeyboardMarkup:
    """Inline keyboard cho 1 account card."""
    mon_text = "⏸ Tắt theo dõi" if monitoring else "▶️ Theo dõi"
    done_text = "↩️ Bỏ Done" if done else "✅ Done kèo"

    buttons = [
        [
            InlineKeyboardButton("✏️ Cập nhật",      callback_data=f"update:{account_id}"),
            InlineKeyboardButton(mon_text,            callback_data=f"toggle_mon:{account_id}"),
        ],
        [
            InlineKeyboardButton("🐵 Hiện thông tin", callback_data=f"info:{account_id}"),
            InlineKeyboardButton(done_text,           callback_data=f"toggle_done:{account_id}"),
        ],
        [
            InlineKeyboardButton("❌ Hủy kèo",        callback_data=f"remove:{account_id}"),
            InlineKeyboardButton("◀️ Danh sách UID",  callback_data="list"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def list_keyboard(accounts: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard danh sách accounts."""
    buttons = []
    for acc in accounts:
        s = status_emoji(acc["status"])
        mon = "⏸" if not acc["monitoring"] else ""
        done = "✅" if acc["done"] else ""
        label = f"{s} {acc['fb_id']} {acc['note'] or ''} {mon}{done}".strip()
        buttons.append([InlineKeyboardButton(label, callback_data=f"view:{acc['id']}")])

    buttons.append([InlineKeyboardButton("➕ Thêm UID mới", callback_data="add_new")])
    return InlineKeyboardMarkup(buttons)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("➕ Thêm UID",      callback_data="add_new"),
            InlineKeyboardButton("📋 Danh sách UID", callback_data="list"),
        ],
        [
            InlineKeyboardButton("📊 Thống kê",      callback_data="stats"),
            InlineKeyboardButton("🔄 Check tất cả",  callback_data="checkall"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)
