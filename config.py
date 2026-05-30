import os

# ── Bắt buộc phải điền ──────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ── Tùy chọn ────────────────────────────────────────────────────────────────

# Giới hạn chỉ những Telegram User ID này mới dùng được bot.
# Để trống [] để cho phép tất cả mọi người.
ADMIN_IDS: list[int] = []
# Ví dụ: ADMIN_IDS = [123456789, 987654321]

# Khoảng cách giữa mỗi lần check tự động (giây)
# 60 = mỗi 1 phút
CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "60"))

# Đường dẫn file SQLite
DB_PATH: str = os.getenv("DB_PATH", "fb_monitor.db")
