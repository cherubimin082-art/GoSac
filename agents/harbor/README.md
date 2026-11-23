# Harbor — Amazon Brand Storefront & Flipkart Seller Portal Agent

Covers S2-01. Read this scope note before expecting more from it than it does.

## Scope note (important)
**Amazon Brand Registry enrollment and Flipkart seller account onboarding
are both UI-only flows.** Neither platform exposes a public API to submit
a Brand Registry application or create a seller account - that part stays
manual, in each platform's own portal, no matter what automation exists.

What Harbor actually automates:
1. **`check-readiness`** — verifies every prerequisite (trademark status,
   GST doc, bank account, logo, account existence) is genuinely in hand
   *before* you go submit manually. Confirmed by test: with nothing filled
   in, it correctly flags every missing item for both Amazon and Flipkart
   and exits with an error.
2. **`sync-skus`** — once both seller accounts actually exist, pushes basic
   SKU/title/category metadata via each platform's seller API (Amazon
   SP-API, Flipkart Seller API). This does **not** build the storefront
   page itself - that's still a manual step in each platform's brand
   storefront / store builder UI.

## Prerequisites
- Real trademark registration/application for "GoSac" (or confirmation
  it's not yet filed - this blocks Amazon Brand Registry specifically,
  not Flipkart)
- GST certificate
- Bank account confirmed for marketplace settlement
- Brand logo + any brand story content for the storefront
- Amazon SP-API credentials (once Seller Central account exists)
- Flipkart Seller API credentials (once Seller Hub account exists)

## Setup
```bash
pip install -r requirements.txt
```

Edit `config.yaml` — **only flip a boolean to `true` or fill in a path once
that document/account genuinely exists.** This file is a readiness record,
not a wishlist; setting something true before it's real defeats the whole
point of the gate.

## Usage

Check what's still missing before submitting anything manually:
```bash
python harbor_agent.py check-readiness
```

Sync SKU metadata once both accounts exist for real:
```bash
python harbor_agent.py sync-skus
```

Mock mode (bypasses the account-existence guard, runs against fake data):
```bash
python harbor_agent.py sync-skus --mock
```

## Guardrail confirmed by test
Running `sync-skus` (non-mock) with `seller_central_account_exists: false`
in config correctly refuses immediately ("Amazon Seller Central account
doesn't exist yet - nothing to sync") instead of attempting any API call.

## What this does NOT do
- Does not submit the Brand Registry application or create seller accounts
  - those are manual, UI-only steps on both platforms.
- Does not build the storefront page/banners - that's the platform's own
  store builder, done by a human once Brand Registry is approved.
- `sync_amazon_skus` and `sync_flipkart_skus` contain placeholder real-API
  call shapes that have never been run against a live account - treat the
  first real run as a test.
