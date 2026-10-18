# Systems Mastery

A learning loop that works through 111 systems-engineering topics, then turns what it learned into checks the factory enforces.

- `LEDGER.md` lists every topic, its track and its status.
- `<NNN>-<slug>.md` is one card per topic, written by `/systems-mastery`.
- `GAPS.md` lists places where the factory falls short of a card. The operator turns rows into factory tasks.
- `REVIEWS.md` records each tenth-card review pass.

## Start the loop

Paste this into an interactive Claude Code session in this repo:

```text
/loop You are a principal full-stack engineer whose goal is to master all 111 topics in knowledge/systems/LEDGER.md, from rate limiting to postmortems. Mastery means you can explain each topic from primary sources, you have watched its failure happen in a real experiment, and you can point to exactly where it applies in this factory and where it would be over-engineering. Work autonomously: never stop to ask, and decide, act and report instead. Each iteration, run the systems-mastery skill to learn exactly one topic and write its card. Commit the card, the ledger and any gap rows to the feat/systems-mastery branch with a message naming the topic. Never push, and never change factory code from this loop. Pace yourself: start the next iteration as soon as this one is reported. If you hit the plan's usage limit, wait for it to reset. When the ledger has no todo rows left, write the synthesis and stop the loop.
```

`/loop` with no interval paces itself. Stop it at any time with Esc. Because every iteration commits, it can resume after any interruption: it reads the ledger and picks up the next `todo` row.

## Into the factory

1. **Now:** run `/systems-review` by hand. It PASSes until cards exist. It is user-invoked only (`disable-model-invocation: true`), so factory builds do not spend turns on it yet.
2. **After track A (resilience) is done:** add `systems-review` as a lane in `.github/workflows/qa-gate.yml`, next to `ux-laws`, and make it a required check. The gate invokes it explicitly, as it does thermo-nuclear.
3. **After track A:** remove `disable-model-invocation` from the skill, and add one line to `TASK_PROMPT_TEMPLATE` in `factory/intake/webhook_adapter.py` telling builders to run `/systems-review` before and after building.
4. **As GAPS.md grows:** the operator turns `high` rows into factory tasks.
