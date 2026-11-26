# GoSac Mission Control

A multi-client marketing automation fleet for PaidPromo/Cherubim — 10
agents (Sonar, Current, Coral, Harbor, Compass, Horizon, Pearl, Undertow,
Beacon, Mariner) covering GA4, Google Ads, IndiaMART, Amazon/Flipkart,
Meesho, and Meta, each with a dashboard you can actually run and click
"Run" on.

## First time only
```
Setup (first time only).bat
```
Installs every agent's Python dependencies in one pass. Safe to re-run
any time.

## Every time after that
```
Start GoSac Mission Control.bat
```
Starts the local dashboard and opens it in your browser at
http://localhost:8080. Close the window (or Ctrl+C) to stop it.

If it's already running, this just opens the dashboard in a new tab
instead of starting a second copy.

## What you can do from the dashboard
- Switch between clients (each gets their own set of agent configs,
  fully separate)
- See which platforms are auto-detected as connected (real credentials
  filled in) vs. not
- Add a new client, which scaffolds config folders for every agent
- Run any agent's commands directly from its card — pick a command,
  leave "mock" checked to test safely, or uncheck it once real
  credentials exist — and see the real output right there

## Project layout
- `agents/` — the 10 agents, each with its own code, config, README, and
  `--mock` mode
- `clients/` — the client registry and each client's own config folders
  (gitignored except the registry itself, since these can later hold
  real credentials)
- `web/` — the dashboard: `server.py` (local backend), `index.html`
  (the page), its own `README.md` with the API details
- `launch.py` / `setup.py` — the two `.bat` files above call these

## Where to go deeper
- `agents/mariner/README.md` — the orchestrator, running agents on a
  schedule, and the automatic connection-status checker
- `web/README.md` — the dashboard's backend API in detail
- Each agent's own `README.md` — what's real vs. mock, what's confirmed
  by test, and what's still unverified against a live account
