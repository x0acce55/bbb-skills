#!/usr/bin/env python3
"""Acceptance tests for twss.py — run: python3 test_twss.py

Each test runs twss.py as a subprocess against a throwaway project root
(CLAUDE_PROJECT_DIR), exactly as Claude Code invokes the hook. No test touches
the real vault.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TWSS = Path(__file__).parent / "twss.py"
PASS, FAIL = 0, 0


def run(mode, root, stdin=None, env_extra=None):
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    env.pop("BBB_VAULT_ROOT", None)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(TWSS), mode],
        input=stdin, capture_output=True, text=True, env=env)


def hook(root, command, env_extra=None):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return run("hook", root, stdin=payload, env_extra=env_extra)


def is_allow(proc):
    if not proc.stdout.strip():
        return False
    out = json.loads(proc.stdout)
    return out["hookSpecificOutput"]["permissionDecision"] == "allow"


def check(name, cond):
    global PASS, FAIL
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}")
    if cond:
        PASS += 1
    else:
        FAIL += 1


def fresh_root(queue_text):
    root = Path(tempfile.mkdtemp(prefix="twss-test-"))
    (root / ".claude").mkdir()
    (root / ".claude" / "twss-queue.txt").write_text(queue_text, encoding="utf-8")
    return root


QUEUE = "# test queue\necho alpha\necho beta && echo gamma\n"

# (a) approved queue runs with zero prompts (hook allows each line, in any order)
root = fresh_root(QUEUE)
p = run("approve", root)
check("(a) approve exits 0 and prints the queue",
      p.returncode == 0 and "echo alpha" in p.stdout)
check("(a) approved line 1 -> allow", is_allow(hook(root, "echo alpha")))
check("(a) approved compound line -> allow", is_allow(hook(root, "echo beta && echo gamma")))
check("(a) consumed line re-run -> silence (no decision)",
      not hook(root, "echo alpha").stdout.strip())

# (b) any queue edit voids the approval
root = fresh_root(QUEUE)
run("approve", root)
qf = root / ".claude" / "twss-queue.txt"
qf.write_text(QUEUE + "echo smuggled\n", encoding="utf-8")
check("(b) appended line -> approval void, old line silent",
      not hook(root, "echo alpha").stdout.strip())
check("(b) appended line -> new line silent too",
      not hook(root, "echo smuggled").stdout.strip())
root = fresh_root(QUEUE)
run("approve", root)
qf = root / ".claude" / "twss-queue.txt"
qf.write_text(QUEUE.replace("alpha", "ALPHA"), encoding="utf-8")
check("(b) edited line -> approval void", not hook(root, "echo ALPHA").stdout.strip())

# (c) unqueued command falls through (silence)
root = fresh_root(QUEUE)
run("approve", root)
check("(c) unqueued command -> silence", not hook(root, "echo delta").stdout.strip())
check("(c) near-miss (extra space) -> silence",
      not hook(root, "echo  alpha").stdout.strip())

# (d) expired TTL -> silence
root = fresh_root(QUEUE)
run("approve", root)
time.sleep(1.1)
check("(d) expired TTL -> silence",
      not hook(root, "echo alpha", env_extra={"TWSS_TTL_SECONDS": "1"}).stdout.strip())

# extra: no approval at all -> silence
root = fresh_root(QUEUE)
check("(x) no approval -> silence", not hook(root, "echo alpha").stdout.strip())

# extra: denylist blocks at approve time
root = fresh_root("sudo rm -rf /\n")
p = run("approve", root)
check("(x) denylisted queue refused at approve", p.returncode == 2 and "BLOCKED" in p.stdout)
check("(x) denylisted command silent at hook even so",
      not hook(root, "sudo rm -rf /").stdout.strip())

# extra: malformed stdin -> silence, exit 0 (fail closed)
root = fresh_root(QUEUE)
run("approve", root)
p = run("hook", root, stdin="this is not json")
check("(x) malformed stdin -> silence, exit 0",
      p.returncode == 0 and not p.stdout.strip())

# extra: non-Bash tool -> silence
root = fresh_root(QUEUE)
run("approve", root)
p = run("hook", root, stdin=json.dumps(
    {"tool_name": "Write", "tool_input": {"command": "echo alpha"}}))
check("(x) non-Bash tool -> silence", not p.stdout.strip())

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
