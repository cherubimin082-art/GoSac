# Current — Google Ads PPC Agent

Covers DN-03 (campaign build) and DN-05 (daily bid tuning) for Chirantana's
B2B Google Search Ads.

## Guardrails (always on, not configurable away)
- Never lets total spend exceed `budget.monthly_ceiling_inr` — if spend is
  already at or over the ceiling, it stops and reports instead of touching
  any bid.
- Never changes a single keyword's bid by more than
  `budget.max_bid_change_pct` in one run.
- Fails loudly on any API error instead of retrying silently.

## Prerequisites
1. A Google Ads **Manager (MCC) account** linked to Chirantana's Ads account
   (task CH-01 — this is the human-gated step).
2. A Google Ads API **developer token**, approved for the manager account.
3. OAuth2 credentials (Client ID + Secret) from Google Cloud Console, plus a
   refresh token for the account with access.
4. A `google-ads.yaml` file with those credentials (see the
   [google-ads-python docs](https://developers.google.com/google-ads/api/docs/client-libs/python/configuration)
   for the exact format).
5. Chirantana's Google Ads **Customer ID** (10 digits, no dashes).

## Setup
```bash
pip install -r requirements.txt
```

Edit `config.yaml`:
- `google_ads.customer_id` — the real customer ID
- `google_ads.credentials_path` — path to your `google-ads.yaml`
- `budget.monthly_ceiling_inr` — the agreed ad spend ceiling
- `campaign.seed_keywords` — starting keyword list
- `negative_signal_terms` — extend as real search-term reports reveal noise

## Usage

Build the campaign structure (run once):
```bash
python current_agent.py build
```

Run the daily tuning pass (schedule this, e.g. via cron, once a day):
```bash
python current_agent.py tune
```

Mock mode — no credentials needed, runs against fake data:
```bash
python current_agent.py build --mock
python current_agent.py tune --mock
```

## What `tune` actually does each run
1. Checks month-to-date spend against the ceiling — stops here if already over.
2. Pulls yesterday's search term report.
3. Flags queries matching `negative_signal_terms` (a rule-based check, not
   model judgment) and adds them as negative keywords.
4. For the remaining buyer-intent queries, flags whether each keyword's bid
   should move up or down based on cost-per-lead vs. `target.cost_per_lead_inr`
   — bounded by `max_bid_change_pct`.

## What this does NOT do yet
- `build_campaign`, `fetch_search_terms`, `fetch_month_to_date_spend`, and
  `add_negative_keywords` contain the real Google Ads API call shapes but
  have **never been run against a live account**. The exact mutate
  operations (creating AdGroupCriterion objects, etc.) need to be filled in
  and tested against a real or sandbox account before the first live run —
  treat that first run as a test, not a guarantee.
- Does not actually execute bid *changes* via the API yet — right now `tune`
  reports what it would do (increase/decrease) rather than mutating bids.
  Wiring that up is the next step once the reporting side is verified against
  real data.
