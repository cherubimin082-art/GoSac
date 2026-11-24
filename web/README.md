# GoSac Mission Control — local console

The dashboard for the whole agent fleet, run locally with real
"Add Client" functionality (the published Artifact version is read-only
for clients, since it has no backend to write files).

## Run it
```bash
python server.py
```
Serves the dashboard at http://localhost:8080 and the client API it needs:

- `GET /api/clients` — list registered clients
- `POST /api/clients {"name": "..."}` — scaffold a new client's config
  folders (one `config.yaml` per agent, under `clients/<id>/`) and
  register it in `clients/registry.json`

This is a local-only tool: no auth, binds to `127.0.0.1`, meant to run on
your own machine. Don't expose it on a public network as-is.

## Keeping connection status current
`server.py` only serves files and handles the client API - it doesn't run
`connection_status.py` itself. After adding real credentials for a client
(or a new client), refresh the dashboard's status with:
```bash
python ../agents/mariner/connection_status.py
```
This writes `connection_status.json` here, which the dashboard fetches
automatically on load.

## Files
- `index.html` — the dashboard page (full standalone copy of
  `agents/gosac-dashboard.html`, since the Artifact publish step wraps
  that file differently than a plain static server would)
- `server.py` — the local backend described above
- `connection_status.json` — generated, not committed (see `.gitignore`)
