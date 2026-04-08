"""
deduplicator.py
Tracks which article URLs have already been reported so repeat
runs don't re-surface the same deals.

State is stored in data/seen.json and committed back to the repo
by the GitHub Actions workflow after each run.
"""
import json
import os
from pathlib import Path

_SEEN_FILE = Path(__file__).parent.parent / "data" / "seen.json"


def _load_seen() -> set[str]:
    if _SEEN_FILE.exists():
        try:
            return set(json.loads(_SEEN_FILE.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return set()


def _save_seen(seen: set[str]) -> None:
    _SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))


def filter_new(articles: list[dict]) -> tuple[list[dict], set[str]]:
    """
    Remove articles whose URL was already seen in a prior run.
    Returns (new_articles, updated_seen_set).
    """
    seen = _load_seen()
    new_articles = []

    for a in articles:
        url = a.get("url", "")
        if url and url not in seen:
            new_articles.append(a)

    new_urls = {a["url"] for a in new_articles if a.get("url")}
    updated_seen = seen | new_urls

    dropped = len(articles) - len(new_articles)
    if dropped:
        print(f"  ✓ Deduplicated: {dropped} already-seen articles removed")
    print(f"  ✓ {len(new_articles)} new articles after deduplication")

    return new_articles, updated_seen


def persist_seen(seen: set[str]) -> None:
    """Write the updated seen set to disk so the workflow can commit it."""
    _save_seen(seen)
    print(f"  ✓ seen.json updated ({len(seen)} total tracked URLs)")
