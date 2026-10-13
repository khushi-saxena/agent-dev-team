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
from .diff import get_new_items

# Environment variable that can override the default synthetic feed.
FEED_URL_ENV = "FEED_URL"


def _stable_id(entry: feedparser.FeedParserDict) -> str:
    """Return a stable identifier for a feed entry.

    Recent tests exercise two scenarios:
    * The feed provides a ``<guid>`` element – we must use its value.
    * The feed omits ``<guid>`` – we fall back to the SHA‑256 of the link.

    Feedparser normalises RSS feed elements into attributes such as ``id``
    (the value of the ``guid`` element) and ``link``.  Some feeds, like the
    CPython releases feed, expose a dedicated ``guid`` attribute in the
    parsed entry.  To support both forms, we first try the explicit
    ``guid`` key, then the ``id`` key.  If neither are present we use the
    hash of the link.
    """
    # ``guid`` is the explicit element; ``id`` is the fallback used by
    # feedparser when <guid> is present or coalesced.
    guid = entry.get("guid") or entry.get("id")
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
        storage_items: list[dict] = []
        for entry in feed.entries:
            item_id = _stable_id(entry)
            title = entry.get("title", "")
            link = entry.get("link", "")
            # Build the return dict expected by callers/tests.
            item_output = {"id": item_id, "title": title, "link": link}
            items.append(item_output)
            # Build the dictionary for storage that uses ``stable_id`` key.
            storage_items.append({"stable_id": item_id, "title": title, "link": link})
        # Determine which items are new compared to the database.
        new_items = get_new_items(items)
        # ``new_items`` use the key ``id`` for stable identifiers, but
        # :func:`app.storage.save_run` expects ``stable_id``.  Convert the
        # shape so that the downstream save routine can persist the data
        # without error.
        new_items_for_save = [
            {
                "stable_id": it["id"],
                "title": it.get("title"),
                "link": it.get("link"),
                "summary": None,  # no summary provided in this context
            }
            for it in new_items
        ]
        # Persist only the new items for this run.
        save_run(timestamp, success, error_msg, new_items_for_save, new_count=len(new_items))
    except Exception as exc:  # pragma: no cover - exercised by tests
        success = False
        # Capture a clean error message for the database. ``URLError``
        # includes the original reason string.
        error_msg = getattr(exc, "reason", str(exc))
        # Record the failed run with zero items
        save_run(timestamp, success, error_msg, None, new_count=0)
        items = []
    return items

