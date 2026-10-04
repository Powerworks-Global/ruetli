import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.ledger import Ledger  # noqa: E402


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.ledger = Ledger(self.tmp_dir / "test.db")

    def tearDown(self):
        self.ledger.close()

    def test_append_and_read_back(self):
        self.ledger.append("r1", "T1", "PromptReceived", {"x": 1})
        self.ledger.append("r1", "T1", "ModelOutput", {"x": 2})
        events = self.ledger.events_for_run("r1")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].event_type, "PromptReceived")
        self.assertEqual(events[1].parent_hash, events[0].payload_hash)

    def test_verify_chain_passes_on_untouched_run(self):
        self.ledger.append("r1", "T1", "PromptReceived", {"x": 1})
        self.ledger.append("r1", "T1", "ModelOutput", {"x": 2})
        valid, broken = self.ledger.verify_chain("r1")
        self.assertTrue(valid)
        self.assertIsNone(broken)

    def test_verify_chain_catches_naive_tamper(self):
        self.ledger.append("r1", "T1", "PromptReceived", {"x": 1})
        ev2 = self.ledger.append("r1", "T1", "ModelOutput", {"x": 2})
        self.ledger.tamper("r1", ev2.event_id, {"x": 999})
        valid, broken = self.ledger.verify_chain("r1")
        self.assertFalse(valid)
        self.assertEqual(broken, ev2.event_id)

    def test_separate_runs_do_not_share_chain_state(self):
        self.ledger.append("r1", "T1", "PromptReceived", {"x": 1})
        self.ledger.append("r2", "T2", "PromptReceived", {"x": 1})
        events_r2 = self.ledger.events_for_run("r2")
        self.assertEqual(events_r2[0].parent_hash, "0" * 64)


if __name__ == "__main__":
    unittest.main()
