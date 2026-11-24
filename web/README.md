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

## Files
- `index.html` — the dashboard page (full standalone copy of
  `agents/gosac-dashboard.html`, since the Artifact publish step wraps
  that file differently than a plain static server would)
- `server.py` — the local backend described above
- `connection_status.json` — generated, not committed (see `.gitignore`)
