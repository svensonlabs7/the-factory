---
name: systems-review
description: Review or plan a change against the systems-engineering checklists in knowledge/systems/ (timeouts, retries, idempotency, security, observability, concurrency, data, deploys) and end with a PASS or BLOCK verdict. Use before building backend, infrastructure, or integration work, after building it, and when asked for a systems or reliability review.
disable-model-invocation: true
---

# Systems Review

The checklists come from the topic cards in `knowledge/systems/*.md` written by `/systems-mastery`. Only cards with status `learned` or `proven` count. With no cards yet, say so and PASS.

## Before building

List the cards whose `Applies when` triggers match the planned change. Name the checklist items the plan must satisfy, and the items that look relevant but are not worth it at this project's load, with the card's reason.

## After building

1. Read the diff and the code it touches.
2. For each card, check each `Review checklist` item whose `Applies when` matches the diff. Skip items that do not match.
3. An item fails only when its `Block if` condition is true in this diff. Cite the card file and the `file:line`.
4. Never block for a scale or infrastructure technique the card's `When it is worth it` says this load does not need. Missing sharding on a single-host service is not a finding. This is the same rule as Ponytail: the smallest change that is correct at the real load.

## Output

- `What this change touches:` the cards that applied, in one line.
- Findings, numbered. Each one has the card, `file:line`, the concrete failure scenario, and the smallest fix.
- End with `Verdict: PASS` or `Verdict: BLOCK — fix 1 and 3`.
