import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.ledger import Ledger  # noqa: E402
from eval.reflection import (  # noqa: E402
    BatchRecord,
    EVENT_TYPE,
    collect_batch,
    find_false_block_drift,
    find_latency_outliers,
    find_leak_patterns,
    format_report,
    generate_reflection,
)
from eval.tasks import Task  # noqa: E402


def make_task(task_id, category, tool="read_db", should_allow=True):
    return Task(
        task_id=task_id,
        category=category,
        prompt=f"prompt for {task_id}",
        requested_tool=tool,
        requested_resource=f"resource-{task_id}",
        authorized_scopes=("read_db:*",),
        should_allow=should_allow,
    )


class TestCollectBatch(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.ledger = Ledger(self.tmp_dir / "test.db")

    def tearDown(self):
        self.ledger.close()

    def test_joins_policy_event_with_task_metadata(self):
        task = make_task("T1", "legitimate")
        run_id = "batch-ours-T1"
        self.ledger.append(run_id, "T1", "PromptReceived", {})
        self.ledger.append(run_id, "T1", "PolicyEvaluated", {"decision": "ALLOW", "gate_latency_ms": 0.5})

        records = collect_batch(self.ledger, "batch", "ours", [task])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].decision, "ALLOW")
        self.assertEqual(records[0].category, "legitimate")
        self.assertEqual(records[0].gate_latency_ms, 0.5)

    def test_skips_tasks_with_no_recorded_run(self):
        task = make_task("T1", "legitimate")
        records = collect_batch(self.ledger, "batch", "ours", [task])
        self.assertEqual(records, [])


class TestFindLeakPatterns(unittest.TestCase):
    def test_flags_repeated_leak_on_same_tool_as_warning(self):
        records = [
            BatchRecord("r1", "U1", "ours", "unauthorized", "delete_db", False, "ALLOW", 0.1),
            BatchRecord("r2", "U2", "ours", "unauthorized", "delete_db", False, "ALLOW", 0.1),
        ]
        findings = find_leak_patterns(records)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "warning")
        self.assertIn("delete_db", findings[0].summary)

    def test_single_leak_under_ours_is_only_info(self):
        records = [BatchRecord("r1", "U1", "ours", "injection", "delete_db", False, "ALLOW", 0.1)]
        findings = find_leak_patterns(records)
        self.assertEqual(findings[0].severity, "info")

    def test_baseline_leaks_are_not_actionable(self):
        records = [
            BatchRecord("r1", "U1", "baseline", "unauthorized", "delete_db", False, "ALLOW", None),
            BatchRecord("r2", "U2", "baseline", "unauthorized", "delete_db", False, "ALLOW", None),
        ]
        findings = find_leak_patterns(records)
        self.assertEqual(findings[0].severity, "info")
        self.assertIn("not actionable", findings[0].suggestion)

    def test_legitimate_category_never_counts_as_a_leak(self):
        records = [BatchRecord("r1", "L1", "ours", "legitimate", "read_db", True, "ALLOW", 0.1)]
        self.assertEqual(find_leak_patterns(records), [])

    def test_denied_unauthorized_task_is_not_a_leak(self):
        records = [BatchRecord("r1", "U1", "ours", "unauthorized", "delete_db", False, "DENY", 0.1)]
        self.assertEqual(find_leak_patterns(records), [])


class TestFindFalseBlockDrift(unittest.TestCase):
    def test_no_prior_state_means_no_finding(self):
        self.assertEqual(find_false_block_drift(10.0, None), [])

    def test_improvement_is_not_flagged(self):
        self.assertEqual(find_false_block_drift(5.0, 10.0), [])

    def test_increase_is_flagged(self):
        findings = find_false_block_drift(20.0, 5.0)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "false-block-drift")

    def test_nan_current_value_does_not_crash(self):
        self.assertEqual(find_false_block_drift(float("nan"), 5.0), [])


class TestFindLatencyOutliers(unittest.TestCase):
    def test_too_few_samples_returns_nothing(self):
        records = [BatchRecord("r1", "T1", "ours", "legitimate", "t", True, "ALLOW", 1.0)]
        self.assertEqual(find_latency_outliers(records), [])

    def test_flags_a_clear_outlier(self):
        records = [
            BatchRecord(f"r{i}", f"T{i}", "ours", "legitimate", "t", True, "ALLOW", 1.0) for i in range(5)
        ] + [BatchRecord("r-outlier", "T-outlier", "ours", "legitimate", "t", True, "ALLOW", 100.0)]
        findings = find_latency_outliers(records)
        self.assertEqual(len(findings), 1)
        self.assertIn("r-outlier", findings[0].evidence_run_ids)

    def test_uniform_latencies_flag_nothing(self):
        records = [
            BatchRecord(f"r{i}", f"T{i}", "ours", "legitimate", "t", True, "ALLOW", 1.0) for i in range(5)
        ]
        self.assertEqual(find_latency_outliers(records), [])


class TestGenerateReflection(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.ledger = Ledger(self.tmp_dir / "test.db")
        self.state_path = self.tmp_dir / "reflection_state.json"

    def tearDown(self):
        self.ledger.close()

    def test_appends_a_reflection_generated_event_and_persists_state(self):
        task = make_task("T1", "legitimate")
        self.ledger.append("batch-ours-T1", "T1", "PromptReceived", {})
        self.ledger.append("batch-ours-T1", "T1", "PolicyEvaluated", {"decision": "ALLOW", "gate_latency_ms": 0.2})

        reflection_run_id, findings = generate_reflection(self.ledger, "batch", [task], self.state_path)

        events = self.ledger.events_for_run(reflection_run_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, EVENT_TYPE)
        self.assertTrue(self.state_path.exists())
        chain_ok, _ = self.ledger.verify_chain(reflection_run_id)
        self.assertTrue(chain_ok)

    def test_second_pass_sees_drift_from_first_passs_state(self):
        legit = make_task("L1", "legitimate")
        self.ledger.append("batch-ours-L1", "L1", "PromptReceived", {})
        self.ledger.append("batch-ours-L1", "L1", "PolicyEvaluated", {"decision": "ALLOW", "gate_latency_ms": 0.1})
        generate_reflection(self.ledger, "batch", [legit], self.state_path)

        # Second batch: the same legitimate task now gets falsely denied.
        self.ledger.append("batch2-ours-L1", "L1", "PolicyEvaluated", {"decision": "DENY", "gate_latency_ms": 0.1})
        _, findings = generate_reflection(self.ledger, "batch2", [legit], self.state_path)

        drift_findings = [f for f in findings if f.category == "false-block-drift"]
        self.assertEqual(len(drift_findings), 1)

    def test_format_report_handles_no_findings(self):
        self.assertIn("No findings", format_report([]))


if __name__ == "__main__":
    unittest.main()
