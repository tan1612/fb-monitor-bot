import sqlite3
from datetime import datetime
from config import DB_PATH


class Database:
    def __init__(self):
        self.path = DB_PATH

    def init(self):
        with sqlite3.connect(self.path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    fb_id       TEXT NOT NULL,
                    user_id     INTEGER NOT NULL,
                    name        TEXT,
                    status      TEXT DEFAULT 'unknown',
                    last_check  TEXT,
                    added_at    TEXT NOT NULL,
                    PRIMARY KEY (fb_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS status_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    fb_id       TEXT NOT NULL,
                    old_status  TEXT,
                    new_status  TEXT,
                    changed_at  TEXT NOT NULL
                );
            """)
        print("✅ Database initialized")

    def add_account(self, fb_id: str, name: str, status: str, user_id: int) -> bool:
        """Thêm account. Trả về True nếu thêm mới, False nếu đã tồn tại."""
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    "INSERT INTO accounts (fb_id, user_id, name, status, added_at) VALUES (?, ?, ?, ?, ?)",
                    (fb_id, user_id, name, status, datetime.now().isoformat())
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_account(self, fb_id: str, user_id: int) -> bool:
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute(
                "DELETE FROM accounts WHERE fb_id = ? AND user_id = ?",
                (fb_id, user_id)
            )
            return cur.rowcount > 0

    def get_accounts(self, user_id: int) -> list:
        """Lấy danh sách accounts của một user."""
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT fb_id, name, status, last_check, added_at FROM accounts WHERE user_id = ? ORDER BY added_at DESC",
                (user_id,)
            ).fetchall()
        return rows

    def get_all_accounts(self) -> list:
        """Lấy tất cả accounts cho monitor loop."""
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT fb_id, name, status, user_id FROM accounts"
            ).fetchall()
        return rows

    def update_status(self, fb_id: str, status: str, name: str = None):
        with sqlite3.connect(self.path) as conn:
            if name:
                conn.execute(
                    "UPDATE accounts SET status = ?, name = ?, last_check = ? WHERE fb_id = ?",
                    (status, name, datetime.now().isoformat(), fb_id)
                )
            else:
                conn.execute(
                    "UPDATE accounts SET status = ?, last_check = ? WHERE fb_id = ?",
                    (status, datetime.now().isoformat(), fb_id)
                )

    def update_last_check(self, fb_id: str):
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "UPDATE accounts SET last_check = ? WHERE fb_id = ?",
                (datetime.now().isoformat(), fb_id)
            )

    def log_change(self, fb_id: str, old_status: str, new_status: str):
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO status_log (fb_id, old_status, new_status, changed_at) VALUES (?, ?, ?, ?)",
                (fb_id, old_status, new_status, datetime.now().isoformat())
            )

    def get_stats(self, user_id: int) -> tuple:
        """Trả về (total, live, die)."""
        with sqlite3.connect(self.path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            live = conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE user_id = ? AND status = 'live'", (user_id,)
            ).fetchone()[0]
            die = conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE user_id = ? AND status = 'die'", (user_id,)
            ).fetchone()[0]
        return total, live, die
