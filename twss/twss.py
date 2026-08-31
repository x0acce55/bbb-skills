#!/usr/bin/env python3
"""twss — batch approval for a queue of shell commands.

Claude Code PreToolUse hook (matcher: Bash) plus the approve/status/clear CLI.

Fail-closed contract: the hook either prints a permissionDecision JSON for a
byte-exact, user-approved, unconsumed queue line — or prints NOTHING and exits 0,
which Claude Code treats as "no decision" (the normal permission flow applies).
Every error path is silence, never allow.

Layout (ADR-0043). The queue lives at `<root>/.twss-queue.txt`; the approval,
state and log live in `<root>/.claude/`. The split is the point: the queue is the
one file that is *meant* to be agent-authored — it is the proposal the user reads
— while the approval is the consent record. Claude Code refuses agent writes into
any `.claude/` on its own, so keeping the approval there makes the trust boundary
the filesystem rather than a comment.

Honesty clause (ADR-0010 tradition): that gate enforces "only the user runs
approve" for the Edit/Write path, but this script still cannot verify it — a file
does not record its author, and an agent can reach `.claude/` through a
sandbox-disabled Bash call (ADR-0044). A strong guardrail against accident; not a
security boundary.

Silence is the designed decline, which makes a broken twss and a declining twss
look identical from outside — the expensive failure in ADR-0038. Every decline
therefore names its branch in the log while still printing nothing.

Cross-platform: stdlib only; run with python3 (macOS/Linux) or python (Windows).
"""

import hashlib
import json
import os
import re
import shlex
import shutil
import sys
import time
from pathlib import Path

TTL_SECONDS = int(os.environ.get("TWSS_TTL_SECONDS", "1800"))  # default 30 min


def resolve_root():
    """Where twss keeps its state, and which variable decided it.

    TWSS_ROOT is explicit and wins: `bbb` exports it at launch so the hook and
    the user's `!` shell provably agree instead of agreeing by coincidence.
    CLAUDE_PROJECT_DIR is next — Claude Code injects it into hook processes, but
    NOT into `!` shells, so it alone cannot keep the two halves in step. cwd is
    the last resort.

    BBB_VAULT_ROOT is deliberately absent (ADR-0043). `bbb` exports it into the
    session and then cd's into a domain, so honouring it made `approve` write to
    the vault root while the hook read the domain — an approval and a decision
    pointing at different directories, with silence as the only symptom.
    """
    for var in ("TWSS_ROOT", "CLAUDE_PROJECT_DIR"):
        v = os.environ.get(var)
        if v:
            return Path(v), var
    return Path.cwd(), "cwd"


ROOT, ROOT_SOURCE = resolve_root()
CLAUDE_DIR = ROOT / ".claude"
QUEUE = ROOT / ".twss-queue.txt"
LEGACY_QUEUE = CLAUDE_DIR / "twss-queue.txt"  # pre-ADR-0043; reported, never moved
APPROVED = CLAUDE_DIR / "twss-approved.json"
STATE = CLAUDE_DIR / "twss-state.json"
LOG = CLAUDE_DIR / "twss-log.txt"

# A queue may opt into commands that run with Claude Code's sandbox disabled.
# The directive is a comment line, so it is inside the hashed bytes and the user
# reads it in the approve listing — which is the whole point (ADR-0044): the
# escape becomes something consented to, not something the allow quietly covers.
SANDBOX_OPT_IN = re.compile(r"^\s*#\s*twss:\s*allow-sandbox-escape\b", re.I | re.M)


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


def decline(reason):
    """A decline: name the branch in the log, print nothing.

    Reached only once a queue exists, so an unarmed project stays quiet instead
    of logging a line per Bash call. Consecutive identical declines collapse to
    one — a stale queue sitting unapproved would otherwise write a line per Bash
    call and bury the log this exists to make readable. Returns None so callers
    can `return decline(...)` and keep the silent contract plain at the call site.
    """
    msg = f"DECLINE {reason}"
    try:
        with open(LOG, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 4096))
            tail = f.read().decode("utf-8", "replace").splitlines()
        if tail and tail[-1].split(" ", 1)[-1] == msg:
            return None
    except Exception:
        pass  # never let bookkeeping affect a decision path
    log(msg)
    return None


def banner():
    """Every CLI command opens by saying which root it resolved, and why.

    A split brain — `approve` writing one directory while the hook reads another
    — used to be invisible, and silence is the only other symptom. Now it is line
    one of any twss command.
    """
    print(f"twss: root {ROOT} (from {ROOT_SOURCE})")
    if LEGACY_QUEUE.exists():
        print(f"twss: legacy queue at {LEGACY_QUEUE} is ignored (ADR-0043).")
        print(f"      move it yourself:  mv {LEGACY_QUEUE} {QUEUE}")


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
        tool_input = data.get("tool_input") or {}
        cmd = tool_input.get("command")
        if not isinstance(cmd, str):
            return
        try:
            qbytes = QUEUE.read_bytes()
        except FileNotFoundError:
            return  # unarmed: the ordinary case, and it stays quiet
        qhash = queue_hash(qbytes)
        qtext = qbytes.decode("utf-8")
        # An approval covers the command text the user read. Running that text
        # with the sandbox disabled is a larger act than the queue describes, so
        # it needs its own consent: either the queue opts in where the user can
        # see it, or the escape costs its own prompt (ADR-0044).
        if tool_input.get("dangerouslyDisableSandbox") and not SANDBOX_OPT_IN.search(qtext):
            return decline(f"sandbox-escape (queue has no allow-sandbox-escape) {qhash[:12]} {cmd}")
        try:
            appr = json.loads(APPROVED.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return decline(f"no-approval {qhash[:12]}")
        if appr.get("hash") != qhash:
            return decline(
                f"hash-void queue {qhash[:12]} != approved {str(appr.get('hash'))[:12]} "
                "(queue changed since approval)")
        age = time.time() - float(appr.get("approved_at", 0))
        if age < 0 or age > TTL_SECONDS:
            return decline(f"ttl-expired {int(age)}s old, ttl {TTL_SECONDS}s {qhash[:12]}")
        reason = denied(cmd)
        if reason:
            log(f"REFUSED-DENYLIST ({reason}) {qhash[:12]} {cmd}")
            return
        state = load_state()
        consumed = set(state.get(qhash, []))
        target = cmd.rstrip("\r\n")
        seen_consumed = None
        for i, l in real_lines(qtext):
            if l != target:
                continue
            if i in consumed:
                seen_consumed = i + 1  # a duplicate line may still be runnable
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
        # Silence either way — but say which, because an approval is live here
        # and the difference between "you already ran it" and "your command text
        # drifted from the queue" is the whole diagnosis.
        if seen_consumed is not None:
            return decline(f"consumed line {seen_consumed} {qhash[:12]} {target}")
        return decline(f"no-match {qhash[:12]} {target}")
    except Exception:
        return  # fail closed


def cmd_approve():
    banner()
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
    if SANDBOX_OPT_IN.search(qbytes.decode("utf-8")):
        print("  !! this queue carries `# twss: allow-sandbox-escape` — approved lines")
        print("     may run with Claude Code's sandbox DISABLED (network and writes")
        print("     outside the workspace). Remove that line to withhold it.\n")
    else:
        print()
    if blocked:
        print("twss: REFUSED — denylisted line(s): "
              + ", ".join(f"line {n} ({r})" for n, r in blocked))
        sys.exit(2)
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    APPROVED.write_text(
        json.dumps({"hash": qhash, "approved_at": time.time()}), encoding="utf-8")
    STATE.write_text(json.dumps({qhash: []}), encoding="utf-8")
    log(f"APPROVED {qhash[:12]} ({len(lines)} commands, ttl {TTL_SECONDS}s)")
    print(f"twss: approved {len(lines)} command(s), queue {qhash[:12]}, "
          f"valid {TTL_SECONDS // 60} min. Each line runs at most once.")


def hook_health():
    """Is a twss hook registered for this root, and can its interpreter start?

    ADR-0038: presence is not health. The registration that cost two sessions was
    present and correct-looking, and could not run — so report both facts, and
    report "not registered here" loudly, since that is indistinguishable from a
    decline at the point where the user notices.
    """
    found = []
    for name in ("settings.json", "settings.local.json"):
        try:
            cfg = json.loads((CLAUDE_DIR / name).read_text(encoding="utf-8"))
        except Exception:
            continue
        for entry in (cfg.get("hooks", {}) or {}).get("PreToolUse", []) or []:
            for h in entry.get("hooks", []) or []:
                if "twss" in h.get("command", ""):
                    found.append((name, h["command"]))
    if not found:
        print(f"  hook: NOT registered in {CLAUDE_DIR} — nothing can be allowed here")
        return
    for name, command in found:
        try:
            parts = shlex.split(command, posix=(os.name != "nt"))
        except ValueError:
            parts = command.split()
        exe = parts[0].strip('"') if parts else ""
        ok = bool(shutil.which(exe) or (exe and Path(exe).exists()))
        print(f"  hook: registered in {name}, interpreter {exe} "
              f"{'ok' if ok else 'NOT FOUND — the hook cannot start (ADR-0038)'}")


def cmd_status():
    banner()
    hook_health()
    if not QUEUE.exists():
        print(f"twss: no queue file at {QUEUE}")
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
    banner()
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
