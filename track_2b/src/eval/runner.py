"""Runs the baseline-vs-ours comparison over the task set, appending every
step to the event ledger (ADR-003) and encrypting any company/subject
identifier it touches (ADR-005) along the way.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from eval.agent import AgentBackend
from eval.ledger import Ledger
from eval.policy import PolicyGate
from eval.tasks import Task

CANTONAL_UID_RE = re.compile(r"CHE-\d{3}\.\d{3}\.\d{3}")


def _extract_subject_id(resource: str) -> str | None:
    match = CANTONAL_UID_RE.search(resource)
    return match.group(0) if match else None


@dataclass
class TaskResult:
    task_id: str
    category: str
    should_allow: bool
    allowed: bool
    self_censored: bool
    gate_latency_ms: float | None


def decide(agent: AgentBackend, gate: PolicyGate | None, task: Task) -> tuple[bool, bool, float | None]:
    """Returns (allowed, self_censored, gate_latency_ms)."""
    if agent.self_censors(task):
        return False, True, None
    proposed = agent.propose(task)
    if gate is None:
        return True, False, None
    t0 = time.perf_counter()
    decision = gate.check(proposed.resource, task.authorized_scopes)
    latency_ms = (time.perf_counter() - t0) * 1000
    return decision.allowed, False, latency_ms


def run_condition(
    ledger: Ledger,
    run_id_prefix: str,
    condition_name: str,
    tasks: list[Task],
    agent: AgentBackend,
    gate: PolicyGate | None,
) -> list[TaskResult]:
    results = []
    for task in tasks:
        run_id = f"{run_id_prefix}-{condition_name}-{task.task_id}"
        subject_id = _extract_subject_id(task.requested_resource)

        ledger.append(
            run_id,
            task.task_id,
            "PromptReceived",
            {"category": task.category, "requested_tool": task.requested_tool},
            personal_fields={"prompt": task.prompt} if subject_id else None,
            subject_id=subject_id,
        )

        allowed, self_censored, latency_ms = decide(agent, gate, task)

        ledger.append(
            run_id,
            task.task_id,
            "PolicyEvaluated",
            {
                "condition": condition_name,
                "self_censored": self_censored,
                "gate_present": gate is not None,
                "decision": "ALLOW" if allowed else "DENY",
                "gate_latency_ms": latency_ms,
            },
        )

        if allowed:
            ledger.append(
                run_id,
                task.task_id,
                "ToolExecutionCompleted",
                {"tool": task.requested_tool, "resource": task.requested_resource},
                personal_fields={"accessed_resource": task.requested_resource} if subject_id else None,
                subject_id=subject_id,
            )

        ledger.append(
            run_id,
            task.task_id,
            "ModelOutput",
            {"final_decision": "ALLOW" if allowed else "DENY"},
        )

        results.append(
            TaskResult(
                task_id=task.task_id,
                category=task.category,
                should_allow=task.should_allow,
                allowed=allowed,
                self_censored=self_censored,
                gate_latency_ms=latency_ms,
            )
        )
    return results
