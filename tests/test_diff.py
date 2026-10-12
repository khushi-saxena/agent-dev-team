"""Unit tests for the :mod:`app.diff` helper.

The goal of these tests is to satisfy the ticket requirements:

* The first ingest run on a freshly initialised database should report all
  items as new.
* Running the ingestion a second time against the *same* synthetic feed
  should produce zero new items.

The tests create a temporary RSS feed file, monkey‑patch
``urllib.request.urlopen`` to return that file, and use a temporary
directory for the SQLite database so no external state is mutated.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch
import urllib.request

import app.diff as diff
import app.ingest as ingest
from app.storage import init_db, DB_PATH


def _create_synthetic_feed(tmp_path: Path) -> Path:
    feed_xml = """
    <?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <link>http://example.com/</link>
        <description>Unit test feed</description>
        <item>
          <guid>item-1</guid>
          <title>First Item</title>
          <link>http://example.com/1</link>
        </item>
        <item>
          <guid>item-2</guid>
          <title>Second Item</title>
          <link>http://example.com/2</link>
        </item>
      </channel>
    </rss>
    """
    fp = tmp_path / "synthetic.xml"
    fp.write_text(feed_xml.strip(), encoding="utf-8")
    return fp


def _patch_urlopen(monkeypatch: MonkeyPatch, feed_path: Path) -> None:
    def _fake_urlopen(*_args, **_kwargs):  # pragma: no cover - simple stub
        return open(feed_path, "rb")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)


def _perform_ingest_and_diff(monkeypatch: MonkeyPatch, feed_path: Path):
    _patch_urlopen(monkeypatch, feed_path)
    items = ingest.fetch_feed()
    return items, diff.get_new_items(items)


def test_first_run_reports_all_items(monkeypatch: MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Use a temporary directory to hold the SQLite db so we start with
        # a clean state.
        orig_cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            init_db()
            feed_path = _create_synthetic_feed(Path(tmp_dir))
            items, new_items = _perform_ingest_and_diff(monkeypatch, feed_path)
            assert len(new_items) == len(items)
            assert set(it["id"] for it in new_items) == set(it["id"] for it in items)
        finally:
            os.chdir(orig_cwd)


def test_subsequent_run_reports_no_new_items(monkeypatch: MonkeyPatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        orig_cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            init_db()
            feed_path = _create_synthetic_feed(Path(tmp_dir))
            # First run – populate DB
            _perform_ingest_and_diff(monkeypatch, feed_path)
            # Second run – should see zero new items
            _, new_items = _perform_ingest_and_diff(monkeypatch, feed_path)
            assert len(new_items) == 0
        finally:
            os.chdir(orig_cwd)

