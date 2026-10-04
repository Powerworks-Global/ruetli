"""Per-subject key vault for crypto-shredding (ADR-005).

Deliberately separate from the hash-chained ledger table in ledger.py:
this table is MUTABLE by design — deleting a row here is how a GDPR/FADP
erasure request is honored, without ever touching a hashed ledger event.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

ERASED = "ERASED"


class KeyVault:
    def __init__(self, db_path: Path):
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subject_keys (
                subject_id TEXT PRIMARY KEY,
                key_b64 TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def get_or_create_key(self, subject_id: str) -> bytes:
        row = self._conn.execute(
            "SELECT key_b64 FROM subject_keys WHERE subject_id = ?", (subject_id,)
        ).fetchone()
        if row:
            return row[0].encode()
        key = Fernet.generate_key()
        self._conn.execute(
            "INSERT INTO subject_keys (subject_id, key_b64, created_at) VALUES (?, ?, ?)",
            (subject_id, key.decode(), time.time()),
        )
        self._conn.commit()
        return key

    def get_key(self, subject_id: str) -> bytes | None:
        row = self._conn.execute(
            "SELECT key_b64 FROM subject_keys WHERE subject_id = ?", (subject_id,)
        ).fetchone()
        return row[0].encode() if row else None

    def shred(self, subject_id: str) -> bool:
        """Destroy a subject's key. Every ciphertext in the ledger referencing
        this subject_id becomes permanently undecryptable from this point on.
        Returns True if a key existed and was deleted."""
        cur = self._conn.execute("DELETE FROM subject_keys WHERE subject_id = ?", (subject_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        self._conn.close()


def encrypt_fields(key: bytes, fields: dict[str, str]) -> dict[str, str]:
    f = Fernet(key)
    return {name: f.encrypt(value.encode()).decode() for name, value in fields.items()}


def decrypt_fields(key: bytes, ciphertext: dict[str, str]) -> dict[str, str]:
    f = Fernet(key)
    out = {}
    for name, token in ciphertext.items():
        try:
            out[name] = f.decrypt(token.encode()).decode()
        except InvalidToken:
            out[name] = ERASED
    return out
