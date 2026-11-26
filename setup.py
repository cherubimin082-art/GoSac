"""
setup — installs every agent's Python dependencies in one pass.

Run this once before the first "Start GoSac Mission Control". Safe to
re-run any time (pip skips already-satisfied requirements).
"""

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent
AGENTS_DIR = ROOT_DIR / "agents"
WEB_DIR = ROOT_DIR / "web"


def main():
    requirement_files = sorted(AGENTS_DIR.glob("*/requirements.txt"))
    web_requirements = WEB_DIR / "requirements.txt"
    if web_requirements.exists():
        requirement_files.append(web_requirements)
    if not requirement_files:
        print("setup: no requirements.txt files found - is this the right folder?")
        sys.exit(1)

    print(f"setup: installing dependencies for {len(requirement_files)} agent(s)...\n")
    failed = []
    for req_file in requirement_files:
        agent_name = req_file.parent.name
        print(f"setup: [{agent_name}] installing...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", "--quiet", "-r", str(req_file)]
        )
        if result.returncode != 0:
            failed.append(agent_name)
            print(f"setup: [{agent_name}] FAILED - see pip output above")
        else:
            print(f"setup: [{agent_name}] done")

    print()
    if failed:
        print(f"setup: finished with problems in: {', '.join(failed)}")
        sys.exit(1)
    print("setup: all agent dependencies installed. You can now run "
          "\"Start GoSac Mission Control.bat\".")


if __name__ == "__main__":
    main()
