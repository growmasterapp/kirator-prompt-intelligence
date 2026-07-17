#!/usr/bin/env python3
"""
Kirator Prompt Intelligence — Overnight Ship-Readiness Battery

Runs the full QA stack intended for overnight pre-release validation:
  1) Fast unit + API pytest suite (no Ollama required for most)
  2) Playwright GUI suite (browser automation)
  3) Full LLM pipeline battery (requires Ollama) — optional loops for soak

Usage (from project root):
  python scripts/run_overnight_battery.py
  python scripts/run_overnight_battery.py --loops 3
  python scripts/run_overnight_battery.py --skip-pipeline
  python scripts/run_overnight_battery.py --skip-gui
  python scripts/run_overnight_battery.py --quick

Windows:
  run_overnight_tests.bat
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "test_results"


def run(cmd: list[str], cwd: Path | None = None) -> dict:
    print()
    print("=" * 72)
    print(">", " ".join(cmd))
    print("=" * 72)
    start = time.time()
    proc = subprocess.run(cmd, cwd=str(cwd or ROOT))
    elapsed = round(time.time() - start, 1)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "elapsed_sec": elapsed,
        "ok": proc.returncode == 0,
    }


def ollama_up() -> bool:
    try:
        import httpx

        return httpx.get("http://localhost:11434/api/tags", timeout=3).status_code == 200
    except Exception:
        return False


def write_summary(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = []
    md.append("# Kirator Overnight Battery Summary")
    md.append(f"**Started:** {payload['started']}")
    md.append(f"**Finished:** {payload['finished']}")
    md.append(f"**Overall:** {'PASS' if payload['ok'] else 'FAIL'}")
    md.append("")
    md.append("| Step | OK | Seconds | Exit |")
    md.append("|------|----|---------|------|")
    for step in payload["steps"]:
        md.append(
            f"| {step['name']} | {'PASS' if step['ok'] else 'FAIL'} | "
            f"{step['elapsed_sec']} | {step['returncode']} |"
        )
    md.append("")
    if payload.get("notes"):
        md.append("## Notes")
        for n in payload["notes"]:
            md.append(f"- {n}")
        md.append("")
    (path.with_suffix(".md")).write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Kirator overnight ship-readiness battery")
    parser.add_argument("--skip-unit", action="store_true", help="Skip unit/API pytest")
    parser.add_argument("--skip-gui", action="store_true", help="Skip Playwright GUI tests")
    parser.add_argument("--skip-pipeline", action="store_true", help="Skip LLM pipeline battery")
    parser.add_argument("--skip-e2e", action="store_true", help="Skip GUI E2E pipeline run")
    parser.add_argument("--quick", action="store_true", help="Faster pipeline matrix (4 tests)")
    parser.add_argument(
        "--loops",
        type=int,
        default=1,
        help="Repeat the pipeline battery N times (soak testing)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Pipeline battery parallelism (careful with GPU/VRAM)",
    )
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    started = datetime.now().isoformat(timespec="seconds")
    steps: list[dict] = []
    notes: list[str] = []

    print()
    print("*" * 72)
    print("  KIRATOR PROMPT INTELLIGENCE — OVERNIGHT SHIP-READINESS BATTERY")
    print(f"  {started}")
    print("*" * 72)

    py = sys.executable

    # 1) Unit + API
    if not args.skip_unit:
        step = run(
            [
                py,
                "-m",
                "pytest",
                "tests/unit",
                "tests/api",
                "-m",
                "unit or api",
                "-q",
                "--tb=short",
            ]
        )
        step["name"] = "unit_api"
        steps.append(step)
    else:
        notes.append("Skipped unit/API suite")

    # 2) GUI (excluding slow e2e unless overnight wants it)
    if not args.skip_gui:
        gui_cmd = [
            py,
            "-m",
            "pytest",
            "tests/gui",
            "-m",
            "gui and not e2e",
            "-q",
            "--tb=short",
        ]
        step = run(gui_cmd)
        step["name"] = "gui_chrome"
        steps.append(step)

        if not args.skip_e2e:
            if ollama_up():
                step = run(
                    [
                        py,
                        "-m",
                        "pytest",
                        "tests/gui",
                        "-m",
                        "e2e",
                        "-q",
                        "--tb=short",
                        "--timeout=900",
                    ]
                )
                step["name"] = "gui_e2e"
                steps.append(step)
            else:
                notes.append("Skipped GUI E2E — Ollama not reachable")
    else:
        notes.append("Skipped GUI suite")

    # 3) Pipeline battery (existing scripts/test_battery.py)
    if not args.skip_pipeline:
        if not ollama_up():
            notes.append("Skipped pipeline battery — Ollama not reachable")
            steps.append(
                {
                    "name": "pipeline_battery",
                    "ok": False,
                    "returncode": 2,
                    "elapsed_sec": 0,
                    "cmd": ["pipeline_skipped"],
                }
            )
        else:
            for i in range(1, max(1, args.loops) + 1):
                cmd = [py, str(ROOT / "scripts" / "test_battery.py"), "--parallel", str(args.parallel)]
                if args.quick:
                    cmd.append("--quick")
                out = RESULTS / f"overnight_pipeline_{ts}_loop{i}"
                out.mkdir(parents=True, exist_ok=True)
                cmd.extend(["--out", str(out)])
                step = run(cmd)
                step["name"] = f"pipeline_loop_{i}"
                steps.append(step)
    else:
        notes.append("Skipped pipeline battery")

    finished = datetime.now().isoformat(timespec="seconds")
    ok = all(s.get("ok") for s in steps) if steps else False
    summary = {
        "started": started,
        "finished": finished,
        "ok": ok,
        "steps": steps,
        "notes": notes,
        "args": vars(args),
    }
    summary_path = RESULTS / f"overnight_summary_{ts}.json"
    write_summary(summary_path, summary)

    print()
    print("*" * 72)
    print(f"  OVERNIGHT BATTERY {'PASSED' if ok else 'FAILED'}")
    print(f"  Summary: {summary_path}")
    print(f"           {summary_path.with_suffix('.md')}")
    print("*" * 72)
    print()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
