# Compass — Fulfillment Routing Agent

Covers S2-03: decides, per SKU, whether fulfillment should be FBA or
merchant dispatch.

## The rule
From the Chirantana/GoSac playbook:
- Fast-moving, light retail SKUs (1/3/5kg bag sets) -> **FBA** (worth the
  storage fee, gets the Prime fast-delivery badge)
- Bulk/custom/heavy SKUs (net rolls, shade nets, commercial packs) ->
  **merchant dispatch** (avoids high Amazon storage fees on stock that
  won't turn over fast)

Encoded as two thresholds in `config.yaml`:
- `fba_min_monthly_velocity` — below this, FBA's storage fee isn't worth it
- `fba_max_weight_kg` — above this, goes merchant dispatch regardless of velocity

## The guardrail — confirmed by test
A routing change is only flagged as an action to take once the new
classification has held for `stable_runs_required` consecutive runs
(default 2). This stops Compass from flip-flopping a SKU between FBA and
merchant dispatch because of one unusually busy or quiet month.

Verified directly:
- Run 1 (baseline): all SKUs classified, no changes flagged (nothing to
  compare against yet).
- Run 2: raised one SKU's velocity above the FBA threshold — correctly
  logged as "streak=1", **no change flagged yet**.
- Run 3: same velocity held — streak reached 2, **"ROUTE CHANGE to FBA"**
  correctly flagged.

## Setup
```bash
pip install -r requirements.txt
```

Edit `config.yaml`:
- `skus` — real SKU list with actual weight and monthly order velocity
  (replace the `0` placeholders with real sales data once you have it)
- `thresholds` — adjust if Chirantana's actual storage-fee economics differ

## Usage
```bash
python compass_agent.py classify
```

Run this monthly (or whenever you pull fresh sales data) — it's not a
daily job like Current's bid tuning.

Mock mode (random fake velocity data, no real sales numbers needed):
```bash
python compass_agent.py classify --mock
```

## State
`compass_state.json` tracks each SKU's current classification streak and
active routing. Delete it to reset the guardrail history (e.g. if you
intentionally want today's numbers to count as a fresh baseline).

## What this does NOT do
- Does not call any marketplace API to actually move inventory or change
  fulfillment settings — it only decides and reports what the routing
  *should* be. Amazon's actual FBA routing happens via inbound shipment
  creation in Seller Central (or SP-API's shipment APIs), which is a
  separate, heavier integration than this agent currently attempts.
- Does not pull real sales velocity itself - that data has to be fed in via
  config.yaml (or wired to a real sales data source later).
