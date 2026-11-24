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
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "mariner"))
import client_registry  # noqa: E402

WEB_DIR = Path(__file__).parent
AGENTS_DIR = WEB_DIR.parent / "agents"

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

    def do_GET(self):
        if self.path == "/api/clients":
            try:
                clients = client_registry.list_clients()
                self._send_json(200, {"clients": clients})
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
            return
        if self.path == "/api/agents":
            self._send_json(200, {"agents": RUNNABLE_AGENTS})
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
