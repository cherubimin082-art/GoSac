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
