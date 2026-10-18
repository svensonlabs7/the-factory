# Gaps

Places where the factory falls short of a topic card. `/systems-mastery` appends rows; the operator turns them into factory tasks and marks them done.

| Topic | Where | Failure scenario | Severity | Status |
|---|---|---|---|---|
| Timeouts | `.github/workflows/qa-gate.yml:12`, `tests.yml:11`, `static.yml:12`, `static.yml:20` | No job sets `timeout-minutes`, so GitHub's 360-minute default applies. A hung Claude review keeps using runner minutes and plan usage for up to 6 hours, long after the adapter stopped waiting at `CHECKS_TIMEOUT` (20 min) and marked the run `error`. | medium | open |
| Timeouts | `factory/build/run_agent.py:34-35`, `factory/intake/webhook_adapter.py:53` | The comments say the agent's shorter limit lets it end itself. `acp_prompt_timeout` is an idle timeout that every progress event resets: given 40 s, a real run lasted 625 s. Only `AGENT_TIMEOUT` bounds a round. Anyone tuning limits from the comment will trust a deadline that does not exist. | low | open |
