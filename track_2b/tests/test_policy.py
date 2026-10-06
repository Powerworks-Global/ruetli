import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.policy import EunomiaPolicyGate, NullPolicyGate, ScopePolicyGate  # noqa: E402


class TestScopePolicyGate(unittest.TestCase):
    def setUp(self):
        self.gate = ScopePolicyGate()

    def test_wildcard_scope_allows_matching_prefix(self):
        decision = self.gate.check("db-readonly:invoices:2026-Q3-004", ("db-readonly:invoices:*",))
        self.assertTrue(decision.allowed)

    def test_wildcard_scope_denies_non_matching_prefix(self):
        decision = self.gate.check("db-readonly:customer_pii:raw", ("db-readonly:invoices:*",))
        self.assertFalse(decision.allowed)

    def test_exact_scope_matches_exact_resource(self):
        decision = self.gate.check("cantonal_registry:company:*", ("cantonal_registry:company:*",))
        self.assertTrue(decision.allowed)

    def test_no_authorized_scopes_denies_everything(self):
        decision = self.gate.check("anything:at:all", ())
        self.assertFalse(decision.allowed)


class TestNullPolicyGate(unittest.TestCase):
    def test_always_allows(self):
        gate = NullPolicyGate()
        decision = gate.check("anything:at:all", ())
        self.assertTrue(decision.allowed)


class _FakeResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestEunomiaPolicyGate(unittest.TestCase):
    """Exercises EunomiaPolicyGate against a mocked server - not a live
    eunomia-server (this sandbox can't reach the Docker daemon at all).
    Verifies the request shapes and decision-parsing logic; does NOT prove
    the real server actually enforces these rules the way ScopePolicyGate's
    own tests prove its in-process logic does. Re-run against a real
    container (`docker run -p 8421:8421 ttommitt/eunomia-server:latest`)
    before trusting this for submission numbers."""

    def _patched(self, check_response: dict):
        calls = []

        def fake_urlopen(request, timeout=10.0):
            body = json.loads(request.data.decode())
            calls.append((request.full_url, body))
            if request.full_url.endswith("/admin/policies"):
                return _FakeResponse({"status": "created"})
            return _FakeResponse(check_response)

        return patch("eval.policy.urllib.request.urlopen", fake_urlopen), calls

    def test_registers_a_policy_then_checks(self):
        patcher, calls = self._patched({"allowed": True, "reason": "matched rule"})
        with patcher:
            gate = EunomiaPolicyGate()
            decision = gate.check("read_db:invoices:2026-Q3-004", ("read_db:invoices:*",))

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "matched rule")
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][0].endswith("/admin/policies"))
        self.assertTrue(calls[1][0].endswith("/check"))

    def test_wildcard_scope_becomes_a_startswith_rule(self):
        patcher, calls = self._patched({"allowed": True, "reason": "ok"})
        with patcher:
            gate = EunomiaPolicyGate()
            gate.check("read_db:invoices:x", ("read_db:invoices:*",))

        policy_body = calls[0][1]
        rules = policy_body["rules"]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["resource_conditions"][0]["operator"], "startswith")
        self.assertEqual(rules[0]["resource_conditions"][0]["value"], "read_db:invoices:")

    def test_exact_scope_becomes_equals_and_nested_startswith_rules(self):
        patcher, calls = self._patched({"allowed": True, "reason": "ok"})
        with patcher:
            gate = EunomiaPolicyGate()
            gate.check("swiss_tax_lookup", ("swiss_tax_lookup",))

        rules = calls[0][1]["rules"]
        operators = {r["resource_conditions"][0]["operator"] for r in rules}
        self.assertEqual(operators, {"equals", "startswith"})

    def test_policy_registered_only_once_per_distinct_scope_set(self):
        patcher, calls = self._patched({"allowed": True, "reason": "ok"})
        with patcher:
            gate = EunomiaPolicyGate()
            gate.check("a", ("a", "b"))
            gate.check("b", ("a", "b"))  # same scope-set, second task

        policy_calls = [c for c in calls if c[0].endswith("/admin/policies")]
        self.assertEqual(len(policy_calls), 1)

    def test_no_authorized_scopes_denies_without_a_network_call(self):
        patcher, calls = self._patched({"allowed": True, "reason": "should never be reached"})
        with patcher:
            gate = EunomiaPolicyGate()
            decision = gate.check("anything", ())

        self.assertFalse(decision.allowed)
        self.assertEqual(calls, [])

    def test_already_registered_policy_is_not_a_failure(self):
        def fake_urlopen(request, timeout=10.0):
            if request.full_url.endswith("/admin/policies"):
                raise urllib.error.HTTPError(
                    request.full_url, 409, "already exists", None, io.BytesIO(b"already exists")
                )
            return _FakeResponse({"allowed": True, "reason": "ok"})

        with patch("eval.policy.urllib.request.urlopen", fake_urlopen):
            gate = EunomiaPolicyGate()
            decision = gate.check("x", ("x",))

        self.assertTrue(decision.allowed)


if __name__ == "__main__":
    unittest.main()
