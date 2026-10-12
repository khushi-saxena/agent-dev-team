import os
import sqlite3
import datetime

import pytest

from app.storage import init_db, save_run, get_all_ids, DB_PATH


# Ensure a clean slate before each test. The DB file is created under
# ``data/briefing.db``.
@pytest.fixture(autouse=True)
def clean_db(tmp_path_factory):
    # ``tmp_path_factory`` gives us a fresh temporary directory that we
    # can copy the database into. For simplicity we delete the real file
    # if it exists.
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


def test_init_creates_tables():
    init_db()
    # Verify tables
    conn = sqlite3.connect(DB_PATH)
    curs = conn.cursor()
    curs.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
    assert curs.fetchone() is not None, "runs table not created"
    curs.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
    assert curs.fetchone() is not None, "items table not created"
    conn.close()


def test_save_and_retrieve_items():
    init_db()
    items = [
        {"stable_id": "id1", "title": "Tweet 1", "link": "http://example.com/1", "summary": "hi"},
        {"stable_id": "id2", "title": "Tweet 2", "link": "http://example.com/2", "summary": None},
    ]
    save_run(datetime.datetime.now(), True, None, items)
    ids = get_all_ids()
    assert "id1" in ids
    assert "id2" in ids
    assert len(ids) == 2

