"""Event-sourced agent ledger: append-only, hash-chained event store.

Each event's hash covers its own payload plus the previous event's hash,
so mutating any stored event breaks every hash after it in that run —
this is what Section 5's "tamper detection" metric checks, and what
"replay fidelity" relies on to prove the recorded run wasn't altered.

Personal-data fields (per ADR-005) are encrypted with a per-subject key
*before* the event is hashed, so the hash chain is computed over
ciphertext and never needs to change when a subject is later erased —
see `append(personal_fields=..., subject_id=...)` and `shred()`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from eval.crypto_shredding import ERASED, KeyVault, decrypt_fields, encrypt_fields
from eval.worm_mirror import WormMirror

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class Event:
    event_id: str
    run_id: str
    task_id: str
    event_type: str  # PromptReceived | PolicyEvaluated | ToolProposed | ToolExecuted | ModelOutput
    payload: dict
    parent_hash: str
    payload_hash: str = field(init=False)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        object.__setattr__(self, "payload_hash", self._compute_hash())

    def _compute_hash(self) -> str:
        canonical = json.dumps(
            {
                "event_id": self.event_id,
                "run_id": self.run_id,
                "task_id": self.task_id,
                "event_type": self.event_type,
                "payload": self.payload,
                "parent_hash": self.parent_hash,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


class Ledger:
    """SQLite-backed event store. One `Ledger` instance can hold many runs."""

    def __init__(self, db_path: Path, key_vault: KeyVault | None = None, worm: WormMirror | None = None):
        self.db_path = db_path
        self.key_vault = key_vault or KeyVault(db_path.with_suffix(".keys.db"))
        self.worm = worm or WormMirror(db_path.with_suffix(".worm.jsonl"))
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                parent_hash TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                timestamp REAL NOT NULL,
                seq INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, seq)"
        )
        self._conn.commit()
        self._last_hash_by_run: dict[str, str] = {}

    def _parent_hash(self, run_id: str) -> str:
        if run_id in self._last_hash_by_run:
            return self._last_hash_by_run[run_id]
        row = self._conn.execute(
            "SELECT payload_hash FROM events WHERE run_id = ? ORDER BY seq DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        parent = row[0] if row else GENESIS_HASH
        self._last_hash_by_run[run_id] = parent
        return parent

    def append(
        self,
        run_id: str,
        task_id: str,
        event_type: str,
        payload: dict,
        personal_fields: dict[str, str] | None = None,
        subject_id: str | None = None,
    ) -> Event:
        if personal_fields:
            if not subject_id:
                raise ValueError("personal_fields requires a subject_id")
            key = self.key_vault.get_or_create_key(subject_id)
            payload = {
                **payload,
                "_personal": {
                    "subject_id": subject_id,
                    "ciphertext": encrypt_fields(key, personal_fields),
                },
            }
        parent_hash = self._parent_hash(run_id)
        event = Event(
            event_id=str(uuid.uuid4()),
            run_id=run_id,
            task_id=task_id,
            event_type=event_type,
            payload=payload,
            parent_hash=parent_hash,
        )
        seq_row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM events WHERE run_id = ?", (run_id,)
        ).fetchone()
        seq = seq_row[0]
        self._conn.execute(
            """
            INSERT INTO events
                (event_id, run_id, task_id, event_type, payload_json,
                 parent_hash, payload_hash, timestamp, seq)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.run_id,
                event.task_id,
                event.event_type,
                json.dumps(event.payload, sort_keys=True),
                event.parent_hash,
                event.payload_hash,
                event.timestamp,
                seq,
            ),
        )
        self._conn.commit()
        self._last_hash_by_run[run_id] = event.payload_hash
        self.worm.append_record(
            {
                "event_id": event.event_id,
                "run_id": event.run_id,
                "task_id": event.task_id,
                "event_type": event.event_type,
                "payload": event.payload,
                "parent_hash": event.parent_hash,
                "payload_hash": event.payload_hash,
            }
        )
        return event

    def events_for_run(self, run_id: str) -> list[Event]:
        rows = self._conn.execute(
            """
            SELECT event_id, run_id, task_id, event_type, payload_json,
                   parent_hash, payload_hash, timestamp
            FROM events WHERE run_id = ? ORDER BY seq ASC
            """,
            (run_id,),
        ).fetchall()
        events = []
        for row in rows:
            event_id, run_id_, task_id, event_type, payload_json, parent_hash, stored_hash, ts = row
            payload = json.loads(payload_json)
            ev = Event(
                event_id=event_id,
                run_id=run_id_,
                task_id=task_id,
                event_type=event_type,
                payload=payload,
                parent_hash=parent_hash,
                timestamp=ts,
            )
            events.append(ev)
        return events

    def tamper(self, run_id: str, event_id: str, new_payload: dict) -> None:
        """Mutate a stored event's payload WITHOUT recomputing the hash chain —
        simulates an attacker editing the database directly. Used only by the
        tamper-detection test in metrics.py; never call this in a real run."""
        self._conn.execute(
            "UPDATE events SET payload_json = ? WHERE run_id = ? AND event_id = ?",
            (json.dumps(new_payload, sort_keys=True), run_id, event_id),
        )
        self._conn.commit()

    def verify_chain(self, run_id: str) -> tuple[bool, str | None]:
        """Recompute each event's hash from its stored payload and check it
        matches both the stored payload_hash and the next event's parent_hash.
        Returns (is_valid, first_broken_event_id_or_None)."""
        events = self.events_for_run(run_id)
        expected_parent = GENESIS_HASH
        for ev in events:
            if ev.parent_hash != expected_parent:
                return False, ev.event_id
            recomputed = ev._compute_hash()
            if recomputed != self._stored_hash(run_id, ev.event_id):
                return False, ev.event_id
            expected_parent = recomputed
        return True, None

    def _stored_hash(self, run_id: str, event_id: str) -> str:
        row = self._conn.execute(
            "SELECT payload_hash FROM events WHERE run_id = ? AND event_id = ?",
            (run_id, event_id),
        ).fetchone()
        return row[0]

    def verify_against_worm(self, run_id: str) -> tuple[bool, str | None]:
        """Cross-check the primary ledger against the WORM mirror (ADR-006).
        Catches a sophisticated tamper that rewrites the SQLite file AND
        recomputes every downstream hash consistently — verify_chain() alone
        would not detect that, because the forged chain is internally
        consistent. It still can't match an independent write-once copy.
        Returns (matches, first_mismatched_event_id_or_None)."""
        primary = self.events_for_run(run_id)
        mirrored = self.worm.read_run(run_id)
        if len(primary) != len(mirrored):
            return False, (mirrored[-1]["event_id"] if mirrored else None)
        for ev, record in zip(primary, mirrored):
            if (
                ev.event_id != record["event_id"]
                or ev.payload != record["payload"]
                or ev.parent_hash != record["parent_hash"]
                or self._stored_hash(run_id, ev.event_id) != record["payload_hash"]
            ):
                return False, ev.event_id
        return True, None

    def resolve_personal_fields(self, event: Event) -> dict[str, str] | None:
        """Decrypt an event's personal-data fields, or return each as ERASED
        if the subject's key has been shredded. Returns None if the event
        carries no personal data at all."""
        personal = event.payload.get("_personal")
        if personal is None:
            return None
        key = self.key_vault.get_key(personal["subject_id"])
        if key is None:
            return {name: ERASED for name in personal["ciphertext"]}
        return decrypt_fields(key, personal["ciphertext"])

    def shred(self, subject_id: str) -> bool:
        """GDPR/FADP erasure: destroy a subject's key. Does not touch any
        ledger row — verify_chain() for every run remains valid afterward."""
        return self.key_vault.shred(subject_id)

    def close(self) -> None:
        self._conn.close()
        self.key_vault.close()
