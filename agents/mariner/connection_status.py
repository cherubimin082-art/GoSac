"""
connection_status — checks which agents, for every registered client,
actually have real credentials configured, and writes a status file the
dashboard reads automatically.

This does NOT make a live API call to each platform (that would mean every
dashboard load pings Google/Meta/Amazon, which is slow and can trip rate
limits). Instead it checks the one thing that's actually verifiable from
disk: has a real credential been filled in, in place of the config's
REPLACE_WITH... placeholder, and does the referenced credentials file
(where one is required) actually exist.

So "connected" here means "this agent is configured with what looks like
real credentials" - not "we just successfully called the API." That's a
meaningfully weaker claim, and the dashboard should say so.

Output: connection_status.json, written to this directory and to web/
(so the locally-served dashboard can fetch it with a relative path).
Structure: {"generated_at": ..., "clients": {<client_id>: {<platform_key>: bool}}}
Platform keys match the dashboard's own scheme: "<agentId>::<platform name>".
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from client_registry import AGENTS_DIR, client_config_path, list_clients


def _is_filled(value) -> bool:
    return bool(value) and not str(value).startswith("REPLACE_WITH")


def _load(client_id: str, agent: str) -> dict:
    path = client_config_path(client_id, agent)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _file_exists_relative_to_config(client_id: str, agent: str, path_value: str) -> bool:
    if not _is_filled(path_value):
        return False
    p = Path(path_value)
    if not p.is_absolute():
        p = (client_config_path(client_id, agent).parent / p).resolve()
    return p.exists()


def check_sonar(client_id: str) -> dict:
    cfg = _load(client_id, "sonar")["ga4"]
    ok = _is_filled(cfg["property_id"]) and _file_exists_relative_to_config(client_id, "sonar", cfg["credentials_path"])
    return {"sonar::Google Analytics (GA4)": ok}


def check_current(client_id: str) -> dict:
    cfg = _load(client_id, "current")["google_ads"]
    ok = _is_filled(cfg["customer_id"]) and _file_exists_relative_to_config(client_id, "current", cfg["credentials_path"])
    return {"current::Google Ads": ok}


def check_coral(client_id: str) -> dict:
    cfg = _load(client_id, "coral")["indiamart"]
    ok = _is_filled(cfg["crm_api_key"])
    return {"coral::IndiaMART Seller Panel": ok}


def check_harbor(client_id: str) -> dict:
    cfg = _load(client_id, "harbor")
    amazon_ok = bool(cfg["amazon"]["seller_central_account_exists"])
    flipkart_ok = bool(cfg["flipkart"]["seller_hub_account_exists"])
    return {
        "harbor::Amazon Seller Central": amazon_ok,
        "harbor::Flipkart Seller Hub": flipkart_ok,
        # Compass routes FBA on the same Amazon account Harbor tracks.
        "compass::Amazon Seller Central (FBA)": amazon_ok,
    }


def check_horizon(client_id: str) -> dict:
    cfg = _load(client_id, "horizon")["business"]
    ok = bool(cfg["supplier_panel_account_exists"])
    return {"horizon::Meesho Supplier Panel": ok}


def check_undertow(client_id: str) -> dict:
    cfg = _load(client_id, "undertow")["meta"]
    ok = _is_filled(cfg["ad_account_id"]) and _file_exists_relative_to_config(client_id, "undertow", cfg["access_token_path"])
    return {"undertow::Meta Business Suite": ok}


def run_for_client(client_id: str) -> dict:
    status = {}
    for fn in (check_sonar, check_current, check_coral, check_harbor, check_horizon, check_undertow):
        status.update(fn(client_id))
    # Beacon's Looker Studio connector is set up manually inside Looker
    # Studio itself - nothing on disk here can confirm it, so it's left
    # out of the auto-detected status entirely (the dashboard falls back
    # to the manual toggle for any key not present in this file).
    return status


def run() -> dict:
    return {client["id"]: run_for_client(client["id"]) for client in list_clients()}


def main():
    clients_status = run()
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "clients": clients_status,
    }

    mariner_path = Path(__file__).parent / "connection_status.json"
    web_path = AGENTS_DIR.parent / "web" / "connection_status.json"

    for path in (mariner_path, web_path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)

    for client_id, status in clients_status.items():
        connected = sum(1 for v in status.values() if v)
        print(f"Mariner: [{client_id}] {connected}/{len(status)} platforms auto-detected as connected")
        for key, ok in status.items():
            print(f"Mariner:   [{'CONNECTED' if ok else 'not connected'}] {key}")
    print(f"Mariner: wrote {mariner_path} and {web_path}")


if __name__ == "__main__":
    main()
