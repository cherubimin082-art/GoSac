# Sonar — GA4 Tracking Agent

Covers DN-01: sets up GA4 conversion tracking for Chirantana & GoSac (RFQ form
submits, call clicks, WhatsApp clicks, spec downloads), then verifies the
events are actually firing.

## Two ways to get access — pick one

`ga4.credentials_path` points at a JSON file, and `get_credentials` in
`sonar_agent.py` auto-detects which kind it is by its shape — no config
flag needed to say which.

### Option A — One-click OAuth sign-in (via the dashboard)
Click **"Connect (real sign-in)"** on Sonar's GA4 card in GoSac Mission
Control. You sign in with a Google account that already has access to the
GA4 property (Admin, Editor, or similar) — no separate service account to
create. The dashboard's backend writes a `ga4-oauth-credentials.json` file
and points `config.yaml` at it automatically.

Needs `web/google_oauth_client.json` set up once (see `web/README.md`) —
the same OAuth client Current's Connect button uses, since this reuses
the same Web application type client with
`http://localhost:8080/api/oauth/google/callback` registered.

### Option B — Service account (manual, no sign-in dependency)
Good when you want a credential that doesn't belong to a specific person.
1. A Google Cloud project with the Google Analytics Admin API and Google
   Analytics Data API enabled.
2. A service account in that project, with a downloaded JSON key.
3. The service account's email added as a user on the Chirantana GA4
   property (Editor role to create events, Viewer is enough for verify-only
   runs). This step is the human-gated part — it depends on Girish/Chirantana
   granting access (task CH-01).

## Prerequisite either way
The GA4 **property ID** (Admin > Property Settings in GA4) — OAuth proves
who you are, not which property you mean, so this always needs to be
filled in by hand in `config.yaml`.

## Setup
```bash
pip install -r requirements.txt
```

Edit `config.yaml`:
- `ga4.property_id` — the numeric GA4 property ID
- `ga4.credentials_path` — filled in automatically by Option A, or point
  it at your service account JSON key for Option B
- `events_to_track` — add/remove events as needed

## Usage

Register the conversion events (run once):
```bash
python sonar_agent.py setup
```

Verify events are firing (run any time, or on a schedule):
```bash
python sonar_agent.py verify
```

Exit code is non-zero if anything failed to register or isn't firing yet —
safe to wire into a cron job or CI check that alerts on failure.

## Confirmed by test
`get_credentials`'s auto-detection was tested directly against both
credential shapes: a file with a `refresh_token` field correctly builds
`google.oauth2.credentials.Credentials` (the OAuth path); a file without
one correctly falls through to `service_account.Credentials.from_service_account_info`
(the service-account path). Mock mode re-verified with no regressions
after this change.

## What this does NOT do
- Does not touch ad spend, billing, or any other agent's data.
- Does not guess at GA4 access — if the credentials lack permission,
  the API call fails loudly instead of silently skipping.
- The OAuth route (Option A) has never completed a real browser consent
  round-trip yet — the redirect URL and credential-detection logic are
  verified, but the first real click-through is the actual test.
