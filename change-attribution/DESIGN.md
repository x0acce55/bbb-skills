# Change attribution — final design

**Status:** Settled 2026-08-30. Implemented as the `change-attribution` skill.
**Decided by:** Josiah Nosek (SecOps), over three review rounds taken from the SecOps
and Platform Engineering perspectives.
**Scope:** Infrastructure merge requests in Audacy GitLab — `tf-*`, `gitops-k8s-*`,
`tf-org-v2`, `tf-gcp-*`.

This is the design document, not the operating instructions. For how to apply the scheme,
read `SKILL.md`. For why any individual choice was made, `references/rationale.md` carries
the argument and the evidence index.

---

## Problem

Every infrastructure merge request should answer three questions: which team did this,
what kind of access it touches, and what authorised it. Today none of them are answered
reliably.

Platform Engineering's `iac-request` skill applies `pe:iac-request` to MRs and
`pe-iac-request` plus a `DevOps` label to Jira issues. That watermark assumes all IaC work
belongs to Platform Engineering and is tracked on the DEVOPS board. Much of it is SecOps
work, originating from a Zendesk ticket in the Identity queue or a SECOPS Jira issue, and
carried out in repos Platform Engineering owns.

The result is that provenance (an agent did this) and attribution (which team, which
ticket) are welded together, and the weld puts SecOps changes on the wrong board.

## Design

Three independent axes, applied together as scoped GitLab labels.

| Scope | Values | Presence |
| --- | --- | --- |
| `origin::` | `secops`, `pe` | Always |
| `iam::` | `user`, `group`, `permission-set`, `assignment`, `service-account`, `federation` | Only when the change touches identity |
| `ticket::` | `ZD-<n>`, `SECOPS-<n>`, `none-<reason>` | Always |

Mirrored as trailers in the squash commit message:

```
Change-Origin: secops
Change-IAM: group
Change-Ticket: ZD-12345
```

Labels are lowercase and scoped. GitLab makes values within one scope mutually exclusive,
so a change cannot be both `iam::user` and `iam::group` — that property is what lets the
vocabularies stay closed.

The two records are redundant deliberately. The label is queryable through the GitLab API;
the trailer survives outside GitLab and greps with `git log --grep`.

## The decisions, and what drove them

### Three axes, not chained prefixes

The first draft chained: `secops-iac`, then `secops-iac-group-iam`. That repeats the parent
inside the child, so filtering one dimension means string-matching the other. Origin,
subject and ticket are independent — a SecOps change can touch groups or service accounts,
and either can come from Zendesk or Jira.

### Lowercase, scoped

`groups.yaml` in `tf-org-v2` already treats a lowercase slug as the canonical machine key
("a stable slug used as the Terraform resource key — do not change after import"), with
PascalCase reserved for display names. The estate's tags are split across clouds —
PascalCase `Name`/`Environment`/`BusinessUnit`/`Team` on AWS, lowercase `cost-center`/
`support-url`/`env` on GCP, where labels cannot legally hold uppercase. Lowercase is the
only form that works everywhere, and it matches the convention already in force.

### Origin is a team, and it is configured

Origin cannot be derived from the repo path, because SecOps does IAM work inside
`gcp/devops/` repos that Platform Engineering owns — and that is most of it. Repo ownership
and work ownership are different facts. So origin is read from operator configuration and
never inferred.

`pe` rather than `devops` because they are one team with two names — the plugin's own jira
skill describes the DEVOPS board as being "for Platform Engineering" — and `pe:` is the
prefix that team already established for itself.

### The subject axis mirrors `tf-org-v2`

Four of the six values are the four primitives in that repo's README: `user`, `group`,
`permission-set`, `assignment`. A reviewer reads the same word in the label, the directory
name, and the documentation. `service-account` and `federation` are added for the GCP and
trust cases AWS Identity Center has no equivalent for.

An earlier draft folded assignments into `group`. The README separates them and is right
to: a permission set "on its own does nothing — it must be assigned", so a permission-set
change alters capability and an assignment change alters who holds it. Collapsed together,
the highest-consequence change wears the lowest-consequence label.

### No `iam::none`

Absence is only ambiguous if it depends on someone remembering. CI detects identity changes
from diff content, so an unlabelled IAM change fails the pipeline rather than passing
quietly — which makes absence mechanically verified.

A mandatory `iam::none` on every MR trains everyone to apply it without looking. That is a
worse guarantee than none at all, wearing the costume of a better one.

### Detection reads content, not paths

This is the choice with the widest margin behind it, and it was measured rather than
argued. Across the workspace, **46** files declare IAM resources. **Two** sit under an
`**/iam/**` path.

A path-only glob would have caught 4% of identity changes and silently passed the other 44
— including `tf-gcp-service-accounts/main.tf`, the `gcve-iam` modules, and service-account
bindings under `firebase-app-hosting/`. The GCP terragrunt convention genuinely does put
*project-level* IAM in `<env>/iam/`, which is what makes path detection look reasonable
until it is measured; module- and resource-level IAM lives wherever the resource lives.

Paths are therefore used only as the cheap `changes:` gate deciding whether the job runs.
Diff content decides whether a label is required.

### The ticket axis is mandatory, with an explicit escape

Formatting runs, drift correction and `_modules/` refactors have no authorising ticket and
never will. `ticket::none-fmt`, `none-drift`, `none-refactor` keep the axis mandatory — a
missing label is unambiguously an error — while keeping unticketed changes auditable as a
set. Watching the frequency of `none-*` is a better control than trusting that everything
got a ticket.

### Trailers go in the squash message

`tf-org-v2` uses `merge_method: rebase_merge` with `squash_option: default_off` — squash
is enabled per MR, notably for the `[skip ci]` flow. Either way GitLab writes a merge
commit on top whose message is a template, so the trailer never lands on HEAD, and a
trailer omitted from a squash message is lost entirely. GitLab pre-fills that field from MR creation and it carries through unless
a human overrides it at merge — so creation time is the only reliable moment to set it.

The label survives regardless, which is why a lost trailer degrades the record rather than
breaking it, and why the post-merge check warns instead of blocking.

The commit subject line was rejected as a carrier: length-constrained, and `tf-org-v2`
already spends that space on `[skip ci]`.

## One subject per merge request

The splits in `tf-org-v2` are forced by dependency ordering, not chosen for tidiness.
Terragrunt cannot resolve `dependency.groups.outputs.group_ids["new_key"]` for a group that
has not been applied, and AWS enforces referential integrity against destroying a permission
set that assignments still reference. A combined MR would not be harder to unwind — it would
fail to apply.

The side effect is worth naming: because the ordering is forced, every intermediate state is
access-safe in both directions. The cost is lost atomicity — a three-MR sequence is three
reverts in reverse order, and a partial revert lands in a state no single MR describes. The
`ticket::` label is the compensating control; it is the only join key that reassembles the
sequence.

## Resource attribution

`Change-Resource` carries the **resource name**, qualified by type and location:

```
Change-Resource: gcp_compute_instance/nslt-20260830-vm@us-east4-a
```

An earlier draft proposed joining through labels — MR `ticket::ZD-12345` to GCP
`ticket=zd-12345` — and measurement killed it. NorthStar's `gcp_compute_instance` table
exposes only `label_fingerprint`, a hash: it can see that labels changed and never what
they say. The GCP numeric id is out too (NorthStar keys by its own `res_` id), and that
`res_` id is assigned at ingestion so it cannot be written into a trailer that predates it.

Name is what `search_resources` resolves, and what an engineer already writes in the
Terraform. The join then runs in the direction that works: our trailer names the resource,
NorthStar is queried by that name, and nothing requires NorthStar to read what we write.

`Change-Principal` remains open for IAM-shaped changes — an enhancement, not a blocker.

## Enforcement

Two blocking CI rules, both scoped to identity changes so they never fire on unrelated MRs:
an IAM change must carry an `iam::` and a `ticket::` label, and the ticket label must agree
with the branch name. One post-merge advisory warns when a squash message lost its trailers.

Everything else is generated by the skill rather than checked by CI — rung one of the
enforcement ladder rather than rung three. Every blocking rule is an interruption charged to
whoever is merging, and a third one should have to argue for what it catches that these two
miss.

The label definitions and CI job text are in `references/enforcement.md`, as text for a
human to apply. The skill writes no CI configuration, no label definitions, and no
credentials.

## Relationship to `pe:iac-request`

Left alone. Nothing consumes it — 187 cloned `tf-*` and `gitops-k8s-*` repos contain zero
references to `CI_MERGE_REQUEST_LABELS` — so asking Platform Engineering to delete their own
label buys nothing and costs goodwill. The upstream ask is addition: that their skill also
emit these three axes. Same end state for the data, far less friction.

## Evaluating this yourself

```
git clone github-bbb-agent:x0acce55/bbb-skills.git
cd bbb-skills/change-attribution
```

`SKILL.md` is the operating procedure, `references/rationale.md` carries the argument for
each choice with an evidence index, and `references/enforcement.md` holds the CI and label
text. Every factual claim in the rationale cites where it came from, so it can be re-checked
rather than trusted — including the two that most shaped the design: the 44-of-46 detection
measurement, and the squash-merge trailer behaviour.
