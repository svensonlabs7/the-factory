# Load assumptions

Many cards say a technique is "not needed at today's load". These are the facts that verdict rests on. When a diff
changes a line matching an assumption's `lines` regex, `factory/qa/route.py` re-opens the cards listed, because their verdict may
no longer hold. Keep each `where` pointing at the line that sets the fact.

- **One build worker: runs never overlap** · where `factory/intake/webhook_adapter.py:151` · lines `RUN_EXECUTOR|ProcessPool` · re-check 015 039 043 044 092
- **One adapter process on one host** · where `factory/intake/com.svenson.factory-intake.plist` · lines `--workers|gunicorn|(?i:replicas|instances)` · re-check 001 003 033 037 046 052
- **The origin is reachable only through the tunnel** · where `factory/intake/com.svenson.factory-intake.plist:20-21`, `infra/cloudflare-tunnel/config.yml:7,10` · lines `--host|0\.0\.0\.0|127\.0\.0\.1|service: http|hostname:` · re-check 004 048 075 076 080
- **Load is capped: 5 in flight, 30 runs a day, 2 fix rounds** · where `factory/intake/webhook_adapter.py:58,72-73` · lines `MAX_PENDING|MAX_RUNS_PER_DAY|MAX_RETRIES` · re-check 001 044 088 092
- **The build sandbox holds no GitHub credential** · where `factory/build/run_agent.py:9,42` · lines `forward_env|GH_TOKEN|GITHUB_TOKEN|gh auth` · re-check 067 068 080
- **The gate runs main's copy of the workflow** · where `.github/workflows/qa-gate.yml:3-5` · lines `pull_request_target|pull_request:|ref: \$\{\{` · re-check 006 055 067 068
