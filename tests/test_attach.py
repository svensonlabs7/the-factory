import json
import os
import pathlib
import re
import subprocess

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = yaml.safe_load((ROOT / ".github/workflows/qa-gate.yml").read_text())
JOB = GATE["jobs"]["review"]
LANES = [lane["check"] for lane in JOB["strategy"]["matrix"]["include"]]
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


def fake_gh(tmp_path, body):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "gh").write_text("#!/bin/sh\n" + body)
    (bin_dir / "gh").chmod(0o755)
    return {**ENV, "PATH": f"{bin_dir}:{ENV['PATH']}", "STATE": str(tmp_path)}


def test_the_gate_can_be_called_and_needs_the_pinned_commit():
    assert set(GATE[True]) == {"pull_request_target", "workflow_call"}
    assert GATE[True]["workflow_call"]["inputs"]["factory_ref"]["required"]


def test_the_install_step_copies_the_gate_beside_the_base_and_never_over_it(tmp_path):
    step = next(s for s in JOB["steps"] if s.get("name") == "Install the gate's files")
    assert step["if"] == "github.repository != 'svensonlabs7/the-factory'"
    files = {".gate/.claude/skills/x/SKILL.md": "gate", ".gate/.claude/skills/y/SKILL.md": "gate", ".gate/factory/qa/scope.sh": "gate",
             ".gate/knowledge/systems/c.md": "gate", ".claude/skills/x/SKILL.md": "the repo's own", "knowledge/own.md": "own"}
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    subprocess.run(["bash", "-ec", step["run"]], cwd=tmp_path, check=True)
    read = lambda name: (tmp_path / name).read_text()
    assert read(".claude/skills/x/SKILL.md") == "the repo's own" and read(".claude/skills/y/SKILL.md") == "gate"
    assert read("factory/qa/scope.sh") == "gate" and read("knowledge/systems/c.md") == "gate" and read("knowledge/own.md") == "own"


def test_a_missing_token_fails_every_lane_with_the_reason(tmp_path):
    step = next(s for s in JOB["steps"] if s.get("name") == "Check the token")
    run = lambda token: subprocess.run(["bash", "-c", step["run"].replace("${{ github.repository }}", "acme/app")], env={"TOKEN": token, "PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
    assert run("sk").returncode == 0
    failed = run("")
    assert failed.returncode == 1 and "gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo acme/app" in failed.stdout


def test_the_caller_pins_one_commit_twice_and_protect_requires_the_checks_it_produces():
    caller = yaml.safe_load((ROOT / "factory/qa/caller.yml").read_text().replace("__SHA__", "abc123").replace("__BRANCH__", "trunk"))
    job = caller["jobs"]["gate"]
    assert job["uses"] == "svensonlabs7/the-factory/.github/workflows/qa-gate.yml@abc123" and job["with"]["factory_ref"] == "abc123"
    assert job["secrets"] == "inherit" and caller[True]["pull_request_target"]["branches"] == ["trunk"]
    protect = (ROOT / "factory/qa/protect.sh").read_text()
    contexts = json.loads(re.search(r"<<'JSON'.*?\n(.*?)\nJSON", protect, re.S)[1])["required_status_checks"]["contexts"]
    assert contexts == [f"gate / {lane}" for lane in LANES]  # the caller's job is named gate, and each lane's job its check


def test_attach_opens_a_pr_with_the_caller_pinned_to_the_factorys_main(tmp_path):
    remote = tmp_path / "acme.git"
    seed = tmp_path / "seed"
    for args in (["init", "-q", "--bare", "-b", "trunk", str(remote)], ["clone", "-q", str(remote), str(seed)]):
        subprocess.run(["git", *args], check=True, env=ENV, capture_output=True)
    (seed / "README.md").write_text("app")
    for args in (["add", "-A"], ["commit", "-q", "-m", "seed"], ["push", "-q", "origin", "HEAD:trunk"]):
        subprocess.run(["git", *args], cwd=seed, check=True, env=ENV, capture_output=True)
    env = fake_gh(tmp_path, '''echo "$*" >> "$STATE/gh.log"
case "$1 $2" in
  "api repos/svensonlabs7/the-factory/commits/main") echo abc123def ;;
  "repo view") echo trunk ;;
  "repo clone") git clone -q "$REMOTE" "$4" ;;
  "pr create") echo https://example.invalid/pull/9 ;;
esac''')
    env["REMOTE"] = str(remote)
    done = subprocess.run([ROOT / "factory/qa/attach.sh", "acme/app"], env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    workflow = subprocess.run(["git", "show", "factory/attach-gate:.github/workflows/qa-gate.yml"], cwd=remote, capture_output=True, text=True, check=True).stdout
    assert workflow.count("abc123def") == 2 and "branches: [trunk]" in workflow and "__" not in workflow.replace("__BRANCH__", "")
    log = (tmp_path / "gh.log").read_text()
    assert "pr create --repo acme/app --base trunk --head factory/attach-gate" in log
    assert subprocess.run([ROOT / "factory/qa/attach.sh", "not a repo"], env=env, capture_output=True).returncode == 2


def test_protect_requires_the_lanes_on_the_default_branch_for_admins_too(tmp_path):
    env = fake_gh(tmp_path, '''case "$1" in
  repo) echo trunk ;;
  api) echo "$*" > "$STATE/put.args"; cat > "$STATE/put.json" ;;
esac''')
    done = subprocess.run([ROOT / "factory/qa/protect.sh", "acme/app"], env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert "repos/acme/app/branches/trunk/protection" in (tmp_path / "put.args").read_text()
    body = json.loads((tmp_path / "put.json").read_text())
    assert body["enforce_admins"] is True and body["required_status_checks"]["strict"] is True
    assert subprocess.run([ROOT / "factory/qa/protect.sh", "../x"], env=env, capture_output=True).returncode == 2
