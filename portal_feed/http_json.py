"""Small JSON-over-HTTP helper shared by the Sugar and Freshdesk clients (stdlib only)."""
import json
import urllib.error
import urllib.request


class UpstreamError(Exception):
    pass


def request_json(method, url, headers=None, body=None, timeout=20):
    data = None
    hdrs = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        # Never include the request headers (credentials) in the error.
        raise UpstreamError(f"{method} {url.split('?')[0]} failed: HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise UpstreamError(f"{method} {url.split('?')[0]} unreachable: {exc.reason}") from None
