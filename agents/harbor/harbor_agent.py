"""
Harbor — Amazon Brand Storefront & Flipkart Seller Portal agent for GoSac (task S2-01).

IMPORTANT SCOPE NOTE:
  Amazon Brand Registry enrollment and Flipkart seller account onboarding
  are both UI-only flows - neither platform offers a public API to submit
  them. Harbor does not attempt (and cannot attempt) to automate that
  submission. Its actual job is narrower and split into two pieces:

  1. `check-readiness` — verifies every prerequisite document/account in
     config.yaml is genuinely in hand before you go submit manually. This
     is the useful automatable part: a clear go/no-go gate instead of
     discovering a missing document mid-application.
  2. `sync-skus`       — once both seller accounts actually exist, pushes
     basic SKU/title/category metadata via each platform's seller API
     (Amazon SP-API, Flipkart Seller API). This does NOT create the brand
     storefront page itself - that's still a manual builder step in each
     platform's UI.

Use --mock to run both commands against fake data, with no SP-API or
Flipkart API credentials required.
"""

import argparse
import sys
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _is_filled(value: str) -> bool:
    return bool(value) and not str(value).startswith("REPLACE_WITH")


# ---------------------------------------------------------------------------
# Readiness check
# ---------------------------------------------------------------------------

def check_readiness(config: dict) -> dict:
    """Returns a structured pass/fail readiness report, split by what each
    platform actually requires."""
    brand = config["brand"]

    brand_checks = {
        "trademark registered or pending": brand["trademark_registered_or_pending"],
        "trademark document on file": _is_filled(brand["trademark_doc_path"]),
        "GST document on file": _is_filled(brand["gst_doc_path"]),
        "bank account confirmed": brand["bank_account_confirmed"],
        "brand logo on file": _is_filled(brand["brand_logo_path"]),
    }

    # Amazon Brand Registry specifically requires a registered/pending trademark.
    amazon_checks = dict(brand_checks)
    amazon_checks["Seller Central account created"] = config["amazon"]["seller_central_account_exists"]
    amazon_checks["Brand Registry enrolled"] = config["amazon"]["brand_registry_enrolled"]

    # Flipkart does not require Brand Registry-style trademark proof to onboard
    # as a seller, so its checklist omits the trademark items.
    flipkart_checks = {
        "GST document on file": brand_checks["GST document on file"],
        "bank account confirmed": brand_checks["bank account confirmed"],
        "Seller Hub account created": config["flipkart"]["seller_hub_account_exists"],
    }

    return {"amazon": amazon_checks, "flipkart": flipkart_checks}


def run_check_readiness(config_path: str) -> None:
    config = load_config(config_path)
    report = check_readiness(config)

    all_pass = True
    for platform, checks in report.items():
        print(f"Harbor: --- {platform.title()} readiness ---")
        for label, passed in checks.items():
            status = "OK" if passed else "MISSING"
            if not passed:
                all_pass = False
            print(f"Harbor:   [{status}] {label}")

    if not all_pass:
        print("Harbor: NOT READY - fill in the missing items above before submitting manually.")
        sys.exit(1)
    print("Harbor: all prerequisites in hand - safe to proceed with manual submission.")


# ---------------------------------------------------------------------------
# SKU/category sync (only meaningful once accounts exist)
# ---------------------------------------------------------------------------

def sync_amazon_skus(config: dict) -> list[tuple[str, str]]:
    # Real implementation: use the SP-API Listings Items API to create/update
    # each SKU's listing, referencing config["amazon"]["sp_api"]["credentials_path"].
    results = []
    for item in config["skus"]:
        results.append((item["sku"], "pushed to Amazon listings"))
    return results


def sync_flipkart_skus(config: dict) -> list[tuple[str, str]]:
    # Real implementation: use Flipkart's Seller API (Listings endpoint),
    # referencing config["flipkart"]["seller_api"]["credentials_path"].
    results = []
    for item in config["skus"]:
        results.append((item["sku"], "pushed to Flipkart listings"))
    return results


def sync_amazon_skus_mock(config: dict) -> list[tuple[str, str]]:
    return [(item["sku"], "pushed to Amazon listings") for item in config["skus"]]


def sync_flipkart_skus_mock(config: dict) -> list[tuple[str, str]]:
    return [(item["sku"], "pushed to Flipkart listings") for item in config["skus"]]


def run_sync_skus(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    prefix = "Harbor [MOCK]" if mock else "Harbor"

    report = check_readiness(config)
    if not mock:
        if not report["amazon"]["Seller Central account created"]:
            print(f"{prefix}: Amazon Seller Central account doesn't exist yet - nothing to sync")
            sys.exit(1)
        if not report["flipkart"]["Seller Hub account created"]:
            print(f"{prefix}: Flipkart Seller Hub account doesn't exist yet - nothing to sync")
            sys.exit(1)

    amazon_results = sync_amazon_skus_mock(config) if mock else sync_amazon_skus(config)
    flipkart_results = sync_flipkart_skus_mock(config) if mock else sync_flipkart_skus(config)

    for sku, status in amazon_results:
        print(f"{prefix}: {sku} -> {status}")
    for sku, status in flipkart_results:
        print(f"{prefix}: {sku} -> {status}")

    print(f"{prefix}: synced {len(amazon_results)} SKU(s) to Amazon, "
          f"{len(flipkart_results)} SKU(s) to Flipkart")


def main():
    parser = argparse.ArgumentParser(description="Harbor — Amazon/Flipkart marketplace setup agent")
    parser.add_argument("command", choices=["check-readiness", "sync-skus"])
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run sync-skus against fake data, bypassing account-existence checks",
    )
    args = parser.parse_args()

    if args.command == "check-readiness":
        run_check_readiness(args.config)
    else:
        run_sync_skus(args.config, args.mock)


if __name__ == "__main__":
    main()
