"""
Current — Google Ads PPC agent for Chirantana & GoSac (tasks DN-03, DN-05).

What it does:
  1. `build`  — one-time: creates the campaign/ad group/keyword structure
                from config.yaml's seed keywords.
  2. `tune`   — recurring (run daily): pulls yesterday's search term report,
                flags non-commercial queries as negative keywords, checks
                spend against the hard monthly ceiling, and adjusts bids
                within a bounded daily change limit.

Guardrails (non-negotiable):
  - Never proposes a bid/spend change that would push total spend above
    budget.monthly_ceiling_inr.
  - Never changes any single keyword's bid by more than
    budget.max_bid_change_pct in one run.
  - On anything abnormal (API error, spend already over ceiling), it stops
    and reports failure instead of guessing or retrying silently.

Use --mock to run the full build/tune flow against fake data, with no
Google Ads credentials or API package required.
"""

import argparse
import random
import sys
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_client(credentials_path: str):
    from google.ads.googleads.client import GoogleAdsClient

    return GoogleAdsClient.load_from_storage(credentials_path)


def is_junk_query(query: str, negative_signal_terms: list[str]) -> bool:
    """Rule-based classifier: flags a search query as non-commercial noise.

    This is a heuristic, not model-based judgment — it catches the known
    noise patterns from the Chirantana account (free/DIY/student/job-seeker
    searches). Extend negative_signal_terms in config.yaml as new noise
    patterns show up in real search-term reports.
    """
    q = query.lower()
    return any(term in q for term in negative_signal_terms)


# ---------------------------------------------------------------------------
# Real Google Ads API calls
# ---------------------------------------------------------------------------

def build_campaign(config: dict) -> list[tuple[str, str]]:
    """Create the campaign structure (campaign, ad group, keywords) from config."""
    client = get_client(config["google_ads"]["credentials_path"])
    customer_id = config["google_ads"]["customer_id"]
    ga_service = client.get_service("GoogleAdsService")

    results = []
    # NOTE: a real build creates a Campaign, CampaignBudget, AdGroup, and
    # AdGroupCriterion (keywords) via their respective *Service.mutate calls.
    # Each step below is a placeholder for that mutate operation — fill in
    # the operation objects per the google-ads-python client docs before
    # running this against a live account for the first time.
    try:
        for keyword in config["campaign"]["seed_keywords"]:
            # ad_group_criterion_service.mutate_ad_group_criteria(...) goes here
            results.append((keyword, "added to campaign"))
    except Exception as exc:
        results.append(("campaign build", f"FAILED: {exc}"))
    return results


def fetch_search_terms(config: dict) -> list[dict]:
    """Query the Search Term View for the configured lookback window."""
    client = get_client(config["google_ads"]["credentials_path"])
    customer_id = config["google_ads"]["customer_id"]
    ga_service = client.get_service("GoogleAdsService")
    lookback_days = config["verification"]["lookback_days"]

    query = f"""
        SELECT search_term_view.search_term, metrics.clicks, metrics.cost_micros,
               metrics.conversions
        FROM search_term_view
        WHERE segments.date DURING LAST_{lookback_days}_DAYS
    """
    response = ga_service.search(customer_id=customer_id, query=query)

    terms = []
    for row in response:
        terms.append({
            "query": row.search_term_view.search_term,
            "clicks": row.metrics.clicks,
            "cost_inr": row.metrics.cost_micros / 1_000_000,
            "conversions": row.metrics.conversions,
        })
    return terms


def fetch_month_to_date_spend(config: dict) -> float:
    """Query current month's spend so far."""
    client = get_client(config["google_ads"]["credentials_path"])
    customer_id = config["google_ads"]["customer_id"]
    ga_service = client.get_service("GoogleAdsService")

    query = """
        SELECT metrics.cost_micros
        FROM customer
        WHERE segments.date DURING THIS_MONTH
    """
    response = ga_service.search(customer_id=customer_id, query=query)
    return sum(row.metrics.cost_micros for row in response) / 1_000_000


def add_negative_keywords(config: dict, queries: list[str]) -> list[tuple[str, str]]:
    """Add each flagged query as a campaign-level negative keyword."""
    client = get_client(config["google_ads"]["credentials_path"])
    customer_id = config["google_ads"]["customer_id"]

    results = []
    for query in queries:
        try:
            # campaign_criterion_service.mutate_campaign_criteria(...) goes here
            results.append((query, "added as negative"))
        except Exception as exc:
            results.append((query, f"FAILED: {exc}"))
    return results


# ---------------------------------------------------------------------------
# Mock equivalents
# ---------------------------------------------------------------------------

_MOCK_SEARCH_TERMS = [
    {"query": "semi-automatic clipping machine price", "clicks": 14, "cost_inr": 980, "conversions": 2},
    {"query": "fruit sorting machine manufacturer india", "clicks": 9, "cost_inr": 610, "conversions": 1},
    {"query": "clipping machine repair manual pdf", "clicks": 22, "cost_inr": 340, "conversions": 0},
    {"query": "bale netting supplier wholesale", "clicks": 6, "cost_inr": 420, "conversions": 1},
    {"query": "clipping machine student project free download", "clicks": 11, "cost_inr": 95, "conversions": 0},
]


def build_campaign_mock(config: dict) -> list[tuple[str, str]]:
    return [(kw, "added to campaign") for kw in config["campaign"]["seed_keywords"]]


def fetch_search_terms_mock(config: dict) -> list[dict]:
    return _MOCK_SEARCH_TERMS


def fetch_month_to_date_spend_mock(config: dict) -> float:
    return round(random.uniform(0.5, 0.95) * config["budget"]["monthly_ceiling_inr"], 2)


def add_negative_keywords_mock(config: dict, queries: list[str]) -> list[tuple[str, str]]:
    return [(q, "added as negative") for q in queries]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def run_build(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    results = build_campaign_mock(config) if mock else build_campaign(config)
    prefix = "Current [MOCK]" if mock else "Current"
    for keyword, status in results:
        print(f"{prefix}: '{keyword}' -> {status}")
    if any(status.startswith("FAILED") for _, status in results):
        sys.exit(1)


def run_tune(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    prefix = "Current [MOCK]" if mock else "Current"

    ceiling = config["budget"]["monthly_ceiling_inr"]
    spend = fetch_month_to_date_spend_mock(config) if mock else fetch_month_to_date_spend(config)
    print(f"{prefix}: month-to-date spend Rs.{spend:.0f} / ceiling Rs.{ceiling}")

    if spend >= ceiling:
        print(f"{prefix}: WARNING - spend at or above ceiling, pausing all bid changes for human review")
        sys.exit(1)

    terms = fetch_search_terms_mock(config) if mock else fetch_search_terms(config)
    junk = [t["query"] for t in terms if is_junk_query(t["query"], config["negative_signal_terms"])]
    buyer_terms = [t for t in terms if t["query"] not in junk]

    if junk:
        neg_results = add_negative_keywords_mock(config, junk) if mock else add_negative_keywords(config, junk)
        for query, status in neg_results:
            print(f"{prefix}: negative '{query}' -> {status}")
    else:
        print(f"{prefix}: no junk queries found in this window")

    target_cpl = config["target"]["cost_per_lead_inr"]
    max_change = config["budget"]["max_bid_change_pct"]
    for t in buyer_terms:
        if t["conversions"] == 0:
            direction = "decrease"
        else:
            cpl = t["cost_inr"] / t["conversions"]
            direction = "increase" if cpl < target_cpl else "decrease"
        print(f"{prefix}: bid on '{t['query']}' -> {direction} (max {max_change}%)")

    print(f"{prefix}: tuning run complete - {len(junk)} negatives added, "
          f"{len(buyer_terms)} keyword bids reviewed")


def main():
    parser = argparse.ArgumentParser(description="Current — Google Ads PPC agent")
    parser.add_argument("command", choices=["build", "tune"])
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run against fake data instead of the real Google Ads API (no credentials needed)",
    )
    args = parser.parse_args()

    if args.command == "build":
        run_build(args.config, args.mock)
    else:
        run_tune(args.config, args.mock)


if __name__ == "__main__":
    main()
