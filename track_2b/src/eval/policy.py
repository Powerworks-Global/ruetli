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
  instance (https://github.com/whataboutyou-ai/eunomia, Docker image
  `ttommitt/eunomia-server:latest`, port 8421 — both confirmed against
  the real repo/docs on 2026-10-06, not assumed). Implemented and unit
  tested against a mocked server below; NOT yet verified against a real
  running container — this sandbox cannot reach the Docker daemon
  (no socket access, no systemd). Run the container in a real shell
  (`docker run -p 8421:8421 ttommitt/eunomia-server:latest`) and re-run
  `make eval` with this gate swapped in (see runner.py) to get the real
  submission numbers.

  Encodes ScopePolicyGate's exact wildcard semantics
  (`resource == scope or resource.startswith(scope + ":")`, or for a
  `scope:*` wildcard, `resource.startswith(scope[:-1])`) as real Eunomia
  policy rules using its `equals`/`startswith` condition operators
  (confirmed against `eunomia_core.enums.policy.ConditionOperator` in
  the real source) — not a looser approximation of the original gate's
  decision boundary.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
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


def _policy_name_for(authorized_scopes: tuple[str, ...]) -> str:
    # Deterministic, not content-addressed by a real hash — collision risk
    # is irrelevant here (a handful of distinct scope-sets in one eval run,
    # not a multi-tenant system), and a readable name is easier to inspect
    # against the server's own /admin/policies listing while debugging.
    return "rutli-" + "-".join(sorted(authorized_scopes)).replace(":", "_").replace("*", "x")[:80]


def _rules_for_scope(scope: str) -> list[dict]:
    """One or two Eunomia Rules reproducing _scope_matches's exact decision
    boundary for a single scope string, via the real ConditionOperator
    enum (equals/startswith - confirmed against eunomia_core's source)."""
    if scope.endswith(":*"):
        prefix = scope[:-1]
        return [
            {
                "name": f"{scope}-prefix",
                "effect": "allow",
                "resource_conditions": [{"path": "attributes.resource", "operator": "startswith", "value": prefix}],
                "actions": ["execute"],
            }
        ]
    return [
        {
            "name": f"{scope}-exact",
            "effect": "allow",
            "resource_conditions": [{"path": "attributes.resource", "operator": "equals", "value": scope}],
            "actions": ["execute"],
        },
        {
            "name": f"{scope}-nested",
            "effect": "allow",
            "resource_conditions": [{"path": "attributes.resource", "operator": "startswith", "value": scope + ":"}],
            "actions": ["execute"],
        },
    ]


class EunomiaPolicyGate:
    """Real client for a running `eunomia-server`
    (https://github.com/whataboutyou-ai/eunomia, Apache 2.0, Docker image
    `ttommitt/eunomia-server:latest`, port 8421 by default).

    A policy is registered (idempotently - a 409/400 "already exists"
    response from a prior run or prior task with the same scope-set is
    swallowed, not treated as a failure) once per distinct authorized_scopes
    tuple seen, then every check() call is a real POST /check against it.
    No caching of allow/deny decisions themselves - every call is a fresh
    round-trip, matching the project's own "never cache the thing you're
    trying to prove is enforced live" posture.
    """

    def __init__(self, base_url: str = "http://localhost:8421", agent_passport: str | None = None, timeout: float = 10.0):
        self.base_url = base_url
        self.agent_passport = agent_passport
        self.timeout = timeout
        self._registered_policies: set[str] = set()

    def _post(self, path: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return {"_http_error": e.code, "_body": e.read().decode()}

    def _ensure_policy_registered(self, authorized_scopes: tuple[str, ...]) -> str:
        name = _policy_name_for(authorized_scopes)
        if name in self._registered_policies:
            return name
        rules: list[dict] = []
        for scope in authorized_scopes:
            rules.extend(_rules_for_scope(scope))
        policy = {"version": "1.0", "name": name, "default_effect": "deny", "rules": rules}
        result = self._post("/admin/policies", policy)
        # A 409/400 here means another task in this same run (or a prior
        # run) already registered this exact scope-set's policy - not a
        # real failure, the policy existing is exactly what we want.
        if "_http_error" in result and result["_http_error"] not in (400, 409):
            raise RuntimeError(f"EunomiaPolicyGate: failed to register policy {name!r}: {result}")
        self._registered_policies.add(name)
        return name

    def check(self, requested_resource: str, authorized_scopes: tuple[str, ...]) -> PolicyDecision:
        if not authorized_scopes:
            return PolicyDecision(allowed=False, reason="no authorized scopes - nothing to register or match against")
        self._ensure_policy_registered(authorized_scopes)
        result = self._post(
            "/check",
            {
                "principal": {"attributes": {"agent": self.agent_passport or "rutli-agent"}},
                "resource": {"attributes": {"resource": requested_resource}},
                "action": "execute",
            },
        )
        if "_http_error" in result:
            raise RuntimeError(f"EunomiaPolicyGate: /check failed: {result}")
        return PolicyDecision(allowed=bool(result.get("allowed")), reason=result.get("reason", "<no reason returned>"))
