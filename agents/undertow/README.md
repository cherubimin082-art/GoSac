# Undertow — Meta Retargeting Agent

Covers DN-04: builds custom audiences, launches the retargeting campaign,
and monitors spend + creative fatigue.

## Guardrails (always on)
- **Build** refuses to run if the creative fields (`video_asset_id`,
  `headline`) aren't filled in — confirmed by test: with placeholders still
  in config, it listed exactly which fields were missing and exited rather
  than launching a campaign with no real creative.
- **Monitor** never swaps or pauses creative automatically on fatigue. High
  frequency is *flagged*, not acted on — new creative needs the standard
  48-hour client sign-off (per the account's own rules), so a person
  decides, not the agent.
- **Monitor** never lets spend exceed `budget.monthly_ceiling_inr` without
  flagging it loudly.

## Prerequisites
1. A Meta Business app with Marketing API access, plus an access token
   (`meta.access_token_path` — a JSON file with `app_id`, `app_secret`,
   `access_token`).
2. Chirantana's Meta Ad Account ID.
3. A finished Raycraft video asset ID and headline — Undertow builds the
   campaign structure around creative, it doesn't create the creative.

## Setup
```bash
pip install -r requirements.txt
```

Edit `config.yaml`:
- `meta.ad_account_id`, `meta.access_token_path`
- `budget.monthly_ceiling_inr` — the agreed Meta ad spend ceiling (₹15k/mo
  per the Sprint 1 roster)
- `creative.video_asset_id`, `creative.headline` — real values, not
  placeholders
- `fatigue.frequency_threshold` — adjust if a different fatigue signal
  fits Chirantana's audience size better

## Usage

Build the campaign (run once, after creative is ready):
```bash
python undertow_agent.py build
```

Monitor weekly:
```bash
python undertow_agent.py monitor
```

Mock mode (no credentials needed):
```bash
python undertow_agent.py build --mock
python undertow_agent.py monitor --mock
```

## Confirmed by test
Ran `monitor --mock` six times in a row and saw every expected state:
fatigue-only flagged, spend-and-fatigue both flagged together, and two
genuinely healthy runs with no action needed — the exit code and message
matched the actual numbers each time.

## What this does NOT do yet
- `fetch_spend_and_frequency` (the real, non-mock path) is intentionally
  left unimplemented (raises `NotImplementedError`) rather than containing
  an untested guess at the Insights API call shape — fill this in against
  the real Marketing API once credentials exist, and test it before
  trusting its numbers.
- Does not create or edit the video creative itself — that's Raycraft's
  job; Undertow only references the finished asset ID.
