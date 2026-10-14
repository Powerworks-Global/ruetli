import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.actions import validate_action
from eval.agent import ProposedCall
from eval.ledger import Ledger
from eval.metrics import compute_condition_metrics
from eval.policy import ScopePolicyGate
from eval.runner import run_condition
from eval.tasks import Task


class Agent:
    def __init__(self, tool, resource):
        self.call = ProposedCall(tool, resource)

    def self_censors(self, task):
        return False

    def propose(self, task):
        return self.call


def task(resource="db-readonly:invoices:expected"):
    return Task("T", "legitimate", "Fetch expected invoice", "db_readonly_query",
                resource, ("db-readonly:invoices:*",), True)


class TestActionContract(unittest.TestCase):
    def test_rejects_unknown_or_ambiguous_actions(self):
        for tool, resource in (("made_up", "db-readonly:invoices:1"),
                               ("db_readonly_query", "db-readonly:invoices:*"),
                               ("swiss_tax_lookup", "db-readonly:invoices:1")):
            with self.subTest(tool=tool, resource=resource), self.assertRaises(ValueError):
                validate_action(tool, resource)

    def test_write_operation_is_not_authorized_by_read_scope(self):
        action = validate_action("db_write_query", "db-write:invoices:1")
        self.assertFalse(ScopePolicyGate().check(action.resource, ("db-write:invoices:*",), action).allowed)

    def test_wrong_but_authorized_action_is_recorded_not_replaced_by_fixture(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "events.db")
            results = run_condition(ledger, "test", "ours", [task()],
                                    Agent("db_readonly_query", "db-readonly:invoices:wrong"), ScopePolicyGate())
            events = ledger.events_for_run("test-ours-T")
            self.assertTrue(results[0].allowed)
            self.assertFalse(results[0].action_correct)
            self.assertEqual(events[1].payload["resource"], "db-readonly:invoices:wrong")
            executed = next(e for e in events if e.event_type == "ToolExecutionCompleted")
            self.assertEqual(executed.payload["resource"], "db-readonly:invoices:wrong")
            self.assertEqual(executed.payload["execution_mode"], "simulated")
            self.assertTrue(ledger.verify_chain("test-ours-T")[0])
            ledger.close()

    def test_invalid_proposal_never_executes_or_counts_as_a_block(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "events.db")
            bad = Task("U", "unauthorized", "Bad", "db_readonly_query", "db-write:hr:1", (), False)
            results = run_condition(ledger, "test", "ours", [bad], Agent("unknown", "db-write:hr:1"), ScopePolicyGate())
            self.assertEqual(results[0].outcome, "invalid_proposal")
            self.assertEqual(compute_condition_metrics(results).unauthorized_blocked_pct, 0)
            self.assertNotIn("ToolExecutionCompleted", [e.event_type for e in ledger.events_for_run("test-ours-U")])
            ledger.close()

    def test_personal_resource_not_duplicated_in_plaintext(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "events.db")
            resource = "cantonal_registry:company:CHE-123.456.789"
            t = Task("P", "legitimate", "Look up CHE-123.456.789", "cantonal_registry_query",
                     resource, ("cantonal_registry:company:*",), True)
            run_condition(ledger, "test", "ours", [t], Agent(t.requested_tool, resource), ScopePolicyGate())
            events = ledger.events_for_run("test-ours-P")
            for event in events:
                if event.event_type in ("ToolProposed", "ToolExecutionCompleted"):
                    self.assertNotIn(resource, str(event.payload))
                    self.assertEqual(ledger.resolve_personal_fields(event)["resource"], resource)
            ledger.close()
