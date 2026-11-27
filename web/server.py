"""
server — local backend for GoSac Mission Control's multi-client platform.

Replaces `python -m http.server`: serves the dashboard's static files
exactly as before, plus two small JSON API endpoints the dashboard's
"Add Client" form needs (a static page alone can't write files to disk).

GET  /api/clients        -> list every registered client
POST /api/clients {name} -> scaffold a new client's config folders and
                             register it
GET  /api/agents         -> list runnable agents and their commands
POST /api/run {agentId, command, clientId, mock} -> actually run that
                             agent's command as a real subprocess and
                             return its output + exit code
GET  /api/oauth/google/start?agentId=current&clientId=gosac
                             -> redirects to Google's real OAuth consent
                                screen (Google Ads or GA4 scope,
                                depending on agentId)
GET  /api/oauth/google/callback
                             -> Google redirects here after consent;
                                exchanges the code for a refresh token
                                and writes it straight into that
                                client's credentials file

Covers Current (Google Ads) and Sonar (GA4) - both of Google's APIs
accept a signed-in user's OAuth credentials directly, as long as that
Google account has access to the Ads account / GA4 property. Sonar's
README still documents the service-account route as an alternative,
since some setups prefer a credential that doesn't belong to a
specific person.

This is a local-only tool: it has no auth, binds to localhost by
default, and is meant to run on your own machine while you use the
dashboard. Don't expose it on a public network as-is. /api/run executes
real code on your machine on request from the page - that's the whole
point (running agents from the UI instead of a terminal), but it means
this server should never be exposed beyond localhost.

Usage:
  python server.py [port]   # defaults to 8080
"""

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "mariner"))
import client_registry  # noqa: E402

WEB_DIR = Path(__file__).parent
AGENTS_DIR = WEB_DIR.parent / "agents"
OAUTH_CLIENT_PATH = WEB_DIR / "google_oauth_client.json"

# Which Google scope each OAuth-capable agent needs. analytics (not
# analytics.readonly) is used for Sonar so the same signed-in session can
# both create conversion events (Admin API) and read them back (Data API).
GOOGLE_OAUTH_SCOPES = {
    "current": "https://www.googleapis.com/auth/adwords",
    "sonar": "https://www.googleapis.com/auth/analytics",
}

# Each agent's script and the commands it actually supports, exactly as
# defined in its own argparse. Mock mode is passed uniformly when
# requested; a command that doesn't use --mock (like check-readiness)
# just ignores it, since every script accepts the flag even where it's
# a no-op for that particular command.
RUNNABLE_AGENTS = {
    "sonar":    {"script": "sonar_agent.py",    "commands": ["setup", "verify"]},
    "current":  {"script": "current_agent.py",  "commands": ["build", "tune"]},
    "coral":    {"script": "coral_agent.py",    "commands": ["rewrite", "route-leads"]},
    "harbor":   {"script": "harbor_agent.py",   "commands": ["check-readiness", "sync-skus"]},
    "compass":  {"script": "compass_agent.py",  "commands": ["classify"]},
    "horizon":  {"script": "horizon_agent.py",  "commands": ["check-readiness", "generate-catalog"]},
    "pearl":    {"script": "pearl_agent.py",    "commands": ["generate", "push"]},
    "undertow": {"script": "undertow_agent.py", "commands": ["build", "monitor"]},
}


def run_agent_command(agent_id: str, command: str, client_id: str, mock: bool) -> dict:
    if agent_id not in RUNNABLE_AGENTS:
        raise ValueError(f"unknown agent '{agent_id}'")
    spec = RUNNABLE_AGENTS[agent_id]
    if command not in spec["commands"]:
        raise ValueError(f"'{command}' is not a valid command for {agent_id}")

    config_path = client_registry.client_config_path(client_id, agent_id)
    agent_dir = AGENTS_DIR / agent_id

    cmd = [sys.executable, spec["script"], command, "--config", str(config_path)]
    if mock:
        cmd.append("--mock")

    result = subprocess.run(cmd, cwd=agent_dir, capture_output=True, text=True, timeout=120)
    return {
        "exitCode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# ---------------------------------------------------------------------------
# Google OAuth (Current / Google Ads only — see module docstring for why)
# ---------------------------------------------------------------------------

def load_oauth_client() -> dict:
    if not OAUTH_CLIENT_PATH.exists():
        raise ValueError(
            "No web/google_oauth_client.json found — create a Google Cloud "
            "OAuth client (type: Web application, redirect URI "
            "http://localhost:8080/api/oauth/google/callback) and save its "
            "client_id/client_secret there first."
        )
    with open(OAUTH_CLIENT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_google_auth_url(agent_id: str, client_id: str) -> str:
    if agent_id not in GOOGLE_OAUTH_SCOPES:
        raise ValueError(f"Google OAuth isn't wired up for '{agent_id}'.")
    oauth_client = load_oauth_client()
    state = f"{agent_id}|{client_id}"
    params = {
        "client_id": oauth_client["client_id"],
        "redirect_uri": oauth_client["redirect_uri"],
        "response_type": "code",
        "scope": GOOGLE_OAUTH_SCOPES[agent_id],
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


def exchange_google_code(code: str) -> dict:
    oauth_client = load_oauth_client()
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": oauth_client["client_id"],
        "client_secret": oauth_client["client_secret"],
        "redirect_uri": oauth_client["redirect_uri"],
        "grant_type": "authorization_code",
    }).encode("utf-8")

    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"Google rejected the code exchange: {body}")


def save_google_ads_refresh_token(client_id: str, agent_id: str, refresh_token: str) -> Path:
    """Writes the refresh token into that client's google-ads.yaml, next to
    its config.yaml. Preserves developer_token/login_customer_id if the
    file already has them — those still need to come from the user, OAuth
    can't produce them."""
    oauth_client = load_oauth_client()
    config_path = client_registry.client_config_path(client_id, agent_id)
    yaml_path = config_path.parent / "google-ads.yaml"

    existing = {}
    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}

    existing.update({
        "client_id": oauth_client["client_id"],
        "client_secret": oauth_client["client_secret"],
        "refresh_token": refresh_token,
        "use_proto_plus": True,
    })
    existing.setdefault("developer_token", "REPLACE_WITH_DEVELOPER_TOKEN")
    existing.setdefault("login_customer_id", "REPLACE_WITH_MCC_CUSTOMER_ID")

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing, f)

    # If current's own config.yaml still points at a placeholder, point it
    # at the file we just wrote so it's usable immediately.
    with open(config_path, "r", encoding="utf-8") as f:
        agent_config = yaml.safe_load(f)
    current_path = agent_config.get("google_ads", {}).get("credentials_path", "")
    if not current_path or current_path.startswith("REPLACE_WITH"):
        agent_config["google_ads"]["credentials_path"] = str(yaml_path)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(agent_config, f, sort_keys=False)

    return yaml_path


def save_ga4_refresh_token(client_id: str, agent_id: str, refresh_token: str) -> Path:
    """Writes an OAuth-user-credentials file for Sonar (GA4) — a lighter
    alternative to a service account JSON. sonar_agent.py's get_credentials
    detects this shape (it has a refresh_token field) and authenticates as
    the signed-in user instead of a service account."""
    oauth_client = load_oauth_client()
    config_path = client_registry.client_config_path(client_id, agent_id)
    creds_path = config_path.parent / "ga4-oauth-credentials.json"

    creds = {
        "client_id": oauth_client["client_id"],
        "client_secret": oauth_client["client_secret"],
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    with open(creds_path, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2)

    with open(config_path, "r", encoding="utf-8") as f:
        agent_config = yaml.safe_load(f)
    current_path = agent_config.get("ga4", {}).get("credentials_path", "")
    if not current_path or current_path.startswith("REPLACE_WITH"):
        agent_config["ga4"]["credentials_path"] = str(creds_path)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(agent_config, f, sort_keys=False)

    return creds_path


def save_google_oauth_tokens(agent_id: str, client_id: str, refresh_token: str) -> tuple[Path, str]:
    """Dispatches to the right save routine for this agent and returns
    (path written, a human note about what's still needed)."""
    if agent_id == "current":
        path = save_google_ads_refresh_token(client_id, agent_id, refresh_token)
        note = ("Still needed before Current can run for real: a real "
                "<code>developer_token</code> and <code>login_customer_id</code> in that "
                "same file — OAuth can't produce those.")
        return path, note
    if agent_id == "sonar":
        path = save_ga4_refresh_token(client_id, agent_id, refresh_token)
        note = ("Still needed: a real <code>ga4.property_id</code> in config.yaml — OAuth "
                "proves who you are, not which GA4 property you mean.")
        return path, note
    raise ValueError(f"Google OAuth isn't wired up for '{agent_id}'.")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, html: str):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        split = urllib.parse.urlsplit(self.path)
        path = split.path
        query = urllib.parse.parse_qs(split.query)

        if path == "/api/clients":
            try:
                clients = client_registry.list_clients()
                self._send_json(200, {"clients": clients})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return
        if path == "/api/agents":
            self._send_json(200, {"agents": RUNNABLE_AGENTS})
            return

        if path == "/api/oauth/google/start":
            agent_id = (query.get("agentId") or [""])[0]
            client_id = (query.get("clientId") or ["gosac"])[0]
            try:
                auth_url = build_google_auth_url(agent_id, client_id)
                self.send_response(302)
                self.send_header("Location", auth_url)
                self.end_headers()
            except ValueError as exc:
                self._send_html(400, f"<p>{exc}</p>")
            return

        if path == "/api/oauth/google/callback":
            error = (query.get("error") or [""])[0]
            if error:
                self._send_html(400, f"<p>Google returned an error: {error}</p>")
                return
            code = (query.get("code") or [""])[0]
            state = (query.get("state") or [""])[0]
            if not code or "|" not in state:
                self._send_html(400, "<p>Missing code or state from Google's redirect.</p>")
                return
            agent_id, client_id = state.split("|", 1)
            try:
                tokens = exchange_google_code(code)
                refresh_token = tokens.get("refresh_token")
                if not refresh_token:
                    self._send_html(
                        400,
                        "<p>Google didn't return a refresh token. This usually means you've "
                        "already authorized this app before — revoke access at "
                        "<a href='https://myaccount.google.com/permissions'>"
                        "myaccount.google.com/permissions</a> and try Connect again.</p>",
                    )
                    return
                saved_path, note = save_google_oauth_tokens(agent_id, client_id, refresh_token)
                self._send_html(200, f"""
                    <p>{agent_id} connected for client "{client_id}".</p>
                    <p>Refresh token saved to <code>{saved_path}</code>.</p>
                    <p>{note}</p>
                    <p>You can close this tab and go back to the dashboard.</p>
                """)
            except ValueError as exc:
                self._send_html(400, f"<p>{exc}</p>")
            except Exception as exc:
                self._send_html(500, f"<p>Unexpected error: {exc}</p>")
            return

        super().do_GET()

    def do_POST(self):
        if self.path == "/api/clients":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
                name = (data.get("name") or "").strip()
                if not name:
                    self._send_json(400, {"error": "name is required"})
                    return
                client = client_registry.add_client(name)
                self._send_json(201, {"client": client})
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        if self.path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
                agent_id = data.get("agentId")
                command = data.get("command")
                client_id = data.get("clientId") or "gosac"
                mock = bool(data.get("mock"))
                result = run_agent_command(agent_id, command, client_id, mock)
                self._send_json(200, result)
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
            except subprocess.TimeoutExpired:
                self._send_json(504, {"error": "timed out after 120s"})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return

        self._send_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        print(f"server: {self.address_string()} - {format % args}")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"server: GoSac Mission Control running at http://localhost:{port}")
    print("server: Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nserver: stopped")


if __name__ == "__main__":
    main()
