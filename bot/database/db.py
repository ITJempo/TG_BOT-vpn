import aiosqlite
import time
import logging
from typing import Optional, Dict, Any, List
from bot.config import config

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    email TEXT,
                    expiry_time INTEGER DEFAULT 0,
                    referrer_id INTEGER DEFAULT NULL,
                    trial_used INTEGER DEFAULT 0,
                    device_limit INTEGER DEFAULT 1,
                    created_at INTEGER
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    currency TEXT,
                    payload TEXT,
                    charge_id TEXT,
                    created_at INTEGER
                )
            """)

            # Миграция для уже существующей БД, созданной до появления device_limit
            try:
                await db.execute("ALTER TABLE users ADD COLUMN device_limit INTEGER DEFAULT 1")
            except Exception:
                pass  # колонка уже существует — это ожидаемо и не является ошибкой

            await db.commit()
            logging.info("База данных инициализирована.")

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def add_or_update_user(
        self,
        user_id: int,
        username: str,
        email: str,
        expiry_time: int,
        referrer_id: Optional[int] = None,
        trial_used: Optional[int] = None,
        device_limit: Optional[int] = None,
    ):
        async with aiosqlite.connect(self.db_path) as db:
            user = await self.get_user(user_id)
            now = int(time.time())
            if not user:
                await db.execute(
                    "INSERT INTO users (user_id, username, email, expiry_time, referrer_id, trial_used, device_limit, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, username, email, expiry_time, referrer_id, trial_used or 0, device_limit or 1, now)
                )
            else:
                trial_val = trial_used if trial_used is not None else user["trial_used"]
                device_limit_val = device_limit if device_limit is not None else user.get("device_limit", 1)
                await db.execute(
                    "UPDATE users SET username = ?, email = ?, expiry_time = ?, trial_used = ?, device_limit = ? WHERE user_id = ?",
                    (username, email, expiry_time, trial_val, device_limit_val, user_id)
                )
            await db.commit()

    async def get_device_limit(self, user_id: int, default: int = 1) -> int:
        user = await self.get_user(user_id)
        if user and user.get("device_limit") is not None:
            return user["device_limit"]
        return default

    async def set_device_limit(self, user_id: int, count: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET device_limit = ? WHERE user_id = ?", (count, user_id))
            await db.commit()

    async def add_payment(self, user_id: int, amount: int, currency: str, payload: str, charge_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO payments (user_id, amount, currency, payload, charge_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, amount, currency, payload, charge_id, int(time.time()))
            )
            await db.commit()

    async def get_referrals_count(self, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def get_expiring_users(self) -> List[Dict[str, Any]]:
        """Возвращает пользователей, у которых подписка кончается в течение следующих 24 часов"""
        now_ms = int(time.time() * 1000)
        day_later_ms = now_ms + (24 * 3600 * 1000)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE expiry_time > ? AND expiry_time <= ?",
                (now_ms, day_later_ms)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

db = Database(config.DB_PATH)
