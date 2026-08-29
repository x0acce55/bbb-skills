# bbb-skills

Claude Code skills for the BBB vault. Skills do not sync with the vault
(nothing under `.claude/` does), so this repo is their source of truth.

## Install on a machine

Clone, then copy each skill folder into the machine's skills directory:

- macOS/Linux: `~/.claude/skills/`
- Windows: `%USERPROFILE%\.claude\skills\`

## Update

Edit here, commit, push; on other machines pull and re-copy. Never edit the
copies under `.claude/skills/` directly on a non-maintaining machine — propose
changes via the vault's machine-onboarding note (ADR-0032) instead.
