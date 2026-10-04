"""Time-travel replay: scrub forward/backward through a recorded run,
showing each event and the ledger's own tamper/erasure state for it.
"""

from __future__ import annotations

from eval.ledger import Ledger


def print_timeline(ledger: Ledger, run_id: str) -> None:
    chain_ok, broken_at = ledger.verify_chain(run_id)
    worm_ok, worm_broken_at = ledger.verify_against_worm(run_id)

    print(f"Run: {run_id}")
    print(f"  Hash chain valid:       {chain_ok}" + (f"  (broken at {broken_at})" if not chain_ok else ""))
    print(f"  Matches WORM mirror:    {worm_ok}" + (f"  (mismatch at {worm_broken_at})" if not worm_ok else ""))
    print(f"  WORM append-only (chattr +a enforced): {ledger.worm.immutable_enforced}")
    print()

    for i, ev in enumerate(ledger.events_for_run(run_id)):
        personal = ledger.resolve_personal_fields(ev)
        print(f"[{i}] {ev.event_type}  (task={ev.task_id})")
        print(f"    payload: {ev.payload}")
        if personal is not None:
            print(f"    personal fields (decrypted): {personal}")
        print(f"    hash: {ev.payload_hash[:12]}...  parent: {ev.parent_hash[:12]}...")
        print()
