import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.policy import NullPolicyGate, ScopePolicyGate  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
