"""Read-only Freshdesk client (API v2). Authenticates with the API key as the Basic username."""
import base64

from .http_json import request_json


class FreshdeskClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{api_key}:X".encode()).decode()
        self._headers = {"Authorization": f"Basic {token}"}

    def company(self, company_id):
        data = request_json("GET", f"{self.base_url}/api/v2/companies/{int(company_id)}", headers=self._headers)
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "domains": data.get("domains") or [],
            "description": data.get("description"),
        }
