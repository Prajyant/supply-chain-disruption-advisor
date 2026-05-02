"""Small RSS/Atom parsing helpers for ingestion feeds."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from html import unescape
import re
from typing import Any


def parse_feed_items(content: bytes, limit: int = 15) -> list[dict[str, Any]]:
    """Parse RSS or Atom bytes into simple feed item dictionaries."""
    root = ET.fromstring(content)
    items = root.findall(".//item")

    if items:
        return [_parse_rss_item(item) for item in items[:limit]]

    entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    return [_parse_atom_entry(entry) for entry in entries[:limit]]


def _parse_rss_item(item: ET.Element) -> dict[str, Any]:
    return {
        "title": _child_text(item, "title"),
        "link": _child_text(item, "link"),
        "published": _child_text(item, "pubDate"),
        "summary": _child_text(item, "description"),
    }


def _parse_atom_entry(entry: ET.Element) -> dict[str, Any]:
    link = ""
    link_node = entry.find("{http://www.w3.org/2005/Atom}link")
    if link_node is not None:
        link = link_node.attrib.get("href", "")

    return {
        "title": _child_text(entry, "{http://www.w3.org/2005/Atom}title"),
        "link": link,
        "published": _child_text(entry, "{http://www.w3.org/2005/Atom}updated"),
        "summary": _child_text(entry, "{http://www.w3.org/2005/Atom}summary"),
    }


def _child_text(item: ET.Element, tag: str) -> str:
    child = item.find(tag)
    if child is None or child.text is None:
        return ""
    return clean_html_text(child.text)


def clean_html_text(value: str) -> str:
    """Return readable text from RSS descriptions that may contain HTML."""
    text = unescape(value or "")
    text = re.sub(r"<a\s+[^>]*>(.*?)</a>", r"\1", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
