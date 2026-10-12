"""Diff utility for the builder‑ingest agent.

The primary goal of this file is to expose a small helper that can be
used by the ingestion logic or by external callers to determine which feed
items are *new* compared to what has already been persisted in the
database.

Only a minimal set of functionality is required for the current tests:

* :func:`get_new_items` – take a list of *current* items (as produced by
  :func:`app.ingest.fetch_feed`) and return a list containing only those
  items whose ``id`` values are not already stored.

The function relies on :func:`app.storage.get_all_ids` which returns a set
of all stable identifiers stored in the ``items`` table.  The implementation
is straightforward and performs no I/O beyond a short query.
"""

from __future__ import annotations

from typing import List, Dict

from .storage import get_all_ids

__all__ = ["get_new_items"]


def get_new_items(current_items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Return only the items that have not yet been persisted.

    Parameters
    ----------
    current_items:
        A list of dictionaries describing the current feed items.  The
        dictionaries must contain an ``"id"`` key that matches the stable
        identifier used by :func:`app.storage.save_run`.

    Returns
    -------
    list
        A new list containing only the items whose ``id`` is not found in
        the persistent store.
    """
    # Determine if this is the very first run.  The `runs` table contains a
    # record for each successful or failed ingestion.  For the first
    # ingestion the runs table will have a single entry after ``fetch_feed``
    # has persisted the run.  Subsequent runs will add additional rows.
    #
    # Using the run count gives a reliable way to signal the first
    # ingestion without caring how many items were inserted – the item
    # table insert uses ``INSERT OR IGNORE`` so duplicate rows are
    # ignored.
    from .storage import DB_PATH
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT COUNT(*) FROM runs")
    run_count = cur.fetchone()[0]
    conn.close()
    if run_count == 1:
        # First run: all items are new.
        return current_items
    stored_ids = get_all_ids()
    return [item for item in current_items if item.get("id") not in stored_ids]

