# 51. Feature Flags

Track: E. Delivery and change · Status: proven · Updated: 2026-10-18

Triggers: lines `(?i)feature.?flag|\btoggle|os\.environ\.get\(|getenv\(`

## What it is
A feature flag (or toggle) is a switch that chooses between code paths at runtime. Deploying the code and releasing the behaviour then become separate steps: new code ships dark and is turned on later, for everyone or for some users, and turned off again without a deploy.

Hodgson names four kinds, which differ in how long they live and how often they change:
- **Release flags:** hide unfinished work. They should live days to weeks.
- **Experiment flags:** A/B tests.
- **Ops flags:** kill switches and load-shedding switches.
- **Permission flags:** features for some users only.

Every flag doubles the paths the code can take. So flags are inventory with a carrying cost: test the on and off states that will actually run, give each flag an owner and a removal date, and delete the flag and its dead branch when it is done.

## When it is worth it
Flags are worth it when deploying and releasing must be separate: trunk-based work on features that take longer than one PR, gradual rollouts, kill switches for risky dependencies, and experiments. Where config lives should match how fast it must change: a constant or an environment variable (restart to change) is enough for most. A flag service or database is worth it only when flags must change per user or per request without a restart. With one operator and a manual deploy, a PR plus a restart already is the switch, so most flags would be over-engineering.

## How it fails
- **Repurposed flag:** a new feature reuses an old flag name whose old code is still present. Any server that missed the deploy runs the old meaning. This is Knight Capital: seven of eight servers got the new code, the flag woke dead code on the eighth, and 212 orders became over 4 million executions and a $460M loss in 45 minutes.
- **Dead flag never removed:** the switch and its stale branch stay forever → untested paths that someone can still turn on.
- **Untested combination:** only the "on" state was tested, and the off path (the rollback) is broken.
- **Unsafe default:** a missing or unreadable flag value defaults to "on", or to the risky path.
- **Flag sprawl:** dozens of long-lived flags make behaviour hard to predict or reproduce.
- **Flag checks scattered through the code:** the same flag is tested in many places → changing it means editing all of them, and some get missed.

## Review checklist
- [ ] **Is the flag new, never reused?** · Applies when: the diff adds or changes the meaning of a flag, toggle or mode switch. · Block if: it gives an existing flag name a new meaning, or old code that the name used to enable is still present.
- [ ] **Is the off state tested and safe?** · Applies when: the diff adds a flag or changes code behind one. · Block if: tests do not cover both states that will run, or a missing, empty or malformed value selects the riskier path.
- [ ] **Does the flag have an owner and a way out?** · Applies when: the diff adds a release or experiment flag. · Block if: there is no stated removal condition, such as an issue, a date, or a written removal step.
- [ ] **Is the dead branch deleted with the flag?** · Applies when: the diff removes a flag or makes it always on. · Block if: the code path the flag used to select is left behind.
- [ ] **Is a flag needed at all?** · Applies when: the diff adds a flag service, a flag database, or per-request flags. · Block if: the switch changes no faster than a deploy and a restart, so a constant or an environment variable would do.

## In the factory
- The factory has one runtime switch, and it is handled the way Hodgson recommends:
  - `factory/intake/webhook_adapter.py:49`: `FACTORY_WEBHOOK_SECRET_PREVIOUS` is an ops switch for secret rotation.
  - Empty counts as unset, so the off state is the safe one.
  - `tests/test_adapter.py:904-917` tests both states.
  - `factory/intake/README.md:91` has the removal step.
  - On 2026-10-18 it was absent from `.env`, so no rotation was in progress.

  Right.
- `factory/intake/webhook_adapter.py:52,55,56` (`FACTORY_AGENT_CMD`, `GH_BIN`, `DOCKER_BIN`) are dependency injection for tests, not feature flags. Their defaults are the production values. Right.
- `.github/workflows/qa-gate.yml:24-28`: the `ux-laws` lane's `paths` decides whether a lane runs, and it fails closed: a regex or git error fails the lane, and it never skips (`factory/qa/scope.sh`). Right.
- Not applicable at today's load: a flag service, per-user flags and experiment flags. A PR plus a restart is the switch for one operator. The checklist matters most for what the factory builds for others.

## Proof
`python3 -I knowledge/systems/proofs/051_flags.py` models the SEC order's failure (a fleet of eight, one server missed, a flag reused):
```
A  repurposed flag 'power_peg', 7/8 deployed:   212 parent orders -> 26,186 child orders sent
A  same, every server deployed:                 212 parent orders -> 212 child orders sent
B  fix 1, fresh flag 'rlp' (old code ignores it): 212 parent orders -> 212 child orders sent
B  fix 2, dead code deleted, flag reused:        212 parent orders -> 212 child orders sent
B  fix 3, fleet version checked before the flip: flag flip refused: fleet versions ['new', 'old']
```
Any one of the three fixes alone prevents the failure. The factory's one switch: `pytest tests/test_adapter.py -k previous` → `4 passed` (on, off and removed).

## Related
006-ci-cd.md, 055-rollbacks.md, 053-canary-releases.md, 054-rolling-deployments.md, 010-circuit-breakers.md

## Sources
- "Feature Toggles (aka Feature Flags)", Pete Hodgson, martinfowler.com: https://martinfowler.com/articles/feature-toggles.html
- "In the Matter of Knight Capital Americas LLC", SEC Release No. 34-70694 (2013), paragraphs 13-17: https://www.sec.gov/files/litigation/admin/2013/34-70694.pdf
