"""Read-only Sugar Cloud REST client (v11). OAuth2 password grant; token cached until expiry."""
import time

from .http_json import request_json

API = "/rest/v11_8"


class SugarClient:
    def __init__(self, base_url, client_id, client_secret, username, password, platform="portal-feed"):
        self.base_url = base_url.rstrip("/")
        self._creds = {
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": password,
            "platform": platform,
        }
        self._token = None
        self._expires_at = 0.0

    def _auth_headers(self):
        if not self._token or time.time() > self._expires_at - 60:
            data = request_json("POST", f"{self.base_url}{API}/oauth2/token", body=self._creds)
            self._token = data["access_token"]
            self._expires_at = time.time() + int(data.get("expires_in", 3600))
        return {"Authorization": f"Bearer {self._token}"}

    def get_record(self, module, record_id, fields=None):
        qs = f"?fields={','.join(fields)}" if fields else ""
        return request_json("GET", f"{self.base_url}{API}/{module}/{record_id}{qs}", headers=self._auth_headers())

    def filter(self, module, field, value, fields=None, max_num=200):
        """Records of `module` where `field` equals `value`."""
        body = {"filter": [{field: {"$equals": value}}], "max_num": max_num}
        if fields:
            body["fields"] = fields
        data = request_json("POST", f"{self.base_url}{API}/{module}/filter", headers=self._auth_headers(), body=body)
        return data.get("records", [])
