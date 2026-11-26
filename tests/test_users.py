import json
import os
import unittest
from unittest import mock

from portal_feed.cds import CdsClient

DATA = os.environ.get("PORTAL_FEED_TEST_DATA", os.path.join(os.path.dirname(__file__), "..", "data"))
USERSELECT = os.path.join(DATA, "cds_userselect.json")


class UserDirectoryTests(unittest.TestCase):
    def test_users_maps_userid_to_username(self):
        client = CdsClient("https://content.example", "u", "p")
        payload = [{"userid": 15, "username": "BMW Motorsport"}, {"userid": 12, "username": "Ferrari"}]
        with mock.patch.object(CdsClient, "_get", return_value=payload):
            users = client.users()
        self.assertEqual(users, {15: "BMW Motorsport", 12: "Ferrari"})

    @unittest.skipUnless(os.path.exists(USERSELECT), "userselect export not present (set PORTAL_FEED_TEST_DATA)")
    def test_real_export_has_bmw_motorsport_as_15(self):
        with open(USERSELECT, encoding="utf-8") as f:
            d = json.load(f)
        users = dict(zip(d["userid"], d["username"]))
        self.assertEqual(users[15], "BMW Motorsport")


if __name__ == "__main__":
    unittest.main()
