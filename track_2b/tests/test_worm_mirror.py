import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.ledger import Event  # noqa: E402
from eval.ledger import Ledger  # noqa: E402

import json  # noqa: E402
import sqlite3  # noqa: E402


class TestWormMirror(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.ledger = Ledger(self.tmp_dir / "test.db")

    def tearDown(self):
        self.ledger.close()

    def test_verify_against_worm_passes_on_untouched_run(self):
        self.ledger.append("r1", "T1", "PromptReceived", {"x": 1})
        self.ledger.append("r1", "T1", "ModelOutput", {"x": 2})
        matches, mismatch = self.ledger.verify_against_worm("r1")
        self.assertTrue(matches)
        self.assertIsNone(mismatch)

    def test_verify_against_worm_catches_sophisticated_tamper_that_fools_verify_chain(self):
        """The real point of ADR-006: an attacker who rewrites a row AND
        recomputes every downstream hash consistently fools verify_chain()
        alone, but still can't match the independent WORM mirror."""
        self.ledger.append("r1", "T1", "PromptReceived", {"x": 1})
        ev2 = self.ledger.append("r1", "T1", "PolicyEvaluated", {"decision": "ALLOW"})
        ev3 = self.ledger.append("r1", "T1", "ModelOutput", {"x": 1})

        conn = sqlite3.connect(self.tmp_dir / "test.db")
        forged_ev2 = Event(
            event_id=ev2.event_id, run_id="r1", task_id="T1", event_type="PolicyEvaluated",
            payload={"decision": "DENY"}, parent_hash=ev2.parent_hash,
        )
        conn.execute(
            "UPDATE events SET payload_json=?, payload_hash=? WHERE event_id=?",
            (json.dumps({"decision": "DENY"}, sort_keys=True), forged_ev2.payload_hash, ev2.event_id),
        )
        forged_ev3 = Event(
            event_id=ev3.event_id, run_id="r1", task_id="T1", event_type="ModelOutput",
            payload=ev3.payload, parent_hash=forged_ev2.payload_hash,
        )
        conn.execute(
            "UPDATE events SET parent_hash=?, payload_hash=? WHERE event_id=?",
            (forged_ev3.parent_hash, forged_ev3.payload_hash, ev3.event_id),
        )
        conn.commit()
        conn.close()

        chain_valid, _ = self.ledger.verify_chain("r1")
        self.assertTrue(chain_valid, "sanity check: the forged chain IS internally consistent")

        worm_matches, mismatch_id = self.ledger.verify_against_worm("r1")
        self.assertFalse(worm_matches)
        self.assertEqual(mismatch_id, ev2.event_id)

    def test_mirror_file_contains_every_event(self):
        self.ledger.append("r1", "T1", "PromptReceived", {"x": 1})
        self.ledger.append("r1", "T1", "ModelOutput", {"x": 2})
        mirrored = self.ledger.worm.read_run("r1")
        self.assertEqual(len(mirrored), 2)


if __name__ == "__main__":
    unittest.main()
