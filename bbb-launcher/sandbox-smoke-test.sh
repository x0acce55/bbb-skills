#!/bin/sh
# bbb sandbox smoke test — ADR-0036, Open #2.
#
# Run this inside a domain session (`bbb <domain>`), AFTER accepting that
# folder's trust dialog, to prove three things at once:
#
#   1. the Seatbelt sandbox is actually active (the CONTROL block — without it
#      every result below is meaningless, because an unsandboxed session passes
#      trivially),
#   2. the domain's write boundary holds (project writable, home and vault root
#      not),
#   3. the credential and network workflows still function inside the sandbox.
#
# Secrets never enter the agent's read path (ADR-0020): the secret-access test
# sends stdout to /dev/null and reports only an exit code and stderr. Do not
# "improve" this script by printing the value.
#
# Usage:
#   sh sandbox-smoke-test.sh
#   sh sandbox-smoke-test.sh --project secops-opintel \
#        --secret tines-api-credentials --secret zendesk-api-credentials \
#        --url https://crimson-cloud-7047.tines.com/ \
#        --url https://audacytechnicalservices.zendesk.com/
#
# --secret may repeat (all share one --project). --url may repeat. Exit status
# is 0 if the sandbox was active and no test errored unexpectedly, 1 otherwise.

PROJECT=""
SECRETS=""
URLS=""
RESULT=0

while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --secret)  SECRETS="$SECRETS $2"; shift 2 ;;
    --url)     URLS="$URLS $2"; shift 2 ;;
    -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 64 ;;
  esac
done

say() { printf '%s\n' "$*"; }
hdr() { printf '\n== %s ==\n' "$*"; }

say "bbb sandbox smoke test"
say "cwd:      $(pwd)"
say "domain:   ${BBB_SESSION_DOMAIN:-<unset — not a wrapped session>}"
say "tier:     ${BBB_SESSION_TIER:-<unset>}"
say "machine:  ${BBB_MACHINE_ID:-<unset>}"

# ---------------------------------------------------------------- CONTROL ----
hdr "CONTROL: is the sandbox active?"
if touch "$HOME/.bbb-sandbox-control" 2>/dev/null; then
  rm -f "$HOME/.bbb-sandbox-control" 2>/dev/null
  say "CONTROL=WROTE_HOME  -> SANDBOX OFF. Everything below is VOID:"
  say "  an unsandboxed session passes these tests without proving anything."
  RESULT=1
else
  say "CONTROL=BLOCKED     -> sandbox ON. Results below are meaningful."
fi

# ------------------------------------------------------- WRITE BOUNDARIES ----
hdr "write boundaries"
if touch ./.bbb-write-probe 2>/dev/null; then
  rm -f ./.bbb-write-probe 2>/dev/null
  say "PROJECT_WRITE=ok        (expected: ok)"
else
  say "PROJECT_WRITE=blocked   (UNEXPECTED — the domain cannot write its own tree)"
  RESULT=1
fi

if [ -n "$BBB_VAULT_ROOT" ]; then
  if touch "$BBB_VAULT_ROOT/.bbb-write-probe" 2>/dev/null; then
    rm -f "$BBB_VAULT_ROOT/.bbb-write-probe" 2>/dev/null
    say "VAULTROOT_WRITE=ok      (UNEXPECTED for a domain session — sandbox leaked upward)"
    RESULT=1
  else
    say "VAULTROOT_WRITE=blocked (expected for a domain session)"
  fi
else
  say "VAULTROOT_WRITE=skipped (BBB_VAULT_ROOT unset)"
fi

# ---------------------------------------------------------------- GCLOUD ----
if command -v gcloud >/dev/null 2>&1; then
  hdr "gcloud under the sandbox"
  if ls "$HOME/.config/gcloud" >/dev/null 2>&1; then
    say "GCLOUD_CFG_READ=ok"
  else
    say "GCLOUD_CFG_READ=blocked  (gcloud needs its config dir — add a sandbox.filesystem rule)"
  fi
  if touch "$HOME/.config/gcloud/.bbb-write-probe" 2>/dev/null; then
    rm -f "$HOME/.config/gcloud/.bbb-write-probe" 2>/dev/null
    say "GCLOUD_CFG_WRITE=ok"
  else
    say "GCLOUD_CFG_WRITE=blocked (gcloud caches creds/logs here; the likely failure mode)"
  fi

  for s in $SECRETS; do
    if [ -z "$PROJECT" ]; then
      say "SECRET[$s]=skipped (no --project given)"
      continue
    fi
    # stdout to /dev/null; only stderr is captured. ADR-0020.
    err=$(gcloud secrets versions access latest --secret="$s" --project="$PROJECT" 2>&1 >/dev/null)
    rc=$?
    if [ "$rc" -eq 0 ]; then
      say "SECRET[$s]=ok (exit 0, value discarded)"
    else
      say "SECRET[$s]=FAILED exit=$rc"
      say "  stderr: $(printf '%s' "$err" | tr '\n' ' ' | cut -c1-300)"
      RESULT=1
    fi
  done
else
  hdr "gcloud under the sandbox"
  say "GCLOUD=not installed — skipped"
fi

# --------------------------------------------------------------- NETWORK ----
if [ -n "$URLS" ]; then
  hdr "network egress (unauthenticated — no credentials used)"
  for u in $URLS; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$u" 2>&1 | tr -d '\n')
    if [ "$code" = "000" ] || [ -z "$code" ]; then
      say "URL[$u]=NO RESPONSE (blocked or unreachable)"
      RESULT=1
    else
      say "URL[$u]=http $code"
    fi
  done
fi

hdr "done"
if [ "$RESULT" -eq 0 ]; then
  say "All checks behaved as expected under an active sandbox."
else
  say "Something needs attention — see the UNEXPECTED / FAILED / VOID lines above."
  say "Fix by adding a targeted sandbox.filesystem rule to the domain fragment."
  say "Never disable the sandbox (ADR-0036)."
fi
exit "$RESULT"
