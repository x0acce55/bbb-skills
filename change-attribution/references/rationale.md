# Rationale

Why each axis is shaped the way it is. Read this before changing the vocabulary — most
of these choices were made against a specific piece of evidence, and the evidence is
cited so it can be re-checked rather than trusted.

Settled 2026-08-30 over three rounds of review, from the SecOps and Platform
Engineering perspectives.

## Why three axes instead of prefix chains

The first draft chained prefixes: `secops-iac`, then `secops-iac-group-iam`. That
repeats the parent inside the child, so filtering one dimension means string-matching
the other. Origin, subject and ticket are independent facts — a SecOps change can touch
groups or service accounts, and either can come from Zendesk or Jira. Three scopes,
applied together, each filterable alone.

## Why lowercase scoped labels

`groups.yaml` already treats a lowercase slug as the canonical machine key
("a stable slug used as the Terraform resource key — do not change after import") with
PascalCase reserved for `display_name`. The estate's tags are split — PascalCase `Name`,
`Environment`, `BusinessUnit`, `Team` on AWS; lowercase `cost-center`, `support-url`,
`env` on GCP, which cannot legally hold uppercase in a label. Lowercase is the only form
that works everywhere, and it matches the convention already in force.

`^(origin|iam|ticket)::[a-z0-9-]+$` has no case-folding branch.

## Why origin names a team, and why it is configured

The first draft mixed kinds: `origin::secops` is a team, `origin::landing-zone` is a
repo. An axis answering two questions answers both badly.

Team is the question both audiences actually ask — SecOps wants "did my team authorise
this", PE wants "is this mine to review". Repo is already visible on the MR, so
encoding it in a label is redundant.

Origin cannot be derived from the repo path, because SecOps does IAM work inside
`gcp/devops/` repos that PE owns, and that is most of it. Repo ownership and work
ownership are different facts. So origin comes from operator configuration, and the
skill never infers it.

## Why `pe` and not `devops`

They are one team with two names: the plugin's jira skill describes the DEVOPS board as
being "for Platform Engineering", the GitLab group is `devops`, the Jira key is
`DEVOPS`, and the team's own marketplace is `audacy-platform-engineering` at
platform-engineering@audacy.com. Two labels for one team is a defect.

`pe` wins because teams name themselves, and `pe:` is the prefix they already
established. `devops` would name them by a legacy path.

## Why the subject axis mirrors tf-org-v2

Four of the six values — `user`, `group`, `permission-set`, `assignment` — are the four
primitives in Simon's README. A reviewer reads the same word in the label, the
directory name, and the documentation. `service-account` and `federation` are added for
the GCP and trust cases AWS Identity Center has no equivalent for.

The draft's `iam::group` originally covered assignments too. Simon's model separates
them, and it is right to: a permission set "on its own does nothing — it must be
assigned", so a permission-set change alters capability and an assignment change alters
who holds it. Collapsed together, the highest-consequence change wears the
lowest-consequence label.

## Why there is no `iam::none`

Absence is only ambiguous if it relies on someone remembering. CI detects identity
changes from diff content, so an unlabelled IAM change is a pipeline failure rather than
a silence. That makes absence mechanically verified.

The alternative — a mandatory `iam::none` on every MR — trains everyone to apply it
without looking, which is a worse guarantee than none at all, dressed as a better one.

## Why the ticket axis is mandatory but has an escape

Formatting runs, drift correction and `_modules/` refactors have no authorising ticket
and never will. Without an escape they get a fake ticket or block the merge.

`ticket::none-<reason>` keeps the axis mandatory — a missing label is unambiguously an
error — while making unticketed changes auditable as a set. Watching the frequency of
`none-*` is a better control than trusting that everything got a ticket.

## Why MRs split by subject, and what that costs

Simon's `AGENTS.md` gives the reason, and it is not reversibility: the splits are forced.
Terragrunt cannot resolve `dependency.groups.outputs.group_ids["new_key"]` for a group
that has not been applied, and AWS enforces referential integrity against destroying a
permission set that assignments still reference. A single combined MR would not be harder
to unwind — it would fail to apply.

The valuable side effect is that the forced ordering makes every intermediate state
access-safe in both directions. The cost is lost atomicity: a 3-MR sequence is 3 reverts
in reverse order, and a partial revert lands in a state no single MR describes. The
`ticket::` label is the compensating control — it is the only join key that reassembles
the sequence.

## On Simon's permission-set deletion rule

Two things are bundled in `AGENTS.md` and the skill separates them deliberately.

The **technical fact** is durable: replacing a PS mints a new ARN, and downstream mappings
to the old ARN break silently. That is AWS behaviour and belongs in the skill as a
standing caution.

The **process gate** — deletion requires Simon's written instruction — is a temporary
control while he runs a cleanup pass, and it is stated in the repo as a hard rule. The
skill surfaces it as context so whoever is deciding knows it exists, but does not treat
it as authority. Simon is a contractor working on IAM under the SecOps team; Josiah owns
this work and his decision settles it. An agent should never present a contractor's
process gate as though it outranked the person it is working for, and never block on it.

## Why detection is content-based, not path-based

This is the choice with the widest margin behind it. Across the workspace, 46 files
declare IAM resources. **Two** of them sit under an `**/iam/**` path. A path-only glob
would have caught 4% of identity changes and silently passed the other 44 — including
`tf-gcp-service-accounts/main.tf`, several `gcve-iam` modules, and service-account
bindings under `firebase-app-hosting/`.

The GCP terragrunt convention genuinely does put project-level IAM in `<env>/iam/`, which
is what makes path detection look reasonable until it is measured. Module-level and
resource-level IAM lives wherever the resource lives.

So paths are used only as the cheap `changes:` gate deciding whether the job runs at all;
the diff content decides whether a label is required. Path globs are also evadable by
declaring a binding in an unexpected file, which is exactly the change most worth
labelling.

## Why the trailer goes in the squash message

`tf-org-v2` is `merge_method: rebase_merge` with `squash_option: default_off` — verified
via the API 2026-08-30, correcting an earlier draft of this file that called squash
standing practice. Squash is opt-in per MR, notably for the `[skip ci]` flow.
A trailer on a branch commit does not survive a squash merge unless it is in the squash
message itself. GitLab pre-fills that field from MR creation and it carries through
unless a human overrides it at merge — so creation time is the only reliable moment to
set it.

The label survives regardless, which is why a lost trailer degrades the record instead
of breaking it, and why the post-merge check warns rather than blocks.

## Why the subject line was rejected as a carrier

Length-constrained, and `tf-org-v2` already spends its subject-line real estate on
`[skip ci]`. Structured attribution there would compete with an existing convention for
the same characters.

## Why `Change-Resource` carries a name, not a label or an id

Measured 2026-08-30 against a live resource, which overturned the answer this file
previously carried.

The earlier draft proposed joining an MR to its resource through labels — MR
`ticket::ZD-12345` mapping to GCP `ticket=zd-12345`, which NorthStar would read. **That
does not work.** `describe_table(gcp_compute_instance)` exposes only `label_fingerprint`,
a hash; `labels`, `tags` and `annotations` are not columns. NorthStar can see that labels
changed and never what they say. The mapping was sound in both directions we controlled
and failed on the one we did not.

Three candidates fall away:

- **GCP labels** — not modelled, per above.
- **The GCP numeric id** — NorthStar keys the instance as `res_65704999219`, not
  `5500821878962258694`.
- **NorthStar's `res_` id** — assigned at ingestion, so it does not exist when the MR is
  opened and cannot be written into a trailer.

What survives is the **resource name**: `search_resources` resolved the VM by name, and a
name is knowable at MR time because an engineer writes it in the Terraform.

```
Change-Resource: gcp_compute_instance/nslt-20260830-vm@us-east4-a
```

Type and zone qualify it enough to disambiguate. The join then runs in the direction that
works — our trailer names the resource and NorthStar is queried by that name — and never
requires NorthStar to read anything we write. That independence is worth more than the
elegance of the label mapping it replaces.

### The MR half already works

`search_tables` confirms no table anywhere exposes GCP resource-label key/values — but it
also shows `gitlab_issue.labels`, which means **NorthStar ingests GitLab labels**. So
`origin::secops`, `iam::group` and `ticket::ZD-12345` are consumable by NorthStar today,
with no work from them. The half of the join that looked speculative is the half that
already works; only the cloud-resource half needed replacing.

Beware two lookalikes: `unified_ticket` normalized tags are work-item tags, and
`gcp_folder` tag inheritance is Resource-Manager Tags bound by org policy — neither is the
free-form resource label being set here.

### Do not bake attribution into resource names

The obvious move from NorthStar's side is to encode the ticket into the resource name so
the join needs no trailer at all. Reject it:

- Names in these repos are conventional, load-bearing and length-constrained.
- A name is immutable in practice — a re-ticketed change cannot rename a live resource
  without destroy-and-recreate, which for a permission set is explicitly forbidden.
- It couples cloud naming to a ticketing system, so a tracker migration would invalidate
  every name encoding one.

The trailer already carries the association and costs nothing to change. Attribution
belongs in the record, not in the resource.

### Still open

Whether NorthStar ingests **merge requests** at all — `gitlab_issue` is an issue table,
and MR coverage is unknown. That question now matters more than any remaining latency
number, and should be asked before anything else. Also open: whether they parse commit
trailers, and whether a principal can accompany the name for IAM-shaped changes.

## Why `pe:iac-request` is left alone

Nothing consumes it — 187 cloned `tf-*` and `gitops-k8s-*` repos contain zero references
to `CI_MERGE_REQUEST_LABELS`. The `pe:` strings in the audacy-ai-plugins repo are that
repo's own CI job names; the only substantive uses are two CI guards asserting the
iac-request skill text still contains the watermark.

So it is harmless, and asking PE to delete their own label buys nothing. The upstream ask
is addition — that their skill also emit these three axes — which reaches the same end
state for the data with far less friction.

## Evidence index

| Claim | Source |
| --- | --- |
| Nothing consumes `pe:*` | 187 repos, zero `CI_MERGE_REQUEST_LABELS` matches |
| Branch convention uses `ZD-`/`SECOPS-` | `projects/audacy/audacy.md:30` |
| Slug-is-canonical naming | `tf-org-v2 groups.yaml` header comment |
| Four IAM primitives | `tf-org-v2 README.md` § Concepts |
| PS grants nothing until assigned | `tf-org-v2 README.md:11-14` |
| Grants go to groups, never users | `tf-org-v2 README.md:11-12` |
| tf-org-v2 is rebase_merge, squash opt-in | GitLab projects API, 2026-08-30 |
| HEAD after merge is never the trailer commit | live MR in nslt-20260830, 2026-08-30 |
| One ticket spans several MRs | `tf-org-v2 README.md:40-46` |
| GCP IAM lives in `<env>/iam/` | `tf-gcp-*` terragrunt layout |
| 44 of 46 IAM files are outside `**/iam/**` | content grep vs path glob across the workspace |
| NorthStar resource-ID filtering errors | `northstar-mcp-capability-map.md:27` |
| Compute instances ingest in <8 min | live measurement, 2026-08-30 |
| Bindings/buckets/SAs slower than compute | same measurement |
| gcp_compute_instance has no labels column | `describe_table`, 2026-08-30 |
| No table exposes GCP resource labels | `search_tables`, 2026-08-30 |
| NorthStar ingests GitLab labels | `gitlab_issue.labels`, 2026-08-30 |
| NorthStar ingestion 1–2 days stale | `northstar-mcp-capability-map.md:25` |
| PE and DevOps are one team | jira skill description; marketplace owner email |
