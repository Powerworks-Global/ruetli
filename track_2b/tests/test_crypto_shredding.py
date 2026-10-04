import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eval.crypto_shredding import ERASED  # noqa: E402
from eval.ledger import Ledger  # noqa: E402


class TestCryptoShredding(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.ledger = Ledger(self.tmp_dir / "test.db")

    def tearDown(self):
        self.ledger.close()

    def test_personal_fields_decrypt_before_shredding(self):
        self.ledger.append(
            "r1", "T1", "PromptReceived", {"tool": "x"},
            personal_fields={"company_name": "Acme Sarl"},
            subject_id="CHE-123.456.789",
        )
        ev = self.ledger.events_for_run("r1")[0]
        resolved = self.ledger.resolve_personal_fields(ev)
        self.assertEqual(resolved, {"company_name": "Acme Sarl"})

    def test_shred_makes_field_unreadable_without_touching_ledger(self):
        self.ledger.append(
            "r1", "T1", "PromptReceived", {"tool": "x"},
            personal_fields={"company_name": "Acme Sarl"},
            subject_id="CHE-123.456.789",
        )
        valid_before, _ = self.ledger.verify_chain("r1")

        deleted = self.ledger.shred("CHE-123.456.789")
        self.assertTrue(deleted)

        ev = self.ledger.events_for_run("r1")[0]
        resolved = self.ledger.resolve_personal_fields(ev)
        self.assertEqual(resolved, {"company_name": ERASED})

        valid_after, broken = self.ledger.verify_chain("r1")
        self.assertEqual(valid_before, valid_after)
        self.assertTrue(valid_after)
        self.assertIsNone(broken)

    def test_shredding_one_subject_does_not_affect_another(self):
        self.ledger.append(
            "r1", "T1", "PromptReceived", {"tool": "x"},
            personal_fields={"name": "Subject A"}, subject_id="SUBJ-A",
        )
        self.ledger.append(
            "r1", "T1", "PromptReceived", {"tool": "x"},
            personal_fields={"name": "Subject B"}, subject_id="SUBJ-B",
        )
        self.ledger.shred("SUBJ-A")
        events = self.ledger.events_for_run("r1")
        self.assertEqual(self.ledger.resolve_personal_fields(events[0]), {"name": ERASED})
        self.assertEqual(self.ledger.resolve_personal_fields(events[1]), {"name": "Subject B"})

    def test_personal_fields_requires_subject_id(self):
        with self.assertRaises(ValueError):
            self.ledger.append("r1", "T1", "PromptReceived", {}, personal_fields={"x": "y"})

    def test_event_without_personal_fields_resolves_to_none(self):
        self.ledger.append("r1", "T1", "PromptReceived", {"tool": "x"})
        ev = self.ledger.events_for_run("r1")[0]
        self.assertIsNone(self.ledger.resolve_personal_fields(ev))


if __name__ == "__main__":
    unittest.main()
