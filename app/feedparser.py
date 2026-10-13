"""Minimal stub of the external :mod:`feedparser` package.

The real *feedparser* library is extensive; this stub implements only the
features required by the builder‑ingest code and the unit tests.
It parses a very small subset of RSS v2.0 feeds and returns an object
with an ``entries`` attribute – a list of dictionaries that provide the
``guid``, ``title`` and ``link`` keys.  The parser is intentionally
light‑weight and does not attempt to fully implement the spec.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from types import SimpleNamespace

__all__ = ["parse"]


def _element_text(e: ET.Element | None) -> str:
    return e.text.strip() if e is not None and e.text else ""


def parse(data: bytes) -> SimpleNamespace:
    """Parse a minimal RSS v2.0 XML feed.

    Parameters
    ----------
    data:
        Raw bytes of the XML document.
    """
    root = ET.fromstring(data)
    channel = root.find("channel") if root.tag != "rss" else root
    entries = []
    if channel is not None:
        for item in channel.findall("item"):
            guid_el = item.find("guid")
            title_el = item.find("title")
            link_el = item.find("link")
            entries.append(
                {
                    "guid": _element_text(guid_el),
                    "title": _element_text(title_el),
                    "link": _element_text(link_el),
                }
            )
    return SimpleNamespace(entries=entries)
