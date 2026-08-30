# Enforcement — text to apply by hand

Nothing in this file is applied by the skill. Labels, CI jobs and group settings are
enforcement surface: an agent proposes them, a human applies them.

## 1. Scoped labels at the `audacy-inc` group level — DONE 2026-08-30

**Applied.** All eight labels exist at group level on `audacy-inc`. `ticket::` values are
not pre-seeded — they are open-ended and created on first use. The commands below are
kept for a rebuild or for another namespace.

Exclusivity was verified empirically rather than assumed, on a throwaway issue since
deleted:

| Step | Action | Resulting labels |
| --- | --- | --- |
| 1 | create with `origin::secops` | `origin::secops` |
| 2 | add `origin::pe` (same scope) | `origin::pe` — secops displaced |
| 3 | add `iam::group` (other scope) | `iam::group`, `origin::pe` — coexist |
| 4 | add `iam::user` (same scope) | `iam::user`, `origin::pe` — group displaced |

Both properties the scheme depends on hold: same-scope values displace, cross-scope values
accumulate. The namespace is on the `ultimate` plan (`GET /namespaces/audacy-inc`), so
scoped labels are not at risk from a tier change.

Note for whoever runs these: `glab` holds the token in the OS keyring, so the API calls
below never put a credential on a command line or in a file (ADR-0020). Do not rewrite
them to use a `PRIVATE-TOKEN` header with a token you had to read first.

### Rebuild commands

Define once at the top-level group so all projects inherit. Project-level labels would
mean recreating this vocabulary in 187+ repos and keeping them in sync.

Requires Owner on `audacy-inc`. In the GitLab UI: **Group → Manage → Labels → New label**,
or via the API:

```sh
create() {  # $1 = name, $2 = colour, $3 = description
  glab api --method POST "groups/audacy-inc/labels" \
    -f "name=$1" -f "color=$2" -f "description=$3" >/dev/null && echo "ok  $1"
}

create "origin::secops"        "#0E6B60" "Change produced by the SecOps team"
create "origin::pe"            "#1F6FB2" "Change produced by Platform Engineering"

create "iam::user"             "#9B3524" "Individual human identity lifecycle"
create "iam::group"            "#A8471F" "Group definition or membership"
create "iam::permission-set"   "#8B2F52" "Permission bundle contents - capability, not grant"
create "iam::assignment"       "#A86C09" "Binds a group + permission set to an account"
create "iam::service-account"  "#6B4FA8" "Non-human identity, keys, impersonation"
create "iam::federation"       "#3F5BA8" "Trust between identity systems"
```"
```

`ticket::` values are open-ended (one per ticket), so they are created on demand by
whoever opens the MR rather than pre-seeded. GitLab creates a scoped label on first
use if the group permits it; if it does not, add `ticket::` labels at project level as
they arise.

Scoped labels require Premium or above; `audacy-inc` is on `ultimate`, verified
2026-08-30, so the flat-name fallback that earlier drafts described is not needed and has
been dropped.

## 2. CI: the two blocking rules

Both scoped to identity changes so they never fire on unrelated MRs. Add to the
`.gitlab-ci.yml` of repos carrying IAM — `tf-org-v2` first.

The gate is deliberately broad and the check deliberately narrow: path globs alone are
evadable by declaring a binding in an unexpected file, which is precisely the change
most worth labelling.

```yaml
attribution:iam-labels:
  stage: test
  image: alpine:3.20
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes: ["**/*.tf", "**/*.hcl", "**/*.yaml", "**/*.yml"]
  before_script:
    - apk add --no-cache git grep
  script:
    - |
      DIFF=$(git diff --unified=0 "origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"...HEAD)

      # Does this MR touch identity at all? Content, not path.
      if printf '%s' "$DIFF" | grep -qE \
        'google_(project|folder|organization|storage_bucket|service_account)_iam|google_service_account|aws_ssoadmin_|aws_identitystore_'; then
        IS_IAM=yes
      else
        IS_IAM=no
      fi

      LABELS="$CI_MERGE_REQUEST_LABELS"

      # Rule 1 — an identity change carries an iam:: and a ticket:: label.
      if [ "$IS_IAM" = yes ]; then
        printf '%s' "$LABELS" | grep -q 'iam::' || {
          echo "This MR changes IAM resources but carries no iam:: label."
          echo "Add one of: user, group, permission-set, assignment, service-account, federation."
          exit 1; }
        printf '%s' "$LABELS" | grep -q 'ticket::' || {
          echo "This MR changes IAM resources but carries no ticket:: label."
          echo "Use ticket::ZD-<n>, ticket::SECOPS-<n>, or ticket::none-<reason>."
          exit 1; }
      fi

      # Rule 2 — the ticket label agrees with the branch name.
      BRANCH="$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME"
      BT=$(printf '%s' "$BRANCH" | grep -oE '(ZD|SECOPS)-[0-9]+' | head -1 || true)
      LT=$(printf '%s' "$LABELS" | grep -oE 'ticket::(ZD|SECOPS)-[0-9]+' | sed 's/ticket:://' | head -1 || true)
      if [ -n "$BT" ] && [ -n "$LT" ] && [ "$BT" != "$LT" ]; then
        echo "Branch names $BT but the ticket label says $LT. One of them is stale."
        exit 1
      fi
      echo "attribution ok (iam=$IS_IAM)"
```

## 3. CI: the post-merge advisory

Warns rather than blocks — the merge has already happened, and the labels survive even
when the trailer does not. Its job is to catch squash messages edited at merge time.

```yaml
attribution:trailer-present:
  stage: test
  image: alpine:3.20
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  allow_failure: true
  script:
    - |
      # HEAD is NOT the commit carrying the trailer on merge_method=merge or
      # rebase_merge projects — it is GitLab's own merge commit, whose message is a
      # template. Probe-verified 2026-08-30: knowledge-artifacts is `merge`,
      # tf-org-v2 is `rebase_merge`, and `git log -1` false-alarms on both.
      # Scan the commits this push actually introduced instead.
      RANGE="${CI_COMMIT_BEFORE_SHA}..${CI_COMMIT_SHA}"
      case "$CI_COMMIT_BEFORE_SHA" in
        0000000000000000000000000000000000000000|"") RANGE="${CI_COMMIT_SHA}~5..${CI_COMMIT_SHA}" ;;
      esac
      if ! git log --format=%B "$RANGE" 2>/dev/null | grep -q '^Change-Origin:'; then
        echo "WARNING: no Change-* trailers in the commits this merge introduced."
        echo "The squash or branch commit message was probably edited at merge time."
        echo "The MR labels still hold the attribution; the in-repo record does not."
      fi
```

## 4. What stays convention

| Not enforced | Why |
| --- | --- |
| Label vocabulary validity | Scoped labels already constrain it; a CI check would duplicate GitLab |
| Trailer presence pre-merge | Generated by the skill — rung one of the ladder, not rung three |
| `none-*` reason accuracy | Unfalsifiable by CI. Watch the frequency instead |
| Multi-subject MR splitting | A judgement call; the skill flags it in the description |

Two blocking rules, both narrow. Adding a third should require an argument about what
it catches that these two miss — every blocking rule is an interruption charged to
whoever is merging, and the vocabulary is generated rather than typed.
