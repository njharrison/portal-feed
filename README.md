# Portal feed service

Read-only service that returns a customer's content feed from the CDS admin jsonresponder.
Stdlib-only Python 3.11+, no third-party packages.

## Endpoints

- `GET /healthz`: liveness check, no auth.
- `GET /customer/<freshdesk_id>`: Freshdesk company plus the Sugar accounts it maps to (auth required).
- `GET /feed/<uid>`: feed for one CDS uid. Requires `Authorization: Bearer <FEED_API_TOKEN>`.
  Cached per uid for `FEED_CACHE_TTL_SECONDS`. Add `?refresh=1` to bypass the cache.

Response: `assigned` (includes Private, for this uid only) and `available_to_request`
(Current items, one per track, latest release date wins). Private items are never in the available list.

## Configuration (environment variables)

| Variable | Purpose |
|---|---|
| `CDS_BASE_URL` | e.g. `https://content.rfpro.com` |
| `CDS_USERNAME`, `CDS_PASSWORD` | Dedicated read-only CDS service account. Never commit. |
| `FEED_API_TOKEN` | Shared secret the portal backend sends. Never commit. |
| `FEED_CACHE_TTL_SECONDS` | Default 900 |
| `FEED_INCLUDE_DEPRECATED` | `1` to include Deprecated items in the available list. Default `0`. |
| `PORT` | Default 8080 |
| `FRESHDESK_BASE_URL`, `FRESHDESK_API_KEY` | Read-only Freshdesk API v2. Optional; the customer endpoint returns no company without it. |
| `SUGAR_BASE_URL`, `SUGAR_CLIENT_ID`, `SUGAR_CLIENT_SECRET`, `SUGAR_USERNAME`, `SUGAR_PASSWORD` | Sugar Cloud REST v11 via OAuth2 password grant. Use a dedicated read-only user. |
| `CUSTOMER_MAP_PATH` | Default `data/freshdesk_map.csv` |

## Run

    python3 -m portal_feed

## Test

    python3 -m unittest discover -s tests -t .

Tests read the CDS exports and customer map from `data/` (or the folder in `PORTAL_FEED_TEST_DATA`). Those files contain internal item and customer data, are git-ignored, and are never committed. Without them the data-dependent tests are skipped.

## Status of the clients

- Freshdesk and Sugar clients are written and unit-tested with mocked responses. **They have not been run against the live APIs.** The Sugar filter endpoint, module names and field names are assumptions to verify against the first real response.
- The Freshdesk to Sugar map (`data/freshdesk_map.csv`) is loaded and used by `/customer`.

## Not yet built

- **uid to customer link.** `/feed/<uid>` takes a CDS uid directly. The Account Details report's ID column is the Sugar account ID, so the CDS uid may not be the same value. Check against one known customer before relying on it.
- **Jira.** No client yet. Release notes need Sugar Products, and Jira links need the Build records.
- **Tickets.** Not included in the Freshdesk client.
- **Licensed content (releasecategory 6).** The jsonresponder output doesn't include release category, so this needs the objects table or a separate source. Parked until the Contracts module is confirmed.
- **Outbound IP for the CDS MySQL whitelist.** Only needed if the service connects to MySQL directly. The jsonresponder is HTTPS and needs no IP whitelisting.

## Security notes

- Private content is only returned for the uid it's assigned to, and only with a valid bearer token.
- The CDS password and API token must come from the environment. The service never logs them.
- The earlier CDS account export contained plaintext passwords. Rotate those before deploying.
