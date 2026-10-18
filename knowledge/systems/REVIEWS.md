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

## 2026-10-18 · 20 cards (track A, and track B up to 71; 68 deferred)

Re-ran `101_webhooks.py` against the adapter: same results (202 answered in 3 ms against 2 ms; the 2 MB task still fails at spawn). The factory code is unchanged since the cards were written, so their line references still hold.

Changed:
- **067-secrets-management.md:** the publish-step item would have blocked any edit to an existing publish step because of the known pre-scan gap. It now applies to new publish steps, or to an existing one that starts publishing new agent-produced content.
- **071-tls.md:** the edge item would have blocked any new hostname because of a Cloudflare zone setting no diff can change. It now judges only the configuration the diff itself controls. The general rule for both: block on what the diff controls, and record the rest as a gap.
- **Related links:** 23 links were one-way. Two-way links were added only where the connection is real (001↔010, 011↔056, 012↔101, 010↔013, 057↔011, 057↔014, 067↔069, 067↔080, 067↔078, 070↔076, 076↔080, 077↔101). The rest stay one-way so the hub cards (067, 101) do not list everything.

Checked and kept:
- 076 (Host validation) and 070 (Access JWT validation) both close the DNS-rebinding exposure. They are alternatives, not a contradiction, and each card names the other.
- The severities in GAPS.md are consistent across cards: one high (no secret scan before the push), the rest medium or low. 68 IAM is deferred, and nothing from it is recorded.
