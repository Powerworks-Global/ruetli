"""Entry point: `python -m eval.cli <command>`.

Commands:
  run-eval          Run baseline vs ours over data/tasks.jsonl, print the
                     Section 5 metrics table.
  replay RUN_ID      Print the timeline for one run (see replay.py).
  shred SUBJECT_ID   GDPR/FADP erasure — destroy a subject's key (ADR-005).
  reflect            Run the self-review pass over the last eval batch and
                      print its findings (ADR-007). Advisory only — never
                      changes policy/scopes/prompts on its own.

Uses the dev-stub agent and the ScopePolicyGate stand-in by default (see
policy.py / agent.py docstrings) — set RUTLI_REAL_BACKENDS=1 to swap in
OllamaApertusAgent + EunomiaPolicyGate instead, once `ollama serve` has
the real model and a `eunomia-server` container is running (see those
modules' docstrings for exact setup). One env var, not a code change,
so flipping to real submission numbers never requires editing this file.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from eval.agent import AgentBackend, OllamaApertusAgent, StubApertusAgent
from eval.ledger import Ledger
from eval.metrics import (
    compute_condition_metrics,
    format_markdown_table,
    replay_fidelity,
    tamper_detection_rate,
)
from eval.policy import EunomiaPolicyGate, PolicyGate, ScopePolicyGate
from eval.reflection import format_report, generate_reflection
from eval.replay import print_timeline
from eval.runner import run_condition
from eval.tasks import load_tasks

TRACK_ROOT = Path(__file__).resolve().parents[2]
TASKS_PATH = TRACK_ROOT / "data" / "tasks.jsonl"
LEDGER_PATH = TRACK_ROOT / "data" / "eval_run.db"
REFLECTION_STATE_PATH = TRACK_ROOT / "data" / "reflection_state.json"
EVAL_RUN_PREFIX = "eval"


def _use_real_backends() -> bool:
    return os.environ.get("RUTLI_REAL_BACKENDS", "").strip() == "1"


def _make_agent() -> AgentBackend:
    if _use_real_backends():
        return OllamaApertusAgent(
            model=os.environ.get("RUTLI_OLLAMA_MODEL", "apertus-1.5-8b"),
            host=os.environ.get("RUTLI_OLLAMA_HOST", "http://localhost:11434"),
        )
    return StubApertusAgent()


def _make_gate() -> PolicyGate:
    if _use_real_backends():
        return EunomiaPolicyGate(base_url=os.environ.get("RUTLI_EUNOMIA_URL", "http://localhost:8421"))
    return ScopePolicyGate()


def cmd_run_eval(_args: argparse.Namespace) -> None:
    tasks = load_tasks(TASKS_PATH)
    ledger = Ledger(LEDGER_PATH)
    agent = _make_agent()

    baseline_run_prefix = EVAL_RUN_PREFIX
    baseline_results = run_condition(ledger, baseline_run_prefix, "baseline", tasks, agent, gate=None)
    ours_results = run_condition(ledger, baseline_run_prefix, "ours", tasks, agent, gate=_make_gate())

    baseline_metrics = compute_condition_metrics(baseline_results)
    ours_metrics = compute_condition_metrics(ours_results)

    all_run_ids = [f"{baseline_run_prefix}-baseline-{t.task_id}" for t in tasks] + [
        f"{baseline_run_prefix}-ours-{t.task_id}" for t in tasks
    ]
    fidelity = replay_fidelity(ledger, all_run_ids)
    tamper_rate = tamper_detection_rate()

    if _use_real_backends():
        print("Using REAL backends: OllamaApertusAgent + EunomiaPolicyGate — submission numbers.\n")
    else:
        print(
            "NOTE: dev-stub agent + ScopePolicyGate stand-in — harness-validation numbers, "
            "NOT final submission numbers (see technical_report.md Section 5). "
            "Set RUTLI_REAL_BACKENDS=1 once ollama + eunomia-server are running.\n"
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


def cmd_reflect(_args: argparse.Namespace) -> None:
    tasks = load_tasks(TASKS_PATH)
    ledger = Ledger(LEDGER_PATH)
    reflection_run_id, findings = generate_reflection(ledger, EVAL_RUN_PREFIX, tasks, REFLECTION_STATE_PATH)
    print(f"Reflection recorded as ledger run '{reflection_run_id}' (ADR-007 — advisory only).\n")
    print(format_report(findings))
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

    sub.add_parser("reflect").set_defaults(func=cmd_reflect)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
