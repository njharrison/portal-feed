"""Content rules agreed for the customer portal.

- Private (category 25) is never advertised; it appears only in the uid's assigned list.
- Current (category 3) items are shown as "available to request".
- Test, DD and placeholder items are excluded.
- Only the latest version per track is shown.
"""
import re

from .cds import CATEGORY_CURRENT, CATEGORY_DEPRECATED, CATEGORY_PRIVATE

EXCLUDE_PATTERNS = [
    r"\btest\b",
    r"\btour test\b",
    r"\bwinter test\b",
    r"\bsmoothing\b",
    r"\bcustomercopy\b",
    r"\bDD\b",
    r"\bdummy delivery\b",
    r"^\s*1 start here\s*$",
]
_EXCLUDE_RE = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)


def is_excluded(item):
    # Check name and description separately so anchored patterns (e.g. "1 start here") work.
    return any(_EXCLUDE_RE.search(item.get(field) or "") for field in ("name", "desc"))


def track_key(name):
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def latest_per_track(items):
    """Keep one item per track: the most recent release date, ties broken by id."""
    best = {}
    for item in items:
        key = track_key(item.get("name"))
        current = best.get(key)
        rank = (item.get("date") or "", item.get("id") or 0)
        if current is None or rank > current[0]:
            best[key] = (rank, item)
    return [entry[1] for entry in best.values()]


def to_public(item, status):
    return {
        "content_id": item.get("id"),
        "track": item.get("name"),
        "version": item.get("version"),
        "release_date": item.get("date"),
        "status": status,
        "url": item.get("url"),
    }


def build_feed(uid, assigned_items, current_items, generated_at, include_deprecated=False):
    """Build the portal feed for one uid.

    assigned_items: items from assignedcontent for this uid (any category).
    current_items: items from unassignedcontent for category 3 (available to request).
    Private items from unassignedcontent are deliberately not accepted here.
    """
    assigned = [i for i in assigned_items if not is_excluded(i)]
    assigned_ids = {i.get("id") for i in assigned}

    available_pool = [
        i for i in current_items
        if i.get("categoryid") == CATEGORY_CURRENT and not is_excluded(i)
        and i.get("id") not in assigned_ids
    ]
    if include_deprecated:
        available_pool += [
            i for i in assigned_items
            if i.get("categoryid") == CATEGORY_DEPRECATED and not is_excluded(i)
        ]

    available = latest_per_track(available_pool)

    return {
        "uid": uid,
        "generated_at": generated_at,
        "assigned": [to_public(i, "assigned") for i in assigned],
        "available_to_request": [to_public(i, "available to request") for i in available],
    }
