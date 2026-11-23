"""
Compass — fulfillment routing agent for GoSac (task S2-03).

What it does:
  Decides, per SKU, whether fulfillment should be FBA (Amazon stores/ships)
  or merchant dispatch (Chirantana's own warehouse ships), based on order
  velocity and weight:
    - light + fast-moving  -> FBA (worth the storage fee, fast delivery badge)
    - heavy or slow-moving  -> merchant dispatch (avoids storage fees on
                                stock that won't turn over fast)

Guardrail: a routing change is only flagged as an action to take once the
new classification has held for `thresholds.stable_runs_required`
consecutive runs. This prevents the agent from flip-flopping a SKU's
fulfillment method based on one noisy month of sales data.

Use --mock to run against fake velocity data, no real sales numbers needed.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

FBA = "FBA"
MERCHANT_DISPATCH = "MERCHANT_DISPATCH"


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state(state_path: Path) -> dict:
    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state_path: Path, state: dict) -> None:
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def classify_sku(sku_config: dict, thresholds: dict) -> str:
    velocity_ok = sku_config["monthly_order_velocity"] >= thresholds["fba_min_monthly_velocity"]
    weight_ok = sku_config["weight_kg"] <= thresholds["fba_max_weight_kg"]
    return FBA if (velocity_ok and weight_ok) else MERCHANT_DISPATCH


def run_classify(config_path: str, mock: bool) -> None:
    config = load_config(config_path)
    prefix = "Compass [MOCK]" if mock else "Compass"
    thresholds = config["thresholds"]
    state_path = Path(__file__).parent / config["state_file"]
    state = load_state(state_path)

    skus = config["skus"]
    if mock:
        import random
        skus = [dict(s, monthly_order_velocity=random.randint(0, 60)) for s in skus]

    required_streak = thresholds["stable_runs_required"]
    any_action_needed = False

    for sku_config in skus:
        sku = sku_config["sku"]
        new_classification = classify_sku(sku_config, thresholds)
        prev = state.get(sku, {"classification": new_classification, "streak": 0, "active": new_classification})

        if new_classification == prev["classification"]:
            streak = prev["streak"] + 1
        else:
            streak = 1  # classification flipped, restart the streak

        action_needed = streak >= required_streak and new_classification != prev["active"]
        if action_needed:
            any_action_needed = True
            print(f"{prefix}: {sku} -> ROUTE CHANGE to {new_classification} "
                  f"(stable for {streak} runs, velocity={sku_config['monthly_order_velocity']}, "
                  f"weight={sku_config['weight_kg']}kg)")
            active = new_classification
        else:
            active = prev["active"]
            print(f"{prefix}: {sku} -> {active} (currently active, no change needed; "
                  f"latest read: {new_classification}, streak={streak})")

        state[sku] = {"classification": new_classification, "streak": streak, "active": active}

    save_state(state_path, state)
    if not any_action_needed:
        print(f"{prefix}: no routing changes needed this run")


def main():
    parser = argparse.ArgumentParser(description="Compass — fulfillment routing agent")
    parser.add_argument("command", choices=["classify"])
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run against randomized fake velocity data instead of config.yaml's real numbers",
    )
    args = parser.parse_args()

    run_classify(args.config, args.mock)


if __name__ == "__main__":
    main()
