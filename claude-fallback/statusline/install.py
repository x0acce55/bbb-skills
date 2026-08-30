#!/usr/bin/env python3
"""install.py — install the claude-cost status line for the current machine.

Copies claude-cost.py into ~/.claude/statusline/ and reports whether the
`statusLine` key is registered in ~/.claude/settings.json. Idempotent — safe to
re-run. Stdlib only.

Run this YOURSELF (via the ! prefix in Claude Code). Like the twss installer,
it NEVER edits settings.json: it prints the exact JSON to merge and leaves the
edit to you. Settings are the human's consent surface.

What it does:
  1. Copies claude-cost.py (next to this file) to ~/.claude/statusline/ and
     creates the cache/ and daily/ working directories.
  2. Picks the interpreter for the statusLine command:
       Windows : python   (python3 there is the Store stub — it is not Python)
       else    : python3
     Override with CLAUDE_COST_PYTHON.
  3. Reports the statusLine registration state and prints the JSON to merge if
     it is missing or points somewhere else.
  4. Smoke-tests the installed script with a mock payload and shows the line.

Run with python3 (macOS/Linux) or python (Windows).
"""

import json
import os
import platform
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "claude-cost.py")
DEST_DIR = os.path.join(os.path.expanduser("~"), ".claude", "statusline")
DEST = os.path.join(DEST_DIR, "claude-cost.py")
SETTINGS = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
IS_WINDOWS = platform.system() == "Windows"


def interpreter():
    override = os.environ.get("CLAUDE_COST_PYTHON")
    if override:
        return override
    return "python" if IS_WINDOWS else "python3"


def status_line_command():
    return '%s "%s"' % (interpreter(), DEST)


def install_script():
    if not os.path.isfile(SRC):
        sys.exit("install: claude-cost.py not found next to install.py (%s)" % SRC)
    os.makedirs(os.path.join(DEST_DIR, "cache"), exist_ok=True)
    os.makedirs(os.path.join(DEST_DIR, "daily"), exist_ok=True)
    unchanged = os.path.isfile(DEST) and open(SRC, "rb").read() == open(DEST, "rb").read()
    shutil.copyfile(SRC, DEST)
    if not IS_WINDOWS:
        os.chmod(DEST, 0o755)
    print("%s %s" % ("unchanged:" if unchanged else "installed: ", DEST))


def check_registration():
    want = status_line_command()
    try:
        with open(SETTINGS) as fh:
            settings = json.load(fh)
    except FileNotFoundError:
        print("\nsettings: %s does not exist yet." % SETTINGS)
        settings = None
    except ValueError as exc:
        print("\nsettings: %s is not valid JSON (%s)." % (SETTINGS, exc))
        print("          Fix that first — a malformed settings.json disables every")
        print("          setting in the file, silently.")
        return False

    current = (settings or {}).get("statusLine")
    if isinstance(current, dict) and current.get("command") == want:
        print("settings: statusLine already registered and pointing here. Nothing to do.")
        return True

    if current:
        print("\nsettings: a DIFFERENT statusLine is registered:")
        print("            %s" % json.dumps(current))
        print("          Replace its command with the one below, or keep yours if")
        print("          you have merged this script into it.")
    else:
        print("\nsettings: statusLine is not registered. Merge this into %s" % SETTINGS)
        print("          (merge — do not replace the file; keep your other keys):")
    print()
    print(json.dumps({"statusLine": {"type": "command", "command": want}}, indent=2))
    print()
    print("          Then open /statusline once, or restart, to load it.")
    return False


def smoke_test():
    payload = json.dumps({
        "session_id": "install-smoke-test",
        "transcript_path": "",
        "model": {"id": "claude-fable-5", "display_name": "Fable 5"},
        "context_window": {"used_percentage": 12},
    })
    env = dict(os.environ, COLUMNS="100")
    env.pop("ANTHROPIC_BASE_URL", None)
    try:
        out = subprocess.run(
            [interpreter(), DEST], input=payload, capture_output=True,
            text=True, env=env, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print("\nsmoke test: could not run %s (%s)" % (interpreter(), exc))
        print("            On Windows use `python`, not `python3`.")
        return False
    if out.returncode != 0 or not out.stdout.strip():
        print("\nsmoke test: FAILED (exit %s)" % out.returncode)
        if out.stderr.strip():
            print(out.stderr.strip()[:500])
        return False
    print("\nsmoke test: ok ->  %s" % out.stdout.rstrip("\n"))
    # leave no trace of the fake session
    for sub in ("cache", "daily"):
        p = os.path.join(DEST_DIR, sub, "install-smoke-test.json")
        if os.path.exists(p):
            os.unlink(p)
    for name in os.listdir(os.path.join(DEST_DIR, "daily")):
        p = os.path.join(DEST_DIR, "daily", name)
        try:
            with open(p) as fh:
                rollup = json.load(fh)
            if rollup.pop("install-smoke-test", None) is not None:
                with open(p, "w") as fh:
                    json.dump(rollup, fh)
        except (ValueError, OSError):
            pass
    return True


def main():
    print("claude-cost status line installer")
    print("---------------------------------")
    install_script()
    ok = smoke_test()
    registered = check_registration()
    if not ok:
        sys.exit(1)
    if not registered:
        print("Script is installed; the settings merge above is still yours to make.")


if __name__ == "__main__":
    main()
