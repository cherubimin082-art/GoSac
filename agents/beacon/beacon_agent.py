"""
Beacon — reporting agent for GoSac (task: weekly performance dashboard).

What it does:
  `compile` — reads each sibling agent's own output/state file (read-only,
  never touches another agent's files) and produces one consolidated
  weekly report: a JSON file for programmatic use and a CSV file meant to
  be the data source a Looker Studio dashboard connects to.

IMPORTANT on Looker Studio: there's no API to push data directly into a
Looker Studio dashboard. The real integration is Looker Studio connecting
to a live source - Google Sheets, BigQuery, or a CSV in Drive. Beacon
produces the CSV; pointing Looker Studio's connector at it (or at a Sheet
you upload it to) is a one-time manual setup step. GA4 and Google Ads data
go into Looker Studio through their own native connectors directly -
Beacon does not duplicate that.

A source with no file yet is reported as "no data yet", never a fabricated
number - a missing agent output means that agent hasn't run, not zero
activity.

Use --mock to compile a report from built-in fake data instead of reading
real sibling agent files, useful to see the report shape before any other
agent has actually run.
"""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve(base_dir: Path, relative_path: str) -> Path:
    return (base_dir / relative_path).resolve()


def read_coral_summary(path: Path) -> dict:
    if not path.exists():
        return {"status": "no data yet", "leads_routed": None}
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    return {"status": "ok", "leads_routed": len(state.get("routed_lead_ids", []))}


def read_compass_summary(path: Path) -> dict:
    if not path.exists():
        return {"status": "no data yet", "skus_tracked": None, "skus_under_review": None}
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    under_review = sum(1 for s in state.values() if s["classification"] != s["active"])
    return {"status": "ok", "skus_tracked": len(state), "skus_under_review": under_review}


def read_pearl_summary(path: Path) -> dict:
    if not path.exists():
        return {"status": "no data yet", "listings_generated": None, "listings_complete": None}
    with open(path, "r", encoding="utf-8") as f:
        listings = json.load(f)
    complete = sum(1 for l in listings if l.get("skipped_bullets", 0) == 0)
    return {"status": "ok", "listings_generated": len(listings), "listings_complete": complete}


def read_horizon_summary(path: Path) -> dict:
    if not path.exists():
        return {"status": "no data yet", "catalog_rows": None}
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {"status": "ok", "catalog_rows": len(rows)}


def compile_report(config: dict, config_dir: Path) -> dict:
    sources = config["sources"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coral": read_coral_summary(_resolve(config_dir, sources["coral_state"])),
        "compass": read_compass_summary(_resolve(config_dir, sources["compass_state"])),
        "pearl": read_pearl_summary(_resolve(config_dir, sources["pearl_listings"])),
        "horizon": read_horizon_summary(_resolve(config_dir, sources["horizon_catalog"])),
    }


def compile_report_mock() -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coral": {"status": "ok", "leads_routed": 14},
        "compass": {"status": "ok", "skus_tracked": 5, "skus_under_review": 1},
        "pearl": {"status": "ok", "listings_generated": 2, "listings_complete": 1},
        "horizon": {"status": "ok", "catalog_rows": 3},
    }


def flatten_to_rows(report: dict) -> list[dict]:
    rows = [{"metric": "generated_at", "value": report["generated_at"]}]
    for agent, summary in report.items():
        if agent == "generated_at":
            continue
        for key, value in summary.items():
            rows.append({"metric": f"{agent}.{key}", "value": value if value is not None else "no data yet"})
    return rows


def run_compile(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    config_dir = Path(config_path).parent
    prefix = "Beacon [MOCK]" if mock else "Beacon"

    report = compile_report_mock() if mock else compile_report(config, config_dir)

    json_path = config_dir / config["report_json_path"]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    rows = flatten_to_rows(report)
    csv_path = config_dir / config["report_csv_path"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["metric", "value"])
        writer.writeheader()
        writer.writerows(rows)

    for agent, summary in report.items():
        if agent == "generated_at":
            continue
        if summary.get("status") == "no data yet":
            print(f"{prefix}: {agent} -> no data yet (agent hasn't produced output)")
        else:
            details = ", ".join(f"{k}={v}" for k, v in summary.items() if k != "status")
            print(f"{prefix}: {agent} -> {details}")

    print(f"{prefix}: wrote {json_path} and {csv_path}")
    print(f"{prefix}: point Looker Studio's Sheets/CSV connector at {csv_path.name} "
          f"(upload it to Sheets, or re-run this on a schedule and sync it there)")


def main():
    parser = argparse.ArgumentParser(description="Beacon — reporting agent")
    parser.add_argument("command", choices=["compile"])
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Compile from built-in fake data instead of reading real sibling agent files",
    )
    args = parser.parse_args()

    run_compile(args.config, args.mock)


if __name__ == "__main__":
    main()
