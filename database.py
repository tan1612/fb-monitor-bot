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
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    fb_id       TEXT NOT NULL,
                    user_id     INTEGER NOT NULL,
                    note        TEXT DEFAULT '',
                    price       TEXT DEFAULT '',
                    deadline    TEXT DEFAULT 'Vĩnh viễn',
                    status      TEXT DEFAULT 'unknown',
                    monitoring  INTEGER DEFAULT 1,
                    done        INTEGER DEFAULT 0,
                    last_check  TEXT,
                    added_at    TEXT NOT NULL,
                    UNIQUE(fb_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS status_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    fb_id       TEXT NOT NULL,
                    user_id     INTEGER NOT NULL,
                    old_status  TEXT,
                    new_status  TEXT,
                    changed_at  TEXT NOT NULL
                );
            """)
        print("✅ Database initialized")

    # ── CRUD ──────────────────────────────────────────────────────────────

    def add_account(self, fb_id, user_id, note="", price="", deadline="Vĩnh viễn", status="unknown") -> bool:
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    "INSERT INTO accounts (fb_id, user_id, note, price, deadline, status, added_at) VALUES (?,?,?,?,?,?,?)",
                    (fb_id, user_id, note, price, deadline, status, datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_account(self, fb_id: str, user_id: int) -> dict | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM accounts WHERE fb_id=? AND user_id=?", (fb_id, user_id)
            ).fetchone()
        return dict(row) if row else None

    def get_account_by_id(self, account_id: int) -> dict | None:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        return dict(row) if row else None

    def get_accounts(self, user_id: int) -> list[dict]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM accounts WHERE user_id=? ORDER BY added_at DESC", (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_all_monitoring(self) -> list[dict]:
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM accounts WHERE monitoring=1"
            ).fetchall()
        return [dict(r) for r in rows]

    def update_account(self, account_id: int, **kwargs):
        if not kwargs:
            return
        sets = ", ".join(f"{k}=?" for k in kwargs)
        vals = list(kwargs.values()) + [account_id]
        with sqlite3.connect(self.path) as conn:
            conn.execute(f"UPDATE accounts SET {sets} WHERE id=?", vals)

    def remove_account(self, fb_id: str, user_id: int) -> bool:
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute(
                "DELETE FROM accounts WHERE fb_id=? AND user_id=?", (fb_id, user_id)
            )
            return cur.rowcount > 0

    def toggle_monitoring(self, account_id: int) -> bool:
        """Toggle monitoring on/off. Returns new state."""
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT monitoring FROM accounts WHERE id=?", (account_id,)).fetchone()
            if not row:
                return False
            new_val = 0 if row[0] else 1
            conn.execute("UPDATE accounts SET monitoring=? WHERE id=?", (new_val, account_id))
        return bool(new_val)

    def set_done(self, account_id: int, done: bool):
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE accounts SET done=? WHERE id=?", (int(done), account_id))

    def log_change(self, fb_id: str, user_id: int, old_status: str, new_status: str):
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO status_log (fb_id, user_id, old_status, new_status, changed_at) VALUES (?,?,?,?,?)",
                (fb_id, user_id, old_status, new_status, datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            )

    def get_stats(self, user_id: int) -> dict:
        with sqlite3.connect(self.path) as conn:
            total  = conn.execute("SELECT COUNT(*) FROM accounts WHERE user_id=?", (user_id,)).fetchone()[0]
            live   = conn.execute("SELECT COUNT(*) FROM accounts WHERE user_id=? AND status='live'", (user_id,)).fetchone()[0]
            die    = conn.execute("SELECT COUNT(*) FROM accounts WHERE user_id=? AND status='die'", (user_id,)).fetchone()[0]
            done   = conn.execute("SELECT COUNT(*) FROM accounts WHERE user_id=? AND done=1", (user_id,)).fetchone()[0]
            mon    = conn.execute("SELECT COUNT(*) FROM accounts WHERE user_id=? AND monitoring=1", (user_id,)).fetchone()[0]
        return {"total": total, "live": live, "die": die, "done": done, "monitoring": mon}
