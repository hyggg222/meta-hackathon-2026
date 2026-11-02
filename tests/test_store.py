from datetime import date, datetime, timedelta
import sqlite3
import threading
from types import SimpleNamespace

import pytest

from shrimp.models import FeedEntry, SampleRecord, Settings
from shrimp.store import DEMO_HISTORY, Store


# Verify persistence of samples, feed and settings across reopen.
def test_reopen_persists(tmp_path):
    db_file = tmp_path / "shrimp.db"
    day1 = date(2026, 11, 1)

    store = Store(db_file)
    tray = SimpleNamespace(n_measured=9, n_left_out=1, mean_length_mm=88.5)
    sid = store.save_sample(day1, tray, photo_path="pics/p1.jpg", demo=False)
    store.add_feed(FeedEntry(day=day1, kg_per_day=95.0, price_vnd=44000))

    defaults = Settings()
    new_settings = Settings(pond_name="Pond A", feed_price_vnd=48000)
    store.save_settings(new_settings)
    store.close()

    reopened = Store(db_file)
    samples = reopened.samples()
    feeds = reopened.feeds()
    loaded_settings = reopened.load_settings(defaults)
    reopened.close()

    assert len(samples) == 1
    assert samples[0] == SampleRecord(
        id=sid,
        day=day1,
        n_measured=9,
        n_left_out=1,
        mean_length_mm=88.5,
        demo=False,
        photo_path="pics/p1.jpg",
    )
    assert isinstance(samples[0].day, date)

    assert len(feeds) == 1
    assert feeds[0] == FeedEntry(day=day1, kg_per_day=95.0, price_vnd=44000)
    assert isinstance(feeds[0].day, date)

    assert loaded_settings.pond_name == "Pond A"
    assert loaded_settings.feed_price_vnd == 48000
    assert loaded_settings.ruler_mm == defaults.ruler_mm


# Verify demo seeding behavior and non-duplication.
def test_seed_demo():
    store = Store(":memory:")
    today = date(2026, 11, 2)
    store.seed_demo(today)

    samples = store.samples()
    assert len(samples) == 5
    for s in samples:
        assert s.demo is True
        assert s.n_measured == 8
        assert s.n_left_out == 2
        assert s.photo_path is None

    expected_days = [
        today - timedelta(days=14),
        today - timedelta(days=11),
        today - timedelta(days=8),
        today - timedelta(days=5),
        today - timedelta(days=2),
    ]
    expected_means = [72.0, 79.0, 85.5, 91.0, 91.5]
    assert [s.day for s in samples] == expected_days
    assert [s.mean_length_mm for s in samples] == expected_means

    feeds = store.feeds()
    assert len(feeds) == 1
    assert feeds[0] == FeedEntry(
        day=today - timedelta(days=14), kg_per_day=100.0, price_vnd=45000
    )

    # Real sample saved afterwards has demo=False.
    tray = SimpleNamespace(n_measured=10, n_left_out=0, mean_length_mm=95.0)
    store.save_sample(today, tray)
    samples_after = store.samples()
    assert len(samples_after) == 6
    assert samples_after[-1].demo is False

    # Calling seed_demo again does not duplicate.
    store.seed_demo(today)
    assert len(store.samples()) == 6
    assert len(store.feeds()) == 1


# Verify in-memory database works.
def test_memory_db():
    store = Store(":memory:")
    today = date(2026, 11, 2)
    tray = SimpleNamespace(n_measured=7, n_left_out=3, mean_length_mm=None)
    sid = store.save_sample(today, tray)
    samples = store.samples()
    assert len(samples) == 1
    assert samples[0].id == sid
    assert samples[0].mean_length_mm is None


# Verify samples ordering by day then id.
def test_sample_ordering():
    store = Store(":memory:")
    day1 = date(2026, 11, 1)
    day2 = date(2026, 11, 2)
    tray = SimpleNamespace(n_measured=8, n_left_out=2, mean_length_mm=80.0)

    sid2 = store.save_sample(day2, tray)
    sid1_a = store.save_sample(day1, tray)
    sid1_b = store.save_sample(day1, tray)

    samples = store.samples()
    assert [s.id for s in samples] == [sid1_a, sid1_b, sid2]
    assert [s.day for s in samples] == [day1, day1, day2]


# Verify feed replacement on same day.
def test_feed_replace():
    store = Store(":memory:")
    day = date(2026, 11, 1)
    store.add_feed(FeedEntry(day=day, kg_per_day=50.0, price_vnd=40000))
    store.add_feed(FeedEntry(day=day, kg_per_day=60.0, price_vnd=42000))

    feeds = store.feeds()
    assert len(feeds) == 1
    assert feeds[0] == FeedEntry(day=day, kg_per_day=60.0, price_vnd=42000)


# Verify feeds ordering by day.
def test_feed_ordering():
    store = Store(":memory:")
    day1 = date(2026, 11, 1)
    day2 = date(2026, 11, 2)
    day3 = date(2026, 11, 3)

    store.add_feed(FeedEntry(day=day3, kg_per_day=30.0, price_vnd=40000))
    store.add_feed(FeedEntry(day=day1, kg_per_day=10.0, price_vnd=40000))
    store.add_feed(FeedEntry(day=day2, kg_per_day=20.0, price_vnd=40000))

    feeds = store.feeds()
    assert [f.day for f in feeds] == [day1, day2, day3]


# Verify load_settings defaults on fresh db.
def test_settings_defaults():
    store = Store(":memory:")
    defaults = Settings()
    loaded = store.load_settings(defaults)
    assert loaded == defaults


# Verify settings update and partial override.
def test_settings_update():
    store = Store(":memory:")
    defaults = Settings()
    modified = Settings(pond_name="North Pond", harvest_per_kg=45.0)
    store.save_settings(modified)

    loaded = store.load_settings(defaults)
    assert loaded.pond_name == "North Pond"
    assert loaded.harvest_per_kg == 45.0
    assert loaded.card_mm == 85.6
    assert loaded.ruler_mm == 150.0


# Verify two stores on same file see committed rows.
def test_concurrent_stores(tmp_path):
    db_file = tmp_path / "shared.db"
    store1 = Store(db_file)
    store2 = Store(db_file)

    day = date(2026, 11, 2)
    tray = SimpleNamespace(n_measured=8, n_left_out=2, mean_length_mm=82.0)
    sid = store1.save_sample(day, tray)

    samples = store2.samples()
    assert len(samples) == 1
    assert samples[0].id == sid

    store2.add_feed(FeedEntry(day=day, kg_per_day=75.0, price_vnd=43000))
    feeds = store1.feeds()
    assert len(feeds) == 1
    assert feeds[0].kg_per_day == 75.0


# Verify store access from another thread.
def test_cross_thread_access(tmp_path):
    store = Store(tmp_path / "cross.db")
    day = date(2026, 11, 2)
    tray = SimpleNamespace(n_measured=8, n_left_out=2, mean_length_mm=80.0)
    errors = []
    samples = []

    def worker():
        try:
            store.save_sample(day, tray)
            samples.extend(store.samples())
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    if errors:
        raise errors[0]

    assert len(samples) == 1
    assert samples[0].n_measured == 8
    store.close()


# Verify concurrent saves across multiple threads.
def test_concurrent_saves(tmp_path):
    store = Store(tmp_path / "concurrent.db")
    day = date(2026, 11, 2)
    tray = SimpleNamespace(n_measured=8, n_left_out=2, mean_length_mm=80.0)
    errors = []

    def worker():
        try:
            for _ in range(20):
                store.save_sample(day, tray)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if errors:
        raise errors[0]

    all_samples = store.samples()
    assert len(all_samples) == 80
    distinct_ids = {s.id for s in all_samples}
    assert len(distinct_ids) == 80
    store.close()


# Verify concurrent seed_demo calls.
def test_concurrent_seed_demo(tmp_path):
    store = Store(tmp_path / "seed.db")
    today = date(2026, 11, 2)
    errors = []

    def worker():
        try:
            store.seed_demo(today)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if errors:
        raise errors[0]

    samples = store.samples()
    assert len(samples) == 5
    store.close()


# Verify rollback when save_settings fails.
def test_rollback_save_settings():
    store = Store(":memory:")
    defaults = Settings()
    with pytest.raises(TypeError):
        store.save_settings(Settings(pond_name=object()))
    with pytest.raises(TypeError):
        store.save_settings(Settings(pond_name="New Pond", card_mm=object()))
    tray = SimpleNamespace(n_measured=8, n_left_out=2, mean_length_mm=80.0)
    store.save_sample(date(2026, 11, 2), tray)
    assert store.load_settings(defaults) == defaults


# Verify rollback when seed_demo fails midway.
def test_rollback_seed_demo(monkeypatch):
    store = Store(":memory:")
    today = date(2026, 11, 2)
    feed_offset, feed_kg, _ = DEMO_HISTORY["feed"]
    monkeypatch.setitem(DEMO_HISTORY, "feed", (feed_offset, feed_kg, object()))
    with pytest.raises(sqlite3.Error):
        store.seed_demo(today)
    tray = SimpleNamespace(n_measured=8, n_left_out=2, mean_length_mm=80.0)
    store.save_sample(today, tray)
    assert [s for s in store.samples() if s.demo] == []


# Verify corrupt or mistyped settings rows are ignored and valid settings load.
def test_corrupt_settings():
    store = Store(":memory:")
    defaults = Settings()
    rows = [
        ("pond_name", '"Valid Pond"'),
        ("card_mm", "garbage"),
        ("min_measured", "[1, 2, 3]"),
        ("ruler_mm", "1"),
    ]
    for key, val in rows:
        store._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)", (key, val)
        )
    store._conn.commit()

    loaded = store.load_settings(defaults)
    assert loaded.pond_name == "Valid Pond"
    assert loaded.card_mm == defaults.card_mm
    assert loaded.min_measured == defaults.min_measured
    assert loaded.ruler_mm == 1.0
    assert isinstance(loaded.ruler_mm, float)

    store._conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("ruler_mm", '"abc"'),
    )
    store._conn.commit()
    loaded_abc = store.load_settings(defaults)
    assert loaded_abc.ruler_mm == defaults.ruler_mm

    store._conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("feed_price_vnd", "true"),
    )
    store._conn.commit()
    assert store.load_settings(defaults).feed_price_vnd == defaults.feed_price_vnd


# Verify datetime is stored as date and invalid date type raises TypeError.
def test_date_handling():
    store = Store(":memory:")
    dt = datetime(2026, 11, 2, 10, 30, 0)
    expected_d = date(2026, 11, 2)
    tray = SimpleNamespace(n_measured=8, n_left_out=2, mean_length_mm=80.0)

    sid = store.save_sample(dt, tray)
    store.add_feed(FeedEntry(day=dt, kg_per_day=50.0, price_vnd=40000))

    samples = store.samples()
    feeds = store.feeds()
    assert len(samples) == 1
    assert samples[0].id == sid
    assert samples[0].day == expected_d
    assert type(samples[0].day) is date

    assert len(feeds) == 1
    assert feeds[0].day == expected_d
    assert type(feeds[0].day) is date

    with pytest.raises(TypeError):
        store.save_sample("2026-11-02", tray)
    with pytest.raises(TypeError):
        store.add_feed(FeedEntry(day="2026-11-02", kg_per_day=20.0, price_vnd=40000))

    assert len(store.samples()) == 1
    assert len(store.feeds()) == 1


# Verify real feed entry on demo feed day survives seed_demo.
def test_seed_demo_preserves_real_feed():
    store = Store(":memory:")
    today = date(2026, 11, 2)
    real_day = today - timedelta(days=14)
    real_feed = FeedEntry(day=real_day, kg_per_day=50.0, price_vnd=40000)
    store.add_feed(real_feed)

    store.seed_demo(today)
    feeds = store.feeds()
    assert len(feeds) == 1
    assert feeds[0] == real_feed


# Verify corrupt or missing min_length_mm falls back to default.
def test_corrupt_min_length_falls_back():
    store = Store(":memory:")
    defaults = Settings()
    assert store.load_settings(defaults).min_length_mm == 50.0

    for bad in ('"corrupt"', "true", "[1, 2]", "{}", "null"):
        store._conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("min_length_mm", bad),
        )
        store._conn.commit()
        assert store.load_settings(defaults).min_length_mm == 50.0


# Verify round trip of sd_length_mm.
def test_sample_sd_length_round_trip():
    store = Store(":memory:")
    today = date(2026, 11, 2)
    tray = SimpleNamespace(n_measured=8, n_left_out=2, mean_length_mm=85.0, sd_length_mm=6.5)
    sid = store.save_sample(today, tray)
    samples = store.samples()
    assert len(samples) == 1
    assert samples[0].id == sid
    assert samples[0].sd_length_mm == pytest.approx(6.5)


# Verify old database without sd_length_mm opens, reads None, and new sample saves.
def test_old_database_migration_and_save(tmp_path):
    db_file = tmp_path / "old_shrimp.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE samples (
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
        INSERT INTO samples (day, n_measured, n_left_out, mean_length_mm, demo, photo_path)
        VALUES ('2026-11-01', 8, 2, 85.0, 0, NULL)
        """
    )
    conn.commit()
    conn.close()

    store = Store(db_file)
    samples = store.samples()
    assert len(samples) == 1
    assert samples[0].sd_length_mm is None

    new_tray = SimpleNamespace(n_measured=10, n_left_out=0, mean_length_mm=90.0, sd_length_mm=8.2)
    new_sid = store.save_sample(date(2026, 11, 2), new_tray)

    samples_after = store.samples()
    assert len(samples_after) == 2
    assert samples_after[0].sd_length_mm is None
    assert samples_after[1].id == new_sid
    assert samples_after[1].sd_length_mm == pytest.approx(8.2)
    store.close()


# Verify demo samples have sd_length_mm as None.
def test_seed_demo_sd_length_is_none():
    store = Store(":memory:")
    today = date(2026, 11, 2)
    store.seed_demo(today)
    samples = store.samples()
    assert len(samples) == 5
    for s in samples:
        assert s.sd_length_mm is None


