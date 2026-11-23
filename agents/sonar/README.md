# Sonar — GA4 Tracking Agent

Covers DN-01: sets up GA4 conversion tracking for Chirantana & GoSac (RFQ form
submits, call clicks, WhatsApp clicks, spec downloads), then verifies the
events are actually firing.

## Prerequisites
1. A Google Cloud project with the Google Analytics Admin API and Google
   Analytics Data API enabled.
2. A service account in that project, with a downloaded JSON key.
3. The service account's email added as a user on the Chirantana GA4
   property (Editor role to create events, Viewer is enough for verify-only
   runs). This step is the human-gated part — it depends on Girish/Chirantana
   granting access (task CH-01).
4. The GA4 property ID (Admin > Property Settings in GA4).

## Setup
```bash
pip install -r requirements.txt
```

Edit `config.yaml`:
- `ga4.property_id` — the numeric GA4 property ID
- `ga4.credentials_path` — path to the service account JSON key
- `events_to_track` — add/remove events as needed

## Usage

Register the conversion events (run once):
```bash
python sonar_agent.py setup
```

Verify events are firing (run any time, or on a schedule):
```bash
python sonar_agent.py verify
```

Exit code is non-zero if anything failed to register or isn't firing yet —
safe to wire into a cron job or CI check that alerts on failure.

## What this does NOT do
- Does not touch ad spend, billing, or any other agent's data.
- Does not guess at GA4 access — if the service account lacks permission,
  the API call fails loudly instead of silently skipping.
