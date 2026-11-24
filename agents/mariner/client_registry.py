"""
client_registry — shared logic for the multi-client platform.

A "client" is a business the fleet runs for. Each client gets their own
config.yaml per agent (same schema, same placeholders, just a separate
file) so the same agent code serves every client without copying code.

The original GoSac/Chirantana setup is special-cased as client id
"gosac": it keeps using each agent's existing agents/<agent>/config.yaml
directly, exactly as already built and tested - adding this system
doesn't move or touch anything that already works.

A new client's configs live at clients/<client_id>/<agent>/config.yaml,
scaffolded by copying each agent's current config.yaml as a starting
template (so a new client starts with the same REPLACE_WITH... placeholders
Sonar/Current/etc. already ship with).
"""

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
CLIENTS_DIR = REPO_ROOT / "clients"
REGISTRY_PATH = CLIENTS_DIR / "registry.json"

# Agents that take a per-client config.yaml. Beacon aggregates across
# everything and Mariner coordinates - neither is "per client" in the
# same sense, so both are left out for now.
CONFIGURABLE_AGENTS = [
    "sonar", "current", "coral", "harbor", "compass", "horizon", "pearl", "undertow",
]


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"clients": []}
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(data: dict) -> None:
    CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def list_clients() -> list[dict]:
    return load_registry()["clients"]


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "client"


def client_config_path(client_id: str, agent: str) -> Path:
    """Where this client's config.yaml for this agent lives."""
    if client_id == "gosac":
        return AGENTS_DIR / agent / "config.yaml"
    return CLIENTS_DIR / client_id / agent / "config.yaml"


def add_client(name: str) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("Client name can't be empty")

    registry = load_registry()
    base_id = slugify(name)
    existing_ids = {c["id"] for c in registry["clients"]}
    client_id = base_id
    n = 2
    while client_id in existing_ids:
        client_id = f"{base_id}-{n}"
        n += 1

    for agent in CONFIGURABLE_AGENTS:
        template_path = AGENTS_DIR / agent / "config.yaml"
        dest_path = client_config_path(client_id, agent)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if template_path.exists():
            shutil.copyfile(template_path, dest_path)
        else:
            dest_path.touch()

    client = {
        "id": client_id,
        "name": name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "default": False,
    }
    registry["clients"].append(client)
    save_registry(registry)
    return client
