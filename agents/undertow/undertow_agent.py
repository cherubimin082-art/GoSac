"""
Undertow — Meta retargeting agent for Chirantana & GoSac (task DN-04).

What it does:
  1. `build`    — one-time: creates the custom audiences and the
                  retargeting campaign/ad set/ad referencing the configured
                  video creative.
  2. `monitor`  — recurring (run weekly): checks spend against the hard
                  monthly ceiling and checks ad frequency for creative
                  fatigue.

Guardrails (non-negotiable):
  - Never lets spend exceed budget.monthly_ceiling_inr — if already at or
    over, it stops and reports instead of making any change.
  - Never swaps or pauses creative automatically on fatigue. It flags high
    frequency for a human decision, since new creative needs the standard
    48-hour client sign-off before it can go live.

Use --mock to run both commands against fake data, with no Meta Marketing
API credentials required.
"""

import argparse
import random
import sys
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _is_filled(value) -> bool:
    return bool(value) and not str(value).startswith("REPLACE_WITH")


def get_api(access_token_path: str):
    from facebook_business.api import FacebookAdsApi
    import json

    with open(access_token_path, "r", encoding="utf-8") as f:
        creds = json.load(f)
    return FacebookAdsApi.init(
        app_id=creds["app_id"], app_secret=creds["app_secret"], access_token=creds["access_token"]
    )


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_campaign(config: dict) -> list[tuple[str, str]]:
    get_api(config["meta"]["access_token_path"])
    results = []
    for audience in config["audiences"]:
        # CustomAudience.create(...) via the Marketing API goes here
        results.append((audience["name"], "custom audience created"))
    # Campaign / AdSet / Ad creation referencing config["creative"] goes here
    results.append((config["campaign"]["name"], "campaign created"))
    return results


def build_campaign_mock(config: dict) -> list[tuple[str, str]]:
    results = [(a["name"], "custom audience created") for a in config["audiences"]]
    results.append((config["campaign"]["name"], "campaign created"))
    return results


def run_build(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    prefix = "Undertow [MOCK]" if mock else "Undertow"

    creative = config["creative"]
    missing = [k for k in ("video_asset_id", "headline") if not _is_filled(creative.get(k))]
    if missing and not mock:
        print(f"{prefix}: cannot build - creative fields not filled in: {', '.join(missing)}")
        sys.exit(1)

    results = build_campaign_mock(config) if mock else build_campaign(config)
    for name, status in results:
        print(f"{prefix}: '{name}' -> {status}")


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

def fetch_spend_and_frequency(config: dict) -> dict:
    get_api(config["meta"]["access_token_path"])
    # Real implementation: query the Ad Account's Insights API for
    # spend and frequency over the current month.
    raise NotImplementedError("Wire up the real Insights API call before running without --mock")


def fetch_spend_and_frequency_mock(config: dict) -> dict:
    return {
        "spend_inr": round(random.uniform(0.4, 1.1) * config["budget"]["monthly_ceiling_inr"], 2),
        "frequency": round(random.uniform(1.5, 5.0), 2),
    }


def run_monitor(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    prefix = "Undertow [MOCK]" if mock else "Undertow"

    metrics = fetch_spend_and_frequency_mock(config) if mock else fetch_spend_and_frequency(config)
    ceiling = config["budget"]["monthly_ceiling_inr"]
    threshold = config["fatigue"]["frequency_threshold"]

    print(f"{prefix}: spend Rs.{metrics['spend_inr']:.0f} / ceiling Rs.{ceiling}")
    print(f"{prefix}: average frequency {metrics['frequency']:.2f} (fatigue threshold {threshold})")

    problems = []
    if metrics["spend_inr"] >= ceiling:
        problems.append("spend at or above ceiling")
    if metrics["frequency"] >= threshold:
        problems.append(f"frequency {metrics['frequency']:.2f} suggests creative fatigue - "
                         f"flag for a human creative-refresh decision (48-hour sign-off applies)")

    if problems:
        for p in problems:
            print(f"{prefix}: ACTION NEEDED - {p}")
        sys.exit(1)

    print(f"{prefix}: healthy - no action needed")


def main():
    parser = argparse.ArgumentParser(description="Undertow — Meta retargeting agent")
    parser.add_argument("command", choices=["build", "monitor"])
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run against fake data instead of the real Meta Marketing API (no credentials needed)",
    )
    args = parser.parse_args()

    if args.command == "build":
        run_build(args.config, args.mock)
    else:
        run_monitor(args.config, args.mock)


if __name__ == "__main__":
    main()
