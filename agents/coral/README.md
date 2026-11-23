# Coral — IndiaMART Catalog & Lead-Routing Agent

Covers DN-02: rewrites IndiaMART catalog listings and routes incoming leads
to sales reps instantly.

## Prerequisites
1. IndiaMART seller panel access, with **CRM Integration** enabled, to get
   a `glusr_crm_api_key` (task CH-01 — human-gated, depends on Chirantana).
2. Real product specs — this agent never invents details. Any spec left as
   `REPLACE_WITH...` in config is skipped in the generated listing, not
   guessed.
3. A real notification channel (WhatsApp Business API or an SMS provider
   like Twilio) if you want `route-leads` to actually deliver messages
   instead of just logging them.

## Setup
```bash
pip install -r requirements.txt
```

Edit `config.yaml`:
- `indiamart.crm_api_key` — from IndiaMART's CRM Integration settings
- `sales_reps` — real names + phone numbers for round-robin routing
- `products` — real specs per product; leave unknown fields as-is to skip them

## Usage

Rewrite catalog listings:
```bash
python coral_agent.py rewrite
```

Poll for new leads and route them (schedule this frequently, e.g. every
5-15 minutes, or trigger on IndiaMART's webhook if available):
```bash
python coral_agent.py route-leads
```

Mock mode (no credentials needed):
```bash
python coral_agent.py rewrite --mock
python coral_agent.py route-leads --mock
```

## How duplicate routing is prevented
Every lead's `UNIQUE_QUERY_ID` is recorded in `coral_state.json` (configurable
via `state_file`) once routed. Re-running `route-leads` only picks up leads
not already in that list — confirmed by test: running it twice in a row with
the same mock leads routed nothing the second time.

## What this does NOT do yet
- `notify_rep` is a placeholder — it prints what it *would* send. Wire in a
  real WhatsApp Business API or Twilio SMS call before relying on it to
  actually reach sales reps.
- `fetch_new_leads` uses IndiaMART's documented CRM Lead API shape, but has
  never been run against a real account — treat the first real run as a
  test of the request/response format, not a guarantee.
- The catalog rewrite is template-based (titles/descriptions assembled from
  real specs), not free-form AI copywriting. It's deliberately conservative:
  it would rather skip an unknown field than invent a plausible-sounding one.
