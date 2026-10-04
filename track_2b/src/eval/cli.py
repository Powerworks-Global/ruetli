"""Entry point: `python -m eval.cli <command>`.

Commands:
  run-eval          Run baseline vs ours over data/tasks.jsonl, print the
                     Section 5 metrics table.
  replay RUN_ID      Print the timeline for one run (see replay.py).
  shred SUBJECT_ID   GDPR/FADP erasure — destroy a subject's key (ADR-005).

Uses the dev-stub agent and the ScopePolicyGate stand-in for a live
Eunomia server (see policy.py / agent.py docstrings) — not yet wired to
real Apertus 1.5 inference or a running eunomia-server instance.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval.agent import StubApertusAgent
from eval.ledger import Ledger
from eval.metrics import (
    compute_condition_metrics,
    format_markdown_table,
    replay_fidelity,
    tamper_detection_rate,
)
from eval.policy import ScopePolicyGate
from eval.replay import print_timeline
from eval.runner import run_condition
from eval.tasks import load_tasks

TRACK_ROOT = Path(__file__).resolve().parents[2]
TASKS_PATH = TRACK_ROOT / "data" / "tasks.jsonl"
LEDGER_PATH = TRACK_ROOT / "data" / "eval_run.db"


def cmd_run_eval(_args: argparse.Namespace) -> None:
    tasks = load_tasks(TASKS_PATH)
    ledger = Ledger(LEDGER_PATH)
    agent = StubApertusAgent()

    baseline_run_prefix = "eval"
    baseline_results = run_condition(ledger, baseline_run_prefix, "baseline", tasks, agent, gate=None)
    ours_results = run_condition(ledger, baseline_run_prefix, "ours", tasks, agent, gate=ScopePolicyGate())

    baseline_metrics = compute_condition_metrics(baseline_results)
    ours_metrics = compute_condition_metrics(ours_results)

    all_run_ids = [f"{baseline_run_prefix}-baseline-{t.task_id}" for t in tasks] + [
        f"{baseline_run_prefix}-ours-{t.task_id}" for t in tasks
    ]
    fidelity = replay_fidelity(ledger, all_run_ids)
    tamper_rate = tamper_detection_rate()

    print(
        "NOTE: dev-stub agent + ScopePolicyGate stand-in — harness-validation numbers, "
        "NOT final submission numbers (see technical_report.md Section 5).\n"
    )
    print(format_markdown_table(baseline_metrics, ours_metrics, fidelity, tamper_rate))
    ledger.close()


def cmd_replay(args: argparse.Namespace) -> None:
    ledger = Ledger(LEDGER_PATH)
    print_timeline(ledger, args.run_id)
    ledger.close()


def cmd_shred(args: argparse.Namespace) -> None:
    ledger = Ledger(LEDGER_PATH)
    deleted = ledger.shred(args.subject_id)
    print(f"Shredded key for subject '{args.subject_id}': {'done' if deleted else 'no key found'}")
    ledger.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m eval.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run-eval").set_defaults(func=cmd_run_eval)

    replay_parser = sub.add_parser("replay")
    replay_parser.add_argument("run_id")
    replay_parser.set_defaults(func=cmd_replay)

    shred_parser = sub.add_parser("shred")
    shred_parser.add_argument("subject_id")
    shred_parser.set_defaults(func=cmd_shred)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
