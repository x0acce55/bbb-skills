# Routing a memory to its destination

## The procedure

Ask these in order and stop at the first yes.

0. **Is it credential-shaped — a token, key, or password?** → Drop on sight and tell
   the user it was found in a buffer. Secrets never promote and never persist
   (ADR-0020).

1. **Is it already recorded in `context/`, an ADR, or a project note?** → Drop. Check
   before assuming; the most common distillation error is duplicating something the user
   already wrote in their own words.

2. **Has it been superseded?** → Drop, unless it superseded a *decision*, in which case
   write a new ADR and set `superseded_by` on the old one.

3. **Was a choice made between alternatives?** → Decision. The test is whether you can
   name something that lost. If nothing lost, it isn't a decision — it's a preference,
   and preferences go in context.

4. **Is it true only within one project?** → That project's index note or an existing
   note in its folder.

4b. **True across one domain but not the others — an employer's tooling, a client
   fact?** → That domain's index note or a note in its folder. Never global
   `context/`: what one employer's sessions taught the agent must not shape another
   employer's sessions (ADR-0018, ADR-0019).

5. **Is it tied to a date?** → Daily note. Things that happened, as opposed to things
   that are true.

6. **Will it still be true in six months, across every project?** → Context.

7. **Otherwise** → Drop.

## Context or drop

The hard call, and the one worth being conservative about.

`context/` loads into every session and the user treats it as true without re-checking.
A wrong entry there is invisible and compounds — it shapes agent behaviour in sessions
that have nothing to do with where it came from.

So the bar is not "might be useful." It is: **would you assert this to the user's face
as something true about them?** An inference from one session's evidence usually
doesn't clear that bar. Leave it in the buffer; if it's real, it will show up again.

A memory is a claim an agent made, not a fact it observed.

## Worked examples

**"User prefers pnpm over npm."**
Observed once, from a single correction. → Context, in `stack-and-conventions.md`, under
"Things agents get wrong here." It's a standing preference, it's cheap to record, and
it's verifiable at a glance if wrong.

**"User seemed frustrated with the auth refactor."**
→ Drop. An inference about a mood on one day. Not a standing truth, and asserting it in
a file the user reads is presumptuous.

**"We chose Postgres over SQLite because the vault sync needs concurrent writers."**
→ Decision. Alternatives were considered, one lost, and there's a reason. Write the ADR,
set `affects:` on it and `decisions:` on the notes it governs.

**"The test suite takes 11 minutes."**
→ Project note for that project. True, useful, and not true across every project.

**"Spent Tuesday debugging the sync conflict; it was settings.local.json syncing."**
→ Daily note for the date. But note the second clause is a general trap and belongs in
`stack-and-conventions.md` too — one memory can legitimately split across two
destinations. Say so when presenting the classification.

**"User works in TypeScript."**
→ Check `context/stack-and-conventions.md` first. Almost certainly already there. → Drop.

**"User wants the vault to work from two machines."**
→ Already an ADR (ADR-0009). → Drop, and mention to the user that it's covered, so they
know the ledger is doing its job.

## When one memory splits

Some memories carry both an event and a lesson. The event goes to `daily/`, the lesson
to `context/`. Don't force a single destination — but do say explicitly that you're
splitting it, so the user can veto half.

## When you can't classify

Leave it in the buffer and say so. An unclassifiable memory is usually one that's too
vague to be useful anywhere, and the next session that touches the same ground will
either sharpen it or let it go stale, which is itself a signal.
