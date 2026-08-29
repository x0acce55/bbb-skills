#!/usr/bin/env python3
"""Verify that this machine is correctly wired to the BBB vault.

Answers one question: is the vault present, and is this machine registered against
it? Content consistency is a different concern -- that's check_vault.py.

Resolution order for the vault root:
    1. the path given as an argument
    2. $BBB_VAULT_ROOT
    3. walking up from the current directory looking for a .obsidian folder

Usage:
    python verify_setup.py [vault-root] [--json] [--quiet]

Exit codes are designed to be branched on by a SessionStart hook later:
    0  vault found and this machine is registered
    4  vault found, but this machine is not registered
    5  vault not found            <- the future hook would fetch the skill here
    1  error
"""

import argparse
import json
import os
import sys
from pathlib import Path

CORE_DIRS = ("context", "decisions", "projects", "daily", "memories")
ROOT_FILES = ("AGENTS.md", "CLAUDE.md")

OK, WARN, BAD = "ok", "warn", "bad"


class Report:
    def __init__(self):
        self.lines = []
        self.worst = OK

    def add(self, level, label, detail=""):
        self.lines.append((level, label, detail))
        if level == BAD or (level == WARN and self.worst == OK):
            self.worst = level

    def render(self, quiet=False):
        mark = {OK: "  ok  ", WARN: " warn ", BAD: "  !!  "}
        out = []
        for level, label, detail in self.lines:
            if quiet and level == OK:
                continue
            out.append(f"{mark[level]}  {label}")
            if detail:
                out.append(f"          {detail}")
        return "\n".join(out)


def find_vault(explicit):
    """Return (path, how_it_was_found) or (None, reason)."""
    if explicit:
        return Path(explicit).expanduser(), "argument"

    env = os.environ.get("BBB_VAULT_ROOT")
    if env:
        return Path(env).expanduser(), "$BBB_VAULT_ROOT"

    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".obsidian").is_dir():
            return candidate, "found .obsidian walking up from cwd"

    return None, "no argument, no $BBB_VAULT_ROOT, no .obsidian above cwd"


def looks_like_vault(root: Path):
    """Distinguish 'an Obsidian vault' from 'the BBB vault'."""
    if not root.is_dir():
        return False, f"not a directory: {root}"
    if not (root / ".obsidian").is_dir():
        return False, "no .obsidian/ -- this is not an Obsidian vault"
    missing = [d for d in CORE_DIRS if not (root / d).is_dir()]
    if len(missing) == len(CORE_DIRS):
        return False, "no BBB directories present -- vault exists but is not scaffolded"
    return True, ", ".join(missing) if missing else ""


def read_settings(root: Path):
    path = root / ".claude" / "settings.local.json"
    if not path.exists():
        return None, path, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), path, None
    except json.JSONDecodeError as exc:
        return None, path, f"invalid JSON: {exc}"


def sync_excluded(root: Path) -> bool:
    """Is settings.local.json kept out of sync? Only git is checkable from here."""
    for name in (".gitignore", ".syncignore"):
        f = root / name
        if f.exists() and "settings.local.json" in f.read_text(
            encoding="utf-8", errors="replace"
        ):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("vault", nargs="?", default=None)
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    report = Report()
    result = {"vault_found": False, "machine_registered": False}

    root, how = find_vault(args.vault)
    if root is None:
        report.add(BAD, "Vault NOT found", how)
        if args.as_json:
            print(json.dumps({**result, "reason": how}, indent=2))
        else:
            print(report.render())
            print()
            print("The vault could not be located. Set BBB_VAULT_ROOT in")
            print(".claude/settings.local.json, or run the bbb-vault-setup skill.")
        return 5

    ok, detail = looks_like_vault(root)
    if not ok:
        report.add(BAD, "Vault NOT found", detail)
        if args.as_json:
            print(json.dumps({**result, "root": str(root), "reason": detail}, indent=2))
        else:
            print(report.render())
        return 5

    result["vault_found"] = True
    result["root"] = str(root)
    report.add(OK, f"Vault FOUND at {root}", f"located via {how}")
    if detail:
        report.add(WARN, "Some core directories are missing", detail)

    for name in ROOT_FILES:
        if (root / name).exists():
            report.add(OK, f"{name} present")
        else:
            report.add(BAD, f"{name} missing", "run the bbb-vault-setup skill")

    settings, spath, err = read_settings(root)
    if settings is None:
        report.add(BAD, "settings.local.json " + err, str(spath))
        registered = False
    else:
        report.add(OK, "settings.local.json present and valid")
        env = settings.get("env", {}) or {}
        machine = env.get("BBB_MACHINE_ID")
        declared_root = env.get("BBB_VAULT_ROOT")
        mem = settings.get("autoMemoryDirectory")

        registered = bool(machine and mem)
        result["machine_id"] = machine

        if machine:
            report.add(OK, f"machine registered as '{machine}'")
        else:
            report.add(BAD, "env.BBB_MACHINE_ID not set", "this machine is unregistered")

        if declared_root:
            if Path(declared_root).expanduser().resolve() == root.resolve():
                report.add(OK, "env.BBB_VAULT_ROOT matches this vault")
            else:
                report.add(
                    BAD,
                    "env.BBB_VAULT_ROOT points somewhere else",
                    f"declared {declared_root}, actual {root}",
                )
                registered = False
        else:
            report.add(WARN, "env.BBB_VAULT_ROOT not set", "vault won't self-locate")

        if mem:
            mpath = Path(mem).expanduser()
            if not mpath.is_dir():
                report.add(BAD, "autoMemoryDirectory does not exist", str(mpath))
                registered = False
            elif root.resolve() not in mpath.resolve().parents:
                report.add(BAD, "autoMemoryDirectory is outside the vault", str(mpath))
                registered = False
            elif machine and mpath.name != machine:
                report.add(
                    BAD,
                    "autoMemoryDirectory does not match the machine id",
                    f"buffer is '{mpath.name}', machine is '{machine}' -- two machines "
                    "sharing a buffer is the failure ADR-0009 exists to prevent",
                )
                registered = False
            else:
                report.add(OK, f"memory buffer at memories/{mpath.name}")
        else:
            report.add(BAD, "autoMemoryDirectory not set")
            registered = False

        vault_id = env.get("BBB_VAULT_ID")
        if vault_id:
            report.add(OK, f"vault identified as '{vault_id}'")
        else:
            report.add(
                WARN,
                "env.BBB_VAULT_ID not set",
                "with multiple vaults, session tooling cannot tell them apart (ADR-0019)",
            )

        skill = env.get("BBB_SETUP_SKILL")
        source = env.get("BBB_SETUP_SOURCE")
        if skill:
            report.add(OK, f"setup skill declared as '{skill}'")
        else:
            report.add(WARN, "env.BBB_SETUP_SKILL not declared")
        if source:
            report.add(OK, "setup skill source recorded", source)
        else:
            report.add(
                WARN,
                "env.BBB_SETUP_SOURCE not set",
                "set this once the skill is published to git",
            )

    if (root / ".git").exists() or (root / ".gitignore").exists():
        if sync_excluded(root):
            report.add(OK, "settings.local.json is excluded from sync")
        else:
            report.add(
                BAD,
                "settings.local.json is NOT excluded from sync",
                "if it syncs, the other machine inherits this machine's memory path",
            )

    result["machine_registered"] = registered

    if args.as_json:
        print(json.dumps(result, indent=2))
    else:
        print(report.render(args.quiet))
        print()
        if registered and report.worst != BAD:
            print(f"Setup verified. Vault found at {root}.")
        elif registered:
            print("Vault found and machine registered, but problems above need fixing.")
        else:
            print("Vault found, but this machine is not registered against it.")
            print("Run the bbb-vault-setup skill to register it.")

    if not registered:
        return 4
    return 1 if report.worst == BAD else 0


if __name__ == "__main__":
    sys.exit(main())
