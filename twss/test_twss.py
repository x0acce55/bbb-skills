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


def run(mode, root, stdin=None, env_extra=None, cwd=None):
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    for stale in ("BBB_VAULT_ROOT", "TWSS_ROOT"):
        env.pop(stale, None)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(TWSS), mode],
        input=stdin, capture_output=True, text=True, env=env, cwd=cwd)


def run_bare(mode, stdin=None, env_extra=None, cwd=None):
    """Like run(), but with NO root variables set at all — the shape of the
    user's `!` shell, which is where the hook and the CLI used to disagree."""
    env = dict(os.environ)
    for stale in ("BBB_VAULT_ROOT", "TWSS_ROOT", "CLAUDE_PROJECT_DIR"):
        env.pop(stale, None)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(TWSS), mode],
        input=stdin, capture_output=True, text=True, env=env, cwd=cwd)


def hook(root, command, env_extra=None, tool_input=None):
    ti = {"command": command}
    ti.update(tool_input or {})
    payload = json.dumps({"tool_name": "Bash", "tool_input": ti})
    return run("hook", root, stdin=payload, env_extra=env_extra)


def log_text(root):
    p = Path(root) / ".claude" / "twss-log.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""


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
    """The queue sits at the project root, not in .claude/ (ADR-0043)."""
    root = Path(tempfile.mkdtemp(prefix="twss-test-"))
    (root / ".claude").mkdir()
    (root / ".twss-queue.txt").write_text(queue_text, encoding="utf-8")
    return root


def queue_path(root):
    return Path(root) / ".twss-queue.txt"


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
qf = queue_path(root)
qf.write_text(QUEUE + "echo smuggled\n", encoding="utf-8")
check("(b) appended line -> approval void, old line silent",
      not hook(root, "echo alpha").stdout.strip())
check("(b) appended line -> new line silent too",
      not hook(root, "echo smuggled").stdout.strip())
root = fresh_root(QUEUE)
run("approve", root)
qf = queue_path(root)
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

def payload(command):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


# (e) root resolution — the axis that was wholly untested while the bug lived in it
root = fresh_root(QUEUE)
other = fresh_root("# other\necho zulu\n")
run("approve", root)
check("(e) TWSS_ROOT wins over CLAUDE_PROJECT_DIR",
      is_allow(hook(other, "echo alpha", env_extra={"TWSS_ROOT": str(root)})))

# BBB_VAULT_ROOT used to redirect the hook away from cwd. It must not any more:
# `bbb` exports it into the session while cd'ing into a domain, which is exactly
# how approve and the hook came to address different directories.
p = run_bare("hook", stdin=payload("echo alpha"),
             env_extra={"BBB_VAULT_ROOT": str(root)}, cwd=str(other))
check("(e) BBB_VAULT_ROOT no longer redirects the hook", not p.stdout.strip())
cwd_root = fresh_root(QUEUE)  # a fresh one: `root`'s line is already consumed
run("approve", cwd_root)
check("(e) bare env falls back to cwd",
      is_allow(run_bare("hook", stdin=payload("echo alpha"), cwd=str(cwd_root))))

# The regression proper: a `bbb <domain>`-shaped shell. TWSS_ROOT names the
# domain, BBB_VAULT_ROOT names the vault, cwd is the vault. approve must land on
# the domain — the same directory the hook will read.
vault = fresh_root("# vault queue\necho vault-line\n")
domain = fresh_root(QUEUE)
p = run_bare("approve", env_extra={"BBB_VAULT_ROOT": str(vault), "TWSS_ROOT": str(domain)},
             cwd=str(vault))
check("(e) approve under a bbb-shaped shell targets the domain, not the vault",
      p.returncode == 0 and "echo alpha" in p.stdout and str(domain) in p.stdout)
check("(e) and the hook then allows that line", is_allow(hook(domain, "echo alpha")))
check("(e) the vault's own queue was left untouched",
      not (Path(vault) / ".claude" / "twss-approved.json").exists())

# (f) the queue is agent-writable territory, outside .claude/
root = fresh_root(QUEUE)
check("(f) queue lives at <root>/.twss-queue.txt, not in .claude/",
      queue_path(root).exists() and not (root / ".claude" / "twss-queue.txt").exists())
run("approve", root)
check("(f) the approval stays inside .claude/",
      (root / ".claude" / "twss-approved.json").exists())

# (g) every decline names its branch in the log, and still prints nothing
root = fresh_root(QUEUE)
hook(root, "echo alpha")
check("(g) no-approval decline is logged", "DECLINE no-approval" in log_text(root))

root = fresh_root(QUEUE)
run("approve", root)
queue_path(root).write_text(QUEUE + "echo smuggled\n", encoding="utf-8")
hook(root, "echo alpha")
check("(g) hash-void decline is logged", "DECLINE hash-void" in log_text(root))

root = fresh_root(QUEUE)
run("approve", root)
time.sleep(1.1)
hook(root, "echo alpha", env_extra={"TWSS_TTL_SECONDS": "1"})
check("(g) ttl-expired decline is logged", "DECLINE ttl-expired" in log_text(root))

root = fresh_root(QUEUE)
run("approve", root)
hook(root, "echo alpha")
hook(root, "echo alpha")
check("(g) consumed decline is logged", "DECLINE consumed line 2" in log_text(root))

root = fresh_root(QUEUE)
run("approve", root)
p = hook(root, "echo delta")
check("(g) no-match decline is logged", "DECLINE no-match" in log_text(root))
check("(g) a logged decline still prints nothing", not p.stdout.strip())
for _ in range(3):
    hook(root, "echo delta")
check("(g) repeated identical declines collapse to one line",
      log_text(root).count("DECLINE no-match") == 1)

bare = Path(tempfile.mkdtemp(prefix="twss-test-"))
(bare / ".claude").mkdir()
hook(bare, "echo alpha")
check("(g) no queue -> nothing logged at all", log_text(bare) == "")

# (h) the CLI says where it is looking, and flags a pre-ADR-0043 queue
root = fresh_root(QUEUE)
(root / ".claude" / "twss-queue.txt").write_text("# legacy\n", encoding="utf-8")
p = run("status", root)
check("(h) status names the resolved root", f"root {root}" in p.stdout)
check("(h) legacy queue location is reported", "legacy queue" in p.stdout)
check("(h) status reports hook registration", "hook:" in p.stdout)

# (i) a sandbox escape is not covered by an approval unless the queue says so
root = fresh_root(QUEUE)
run("approve", root)
p = hook(root, "echo alpha", tool_input={"dangerouslyDisableSandbox": True})
check("(i) sandbox escape without opt-in -> silence", not p.stdout.strip())
check("(i) sandbox escape is logged", "DECLINE sandbox-escape" in log_text(root))

OPT_IN = "# twss: allow-sandbox-escape\n" + QUEUE
root = fresh_root(OPT_IN)
p = run("approve", root)
check("(i) approve warns that the queue opts into sandbox escapes",
      "sandbox DISABLED" in p.stdout)
check("(i) sandbox escape with opt-in -> allow",
      is_allow(hook(root, "echo alpha", tool_input={"dangerouslyDisableSandbox": True})))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
