---
name: bbb-vault-setup
description: Scaffold and maintain the BBB Obsidian vault: frontmatter, up-links, generated indexes, ADRs, AGENTS.md/CLAUDE.md, machine registration, auto-memory wiring. Use for any vault or second-brain structure work: add a note or project, write or link an ADR, regenerate indexes, check orphans.
---

# BBB vault setup and maintenance

The BBB vault is an Obsidian vault that doubles as a working directory for coding
agents. It serves two readers who see different things. A human in Obsidian gets
backlinks, a graph, and clickable properties. An agent reading raw markdown off disk
gets the text and the forward links, and nothing else. Nearly every convention here
exists to keep both readers served by the same file.

## Step 1: establish the environment

Do this first, every time the vault is scaffolded on a new machine. Do not assume a
path or an operating system — this vault is used from more than one machine, and the
answers differ per machine.

Ask the user:

1. **Which operating system?** Windows, macOS, or Linux.
2. **Where is the vault?** Full absolute path to the vault root.
3. **Does this vault sync to other machines?** If yes, by what — Obsidian Sync, git,
   Syncthing, OneDrive, Dropbox? This determines the memory configuration and is not
   optional; getting it wrong produces conflicted copies later.
4. **A short machine identifier.** Something stable and filesystem-safe:
   `desktop-win`, `macbook`, `work-laptop`. Used to scope this machine's memory buffer.
5. **Initial domains.** Work under `projects/` is partitioned by domain — an employer,
   a client, or `personal` (ADR-0018). At minimum `personal` plus one per employer.
   Name the org, not the class: `audacy`, not `work`.
6. **A short vault identifier.** A stable name for this vault, independent of its
   folder path — `bbb` unless the user runs several vaults. Sessions use it to tell
   vaults apart (ADR-0019).

Then verify rather than trust: list the path and confirm it exists and looks like a
vault. If the user gives a path under OneDrive, Dropbox, or Google Drive, say so
directly — a folder where an agent writes rapidly and a cloud client syncs continuously
produces conflict-copy files scattered through the notes.

Record the answers in `context/stack-and-conventions.md` under an **Environment**
heading, one block per machine, so the vault carries its own deployment notes:

```markdown
## Environment

### desktop-win
- OS: Windows 11
- Vault root: C:\Users\Admin\Obsidian\big-beautiful-brain\BBB
- Sync: Obsidian Sync
- Shell: Git Bash via Git for Windows
```

Path formats follow from the OS answer and are easy to get wrong: Windows paths inside
`settings.json` need doubled backslashes, because that file is JSON and a lone backslash
escapes the next character.

## Step 2: verify what's already there

Before scaffolding anything, find out what exists:

```
python scripts/verify_setup.py [vault-root]
```

It locates the vault from the argument, then `$BBB_VAULT_ROOT`, then by walking up from
the current directory looking for `.obsidian/`. Then it reports whether the vault was
found and whether this machine is registered against it.

Report the result to the user in plain terms — "vault found at X, this machine is
registered" or "vault found, this machine is not registered yet" — rather than dumping
the output silently. Knowing which of those two states they're in determines everything
that follows.

Branch on the exit code:

| Code | Meaning | Do this |
| --- | --- | --- |
| 0 | Vault found, machine registered | Go straight to the task |
| 4 | Vault found, machine not registered | **Register this machine** (Step 3) |
| 5 | Vault not found | **First-time scaffold** |
| 1 | Found but something is broken | Report the specific failures and fix them |

Never overwrite an existing `context/` file, `AGENTS.md`, or any ADR without asking.
Those accumulate the user's own writing.

## Step 3: register this machine

Every machine that touches the vault gets a `.claude/settings.local.json`. This is what
makes the vault self-locating and gives each machine its own memory buffer.

Copy `assets/claude/settings.local.json` to `<vault>/.claude/settings.local.json` and
replace the placeholders with the absolute vault path and the machine and vault
identifiers from Step 1:

```json
{
  "autoMemoryDirectory": "C:\\Users\\Admin\\Obsidian\\big-beautiful-brain\\BBB\\memories\\desktop-win",
  "env": {
    "BBB_VAULT_ROOT": "C:\\Users\\Admin\\Obsidian\\big-beautiful-brain\\BBB",
    "BBB_MACHINE_ID": "desktop-win",
    "BBB_VAULT_ID": "bbb",
    "BBB_SETUP_SKILL": "bbb-vault-setup",
    "BBB_SETUP_SOURCE": "github-bbb-agent:x0acce55/bbb-skills.git"
  }
}
```

Windows paths are doubled-backslashed because the file is JSON. On macOS or Linux use a
plain absolute path or one starting with `~/`.

`env` values are exported into the session, so `$BBB_VAULT_ROOT` is available to any
command the agent runs and the vault becomes locatable from any working directory.
`BBB_SETUP_SOURCE` is the clone URL this skill came from: the bbb-skills repo through
the standard per-machine host alias, `github-bbb-agent:x0acce55/bbb-skills.git` (see
the vault's machine-onboarding note, § Skills repo and SSH key). `verify_setup.py`
warns while it is empty.

Then create `memories/<machine-id>/`, copy `assets/gitignore` to `<vault>/.gitignore` if
the vault is a git repo, and confirm with `verify_setup.py` that it now exits 0.

**`settings.local.json` must be excluded from sync.** If it reaches another machine,
that machine inherits this one's memory path and the per-machine separation silently
collapses. `verify_setup.py` checks this. `.gitignore` covers it for git; under
Obsidian Sync the exclusion is automatic, because Obsidian Sync never syncs hidden
files or folders — which also means nothing under `.claude/` reaches other machines
that way, and each machine gets its config from this skill. For Syncthing or a cloud
client, add the exclusion in that client's settings explicitly.

## What to do next

- Vault not found → **First-time scaffold** below.
- Vault found, machine unregistered → Step 3 only. Do not re-scaffold.
- Everything green → go to the task: **Add a project**, **Add a note**, **Record a
  decision**, **Regenerate indexes**, **Check the vault**.

## The shape

```
BBB/
├── BBB.md                     # home note, links to everything
├── AGENTS.md                  # all instructions. Agent-agnostic.
├── CLAUDE.md                  # @AGENTS.md + Claude-only additions
├── .claude/
│   ├── settings.json          # shared config
│   └── settings.local.json    # this machine's memory path. Not synced.
├── context/                   # background the user writes. Assume true.
├── decisions/
│   ├── decisions.md           # generated ADR index
│   └── ADR-0001-....md
├── projects/
│   └── <domain>/              # an employer, a client, or `personal`
│       ├── <domain>.md        # domain index, generated block inside
│       ├── CLAUDE.md          # one line: @<domain>.md
│       └── <project>/
│           ├── <project>.md   # project index, generated block inside
│           ├── CLAUDE.md      # one line: @<project>.md
│           └── ...notes
├── daily/                     # YYYY-MM-DD.md
└── memories/
    ├── <machine-id>/          # one buffer per machine. Never shared.
    └── .lock.json             # held only during distillation
```

Read `references/conventions.md` before writing any note — frontmatter schema, naming,
linking, and the append-before-create rule. Read `references/claude-code-config.md`
before touching `CLAUDE.md`, `AGENTS.md`, or settings. Read
`references/memory-protocol.md` before touching anything under `memories/`.

## First-time scaffold

1. Create the directories above, using the path from Step 1.
2. Copy `assets/AGENTS.md`, `assets/CLAUDE.md`, and `assets/BBB.md` to the vault root.
   The home note is always `BBB.md`, whatever the vault folder is called — the folder
   name is machine-local and the note is synced (ADR-0015). Never rename it.
3. Copy `assets/context/` into `context/`, then fill in **Environment** from Step 1.
   Walk the user through `about-me.md` and `goals.md` interactively; a context file
   nobody filled in is worse than none, because it looks answered.
4. Copy every ADR from `assets/decisions/` into `decisions/`. These record the decisions
   that produced this structure. Several contain `**Open:**` markers — surface those to
   the user rather than letting them sit.
5. Copy `assets/claude/settings.json` to `<vault>/.claude/settings.json`, then register
   this machine per Step 3.
6. Copy `assets/gitignore` to `<vault>/.gitignore`.
7. Create each initial domain from Step 1 — see **Add a domain** below.
8. Run `python scripts/build_index.py <vault>`, then `python scripts/check_vault.py
   <vault>`, then `python scripts/verify_setup.py <vault>`, and report all three.

Then tell the user to create one real project inside a domain and let the conventions
prove themselves before scaffolding ten empty folders.

## Setting up on an additional machine

`verify_setup.py` exits 4 here: the vault is present and synced, but this machine isn't
registered. Do not re-scaffold — everything shared already exists.

1. Run Step 1 and append this machine's block to **Environment** in
   `context/stack-and-conventions.md`.
2. Run Step 3 with this machine's identifier.
3. Run `check_vault.py` to confirm nothing arrived broken through sync, and
   `verify_setup.py` to confirm registration took.

## Add a domain

```
projects/<kebab-case-org>/
├── <kebab-case-org>.md     # domain index, from assets/templates/domain-index.md
└── CLAUDE.md               # contains exactly: @<kebab-case-org>.md
```

A domain is an employer, a client, or `personal` — the org, not the class, because
`work` does not survive a second job (ADR-0018). Set the index's `up:` to `[[BBB]]`
and its `domain:` to the folder name, then regenerate: the home note lists domains
from disk.

## Add a project

```
projects/<domain>/<kebab-case-name>/
├── <kebab-case-name>.md    # project index, from assets/templates/index-note.md
└── CLAUDE.md               # contains exactly: @<kebab-case-name>.md
```

The one-line `CLAUDE.md` is the loading mechanism. Claude Code pulls in subdirectory
`CLAUDE.md` files when it reads files in that directory, so the domain's context loads
when work starts anywhere inside the domain, and the project's on top of it when work
starts in the project — and neither costs anything otherwise. It holds no instructions
of its own, only a pointer, so the substance stays in the index note where any agent
can read it.

In the project index set `up:` to the domain index (`"[[<domain>]]"`) and fill
`domain:` and `project:` to mirror the path — the path is authoritative and
`check_vault.py` reports disagreement. Then regenerate; never hand-edit an index
table.

## Add a note

**First check whether you need a new file at all.** Read the folder's index and look for
an existing note whose `summary` already covers this topic. If one exists, append a
dated section to it and update its `summary` and `updated` fields instead of creating a
sibling. A vault of many thin files is harder to navigate, not easier, and every new
file is another thing to index, link, and keep honest.

Create a new note when the topic genuinely doesn't belong under an existing summary —
not merely because the content is new.

When you do create one, copy the frontmatter from `assets/templates/note.md` and fill in
`summary` first: the single sentence you'd want to read when deciding whether to open
the file. That sentence is the file's context index. Set `up:` to the folder's index
note so a human can click back out, then regenerate the index.

Never hand-add the link to the index. If the generated block is wrong, the frontmatter
or the generator is wrong.

## Record a decision

`decisions/ADR-NNNN-kebab-title.md`, sequential, from `assets/templates/adr.md`.

ADRs are append-only. To change a decision, write a new ADR and set `superseded_by` on
the old one. Do not rewrite an accepted ADR — the ledger's value is that it records what
was believed at the time, including what turned out to be wrong.

Cross-reference in both directions, because an agent cannot see backlinks:

- In the ADR: `affects: ["[[some-note]]"]`
- In each affected note: `decisions: [ADR-0004]`
- Inline `[[ADR-0004-...]]` in a body **only** where the prose invokes the decision.
  Frontmatter carries the relationship; prose carries the argument.

`check_vault.py` reconciles the directions and reports asymmetry.

## Regenerate indexes

```
python scripts/build_index.py <vault>                             # everything
python scripts/build_index.py <vault> --project <domain>/<name>   # one project
python scripts/build_index.py <vault> --project <domain>          # one whole domain
python scripts/build_index.py <vault> --check                     # report drift only
```

Rebuilds five things from frontmatter: each project's index note, each domain's index
note (its projects plus any loose notes), `decisions/decisions.md`, `daily/daily.md`,
and the home note's domain list. It also regenerates every ADR's
`affects:` field from the `decisions:` fields of the notes that declare it — notes are
authoritative, so the two directions cannot disagree. This is what makes "traversing the index touches every file" hold: the index is a
function of the folder's contents, not a list someone remembered to update.

Run it after adding, renaming, or deleting any note.

## Maintenance rhythm

Two checks at different cadences, because they catch different kinds of decay.

| When | Command | Catches |
| --- | --- | --- |
| After any batch of edits | `build_index.py` then `check_vault.py` | Structural breakage. Seconds to run. |
| Monthly, or when the vault feels untrustworthy | `health_report.py` | Semantic rot: stale summaries, dormant projects marked active, decisions left proposed, notes unreachable by clicking, context over budget |
| Weekly | `bbb-memory-distill` | Buffers accumulating without promotion |
| Quarterly | Read `context/goals.md` and prune | A goals file unchanged in a year is unread |

The health report reports nothing as an error. Every finding is a prompt for a judgment
the tooling cannot make -- whether a project is genuinely paused, whether a summary still
describes its note. Present them to the user that way rather than as failures.

### The enforcement ladder

When something drifts, ask which rung it is on before adding another check:

1. **Impossible** -- generated from one source. Index notes, ADR back-references.
2. **Blocked** -- a hook, enforced regardless of what an agent decides.
3. **Detected** -- a check script. Visible, but needs a human to act.
4. **Noticed** -- eventually, by someone. Where you do not want to be.

Move things up when you can. A rule that keeps being broken is usually a rule that should
have been generated instead of written down. That is what happened to ADR-0005, which
required both directions of a decision reference to be hand-written and drifted within
twenty minutes; [[ADR-0016-back-references-are-generated]] replaced the rule with a
generator and the drift became impossible rather than merely visible.

## Check the vault

```
python scripts/check_vault.py <vault>
```

Reports notes missing frontmatter, summaries, or `up:` links; ADR cross-reference
asymmetry; duplicate basenames that break Obsidian's vault-global link resolution;
broken links; index drift; ADR numbering gaps; sync-conflict files; and stale memory
locks.

Run after any batch of edits, and whenever the user says the vault feels messy.

A note on enforcement: `AGENTS.md` and `CLAUDE.md` are context, not configuration. They
shape behaviour and guarantee nothing. If the user wants these invariants enforced
rather than encouraged, the mechanism is a `PostToolUse` hook running `build_index.py`
after writes under `projects/`. Offer it once the conventions stop moving — a hook wired
to a convention still in flux breaks every time the convention moves.

## Reference files

- `references/conventions.md` — frontmatter schema, naming, linking, append-before-create
- `references/claude-code-config.md` — instruction loading, settings, per-machine config
- `references/memory-protocol.md` — memory buffers, the lock, distillation
- `assets/` — files to copy into the vault
- `scripts/verify_setup.py` — is the vault here and is this machine wired to it
- `scripts/build_index.py` — regenerates every derived thing
- `scripts/check_vault.py` — fast structural check, run constantly
- `scripts/health_report.py` — slow semantic check, run monthly
- `scripts/memlock.py` — the distillation lock
- `scripts/test_frontmatter.py`, `scripts/test_build_index.py` — the generators' test
  suites; plain python, no dependencies. Run both after changing any script, and once
  on any new machine to prove the environment: the frontmatter tests pin the parser to
  what Obsidian's Properties UI actually writes (block-style lists), which is the bug
  class that silently emptied ADR back-references before it was caught.
