import sqlite3
from contextlib import contextmanager
from typing import Optional

DB_PATH = "attendance.db"


def init_db():
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS members (
                discord_id   TEXT PRIMARY KEY,
                username     TEXT NOT NULL,
                attendance   INTEGER NOT NULL DEFAULT 0,
                created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_member(discord_id: str) -> Optional[dict]:
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM members WHERE discord_id = ?", (discord_id,)
        ).fetchone()
        return dict(row) if row else None


def increment_attendance(discord_id: str, username: str) -> int:
    """Increment attendance by 1. Returns the new count."""
    with _db() as conn:
        existing = conn.execute(
            "SELECT attendance FROM members WHERE discord_id = ?", (discord_id,)
        ).fetchone()
        if existing:
            new_count = existing["attendance"] + 1
            conn.execute(
                """UPDATE members
                   SET username = ?, attendance = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE discord_id = ?""",
                (username, new_count, discord_id),
            )
        else:
            new_count = 1
            conn.execute(
                "INSERT INTO members (discord_id, username, attendance) VALUES (?, ?, ?)",
                (discord_id, username, new_count),
            )
        return new_count


def set_attendance(discord_id: str, username: str, count: int) -> int:
    """Set attendance to an explicit count. Returns the new count."""
    with _db() as conn:
        existing = conn.execute(
            "SELECT 1 FROM members WHERE discord_id = ?", (discord_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE members
                   SET username = ?, attendance = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE discord_id = ?""",
                (username, count, discord_id),
            )
        else:
            conn.execute(
                "INSERT INTO members (discord_id, username, attendance) VALUES (?, ?, ?)",
                (discord_id, username, count),
            )
        return count


def reset_all() -> int:
    """Delete all attendance records. Returns the number of rows deleted."""
    with _db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        conn.execute("DELETE FROM members")
        return count


def get_leaderboard(limit: int = 10) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM members ORDER BY attendance DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
