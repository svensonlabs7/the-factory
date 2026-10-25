# 78. SQL Injection

Track: B. Security · Status: proven · Updated: 2026-10-18

Triggers: lines `(?i)\.execute\(|\bselect\b.+\bfrom\b|\binsert into\b|\bupdate\b.+\bset\b|shell=|shlex|os\.system`

## What it is
SQL injection happens when user input is pasted into the text of a query, so input such as `' OR '1'='1` or `' UNION SELECT ...` changes what the query does: logging in without a password, reading other tables, deleting data. The fix is structural: send the query and the values separately (parameterized queries or prepared statements), so the database never parses input as SQL. Escaping is fragile and a last resort. Anything that cannot be a parameter, such as a table name, column or sort order, is mapped from an allow-list defined in code.

It is one case of a wider bug class, injection: data crossing into code. The same flaw appears as:
- **Shell injection:** a command line built as a string.
- **Argument injection:** a value starting with `-` read as an option.
- **CI expression injection:** `${{ }}` pasted into a script.
- **Prompt injection:** untrusted text read as instructions by an LLM.

## When it is worth it
Always, wherever untrusted input meets an interpreter: SQL, a shell, a command's options, a template, a CI script, an LLM prompt. It costs nothing to use parameters and argument lists from the start. There is no load below which string-built queries or shell strings are acceptable. Least-privilege database accounts and input validation are the second layer, never the first.

## How it fails
- **String-built SQL:** `f"... WHERE name = '{name}'"` → input closes the quote and appends its own SQL: authentication bypass, `UNION` data theft, destructive statements.
- **Escaping instead of parameters:** a homemade escape misses one encoding or context → the injection gets through anyway.
- **Unparameterizable parts:** a table name or `ORDER BY` built from input → injection where parameters cannot reach.
- **Shell strings:** `subprocess.run(f"git log {branch}", shell=True)` → `; rm -rf` in the input runs.
- **Argument injection:** a value like `--output=/path` or `--upload-pack=cmd` passed as an argument → the program treats it as an option.
- **CI expression injection:** `run: echo "${{ github.base_ref }}"` → GitHub pastes the text into the script before bash runs, so a branch named `x$(cmd)` executes `cmd` in a job that may hold secrets.

## Review checklist
- [ ] **Are queries parameterized?** · Applies when: the diff adds or changes SQL or another query language. · Block if: any value from input is formatted or concatenated into the query text.
- [ ] **Are unparameterizable parts taken from an allow-list?** · Applies when: a table, column, sort order or operator in a query depends on input. · Block if: the input is used directly instead of being mapped from values defined in code.
- [ ] **Are processes started with an argument list, not a shell string?** · Applies when: the diff starts a subprocess. · Block if: it uses `shell=True`, `os.system`, `sh -c` or a backtick with any input-derived part.
- [ ] **Can an input value become an option?** · Applies when: an input-derived value is passed as an argument to a command. · Block if: the value could start with `-` and is passed with no `--` separator and no pattern that forbids it.
- [ ] **Do CI scripts take event data through environment variables?** · Applies when: the diff adds or edits a `run:` step. · Block if: it interpolates `${{ github.event.* }}`, `github.base_ref` or `github.head_ref` directly into the script text.

## In the factory
- No database, so SQL injection itself is not applicable. The same bug class is checked at the factory's real interpreters below.
- `factory/intake/webhook_adapter.py:313-322` (`_run`) and every other subprocess call: argument lists, never `shell=True`, `os.system` or `sh -c` (grep finds none). Right.
- `factory/intake/webhook_adapter.py:183`: the caller-supplied `branch` must match `^factory/[A-Za-z0-9][A-Za-z0-9._/-]*$`, so it cannot start with `-` or carry shell characters. Right.
- `factory/intake/webhook_adapter.py:263,389-394` (`FIX_TASK_TEMPLATE`, `_fix_prompt`): reviewer findings reach the builder fenced, with `---` defanged and a line saying they are data, not instructions. That is the prompt-injection version of keeping data out of code. Right.
- Gap (low): `.github/workflows/qa-gate.yml:49,61` paste `${{ github.base_ref }}` into `run:` scripts in the privileged `pull_request_target` job. A branch named `main$(cmd)` passes git's name rules, and the emulation ran `cmd` (see GAPS.md).

## Proof
`python3 -I knowledge/systems/proofs/078_injection.py`. A uses an in-memory sqlite3 database. B is git's own name check plus an emulation of GitHub's text substitution, run by bash in a scratch directory. C runs real `git` in a scratch repo:
```
A  login with password "' OR '1'='1":
A    string-built: [('operator',)]
A    parameters:   []
A  search "x' UNION SELECT value FROM tokens --": [('tok-123',)]
A  ORDER BY via allow-list, input 'name; DROP TABLE users': rejected
B  git accepts the branch name 'main$(touch${IFS}pwned)': True
B  interpolated into run:   command ran (file 'pwned' created) = True
B  passed via env var:      command ran = False
C  value --output=... as an argument    wrote a file: True
C  same value after --                  wrote a file: False
C  factory's branch pattern accepts '--output=x': False, 'main$(touch${IFS}pwned)': False
```

## Related
101-webhooks.md, 067-secrets-management.md, 079-xss.md, 080-ssrf.md, 006-ci-cd.md, 074-waf.md

## Sources
- "SQL Injection Prevention Cheat Sheet", OWASP: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
- "OS Command Injection Defense Cheat Sheet", OWASP: https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html
- "Security hardening for GitHub Actions" (script injection), GitHub Docs: https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
