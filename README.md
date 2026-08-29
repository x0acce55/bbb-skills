# bbb-skills

Claude Code skills for the BBB vault. Skills do not sync with the vault
(nothing under `.claude/` does), so this repo is their source of truth.

Two entries are more than skill folders:

- `twss/` — the batch-approval skill **plus** its enforcement pieces: `twss.py`
  (the PreToolUse hook — install to `<vault>/.claude/hooks/` and register in
  settings, human acts), `install.py` (cross-platform `twss` PATH shim
  installer, user-run), `test_twss.py` (run once per machine).
- `claude-fallback/` — not a skill: the paid-fallback config bundle
  (`paid-settings.json` + `claude-paid`/`fable` shims). Install per its README;
  never merge its apiKeyHelper into main settings.

## Install on a machine

Clone, then copy each skill folder into the machine's skills directory:

- macOS/Linux: `~/.claude/skills/`
- Windows: `%USERPROFILE%\.claude\skills\`

## Update

Edit here, commit, push; on other machines pull and re-copy. Never edit the
copies under `.claude/skills/` directly on a non-maintaining machine — propose
changes via the vault's machine-onboarding note (ADR-0032) instead.
