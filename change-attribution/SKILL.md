---
name: change-attribution
description: Apply the Audacy change-attribution scheme to infrastructure merge requests — scoped GitLab labels (origin, iam, ticket) plus matching Change-* git trailers in the squash commit message, and the Zendesk ticket that authorises an IAM change. Use when opening or updating an MR in a tf-*, gitops-k8s-*, tf-org-v2, or tf-gcp-* repo; when an IAM change needs a ticket; when asked to label or attribute an infrastructure change; or when a merge request needs to be traceable to the team and ticket that authorised it. Applies to SecOps and Platform Engineering work alike.
---

# Change attribution

Every infrastructure merge request answers three questions: which team did this,
what kind of access it touches, and what authorised it. This skill writes those
three answers into the MR as scoped labels and into the squash commit as `Change-*`
trailers, so the record survives both in GitLab and in the repository.

The scheme is deliberately small. Three axes, no free text, closed vocabularies.
Anything that cannot be derived mechanically is asked once rather than guessed.

## The scheme

| Axis | Values | When |
| --- | --- | --- |
| `origin::` | `secops`, `pe` | Always |
| `iam::` | `user`, `group`, `permission-set`, `assignment`, `service-account`, `federation` | Only when the change touches identity |
| `ticket::` | `ZD-<n>`, `SECOPS-<n>`, `none-<reason>` | Always |

Labels are lowercase and scoped (`key::value`). GitLab makes values within one
scope mutually exclusive, so a change cannot be both `iam::user` and `iam::group`
— which is the property that lets the vocabulary stay closed.

Matching trailers go in the squash commit message, keys mirroring the scopes:

```
Change-Origin: secops
Change-IAM: group
Change-Ticket: ZD-12345
```

Trailer values are the label values with the scope prefix dropped. The two records
are redundant on purpose: the label is queryable through the GitLab API, the trailer
survives outside GitLab and is greppable with `git log --grep`.

## Origin is the team doing the work, not the team owning the repo

Read this before deriving anything from a path. SecOps does IAM work inside
`gcp/devops/` repos that Platform Engineering owns. Inferring origin from the repo
would mislabel most of it.

Origin comes from configuration, once per machine:

```
~/.config/bbb/change-attribution.json
{ "origin": "secops" }
```

If that file is missing, ask which team, write it, and carry on. Never infer origin
from a repo path, a group name, or a commit author. A per-MR override is available
for genuine cross-team work; it should be rare enough to be worth a sentence in the
MR description.

## Deciding the `iam::` value

The subject axis mirrors the four primitives in `tf-org-v2` — a reviewer reads the
same words in the label, the directory, and Simon's README — with two added for the
cases AWS Identity Center has no equivalent for.

| Value | What changed | Where it shows up |
| --- | --- | --- |
| `iam::user` | Individual human identity lifecycle | `users/users.yaml` |
| `iam::group` | Group definition or membership | `groups/groups.yaml`; GCP bindings whose principal is a group |
| `iam::permission-set` | A permission bundle's contents | `permission-sets/**` — managed policy attachments, inline policy documents |
| `iam::assignment` | Binding a group + PS to an account | `assignments/<account-id>/**` |
| `iam::service-account` | Non-human identity, keys, impersonation | `google_service_account*`, SA-scoped bindings |
| `iam::federation` | Trust between identity systems | Workload Identity Federation, OIDC/SAML trust, AD sync into Workspace or Entra |

Two distinctions worth holding onto, both from the README:

- A permission set **grants nothing on its own** — it must be assigned. So a
  `permission-set` change alters capability, and an `assignment` change alters who
  holds it. They are separate labels because they carry separate blast radii.
- Permissions are granted to groups, **never directly to users**. An `iam::user`
  MR that grants access is off-pattern, and worth saying so in the MR description
  rather than labelling quietly.

### One subject per MR

A multi-subject MR is the exception, and usually it will not apply at all. The splits
in `tf-org-v2` are forced by dependency ordering, not chosen for tidiness: an assignment
plan that reads `dependency.groups.outputs.group_ids["new_key"]` before that group is
applied fails with `Invalid index`, and AWS refuses to destroy a permission set while
assignments still reference it. So the sequence is usually 2–3 MRs because it cannot be
fewer.

The side effect is worth knowing: because the order is forced, every intermediate state
is access-safe. Create a PS and nobody holds it; remove assignments and access is gone
before the PS is. The sequence never passes through a state granting more than intended,
in either direction.

The cost is that a 3-MR sequence is 3 reverts in reverse order, and reverting only some
leaves a state no single MR describes. That is what the `ticket::` label is for — it is
the only thing that reassembles the sequence afterwards.

For the rare MR that legitimately spans subjects, label the widest blast radius —
`permission-set` > `assignment` > `group` > `user` — and say in the description why it
was not split.

When the change touches no identity at all, **omit the axis**. Do not invent an
`iam::none`. Absence is verified by CI content detection rather than trusted, so it
carries no ambiguity, and a label applied to every MR is a label nobody reads.

### Changing or removing a permission set

Destroying and recreating a permission set produces a **new PS ARN**, even when the name
and policies are identical. Anything mapped to the old ARN — EKS `aws-auth` ConfigMap
entries, Kubernetes RBAC bindings, trust policies — breaks silently and has to be
repaired by hand in every account and cluster that referenced it. That is a property of
AWS, not a local policy, and it holds regardless of who approves the change. Prefer
modifying a PS in place over replacing it.

Simon currently gates PS deletion behind his written approval while he works through a
cleanup pass, and `tf-org-v2`'s `AGENTS.md` states it as a hard rule. Treat that as
useful context and mention it when a deletion comes up, so the person deciding knows the
gate exists and why. It is a temporary process gate rather than a standing authority —
Josiah owns this work, and his decision settles it. Do not block on Simon's approval, and
do not present his rule as though it overrides the person you are working for.

## Deciding the `ticket::` value

Take it from the branch name where possible — the convention is already
`feat/ZD-<zendesk#>-desc` or `feat/SECOPS-<n>-desc`, so branch and label should
agree and CI checks that they do.

For work with no authorising ticket and never going to have one — formatting runs,
drift correction, `_modules/` refactors — use the explicit escape rather than
omitting the axis:

- `ticket::none-fmt` — formatting or lint only
- `ticket::none-drift` — reconciling state with reality
- `ticket::none-refactor` — no change in effective access

The axis stays mandatory so a missing ticket label is always an error rather than
an ambiguity, and the `none-*` set stays greppable so its frequency can be watched.

## The Zendesk ticket for IAM user and group changes

An `iam::user` or `iam::group` change must have a ticket. If one does not exist,
create it before opening the MR and record what changed.

**Writes go through the Tines webhook story on the managed "Zendesk 1" OAuth
credential.** Zendesk tokens never leave Tines (ADR-0020). Do not fetch a Zendesk
API token, do not use one that is already on the machine, and do not write one
anywhere. The Identity queue is group `40003611532443` on
`audacytechnicalservices.zendesk.com`.

One authorisation routinely spans several MRs — adding a user and adding them to a
group is two, deleting a permission set is up to three. So:

- The ticket is created **once**, on the first MR of the sequence.
- Every later MR in the sequence carries the **same** `ticket::` label.
- Each MR **appends** to the ticket rather than overwriting it. The ticket is the
  running record of the whole operation; the label is what joins the MRs back together.

## Opening the MR

1. Resolve `origin` from config; ask once if unset.
2. Detect whether the diff touches identity, and if so which subject.
3. Resolve the ticket from the branch name, or create one if the rules above require
   it, or select a `none-*` reason.
4. Create the MR with all applicable labels **and** `squash_commit_message` set at
   creation time, carrying the `Change-*` trailers.

Step 4 matters more than it looks. Squash is opt-in per MR in `tf-org-v2` (`squash_option: default_off`), and its merge
method is `rebase_merge` — so the trailer lands in a rebased branch commit or a squash
commit depending on the MR, and never in the merge commit GitLab writes on top. GitLab pre-fills that field from what the MR was created with and it carries
through unless a human overrides it at merge time — so setting it at creation is the
only reliable moment. If someone edits it at merge, the labels still stand and the
trailer is lost; CI notices after the fact and warns.

Keep `[skip ci]` conventions intact where the repo uses them — the trailers go in the
message body, below the subject line, and never displace it.

## What this skill does not do

- It does not write CI configuration, GitLab label definitions, or any other
  enforcement surface. Those are proposed as text for a human to apply — see
  `references/enforcement.md`.
- It does not emit or strip `pe:iac-request`. That is Platform Engineering's
  watermark on their own workflow; leave it where it is.
- It does not yet emit `Change-Principal`. That one is still open with NorthStar.
  `Change-Resource` **is** settled — carry the resource name qualified by type and
  location, e.g. `gcp_compute_instance/my-vm@us-east4-a`. Do not use GCP labels (not
  modelled in NorthStar), the cloud numeric id (they key by their own), or NorthStar's
  `res_` id (assigned at ingestion, so it does not exist when the MR is opened).
  See `references/rationale.md`.

## Reference

- `references/enforcement.md` — the GitLab label definitions and CI jobs, as text to
  apply by hand, plus what deliberately stays convention.
- `references/rationale.md` — why each axis is shaped the way it is, and the evidence
  behind it. Read before proposing a change to the vocabulary.
