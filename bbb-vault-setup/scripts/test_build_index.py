#!/usr/bin/env python3
"""Integration test for the generators against the domain layout (ADR-0018).

Builds a throwaway vault under a temp directory with:

  - projects/<domain>/<project>/ nesting, two domains
  - one note whose frontmatter is written the way Obsidian's Properties UI
    writes it (block-style lists), declaring `decisions: [ADR-0001]`
  - one ADR whose `affects:` has been rewritten by Obsidian into block style,
    pointing at a stale target

Then asserts:

  1. build_index exits 0 and produces the home -> domain -> project chain
  2. the block-style `decisions:` was read, so ADR-0001's `affects:` is
     regenerated to the real note (the ADR-0016 invariant survives Obsidian)
  3. the block-style `affects:` was replaced as a block -- no orphaned
     "  - " continuation lines left behind in the ADR's frontmatter
  4. a second run reports no drift (idempotent), including --check
  5. check_vault reports the vault clean
  6. a deliberate domain/path mismatch is caught by check_vault, then fixed

Plain python, no pytest:

    python test_build_index.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).parent
FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok    {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL  {name}")
        if detail:
            print(f"        {detail}")


def run(script, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        capture_output=True, text=True,
    )


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_vault(root: Path):
    write(root / ".obsidian" / "app.json", "{}")
    write(root / "BBB.md", (
        "---\ntype: index\nsummary: Home note for the BBB vault. Start here.\n"
        "created: 2026-08-25\nupdated: 2026-08-25\n---\n\n# BBB\n\n"
        "## Decisions\n\n- [[decisions]]\n\n## Domains\n\n"
        "<!-- INDEX:START -->\n<!-- INDEX:END -->\n\n## Daily\n\n- [[daily]]\n"
    ))
    write(root / "decisions" / "decisions.md", (
        "---\ntype: index\nsummary: Index of every ADR.\nup: \"[[BBB]]\"\n"
        "created: 2026-08-25\nupdated: 2026-08-25\n---\n\n# Decisions\n\n"
        "<!-- INDEX:START -->\n<!-- INDEX:END -->\n"
    ))
    # ADR whose affects: Obsidian has rewritten into BLOCK style, and stale.
    write(root / "decisions" / "ADR-0001-test-decision.md", (
        "---\ntype: adr\nstatus: accepted\n"
        "summary: A test decision.\nup: \"[[decisions]]\"\nscope: foundational\n"
        "affects:\n  - \"[[stale-target]]\"\n"
        "created: 2026-08-25\nupdated: 2026-08-25\n---\n\n"
        "# ADR-0001: Test decision\n\n"
        "## Context\n\nBody must never be touched. Not even this fenced example:\n\n"
        "```yaml\naffects: [\"[[decoy]]\"]\n```\n"
    ))
    write(root / "daily" / "daily.md", (
        "---\ntype: index\nsummary: Every daily note, newest first.\nup: \"[[BBB]]\"\n"
        "created: 2026-08-25\nupdated: 2026-08-25\n---\n\n# Daily\n\n"
        "<!-- INDEX:START -->\n<!-- INDEX:END -->\n"
    ))
    write(root / "daily" / "2026-08-25.md", (
        "---\ntype: daily\nsummary: Test day.\nmachine: test-box\n"
        "created: 2026-08-25\nupdated: 2026-08-25\n---\n\nnotes\n"
    ))
    for domain, summary in (("audacy", "Work for Audacy."), ("personal", "Personal projects.")):
        write(root / "projects" / domain / f"{domain}.md", (
            f"---\ntype: index\ndomain: {domain}\nsummary: {summary}\n"
            "up: \"[[BBB]]\"\nstatus: active\ncreated: 2026-08-25\nupdated: 2026-08-25\n---\n\n"
            f"# {domain}\n\n<!-- INDEX:START -->\n<!-- INDEX:END -->\n"
        ))
        write(root / "projects" / domain / "CLAUDE.md", f"@{domain}.md\n")
    write(root / "projects" / "audacy" / "podcast" / "podcast.md", (
        "---\ntype: index\ndomain: audacy\nproject: podcast\n"
        "summary: Audio ingestion pipeline.\nup: \"[[audacy]]\"\nstatus: active\n"
        "created: 2026-08-25\nupdated: 2026-08-25\n---\n\n# podcast\n\n"
        "<!-- INDEX:START -->\n<!-- INDEX:END -->\n"
    ))
    write(root / "projects" / "audacy" / "podcast" / "CLAUDE.md", "@podcast.md\n")
    # The note whose frontmatter is written the way OBSIDIAN writes it.
    write(root / "projects" / "audacy" / "podcast" / "ingest-benchmarks.md", (
        "---\ntype: note\nsummary: Benchmarks of three ingest paths; ffmpeg won.\n"
        "up: \"[[podcast]]\"\ndomain: audacy\nproject: podcast\n"
        "decisions:\n  - ADR-0001\n"
        "tags:\n  - research\n"
        "created: 2026-08-25\nupdated: 2026-08-25\n---\n\nbody\n"
    ))
    # A loose note at domain level.
    write(root / "projects" / "personal" / "reading-list.md", (
        "---\ntype: note\nsummary: Books queued for this year.\nup: \"[[personal]]\"\n"
        "domain: personal\ncreated: 2026-08-25\nupdated: 2026-08-25\n---\n\nbody\n"
    ))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "big-beautiful-brain"  # folder name != BBB on purpose
        make_vault(vault)

        # 1. First build.
        r = run("build_index.py", vault)
        check("build_index exits 0 on first run", r.returncode == 0, r.stdout + r.stderr)

        home = (vault / "BBB.md").read_text(encoding="utf-8")
        check("home note pinned to BBB.md despite folder name",
              "| [[audacy]] |" in home and "| [[personal]] |" in home, home)
        check("home links the daily index", "| [[daily]] |" in home)

        dom = (vault / "projects" / "audacy" / "audacy.md").read_text(encoding="utf-8")
        check("domain index lists its project", "| [[podcast]] |" in dom, dom)
        pers = (vault / "projects" / "personal" / "personal.md").read_text(encoding="utf-8")
        check("domain index lists loose notes", "| [[reading-list]] |" in pers, pers)

        proj = (vault / "projects" / "audacy" / "podcast" / "podcast.md").read_text(encoding="utf-8")
        check("project index lists the note with its ADR",
              "| [[ingest-benchmarks]] |" in proj and "[[ADR-0001]]" in proj, proj)

        # 2 + 3. Block-style decisions was read; block-style affects rebuilt cleanly.
        adr = (vault / "decisions" / "ADR-0001-test-decision.md").read_text(encoding="utf-8")
        fm_end = adr.find("\n---", 3)
        head = adr[:fm_end]
        check("ADR affects regenerated from Obsidian-style decisions field",
              'affects: ["[[ingest-benchmarks]]"]' in head, head)
        check("no orphaned block-list lines left in ADR frontmatter",
              "stale-target" not in head and "\n  -" not in head, head)
        check("ADR body untouched, fenced decoy intact",
              'affects: ["[[decoy]]"]' in adr[fm_end:], "body was modified")

        # 4. Idempotency.
        r2 = run("build_index.py", vault)
        check("second run exits 0", r2.returncode == 0, r2.stdout + r2.stderr)
        check("second run reports everything ok",
              "built" not in r2.stdout and "DRIFT" not in r2.stdout, r2.stdout)
        rc = run("build_index.py", vault, "--check")
        check("--check reports no drift", rc.returncode == 0, rc.stdout)

        # 5. check_vault clean.
        cv = run("check_vault.py", vault)
        check("check_vault reports the vault clean",
              cv.returncode == 0 and "Vault is clean." in cv.stdout,
              cv.stdout + cv.stderr)

        # 6. Placement mismatch is caught, then fixed.
        note = vault / "projects" / "audacy" / "podcast" / "ingest-benchmarks.md"
        good = note.read_text(encoding="utf-8")
        note.write_text(good.replace("domain: audacy", "domain: personal"), encoding="utf-8")
        cv2 = run("check_vault.py", vault)
        check("check_vault flags a domain/path mismatch",
              cv2.returncode == 1 and "placement" in cv2.stdout and "personal" in cv2.stdout,
              cv2.stdout)
        note.write_text(good, encoding="utf-8")
        cv3 = run("check_vault.py", vault)
        check("clean again after fixing the mismatch", cv3.returncode == 0, cv3.stdout)

        # Targeted rebuild forms.
        rp = run("build_index.py", vault, "--project", "audacy/podcast")
        check("--project domain/name works", rp.returncode == 0, rp.stdout + rp.stderr)
        rd = run("build_index.py", vault, "--project", "personal")
        check("--project bare domain works", rd.returncode == 0, rd.stdout + rd.stderr)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} test(s) FAILED: {', '.join(FAILURES)}")
        return 1
    print("All integration tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
