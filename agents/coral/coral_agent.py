"""
Coral — IndiaMART catalog & lead-routing agent for Chirantana & GoSac (task DN-02).

What it does:
  1. `rewrite`      — generates search-optimized titles/descriptions/keywords
                       for each configured product, from its real specs only
                       (never invents details it wasn't given).
  2. `route-leads`  — recurring: polls IndiaMART's CRM Lead API for new leads
                       since the last run, round-robin assigns each to a sales
                       rep, and sends a notification. Tracks already-routed
                       lead IDs in a local state file so a lead is never
                       routed twice.

Use --mock to run both commands against fake data, with no IndiaMART API key
or network access required.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state(state_path: Path) -> dict:
    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"routed_lead_ids": [], "next_rep_index": 0}


def save_state(state_path: Path, state: dict) -> None:
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Catalog rewrite
# ---------------------------------------------------------------------------

def generate_listing(product: dict) -> dict:
    """Builds a search-optimized title/description/keywords from real specs only.

    Template-based, not free-form generation: every field it writes traces
    back to something in product['specs']. Unfilled spec placeholders
    (still saying "REPLACE_WITH...") are skipped rather than guessed.
    """
    name = product["name"]
    category = product["category"]
    specs = {k: v for k, v in product.get("specs", {}).items() if not str(v).startswith("REPLACE_WITH")}

    title = name
    if "capacity" in specs:
        title += f" ({specs['capacity']})"

    description_lines = [f"{name} - {category}."]
    for key, value in specs.items():
        if key == "use_case":
            continue
        description_lines.append(f"{key.replace('_', ' ').title()}: {value}")
    if "use_case" in specs:
        description_lines.append(f"Use case: {specs['use_case']}")

    keywords = [category, name.lower()]
    if "use_case" in specs:
        keywords += [term.strip().lower() for term in specs["use_case"].split(",")]

    return {
        "title": title,
        "description": "\n".join(description_lines),
        "keywords": sorted(set(keywords)),
        "skipped_fields": [k for k, v in product.get("specs", {}).items() if str(v).startswith("REPLACE_WITH")],
    }


def run_rewrite(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    prefix = "Coral [MOCK]" if mock else "Coral"

    any_skipped = False
    for product in config["products"]:
        listing = generate_listing(product)
        print(f"{prefix}: '{product['name']}' -> title='{listing['title']}'")
        print(f"{prefix}:   keywords: {', '.join(listing['keywords'])}")
        if listing["skipped_fields"]:
            any_skipped = True
            print(f"{prefix}:   SKIPPED (no real value given): {', '.join(listing['skipped_fields'])}")
        # In a real run, the generated listing would be pushed to IndiaMART
        # here via its catalog update API.

    if any_skipped:
        print(f"{prefix}: some fields were skipped - fill in real specs in config.yaml for a complete listing")


# ---------------------------------------------------------------------------
# Lead routing
# ---------------------------------------------------------------------------

def fetch_new_leads(config: dict) -> list[dict]:
    import requests

    since = datetime.now(timezone.utc) - timedelta(minutes=config["indiamart"]["poll_lookback_minutes"])
    params = {
        "glusr_crm_api_key": config["indiamart"]["crm_api_key"],
        "start_time": since.strftime("%d-%b-%Y %H:%M:%S"),
        "end_time": datetime.now(timezone.utc).strftime("%d-%b-%Y %H:%M:%S"),
    }
    response = requests.get(config["indiamart"]["leads_endpoint"], params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get("RESPONSE", [])


def fetch_new_leads_mock(config: dict) -> list[dict]:
    return [
        {"UNIQUE_QUERY_ID": "mock-lead-1", "SENDER_NAME": "Ravi Kumar", "SENDER_MOBILE": "9800000001",
         "QUERY_PRODUCT_NAME": "Semi-Automatic Industrial Clipping Machine"},
        {"UNIQUE_QUERY_ID": "mock-lead-2", "SENDER_NAME": "Anita Sharma", "SENDER_MOBILE": "9800000002",
         "QUERY_PRODUCT_NAME": "Reusable Produce Mesh Bag Set"},
    ]


def notify_rep(rep: dict, lead: dict, mock: bool) -> str:
    """Sends the lead to a sales rep. Placeholder for a real WhatsApp/SMS
    integration (e.g. Twilio) — wire that in here once credentials exist."""
    message = (f"New IndiaMART lead: {lead.get('SENDER_NAME')} "
               f"({lead.get('SENDER_MOBILE')}) asked about {lead.get('QUERY_PRODUCT_NAME')}")
    if mock:
        return f"[MOCK notify to {rep['name']}] {message}"
    # real_sms_or_whatsapp_send(rep['phone'], message) goes here
    return f"[NOT SENT - no notification channel configured] {message}"


def run_route_leads(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    prefix = "Coral [MOCK]" if mock else "Coral"
    state_path = Path(__file__).parent / config["state_file"]
    state = load_state(state_path)

    leads = fetch_new_leads_mock(config) if mock else fetch_new_leads(config)
    new_leads = [lead for lead in leads if lead["UNIQUE_QUERY_ID"] not in state["routed_lead_ids"]]

    if not new_leads:
        print(f"{prefix}: no new leads since last run")
        return

    reps = config["sales_reps"]
    for lead in new_leads:
        rep = reps[state["next_rep_index"] % len(reps)]
        state["next_rep_index"] += 1
        result = notify_rep(rep, lead, mock)
        print(f"{prefix}: {result}")
        state["routed_lead_ids"].append(lead["UNIQUE_QUERY_ID"])

    save_state(state_path, state)
    print(f"{prefix}: routed {len(new_leads)} new lead(s)")


def main():
    parser = argparse.ArgumentParser(description="Coral — IndiaMART catalog & lead-routing agent")
    parser.add_argument("command", choices=["rewrite", "route-leads"])
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run against fake data instead of the real IndiaMART API (no credentials needed)",
    )
    args = parser.parse_args()

    if args.command == "rewrite":
        run_rewrite(args.config, args.mock)
    else:
        run_route_leads(args.config, args.mock)


if __name__ == "__main__":
    main()
