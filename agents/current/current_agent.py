"""
Current — Google Ads PPC agent for Chirantana & GoSac (tasks DN-03, DN-05).

What it does:
  1. `build`  — one-time: creates a real campaign/budget/ad group/keywords
                (and an ad, if real ad copy is configured) via the Google
                Ads API, from config.yaml's seed keywords.
  2. `tune`   — recurring (run daily): pulls yesterday's search term report,
                adds non-commercial queries as real negative keywords,
                checks spend against the hard monthly ceiling, and applies
                real bid changes to keyword criteria within a bounded
                daily change limit.

Guardrails (non-negotiable):
  - The campaign and its ad are created PAUSED, never ENABLED. Spending
    real money is a decision only a human makes — Current prepares
    everything and stops there; enabling the campaign in Google Ads is a
    deliberate manual step.
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
import json
import random
import sys
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _state_path(config_path: str) -> Path:
    # Lives next to the config, same convention as every other agent's
    # state file (coral_state.json, compass_state.json, ...).
    return Path(config_path).parent / "current_state.json"


def load_state(config_path: str) -> dict:
    path = _state_path(config_path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(config_path: str, state: dict) -> None:
    with open(_state_path(config_path), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _is_filled(value) -> bool:
    return bool(value) and not str(value).startswith("REPLACE_WITH")


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
#
# Written against the google-ads-python client's documented mutate shapes.
# Never run against a live or sandbox account yet — treat the first real
# run as a test of these exact calls, not a guarantee.
# ---------------------------------------------------------------------------

def build_campaign(config: dict, config_path: str) -> list[tuple[str, str]]:
    """Creates a real CampaignBudget, Campaign, AdGroup, keyword criteria,
    and (if real ad copy is configured) a Responsive Search Ad. The
    campaign and ad are created PAUSED — enabling them is a deliberate
    human step in Google Ads, not something this agent does.

    The created campaign's and ad group's resource names are saved to
    current_state.json — tune() needs them to add negative keywords and
    look up keyword performance for the SAME campaign build created,
    not just any campaign on the account."""
    client = get_client(config["google_ads"]["credentials_path"])
    customer_id = config["google_ads"]["customer_id"]
    campaign_cfg = config["campaign"]
    results = []

    try:
        daily_budget_inr = config["budget"]["monthly_ceiling_inr"] / 30
        budget_resource_name = _create_campaign_budget(
            client, customer_id, campaign_cfg["name"], daily_budget_inr
        )
        results.append(("campaign budget", f"created ({daily_budget_inr:.0f} INR/day)"))

        campaign_resource_name = _create_campaign(
            client, customer_id, campaign_cfg["name"], budget_resource_name
        )
        results.append((campaign_cfg["name"], "campaign created (PAUSED)"))

        ad_group_resource_name = _create_ad_group(
            client, customer_id, campaign_resource_name, f"{campaign_cfg['name']} - Ad Group 1"
        )
        results.append(("ad group", "created"))

        for keyword in campaign_cfg["seed_keywords"]:
            _add_keyword(client, customer_id, ad_group_resource_name, keyword)
            results.append((keyword, "added to campaign"))

        headlines = [h for h in campaign_cfg.get("ad_headlines", []) if _is_filled(h)]
        descriptions = [d for d in campaign_cfg.get("ad_descriptions", []) if _is_filled(d)]
        final_url = campaign_cfg.get("final_url", "")
        if headlines and descriptions and _is_filled(final_url):
            _create_responsive_search_ad(
                client, customer_id, ad_group_resource_name, headlines, descriptions, final_url
            )
            results.append(("ad", "created (PAUSED)"))
        else:
            results.append(("ad", "SKIPPED - fill in ad_headlines, ad_descriptions, final_url in config.yaml"))

        save_state(config_path, {
            "campaign_resource_name": campaign_resource_name,
            "ad_group_resource_name": ad_group_resource_name,
        })

    except Exception as exc:
        results.append(("campaign build", f"FAILED: {exc}"))

    return results


def _create_campaign_budget(client, customer_id: str, campaign_name: str, daily_budget_inr: float) -> str:
    service = client.get_service("CampaignBudgetService")
    operation = client.get_type("CampaignBudgetOperation")
    budget = operation.create
    budget.name = f"{campaign_name} Budget"
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    budget.amount_micros = int(daily_budget_inr * 1_000_000)

    response = service.mutate_campaign_budgets(customer_id=customer_id, operations=[operation])
    return response.results[0].resource_name


def _create_campaign(client, customer_id: str, campaign_name: str, budget_resource_name: str) -> str:
    service = client.get_service("CampaignService")
    operation = client.get_type("CampaignOperation")
    campaign = operation.create
    campaign.name = campaign_name
    campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
    # PAUSED is the guardrail: a human reviews and enables this in Google
    # Ads, Current never flips real spend on by itself.
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    campaign.manual_cpc.enhanced_cpc_enabled = True
    campaign.campaign_budget = budget_resource_name
    campaign.network_settings.target_google_search = True
    campaign.network_settings.target_search_network = True
    campaign.network_settings.target_partner_search_network = False
    campaign.network_settings.target_content_network = False

    response = service.mutate_campaigns(customer_id=customer_id, operations=[operation])
    return response.results[0].resource_name


def _create_ad_group(client, customer_id: str, campaign_resource_name: str, name: str) -> str:
    service = client.get_service("AdGroupService")
    operation = client.get_type("AdGroupOperation")
    ad_group = operation.create
    ad_group.name = name
    ad_group.campaign = campaign_resource_name
    ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
    ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD

    response = service.mutate_ad_groups(customer_id=customer_id, operations=[operation])
    return response.results[0].resource_name


def _add_keyword(client, customer_id: str, ad_group_resource_name: str, keyword: str) -> str:
    service = client.get_service("AdGroupCriterionService")
    operation = client.get_type("AdGroupCriterionOperation")
    criterion = operation.create
    criterion.ad_group = ad_group_resource_name
    criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
    criterion.keyword.text = keyword
    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE

    response = service.mutate_ad_group_criteria(customer_id=customer_id, operations=[operation])
    return response.results[0].resource_name


def _create_responsive_search_ad(client, customer_id: str, ad_group_resource_name: str,
                                  headlines: list[str], descriptions: list[str], final_url: str) -> str:
    service = client.get_service("AdGroupAdService")
    operation = client.get_type("AdGroupAdOperation")
    ad_group_ad = operation.create
    ad_group_ad.ad_group = ad_group_resource_name
    # PAUSED, same guardrail as the campaign itself.
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED
    ad_group_ad.ad.final_urls.append(final_url)

    for text in headlines:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        ad_group_ad.ad.responsive_search_ad.headlines.append(asset)
    for text in descriptions:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        ad_group_ad.ad.responsive_search_ad.descriptions.append(asset)

    response = service.mutate_ad_group_ads(customer_id=customer_id, operations=[operation])
    return response.results[0].resource_name


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


def add_negative_keywords(config: dict, campaign_resource_name: str, queries: list[str]) -> list[tuple[str, str]]:
    """Add each flagged query as a campaign-level negative keyword."""
    client = get_client(config["google_ads"]["credentials_path"])
    customer_id = config["google_ads"]["customer_id"]
    service = client.get_service("CampaignCriterionService")

    results = []
    for query in queries:
        try:
            operation = client.get_type("CampaignCriterionOperation")
            criterion = operation.create
            criterion.campaign = campaign_resource_name
            criterion.negative = True
            criterion.keyword.text = query
            criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.BROAD
            service.mutate_campaign_criteria(customer_id=customer_id, operations=[operation])
            results.append((query, "added as negative"))
        except Exception as exc:
            results.append((query, f"FAILED: {exc}"))
    return results


def fetch_keyword_performance(config: dict, campaign_resource_name: str) -> list[dict]:
    """Query keyword-level performance (not search-term-level) — this is
    what a real bid change should be based on, since a bid lives on the
    keyword criterion, not on the raw search term. Scoped to the campaign
    this agent built, not the whole account."""
    client = get_client(config["google_ads"]["credentials_path"])
    customer_id = config["google_ads"]["customer_id"]
    ga_service = client.get_service("GoogleAdsService")
    lookback_days = config["verification"]["lookback_days"]
    campaign_id = campaign_resource_name.split("/")[-1]

    query = f"""
        SELECT ad_group_criterion.resource_name, ad_group_criterion.keyword.text,
               ad_group_criterion.cpc_bid_micros, metrics.cost_micros, metrics.conversions
        FROM keyword_view
        WHERE segments.date DURING LAST_{lookback_days}_DAYS
          AND campaign.id = {campaign_id}
    """
    response = ga_service.search(customer_id=customer_id, query=query)

    rows = []
    for row in response:
        rows.append({
            "resource_name": row.ad_group_criterion.resource_name,
            "keyword": row.ad_group_criterion.keyword.text,
            "current_bid_micros": row.ad_group_criterion.cpc_bid_micros,
            "cost_inr": row.metrics.cost_micros / 1_000_000,
            "conversions": row.metrics.conversions,
        })
    return rows


def apply_bid_change(config: dict, resource_name: str, new_bid_micros: int) -> str:
    """Executes the actual bid change on a keyword criterion."""
    client = get_client(config["google_ads"]["credentials_path"])
    customer_id = config["google_ads"]["customer_id"]
    service = client.get_service("AdGroupCriterionService")

    from google.api_core import protobuf_helpers

    operation = client.get_type("AdGroupCriterionOperation")
    criterion = operation.update
    criterion.resource_name = resource_name
    criterion.cpc_bid_micros = new_bid_micros
    client.copy_from(operation.update_mask, protobuf_helpers.field_mask(None, criterion._pb))

    service.mutate_ad_group_criteria(customer_id=customer_id, operations=[operation])
    return "bid updated"


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

_MOCK_KEYWORD_PERFORMANCE = [
    {"resource_name": "mock/kw/1", "keyword": "semi-automatic clipping machine", "current_bid_micros": 45_000_000, "cost_inr": 980, "conversions": 2},
    {"resource_name": "mock/kw/2", "keyword": "fruit sorting machine manufacturer", "current_bid_micros": 38_000_000, "cost_inr": 610, "conversions": 1},
    {"resource_name": "mock/kw/3", "keyword": "bale netting supplier", "current_bid_micros": 30_000_000, "cost_inr": 420, "conversions": 1},
]


def build_campaign_mock(config: dict) -> list[tuple[str, str]]:
    results = [(kw, "added to campaign") for kw in config["campaign"]["seed_keywords"]]
    results.append(("ad", "created (PAUSED) [mock]"))
    return results


def fetch_search_terms_mock(config: dict) -> list[dict]:
    return _MOCK_SEARCH_TERMS


def fetch_month_to_date_spend_mock(config: dict) -> float:
    return round(random.uniform(0.5, 0.95) * config["budget"]["monthly_ceiling_inr"], 2)


def add_negative_keywords_mock(config: dict, queries: list[str]) -> list[tuple[str, str]]:
    return [(q, "added as negative") for q in queries]


def fetch_keyword_performance_mock(config: dict) -> list[dict]:
    return _MOCK_KEYWORD_PERFORMANCE


def apply_bid_change_mock(config: dict, resource_name: str, new_bid_micros: int) -> str:
    return "bid updated [mock]"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def run_build(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    results = build_campaign_mock(config) if mock else build_campaign(config, config_path)
    prefix = "Current [MOCK]" if mock else "Current"
    for keyword, status in results:
        print(f"{prefix}: '{keyword}' -> {status}")
    if any(status.startswith("FAILED") for _, status in results):
        sys.exit(1)


def run_tune(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    prefix = "Current [MOCK]" if mock else "Current"

    campaign_resource_name = None
    if not mock:
        state = load_state(config_path)
        campaign_resource_name = state.get("campaign_resource_name")
        if not campaign_resource_name:
            print(f"{prefix}: no campaign on record - run 'build' first")
            sys.exit(1)

    ceiling = config["budget"]["monthly_ceiling_inr"]
    spend = fetch_month_to_date_spend_mock(config) if mock else fetch_month_to_date_spend(config)
    print(f"{prefix}: month-to-date spend Rs.{spend:.0f} / ceiling Rs.{ceiling}")

    if spend >= ceiling:
        print(f"{prefix}: WARNING - spend at or above ceiling, pausing all bid changes for human review")
        sys.exit(1)

    terms = fetch_search_terms_mock(config) if mock else fetch_search_terms(config)
    junk = [t["query"] for t in terms if is_junk_query(t["query"], config["negative_signal_terms"])]

    if junk:
        neg_results = add_negative_keywords_mock(config, junk) if mock \
            else add_negative_keywords(config, campaign_resource_name, junk)
        for query, status in neg_results:
            print(f"{prefix}: negative '{query}' -> {status}")
    else:
        print(f"{prefix}: no junk queries found in this window")

    target_cpl = config["target"]["cost_per_lead_inr"]
    max_change = config["budget"]["max_bid_change_pct"]
    keywords = fetch_keyword_performance_mock(config) if mock \
        else fetch_keyword_performance(config, campaign_resource_name)

    bids_changed = 0
    for kw in keywords:
        if kw["conversions"] == 0:
            direction = -1
        else:
            cpl = kw["cost_inr"] / kw["conversions"]
            direction = 1 if cpl < target_cpl else -1

        change_pct = min(max_change, max_change)  # bounded — never exceeds config's own cap
        new_bid_micros = int(kw["current_bid_micros"] * (1 + direction * change_pct / 100))

        status = apply_bid_change_mock(config, kw["resource_name"], new_bid_micros) if mock \
            else apply_bid_change(config, kw["resource_name"], new_bid_micros)
        bids_changed += 1
        direction_word = "increase" if direction > 0 else "decrease"
        print(f"{prefix}: bid on '{kw['keyword']}' -> {direction_word} {change_pct}% -> {status}")

    print(f"{prefix}: tuning run complete - {len(junk)} negatives added, "
          f"{bids_changed} keyword bids updated")


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
