# Software factory comparison: the-factory vs Factory vs Warp Factories

- **Date:** 2026-11-23
- **Status:** accepted by the operator, 2026-11-23
- **Feature requests that follow from it:** FR-01 to FR-14, filed as issues #77 to #90 (listed below)

## Why this record exists

The operator asked what two commercial software factories do that the-factory should learn from. This record keeps
the reasoning: which ideas were taken, which were turned down on purpose, and why. Later builds and reviews can then
see why the feature requests exist, instead of rediscovering it. It queues no work. Work still arrives only through
the webhook or the operator.

## Summary

- **the-factory's core holds up, and in places it is stronger than both products.** Its review gate is enforced, its
  sandbox network is locked and proven before every run, and it scans for secrets before it pushes.
- **Both products are ahead on knowing whether the factory works.** They have outcome dashboards, graded runs,
  benchmarks and live tests of the running app. the-factory's own gap register (`knowledge/systems/GAPS.md`) already
  names these misses in its SLIs, Error Budgets and Observability rows.
- **Ideas to take:**
  - a committed "why we built this" record (operator decision, 2026-11-23)
  - an outcome scorecard
  - checking work against the original request
  - a live check for infrastructure changes
  - a merge-risk rating
  - a stuck-run handoff
  - benchmarks
  - a running-app check that the operator reviews
  - a security review lane with a threat map
  - one command to send a task
  - kaizen on a schedule
  - fixes for known-vulnerable dependencies
- **Ideas to turn down:**
  - advisory-only review
  - an open network by default
  - auto-approving PRs
  - pauses for plan or spec approval
  - self-improvement that changes the factory without approval
  - extra agent harnesses
- **All four operator decisions were made on 2026-11-23.** A person reviews at the QA step, including visual and
  running-app checks; the factory runs everything else.
- **Fourteen feature requests follow**, ranked Now, Next and Later.

## Feature request issues

Each issue has the problem, evidence, user stories, "Done when" checks, a ready-to-send task and a measure.
Filing one starts nothing; the operator approves by sending its task to the factory.

| FR | Issue | Request | When |
|---|---|---|---|
| FR-01 | #77 | Keep a "why we built this" record with every factory change | Now |
| FR-02 | #78 | Outcome scorecard: autonomy rate, time to merge, plan usage | Now |
| FR-03 | #79 | Judge the work against the original request, not only the builder's plan | Now |
| FR-04 | #80 | Live proof before merge for sandbox and infrastructure changes | Now |
| FR-05 | #81 | Merge-risk rating to focus the QA review | Next |
| FR-06 | #82 | Stuck-run inbox and local takeover | Next |
| FR-07 | #83 | Benchmarks: prove a factory change helps before real requests depend on it | Next |
| FR-08 | #84 | Running-app check for UI work, reviewed by the operator at QA | Next (phase 1), Later (phase 2) |
| FR-09 | #85 | Readiness report and per-repo network allowlist in onboarding | Later |
| FR-10 | #86 | The factory's workflow as a file, with conditional review flags | Later |
| FR-11 | #87 | Security review lane with a threat map | Next |
| FR-12 | #88 | One command to send a task to the factory | Now (first) |
| FR-13 | #89 | Run kaizen on a schedule and check its own results | Next |
| FR-14 | #90 | Turn known-vulnerable dependencies into ready-to-approve fixes | Later |

## The three at a glance

| | the-factory | Factory (Factory-AI) | Warp Factories |
|---|---|---|---|
| What it is | Your own pipeline on one Mac | Commercial agent platform (Droids) | Hosted factory service |
| Open source | All of it | Plugins, skills, CI actions | Examples and skills (MIT); the engine is closed |
| How work arrives | Signed webhook (Grok Bot not wired yet) | Slack, Teams, Linear, Jira | Slack, Teams, GitHub, GitLab, Jira, Linear, webhooks, Factory MCP |
| How the flow is defined | Code in `factory/intake/webhook_adapter.py` | Product features (Missions, Spec Mode) | A Blueprint file (`factory.yaml`) |
| Human checkpoints | Merge only, by design | Plan approval (CVE fixes) | Spec approval, open questions, merge |
| Sandbox network | Allowlist, proven before every run | OS sandbox, Droid Shield | `networkPolicy`, unrestricted unless declared |
| Review | Enforced: six required checks | Advisory | Advisory |
| Testing the running app | None | Automated QA (browser, terminal), `/verify` | Computer Use verifier |
| Measuring the factory | Kaizen report (most-failed check) | Agent Effectiveness dashboards | Scorers, benchmarks, self-improvement, dashboard |
| Agent | Claude Code only | Droid, any model | Claude Code, Codex, pi, Warp Agent |
| Cost | Claude plan | Paid plans | Paid plans; self-hosting needs Enterprise |

## What the-factory already does better (keep)

1. **An enforced gate.**
   - Six required checks must pass, even for admins (`enforce_admins` is on).
   - The gate runs main's copy of its own workflow, so a PR cannot weaken the gate that reviews it.
   - Warp's docs say "Worker review is advisory," and Factory's review is advisory too. Both leave enforcement to
     branch protection.
2. **A closed network.**
   - The sandbox reaches only allowlisted hosts, and the block is proven before each run.
   - In Warp, outbound access is unrestricted until a policy is declared.
3. **Push safety.**
   - gitleaks scans new commits before anything is pushed.
   - The adapter never runs git in the agent's clone.
4. **Knowledge that becomes checks.**
   - 111 systems cards and the open GAPS rows are routed to each diff (`factory/qa/route.py`), and `rules.py` turns
     cards into free static checks.
   - Factory's closest idea is lint rules that steer agents (its `eslint-plugin`). That is the same idea `rules.py`
     already uses.
5. **Kaizen with a measure.**
   - Warp's self-improvement proposes fixes from repeated failures.
   - Kaizen does that too (`factory/qa/kaizen_report.py`, issue #68), and it also says how to tell whether the fix
     worked.
6. **Owned and cheap.** It needs only the Claude plan. There's no platform fee and no vendor lock-in.

## Good ideas to adopt

Each idea is tied to evidence from the-factory itself and to a feature request.

| # | Idea | Where it comes from | Why it fits the-factory | Feature request |
|---|---|---|---|---|
| 1 | **"Why we built this" record** | Warp's own repo commits a spec for every ticket (296 so far, `PRODUCT.md` + `TECH.md`), and skills check code against them | The plan and guide live in `.git` and the PR body, never in the repo, so a later builder can't see why code is the way it is. Operator decided 2026-11-23 to keep the record | FR-01 |
| 2 | **Outcome scorecard** | Warp dashboard (autonomy %, PR cycle time, cost per PR); Factory Agent Effectiveness | The GAPS SLIs row already defines the metric and counts 5 of 8 by hand. The Observability row: every `Tokens:` line reads 0. The Metrics row: usage-limit pauses leave no event | FR-02 |
| 3 | **Judge the work against the request** | Warp's example scorer: "Judge scope from the issue text, not from the pull request's description of itself" | The thermo-nuclear lane gets the PR body from `## Plan` on and checks the diff against the builder's own plan. A plan that drifts from the request still passes | FR-03 |
| 4 | **Live proof before merge** | Factory `/verify` (an "investigator, not an advocate"); Warp's verifier: "Don't infer success from missing proof" | GAPS Error Budgets row: PR #55 passed all six checks, but its container cleanup failed against real Docker. That miss used 63% of the starter SLO's budget. The agent runs the proof in a throwaway VM (Decision 3) | FR-04 |
| 5 | **Merge-risk rating** | Warp `common-skills` merge-risk (MIT); Factory `.factory/review.yaml` risk-based approval | Every green PR looks the same today. A rating, label only, shows the operator where to look first at the QA step | FR-05 |
| 6 | **Stuck-run handoff** | Warp Factory MCP (take a run over locally, hand it back); Warp's human handoff stage | GAPS Dead Letter Queues row: a blocked run disappears when the next run succeeds. Two runs were finished by hand | FR-06 |
| 7 | **Benchmarks** | Warp benchmarks: fixed tasks with correctness criteria, comparing setups on cost and quality | Today the only proof a factory change helped is kaizen's report after 10 more real PRs. Past merged PRs make a ready answer key | FR-07 |
| 8 | **Test the running app** | Factory Automated QA (`/install-qa`, `/qa`); Warp Computer Use verifier | The ux-laws lane reads code, not screens. Decision 2 makes the visual and running-app checks the place where the operator reviews. Phase 1 starts with the factory's own dashboard; phase 2 covers apps it builds (roadmap items 4–6) | FR-08 |
| 9 | **Readiness report and per-repo network allowlist** | Factory Agent Readiness (5 levels, 9 pillars, 80% of a level to unlock the next); Warp `AGENTS.md` validation order; Warp `networkPolicy` | Roadmap item 4's brief has no readiness score, and every repo shares one allowlist. The registry-upload gap (`factory/build/README.md`) gets narrower | FR-09 |
| 10 | **Workflow as a file** | Warp Blueprint (`factory.yaml`: stages, transitions, conditional gates); Factory Missions (milestones) | The flow is hard-coded in the adapter, and items 4–5 add new flows. Use deterministic conditions, not plain-language ones, and only to flag PRs for the QA review (Decision 2) | FR-10 |
| 11 | **Security review lane with a threat map** | Factory Security Review: STRIDE, OWASP and supply-chain methods, a repo threat model, a candidate pass then a validation pass, and checks for look-alike and brand-new packages | Security is one item among many in ponytail-review. The factory's riskiest parts are a public repo, a privileged gate workflow and an internet-facing webhook, and GAPS.md already holds several security rows found by hand | FR-11 |
| 12 | **One command to send a task** | Warp Factory MCP (send work in from a local session) | Every approval means sending a task through the signed webhook, which today takes a hand-built `curl` and `openssl` request | FR-12 |
| 13 | **Kaizen on a schedule** | Warp self-improvement (runs automatically once failures pass a threshold) | Kaizen and its "did it work?" measure run only when someone starts them. Issue #68 is still open | FR-13 |
| 14 | **Fixes for known-vulnerable dependencies** | Factory CVE remediation (each finding becomes a plan with risk and rollback, then a PR) | Roadmap item 3 finds vulnerable dependencies but nothing proposes the fix. Dependabot alerts or osv-scanner can find them; the factory fixes them through its gate | FR-14 |

## Ideas to adapt, not copy

- **Scorers (sampled AI grading).**
  - The gate already reviews every PR and enforces the result. A second, sampled judge would add cost and little else.
  - What's missing is outcome data to grade the gate itself (FR-02). Revisit sampled scorers only if gate verdicts
    and outcomes disagree.
- **Self-improvement PRs.**
  - Warp can open PRs that change the factory's own definition after repeated failures.
  - Kaizen already drafts the task with evidence and a measure, and waits for the operator. Keep that approval step,
    and feed kaizen outcome data, not only gate failures (FR-02).
- **Human checkpoints.**
  - Warp pauses for spec approval, questions and merge. the-factory's rule is "decide, act and report."
  - Decision 2 keeps that rule: a person reviews only at the QA step, where the visual and running-app checks
    (FR-08) and the merge-risk rating (FR-05) show where to look.
- **Missions.** Splitting a feature into milestones, each with a check, suits roadmap item 5 (a new app from an
  idea). It belongs in FR-10's later scope.
- **Readiness as a gate.**
  - Factory gates each level at 80%. Use readiness as a report instead.
  - Only "builds" and "tests run" should block, as roadmap item 4 already says.
- **Triage and duplicate detection at intake.** Both products triage requests. Revisit once Grok Bot sends real
  traffic. The duplicate-run risk is already tracked in the GAPS Idempotency row.
- **More intake channels and one factory per product.** Both products take work from Slack, Teams, Jira and more, and
  Warp runs one factory per product. Grok Bot is the planned channel, and repos are separated by the `FACTORY_REPOS`
  allowlist. Revisit when there is real traffic from more than one product.

## Already covered, no request needed

| Idea | Who does it | What the-factory already has |
|---|---|---|
| Secret scanning before code leaves | Factory Droid Shield | gitleaks scans new commits before push |
| Lint rules that steer agents | Factory `eslint-plugin` | `factory/qa/rules.py`, compiled from the systems cards |
| Shared skills pinned by hash | Warp `skills-lock.json` | Vendored skills pinned by `vendor/*/CHECKSUMS.txt` |
| Plan before code | Factory Spec Mode | `.git/factory/plan.md` before any change (roadmap item 1) |
| A map of the codebase | Factory AutoWiki | The floorplan skill, run on demand (#70) |

## Ideas to turn down

| Idea | Who does it | Why not for the-factory |
|---|---|---|
| Advisory-only review | Factory, Warp | The gate is the product. A green PR has to mean something without a person re-reading every diff |
| Open network unless declared | Warp | Builders run with permission prompts off. The only safe default is to deny everything and prove the block before each run |
| Auto-approve low-risk PRs | Factory (`approve_risk_level: low`) | Decision 2 keeps a person at the QA step, the one human check on what ships. The merge-risk rating (FR-05) shows where to look; it never merges anything |
| Pauses for plan or spec approval | Warp (by default), Factory (CVE plans) | Decision 2: a person reviews only at the QA step. Conditions can flag a PR for a closer look there, but never pause a run |
| Self-improvement that changes the factory without approval | Warp | A standing rule says "never weaken the gate to pass it." Changes to the factory's own rules need an operator yes |
| More agent harnesses (Codex, pi, other models) | Factory, Warp | A hard rule says Claude Code only. Every new harness adds to what the sandbox and the gate must cover. Benchmarks (FR-07) can compare Claude models instead |
| Plain-language conditions read by an agent | Warp Blueprint | They make the flow unpredictable. the-factory's checks are deterministic on purpose |
| A hosted platform | Factory, Warp | Owning the stack is the point |

## Gaps in the-factory

| Gap | Evidence | Who solves it today | FR |
|---|---|---|---|
| Nothing explains, in the repo, why code is the way it is | Plan and guide are never committed (roadmap item 1) | Warp specs | FR-01 |
| No outcome measure | GAPS SLIs: run `4981e691` completed but PR #55 closed unmerged; runs `b3c60871` and `1e8e28c7` merged after a human finished them | Warp dashboard | FR-02 |
| Plan usage can't be seen | GAPS Observability (every `Tokens:` line reads 0) and Metrics (usage-limit pauses leave no event) | Warp cost per PR | FR-02 |
| Work is checked against the builder's plan, not the request | `qa-gate.yml` gives the lane everything from `## Plan` on | Warp scorer | FR-03 |
| Green checks, broken behavior on real infrastructure | GAPS Error Budgets: PR #55 | Factory `/verify`, Warp verifier | FR-04 |
| No risk signal per PR | None. Every PR is reviewed the same way | Warp merge-risk, Factory `review.yaml` | FR-05 |
| Stuck runs disappear | GAPS Dead Letter Queues | Warp Factory MCP takeover | FR-06 |
| No fast way to prove a factory change helped | Kaizen measures after 10 more PRs (#68) | Warp benchmarks | FR-07 |
| No check of the running app for UI work | ux-laws reviews code only | Factory QA, Warp verifier | FR-08 |
| No readiness score; one allowlist for all repos; registries accept uploads | Roadmap item 4; `factory/build/README.md` | Factory Agent Readiness, Warp `networkPolicy` | FR-09 |
| Flow hard-coded in the adapter | `factory/intake/webhook_adapter.py` | Warp Blueprint | FR-10 |
| No dedicated security review and no threat map | Security is one item in ponytail-review; GAPS.md's security rows were found by hand | Factory Security Review | FR-11 |
| Approving a task means hand-signing a request | `factory/intake/README.md`, "Running locally" | Warp Factory MCP | FR-12 |
| Kaizen and its measure run only by hand | `factory/qa/README.md`; #68 still open | Warp self-improvement | FR-13 |
| Vulnerable dependencies are found but not fixed | Roadmap item 3 adds osv-scanner, with no fix step | Factory CVE remediation | FR-14 |

Other open GAPS rows, such as Idempotency, Message Queues and TLS, are outside this research and stay in
`GAPS.md`.

## Decisions

All decisions below were made by the operator on 2026-11-23.

**Keep a "why we built this" record.** This becomes FR-01.

1. **Scanning for instructions aimed at an AI agent (roadmap items 3 and 4).**
   - **Decision:** flag only instructions that send data out, run remote code or switch off checks.
   - **Why:** agent-ready repos ship `AGENTS.md`, `CLAUDE.md` or `.claude/`. Warp's own repo has all three, and so
     does this one. The old wording refused them all, and it contradicted item 3's own "Done when," which expects this
     repo to scan as `safe`.
   - **Item 3 (the free scan) is already built in PR #76, open as of this writing.**
     - It doesn't refuse agent-ready repos; this repo scans `safe`.
     - It treats two kinds of agent text as malicious: "ignore previous instructions" phrasing and hidden characters.
       A free text scan can't reliably tell what prose asks an agent to do, so the judgment of intent belongs to
       item 4's model pass.
   - **Roadmap change, which lands with this record's PR:** item 4, step 2's model pass asks whether anything tells
     an AI to send data out, fetch and run remote code, or switch off checks; runs code on the operator's machine; or
     sends data out. Agent files that only describe the repo are normal.
2. **Human checkpoints.**
   - **Decision:** people review only at the QA step, including the visual and running-app checks, which don't exist
     yet.
   - **Effect:**
     - no pauses for plan or spec approval
     - no auto-merge
     - the merge-risk rating (FR-05) and conditional flags (FR-10) only shape the QA review
     - FR-08's first phase moves up so the visual checks exist sooner
   - **Not covered by this decision:** which factory-generated proposals get built (kaizen, dependency fixes). Those
     stay operator approvals through FR-12.
3. **Who runs the live proof (FR-04).**
   - **Decision:** the agent runs it, unless the change produces creative or visual output that needs human taste.
     That part goes to the operator at the QA step.
   - **How it stays safe:** the proof runs builder-written code, so it runs in a throwaway VM with no shared folders
     and no secrets, never directly on the Mac.
4. **"Why" records in other repos (FR-01).**
   - **Decision:** on for new apps (item 5); asked per repo for existing ones during onboarding (item 4).

## How this reaches the factory

1. **This record:** a PR adds it under `docs/research/`, together with the roadmap change from Decision 1. The card
   router reads only `knowledge/systems/`, so the record changes no review.
2. **Each feature request:** one GitHub issue in the kaizen shape (Problem, Evidence, Proposed task, Measure), plus
   user stories and acceptance criteria, labeled `enhancement` and `research`. Filing an issue starts nothing, because
   work comes only from the webhook or the operator.
3. **To approve one:** send its Proposed task to the factory (`factory/intake/README.md`), then close the issue with a
   link to its PR. This is the same flow as kaizen. Once FR-12 lands, `send.sh --issue <N>` does it in one command.
4. **Keep proposals out of `factory/ROADMAP.md`.** The build loop takes the first item that isn't `done`, so anything
   listed there gets built. Add an approved request there only if it spans more than one PR.
5. **Close the gap rows:** each task tells the builder to mark the GAPS rows it closes as fixed.

## Licensing

- **Free to adapt, with credit:**
  - Warp: `common-skills`, `warp-factory-examples` and `oz-skills` (MIT).
  - Factory: `skills` (MIT) and `eslint-plugin` (Apache-2.0).
- **Ideas only:**
  - Warp's `warp-factories-skills`, and Factory's `factory-plugins` and `droid-action`, have no license.
  - `warpdotdev/warp` has both AGPL and MIT license files. Check which one applies before copying any code.
- **What the feature requests borrow:** ideas and patterns, not code. FR-05 may adapt the merge-risk rubric (MIT); if
  it does, keep the original credit.

## Sources

- Factory: <https://docs.factory.com/>, <https://github.com/Factory-AI>
- Warp: <https://docs.warp.dev/> (Factories section), <https://github.com/warpdotdev/warp>,
  <https://github.com/warpdotdev/common-skills>, <https://github.com/warpdotdev/warp-factory-examples>
- the-factory:
  - `README.md` and `CLAUDE.md`
  - `factory/ROADMAP.md`
  - the intake, QA and build READMEs in `factory/intake/`, `factory/qa/` and `factory/build/`
  - `knowledge/systems/GAPS.md`
  - issue #68
