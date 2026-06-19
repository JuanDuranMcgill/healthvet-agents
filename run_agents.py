#!/usr/bin/env python3
"""Launch all HealthVet agents in separate processes."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

AGENTS = ("scout", "forensics", "compliance", "gap", "risk", "synthesis", "research")


def resolve_python(root: Path) -> Path:
    venv_python = root / "venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return venv_python
    venv_python = root / "venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all HealthVet Band agents")
    parser.add_argument(
        "--agent",
        choices=AGENTS,
        help="Run a single agent instead of all of them",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    python = resolve_python(root)
    targets = [args.agent] if args.agent else list(AGENTS)
    processes: list[tuple[str, subprocess.Popen]] = []

    print("HealthVet Agents - starting Band workers")
    print(f"Python: {python}")
    print("Press Ctrl+C to stop all agents\n")

    for name in targets:
        script = root / "agents" / f"{name}.py"
        proc = subprocess.Popen(
            [str(python), str(script)],
            cwd=root,
        )
        processes.append((name, proc))
        print(f"  started {name} (pid {proc.pid})")

    try:
        for name, proc in processes:
            code = proc.wait()
            if code != 0:
                print(f"{name} exited with code {code}", file=sys.stderr)
                return code
    except KeyboardInterrupt:
        print("\nStopping agents...")
        for name, proc in processes:
            if proc.poll() is None:
                proc.terminate()
                print(f"  stopped {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
