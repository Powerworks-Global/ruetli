"""Policy gates checked before any tool call executes.

Three implementations:
- NullPolicyGate: the baseline — no gate at all, relies entirely on the
  agent having read its instructions in the system prompt.
- ScopePolicyGate: a real (if simple) ABAC check against the resource
  scope, independent of what the LLM was tricked into believing by the
  prompt. This stands in for a live Eunomia server during development —
  it implements the same decision Eunomia's `/check` makes, so swapping
  in EunomiaPolicyGate later should not change the metrics code at all.
- EunomiaPolicyGate: real HTTP client against a running `eunomia-server`
  instance (https://github.com/whataboutyou-ai/eunomia). NOT exercised
  yet in this environment — no Docker/network available here. Wire this
  in once the server is actually running (see technical_report.md
  Section 7) and swap it for ScopePolicyGate in runner.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


class PolicyGate(Protocol):
    def check(self, requested_resource: str, authorized_scopes: tuple[str, ...]) -> PolicyDecision:
        ...


class NullPolicyGate:
    """The baseline: always allows. Matches a system where authorization
    is only ever a sentence in the system prompt, never enforced."""

    def check(self, requested_resource: str, authorized_scopes: tuple[str, ...]) -> PolicyDecision:
        return PolicyDecision(allowed=True, reason="no gate — baseline has no enforcement")


def _scope_matches(resource: str, scope: str) -> bool:
    if scope.endswith(":*"):
        return resource.startswith(scope[:-1])
    return resource == scope or resource.startswith(scope + ":")


class ScopePolicyGate:
    """Deterministic ABAC stand-in for a live Eunomia server: allow iff the
    requested resource falls under one of the caller's authorized scopes."""

    def check(self, requested_resource: str, authorized_scopes: tuple[str, ...]) -> PolicyDecision:
        for scope in authorized_scopes:
            if _scope_matches(requested_resource, scope):
                return PolicyDecision(allowed=True, reason=f"matched scope '{scope}'")
        return PolicyDecision(
            allowed=False,
            reason=f"resource '{requested_resource}' not covered by any authorized scope {authorized_scopes}",
        )


class EunomiaPolicyGate:
    """Real client for a running `eunomia-server` (Apache 2.0, see
    https://github.com/whataboutyou-ai/eunomia). TODO — not exercised in
    this environment: requires `pip install eunomia-sdk` or `requests`,
    plus a reachable server (default http://localhost:8421)."""

    def __init__(self, base_url: str = "http://localhost:8421", agent_passport: str | None = None):
        self.base_url = base_url
        self.agent_passport = agent_passport

    def check(self, requested_resource: str, authorized_scopes: tuple[str, ...]) -> PolicyDecision:
        raise NotImplementedError(
            "EunomiaPolicyGate is a real-server client, not wired into the eval run yet. "
            "Spin up `docker run -p 8421:8421 ttommitt/eunomia-server:latest`, "
            "configure policies via /admin/policies, then POST to /check here."
        )
