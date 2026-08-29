---
name: bbb-brainstorm
description: Run a grilling brainstorm session and capture it as a note in the BBB vault under projects/personal/brainstorming/. Use when the user wants to brainstorm, set goals, or scope a personal project and keep the session.
argument-hint: "What do you want to brainstorm?"
---

Run a brainstorming session and save it to the BBB vault. This wraps the `grilling`
skill (from mattpocock/skills) with BBB capture conventions. Do not edit the grilling
skill itself; adaptation lives here.

## 1. Interview

Call the Skill tool with "grilling". Treat the arguments (if any) as the topic to
grill about; otherwise ask for the topic first. Run the session to completion: the
frontier is empty and the user confirms shared understanding.

## 2. Capture

When the session ends (or the user says to save early), write it into the vault at
`$BBB_VAULT_ROOT/projects/personal/brainstorming/`.

Follow the vault's append-before-create rule: read the folder's index note
(`brainstorming.md`) first. If an existing note's summary already covers this topic,
append a dated `## YYYY-MM-DD` section and update its `summary` and `updated` fields.
Only create a new note for a genuinely new topic.

A new note needs the standard frontmatter (see `bbb-vault-setup` conventions):

```markdown
---
type: note
domain: personal
project: brainstorming
summary: <one sentence: the question grilled and where it landed>
up: "[[brainstorming]]"
created: <today>
updated: <today>
---
```

Structure the body as decisions, not transcript:

- **Question** — what was being brainstormed and why now.
- **Resolved** — each settled branch as a bullet: the decision and the one-line why.
- **Open** — branches deliberately left unresolved.
- **Next actions** — concrete steps, if any emerged.

Link related vault notes inline with `[[wikilinks]]` where the prose explains the
relation.

## 3. Reindex and propose promotions

Regenerate the index so the note is reachable:

```
python3 ~/.claude/skills/bbb-vault-setup/scripts/build_index.py "$BBB_VAULT_ROOT" --project personal/brainstorming
```

Then, if the session produced something durable, propose — never do unasked:

- a goal → suggest adding it to `context/goals.md` (user edits context themselves)
- a real project → offer to scaffold it via `bbb-vault-setup`
- a hard-to-reverse decision → offer an ADR

