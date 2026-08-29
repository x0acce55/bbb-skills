#!/usr/bin/env python3
"""twss — batch approval for a queue of shell commands.

Claude Code PreToolUse hook (matcher: Bash) plus the approve/status/clear CLI.

Fail-closed contract: the hook either prints a permissionDecision JSON for a
byte-exact, user-approved, unconsumed queue line — or prints NOTHING and exits 0,
which Claude Code treats as "no decision" (the normal permission flow applies).
Every error path is silence, never allow.

Honesty clause (ADR-0010 tradition): the "only the user runs approve" rule is a
convention plus an audit log, not something this script can enforce — a file does
not record its author. This is a guardrail against accident, not a security
boundary.

Cross-platform: stdlib only; run with python3 (macOS/Linux) or python (Windows).
"""

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

TTL_SECONDS = int(os.environ.get("TWSS_TTL_SECONDS", "1800"))  # default 30 min


def root() -> Path:
    for var in ("CLAUDE_PROJECT_DIR", "BBB_VAULT_ROOT"):
        v = os.environ.get(var)
        if v:
            return Path(v)
    return Path.cwd()


CLAUDE_DIR = root() / ".claude"
QUEUE = CLAUDE_DIR / "twss-queue.txt"
APPROVED = CLAUDE_DIR / "twss-approved.json"
STATE = CLAUDE_DIR / "twss-state.json"
LOG = CLAUDE_DIR / "twss-log.txt"


def denied(cmd):
    """Hardcoded backstop, not a general safety filter. Checked at approve time
    AND at hook time, so a queue can never smuggle these past a stale review."""
    if re.search(r"(^|\s)sudo\s", cmd):
        return "sudo"
    if re.search(r"rm\s+(-[a-zA-Z]+\s+)*-[a-zA-Z]*r[a-zA-Z]*\s+(--\S+\s+)*/(\*|\s|$)", cmd):
        return "recursive delete of /"
    if re.search(r"\b(curl|wget)\b[^|]*\|\s*\S*sh\b", cmd):
        return "network pipe-to-shell"
    return None


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {msg}\n")
    except Exception:
        pass  # logging must never break a decision path


def queue_hash(qbytes):
    return hashlib.sha256(qbytes).hexdigest()


def real_lines(qtext):
    """(index, line) for every non-blank, non-comment line. Index is the physical
    line position; any byte change to the file voids the approval before indices
    could ever drift."""
    out = []
    for i, line in enumerate(qtext.splitlines()):
        l = line.rstrip("\r")
        if not l.strip() or l.lstrip().startswith("#"):
            continue
        out.append((i, l))
    return out


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def cmd_hook():
    try:
        data = json.load(sys.stdin)
        if data.get("tool_name") != "Bash":
            return
        cmd = data.get("tool_input", {}).get("command")
        if not isinstance(cmd, str):
            return
        qbytes = QUEUE.read_bytes()
        qhash = queue_hash(qbytes)
        appr = json.loads(APPROVED.read_text(encoding="utf-8"))
        if appr.get("hash") != qhash:
            return  # queue changed since approval — void
        age = time.time() - float(appr.get("approved_at", 0))
        if age < 0 or age > TTL_SECONDS:
            return  # expired (or clock skew — treat as expired)
        reason = denied(cmd)
        if reason:
            log(f"REFUSED-DENYLIST ({reason}) {qhash[:12]} {cmd}")
            return
        state = load_state()
        consumed = set(state.get(qhash, []))
        target = cmd.rstrip("\r\n")
        for i, l in real_lines(qbytes.decode("utf-8")):
            if i in consumed or l != target:
                continue
            consumed.add(i)
            STATE.write_text(json.dumps({qhash: sorted(consumed)}), encoding="utf-8")
            log(f"ALLOW line {i + 1} {qhash[:12]} {l}")
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": (
                        f"twss: line {i + 1} of approved queue {qhash[:12]} "
                        f"(approved {time.strftime('%H:%M:%S', time.localtime(float(appr['approved_at'])))}, "
                        f"ttl {TTL_SECONDS}s)"
                    ),
                }
            }))
            return
        # No match / already consumed: silence = no decision.
    except Exception:
        return  # fail closed


def cmd_approve():
    if not QUEUE.exists():
        print(f"twss: no queue file at {QUEUE}")
        sys.exit(1)
    qbytes = QUEUE.read_bytes()
    qhash = queue_hash(qbytes)
    lines = real_lines(qbytes.decode("utf-8"))
    if not lines:
        print("twss: queue is empty — nothing to approve")
        sys.exit(1)
    print(f"twss: approving queue {qhash[:12]} — read this list; it is exactly what will run:\n")
    blocked = []
    for i, l in lines:
        reason = denied(l)
        flag = f"   << BLOCKED ({reason})" if reason else ""
        print(f"  {i + 1:3d}  {l}{flag}")
        if reason:
            blocked.append((i + 1, reason))
    print()
    if blocked:
        print("twss: REFUSED — denylisted line(s): "
              + ", ".join(f"line {n} ({r})" for n, r in blocked))
        sys.exit(2)
    APPROVED.write_text(
        json.dumps({"hash": qhash, "approved_at": time.time()}), encoding="utf-8")
    STATE.write_text(json.dumps({qhash: []}), encoding="utf-8")
    log(f"APPROVED {qhash[:12]} ({len(lines)} commands, ttl {TTL_SECONDS}s)")
    print(f"twss: approved {len(lines)} command(s), queue {qhash[:12]}, "
          f"valid {TTL_SECONDS // 60} min. Each line runs at most once.")


def cmd_status():
    if not QUEUE.exists():
        print("twss: no queue file")
        return
    qbytes = QUEUE.read_bytes()
    qhash = queue_hash(qbytes)
    lines = real_lines(qbytes.decode("utf-8"))
    print(f"twss: queue {qhash[:12]}, {len(lines)} command(s)")
    consumed = set()
    try:
        appr = json.loads(APPROVED.read_text(encoding="utf-8"))
        age = time.time() - float(appr.get("approved_at", 0))
        if appr.get("hash") != qhash:
            print("  approval: VOID (queue changed since approval)")
        elif age > TTL_SECONDS:
            print(f"  approval: EXPIRED ({int(age)}s old, ttl {TTL_SECONDS}s)")
        else:
            print(f"  approval: ACTIVE ({int(TTL_SECONDS - age)}s remaining)")
            consumed = set(load_state().get(qhash, []))
    except FileNotFoundError:
        print("  approval: none")
    for i, l in lines:
        mark = "done" if i in consumed else "    "
        print(f"  [{mark}] {i + 1:3d}  {l}")


def cmd_clear():
    for p in (APPROVED, STATE, QUEUE):
        try:
            p.unlink()
            print(f"twss: removed {p.name}")
        except FileNotFoundError:
            pass
    log("CLEARED")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "hook":
        cmd_hook()
    elif mode == "approve":
        cmd_approve()
    elif mode == "status":
        cmd_status()
    elif mode == "clear":
        cmd_clear()
    else:
        print("usage: twss.py hook|approve|status|clear")
        sys.exit(64)


if __name__ == "__main__":
    main()
