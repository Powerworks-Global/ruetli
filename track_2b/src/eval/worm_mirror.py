"""Local append-only WORM mirror (ADR-006, Option A).

A sidecar JSONL copy of every ledger event, written to a file with the
Linux append-only attribute (`chattr +a`) set where the host supports it.
That attribute is kernel-enforced: once set, the file can be opened for
appending but not truncated, edited in place, or deleted, without a
separate privileged `chattr -a` first — a privilege the ledger process
itself never requests. This defeats a compromised *ledger process*
rewriting history consistently; it does not defeat a compromised root/host
(see ADR-006's honesty note on what "hackproof" actually means here).

Where `chattr` isn't available (non-Linux, non-ext filesystem, this
sandboxed dev environment), the mirror still writes — it just can't make
the stronger claim, and `immutable_enforced` tells the caller which case
it's in rather than pretending the guarantee holds everywhere.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


class WormMirror:
    def __init__(self, path: Path):
        self.path = path
        if not path.exists():
            path.touch()
        self.immutable_enforced = self._try_set_append_only()

    def _try_set_append_only(self) -> bool:
        try:
            result = subprocess.run(
                ["chattr", "+a", str(self.path)],
                capture_output=True,
                timeout=2,
            )
            return result.returncode == 0
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return False

    def append_record(self, record: dict) -> None:
        with open(self.path, "a") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]

    def read_run(self, run_id: str) -> list[dict]:
        return [r for r in self.read_all() if r["run_id"] == run_id]
