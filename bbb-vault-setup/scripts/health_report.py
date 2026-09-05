#!/usr/bin/env python3
"""Periodic health report for the BBB vault.

check_vault.py catches structural breakage and runs in a second -- use it constantly.
This is the slower pass: things that are structurally valid but rotting. Nothing here
is an error. Every finding is a prompt for a human judgment the tooling cannot make.

Run it monthly, or when the vault starts feeling untrustworthy.

Usage:
    python health_report.py <vault-root> [--stale-days 90] [--proposed-days 30]
"""

import argparse
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_index import parse_frontmatter, SKIP_NAMES, CONFLICT_PATTERNS  # noqa: E402

LINK = re.compile(r"\[\[([^\]|#]+)")
FENCE = re.compile(r"```.*?```", re.DOTALL)
CODE_SPAN = re.compile(r"`[^`\n]*`")
EXEMPT = {"memories", ".claude", ".obsidian", ".git", ".trash"}

# Claude Code loads only the first 200 lines or 25KB of a memory index, and the
# guidance for instruction files is under 200 lines. Past these, content is either
# silently dropped or quietly degrading adherence.
MEMORY_INDEX_LINES = 200
MEMORY_INDEX_BYTES = 25 * 1024
# Cost budget, distinct from the load limit above: the index is resident on every
# turn of every session, so a long entry costs far more than a long file. One line
# per memory, at most this many bytes each, and a byte budget for the whole index
# (vault-method audit, 2026-09-05).
MEMORY_INDEX_ENTRY_BYTES = 300
MEMORY_INDEX_BUDGET_BYTES = 8 * 1024
INSTRUCTION_BUDGET_LINES = 200


def strip_code(text):
    return CODE_SPAN.sub("", FENCE.sub("", text))


def parse_date(value):
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def collect(vault):
    notes = []
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault)
        if any(p in EXEMPT for p in rel.parts) or path.name in SKIP_NAMES:
            continue
        if any(pat in path.name.lower() for pat in CONFLICT_PATTERNS):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        notes.append((path, rel, text, parse_frontmatter(text)))
    return notes


class Out:
    def __init__(self):
        self.n = 0

    def section(self, title, items, why=None):
        if not items:
            print(f"  ok    {title}")
            return
        self.n += len(items)
        print(f"\n  {len(items)}  {title}")
        if why:
            print(f"        {why}")
        for line in items:
            print(f"        - {line}")
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("vault", type=Path)
    ap.add_argument("--stale-days", type=int, default=90)
    ap.add_argument("--proposed-days", type=int, default=30)
    args = ap.parse_args()
    vault, today, out = args.vault, date.today(), Out()

    if not vault.is_dir():
        print(f"Not a directory: {vault}", file=sys.stderr)
        return 2

    notes = collect(vault)
    print(f"Health report for {vault} -- {len(notes)} notes\n")

    # 1. Metadata staleness: the file changed but `updated` did not. This is the
    #    only mechanical proxy for a summary that no longer describes its note.
    drifted = []
    for path, rel, text, fm in notes:
        declared = parse_date(fm.get("updated"))
        if not declared:
            continue
        mtime = date.fromtimestamp(path.stat().st_mtime)
        if (mtime - declared).days > 14:
            drifted.append(f"{rel}  (updated: {declared}, file touched {mtime})")
    out.section(
        "notes edited without updating `updated`", drifted,
        "The summary may no longer describe the note. A stale summary is worse "
        "than none, because the scanning pass trusts it.",
    )

    # 2. Startup context budget. Everything loaded at launch is paid for every
    #    session, and long instruction files reduce adherence.
    budget = []
    for name in ("CLAUDE.md", "AGENTS.md"):
        f = vault / name
        if f.exists():
            n = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
            if n > INSTRUCTION_BUDGET_LINES:
                budget.append(f"{name}: {n} lines (guidance is under {INSTRUCTION_BUDGET_LINES})")
    ctx = vault / "context"
    if ctx.is_dir():
        total = sum(
            len(f.read_text(encoding="utf-8", errors="replace").splitlines())
            for f in ctx.glob("*.md")
        )
        if total > 400:
            budget.append(f"context/ totals {total} lines -- check what root actually imports")
    out.section(
        "instruction files over budget", budget,
        "Imports do not save context; imported files expand at launch.",
    )

    # 3. Memory index overflow. Past the load limit, entries are silently invisible.
    overflow = []
    mem = vault / "memories"
    if mem.is_dir():
        for idx in sorted(mem.glob("*/MEMORY.md")):
            raw = idx.read_text(encoding="utf-8", errors="replace")
            n, b = len(raw.splitlines()), len(raw.encode("utf-8"))
            if n > MEMORY_INDEX_LINES or b > MEMORY_INDEX_BYTES:
                overflow.append(
                    f"{idx.relative_to(vault)}: {n} lines / {b} bytes -- content past "
                    f"the limit never loads"
                )
    out.section("memory indexes over the load limit", overflow,
                "Only the first 200 lines or 25KB enter context. Distill.")

    # 3b. Memory index cost budget. Every byte here is paid on every turn of every
    #     session, so the check is per entry and per file, not the load limit.
    costly = []
    if mem.is_dir():
        for idx in sorted(mem.glob("*/MEMORY.md")):
            raw = idx.read_text(encoding="utf-8", errors="replace")
            b = len(raw.encode("utf-8"))
            if b > MEMORY_INDEX_BUDGET_BYTES:
                costly.append(
                    f"{idx.relative_to(vault)}: {b} bytes (budget {MEMORY_INDEX_BUDGET_BYTES})"
                )
            for line in raw.splitlines():
                n = len(line.encode("utf-8"))
                if line.startswith("- [") and n > MEMORY_INDEX_ENTRY_BYTES:
                    costly.append(
                        f"{idx.relative_to(vault)}: entry of {n} bytes -- {line[:60]}..."
                    )
    out.section(
        "memory index over its cost budget", costly,
        "The index is resident on every turn. One line per memory, under "
        f"{MEMORY_INDEX_ENTRY_BYTES} bytes each and {MEMORY_INDEX_BUDGET_BYTES} bytes in "
        "total; move detail into the topic file.",
    )

    # 4. Buffers accumulating without distillation.
    undistilled = []
    if mem.is_dir():
        for d in sorted(p for p in mem.iterdir() if p.is_dir()):
            files = list(d.glob("*.md"))
            if not files:
                continue
            oldest = min(date.fromtimestamp(f.stat().st_mtime) for f in files)
            age = (today - oldest).days
            if age > 30:
                undistilled.append(
                    f"{d.name}: {len(files)} files, oldest {age} days -- run bbb-memory-distill"
                )
    out.section("memory buffers overdue for distillation", undistilled)

    # 5. Status honesty: active projects nobody has touched. Projects live one
    #    level down, under a domain (ADR-0018): projects/<domain>/<project>/.
    stale = []
    projects = vault / "projects"
    if projects.is_dir():
        for domain in sorted(p for p in projects.iterdir() if p.is_dir()):
            for folder in sorted(p for p in domain.iterdir() if p.is_dir()):
                idx = folder / f"{folder.name}.md"
                if not idx.exists():
                    continue
                fm = parse_frontmatter(idx.read_text(encoding="utf-8", errors="replace"))
                if fm.get("status") != "active":
                    continue
                newest = max(
                    (date.fromtimestamp(f.stat().st_mtime) for f in folder.rglob("*.md")),
                    default=None,
                )
                if newest and (today - newest).days > args.stale_days:
                    stale.append(
                        f"{domain.name}/{folder.name}: marked active, "
                        f"untouched {(today - newest).days} days"
                    )
    out.section(
        "projects marked active but dormant", stale,
        "Either the status is wrong or the project is. Both are worth knowing.",
    )

    # 6. Decisions nobody ever made.
    proposed, orphan_adrs, broken_chain = [], [], []
    adr_ids = set()
    for path, rel, text, fm in notes:
        m = re.match(r"(ADR-\d{4})", path.stem)
        if not m:
            continue
        adr_ids.add(m.group(1))
        created = parse_date(fm.get("created"))
        status = (fm.get("status") or "").strip()
        if status == "proposed" and created and (today - created).days > args.proposed_days:
            proposed.append(f"{path.stem}: proposed {(today - created).days} days ago")
        affects = fm.get("affects") or []
        if isinstance(affects, str):
            affects = [affects] if affects else []
        # A structural decision governs the vault, not any particular note.
        # `scope: foundational` opts out rather than reporting forever.
        if (
            not affects
            and status == "accepted"
            and (fm.get("scope") or "").strip() != "foundational"
        ):
            orphan_adrs.append(f"{path.stem}: accepted but governs no note")
        sup = (fm.get("superseded_by") or "").strip()
        if sup:
            broken_chain.append((path.stem, sup, status))

    out.section(
        "decisions left proposed", proposed,
        "A proposed ADR is a decision nobody made. It may be blocking something.",
    )
    out.section(
        "accepted ADRs governing nothing", orphan_adrs,
        "Fine for foundational decisions. Suspicious for the rest -- the notes may "
        "have been deleted, or nobody declared the decision.",
    )

    chain = []
    for stem, sup, status in broken_chain:
        if sup not in adr_ids:
            chain.append(f"{stem} superseded_by {sup}, which does not exist")
        elif status != "superseded":
            chain.append(f"{stem} has superseded_by but status is '{status}'")
    out.section("broken supersede chains", chain)

    # 7. Reachability. The actual test of the routing invariant: can a human
    #    clicking from the home note arrive at every file?
    # The home note is pinned to BBB.md (ADR-0015): the vault folder's name is
    # machine-local, so deriving the home note's name from it gave the synced
    # note a different expected name on every machine.
    home = vault / "BBB.md" if (vault / "BBB.md").exists() else None
    unreachable = []
    if home:
        by_stem = {p.stem: (p, t, f) for p, _r, t, f in notes}
        seen, queue = {home.stem}, [home.stem]
        while queue:
            stem = queue.pop()
            entry = by_stem.get(stem)
            if not entry:
                continue
            _p, text, fm = entry
            targets = set(LINK.findall(strip_code(text)))
            for key in ("up", "decisions", "affects"):
                v = fm.get(key) or []
                for item in ([v] if isinstance(v, str) else v):
                    targets.add(str(item).strip().strip('[]"'))
            for tgt in targets:
                tgt = tgt.strip().split("/")[-1]
                if tgt and tgt not in seen:
                    seen.add(tgt)
                    queue.append(tgt)
        for path, rel, _t, _f in notes:
            if path.stem not in seen:
                unreachable.append(str(rel))
    out.section(
        "notes unreachable by clicking from the home note", unreachable,
        "Reachable by search only. This is the invariant ADR-0012 claims to hold.",
    )

    # 8. Merge candidates: near-identical summaries mean the append-before-create
    #    rule is being skipped.
    dupes, by_folder = [], defaultdict(list)
    for path, rel, _t, fm in notes:
        # Daily notes have formulaic summaries by design; comparing them produces
        # nothing but noise, and noise trains you to ignore the report.
        if (fm.get("type") or "").strip() == "daily":
            continue
        s = (fm.get("summary") or "").strip().lower()
        if s:
            by_folder[rel.parent].append((path.stem, s))
    for folder, items in by_folder.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                r = SequenceMatcher(None, items[i][1], items[j][1]).ratio()
                if r > 0.75:
                    dupes.append(
                        f"{folder}: '{items[i][0]}' and '{items[j][0]}' ({int(r*100)}% similar)"
                    )
    out.section(
        "possible merge candidates", dupes,
        "Two notes describing the same thing. The index only indexes while "
        "summaries differ.",
    )

    print()
    if out.n:
        print(f"{out.n} thing(s) worth a look. None of these are errors.")
    else:
        print("Nothing worth flagging.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
