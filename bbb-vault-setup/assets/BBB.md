---
type: index
summary: Home note for the BBB vault. Start here.
created: 
updated: 
---

# BBB

Second brain. Everything is reachable from this note by clicking.

## Context

Background that is true regardless of what's open.

- [[about-me]]
- [[goals]]
- [[stack-and-conventions]]

## Decisions

- [[decisions]] — all architecture decision records

## Domains

Work is partitioned by domain — an employer, a client, or personal.

<!-- INDEX:START -->
<!-- INDEX:END -->

## Daily

- [[daily]] — every daily note, newest first

## Memories

`memories/<machine-id>/` holds each machine's agent-written working notes. They are
volatile. Anything durable gets promoted into context, decisions, or daily by the
`bbb-memory-distill` skill.
