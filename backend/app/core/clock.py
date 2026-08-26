"""Logical-time provider (architecture.md §8).

The demo cannot wait 24 real hours for a cooldown to elapse, so every
timestamp comparison in this system uses a *logical* time carried on the
event payload (`simulated_at`), never `datetime.now()`. This keeps a
batch replay deterministic and reproducible.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def to_iso(dt: datetime) -> str:
    return dt.isoformat()


def now_iso() -> str:
    """Wall-clock time, used only for fields that aren't part of the
    replay's logical ordering (e.g. an audit row's own bookkeeping is
    still keyed off the event's simulated_at, this is not a substitute
    for that). Naive (no tz offset), to stay comparable with every other
    logical timestamp in this system -- all of them are naive ISO strings."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def add_hours(ts: str, hours: float) -> str:
    return to_iso(parse(ts) + timedelta(hours=hours))


def is_at_or_after(ts: str, threshold: str) -> bool:
    return parse(ts) >= parse(threshold)
