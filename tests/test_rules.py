import json
import os
import unittest

from portal_feed.cds import CATEGORY_PRIVATE, rows_from_columns
from portal_feed.rules import build_feed, is_excluded, latest_per_track

DATA = os.environ.get("PORTAL_FEED_TEST_DATA", os.path.join(os.path.dirname(__file__), "..", "data"))
HAVE_DATA = os.path.exists(os.path.join(DATA, "cds_current.json"))


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return rows_from_columns(json.load(f))


@unittest.skipUnless(HAVE_DATA, "CDS fixtures not present (set PORTAL_FEED_TEST_DATA)")
class RulesTests(unittest.TestCase):
    def test_excludes_test_dd_and_placeholders(self):
        self.assertTrue(is_excluded({"name": "Cambridge Test Routes", "desc": ""}))
        self.assertTrue(is_excluded({"name": "Porsche Aragon DD", "desc": ""}))
        self.assertTrue(is_excluded({"name": "Gaydon", "desc": "(dummy delivery)"}))
        self.assertTrue(is_excluded({"name": "1 start here", "desc": ""}))
        self.assertTrue(is_excluded({"name": "WMG_MFM18 customercopy", "desc": ""}))
        self.assertFalse(is_excluded({"name": "Silverstone 2018", "desc": "digital circuit model"}))

    def test_one_item_per_track_latest_wins(self):
        items = [
            {"id": 1, "name": "Monza 2014", "date": "2019-01-01"},
            {"id": 2, "name": "Monza 2014", "date": "2021-06-01"},
            {"id": 3, "name": "Monza 2024", "date": "2024-01-01"},
        ]
        kept = latest_per_track(items)
        self.assertEqual(sorted(i["id"] for i in kept), [2, 3])

    def test_private_never_in_available(self):
        current = load("cds_current.json")
        feed = build_feed("1", assigned_items=[], current_items=current,
                          generated_at="now")
        ids = {a["content_id"] for a in feed["available_to_request"]}
        private_ids = {r["id"] for r in current if r["categoryid"] == CATEGORY_PRIVATE}
        self.assertFalse(ids & private_ids)

    def test_available_has_no_excluded_names_and_one_per_track(self):
        current = load("cds_current.json")
        feed = build_feed("1", assigned_items=[], current_items=current, generated_at="now")
        tracks = [a["track"].strip().lower() for a in feed["available_to_request"]]
        self.assertEqual(len(tracks), len(set(tracks)))
        for a in feed["available_to_request"]:
            self.assertFalse(is_excluded({"name": a["track"], "desc": ""}))
            self.assertEqual(a["status"], "available to request")

    def test_assigned_private_is_shown_for_that_uid(self):
        assigned = [{"id": 9001, "categoryid": 25, "name": "Koenigssee Eisarena",
                     "version": "02+", "date": "2024-01-01", "url": "locations/x.zip", "desc": ""}]
        feed = build_feed("1", assigned_items=assigned, current_items=[], generated_at="now")
        self.assertEqual([a["content_id"] for a in feed["assigned"]], [9001])
        self.assertEqual(feed["assigned"][0]["status"], "assigned")


if __name__ == "__main__":
    unittest.main()
