"""Read-only client for the CDS admin jsonresponder.

Responses are column-oriented: {"id": [...], "name": [...], ...} with parallel arrays.
Credentials come from the environment and are never logged.
"""
import base64
import json
import urllib.parse
import urllib.request

CATEGORY_CURRENT = 3
CATEGORY_DEPRECATED = 24
CATEGORY_PRIVATE = 25


def rows_from_columns(payload):
    """Turn a column-oriented payload into a list of dicts."""
    if not payload:
        return []
    keys = list(payload.keys())
    n = len(payload[keys[0]]) if keys else 0
    return [{k: payload[k][i] for k in keys} for i in range(n)]


class CdsClient:
    def __init__(self, base_url, username, password, timeout=20):
        self.base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._auth = f"Basic {token}"
        self.timeout = timeout

    def _get(self, op, **params):
        query = urllib.parse.urlencode({"op": op, **params})
        req = urllib.request.Request(
            f"{self.base_url}/admin/ajax_jsonresponder.php?{query}",
            headers={"Authorization": self._auth, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return rows_from_columns(json.loads(resp.read().decode("utf-8")))

    def assigned(self, uid):
        """Assigned items for this uid across the three DCM categories."""
        items = []
        for cid in (CATEGORY_CURRENT, CATEGORY_DEPRECATED, CATEGORY_PRIVATE):
            items += self._get("assignedcontent", uid=uid, cid=cid, so=0, sc1=0, sc2=5, lo=0)
        return items

    def unassigned(self, uid, cid=CATEGORY_CURRENT):
        return self._get("unassignedcontent", uid=uid, cid=cid, so=0, sc1=0, sc2=5, lo=0)
