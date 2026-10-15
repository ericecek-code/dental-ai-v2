"""SQLite perzistencia — feedback zubara k nálezom (prežíva reštart servera).

Supabase príde neskôr; rozhranie tu zostáva, len sa vymení úložisko.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/db.sqlite")


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS findings_feedback (
            job_id TEXT NOT NULL,
            finding_index INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (job_id, finding_index)
        )"""
    )
    return conn


def save_feedback(job_id: str, finding_index: int, status: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO findings_feedback (job_id, finding_index, status) VALUES (?, ?, ?)",
            (job_id, finding_index, status),
        )


def get_feedback(job_id: str) -> dict[int, str]:
    with _conn() as c:
        rows = c.execute(
            "SELECT finding_index, status FROM findings_feedback WHERE job_id = ?",
            (job_id,),
        ).fetchall()
    return {idx: status for idx, status in rows}
