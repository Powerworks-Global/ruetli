"""Runs the baseline-vs-ours comparison over the task set, appending every
step to the event ledger (ADR-003) and encrypting any company/subject
identifier it touches (ADR-005) along the way.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from eval.agent import AgentBackend
from eval.actions import Action, validate_action
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
    outcome: str = "unknown"
    action_correct: bool | None = None


def decide(agent: AgentBackend, gate: PolicyGate | None, task: Task) -> tuple[bool, bool, float | None]:
    """Returns (allowed, self_censored, gate_latency_ms)."""
    if agent.self_censors(task):
        return False, True, None
    proposed = agent.propose(task)
    action = validate_action(proposed.tool, proposed.resource)
    if gate is None:
        return True, False, None
    t0 = time.perf_counter()
    decision = gate.check(action.resource, task.authorized_scopes, action)
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

        allowed = False
        self_censored = False
        latency_ms = None
        action: Action | None = None
        reason = ""
        outcome = "invalid_proposal"
        try:
            self_censored = agent.self_censors(task)
            if self_censored:
                outcome = "model_refusal"
            else:
                proposed = agent.propose(task)
                subject_id = _extract_subject_id(proposed.resource) or subject_id
                # Never log an unvalidated proposal: it may contain arbitrary personal data.
                action = validate_action(proposed.tool, proposed.resource)
                proposed_payload = {"contract_version": action.version, "tool": action.tool, "operation": action.operation}
                if not subject_id:
                    proposed_payload["resource"] = action.resource
                ledger.append(run_id, task.task_id, "ToolProposed", proposed_payload,
                              personal_fields={"resource": action.resource} if subject_id else None,
                              subject_id=subject_id)
                if gate is None:
                    allowed = True
                    outcome = "allowed"
                else:
                    t0 = time.perf_counter()
                    try:
                        decision = gate.check(action.resource, task.authorized_scopes, action)
                    finally:
                        latency_ms = (time.perf_counter() - t0) * 1000
                    allowed = decision.allowed
                    reason = decision.reason
                    outcome = "allowed" if allowed else "policy_denial"
        except (ValueError, TypeError, KeyError) as exc:
            outcome = "invalid_proposal"
            reason = str(exc)
        except Exception as exc:
            outcome = "backend_error"
            reason = str(exc)
        if subject_id and reason:
            reason = reason.replace(subject_id, "[protected]")

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
                "outcome": outcome,
                "reason": reason,
                "contract_version": action.version if action else None,
            },
        )

        if allowed:
            ledger.append(
                run_id,
                task.task_id,
                "ToolExecutionCompleted",
                {"tool": action.tool, "operation": action.operation, "contract_version": action.version,
                 "execution_mode": "simulated", "status": "simulated",
                 **({} if subject_id else {"resource": action.resource})},
                personal_fields={"resource": action.resource} if subject_id else None,
                subject_id=subject_id,
            )

        ledger.append(
            run_id,
            task.task_id,
            "ModelOutput",
            {"final_decision": "ALLOW" if allowed else "DENY", "outcome": outcome},
        )

        results.append(
            TaskResult(
                task_id=task.task_id,
                category=task.category,
                should_allow=task.should_allow,
                allowed=allowed,
                self_censored=self_censored,
                gate_latency_ms=latency_ms,
                outcome=outcome,
                action_correct=(action.tool == task.requested_tool and action.resource == task.requested_resource)
                if action else None,
            )
        )
    return results
