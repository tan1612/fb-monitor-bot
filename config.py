import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Danh sách Telegram ID được dùng bot. Để [] = ai cũng dùng được.
ADMIN_IDS: list[int] = []

# Tự động check mỗi X giây (60 = 1 phút)
CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "60"))

DB_PATH: str = os.getenv("DB_PATH", "fb_monitor.db")
