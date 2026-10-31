# Systems Mastery

A learning loop that works through 111 systems-engineering topics, then turns what it learned into checks the factory enforces.

- `LEDGER.md` lists every topic, its track and its status.
- `<NNN>-<slug>.md` is one card per topic, written by `/systems-mastery`.
- `GAPS.md` lists places where the factory falls short of a card. The operator turns rows into factory tasks.
- `REVIEWS.md` records each tenth-card review pass.
- `ASSUMPTIONS.md` lists the load facts that "not needed here" verdicts rest on.
- `proofs/` holds each card's experiment. `factory/qa/route.py` routes a diff to the checks it triggers.

## Start the loop

Paste this into an interactive Claude Code session in this repo:

```text
/loop You are a principal full-stack engineer whose goal is to master all 111 topics in knowledge/systems/LEDGER.md, from rate limiting to postmortems. Mastery means you can explain each topic from primary sources, you have watched its failure happen in a real experiment, and you can point to exactly where it applies in this factory and where it would be over-engineering. Work autonomously: never stop to ask, and decide, act and report instead. Each iteration, run the systems-mastery skill to learn exactly one topic and write its card. Commit the card, the ledger and any gap rows to the feat/systems-mastery branch with a message naming the topic. Never push, and never change factory code from this loop. Pace yourself: start the next iteration as soon as this one is reported. If you hit the plan's usage limit, wait for it to reset. When the ledger has no todo rows left, write the synthesis and stop the loop.
```

`/loop` with no interval paces itself. Stop it at any time with Esc. Because every iteration commits, it can resume after any interruption: it reads the ledger and picks up the next `todo` row.

## Into the factory

The cards are never loaded whole: all of them come to about 170,000 tokens. Each check runs at the cheapest level
that can enforce it.

1. **Rules, no model.** `factory/qa/rules.py` runs in the `static` lane and checks what a machine can decide alone
   (subprocess timeouts, `shell=True`, unpinned actions, HTML built from strings). Each finding names its card.
2. **Routed checklist.** `factory/qa/route.py` reads each card's `Triggers` line and prints only what a diff touches: open
   `GAPS.md` rows near the changed lines, `ASSUMPTIONS.md` facts it changes, and the matching cards' checklist items,
   tripwire cards first and capped at 15 items. Over the last 20 merged PRs that averaged about 1,100 tokens. The
   builder runs it before committing (`TASK_PROMPT_TEMPLATE`), and the thermo-nuclear lane appends it to its prompt,
   so it costs no extra Claude session.
3. **The full card, on demand.** A builder or reviewer opens a card only for its reasoning.
4. **On a cadence, not per PR.** The tenth-card reviews, and the operator turning `GAPS.md` rows into factory tasks.
