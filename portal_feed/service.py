"""Read-only HTTP service that returns a customer's portal feed.

GET /healthz            -> {"status": "ok"}
GET /customer/<freshdesk_id> -> Freshdesk company plus linked Sugar account IDs (auth required)
GET /users              -> CDS user directory (userid and username), auth required
GET /feed/<uid>         -> feed JSON for that CDS uid (cached per uid); needs Authorization: Bearer <FEED_API_TOKEN>
GET /feed/<uid>?refresh=1 -> bypass cache and re-query CDS

Configuration comes from environment variables (see README.md).
"""
import datetime
import hmac
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .cds import CdsClient
from .freshdesk import FreshdeskClient
from .mapping import load_customer_map
from .sugar import SugarClient
from .rules import build_feed

log = logging.getLogger("portal_feed")


class FeedCache:
    def __init__(self, ttl_seconds):
        self.ttl = ttl_seconds
        self._items = {}
        self._lock = threading.Lock()

    def get(self, uid):
        with self._lock:
            hit = self._items.get(uid)
        if hit and time.time() - hit[0] < self.ttl:
            return hit[1]
        return None

    def put(self, uid, feed):
        with self._lock:
            self._items[uid] = (time.time(), feed)


class FeedService:
    def __init__(self, cds, cache, include_deprecated=False, freshdesk=None, sugar=None, customer_map=None):
        self.cds = cds
        self.cache = cache
        self.include_deprecated = include_deprecated
        self.freshdesk = freshdesk
        self.sugar = sugar
        self.f2s, self.s2f = customer_map or ({}, {})
        self._users = None

    def user_directory(self):
        if self._users is None:
            self._users = self.cds.users()
        return self._users

    def customer_for(self, freshdesk_id):
        """Freshdesk company plus the Sugar accounts it maps to (one-to-many is normal here)."""
        sugar_ids = self.f2s.get(str(freshdesk_id), [])
        company = self.freshdesk.company(freshdesk_id) if self.freshdesk else None
        accounts = []
        for sid in sugar_ids:
            record = self.sugar.get_record("Accounts", sid, fields=["name"]) if self.sugar else {}
            accounts.append({"sugar_account_id": sid, "name": record.get("name")})
        return {"freshdesk_company_id": str(freshdesk_id), "company": company, "sugar_accounts": accounts}

    def feed_for(self, uid, refresh=False):
        if not refresh:
            cached = self.cache.get(uid)
            if cached is not None:
                return cached
        assigned = self.cds.assigned(uid)
        current = self.cds.unassigned(uid)
        feed = build_feed(
            uid,
            assigned_items=assigned,
            current_items=current,
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            include_deprecated=self.include_deprecated,
        )
        self.cache.put(uid, feed)
        return feed


def make_handler(service, api_token):
    class Handler(BaseHTTPRequestHandler):
        def _authorised(self):
            # Constant-time comparison; the portal backend must send "Authorization: Bearer <token>".
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {api_token}"
            return bool(api_token) and hmac.compare_digest(supplied.encode(), expected.encode())

        def _send(self, code, body):
            data = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/healthz":
                return self._send(200, {"status": "ok"})
            parts = url.path.strip("/").split("/")
            if url.path == "/users":
                if not self._authorised():
                    return self._send(401, {"error": "unauthorised"})
                try:
                    users = service.user_directory()
                except Exception:
                    log.exception("user directory fetch failed")
                    return self._send(502, {"error": "upstream unavailable"})
                return self._send(200, [{"uid": k, "username": v} for k, v in sorted(users.items())])
            if len(parts) == 2 and parts[0] == "customer" and parts[1].isdigit():
                if not self._authorised():
                    return self._send(401, {"error": "unauthorised"})
                try:
                    return self._send(200, service.customer_for(parts[1]))
                except Exception:
                    log.exception("customer lookup failed for %s", parts[1])
                    return self._send(502, {"error": "upstream unavailable"})
            if len(parts) == 2 and parts[0] == "feed" and parts[1].isdigit():
                if not self._authorised():
                    return self._send(401, {"error": "unauthorised"})
                refresh = parse_qs(url.query).get("refresh", ["0"])[0] == "1"
                try:
                    if int(parts[1]) not in service.user_directory():
                        return self._send(404, {"error": "unknown uid"})
                    feed = service.feed_for(parts[1], refresh=refresh)
                except Exception:
                    log.exception("feed build failed for uid=%s", parts[1])
                    return self._send(502, {"error": "upstream unavailable"})
                return self._send(200, feed)
            return self._send(404, {"error": "not found"})

        def log_message(self, fmt, *args):
            log.info("%s - %s", self.address_string(), fmt % args)

    return Handler


def config_from_env():
    return {
        "freshdesk_base_url": os.environ.get("FRESHDESK_BASE_URL", ""),
        "freshdesk_api_key": os.environ.get("FRESHDESK_API_KEY", ""),
        "sugar_base_url": os.environ.get("SUGAR_BASE_URL", ""),
        "sugar_client_id": os.environ.get("SUGAR_CLIENT_ID", ""),
        "sugar_client_secret": os.environ.get("SUGAR_CLIENT_SECRET", ""),
        "sugar_username": os.environ.get("SUGAR_USERNAME", ""),
        "sugar_password": os.environ.get("SUGAR_PASSWORD", ""),
        "customer_map_path": os.environ.get("CUSTOMER_MAP_PATH", "data/freshdesk_map.csv"),
        "cds_base_url": os.environ["CDS_BASE_URL"],
        "cds_username": os.environ["CDS_USERNAME"],
        "cds_password": os.environ["CDS_PASSWORD"],
        "cache_ttl": int(os.environ.get("FEED_CACHE_TTL_SECONDS", "900")),
        "include_deprecated": os.environ.get("FEED_INCLUDE_DEPRECATED", "0") == "1",
        "port": int(os.environ.get("PORT", "8080")),
        "api_token": os.environ["FEED_API_TOKEN"],
    }


def main():
    logging.basicConfig(level=logging.INFO)
    cfg = config_from_env()
    cds = CdsClient(cfg["cds_base_url"], cfg["cds_username"], cfg["cds_password"])
    freshdesk = FreshdeskClient(cfg["freshdesk_base_url"], cfg["freshdesk_api_key"]) if cfg["freshdesk_base_url"] else None
    sugar = SugarClient(cfg["sugar_base_url"], cfg["sugar_client_id"], cfg["sugar_client_secret"],
                        cfg["sugar_username"], cfg["sugar_password"]) if cfg["sugar_base_url"] else None
    service = FeedService(cds, FeedCache(cfg["cache_ttl"]), cfg["include_deprecated"],
                          freshdesk=freshdesk, sugar=sugar,
                          customer_map=load_customer_map(cfg["customer_map_path"]))
    server = ThreadingHTTPServer(("0.0.0.0", cfg["port"]), make_handler(service, cfg["api_token"]))
    log.info("listening on %s", cfg["port"])
    server.serve_forever()


if __name__ == "__main__":
    main()
