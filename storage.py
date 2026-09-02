from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone


class AlertStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    level TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (symbol, direction)
                )
                """
            )
            self._migrate_alerts_primary_key(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    summary_date TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL
                )
                """
            )

    def _migrate_alerts_primary_key(self, conn: sqlite3.Connection) -> None:
        info = conn.execute("PRAGMA table_info(alerts)").fetchall()
        pk_columns = [row[1] for row in sorted(info, key=lambda item: item[5]) if row_has_pk(row)]
        if pk_columns == ["symbol", "direction", "level"]:
            return

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts_v2 (
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                level TEXT NOT NULL,
                score INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (symbol, direction, level)
            )
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO alerts_v2
                (symbol, direction, level, score, created_at)
            SELECT symbol, direction, level, score, created_at
            FROM alerts
            """
        )
        conn.execute("DROP TABLE alerts")
        conn.execute("ALTER TABLE alerts_v2 RENAME TO alerts")

    def can_alert(self, symbol: str, direction: str, level: str, cooldown_hours: int) -> bool:
        cutoff = int(time.time()) - cooldown_hours * 3600
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT created_at
                FROM alerts
                WHERE symbol = ? AND direction = ? AND level = ? AND created_at >= ?
                """,
                (symbol, direction, level, cutoff),
            ).fetchone()
        return row is None

    def record(self, symbol: str, direction: str, level: str, score: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO alerts
                    (symbol, direction, level, score, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (symbol, direction, level, score, int(time.time())),
            )

    def alerts_sent_today(self, level: str | None = None) -> int:
        now = datetime.now(timezone.utc)
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        cutoff = int(start_of_day.timestamp())
        with self._connect() as conn:
            if level is not None:
                row = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM alerts
                    WHERE created_at >= ? AND level = ?
                    """,
                    (cutoff, level),
                ).fetchone()
                return int(row[0] if row else 0)

            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM alerts
                WHERE created_at >= ?
                """,
                (cutoff,),
            ).fetchone()
        return int(row[0] if row else 0)

    def summary_sent_today(self) -> bool:
        today = datetime.now(timezone.utc).date().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT summary_date
                FROM summaries
                WHERE summary_date = ?
                """,
                (today,),
            ).fetchone()
        return row is not None

    def record_summary_sent(self) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO summaries (summary_date, created_at)
                VALUES (?, ?)
                """,
                (today, int(time.time())),
            )


def row_has_pk(row: tuple) -> bool:
    return int(row[5] or 0) > 0
