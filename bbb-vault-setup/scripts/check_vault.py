#!/usr/bin/env python3
"""Check the BBB vault's invariants.

Reports, in order of how much trouble each one causes:

  1. Sync conflict copies                    - real work about to be lost
  2. Notes missing frontmatter or a summary  - invisible to the scanning pass
  3. Notes missing an up: link               - dead end when clicking through
  4. ADR cross-reference asymmetry           - a decision traceable one way only
  5. Duplicate note basenames                - ambiguous [[wikilink]] resolution
  6. Broken links                            - [[target]] with no matching file
  7. Index drift                             - folder contents not in the index
  8. ADR numbering gaps and duplicates
  9. Stale memory lock                       - a crashed session still holding it

Exit code is 0 when clean, 1 when anything is reported.

Usage:
    python check_vault.py <vault-root>
    python check_vault.py <vault-root> --quiet   # only problems
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_index import parse_frontmatter, SKIP_NAMES  # noqa: E402

LINK = re.compile(r"\[\[([^\]|#]+)")
FENCE = re.compile(r"```.*?```", re.DOTALL)
CODE_SPAN = re.compile(r"`[^`\n]*`")


def strip_code(text: str) -> str:
    """Remove fenced blocks and inline code before scanning for links.

    Documentation notes and ADRs legitimately contain example wikilinks inside
    backticks. Those are illustrations, not links, and flagging them trains the
    user to ignore the checker.
    """
    return CODE_SPAN.sub("", FENCE.sub("", text))
EXEMPT_DIRS = {"memories", ".claude", ".obsidian", ".git", ".trash"}
CONFLICT_PATTERNS = (
    "conflicted copy",
    ".sync-conflict-",
    "conflicted-copy",
    " (case conflict)",
)
NO_UP_REQUIRED = {"context", "daily"}


def iter_notes(vault: Path):
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault)
        if any(part in EXEMPT_DIRS for part in rel.parts):
            continue
        if path.name in SKIP_NAMES:
            continue
        if any(pat in path.name.lower() for pat in CONFLICT_PATTERNS):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        yield path, rel, text, parse_frontmatter(text)


def as_list(value):
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)


def adr_id(stem: str):
    m = re.match(r"(ADR-\d{4})", stem)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("vault", type=Path)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    vault = args.vault

    if not vault.is_dir():
        print(f"Not a directory: {vault}", file=sys.stderr)
        return 2

    notes = list(iter_notes(vault))
    if not notes:
        print(f"No notes found under {vault}")
        return 0

    stems = defaultdict(list)
    no_frontmatter, no_summary, no_up = [], [], []
    adr_affects = {}          # ADR id -> set of referenced note stems
    note_decisions = {}       # note stem -> set of ADR ids
    broken = []

    for path, rel, text, fm in notes:
        stems[path.stem].append(rel)

        if not fm:
            no_frontmatter.append(rel)
        else:
            if not fm.get("summary"):
                no_summary.append(rel)
            top = rel.parts[0] if len(rel.parts) > 1 else ""
            is_home = len(rel.parts) == 1
            if not fm.get("up") and not is_home and top not in NO_UP_REQUIRED:
                no_up.append(rel)

        this_adr = adr_id(path.stem)
        if this_adr:
            targets = set()
            for ref in as_list(fm.get("affects")):
                cleaned = ref.strip().strip("[]").split("|")[0].split("/")[-1]
                if cleaned:
                    targets.add(cleaned)
            adr_affects[this_adr] = targets
        else:
            decisions = {d.strip() for d in as_list(fm.get("decisions")) if d.strip()}
            if decisions:
                note_decisions[path.stem] = decisions

    known = set(stems)
    for path, rel, text, fm in notes:
        body = strip_code(text)
        for target in LINK.findall(body):
            target = target.strip().split("/")[-1]
            if target and target not in known and not adr_id(target):
                broken.append((rel, target))

    # Path is authoritative for placement (ADR-0018): projects/<domain>/<project>/.
    # `domain:` and `project:` frontmatter mirror the path for Obsidian queries;
    # when they disagree with it, one of them is lying.
    misplaced = []
    for path, rel, text, fm in notes:
        if not fm or rel.parts[0] != "projects" or len(rel.parts) < 3:
            continue
        path_domain = rel.parts[1]
        path_project = rel.parts[2] if len(rel.parts) >= 4 else None
        fm_domain = str(fm.get("domain") or "").strip()
        fm_project = str(fm.get("project") or "").strip()
        if fm_domain and fm_domain != path_domain:
            misplaced.append(f"{rel}: domain: '{fm_domain}' but the path says '{path_domain}'")
        if fm_project:
            if path_project is None and fm_project != path_domain:
                misplaced.append(
                    f"{rel}: project: '{fm_project}' but the note sits at domain level"
                )
            elif path_project is not None and fm_project != path_project:
                misplaced.append(
                    f"{rel}: project: '{fm_project}' but the path says '{path_project}'"
                )

    problems = 0

    def section(title, items, render):
        nonlocal problems
        if not items:
            if not args.quiet:
                print(f"  ok    {title}")
            return
        problems += len(items)
        print(f"\n  {len(items)} {title}")
        for item in items:
            print(f"        {render(item)}")

    print(f"Checked {len(notes)} notes under {vault}\n")

    # Conflict copies first: these represent work that is about to be lost.
    conflicts = []
    for path in sorted(vault.rglob("*")):
        if not path.is_file():
            continue
        low = path.name.lower()
        if any(pat in low for pat in CONFLICT_PATTERNS):
            conflicts.append(path.relative_to(vault))
    section("SYNC CONFLICT FILES (merge by hand, do not delete)", conflicts, str)

    section("notes missing frontmatter", no_frontmatter, str)
    section("notes missing a summary", no_summary, str)
    section("notes missing an up: link", no_up, str)

    # ADR symmetry, both directions
    asymmetric = []
    for adr, targets in adr_affects.items():
        for target in targets:
            if adr not in note_decisions.get(target, set()):
                asymmetric.append(f"{adr} affects {target}, but {target} does not list {adr}")
    for stem, decisions in note_decisions.items():
        for adr in decisions:
            if adr in adr_affects and stem not in adr_affects[adr]:
                asymmetric.append(f"{stem} lists {adr}, but {adr} does not affect {stem}")
            elif adr not in adr_affects:
                asymmetric.append(f"{stem} lists {adr}, which does not exist")
    section("asymmetric decision references", asymmetric, str)

    dupes = [(stem, paths) for stem, paths in sorted(stems.items()) if len(paths) > 1]
    section(
        "duplicate note basenames (ambiguous wikilinks)",
        dupes,
        lambda d: f"{d[0]}: " + ", ".join(str(p) for p in d[1]),
    )

    section("broken links", broken, lambda b: f"{b[0]} -> [[{b[1]}]]")

    section("frontmatter placement mismatches (domain/project vs path)", misplaced, str)

    # ADR numbering
    numbers = sorted(
        int(a.split("-")[1]) for a in adr_affects if a
    )
    gaps = []
    if numbers:
        seen = set(numbers)
        for n in range(1, max(numbers) + 1):
            if n not in seen:
                gaps.append(f"ADR-{n:04d} is missing")
        for n in numbers:
            if numbers.count(n) > 1:
                gaps.append(f"ADR-{n:04d} is duplicated")
    section("ADR numbering issues", sorted(set(gaps)), str)

    # Index drift, delegated to the generator
    print()
    try:
        import subprocess

        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "build_index.py"),
             str(vault), "--check"],
            capture_output=True, text=True,
        )
        for line in result.stdout.splitlines():
            print(f"  {line.strip()}")
        if result.returncode == 1:
            problems += 1
    except Exception as exc:  # index check is best-effort
        print(f"  (could not run index check: {exc})")

    # Memory lock state
    lock_file = vault / "memories" / ".lock.json"
    if lock_file.exists():
        import json as _json
        try:
            lock = _json.loads(lock_file.read_text(encoding="utf-8"))
            print(f"  lock   held by {lock.get('machine', '?')} "
                  f"for {lock.get('operation', '?')}, "
                  f"heartbeat {lock.get('heartbeat', '?')}")
            print("         run: python memlock.py <vault> status")
        except Exception:
            print("  !!     memories/.lock.json is present but unreadable")
            problems += 1

    print()
    if problems:
        print(f"{problems} issue(s) found.")
        return 1
    print("Vault is clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
