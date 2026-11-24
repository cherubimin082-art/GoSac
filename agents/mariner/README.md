# Mariner — Fleet Orchestrator

Runs the other 8 agents on the right cadence and reports what needs a human.

## What it deliberately does NOT do
- **Reimplement any guardrail.** Spend ceilings, the incomplete-listing
  guard, the fulfillment-routing stability check - all of that already
  lives inside each individual agent. Mariner only reads the exit code
  each agent already decided on; it never second-guesses it.
- **Retry a failed job.** A non-zero exit means that agent already
  determined something needs a human - Mariner surfaces that clearly, it
  doesn't loop or paper over it.
- **Run anything on its own.** There's no built-in scheduler. Wire
  `mariner_agent.py run daily` into an actual cron job (or Windows Task
  Scheduler) once you're ready for unattended runs.

## The job manifest (`config.yaml`)
Each job names an agent directory, its command, a schedule tag (`daily`,
`weekly`, `monthly`, `frequent`), and whether it supports `--mock`. Jobs
that don't take `--mock` (the two readiness checks) always run for real,
since there's nothing to fake in a config file read.

| Schedule | Jobs |
|---|---|
| daily | sonar-verify, current-tune |
| frequent | coral-route-leads |
| monthly | compass-classify |
| weekly | undertow-monitor, harbor-check-readiness, horizon-check-readiness, beacon-compile |

## Setup
```bash
pip install -r requirements.txt
```
No credentials of its own - it just shells out to each agent's existing
script using the same Python interpreter you're running Mariner with.

## Usage
```bash
python mariner_agent.py run daily
python mariner_agent.py run weekly
python mariner_agent.py run monthly
python mariner_agent.py run frequent
```

Mock mode (passes `--mock` through to every job that supports it):
```bash
python mariner_agent.py run daily --mock
```

## Confirmed by test, against the real fleet
- `run daily --mock`: correctly ran both sonar-verify and current-tune as
  real subprocesses, caught that Sonar's mock always reports
  `spec_download=0`, and flagged `sonar-verify` as **NEEDS ATTENTION**
  while reporting current-tune as **OK** - the aggregate (1 clean, 1
  needs attention, exit code 1) matched reality exactly.
- `run weekly --mock`: correctly ran all 4 weekly jobs; harbor and horizon
  (no `--mock` support) ran for real against their own unfilled configs
  and correctly came back NOT READY; undertow and beacon came back OK.
  Aggregate: 2 clean, 2 need attention.
- `run monthly --mock` and `run frequent --mock`: both ran their one job
  cleanly end to end.

## What this does NOT do yet
- No scheduler of its own - pair it with cron/Task Scheduler for
  unattended runs.
- No notification channel (Slack/WhatsApp/email) for "needs attention"
  jobs yet - right now you have to read its console output or exit code.
  Wiring a real alert is the natural next step once you're running this
  unattended.

## Multi-client platform (`client_registry.py`)
The fleet isn't hardcoded to GoSac anymore. Every other client gets their
own config.yaml per agent, scaffolded by copying each agent's current
config.yaml as a starting template - same placeholders, same schema, just
a separate file, so no agent's code had to change.

- GoSac/Chirantana is special-cased as client id `"gosac"`: it keeps using
  each agent's existing `agents/<agent>/config.yaml` directly, exactly as
  already built and tested. Adding this system didn't move anything.
- A new client's configs live at `clients/<client_id>/<agent>/config.yaml`.
- `clients/registry.json` is the source of truth for which clients exist.

Add a client from Python directly:
```python
from client_registry import add_client
add_client("Acme Produce Co")
```
Or through the dashboard's **"+ Add client"** button, which calls the same
function via `web/server.py`'s API (see `web/README` section below).

**Confirmed by test:** scaffolding a client created all 8 agents' config
folders correctly; giving that client a real-looking IndiaMART key and
re-running `connection_status.py` showed it as connected while GoSac
stayed untouched - proving the isolation is real, not just structural.

**What this does NOT do yet:** `mariner_agent.py run <schedule>` still
only runs GoSac's agents - its job manifest doesn't yet take a `--client`
flag to run another client's configs. That's the natural next step once
a second client actually has real credentials worth running against.

## Automatic connection status (`connection_status.py`)
Checks every **registered client's** `config.yaml` files for real
(non-placeholder) credentials and writes `connection_status.json` - the
file the GoSac Mission Control dashboard reads to show "Connected"
automatically, instead of relying on someone to click "Mark connected."
Output is keyed by client, so each client's status is independent.

```bash
python connection_status.py
```

**What "connected" means here, precisely:** a real credential has been
filled in where the config previously said `REPLACE_WITH...`, and (where
one is required) the referenced credentials file actually exists on disk.
This is **not** a live API call - no agent pings Google, Meta, or Amazon
just because the dashboard loaded. So a green "Connected" means
"configured with what looks like real credentials," not "we just verified
the connection is live." Run the agent's own `verify`/`check-readiness`
command for that stronger guarantee.

Confirmed by test: with nothing filled in, all 8 checked platforms report
`false`. Temporarily faking a real-looking IndiaMART API key flipped
`coral::IndiaMART Seller Panel` to `true`, and reverting the config
flipped it back - proving the detection logic actually reads the live
config, not a cached assumption.

**Beacon's Looker Studio connector isn't included.** It's set up manually
inside Looker Studio's own UI, so nothing on disk here can confirm it -
the dashboard falls back to the manual "Mark connected" toggle for that
one entry only.

Output goes to both `mariner/connection_status.json` and
`web/connection_status.json` (the second is what the locally-served
dashboard actually fetches). Re-run this any time credentials change, or
wire it into a routine - it's cheap and safe to run often since it never
touches the network.
