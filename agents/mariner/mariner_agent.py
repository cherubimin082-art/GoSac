"""
Mariner — the orchestrator for the GoSac agent fleet.

What it does:
  `run <schedule>` — runs every job tagged with the given schedule
  ("daily", "weekly", "monthly", "frequent"), each as its own subprocess,
  and reports a consolidated summary: how many ran clean, which need a
  human to look at them.

What it deliberately does NOT do:
  - Reimplement any guardrail. Spend ceilings, the incomplete-listing
    guard, the fulfillment-routing stability check - those all already
    live inside each individual agent and fire on their own exit code.
    Mariner only reads that exit code; it never second-guesses it.
  - Retry a failed job automatically. A non-zero exit from any agent means
    that agent already decided something needs a human - Mariner surfaces
    that, it doesn't paper over it with a retry loop.
  - Run anything without being told to. Mariner has no cron/scheduler
    built in; wire `mariner_agent.py run daily` into an actual cron job
    (or Windows Task Scheduler) yourself once you're ready for that.

Use --mock to pass --mock through to every job that supports it (jobs that
don't take --mock, like the readiness checks, run exactly as they would
for real, since there's nothing to fake there).
"""

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_job(job: dict, mariner_dir: Path, mock: bool) -> tuple[str, int, str]:
    """Runs one job as a subprocess. Returns (name, exit_code, last_output_line)."""
    cwd = (mariner_dir / job["agent_dir"]).resolve()
    command = list(job["command"])
    if command and command[0] in ("python", "python3"):
        command[0] = sys.executable
    if mock and job.get("supports_mock"):
        command.append("--mock")

    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=120
        )
    except FileNotFoundError as exc:
        return job["name"], 1, f"FAILED TO LAUNCH: {exc}"
    except subprocess.TimeoutExpired:
        return job["name"], 1, "TIMED OUT after 120s"

    output = (result.stdout or result.stderr or "").strip()
    last_line = output.splitlines()[-1] if output else "(no output)"
    return job["name"], result.returncode, last_line


def run_schedule(config_path: str, schedule: str, mock: bool) -> None:
    config = load_config(config_path)
    mariner_dir = Path(config_path).parent
    jobs = [j for j in config["jobs"] if j["schedule"] == schedule]

    if not jobs:
        print(f"Mariner: no jobs tagged '{schedule}' in config.yaml")
        sys.exit(1)

    prefix = "Mariner [MOCK]" if mock else "Mariner"
    print(f"{prefix}: running {len(jobs)} job(s) tagged '{schedule}'")

    ok_jobs = []
    attention_jobs = []
    for job in jobs:
        name, exit_code, last_line = run_job(job, mariner_dir, mock)
        if exit_code == 0:
            ok_jobs.append(name)
            print(f"{prefix}: [OK] {name} - {last_line}")
        else:
            attention_jobs.append(name)
            print(f"{prefix}: [NEEDS ATTENTION] {name} (exit {exit_code}) - {last_line}")

    print(f"{prefix}: {len(ok_jobs)} clean, {len(attention_jobs)} need attention")
    if attention_jobs:
        print(f"{prefix}: review these before re-running: {', '.join(attention_jobs)}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Mariner — fleet orchestrator")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("schedule", choices=["daily", "weekly", "monthly", "frequent"])
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Pass --mock through to every job that supports it",
    )
    args = parser.parse_args()

    run_schedule(args.config, args.schedule, args.mock)


if __name__ == "__main__":
    main()
