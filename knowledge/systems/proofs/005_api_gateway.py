"""API gateways: one place enforces the cross-cutting rules, so every backend route gets them and cannot be
reached without them.

This mirrors the factory's gateway (factory/intake/webhook_adapter.py): HMAC auth, a replay/freshness check,
request validation, an admission limit, then routing to the one backend action. The interesting gateway job
here is VALIDATION: the TriggerPayload model constrains `branch` to ^factory/... so the "never touch a base
branch" invariant is enforced at the door, once, instead of trusted inside the agent.

A. Validation at the gateway: the real TriggerPayload pattern accepts valid factory branches and rejects
   main, traversal, absolute and injection-shaped branches with 422 -- they never reach the backend.
B. Gateway vs no gateway: a backend that commits to whatever branch it is handed is safe behind the gateway
   (bad branches are stopped) and dangerous when reached directly (it would commit to main).
Run with: uv run --with pydantic python 005_api_gateway.py"""
from typing import Optional

from pydantic import BaseModel, Field, ValidationError


class TriggerPayload(BaseModel):  # identical to webhook_adapter.py:180-183
    task: str
    branch: Optional[str] = Field(default=None, pattern=r"^factory/[A-Za-z0-9][A-Za-z0-9._/-]*$")


def through_gateway(task, branch):
    """What /trigger does with the body before routing: validate, or 422."""
    try:
        return TriggerPayload(task=task, branch=branch), None
    except ValidationError:
        return None, 422


def backend_commit(branch):
    """The one backend action, trusting its input: commit to the given branch (default a factory branch)."""
    return branch or "factory/<generated>"


print("A  gateway validation of `branch`:")
cases = ["factory/feat-x", "factory/a/b.c-1", None, "main", "../main", "/etc/x",
         "factory/x; rm -rf /", "release", "factory/"]
for b in cases:
    payload, err = through_gateway("do a thing", b)
    verdict = "422 rejected" if err else f"accepted -> {payload.branch!r}"
    print(f"   branch={b!r:24} -> {verdict}")

print("\nB  same backend, with and without the gateway, for a request asking to commit to main:")
payload, err = through_gateway("ship it", "main")
print(f"   through gateway : {'422 rejected, backend never runs' if err else 'reached backend'}  "
      f"<- invariant held")
print(f"   direct to backend: backend commits to {backend_commit('main')!r}  <- base branch clobbered")
