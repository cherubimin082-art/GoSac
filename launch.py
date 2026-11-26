"""
launch — one-click starter for GoSac Mission Control.

What it does:
  1. Checks if the dashboard is already running at localhost:8080.
  2. If not, starts web/server.py (the local backend + static server).
  3. Opens your default browser to the dashboard.
  4. Keeps running in this window while the server runs - closing this
     window (or Ctrl+C) stops the server.

This is meant to be double-clicked via "Start GoSac Mission Control.bat",
not run directly, though `python launch.py` works the same way.
"""

import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

PORT = 8080
URL = f"http://localhost:{PORT}"
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT_DIR, "web")


def is_up() -> bool:
    try:
        urllib.request.urlopen(URL, timeout=1)
        return True
    except Exception:
        return False


def main():
    if is_up():
        print(f"launch: GoSac Mission Control is already running at {URL}")
        webbrowser.open(URL)
        return

    print("launch: starting GoSac Mission Control...")
    process = subprocess.Popen([sys.executable, "server.py", str(PORT)], cwd=WEB_DIR)

    for _ in range(20):  # wait up to ~5s for the server to actually come up
        time.sleep(0.25)
        if is_up():
            break

    webbrowser.open(URL)
    print(f"launch: running at {URL}")
    print("launch: close this window (or Ctrl+C) to stop the server.")

    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        print("\nlaunch: stopped.")


if __name__ == "__main__":
    main()
