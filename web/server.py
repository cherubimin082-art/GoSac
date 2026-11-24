"""
server — local backend for GoSac Mission Control's multi-client platform.

Replaces `python -m http.server`: serves the dashboard's static files
exactly as before, plus two small JSON API endpoints the dashboard's
"Add Client" form needs (a static page alone can't write files to disk).

GET  /api/clients        -> list every registered client
POST /api/clients {name} -> scaffold a new client's config folders and
                             register it

This is a local-only tool: it has no auth, binds to localhost by
default, and is meant to run on your own machine while you use the
dashboard. Don't expose it on a public network as-is.

Usage:
  python server.py [port]   # defaults to 8080
"""

import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "mariner"))
import client_registry  # noqa: E402

WEB_DIR = Path(__file__).parent


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
