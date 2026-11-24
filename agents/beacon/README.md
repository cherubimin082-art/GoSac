# Beacon — Reporting Agent

Pulls every other agent's own output into one weekly summary.

## Scope note on Looker Studio (important)
There's no API to push data directly into a Looker Studio dashboard. The
real integration is Looker Studio **connecting to a live source** -
Google Sheets, BigQuery, or a CSV. GA4 and Google Ads data flow into
Looker Studio through their own native connectors directly; Beacon does
not duplicate that.

What Beacon actually does: reads every sibling agent's state/output file
(read-only - it never writes to another agent's files) and produces:
- `beacon_report.json` — for programmatic use
- `beacon_report.csv` — the file to point Looker Studio's Sheets/CSV
  connector at (upload it to a Sheet, or re-sync it there on a schedule)

## The honest rule
A source with no file yet is reported as **"no data yet"**, never a
fabricated zero or a guessed number. A missing agent output means that
agent hasn't run, not that it did zero work.

## GoSac Fleet Results dashboard
A live dashboard (an Artifact, not part of this repo) shows Beacon's
numbers as stat tiles: "GoSac Fleet Results". It reads an uploaded copy
of `beacon_report.csv`, not a live connector, so refreshing it is a
two-step process:

```bash
python refresh_dashboard.py
```

This re-runs `compile` for real and prints a reminder, because the second
step - uploading the CSV into the dashboard's store and updating its
`datasets/fleet` record - can only be done through Claude's Artifact/
ArtifactData tools, not from a standalone script. Once this script says
the CSV is up to date, ask Claude (in a Claude Code session) to "sync the
dashboard with the latest Beacon report."

## Setup
```bash
pip install -r requirements.txt
```

`config.yaml`'s `sources` section already points at the other agents'
real output paths (`coral_state.json`, `compass_state.json`,
`pearl_listings.json`, `meesho_catalog.csv`) - nothing to fill in unless
you move those files.

## Usage
```bash
python beacon_agent.py compile
```

Mock mode (built-in fake data, doesn't touch sibling agent files):
```bash
python beacon_agent.py compile --mock
```

## Confirmed by test
- With no sibling agent having run yet, `compile` correctly reported
  **"no data yet"** for all four sources - not zeros, not guesses.
- After running Coral's `route-leads --mock` and Compass's
  `classify --mock`, re-running `compile` correctly picked up their real
  output (`leads_routed=2`, `skus_tracked=5`) while still correctly
  reporting "no data yet" for Pearl and Horizon, which hadn't run.
- `compile --mock` produces a clean `metric,value` CSV with all four
  sources' numbers, ready for a Sheets upload.

## What this does NOT do
- Does not connect to Looker Studio itself - that one-time connector
  setup (pointing Looker Studio at the CSV, or a Sheet synced from it) is
  a manual step, done once in Looker Studio's own UI.
- Does not pull GA4/Google Ads data directly - those already have native
  Looker Studio connectors and don't need Beacon in between.
- Does not read from Harbor, Sonar, Current, or Undertow yet, since none
  of them write a persistent state file the way Coral/Compass/Pearl/
  Horizon do. Extend `sources` in config.yaml if/when those agents start
  logging something worth reporting on.
