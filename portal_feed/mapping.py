"""Freshdesk company <-> Sugar account mapping, from the reviewed customer map file."""
import csv
from collections import defaultdict


def load_customer_map(path):
    """Return (freshdesk_to_sugar, sugar_to_freshdesk); each maps to a list of IDs."""
    f2s = defaultdict(list)
    s2f = defaultdict(list)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            fd = (row.get("freshdesk_company_id") or "").strip()
            sg = (row.get("sugar_account_id") or "").strip()
            if not fd or not sg:
                continue
            if sg not in f2s[fd]:
                f2s[fd].append(sg)
            if fd not in s2f[sg]:
                s2f[sg].append(fd)
    return dict(f2s), dict(s2f)
