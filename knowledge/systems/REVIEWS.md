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

## 2026-10-18 · 30 cards (track B finished, minus 68; track C up to 63)

Re-ran `061_metrics.py` against the real run records: same results (8 runs, 75% completed, 3/6 on the first build). The factory code is unchanged since the cards were written.

Changed:
- **063-slos.md (contradiction):** the suggested availability SLO was "`alive_at` fresh in 99% of minutes", but 057 proved `alive_at` keeps updating while the server cannot answer. It is now an authenticated `/health` probe through the tunnel, with a note explaining why.
- **062-alerts.md:** the same blind spot. The staleness page catches a dead process but not a wedged one, so it is now paired with the authenticated `/health` probe.
- **061-metrics.md:** the golden-signals item would have demanded new signals for any new endpoint. It now covers jobs, queues, pipeline stages and endpoints that start work, not read-only routes on an instrumented service.
- **058-monitoring.md:** the probe item would have demanded a new probe for every route. It now applies to new services and new public hostnames.
- **Related links:** added two-way links where the connection is real (020↔062, 057↔058, 020↔058, 061↔063, 058↔064, 074↔078, 074↔079, 044↔075, 057↔063).

Checked and kept:
- 062 and 064 add no gap rows of their own. Their findings are covered by the Monitoring, Dead Letter Queues and SLIs rows, so GAPS.md has no duplicates.
- The TLS edge row (071) and the WAF card (074) agree that the edge settings are Cloudflare's, not the repo's.

## 2026-10-18 · 40 cards (track C finished; track D up to 41)

Re-ran `039_races.py`: same result. The adapter's `FETCH_HEAD` pattern still reads another fetch's commit, and a dedicated ref still reads the right one. The factory code is unchanged since the cards were written.

Changed:
- **065-error-budgets.md:** the "pause features when the budget is spent" item would have blocked every feature today, because of a starter SLO nobody has adopted. It now applies only once an SLO and budget policy are adopted, and the card's text says the 188% figure is a recommendation until then.
- **041-memory-leaks.md:** the plateau item applied to any hot-path change that allocates, which is nearly every change. It now applies to changes that keep data across requests or runs.
- **Related links:** added two-way links where the connection is real (037↔039, 040↔044, 041↔044, 041↔043, 043↔057, 060↔061, 061↔066, 058↔066, 060↔066, 014↔036).

Checked and kept:
- 039, 037 and 043 agree on the adapter's concurrency model: one run worker, `HEARTBEAT_LOCK` the only lock, the port as a single-instance lock, `FETCH_HEAD` the one cross-process race.
- 060 and 066 agree that the action log covers 2 of 8 runs, and 061 and 066 agree that pauses and token usage are unrecorded. Each has one GAPS row, with no duplicates.

## 2026-10-19 · 50 cards (track D finished; track E up to 102)

Re-ran `057_probes.py`: identical output (a 2.7 s `/health` stall while `alive_at` was stamped 13 times; the same probe-simulation table). The factory code is unchanged since the cards were written.

Changed:
- **037 and 038 (contradiction, now proven wrong):** both called the bound port `127.0.0.1:7654` the adapter's single-instance lock. It is not one. uvicorn imports the module, and the import runs `_recover`, before it binds. Real uvicorn processes on a scratch port and root showed a second start on an occupied port exit with `EADDRINUSE`, but only after it had marked the first instance's in-flight run `error`. Both cards now say so and point to 052.
- **052-blue-green-deployment.md and its GAPS.md row:** raised from low to medium. The trigger is no longer only a debug run on another port: any second start, even one that fails visibly on the live port, corrupts the live run's record. The review proof is added to the card.
- **006-ci-cd.md:** two items would have blocked for things outside the diff. "Does CI run the versions production runs?" blocked any dependency change while the factory has no lockfile; it now blocks only what the diff adds unpinned, or pins on one side only. "Does the deploy reach the running process?" asked every adapter PR for deploy notes; it now applies to launch config, entrypoint, dependency and runtime changes.
- **055-rollbacks.md:** "Is the way back known?" would have blocked every gate change, because `pull_request_target` makes the gate's rollback depend on the gate. It now blocks only a diff that removes or invalidates a documented way back.
- **053-canary-releases.md:** the global-change item now excludes comment-only and doc-only edits, and asks for trial evidence only when a restart cannot undo the change.
- **Related links:** added two-way links where the connection is real (037↔052, 038↔052, 039↔052, 054↔057, 054↔056, 006↔056, 053↔065, 053↔064, 055↔081, 055↔082, 044↔102, 058↔102, 010↔051, 006↔011, 081↔102).

Checked and kept:
- 081 and 102 both find HEARTBEAT's schema hidden in a markdown template. 081 owns the "new rows never reach the live file" gap, and 102 points at the existing Backpressure row for the dead fields, so neither duplicates the other.
- 054 and 055 agree on the adapter's way back: `git checkout` in the working copy plus `launchctl kickstart -k`, with no merge needed. 054's in-flight-run gap and the Idempotency row's orphaned-container gap are separate rows.
- GAPS.md: 33 open rows, 1 high (no secret scan before the push), 15 medium, 17 low.

## 2026-10-19 · 60 cards (track E finished; track F finished)

Re-ran `044_backpressure.py`: identical output (unbounded queue: peak depth 121 and a p99 wait of 11.8 s; both bounded queues: depth 20 and a 2.0 s wait; the 1 MB pipe still blocks `wait()`). The factory code is unchanged since the cards were written.

Changed:
- **012-retries.md:** it called the "no checks reported" match "Right". 103 then showed the match depends on gh's human-readable wording, which no gh version promises, and a reworded message turns the wait into a failure. 012 keeps its verdict on the retry logic and now points to 103's GAPS.md row for the wording dependency.
- **108-dependency-hell.md:** "Is the full dependency tree locked?" would have blocked any dependency change while the factory has no lock files, which is outside the diff's control. That is the same over-breadth review 50 fixed in 006. It now blocks a new environment without a lock, or a change that bypasses or skips updating an existing lock.
- **015-message-queues.md:** "Does waiting work survive a restart?" applied to any diff touching the enqueue path, so the existing never-started-runs gap would have blocked unrelated changes. It now applies to new queues and to changes in how accepted work is stored or recovered.
- **Related links:** added two-way links where the connection is real (012↔103, 067↔103, 067↔107, 067↔108, 006↔103, 006↔107, 006↔108, 076↔022, 077↔022, 060↔016, 060↔017, 044↔023, 054↔015, 043↔023, 037↔021, 011↔023).

Checked and kept:
- 022's claim that the live adapter cannot serve WebSockets holds. Its interpreter has none of `websockets`, `wsproto`, `uvloop` or `httptools`.
- 015's never-started-runs gap, 054's "restart only when idle" gap and the Idempotency row's orphaned-container gap are three separate failures with three separate fixes, so none duplicates another.
- 016, 023 and 024 agree that polling is right for one operator: the 15 s dashboard poll, and the 15 s `gh pr checks` poll that added 16 s to a 492 s run.
- 103 and 108 agree with 006 on pinning. 006's row covers CI and the adapter, 108's row covers the builder's transitive tree, and 103's row covers the gh wording dependency.
- GAPS.md: 36 open rows, 1 high (no secret scan before the push), 16 medium, 19 low.

## 2026-10-19 · 70 cards (track G finished; track H up to 34)

Re-ran `014_idempotency.py`: same results (a retried task makes two runs, an exact resend gets `401 Replayed request`, a keyed store creates one run, and check-then-write under 5 concurrent requests creates 5). Only the random run IDs differ. The factory code is unchanged since the cards were written.

Changed:
- **032-replication.md (contradiction):** it said `_gate_results` "never acts on the previous commit's results". 029 then showed that the checks come from a second read carrying no SHA, which can still return the previous commit's verdict. 032 now says the head check prevents a stale head, and points to 029's gap for the checks read.
- **027-n-plus-one-queries.md:** "Is the query count per request bounded?" applied to any change to a list endpoint, so the dashboard's existing per-PR calls (cached, and right at today's load per the card itself) would have blocked unrelated changes to `command_data`. It now blocks only the per-item calls a diff adds.
- **028-connection-pooling.md:** "Are connections reused?" would have blocked any new `gh` call, contradicting the card's own conclusion that a CLI per call is right at a few calls a minute, because it keeps the token out of the adapter. It now targets hot paths and loops, and names the `gh` exception.
- **Related links:** added two-way links where the connection is real (029↔034, 032↔095, 014↔095, 012↔095, 011↔095, 057↔095, 052↔030, 059↔031, 075↔031, 043↔027, 001↔027, 067↔028, 041↔028, 103↔029).

Checked and kept:
- 095's ambiguous `gh pr create` row and the Retries row are different failures: one is a write whose outcome is unknown, the other is any call failing outright. The fixes differ (look up by branch, against retry on idempotent reads).
- 031 extended the Logging row instead of adding a duplicate. 025, 026 and 027 agree on the adapter's scan and lookup costs (0.5 ms for 30 run records, 17 ms for 900, and 0.48 s per real `gh` call).
- 034's per-operation verdicts (dashboard available, gate consistent, intake available) match what 029, 032 and 095 found about the same code.
- GAPS.md: 38 open rows, 1 high (no secret scan before the push), 16 medium, 21 low.

## 2026-10-19 · 80 cards (track H finished; track I up to 2)

Re-ran `012_retries.py`: identical output (79.8% → 99.3% success with 3 attempts; 27 vs 3 db calls for layered retries; a retry budget brings a dead dependency down to 1.01 calls; transient-only retry makes 1 call on a permanent error). The factory code is unchanged since the cards were written.

Changed:
- **002-caching.md (contradiction):** it said `_pr_cache` is "bounded only by retention". 041 proved that its entries are never evicted, not even when `_recover` prunes their runs. The cache grows, at about 2 KB per PR, until the adapter restarts. 002 now says so.
- **091-latency.md:** "Is latency measured per route and per outcome?" would have blocked every new route while the factory records no latency metrics at all, which is outside a diff's control. It now asks a new service to ship with measurement, and new paths on an instrumented service to be included, the same narrowing review 30 applied to 061.
- **096-clock-skew.md:** the monotonic-clock item blocked any diff touching existing deadlines, while the card itself rates the existing wall-clock uses acceptable on this never-sleeping host. It now applies to code a diff adds or changes, which can use `time.monotonic()` at no cost.
- **Related links:** added two-way links where the connection is real (070↔096, 052↔033, 017↔018, 017↔019, 014↔019, 061↔091, 044↔092, 001↔092, 063↔093, 027↔094).

Checked and kept:
- 033's proposed `flock` guard is the same fix as 052's medium Blue-Green row, and 033 adds no row of its own.
- 091, 092, 093 and 094 agree on where the factory's time goes: the build (82% of a run), then the gate. The gate's critical path is thermo-nuclear in all 15 measured runs. Throughput is bounded by plan usage, not compute. All of them say percentiles over 2–8 runs would be noise.
- 018 and 019 agree that a run is an orchestrated saga with a durable log and deliberately no compensations, and that its crash gaps are already rows (Idempotency, Rolling Deployments, Message Queues, Network Partitions).
- GAPS.md: 39 open rows, 1 high (no secret scan before the push), 16 medium, 22 low.

## 2026-10-19 · 90 cards (track I finished; track J started with 97)

Re-ran `045_autoscaling.py`: identical output (no stabilization flaps 56 replica-count changes in 20 min; a 300 s downscale stabilization damps it to 4; a 300→900 req/s step with 60 s warm-up sheds 15,203 requests above ready capacity). The factory code is unchanged since the cards were written.

- **Link audit across all 90 cards (new this review):** checked every `Related` link for a target that exists and for symmetry. Found one real defect: `097-dns.md` linked `010-retries.md`, but retries is `012` (`010` is circuit-breakers) — a dangling link, now fixed in two places (the checklist and the Related line). The other dangling links (`084`, `085`, `086`, `007`, `008`, `104`, `110`, `111`, `068`) are forward references to still-`todo` topics and become valid when those cards are written; left as-is. The ~150 one-way links are by design — `Related` is "what to read next from here", authored asymmetric on purpose — so I did not mass-add back-links. Added one high-value back-link: `089-cold-starts.md` → `088-cost-optimization.md`, since warm-capacity cost is central to cold starts and 088 already links back.
- **No contradictions found in the 80→90 window (045, 046, 047, 048, 049, 050, 088, 089, 090, 097).** Checked the heaviest overlap, 048 (CDN) vs 049 (edge caching): both state nothing in the factory is edge-cached and cross-reference each other and 002; the tunnel exact-path-match claim (`^/(command(/data)?)?$`, `/command/data.css` → 404) is consistent across 048 and 097.
- **Checklists not tightened:** every item in this window already carries an "Applies when" trigger and an escape for the single-host case (e.g. 045 "Is autoscaling justified?", 046 "Is scale-out justified?"), so none would block a change the factory's real load needs.

## 2026-10-19 · 100 cards (track J finished; track K up to 105)

Re-ran `098_tcp_udp.py`: identical (UDP lost 4 of 10 datagrams through the lossy relay with no retransmit; three TCP sends coalesced into one ordered, complete `recv`). Real kernel sockets on loopback; the factory code is unchanged since the cards were written.

- **Link audit across all 100 cards:** no wrong-slug links (the 90-review's `010-retries` fix was the last; the window 97–105 is clean). The remaining dangling links (`008`, `106`, `109`, `110`, `111`, `84`, `83`, `85`, `86`, `87`, `68`) are forward references to still-`todo` topics and resolve as those cards are written. `104-terraform` and `105` link each other; `007`↔`104` link each other. One-way links remain by design, as recorded at the 90-review.
- **No contradictions in the 90→100 window (97, 98, 99, 4, 3, 5, 9, 7, 104, 105).** Verified the claims repeated across the networking/infra cards: the edge↔origin hop is HTTP/1.1 (004, 048, 099 all agree); there is exactly one origin — single `uvicorn`, `ThreadPoolExecutor(max_workers=1)` (003, 005, 009 agree); static addressing with Docker embedded DNS as the only discovery (009) matches 097. The three gaps added this window — DNS (medium), Reverse Proxies (low), IaC (low) — are distinct from each other and from the existing JWT/CORS/SSRF rows they cross-reference.
- **Checklists not tightened:** every item in the window carries an "Applies when" trigger and a single-host escape (003 "Is load balancing justified here at all?", 005 "Is a heavyweight gateway justified?", 104/105 "Is the tooling proportionate?" with the explicit "do not accept dashboard-clicking as the alternative" caveat). None would block a change the factory's real load needs. No card edits were required.
