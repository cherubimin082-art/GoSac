"""
refresh_dashboard — regenerates Beacon's report and tells you the next step.

What it does:
  Runs `beacon_agent.py compile` for real (reads whatever real output each
  sibling agent has actually produced) and prints the resulting report path.

What it does NOT do:
  Push the refreshed CSV into the GoSac Fleet Results dashboard artifact.
  There's no public API for a script to write to an artifact's store
  directly - only Claude's Artifact/ArtifactData tools can do that, inside
  a Claude Code session. So this script's last step is a reminder to ask
  Claude to sync it, not an automatic push.

Usage:
  python refresh_dashboard.py
"""

import subprocess
import sys
from pathlib import Path


def main():
    beacon_dir = Path(__file__).parent
    result = subprocess.run(
        [sys.executable, "beacon_agent.py", "compile"],
        cwd=beacon_dir,
    )

    if result.returncode != 0:
        print("\nrefresh_dashboard: beacon compile reported an issue above - "
              "check which agent's data is missing before syncing anything.")
        sys.exit(result.returncode)

    csv_path = beacon_dir / "beacon_report.csv"
    print(f"\nrefresh_dashboard: {csv_path} is up to date.")
    print("refresh_dashboard: this script can't push it into the dashboard itself -")
    print("refresh_dashboard: ask Claude to \"sync the dashboard with the latest Beacon report\"")
    print("refresh_dashboard: and it will upload this file and update the GoSac Fleet Results page.")


if __name__ == "__main__":
    main()
