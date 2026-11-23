# Pearl — sevAI Listing Generation Agent

Covers DN-06: generates Amazon-ready listing content (title, 5 bullet
points, backend search keywords, A+ content outline) from real specs only.

## The conservative rule
Same as Coral and Horizon: every word traces back to a real spec or
benefit you gave it. A bullet or spec still left as `REPLACE_WITH...` in
config is dropped from the listing and reported as skipped - never
invented to fill the gap.

## Backend keywords follow Amazon's actual constraint
- Max 249 bytes (configurable via `amazon.backend_keyword_byte_limit`)
- Space-separated, never comma-separated
- Never repeats a word already in the title (Amazon treats that as wasted
  space, since title words are already indexed)
- Truncates on a word boundary, never mid-word

## Setup
```bash
pip install -r requirements.txt
```

Edit `config.yaml` — fill in real specs and at least 5 real benefits per
product. The `pack_count` and remaining `REPLACE_WITH_BENEFIT` placeholders
are there to be replaced, not left in.

## Usage

Generate listings:
```bash
python pearl_agent.py generate
```

Push to Amazon (refuses if any listing is incomplete):
```bash
python pearl_agent.py push
```

Mock mode (simulates the push, bypasses the incomplete-listing guard):
```bash
python pearl_agent.py push --mock
```

## Confirmed by test
- `generate` correctly built both SKU titles without the brand name
  duplicating (a bug caught and fixed during testing - the product name
  already included "GoSac", so it was appearing twice).
- With only 3 of 5 benefits filled in, it generated exactly 3 bullets and
  flagged 2 as skipped, instead of padding with invented ones.
- `push` (real mode) correctly **refused** to push either SKU because both
  had skipped bullets - it lists the incomplete SKUs and exits with an
  error rather than pushing a half-finished listing live.
- `push --mock` runs the full flow against fake data successfully.

## What this does NOT do
- `push_to_amazon` contains the real SP-API Listings Items call shape but
  has never run against a live account - treat the first real run as a
  test.
- Does not generate A+ content imagery or layout - only a text outline of
  what each A+ module should cover, based on filled specs.
