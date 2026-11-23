# Horizon — Meesho Onboarding Agent

Covers S3-01.

## Scope note (important)
Meesho supplier registration (supplier.meesho.com signup, phone OTP,
document verification) is a **UI-only flow with no public API**. Horizon
does not and cannot submit that application. What it actually automates:

1. **`check-readiness`** — verifies every onboarding prerequisite (GST, PAN,
   bank proof, business address proof, panel account) is genuinely in hand
   before you register manually.
2. **`generate-catalog`** — builds the bulk catalog upload CSV in Meesho's
   expected format, from real product data only. Any product missing price
   or MRP is skipped, not guessed, and clearly flagged in the output.

## Setup
```bash
pip install -r requirements.txt
```

Edit `config.yaml` — fill in real document paths and flip booleans to `true`
only once each one is genuinely true. Fill in real `price_inr`/`mrp_inr`
per product once pricing is decided.

## Usage

Check what's still missing before registering manually:
```bash
python horizon_agent.py check-readiness
```

Generate the bulk catalog CSV for upload:
```bash
python horizon_agent.py generate-catalog
```

Mock mode (fake pricing, no real numbers needed):
```bash
python horizon_agent.py generate-catalog --mock
```

## Confirmed by test
- `check-readiness` with nothing filled in correctly flags all 6 items as
  missing and exits with an error.
- `generate-catalog` (real mode) with no pricing filled in correctly
  refuses to write an empty/placeholder catalog — it reports every SKU as
  skipped and exits with an error rather than writing fake numbers to the
  file you'd upload to Meesho.
- `generate-catalog --mock` writes a valid 3-row CSV with the correct
  headers Meesho's bulk upload expects.

## What this does NOT do
- Does not register the supplier account or submit any document to Meesho
  - that stays a manual step on supplier.meesho.com.
- Does not upload the generated CSV itself — Meesho's bulk upload is a
  manual file upload in the supplier panel, not an API call Horizon can
  trigger.
