#!/usr/bin/env python3
"""Acceptance tests for install.py — run: python3 test_install.py

Each test runs install.py as a subprocess against a throwaway vault
(BBB_VAULT_ROOT) with a throwaway shim dir (TWSS_INSTALL_DIR), always with
--no-path (never touches the real registry) and --no-test (the hook suite has
its own runner, test_twss.py). No test touches the real vault or PATH.
"""

import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
INSTALL = SKILL_DIR / "install.py"
IS_WINDOWS = platform.system() == "Windows"
PASS, FAIL = 0, 0


def check(name, cond):
    global PASS, FAIL
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}")
    if cond:
        PASS += 1
    else:
        FAIL += 1


def run_install(vault, bindir, cwd=None, extra=()):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("BBB_VAULT_ROOT", None)
    if vault is not None:
        env["BBB_VAULT_ROOT"] = str(vault)
    env["TWSS_INSTALL_DIR"] = str(bindir)
    return subprocess.run(
        [sys.executable, str(INSTALL), "--no-path", "--no-test", *extra],
        capture_output=True, text=True, env=env, cwd=cwd or SKILL_DIR)


def tmpbin():
    return Path(tempfile.mkdtemp(prefix="twss-install-bin-"))


def hook_entry(command):
    return {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": command, "timeout": 10}]}]}}


def fresh_vault(settings_local=None, settings_shared=None):
    root = Path(tempfile.mkdtemp(prefix="twss-install-test-"))
    (root / ".claude").mkdir()
    if settings_local is not None:
        (root / ".claude" / "settings.local.json").write_text(
            json.dumps(settings_local), encoding="utf-8")
    if settings_shared is not None:
        (root / ".claude" / "settings.json").write_text(
            json.dumps(settings_shared), encoding="utf-8")
    return root


def twss_entries(cfg):
    return [e for e in cfg.get("hooks", {}).get("PreToolUse", [])
            for h in e.get("hooks", []) if "twss.py" in h.get("command", "")]


# (a) fresh vault: hook copied, registered in settings.local.json, shims written
vault = fresh_vault(settings_local={"env": {"KEEP": "me"}})
bindir = Path(tempfile.mkdtemp(prefix="twss-install-bin-"))
p = run_install(vault, bindir)
check("(a) install exits 0", p.returncode == 0)
hook = vault / ".claude" / "hooks" / "twss.py"
check("(a) hook file copied byte-exact",
      hook.exists() and hook.read_bytes() == (SKILL_DIR / "twss.py").read_bytes())
cfg = json.loads((vault / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
entries = twss_entries(cfg)
check("(a) hook registered in settings.local.json", len(entries) == 1)
check("(a) existing settings.local.json keys preserved",
      cfg.get("env", {}).get("KEEP") == "me")
cmd = entries[0]["hooks"][0]["command"] if entries else ""
check("(a) command pins this interpreter and ends with 'hook'",
      Path(sys.executable).stem in cmd and "twss.py" in cmd and cmd.endswith(" hook"))
check("(a) command uses forward slashes only", "\\" not in cmd)
check("(a) sh shim written", (bindir / "twss").exists())
if IS_WINDOWS:
    check("(a) twss.cmd written", (bindir / "twss.cmd").exists())

# (b) idempotent: second run leaves exactly one registration
p = run_install(vault, bindir)
cfg = json.loads((vault / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
check("(b) re-run exits 0 and says already registered",
      p.returncode == 0 and "already registered" in p.stdout)
check("(b) still exactly one registration", len(twss_entries(cfg)) == 1)

# (c) a WORKING registration in settings.json is flagged as misplaced — because
#     that file is an asset copy that machine registration overwrites, NOT because
#     it syncs (no dot-file reaches another machine) — reported and left alone
#     without --repair
working = f'"{sys.executable}" "{{}}/.claude/hooks/twss.py" hook'
vault = fresh_vault(settings_shared=hook_entry(working.format(str(vault).replace(chr(92), "/"))))
p = run_install(vault, tmpbin())
local = vault / ".claude" / "settings.local.json"
check("(c) settings.json registration reported as misplaced (asset copy)",
      "ASSET COPY" in p.stdout and p.returncode == 2)
check("(c) the stale 'it syncs' justification is gone",
      "SYNCS" not in p.stdout)
check("(c) settings.local.json not given a duplicate without --repair",
      not local.exists() or not twss_entries(json.loads(local.read_text(encoding="utf-8"))))
check("(c) settings.json registration left intact without --repair",
      len(twss_entries(json.loads((vault / ".claude" / "settings.json").read_text(encoding="utf-8")))) == 1)

# (c2) --repair moves it into settings.local.json, pinned, and clears settings.json
p = run_install(vault, tmpbin(), extra=("--repair",))
shared_cfg = json.loads((vault / ".claude" / "settings.json").read_text(encoding="utf-8"))
local_cfg = json.loads(local.read_text(encoding="utf-8"))
check("(c2) --repair exits 0", p.returncode == 0)
check("(c2) settings.json no longer registers twss", not twss_entries(shared_cfg))
check("(c2) settings.local.json now holds exactly one", len(twss_entries(local_cfg)) == 1)

# (c3) a BROKEN interpreter is detected, not blessed
vault = fresh_vault(settings_local=hook_entry(
    "definitely-not-a-real-python-xyz \"/tmp/.claude/hooks/twss.py\" hook"))
p = run_install(vault, tmpbin())
check("(c3) broken interpreter reported as BROKEN, exit 2",
      "BROKEN" in p.stdout and p.returncode == 2)
p = run_install(vault, tmpbin(), extra=("--repair",))
local_cfg = json.loads((vault / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
entries = twss_entries(local_cfg)
check("(c3) --repair replaces it with exactly one working entry", len(entries) == 1)
check("(c3) repaired entry pins this interpreter",
      entries and Path(sys.executable).stem in entries[0]["hooks"][0]["command"])

# (c4) unrelated PreToolUse hooks survive a repair
vault = fresh_vault(settings_local={"hooks": {"PreToolUse": [
    {"matcher": "Bash", "hooks": [{"type": "command", "command": "other-tool.sh"}]},
    {"matcher": "Bash", "hooks": [{"type": "command", "command": "nope-python /x/twss.py hook"}]}]}})
run_install(vault, tmpbin(), extra=("--repair",))
cfg = json.loads((vault / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
all_cmds = [h["command"] for e in cfg["hooks"]["PreToolUse"] for h in e["hooks"]]
check("(c4) unrelated hook preserved through repair",
      any("other-tool.sh" in c for c in all_cmds))
check("(c4) broken twss entry gone after repair",
      not any("nope-python" in c for c in all_cmds))

# (d) no vault anywhere -> exit 5
p = run_install(None, tmpbin(), cwd=Path(tempfile.mkdtemp(prefix="twss-install-novault-")))
check("(d) vault not found -> exit 5", p.returncode == 5)

# (e) installed hook actually runs and answers status
vault = fresh_vault(settings_local={})
run_install(vault, tmpbin())
env = dict(os.environ)
env["CLAUDE_PROJECT_DIR"] = str(vault)
env.pop("BBB_VAULT_ROOT", None)
p = subprocess.run([sys.executable, str(vault / ".claude" / "hooks" / "twss.py"), "status"],
                   capture_output=True, text=True, env=env)
check("(e) installed hook answers status", p.returncode == 0 and "twss:" in p.stdout)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
