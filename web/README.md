# GoSac Mission Control — local console

The dashboard for the whole agent fleet, run locally with real
"Add Client" and "Run agent" functionality (the published Artifact
version is read-only for both, since it has no backend to execute
anything).

## Run it
```bash
python server.py
```
Serves the dashboard at http://localhost:8080 and the API it needs:

- `GET /api/clients` — list registered clients
- `POST /api/clients {"name": "..."}` — scaffold a new client's config
  folders (one `config.yaml` per agent, under `clients/<id>/`) and
  register it in `clients/registry.json`
- `GET /api/agents` — list which agents are runnable from the UI and
  their valid commands
- `POST /api/run {agentId, command, clientId, mock}` — actually runs that
  agent's command as a real subprocess (e.g. `python sonar_agent.py
  verify --config clients/<id>/sonar/config.yaml --mock`) and returns its
  exit code, stdout and stderr
- `GET /api/oauth/google/start?agentId=current&clientId=...` — redirects
  to Google's real OAuth consent screen (`agentId` is `current` for
  Google Ads or `sonar` for GA4 — see below)
- `GET /api/oauth/google/callback` — Google redirects here after consent;
  exchanges the code for a refresh token and writes it into that client's
  credentials file (`google-ads.yaml` for Current, `ga4-oauth-credentials.json`
  for Sonar)

Each agent card on the dashboard has a **Run** control once the backend
is up: pick a command, leave "mock" checked (or uncheck it once real
credentials exist), click Run, and the real output appears right there -
no terminal needed.

This is a local-only tool: no auth, binds to `127.0.0.1`, meant to run on
your own machine. `/api/run` executes real code on request from the page
- that's the point, but it means this server should never be exposed
beyond localhost.

## Keeping connection status current
`server.py` only serves files and handles the client API - it doesn't run
`connection_status.py` itself. After adding real credentials for a client
(or a new client), refresh the dashboard's status with:
```bash
python ../agents/mariner/connection_status.py
```
This writes `connection_status.json` here, which the dashboard fetches
automatically on load.

## Real Google OAuth ("Connect (real sign-in)")
Covers both **Current (Google Ads)** and **Sonar (GA4)** — both of
Google's APIs accept a signed-in user's OAuth credentials directly, as
long as that account has access to the Ads account / GA4 property. One
shared OAuth client handles both; `GOOGLE_OAUTH_SCOPES` in `server.py`
picks the right scope (`adwords` or `analytics`) per agent.

**One-time setup:** create `web/google_oauth_client.json` (gitignored,
never commit it):
```json
{
  "client_id": "YOUR_ID.apps.googleusercontent.com",
  "client_secret": "YOUR_SECRET",
  "redirect_uri": "http://localhost:8080/api/oauth/google/callback"
}
```
That OAuth client must be type **Web application** in Google Cloud
Console, with `http://localhost:8080/api/oauth/google/callback` added as
an authorized redirect URI — a **Desktop app** client (the kind used for
the manual `generate_user_credentials.py` script) won't work here, since
that type doesn't support a custom web redirect.

**What happens when you click Connect:** real redirect to Google's
consent screen → you approve → Google redirects back here → the server
exchanges the code for a refresh token and writes it straight into that
client's credentials file:
- **Current:** `google-ads.yaml` (creating it if it doesn't exist yet,
  preserving `developer_token`/`login_customer_id` if already set — OAuth
  can't produce those two, you still fill them in by hand)
- **Sonar:** `ga4-oauth-credentials.json` (you still need to fill in the
  real `ga4.property_id` in `config.yaml` — OAuth proves who you are, not
  which GA4 property you mean)

**Confirmed by test:** the `/start` redirect builds a correct, complete
Google OAuth URL for both agents (verified client_id, redirect_uri,
per-agent scope, and state all present and correctly encoded, with
`current` getting the `adwords` scope and `sonar` getting the
`analytics` scope); an unsupported `agentId` fails with a clean error
instead of a crash; `/callback` correctly rejects a missing code, and
correctly surfaces a Google-side error (e.g. `access_denied`) instead of
swallowing it. Sonar's credential auto-detection (OAuth file vs. service
account file) was also verified directly against both file shapes. The
actual token exchange requires a real browser consent round-trip, so
that step itself is unverified until you click through it for real.

## Files
- `index.html` — the dashboard page (full standalone copy of
  `agents/gosac-dashboard.html`, since the Artifact publish step wraps
  that file differently than a plain static server would)
- `server.py` — the local backend described above
- `connection_status.json` — generated, not committed (see `.gitignore`)
