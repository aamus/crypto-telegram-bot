import sqlite3
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

class WatchlistDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initializes database tables for user watchlists and price alerts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Table for watchlist items
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    user_id INTEGER,
                    coin_id TEXT,
                    symbol TEXT,
                    name TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, coin_id)
                )
            """)
            # Table for target price alerts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    coin_id TEXT,
                    symbol TEXT,
                    target_price REAL,
                    condition TEXT, -- 'ABOVE' or 'BELOW'
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def add_to_watchlist(self, user_id: int, coin_id: str, symbol: str, name: str) -> bool:
        """Adds a coin to user's watchlist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO watchlist (user_id, coin_id, symbol, name) VALUES (?, ?, ?, ?)",
                    (user_id, coin_id, symbol, name)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding to watchlist: {e}")
            return False

    def remove_from_watchlist(self, user_id: int, coin_id: str) -> bool:
        """Removes a coin from user's watchlist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM watchlist WHERE user_id = ? AND coin_id = ?", (user_id, coin_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error removing from watchlist: {e}")
            return False

    def get_user_watchlist(self, user_id: int) -> List[Dict[str, str]]:
        """Returns list of coins in user's watchlist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT coin_id, symbol, name FROM watchlist WHERE user_id = ?", (user_id,))
                rows = cursor.fetchall()
                return [{"coin_id": r[0], "symbol": r[1], "name": r[2]} for r in rows]
        except Exception as e:
            logger.error(f"Error fetching watchlist: {e}")
            return []

    def set_price_alert(self, user_id: int, coin_id: str, symbol: str, target_price: float, condition: str) -> bool:
        """Sets a price alert for a user."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO alerts (user_id, coin_id, symbol, target_price, condition) VALUES (?, ?, ?, ?, ?)",
                    (user_id, coin_id, symbol.upper(), target_price, condition.upper())
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error setting alert: {e}")
            return False

    def get_active_alerts(self) -> List[Dict]:
        """Fetches all active price alerts across all users."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, user_id, coin_id, symbol, target_price, condition FROM alerts WHERE is_active = 1")
                rows = cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "user_id": r[1],
                        "coin_id": r[2],
                        "symbol": r[3],
                        "target_price": r[4],
                        "condition": r[5],
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            return []

    def deactivate_alert(self, alert_id: int):
        """Deactivates an alert after it has been triggered."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE alerts SET is_active = 0 WHERE id = ?", (alert_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error deactivating alert {alert_id}: {e}")
