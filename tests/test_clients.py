import os
import unittest
from unittest import mock

from portal_feed import freshdesk, sugar
from portal_feed.http_json import UpstreamError
from portal_feed.mapping import load_customer_map
from portal_feed.service import FeedService, FeedCache

MAP = os.path.join(os.environ.get("PORTAL_FEED_TEST_DATA", os.path.join(os.path.dirname(__file__), "..", "data")), "freshdesk_map.csv")
HAVE_MAP = os.path.exists(MAP)


@unittest.skipUnless(HAVE_MAP, "customer map not present (set PORTAL_FEED_TEST_DATA)")
class MappingTests(unittest.TestCase):
    def test_counts_match_reviewed_map(self):
        f2s, s2f = load_customer_map(MAP)
        self.assertEqual(len(f2s), 233)
        self.assertEqual(len(s2f), 236)

    def test_one_to_many_both_directions(self):
        f2s, s2f = load_customer_map(MAP)
        self.assertEqual(len(f2s["11000002768"]), 2)
        self.assertEqual(sorted(s2f["14b6c964-8752-c0ca-71d5-534bb19ddd7d"]), ["11000024943", "11000061737"])


class FreshdeskTests(unittest.TestCase):
    def test_company_parsed_and_auth_header_sent(self):
        client = freshdesk.FreshdeskClient("https://example.freshdesk.com/", "KEY")
        with mock.patch.object(freshdesk, "request_json", return_value={"id": 5, "name": "Acme", "domains": ["acme.com"]}) as rj:
            c = client.company(5)
        self.assertEqual(c["name"], "Acme")
        url = rj.call_args.args[1]
        self.assertEqual(url, "https://example.freshdesk.com/api/v2/companies/5")
        self.assertTrue(rj.call_args.kwargs["headers"]["Authorization"].startswith("Basic "))


class SugarTests(unittest.TestCase):
    def test_token_fetched_once_then_reused(self):
        client = sugar.SugarClient("https://x.sugaropencloud.eu", "id", "secret", "u", "p")
        responses = [
            {"access_token": "T1", "expires_in": 3600},
            {"id": "a1", "name": "Acme"},
            {"id": "a2", "name": "Acme 2"},
        ]
        with mock.patch.object(sugar, "request_json", side_effect=responses) as rj:
            client.get_record("Accounts", "a1", fields=["name"])
            client.get_record("Accounts", "a2", fields=["name"])
        self.assertEqual(rj.call_count, 3)  # one token call, two record calls
        self.assertEqual(rj.call_args_list[0].args[1], "https://x.sugaropencloud.eu/rest/v11_8/oauth2/token")


@unittest.skipUnless(HAVE_MAP, "customer map not present (set PORTAL_FEED_TEST_DATA)")
class CustomerTests(unittest.TestCase):
    def test_customer_lookup_returns_company_and_accounts(self):
        f2s, s2f = load_customer_map(MAP)
        fd = mock.Mock()
        fd.company.return_value = {"id": 11000002768, "name": "Acme"}
        sg = mock.Mock()
        sg.get_record.side_effect = lambda module, rid, fields=None: {"name": f"Account {rid[:4]}"}
        svc = FeedService(cds=None, cache=FeedCache(60), freshdesk=fd, sugar=sg, customer_map=(f2s, s2f))
        out = svc.customer_for("11000002768")
        self.assertEqual(out["company"]["name"], "Acme")
        self.assertEqual(len(out["sugar_accounts"]), 2)

    def test_upstream_errors_do_not_leak_headers(self):
        err = UpstreamError("GET https://x failed: HTTP 401")
        self.assertNotIn("Authorization", str(err))


if __name__ == "__main__":
    unittest.main()
