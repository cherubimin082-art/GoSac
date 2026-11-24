# Current — Google Ads PPC Agent

Covers DN-03 (campaign build) and DN-05 (daily bid tuning) for Chirantana's
B2B Google Search Ads.

## Guardrails (always on, not configurable away)
- **The campaign and its ad are created PAUSED, never ENABLED.** Current
  builds the whole campaign structure for real, but spending real money is
  a decision only a human makes — enabling it in Google Ads is a
  deliberate manual step, not something this agent does automatically.
- Never lets total spend exceed `budget.monthly_ceiling_inr` — if spend is
  already at or over the ceiling, it stops and reports instead of touching
  any bid.
- Never changes a single keyword's bid by more than
  `budget.max_bid_change_pct` in one run.
- `tune` refuses to run for real until `build` has run first and recorded
  a campaign in `current_state.json` — it won't guess which campaign to
  tune.
- Fails loudly on any API error instead of retrying silently.

## Prerequisites
1. A Google Ads **Manager (MCC) account** linked to Chirantana's Ads account
   (task CH-01 — this is the human-gated step).
2. A Google Ads API **developer token**, approved for the manager account.
3. OAuth2 credentials (Client ID + Secret) from Google Cloud Console, plus a
   refresh token for the account with access.
4. A `google-ads.yaml` file with those credentials, **including
   `use_proto_plus: True`** (this build's code uses proto-plus style field
   access throughout — `client.get_type(...)`'s objects, `criterion.keyword.text = ...`
   — and the client refuses to load without that key set). See the
   [google-ads-python docs](https://developers.google.com/google-ads/api/docs/client-libs/python/configuration)
   for the full format.
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
- `campaign.ad_headlines` / `ad_descriptions` / `final_url` — real ad copy;
  leave unfilled to skip ad creation (campaign/keywords still get built)
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

## What `build` actually creates
A real `CampaignBudget`, a `Campaign` (PAUSED, Search channel, enhanced
manual CPC), an `AdGroup`, a phrase-match `AdGroupCriterion` per seed
keyword, and — only if `ad_headlines`/`ad_descriptions`/`final_url` are
all filled in with real values — a Responsive Search Ad (also PAUSED).
The campaign's and ad group's resource names are saved to
`current_state.json` so `tune` knows which campaign to act on.

## What `tune` actually does each run
1. Checks month-to-date spend against the ceiling — stops here if already over.
2. Pulls yesterday's search term report.
3. Flags queries matching `negative_signal_terms` (a rule-based check, not
   model judgment) and adds them as **real campaign-level negative
   keywords** via the API.
4. Pulls real keyword-level performance (not search-term-level — a bid
   lives on the keyword criterion, so that's what tuning should look at)
   for the campaign `build` created, and **actually updates each
   keyword's CPC bid** based on cost-per-lead vs.
   `target.cost_per_lead_inr`, bounded by `max_bid_change_pct`.

## Confirmed by test (as far as possible without a live/sandbox account)
- Mock mode: `build --mock` and `tune --mock` both still run end to end
  with no regressions — `tune` now logs an actual "bid updated" result
  per keyword instead of just printing what it would do.
- Real mode, no prior build: `tune` correctly refuses immediately
  ("no campaign on record - run 'build' first") without attempting any
  API call.
- Real mode, no credentials filled in: `build` runs cleanly through the
  entire function (imports, client construction, campaign/budget/ad
  group/keyword/ad logic all execute with no Python errors) and fails
  exactly where expected — on the placeholder `google-ads.yaml` path —
  proving the code structure itself is sound.
- Validated every specific type and enum name used
  (`CampaignOperation`, `AdGroupAdOperation`, `BudgetDeliveryMethodEnum.STANDARD`,
  `KeywordMatchTypeEnum.PHRASE`, etc.) against the actually-installed
  `google-ads==25.1.0` client library, including the exact field
  assignments `build_campaign` and `apply_bid_change` use — all resolved
  correctly. Fixed one real bug found this way: the original
  `apply_bid_change` field-mask construction was wrong and would have
  raised at runtime; now uses `protobuf_helpers.field_mask` correctly.

## What's still unverified
- **The client eagerly authenticates over the network on
  `load_from_storage`** — so the actual mutate calls (creating a real
  campaign, updating a real bid) have never been exercised, even with
  fake credentials; that needs a real OAuth refresh token Google
  recognizes. Treat the first real `build` run as a genuine test, not a
  guarantee — field names can shift slightly between API versions, and
  only a live call proves the whole chain works.
