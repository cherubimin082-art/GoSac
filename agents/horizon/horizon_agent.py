"""
Horizon — Meesho onboarding agent for GoSac (task S3-01).

SCOPE NOTE: Meesho supplier registration (supplier.meesho.com signup, phone
OTP, document verification) is a UI-only flow with no public API - Horizon
does not and cannot submit that application. What it actually automates:

  1. `check-readiness`   — verifies every onboarding prerequisite (GST, PAN,
                            bank proof, address proof, panel account) is
                            genuinely in hand before you register manually.
  2. `generate-catalog`  — builds the bulk catalog upload file in Meesho's
                            expected CSV format from real product data only,
                            skipping any field still left as a placeholder.

Use --mock to run generate-catalog against fake pricing, no real numbers
needed.
"""

import argparse
import csv
import sys
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _is_filled(value) -> bool:
    return bool(value) and not str(value).startswith("REPLACE_WITH")


def run_check_readiness(config_path: str) -> None:
    config = load_config(config_path)
    business = config["business"]

    checks = {
        "GST document on file": _is_filled(business["gst_doc_path"]),
        "PAN document on file": _is_filled(business["pan_doc_path"]),
        "bank account confirmed": business["bank_account_confirmed"],
        "bank proof on file": _is_filled(business["bank_proof_path"]),
        "business address proof on file": _is_filled(business["business_address_proof_path"]),
        "supplier panel account created": business["supplier_panel_account_exists"],
    }

    all_pass = True
    for label, passed in checks.items():
        status = "OK" if passed else "MISSING"
        if not passed:
            all_pass = False
        print(f"Horizon: [{status}] {label}")

    if not all_pass:
        print("Horizon: NOT READY - fill in the missing items above before registering on supplier.meesho.com")
        sys.exit(1)
    print("Horizon: all prerequisites in hand - safe to proceed with manual registration.")


def generate_catalog_rows(config: dict, mock: bool) -> tuple[list[dict], list[str]]:
    rows = []
    skipped_products = []
    for product in config["products"]:
        row = {
            "SKU": product["sku"],
            "Product Name": product["title"],
            "Category": product["category"],
            "Size": product["size"],
        }
        if mock:
            row["Price (INR)"] = "249"
            row["MRP (INR)"] = "349"
        else:
            price_filled = _is_filled(product["price_inr"])
            mrp_filled = _is_filled(product["mrp_inr"])
            if not (price_filled and mrp_filled):
                skipped_products.append(product["sku"])
                continue
            row["Price (INR)"] = product["price_inr"]
            row["MRP (INR)"] = product["mrp_inr"]
        rows.append(row)
    return rows, skipped_products


def run_generate_catalog(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    prefix = "Horizon [MOCK]" if mock else "Horizon"

    rows, skipped = generate_catalog_rows(config, mock)
    output_path = Path(__file__).parent / config["catalog_output_path"]

    if not rows:
        print(f"{prefix}: no products ready to catalog - every product is missing price/MRP")
        sys.exit(1)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["SKU", "Product Name", "Category", "Size", "Price (INR)", "MRP (INR)"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"{prefix}: wrote {len(rows)} row(s) to {output_path}")
    for sku in skipped:
        print(f"{prefix}: SKIPPED {sku} - missing price/MRP in config.yaml")
    if skipped:
        print(f"{prefix}: fill in price/MRP for the skipped SKUs and re-run to include them")


def main():
    parser = argparse.ArgumentParser(description="Horizon — Meesho onboarding agent")
    parser.add_argument("command", choices=["check-readiness", "generate-catalog"])
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="generate-catalog only: use fake pricing instead of config.yaml's real values",
    )
    args = parser.parse_args()

    if args.command == "check-readiness":
        run_check_readiness(args.config)
    else:
        run_generate_catalog(args.config, args.mock)


if __name__ == "__main__":
    main()
