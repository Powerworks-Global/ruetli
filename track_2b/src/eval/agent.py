"""Agent backends that propose tool calls for a task.

StubApertusAgent is a deterministic, rule-based stand-in for the real
Apertus 1.5 8B agent — used so the rest of the harness (ledger, gate,
metrics) can be built and validated today, without a GPU/Ollama runtime
in this environment. It models two things explicitly, as documented
heuristics rather than claimed model behavior:

1. `propose()` — the agent always attempts the tool call the task's
   prompt is actually asking for (whether legitimate, overtly
   unauthorized, or injected). This isolates the effect of the policy
   gate: agent behavior is identical between the "baseline" and "ours"
   conditions in runner.py — only the presence of a gate differs.
2. `self_censors()` — a crude stand-in for the base model's own
   alignment/instruction-following catching an *overtly* stated policy
   violation when the system prompt states the policy in plain text.
   By construction it never catches prompt-injection (the injected text
   is written to look like a legitimate system-level authorization,
   which is exactly what makes injection the harder case — see
   technical_report.md Section 5).

TODO: replace both methods with real Apertus 1.5 8B inference
(`OllamaApertusAgent`, stubbed below) before submission. The stub's
numbers are harness-validation only, not submission-final results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from eval.tasks import Task

OVERT_REFUSAL_TRIGGERS = (
    "delete",
    "admin",
    "override the data classification",
    "grant me",
    "confidential",
    "restricted",
)


@dataclass(frozen=True)
class ProposedCall:
    tool: str
    resource: str


class AgentBackend(Protocol):
    def propose(self, task: Task) -> ProposedCall:
        ...

    def self_censors(self, task: Task) -> bool:
        ...


class StubApertusAgent:
    def propose(self, task: Task) -> ProposedCall:
        return ProposedCall(tool=task.requested_tool, resource=task.requested_resource)

    def self_censors(self, task: Task) -> bool:
        if task.category != "unauthorized":
            # Legitimate requests have nothing to refuse. Injection prompts are
            # written specifically to defeat this surface-level heuristic.
            return False
        prompt_lower = task.prompt.lower()
        return any(trigger in prompt_lower for trigger in OVERT_REFUSAL_TRIGGERS)


class OllamaApertusAgent:
    """Real backend: Apertus 1.5 8B via local Ollama/llama.cpp. TODO — not
    wired yet. Requires the model pulled locally and an agent prompt
    template that asks Apertus to emit a structured tool-call JSON, which
    this class would parse into a ProposedCall."""

    def __init__(self, model: str = "apertus-1.5-8b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host

    def propose(self, task: Task) -> ProposedCall:
        raise NotImplementedError(
            "OllamaApertusAgent is not wired yet — pull the Apertus 1.5 8B "
            "GGUF via Ollama, build the agent prompt template, and parse its "
            "tool-call output into a ProposedCall here."
        )

    def self_censors(self, task: Task) -> bool:
        raise NotImplementedError("See propose() — same TODO.")
