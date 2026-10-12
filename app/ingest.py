"""Feed ingestion for the daily briefing.

The :func:`fetch_feed` function obtains the RSS feed from a URL supplied by
the ``FEED_URL`` environment variable (or a synthetically-generated feed if
not provided). It parses the feed using :mod:`feedparser`, extracts the
stable identifier for each entry and returns a list of dictionaries with the
keys ``id``, ``title`` and ``link``.

The function also records a *run* via :func:`app.storage.save_run`.  The run
record contains a timestamp, a boolean ``success`` flag and an optional
error message.  When successful the function also stores the extracted items
in the ``items`` table.

The logic for stable ID follows the acceptance criteria:

* If an entry contains a ``guid`` element, that value is used.
* Otherwise the SHA‑256 of the entry link is used.  The hash is represented
  as a hex string, lower‑case.

The module is intentionally lightweight and only depends on the standard
library and the ``feedparser`` package.  The tests create a temporary RSS
feed file and patch :func:`urllib.request.urlopen` to return its content,
ensuring that no external HTTP request occurs.
"""

from __future__ import annotations

import hashlib
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional

import feedparser

from .storage import save_run

# Environment variable that can override the default synthetic feed.
FEED_URL_ENV = "FEED_URL"


def _stable_id(entry: feedparser.FeedParserDict) -> str:
    """Return a stable identifier for a feed entry.

    If the entry has a ``guid`` element it is used directly.  Otherwise the
    SHA‑256 hex digest of the entry link is returned.
    """
    guid = entry.get("guid")
    if guid:
        return guid
    link = entry.get("link", "")
    return hashlib.sha256(link.encode("utf-8")).hexdigest()


def fetch_feed() -> List[Dict[str, str]]:
    """Fetch and parse the RSS feed, store a run record and return items.

    Returns
    -------
    list of dict
        Each dict contains the keys ``id``, ``title`` and ``link``.
    """
    url = os.getenv(FEED_URL_ENV, "https://example.com/synthetic")
    timestamp = datetime.utcnow().isoformat()
    items: List[Dict[str, str]] = []
    success = True
    error_msg: Optional[str] = None

    try:
        # Retrieve the feed data. ``urlopen`` handles HTTP/HTTPS.
        with urllib.request.urlopen(url) as resp:
            data = resp.read()
        feed = feedparser.parse(data)
        for entry in feed.entries:
            item_id = _stable_id(entry)
            title = entry.get("title", "")
            link = entry.get("link", "")
            items.append({"id": item_id, "title": title, "link": link})
        # Persist run and items
        save_run(timestamp, success, error_msg, items)
    except Exception as exc:  # pragma: no cover - exercised by tests
        success = False
        error_msg = str(exc)
        # Record the failed run with zero items
        save_run(timestamp, success, error_msg, None)
        items = []
    return items

