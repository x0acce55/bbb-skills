#!/usr/bin/env python3
"""Regenerate folder index notes in the BBB vault from note frontmatter.

Layout (ADR-0018): projects/<domain>/<project>/. Each domain folder and each
project folder is indexed by a note named after the folder. Everything between
the INDEX:START and INDEX:END markers is generated from frontmatter; everything
outside the markers is hand-written and preserved.

The home note is always BBB.md (ADR-0015) and lists the domains. Each domain
index lists its projects and any loose notes at domain level. Each project
index lists the project's notes.

Usage:
    python build_index.py <vault-root>
    python build_index.py <vault-root> --project <domain>/<name>
    python build_index.py <vault-root> --project <domain>        # whole domain
    python build_index.py <vault-root> --check     # report drift, write nothing
"""

import argparse
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

START = "<!-- INDEX:START -->"
END = "<!-- INDEX:END -->"
HOME_NAME = "BBB.md"  # pinned regardless of the vault folder's name (ADR-0015)
SKIP_NAMES = {"CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "MEMORY.md"}
# Sync clients leave these behind. They are not notes and must never be indexed --
# indexing one would link the vault to a file the user is about to delete.
CONFLICT_PATTERNS = ("conflicted copy", ".sync-conflict-", "conflicted-copy")


def parse_frontmatter(text):
    """Return the frontmatter block as a dict, or {} if absent.

    Deliberately minimal: no YAML dependency, since this has to run on a fresh
    box with nothing installed. Handles the schema's three shapes:

      scalar:        key: value        (quotes stripped)
      inline list:   key: [a, "b"]
      block list:    key:              <- what Obsidian's Properties UI writes
                       - a
                       - "b"

    Obsidian serialises list properties in block style, so a parser that only
    reads inline lists silently loses every edit a human makes in the app
    (the failure ADR-0016 turns into data loss: an unreadable `decisions:`
    field regenerates the ADR's `affects:` to empty). Anything outside the
    schema -- nested maps, multi-line strings -- is skipped without error.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    out = {}
    current = None  # key whose block-list items we are absorbing
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        indented = line[0] in " \t"
        if indented:
            if stripped == "-" or stripped.startswith("- "):
                item = stripped[1:].strip().strip('"').strip("'")
                if current is not None and item:
                    prev = out.get(current)
                    if isinstance(prev, list):
                        prev.append(item)
                    elif prev in ("", None):
                        out[current] = [item]
                    # a scalar followed by list items is invalid YAML; keep the scalar
            # any other nested structure is outside the schema; skip it
            continue
        if ":" not in line:
            current = None
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            out[key] = [
                v.strip().strip('"').strip("'")
                for v in inner.split(",")
                if v.strip()
            ]
            current = None
        elif value == "":
            out[key] = ""  # becomes a list if block items follow
            current = key
        else:
            out[key] = value.strip('"').strip("'")
            current = None
    return out


def is_conflict(path: Path) -> bool:
    return any(pat in path.name.lower() for pat in CONFLICT_PATTERNS)


def collect_notes(folder: Path, index_name: str):
    """Every .md directly in the folder except the index note and tool files."""
    notes = []
    for path in sorted(folder.glob("*.md")):
        if path.name in SKIP_NAMES or path.stem == index_name or is_conflict(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        notes.append((path, parse_frontmatter(text)))
    return notes


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def note_rows(notes):
    rows = ["| Note | Summary | Status | Decisions |", "| --- | --- | --- | --- |"]
    for path, fm in notes:
        summary = escape_cell(fm.get("summary", "") or "") or "**missing summary**"
        status = escape_cell(fm.get("status", "") or "—")
        decisions = fm.get("decisions", [])
        if isinstance(decisions, str):
            decisions = [decisions] if decisions else []
        dec = ", ".join(f"[[{d}]]" for d in decisions) if decisions else "—"
        rows.append(f"| [[{path.stem}]] | {summary} | {status} | {dec} |")
    return rows


def build_table(notes):
    if not notes:
        return "_No notes in this folder yet._"
    return "\n".join(note_rows(notes))


def project_folders(domain: Path):
    return sorted(p for p in domain.iterdir()
                  if p.is_dir() and not p.name.startswith(".") and not is_conflict(p))


def build_domain_block(domain: Path):
    """Projects table plus loose-notes table for one domain folder."""
    parts = []
    proj_rows = ["| Project | Summary | Status |", "| --- | --- | --- |"]
    found = 0
    for folder in project_folders(domain):
        idx = folder / f"{folder.name}.md"
        if not idx.exists():
            proj_rows.append(f"| {folder.name}/ | **missing index note** | — |")
            found += 1
            continue
        fm = parse_frontmatter(idx.read_text(encoding="utf-8", errors="replace"))
        summary = escape_cell(fm.get("summary", "") or "") or "**missing summary**"
        proj_rows.append(
            f"| [[{folder.name}]] | {summary} | {escape_cell(fm.get('status') or '—')} |"
        )
        found += 1
    if found:
        parts.append("### Projects\n\n" + "\n".join(proj_rows))

    loose = collect_notes(domain, domain.name)
    if loose:
        parts.append("### Notes\n\n" + "\n".join(note_rows(loose)))

    if not parts:
        return "_No projects in this domain yet._"
    return "\n\n".join(parts)


def build_adr_table(adrs):
    if not adrs:
        return "_No decisions recorded yet._"
    rows = ["| ADR | Decision | Status | Affects |", "| --- | --- | --- | --- |"]
    for path, fm in adrs:
        summary = escape_cell(fm.get("summary", "") or "") or "**missing summary**"
        status = escape_cell(fm.get("status", "") or "—")
        affects = fm.get("affects", [])
        if isinstance(affects, str):
            affects = [affects] if affects else []
        cleaned = []
        for a in affects:
            stem = a.strip().strip("[]").split("|")[0].split("/")[-1]
            if stem:
                cleaned.append(f"[[{stem}]]")
        rows.append(
            f"| [[{path.stem}]] | {summary} | {status} | "
            f"{', '.join(cleaned) if cleaned else '—'} |"
        )
    return "\n".join(rows)


def sync_adr_refs(vault: Path, check_only: bool):
    """Rebuild every ADR's `affects:` from the `decisions:` fields of the notes.

    Notes are authoritative (ADR-0016). Only the frontmatter is touched; the
    ADR's body -- the argument -- is never written.

    The replacement is block-aware: if Obsidian rewrote `affects:` into block
    style, the indented `- ...` continuation lines are consumed along with the
    key line. Replacing only the key line would orphan the items below it and
    corrupt the frontmatter.
    """
    decisions_dir = vault / "decisions"
    if not decisions_dir.is_dir():
        return "clean", "adr-refs: no decisions/ directory"

    # note stem -> the ADR ids it declares
    claimed = defaultdict(set)
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault)
        if any(part in {"memories", ".claude", ".obsidian", ".git"} for part in rel.parts):
            continue
        if path.name in SKIP_NAMES or is_conflict(path):
            continue
        if re.match(r"ADR-\d{4}", path.stem):
            continue
        fm = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        for d in fm.get("decisions", []) or []:
            d = d.strip()
            if d:
                claimed[d].add(path.stem)

    changed, missing = [], []
    for path in sorted(decisions_dir.glob("ADR-*.md")):
        adr = re.match(r"(ADR-\d{4})", path.stem).group(1)
        want = sorted(claimed.get(adr, set()))
        rendered = "[" + ", ".join(f'"[[{s}]]"' for s in want) + "]"

        text = path.read_text(encoding="utf-8", errors="replace")
        current = parse_frontmatter(text).get("affects", [])
        if isinstance(current, str):
            current = [current] if current else []
        current_stems = sorted(
            {c.strip().strip("[]").split("|")[0].split("/")[-1] for c in current if c.strip()}
        )
        if current_stems == want:
            continue

        # Operate on the frontmatter block only, so an `affects:` inside a
        # fenced example in the body can never be rewritten.
        fm_end = text.find("\n---", 3)
        if not text.startswith("---") or fm_end == -1:
            missing.append(path.name)
            continue
        head, tail = text[:fm_end], text[fm_end:]
        lines = head.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("affects:"):
                j = i + 1
                while (
                    j < len(lines)
                    and lines[j][:1] in (" ", "\t")
                    and lines[j].lstrip().startswith("-")
                ):
                    j += 1
                lines[i:j] = [f"affects: {rendered}"]
                break
        else:
            missing.append(path.name)
            continue

        changed.append(path.name)
        if not check_only:
            path.write_text("\n".join(lines) + tail, encoding="utf-8")

    if missing:
        return "error", f"adr-refs: no affects: field in {', '.join(missing)}"
    if not changed:
        return "clean", "adr-refs: back-references up to date"
    if check_only:
        return "drift", f"adr-refs: {len(changed)} ADR(s) out of date"
    return "written", f"adr-refs: rebuilt {len(changed)} ADR back-reference(s)"


def splice(text: str, generated: str):
    """Replace the block between markers. Returns (new_text, error_or_None)."""
    s = text.find(START)
    e = text.find(END)
    if s == -1 or e == -1:
        return None, f"missing {START} / {END} markers"
    if e < s:
        return None, "END marker appears before START marker"
    return text[: s + len(START)] + "\n" + generated + "\n" + text[e:], None


def bump_updated(text: str) -> str:
    """Set updated: to today in the frontmatter, if the field exists."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    head, tail = text[:end], text[end:]
    lines = head.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("updated:"):
            lines[i] = f"updated: {date.today().isoformat()}"
            return "\n".join(lines) + tail
    return text


def regen(index_path: Path, generated: str, label: str, count_msg: str, check_only: bool):
    original = index_path.read_text(encoding="utf-8", errors="replace")
    new_text, err = splice(original, generated)
    if err:
        return "error", f"{label}: {err}"
    if new_text == original:
        return "clean", f"{label}: up to date ({count_msg})"
    # Bump only when the generated block actually changed, so the date stamp
    # itself never registers as drift on the next --check.
    new_text = bump_updated(new_text)
    if check_only:
        return "drift", f"{label}: out of date ({count_msg})"
    index_path.write_text(new_text, encoding="utf-8")
    return "written", f"{label}: rebuilt ({count_msg})"


def process_project(folder: Path, check_only: bool, label: str = None):
    label = label or folder.name
    index_path = folder / f"{folder.name}.md"
    if not index_path.exists():
        return "missing", f"{label}: no index note at {folder.name}.md"
    notes = collect_notes(folder, folder.name)
    return regen(index_path, build_table(notes), label, f"{len(notes)} notes", check_only)


def process_domain(domain: Path, check_only: bool):
    index_path = domain / f"{domain.name}.md"
    if not index_path.exists():
        return "missing", f"{domain.name}: no domain index note at {domain.name}.md"
    n_proj = len(project_folders(domain))
    n_loose = len(collect_notes(domain, domain.name))
    return regen(
        index_path,
        build_domain_block(domain),
        domain.name,
        f"{n_proj} projects, {n_loose} loose notes",
        check_only,
    )


def process_decisions(vault: Path, check_only: bool):
    folder = vault / "decisions"
    if not folder.is_dir():
        return "clean", "decisions: no decisions/ directory"
    index_path = folder / "decisions.md"
    if not index_path.exists():
        return "missing", "decisions: no index note at decisions.md"
    adrs = []
    for path in sorted(folder.glob("ADR-*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        adrs.append((path, parse_frontmatter(text)))
    return regen(index_path, build_adr_table(adrs), "decisions", f"{len(adrs)} ADRs", check_only)


def process_home(vault: Path, check_only: bool):
    """Generate the home note's domain list.

    The home note is pinned to BBB.md (ADR-0015): the vault folder's name is a
    machine-local property, and a synced note derived from it gets a different
    name on every machine. Reachability runs home -> domain -> project -> note.
    """
    home = vault / HOME_NAME
    if not home.exists():
        return "missing", f"home: no {HOME_NAME} at the vault root"

    rows = ["| Domain | Summary | Status |", "| --- | --- | --- |"]
    projects = vault / "projects"
    found = 0
    if projects.is_dir():
        for domain in sorted(p for p in projects.iterdir()
                             if p.is_dir() and not p.name.startswith(".")):
            idx = domain / f"{domain.name}.md"
            if not idx.exists():
                rows.append(f"| {domain.name}/ | **missing domain index** | — |")
                found += 1
                continue
            fm = parse_frontmatter(idx.read_text(encoding="utf-8", errors="replace"))
            summary = escape_cell(fm.get("summary", "") or "") or "**missing summary**"
            rows.append(
                f"| [[{domain.name}]] | {summary} | {escape_cell(fm.get('status') or '—')} |"
            )
            found += 1
    if (vault / "daily" / "daily.md").exists():
        rows.append("| [[daily]] | Dated capture, newest first. | — |")

    generated = "\n".join(rows) if found or len(rows) > 2 else "_No domains yet._"
    return regen(home, generated, "home", f"{found} domains", check_only)


def process_daily(vault: Path, check_only: bool):
    """Generate the daily index, so dated notes are reachable by clicking."""
    folder = vault / "daily"
    if not folder.is_dir():
        return "clean", "daily: no daily/ directory"
    index_path = folder / "daily.md"
    if not index_path.exists():
        return "missing", "daily: no index note at daily.md"

    entries = []
    for path in sorted(folder.glob("*.md"), reverse=True):
        if path.stem == "daily" or is_conflict(path):
            continue
        fm = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        machine = escape_cell(fm.get("machine", "") or "—")
        entries.append(f"| [[{path.stem}]] | {machine} |")

    generated = (
        "\n".join(["| Date | Machine |", "| --- | --- |"] + entries)
        if entries else "_No daily notes yet._"
    )
    return regen(index_path, generated, "daily", f"{len(entries)} notes", check_only)


def resolve_target(projects: Path, spec: str):
    """--project accepts '<domain>/<name>', a bare domain, or a unique bare project name."""
    if "/" in spec:
        domain_name, _, proj_name = spec.partition("/")
        folder = projects / domain_name / proj_name
        if not folder.is_dir():
            return None, None, f"No such project: {spec}"
        return None, folder, None
    if (projects / spec).is_dir():
        return projects / spec, None, None
    matches = [
        p for d in projects.iterdir() if d.is_dir()
        for p in d.iterdir() if p.is_dir() and p.name == spec
    ]
    if len(matches) == 1:
        return None, matches[0], None
    if not matches:
        return None, None, f"No such domain or project: {spec}"
    opts = ", ".join(f"{m.parent.name}/{m.name}" for m in matches)
    return None, None, f"'{spec}' is ambiguous: {opts} (use domain/name)"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("vault", type=Path)
    ap.add_argument("--project", help="one project (<domain>/<name>) or one whole domain")
    ap.add_argument("--check", action="store_true", help="report drift, write nothing")
    args = ap.parse_args()

    projects = args.vault / "projects"

    if args.project:
        if not projects.is_dir():
            print(f"No projects/ directory under {args.vault}", file=sys.stderr)
            return 2
        domain, folder, err = resolve_target(projects, args.project)
        if err:
            print(err, file=sys.stderr)
            return 2
        results = []
        if domain is not None:
            for p in project_folders(domain):
                results.append((p.name, process_project(p, args.check, f"{domain.name}/{p.name}")))
            results.append((domain.name, process_domain(domain, args.check)))
        else:
            results.append((folder.name, process_project(folder, args.check,
                                                         f"{folder.parent.name}/{folder.name}")))
            results.append((folder.parent.name, process_domain(folder.parent, args.check)))
    else:
        results = [("adr-refs", sync_adr_refs(args.vault, args.check))]
        if projects.is_dir():
            for domain in sorted(p for p in projects.iterdir()
                             if p.is_dir() and not p.name.startswith(".")):
                for p in project_folders(domain):
                    results.append(
                        (p.name, process_project(p, args.check, f"{domain.name}/{p.name}"))
                    )
                results.append((domain.name, process_domain(domain, args.check)))
        results.append(("decisions", process_decisions(args.vault, args.check)))
        results.append(("daily", process_daily(args.vault, args.check)))
        results.append(("home", process_home(args.vault, args.check)))

    problems = 0
    for _name, (state, message) in results:
        prefix = {
            "clean": "  ok  ",
            "written": " built",
            "drift": " DRIFT",
            "missing": "  !!  ",
            "error": "  !!  ",
        }[state]
        print(f"{prefix}  {message}")
        if state in ("drift", "missing", "error"):
            problems += 1

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
