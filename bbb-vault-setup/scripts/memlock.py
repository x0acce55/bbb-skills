#!/usr/bin/env python3
"""Advisory lock over the BBB vault's shared files, held during distillation.

This lock is advisory and cannot provide true mutual exclusion across machines that
reach the vault through a sync layer -- the lockfile is subject to the same propagation
delay as the files it protects. See references/memory-protocol.md. It narrows the race
and leaves an attributable record; it does not close the race.

Usage:
    python memlock.py <vault> status
    python memlock.py <vault> acquire  --machine <id> [--operation distill] [--ttl 900]
    python memlock.py <vault> heartbeat --machine <id>
    python memlock.py <vault> release   --machine <id>
    python memlock.py <vault> break --force

Exit codes:
    0  success
    1  usage or filesystem error
    3  lock is held by another machine
"""

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LOCK_NAME = ".lock.json"
DEFAULT_TTL = 900          # 15 minutes
CONFIRM_DELAY = 3.0        # seconds to wait before confirming we still hold it


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        return None


def lock_path(vault: Path) -> Path:
    return vault / "memories" / LOCK_NAME


def read_lock(vault: Path):
    path = lock_path(vault)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt lock is worse than none: report it as held by "unknown" so a
        # human decides, rather than silently steamrolling it.
        return {"machine": "unknown", "corrupt": True}


def is_stale(lock) -> bool:
    if lock.get("corrupt"):
        return False
    beat = parse_iso(lock.get("heartbeat") or lock.get("acquired"))
    if beat is None:
        return True
    ttl = int(lock.get("ttl_seconds", DEFAULT_TTL))
    return (now() - beat).total_seconds() > ttl


def describe(lock) -> str:
    if lock.get("corrupt"):
        return "lock file is present but unreadable"
    age = ""
    beat = parse_iso(lock.get("heartbeat") or lock.get("acquired"))
    if beat:
        age = f", last heartbeat {int((now() - beat).total_seconds())}s ago"
    return (
        f"held by {lock.get('machine', '?')} "
        f"(pid {lock.get('pid', '?')}, {lock.get('operation', 'unspecified')})"
        f"{age}"
    )


def write_lock(vault: Path, machine: str, operation: str, ttl: int):
    path = lock_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "machine": machine,
        "host": platform.node(),
        "pid": os.getpid(),
        "operation": operation,
        "acquired": iso(now()),
        "heartbeat": iso(now()),
        "ttl_seconds": ttl,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def cmd_status(vault: Path, args) -> int:
    lock = read_lock(vault)
    if lock is None:
        print("unlocked")
        return 0
    state = "STALE" if is_stale(lock) else "held"
    print(f"{state}: {describe(lock)}")
    return 0


def cmd_acquire(vault: Path, args) -> int:
    existing = read_lock(vault)

    if existing is not None:
        if existing.get("machine") == args.machine and not existing.get("corrupt"):
            write_lock(vault, args.machine, args.operation, args.ttl)
            print(f"re-acquired (already held by {args.machine})")
            return 0
        if is_stale(existing):
            print(f"reclaiming stale lock: {describe(existing)}", file=sys.stderr)
        else:
            print(f"REFUSED: {describe(existing)}", file=sys.stderr)
            print(
                "Wait for it to be released, or run 'break --force' if you are "
                "certain that session is gone.",
                file=sys.stderr,
            )
            return 3

    write_lock(vault, args.machine, args.operation, args.ttl)

    # Confirm we still hold it. If another machine acquired at the same moment and
    # the writes crossed in sync, one of us will lose here rather than both
    # proceeding. This narrows the window; it does not close it.
    if args.confirm_after > 0:
        time.sleep(args.confirm_after)
        current = read_lock(vault)
        if current is None or current.get("machine") != args.machine:
            holder = describe(current) if current else "lock vanished"
            print(f"REFUSED after confirmation: {holder}", file=sys.stderr)
            return 3

    print(f"acquired by {args.machine} for {args.operation} (ttl {args.ttl}s)")
    return 0


def cmd_heartbeat(vault: Path, args) -> int:
    lock = read_lock(vault)
    if lock is None:
        print("no lock to refresh", file=sys.stderr)
        return 1
    if lock.get("machine") != args.machine:
        print(f"REFUSED: {describe(lock)}", file=sys.stderr)
        return 3
    lock["heartbeat"] = iso(now())
    lock_path(vault).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print("heartbeat refreshed")
    return 0


def cmd_release(vault: Path, args) -> int:
    lock = read_lock(vault)
    if lock is None:
        print("already unlocked")
        return 0
    if lock.get("machine") != args.machine and not args.force:
        print(f"REFUSED: {describe(lock)}", file=sys.stderr)
        print("Use 'break --force' to release another machine's lock.", file=sys.stderr)
        return 3
    lock_path(vault).unlink()
    print("released")
    return 0


def cmd_break(vault: Path, args) -> int:
    if not args.force:
        print("break requires --force", file=sys.stderr)
        return 1
    lock = read_lock(vault)
    if lock is None:
        print("already unlocked")
        return 0
    print(f"breaking lock: {describe(lock)}", file=sys.stderr)
    lock_path(vault).unlink()
    print("released")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("vault", type=Path)
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("status")

    p = sub.add_parser("acquire")
    p.add_argument("--machine", required=True)
    p.add_argument("--operation", default="distill")
    p.add_argument("--ttl", type=int, default=DEFAULT_TTL)
    p.add_argument("--confirm-after", type=float, default=CONFIRM_DELAY)

    p = sub.add_parser("heartbeat")
    p.add_argument("--machine", required=True)

    p = sub.add_parser("release")
    p.add_argument("--machine", required=True)
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("break")
    p.add_argument("--force", action="store_true")

    args = ap.parse_args()

    if not args.vault.is_dir():
        print(f"Not a directory: {args.vault}", file=sys.stderr)
        return 1

    return {
        "status": cmd_status,
        "acquire": cmd_acquire,
        "heartbeat": cmd_heartbeat,
        "release": cmd_release,
        "break": cmd_break,
    }[args.command](args.vault, args)


if __name__ == "__main__":
    sys.exit(main())
