# Reviews

One entry per tenth card. Each review re-reads every card, fixes contradictions, adds missing links, re-runs one experiment, and tightens checklist items that would block work the factory's load does not need.

## 2026-10-18 · 10 cards (track A, all but 57)

Re-ran `011_timeouts.py`: same results (`C-fail` 4.1 s against 4.0 s). The factory code is unchanged since the cards were written, so their line references still hold.

Changed:
- **011-timeouts.md:** the CI `timeout-minutes` item applied to any job that "calls the network", which is nearly every job. It now applies only to jobs that call an LLM, build or run untrusted code, or wait on an external service.
- **056-health-checks.md:** the dependency item would have blocked every change that touches an existing dependency. It now applies to a *new* dependency whose failure would surface only after expensive work.
- **010-circuit-breakers.md:** said a GitHub failure after a build "loses that build". That is true only during the push: at PR creation the branch is already pushed. It now also points to a dependency check before the build (056) as the cheap guard against a dependency that is down for every run, which resolves the tension with 056's gap.
- **GAPS.md:** the first Retries row said one GitHub error "discards a finished build". It now says what happens in each phase: the push, PR creation and polling. The 056 experiment showed that a failure at PR creation leaves the branch pushed.
- **Related links:** added the missing reverse links (001↔101, 012↔020, 012↔101, 013↔101, 014↔011, 020↔010, 044↔013, 011↔101, 011↔056, 010↔001).

Checked and kept:
- All ten statuses are `proven`. 056's part B is labelled as arithmetic, not measurement.
- 012 and 010 agree: token buckets and breakers are not needed for one serial caller, and bounded retries are.
