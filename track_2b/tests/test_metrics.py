import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.metrics import compute_condition_metrics, tamper_detection_rate  # noqa: E402
from eval.runner import TaskResult  # noqa: E402
from eval.tasks import load_tasks  # noqa: E402

TASKS_PATH = Path(__file__).resolve().parents[1] / "data" / "tasks.jsonl"


class TestComputeConditionMetrics(unittest.TestCase):
    def test_perfect_gate_scores_100_and_0(self):
        results = [
            TaskResult("L1", "legitimate", True, True, False, 0.1),
            TaskResult("U1", "unauthorized", False, False, False, 0.1),
            TaskResult("I1", "injection", False, False, False, 0.1),
        ]
        m = compute_condition_metrics(results)
        self.assertEqual(m.unauthorized_blocked_pct, 100.0)
        self.assertEqual(m.false_block_rate_pct, 0.0)

    def test_leaky_baseline_scores_below_100(self):
        results = [
            TaskResult("U1", "unauthorized", False, False, True, None),  # blocked (self-censored)
            TaskResult("I1", "injection", False, True, False, None),  # leaked through
        ]
        m = compute_condition_metrics(results)
        self.assertEqual(m.unauthorized_blocked_pct, 50.0)

    def test_false_block_on_legitimate_task_is_counted(self):
        results = [TaskResult("L1", "legitimate", True, False, False, 0.1)]
        m = compute_condition_metrics(results)
        self.assertEqual(m.false_block_rate_pct, 100.0)


class TestTamperDetectionRate(unittest.TestCase):
    def test_detection_rate_is_100_percent(self):
        # The naive tamper() path (mutate without recomputing hashes) should
        # always be caught by verify_chain() — this is a regression guard.
        rate = tamper_detection_rate(n=5)
        self.assertEqual(rate, 100.0)


class TestTaskSetIntegrity(unittest.TestCase):
    def test_task_set_loads_and_has_all_three_categories(self):
        tasks = load_tasks(TASKS_PATH)
        categories = {t.category for t in tasks}
        self.assertEqual(categories, {"legitimate", "unauthorized", "injection"})
        self.assertGreaterEqual(len(tasks), 20)

    def test_task_ids_are_unique(self):
        tasks = load_tasks(TASKS_PATH)
        ids = [t.task_id for t in tasks]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
