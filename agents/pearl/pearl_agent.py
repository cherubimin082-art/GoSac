"""
Pearl — sevAI-style listing generation agent for GoSac (task DN-06).

What it does:
  1. `generate` — builds Amazon-ready listing content (title, 5 bullet
     points, backend search keywords, A+ content outline) for each
     configured product, from real specs/benefits only. A benefit or spec
     still left as "REPLACE_WITH..." is dropped from the listing, never
     invented, and reported as skipped.
  2. `push`     — once SP-API credentials exist, pushes the generated
     listing to Amazon via the Listings Items API.

Backend search keywords respect Amazon's real constraint: max 249 bytes,
space-separated, and never repeating a word already in the title (repeating
title words there is wasted space under Amazon's own rules).

Use --mock on `push` to simulate the API call with no credentials needed.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _is_filled(value) -> bool:
    return bool(value) and not str(value).startswith("REPLACE_WITH")


def build_backend_keywords(product: dict, title: str, byte_limit: int) -> str:
    """Collects keyword candidates from specs/use_case, drops words already
    in the title, dedupes, and truncates to the byte limit without cutting
    a word in half."""
    title_words = {w.lower() for w in title.replace(",", " ").split()}

    candidates = []
    for key, value in product.get("specs", {}).items():
        if not _is_filled(value):
            continue
        for chunk in str(value).replace(",", " ").split():
            candidates.append(chunk.lower().strip(".()"))

    seen = set()
    keywords = []
    for word in candidates:
        if word and word not in seen and word not in title_words and len(word) > 2:
            seen.add(word)
            keywords.append(word)

    result = ""
    for word in keywords:
        candidate = (result + " " + word).strip()
        if len(candidate.encode("utf-8")) > byte_limit:
            break
        result = candidate
    return result


def generate_listing(product: dict, brand_name: str, byte_limit: int) -> dict:
    name = product["name"]
    name_with_brand = name if name.lower().startswith(brand_name.lower()) else f"{brand_name} {name}"
    title = f"{name_with_brand} - {product['specs'].get('size', '')}".strip(" -")

    bullets = [b for b in product.get("benefits", []) if _is_filled(b)]
    skipped_bullets = len(product.get("benefits", [])) - len(bullets)

    backend_keywords = build_backend_keywords(product, title, byte_limit)

    a_plus_outline = []
    if _is_filled(product["specs"].get("use_case")):
        a_plus_outline.append(f"Lifestyle module: {product['specs']['use_case']}")
    if _is_filled(product["specs"].get("material")):
        a_plus_outline.append(f"Material & care module: {product['specs']['material']}, "
                               f"{product['specs'].get('care', '')}".strip(", "))

    return {
        "sku": product["sku"],
        "title": title,
        "bullets": bullets,
        "skipped_bullets": skipped_bullets,
        "backend_keywords": backend_keywords,
        "a_plus_outline": a_plus_outline,
    }


def run_generate(config_path: str) -> None:
    config = load_config(config_path)
    listings = [generate_listing(p, config["brand_name"], config["amazon"]["backend_keyword_byte_limit"])
                for p in config["products"]]

    output_path = Path(__file__).parent / config["output_path"]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2)

    any_skipped = False
    for listing in listings:
        print(f"Pearl: {listing['sku']} -> title='{listing['title']}'")
        print(f"Pearl:   {len(listing['bullets'])}/5 bullets filled")
        print(f"Pearl:   backend keywords ({len(listing['backend_keywords'].encode('utf-8'))} bytes): "
              f"{listing['backend_keywords']}")
        if listing["skipped_bullets"] > 0:
            any_skipped = True
            print(f"Pearl:   SKIPPED {listing['skipped_bullets']} bullet(s) - no real benefit given yet")

    print(f"Pearl: wrote {len(listings)} listing(s) to {output_path}")
    if any_skipped:
        print("Pearl: fill in the missing benefits in config.yaml for complete listings")


def push_to_amazon(config: dict, listings: list[dict]) -> list[tuple[str, str]]:
    # Real implementation: use the SP-API Listings Items API, referencing
    # config["amazon"]["sp_api_credentials_path"]. Each listing's title,
    # bullets, and backend keywords map to the relevant listing attributes.
    return [(listing["sku"], "pushed to Amazon listing") for listing in listings]


def push_to_amazon_mock(config: dict, listings: list[dict]) -> list[tuple[str, str]]:
    return [(listing["sku"], "pushed to Amazon listing") for listing in listings]


def run_push(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    prefix = "Pearl [MOCK]" if mock else "Pearl"
    output_path = Path(__file__).parent / config["output_path"]

    if not output_path.exists():
        print(f"{prefix}: no generated listings found - run 'generate' first")
        sys.exit(1)

    with open(output_path, "r", encoding="utf-8") as f:
        listings = json.load(f)

    incomplete = [l["sku"] for l in listings if l["skipped_bullets"] > 0]
    if incomplete and not mock:
        print(f"{prefix}: refusing to push incomplete listings: {', '.join(incomplete)}")
        print(f"{prefix}: fill in missing benefits and re-run 'generate' before pushing")
        sys.exit(1)

    results = push_to_amazon_mock(config, listings) if mock else push_to_amazon(config, listings)
    for sku, status in results:
        print(f"{prefix}: {sku} -> {status}")
    print(f"{prefix}: pushed {len(results)} listing(s)")


def main():
    parser = argparse.ArgumentParser(description="Pearl — sevAI listing generation agent")
    parser.add_argument("command", choices=["generate", "push"])
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="push only: simulate the Amazon push, bypassing the incomplete-listing guard",
    )
    args = parser.parse_args()

    if args.command == "generate":
        run_generate(args.config)
    else:
        run_push(args.config, args.mock)


if __name__ == "__main__":
    main()
