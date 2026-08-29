---
name: fable
description: Ask Claude Fable 5 (billed to Claude Platform on AWS, not the subscription) a one-off question from inside any session, via the `fable` PATH shim. Use when the user invokes /fable, asks to "ask fable", or wants a Fable-5-quality answer while the session runs a lower or local model.
argument-hint: "the question for Fable 5"
---

Relay one question to Claude Fable 5 through the `fable` shim (part of the
claude-fallback bundle — CPA-billed, subscription untouched) and report its
answer. This does NOT change the current session's model or billing — backend
choice is launch-time only; the shim spawns an isolated one-shot run.

## Procedure

1. If the arguments are empty, ask what to send. Otherwise compose the prompt:
   the subprocess sees NOTHING of this conversation — no context, no history.
   Include everything Fable needs inline (relevant file paths it should read,
   key facts, the actual question). It runs in the cwd and can read files there.
2. Run via Bash with a generous timeout (Fable turns can take minutes):
   `fable "<composed prompt>"`
   For long input, pipe it: `cat <file> | fable "<question about stdin>"`.
3. Report the answer verbatim (or faithfully summarized if long), clearly
   attributed as Fable 5's output — do not blend it silently into your own
   reasoning.

## Cost honesty

Each call is a full `claude -p` run at Fable pricing ($10/$50 per MTok):
typically **$0.15–0.40** per invocation (harness + cwd context + thinking).
Don't invoke it for questions the session's own model can answer; when the
user is on a Max subscription with usage remaining, `/model fable` in their own
session is free and keeps conversation context — suggest that instead when it
fits.

## Requirements

The `fable` shim installed on PATH (claude-fallback bundle) with gcloud access
to the `anthropic-api-key` secret. If the shim is missing, say so and point at
`claude-fallback/README.md` in the bbb-skills repo — never substitute a
different billing path silently.
