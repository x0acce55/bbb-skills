---
type: adr
status: accepted
summary: Projects are partitioned one level by domain — projects/<domain>/<project>/ — because every scoping mechanism Claude Code has is path-shaped.
up: "[[decisions]]"
scope: foundational
affects: []
created: 2026-08-25
updated: 2026-08-25
---

# ADR-0018: Projects are partitioned by domain

## Context

The vault serves more than one life: at least one employer, personal work, and
— since jobs change — future employers. Three requirements follow. Work and
personal material must be separable for loading, permissions, and credentials.
Leaving a job must be a clean excision of that employer's subtree. And the
scheme must scale by adding a sibling, not by redefining what "work" means.

The deciding constraint is that every scoping mechanism Claude Code offers is
path-shaped: on-demand `CLAUDE.md` loading (ADR-0007), permission rules like
`Edit(projects/audacy/**)`, `.claude/rules` with `paths:` globs, per-directory
`.mcp.json` discovery, and hook matchers. Frontmatter and tags are visible to
Obsidian queries and to the scripts, but they cannot gate what loads, what is
writable, or which credentials attach. A separation that exists only in
metadata is a separation nothing can enforce.

The previous flat `projects/` layout was never recorded as a decision — it was
implicit in the scripts. Testing showed the generators treated any nesting as
silently invisible: nested projects appeared in no index, no home note, and no
dormancy check. This ADR records the layout change and ships with the updated
tooling.

## Decision

One nesting level: `projects/<domain>/<project>/`. A domain is an employer, a
client, or `personal` — the org, not the class, because `work` does not survive
a second job and `audacy` does.

Each domain folder carries `<domain>.md` (a generated index of its projects and
loose notes) and a one-line `CLAUDE.md` containing `@<domain>.md` — the
ADR-0007 pattern applied one level up, so a domain's context loads when work
starts anywhere inside it. The home note lists domains; each domain lists its
projects; reachability (ADR-0012/0017) runs home → domain → project → note.

The path is authoritative for placement. `domain:` and `project:` frontmatter
mirror it for Obsidian queries, and `check_vault.py` reports any disagreement
between the mirror and the path.

## Rejected

**Metadata-only domains (tags or a `domain:` field on a flat layout).** Can be
queried, cannot be enforced. Fails all three requirements the moment an agent
or a permission rule is involved.

**Flat folders with domain-prefixed names (`audacy-podcast/`).** Works for
permission globs and costs no code, but leaves no directory to serve as a
session root, so per-domain `.mcp.json`, per-domain settings, and "launch the
work session in the work tree" have nowhere to live.

**Top-level domain trees (`work-audacy/`, `personal/` beside `context/`).**
Maximal separation, maximal blast radius: every script, `verify_setup.py`'s
core-directory list, and the home-note conventions assume a single `projects/`
root. The single extra path segment buys the same enforcement surface.

**A separate vault per employer.** Not rejected — deferred, and recorded here
as the escalation path. It is the correct move when an employer's policy or
confidentiality requirements forbid commingling work product with a personal
sync account, and ADR-0019 keeps multi-vault operation coherent when that day
comes. Within one vault, domains are the right grain.

## Consequences

Offboarding an employer is `mv projects/<domain>` to an archive or an export —
one subtree, links intact thanks to stem links plus ADR-0014's uniqueness rule.

`build_index.py`, `check_vault.py`, and `health_report.py` were updated with
this ADR and are covered by `scripts/test_build_index.py`. Anything else that
assumes flat `projects/` is a bug.

Domain folders are one more index to keep honest, and generic note names now
collide across employers more often — ADR-0014's prefix convention carries
that weight.

**Open:** whether shared cross-domain resources (a `tools` or `reference`
domain?) deserve a reserved domain name, or whether `context/` already covers
everything genuinely global. Decide when the first genuinely shared project
appears, not before.
