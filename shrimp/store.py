from dataclasses import fields, replace
from datetime import date, timedelta
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, List, Optional, Union

from shrimp.models import FeedEntry, SampleRecord, Settings

# Demo history: samples (offset, n_measured, n_left_out, mean_length_mm) and feed (offset, kg, price).
DEMO_HISTORY = {
    "samples": (
        (-14, 8, 2, 72.0),
        (-11, 8, 2, 79.0),
        (-8, 8, 2, 85.5),
        (-5, 8, 2, 91.0),
        (-2, 8, 2, 91.5),
    ),
    "feed": (-14, 100.0, 45000),
}


# SQLite persistence layer for shrimp measurements, feeds and settings.
class Store:
    # Initialize SQLite store and ensure schema tables exist.
    def __init__(self, path: Union[str, Path]) -> None:
        path_str = str(path)
        if path_str != ":memory:":
            Path(path_str).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path_str, check_same_thread=False)
        self._init_tables()

    # Create tables if not present.
    def _init_tables(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                n_measured INTEGER NOT NULL,
                n_left_out INTEGER NOT NULL,
                mean_length_mm REAL,
                demo INTEGER NOT NULL,
                photo_path TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feeds (
                day TEXT PRIMARY KEY,
                kg_per_day REAL NOT NULL,
                price_vnd INTEGER NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    # Save a sample measurement and return its id.
    def save_sample(
        self,
        day: date,
        tray: Any,
        photo_path: Optional[str] = None,
        demo: bool = False,
    ) -> int:
        with self._lock:
            cur = self._conn.cursor()
            day_str = day.isoformat() if hasattr(day, "isoformat") else str(day)
            cur.execute(
                """
                INSERT INTO samples (day, n_measured, n_left_out, mean_length_mm, demo, photo_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    day_str,
                    int(tray.n_measured),
                    int(tray.n_left_out),
                    tray.mean_length_mm,
                    1 if demo else 0,
                    photo_path,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    # Return all sample records ordered by day, then id.
    def samples(self) -> List[SampleRecord]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT id, day, n_measured, n_left_out, mean_length_mm, demo, photo_path
                FROM samples
                ORDER BY day ASC, id ASC
                """
            )
            records = []
            for row in cur.fetchall():
                records.append(
                    SampleRecord(
                        id=row[0],
                        day=date.fromisoformat(row[1]),
                        n_measured=row[2],
                        n_left_out=row[3],
                        mean_length_mm=row[4],
                        demo=bool(row[5]),
                        photo_path=row[6],
                    )
                )
            return records

    # Add or replace a feed entry for its day.
    def add_feed(self, entry: FeedEntry) -> None:
        with self._lock:
            cur = self._conn.cursor()
            day_str = entry.day.isoformat() if hasattr(entry.day, "isoformat") else str(entry.day)
            cur.execute(
                """
                INSERT OR REPLACE INTO feeds (day, kg_per_day, price_vnd)
                VALUES (?, ?, ?)
                """,
                (
                    day_str,
                    float(entry.kg_per_day),
                    int(entry.price_vnd),
                ),
            )
            self._conn.commit()

    # Return all feed entries ordered by day.
    def feeds(self) -> List[FeedEntry]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT day, kg_per_day, price_vnd
                FROM feeds
                ORDER BY day ASC
                """
            )
            entries = []
            for row in cur.fetchall():
                entries.append(
                    FeedEntry(
                        day=date.fromisoformat(row[0]),
                        kg_per_day=float(row[1]),
                        price_vnd=int(row[2]),
                    )
                )
            return entries

    # Return default settings overridden by saved values.
    def load_settings(self, defaults: Settings) -> Settings:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT key, value FROM settings")
            saved = dict(cur.fetchall())
        overrides = {}
        for f in fields(defaults):
            if f.name in saved:
                overrides[f.name] = json.loads(saved[f.name])
        return replace(defaults, **overrides)

    # Save all settings fields to storage.
    def save_settings(self, settings: Settings) -> None:
        with self._lock:
            cur = self._conn.cursor()
            for f in fields(settings):
                val = getattr(settings, f.name)
                cur.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (f.name, json.dumps(val)),
                )
            self._conn.commit()

    # Insert demo history once if no demo samples exist.
    def seed_demo(self, today: date) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT 1 FROM samples WHERE demo = 1 LIMIT 1")
            if cur.fetchone() is not None:
                return

            for offset, n_meas, n_left, mean_len in DEMO_HISTORY["samples"]:
                sample_day = (today + timedelta(days=offset)).isoformat()
                cur.execute(
                    """
                    INSERT INTO samples (day, n_measured, n_left_out, mean_length_mm, demo, photo_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (sample_day, n_meas, n_left, mean_len, 1, None),
                )

            feed_offset, feed_kg, feed_price = DEMO_HISTORY["feed"]
            feed_day = (today + timedelta(days=feed_offset)).isoformat()
            cur.execute(
                """
                INSERT OR REPLACE INTO feeds (day, kg_per_day, price_vnd)
                VALUES (?, ?, ?)
                """,
                (feed_day, feed_kg, feed_price),
            )
            self._conn.commit()

    # Close the database connection.
    def close(self) -> None:
        with self._lock:
            self._conn.close()
