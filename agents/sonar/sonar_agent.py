"""
Sonar — GA4 tracking agent for Chirantana & GoSac (task DN-01).

What it does:
  1. Registers each configured event as a GA4 conversion (key) event.
  2. Verifies the events actually fired in the lookback window.
  3. Prints a one-line summary suitable for a daily/weekly log.

Run once after GA4 access is granted (service account added to the property),
then re-run `verify` on a schedule to confirm tracking stays healthy.

Use --mock to run the full setup/verify flow against fake data, with no
GA4 credentials or API packages required — useful to see the agent work
before real access exists.
"""

import argparse
import random
import sys
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_credentials(credentials_path: str):
    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_file(credentials_path)


def register_events(config: dict) -> list[tuple[str, str]]:
    """Create each configured event as a GA4 conversion event. Returns (name, status) pairs."""
    from google.analytics.admin_v1alpha import AnalyticsAdminServiceClient, ConversionEvent
    from google.api_core.exceptions import AlreadyExists

    creds = get_credentials(config["ga4"]["credentials_path"])
    client = AnalyticsAdminServiceClient(credentials=creds)
    property_path = f"properties/{config['ga4']['property_id']}"

    results = []
    for event in config["events_to_track"]:
        event_name = event["name"]
        try:
            client.create_conversion_event(
                parent=property_path,
                conversion_event=ConversionEvent(event_name=event_name),
            )
            results.append((event_name, "created"))
        except AlreadyExists:
            results.append((event_name, "already registered"))
        except Exception as exc:  # surface anything else as a visible failure, not a silent skip
            results.append((event_name, f"FAILED: {exc}"))
    return results


def verify_events_firing(config: dict) -> dict[str, int]:
    """Query the GA4 Data API for event counts over the configured lookback window."""
    from google.analytics.data_v1beta import (
        BetaAnalyticsDataClient,
        DateRange,
        Dimension,
        Metric,
        RunReportRequest,
    )

    creds = get_credentials(config["ga4"]["credentials_path"])
    client = BetaAnalyticsDataClient(credentials=creds)
    property_path = f"properties/{config['ga4']['property_id']}"
    lookback_days = config["verification"]["lookback_days"]

    tracked_names = {e["name"] for e in config["events_to_track"]}

    request = RunReportRequest(
        property=property_path,
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount")],
        date_ranges=[DateRange(start_date=f"{lookback_days}daysAgo", end_date="today")],
    )
    response = client.run_report(request)

    counts = {name: 0 for name in tracked_names}
    for row in response.rows:
        name = row.dimension_values[0].value
        if name in tracked_names:
            counts[name] = int(row.metric_values[0].value)
    return counts


def register_events_mock(config: dict) -> list[tuple[str, str]]:
    """Same shape as register_events, but fakes the GA4 Admin API call."""
    results = []
    for event in config["events_to_track"]:
        # first run "creates" each event; pretend one was already registered,
        # to show both code paths a real run can hit
        status = "already registered" if event["name"] == "spec_download" else "created"
        results.append((event["name"], status))
    return results


def verify_events_firing_mock(config: dict) -> dict[str, int]:
    """Same shape as verify_events_firing, but fakes GA4 Data API event counts."""
    counts = {}
    for event in config["events_to_track"]:
        # fake one event as not-yet-firing, to show the "not fully verified" path too
        counts[event["name"]] = 0 if event["name"] == "spec_download" else random.randint(3, 60)
    return counts


def run_setup(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    results = register_events_mock(config) if mock else register_events(config)
    prefix = "Sonar [MOCK]" if mock else "Sonar"
    for name, status in results:
        print(f"{prefix}: {name} -> {status}")
    failures = [r for r in results if r[1].startswith("FAILED")]
    if failures:
        sys.exit(1)


def run_verify(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    counts = verify_events_firing_mock(config) if mock else verify_events_firing(config)
    verified = sum(1 for c in counts.values() if c > 0)
    total = len(counts)
    detail = ", ".join(f"{name}={count}" for name, count in counts.items())
    prefix = "Sonar [MOCK]" if mock else "Sonar"
    print(f"{prefix}: {verified}/{total} events verified firing ({detail})")
    if verified < total:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Sonar — GA4 tracking agent")
    parser.add_argument("command", choices=["setup", "verify"])
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run against fake data instead of real GA4 APIs (no credentials needed)",
    )
    args = parser.parse_args()

    if args.command == "setup":
        run_setup(args.config, args.mock)
    else:
        run_verify(args.config, args.mock)


if __name__ == "__main__":
    main()
