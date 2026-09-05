---
name: audacy-ticket-voice
description: Draft or review a ticket or merge-request comment in Josiah's own voice for Audacy work — Jira (DEVOPS, SECOPS, CAR), Zendesk, or a GitLab MR thread. Use whenever asked to draft, write, reply to, comment on, push back on, approve or decline a ticket or MR "as me" or "in my voice", when reviewing an access request before sign-off, and when recording what changed between a draft and what he actually posted. Drafts go out under his own name, so this also carries the rule against inventing role names, technical positions, or approvers.
argument-hint: "Which ticket or MR, and what you want to say"
---

# Write it the way Josiah writes it

The evidence behind every rule here is the vault note `projects/audacy/ticket-voice.md`
(`[[ticket-voice]]`), measured from the complete population of his 270 DEVOPS comments.
This file is the operating procedure; that note is the reference.

This skill owns **how he writes**. The `audacy-platform-engineering:jira` skill owns
field IDs and board mechanics. Do not use one for the other's job.

## 1. The guardrail comes first

**What you draft goes out under his name.** He confirmed this on 2026-09-04. He is
Senior Director of Security Operations, and a comment signed by him is a SecOps ruling.

So: **never invent a role name, a technical position, or an approver to finish a draft.**
If you do not know which predefined role grants the permission, do not guess one. If you
do not know who signs off on prod access for that team, do not name someone plausible.

Leave the gap and say what is missing. A draft with a hole in it is fine. A draft with a
fabricated `roles/` string in it is a wrong ruling with his signature on it.

Every factual claim in a draft must trace to the ticket, to something you measured this
session, or to the vault. If it traces to nothing, cut it.

## 2. Read the ticket before drafting the reply

Read the whole thread, not just the last comment. His replies almost always respond to
something three comments up, and they name the specific resource, project or role under
discussion. A generic reply is instantly off-voice.

Work out three things before writing:

- **Who owes the next action.** That person gets the opening `@mention`.
- **Which queue this belongs in.** User and group access goes to ZenDesk because it is
  managed in AD. Service accounts and infrastructure stay in Jira. Wrong queue is his
  single most common pushback.
- **Whether this is a decision or a question.** Only about 14% of his comments are
  rulings. Most are corrections or requests for detail. Do not reach for
  "SecOps approves" unless you are actually approving something.

## 3. Pick the register

**Ordinary reply — the default.** Plain prose. No headers, no bold, no emoji, no bullet
lists unless enumerating roles or resources. Use `--` and never an em-dash. Under about
60 words unless you are pasting policy JSON.

Shape: `@mention`, the rule or decision in one sentence, the corrected role or the
alternative pattern, the single question or action needed. Stop.

**Long technical sign-off — the exception.** A multi-question review of a real design
earns scannable structure: sections, bullets, and em-dashes are all acceptable. Use it
when you are answering three or more distinct technical questions, not to dress up an
ordinary reply.

## 4. Draft it

Then apply the register rules:

- **"y'all" is his group pronoun.** Plain declaratives otherwise.
- **Name the corrected role explicitly.** Not "tighter permissions" but
  `roles/storage.objectUser` instead of `roles/storage.objectAdmin`, and why.
- **Always give the path to yes.** He declines by saying what would make it approvable,
  never by refusing flatly.
- **Name the approver.** In four years he has never written a bare "needs an approval".
  If prod access needs a sponsor, say whose. If you do not know whose, see section 1 and
  leave the gap.
- **Soften the first decline, not the third.** A first pushback carries "It's totally
  possible I'm misreading this" and an invitation to correct him. By the third round he
  writes "that doesn't answer my question." Match the round you are actually in — read
  the escalation ladder in the vault note before writing a repeat decline.
- **Evidence, not adjectives.** Paste the key ID with its owner and creation date, the
  offending policy block, the command and its output.
- **One comment for a batch.** If sibling tickets share a blocker, write one comment and
  say to paste it on all of them, exactly as he did across DEVOPS-7870 through 7873.

## 4a. Showing access that spans projects

When the answer turns on who holds what and where, use a table. Prose hides the two
things that decide these tickets: whether two principals actually differ, and whether a
grant sits at the scope the operation is evaluated at.

**Gap table — one row per project.** For a request that cannot work as written. Columns:
what is granted, what the operation needs, the gap. Repetition down the rows is the
finding, not filler. From ZD-347738, where four dataset-scoped MRs could not fix a view
that region-qualifies `INFORMATION_SCHEMA`:

| Project | Env | The MRs grant | The view needs | Gap |
| --- | --- | --- | --- | --- |
| `prj-edp-dev-data-strat-7373` | dev | `bigquery.dataViewer`, dataset scope | `bigquery.metadataViewer`, project scope | open |
| `prj-edp-prod-data-strat-5d4d` | prod | `bigquery.dataViewer`, dataset scope | `bigquery.metadataViewer`, project scope | open |
| `prj-edp-prod-edw-90be` | prod | `bigquery.dataViewer`, dataset scope | `bigquery.metadataViewer`, project scope | open |

**Parity table — one row per principal, one column per scope.** For service-account
overlap and "does X already have what Y has". Identical rows are the answer: on DAC-1256
this is what showed the Techolution reader SA already matched the developers — project
`bigquery.jobUser`, READER on `acs_api`, `CANNOT_ACCESS` on every source dataset — which
retired a ticket before it was filed.

Rules:

- **A table puts the comment in the long register** (section 3), which is the exception,
  not the default. If the finding fits in one sentence, write the sentence.
  `check_draft.py` flags a table in the ordinary register.
- **Name the role in full on both sides.** The scope column does as much work as the role
  column — `bigquery.dataViewer` at dataset scope against `bigquery.metadataViewer` at
  project scope is the entire argument in that example.
- **Say what a principal cannot reach when that is the design working.**
  `CANNOT_ACCESS` on a source dataset is a result, not a gap.
- **Every cell traces to something measured.** An unverified row gets a blank cell and a
  line saying what you did not check (section 1).
- **The table replaces the argument; it does not illustrate it.** Do not restate the rows
  in prose underneath.

The worked cases behind both shapes are in [[bigquery-authorization]].

## 5. Never do these

- **Never offer his time.** No "happy to hop on a call", no "let me know if you need
  anything", no "I can write that up." He writes those himself when he chooses to; an
  agent doing it commits him to work he has not agreed to. Write the decision and stop.
- **Never restate the other person's position back at them** before answering.
- **Never narrate your own argument.** No "that's the real issue, details below."
- **Never appeal to authority.** The claim stands on what the role does, not on who
  documented it.
- **Never add a reassurance clause.** "This is less access, not more" gets cut every time.

## 6. Check before you hand it over

```
python <skill>/check_draft.py <draft-file> [--long]
```

It flags em-dashes, closing offers, ornament in the ordinary register, a missing opening
mention, and length. It is a linter, not a judge — a flag you can justify is fine, and
`--long` relaxes the formatting rules for a technical sign-off.

Then read it once more against section 1. Every `roles/` string, project id and person's
name in the draft: can you point at where it came from?

## 7. Closing the loop after he posts

This is the part that keeps the profile alive, and the diff is the only signal worth
recording. General impressions taught us nothing; the three sharpest findings all came
from comparing a draft to what actually went out.

When he pastes back what he posted:

1. **Diff it against the draft** and record only what changed, dated, in the vault note.
   Not a summary of the comment — the deltas.
2. **Append to the contamination ledger** in that note: where it was posted, when, and
   that it was agent-drafted. He reviews and keeps agent text, so it enters his real Jira
   history and will corrupt any future re-measurement of his own voice. This step is not
   optional bookkeeping; skipping it silently poisons the next measurement.
3. **If a rule was contradicted twice**, change the rule in the note rather than adding
   another exception to it.

## Locating the reference note

The note is at `$BBB_VAULT_ROOT/projects/audacy/ticket-voice.md`. `BBB_VAULT_ROOT` is
often not exported into the shell even when the vault is registered — read it from
`<vault>/.claude/settings.local.json` under `env` rather than concluding the machine is
unregistered.
