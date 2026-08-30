# claude-fallback

Paid fallback for Claude Code when the Max subscription runs out, plus one-off
Fable 5 access from anywhere. Backend: **Claude Platform on AWS** — the
Anthropic-operated endpoint (`aws-external-anthropic.us-east-1.api.aws`), billed
through AWS Marketplace, with same-day first-party API parity (`claude-fable-5`
verified present). Not Amazon Bedrock — Bedrock is partner-operated and does
not carry Fable 5.

## How it works

Two PATH shims, no settings file (plus an optional status line, below):

- `bin/claude-paid` — full fallback session. Fetches the 365-day CPA key from
  Secret Manager (`anthropic-api-key`, project `secops-opintel`) into that one
  session's env as `ANTHROPIC_AUTH_TOKEN`, sets `ANTHROPIC_BASE_URL` and the
  required `anthropic-workspace-id` header via `ANTHROPIC_CUSTOM_HEADERS`
  (Claude Code ≥ 2.1.227), then `exec claude "$@"`. Alternate key sources
  (leading flags; everything after them passes to claude):
  - `claude-paid -s <secret-name> ...` — a different Secret Manager secret,
    same project/endpoint/workspace (the "multiple keys" path).
  - `claude-paid -k <key> ...` — literal key, break-glass for when gcloud is
    down. **A pasted literal lands in shell history** — use
    `-k "$(<command>)"` or `CLAUDE_PAID_KEY="$(<command>)" claude-paid ...`
    instead whenever possible.
  - Precedence: `-k` > `-s` > `CLAUDE_PAID_KEY` env > default secret. An empty
    result from any source fails loudly before claude launches.
- `bin/fable` — same wrapper around `claude -p --model claude-fable-5` for
  one-off questions from any context.

Default `claude` stays on the Max subscription; backend choice is launch-time
only (verified — no mid-session switching).

## Why NOT apiKeyHelper (the hard-won part)

The obvious design — an `apiKeyHelper` in a `--settings` file — **cannot work
against this endpoint**: Claude Code sends helper output in BOTH the
`Authorization: Bearer` and `x-api-key` headers, and the CPA endpoint returns
**401 whenever both are present** (verified by probe: x-api-key alone 200,
Bearer alone 200, both 401). `ANTHROPIC_AUTH_TOKEN` sends Bearer only, and —
unlike `ANTHROPIC_API_KEY` — carries no one-time interactive approval prompt,
so `-p` works non-interactively.

## Other gotchas

- **Probe the endpoint the key belongs to.** A CPA key against
  `api.anthropic.com` returns `invalid x-api-key` — wrong door, not a bad key.
  Working probe shape:
  `curl -s -H "x-api-key: <key>" -H "anthropic-version: 2023-06-01" -H "anthropic-workspace-id: <wrkspc>" https://aws-external-anthropic.us-east-1.api.aws/v1/models`
- Model IDs are bare first-party strings (`claude-fable-5`) — no `anthropic.` prefix.
- The workspace ID is not a secret; it lives in the shims plainly.

## Live spend status line

`statusline/claude-cost.py` — a Claude Code status line showing what the current
session is costing and whether that is real money:

```
PAID $22.33  ·  today $27.72  ·  Fable 5  ·  ctx 34%  ·  cache 91%
sub ~$9.40   ·  today $27.72  ·  Opus 5   ·  ctx 47%
```

Bold red `PAID` = this session bills to CPA. Dim `sub ~$` = the Max
subscription, priced anyway so you can watch a session get expensive *before*
you fall back to paid. `today $` is CPA spend across all sessions for the
current **UTC** day, matching how Cost Explorer buckets.

**Why it parses the transcript** instead of using the harness's own
`cost.total_cost_usd`: that field is a single list-price number with no
billing-path split, and the split is the whole point. Two deliberately redundant
detection paths:

- `ANTHROPIC_BASE_URL` containing `aws-external-anthropic` — set by the shims,
  so the badge is correct from turn one, before any tokens are spent.
- per message, `usage.inference_geo` — `global` on CPA, `not_available` on the
  subscription. Empirically the *only* transcript field separating the two:
  model id, `req_`/`msg_` prefixes, `service_tier` and `version` are identical
  on both paths.

**Accuracy.** CPA has no programmatic usage API — Anthropic documents the Admin
`usage_report` / `cost_report` endpoints as unavailable for Claude Platform on
AWS, so per-key data is Console-only and local pricing is the only real-time
source that exists. Reconcile against Cost Explorer: service `"Claude Platform"`,
usage type `MP:ccu-Units` (1 unit = $0.01), UTC daily buckets, in the CPA
account. Measured 2026-08-30: a session the meter billed at **$27.00** priced
locally at **~$23**. The ~15% gap matches the 5m→1h cache-write premium almost
exactly, so writes appear to bill at the 1h rate even though
`usage.cache_creation` reports them under `ephemeral_5m_input_tokens`. Set
`CLAUDE_COST_WRITES_1H=1` to price them that way, or
`CLAUDE_COST_CALIBRATION=1.15` for a flat multiplier. The default is
as-recorded — a defensible number rather than a tuned one.

**Implementation notes** (each one cost a bug):

- **Dedupe by `message.id`.** Claude Code writes repeated records for the same
  message within one transcript — 188 records for 73 unique messages in the
  measured session — so an undeduped sum roughly doubles.
- **Subagent transcripts** live in `<transcript-without-.jsonl>/subagents/*.jsonl`
  and bill too.
- **Never call `fh.tell()` inside `for line in fh`.** Python raises
  `OSError: telling position disabled by next() call`, which a broad
  `except OSError` swallows into a silent `$0.00` that looks like it works.
  Read the delta as bytes and advance the offset arithmetically.
- **Bucket by each record's own timestamp**, not by when the script runs, or a
  session resumed across midnight UTC dumps its entire history onto today.

Cost is dominated by cache *reads*: 11.4M read tokens (~$11) against 567K writes
(~$7) and 89K output (~$4.50) in the measured session. The driver is context size
re-read every turn, not output volume.

Performance: 59 ms cold on a 2.2 MB transcript, 39 ms warm (mostly interpreter
startup), via per-session byte offsets cached in `~/.claude/statusline/cache/`.

Known limits: the daily rollup is last-writer-wins across concurrent sessions
(self-heals on the next refresh), and all state is machine-local.

## Key lifecycle

- The key is a **long-term (365-day) CPA key**, minted in the Claude console of
  the AWS account. Rotate before expiry (set a reminder): mint a new one, then
  `pbpaste | gcloud secrets versions add anthropic-api-key --data-file=- --project=secops-opintel`,
  clear the clipboard, disable the old key in the console, destroy the old
  secret version. Shims always read `latest`.
- **Zero-standing-secret alternative** (stricter, not currently used): CPA also
  mints short-term keys (≤12h) from AWS credentials
  (`pip install token-generator-for-aws-external-anthropic`); a shim could mint
  per invocation instead of fetching from Secret Manager, at the cost of
  requiring a live AWS SSO session. Revisit with the agent-service-account /
  federation work.

## Install (per machine — user-run; PATH executables are human acts)

1. `cp bin/claude-paid bin/fable <a PATH dir>/` and `chmod +x` them
   (macOS: /opt/homebrew/bin; Linux: ~/.local/bin; Windows Git Bash: ~/bin).
2. Requires gcloud installed and authenticated as yourself, with
   `secretmanager.versions.access` on the secret.
3. Test without touching the subscription: `claude-paid -p "reply OK" --model haiku`.
4. If a `~/.claude/paid-settings.json` exists from the v2 design, delete it —
   it is obsolete and its apiKeyHelper breaks against this endpoint.
5. Status line (optional, independent of the shims):
   `python3 statusline/install.py` — on Windows `python`, never `python3`, which
   is the Store stub there. It copies the script to `~/.claude/statusline/`,
   smoke-tests it, and prints the `statusLine` JSON to merge into
   `~/.claude/settings.json`. Like the twss installer it never edits settings
   itself. Merge it (keep your other keys), then `/statusline` or restart.
