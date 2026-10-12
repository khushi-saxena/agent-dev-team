import os
import sqlite3
import hashlib
import urllib.error

import pytest

from app.ingest import fetch_feed, FEED_URL_ENV
from app.storage import DB_PATH, init_db


def _make_feed_xml(entries: str) -> bytes:
    """Return a minimal RSS XML string containing the given entries.

    Parameters
    ----------
    entries: str
        XML fragment for ``<item>...</item>`` instances.
    """
    return (f"""
    <rss version='2.0'>
        <channel>
            <title>Test Feed</title>
            {entries}
        </channel>
    </rss>
    """.encode("utf-8"))


@pytest.fixture(autouse=True)
def clean_db(tmp_path_factory):
    # Ensure a clean DB for every test
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


def test_fetch_with_guid(monkeypatch):
    # Create feed with a guid
    entry_xml = """
    <item>
        <title>Example 1</title>
        <link>https://example.com/1</link>
        <guid>guid-123</guid>
    </item>
    """
    xml_bytes = _make_feed_xml(entry_xml)

    class DummyResponse:
        def __init__(self, data: bytes):
            self.data = data
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            pass
        def read(self):
            return self.data

    def dummy_urlopen(url):
        return DummyResponse(xml_bytes)

    monkeypatch.setattr(urllib.request, "urlopen", dummy_urlopen)
    init_db()
    items = fetch_feed()
    assert items == [{"id": "guid-123", "title": "Example 1", "link": "https://example.com/1"}]
    # Verify DB rows
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT stable_id, title, link FROM items")
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0] == ("guid-123", "Example 1", "https://example.com/1")
    # run record
    cur = conn.execute("SELECT success, error FROM runs")
    run = cur.fetchone()
    assert run is not None
    assert run[0] == 1  # success
    assert run[1] is None
    conn.close()


def test_fetch_without_guid(monkeypatch):
    # Feed without guid; use hash of link
    entry_xml = """
    <item>
        <title>Example 2</title>
        <link>https://example.com/2</link>
    </item>
    """
    xml_bytes = _make_feed_xml(entry_xml)

    class DummyResponse:
        def __init__(self, data: bytes):
            self.data = data
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            pass
        def read(self):
            return self.data

    def dummy_urlopen(url):
        return DummyResponse(xml_bytes)

    monkeypatch.setattr(urllib.request, "urlopen", dummy_urlopen)
    init_db()
    items = fetch_feed()
    expected_id = hashlib.sha256("https://example.com/2".encode("utf-8")).hexdigest()
    assert items == [{"id": expected_id, "title": "Example 2", "link": "https://example.com/2"}]
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT stable_id FROM items")
    ids = {row[0] for row in cur}
    assert expected_id in ids
    conn.close()


def test_fetch_failure(monkeypatch):
    def dummy_urlopen(url):
        raise urllib.error.URLError("network failure")

    monkeypatch.setattr(urllib.request, "urlopen", dummy_urlopen)
    init_db()
    items = fetch_feed()
    assert items == []
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT success, error FROM runs")
    run = cur.fetchone()
    assert run is not None
    assert run[0] == 0
    assert run[1] == "network failure"
    # Ensure no items saved
    cur = conn.execute("SELECT COUNT(*) FROM items")
    count = cur.fetchone()[0]
    assert count == 0
    conn.close()

