import pathlib
import subprocess

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERDICT = ROOT / "factory/qa/verdict.sh"
SCOPE = ROOT / "factory/qa/scope.sh"
JOB = yaml.safe_load((ROOT / ".github/workflows/qa-gate.yml").read_text())["jobs"]["review"]
LANES = {lane["check"]: lane for lane in JOB["strategy"]["matrix"]["include"]}


@pytest.mark.parametrize("review, passes", [
    ("Looks fine.\n\n**PASS**\n", True),
    ("Looks fine.\nPASS\n", True),
    ("Must fix the loop.\n\n**BLOCK**\n", False),
    ("Fitts's Law, app.html:3, tiny button, enlarge it.\n\n**VIOLATIONS**\n", False),
    ("", False),
    ("A review with no verdict line.\n", False),
    ("**PASS**\nThen a second look found a problem.\nVIOLATIONS\n", False),
])
def test_verdict(tmp_path, review, passes):
    path = tmp_path / "review.md"
    path.write_text(review)
    assert (subprocess.run([VERDICT, path]).returncode == 0) is passes


@pytest.fixture
def repo(tmp_path):
    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=tmp_path, check=True,
                       capture_output=True)

    git("init", "-q", "-b", "main")
    (tmp_path / "app.py").write_text("x = 1\n")
    git("add", ".")
    git("commit", "-qm", "base")

    def head(*files):
        git("checkout", "-qB", "head", "main")
        for name in files:
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text("changed\n")
        git("add", ".")
        git("commit", "-qm", "head")
        return tmp_path

    return head


def scope(cwd, regex, rng="main...head"):
    return subprocess.run([SCOPE, regex, rng], cwd=cwd, capture_output=True, text=True)


UX_PATHS = LANES["ux-laws"]["paths"]


@pytest.mark.parametrize("changed, out", [
    (["web/index.html"], "run=true\n"),
    (["src/App.tsx", "app.py"], "run=true\n"),
    (["factory/intake/templates/page.j2"], "run=true\n"),
    (["app.py"], "run=false\n"),
    (["data.json"], "run=false\n"),
])
def test_scope_with_the_ux_lane_paths(repo, changed, out):
    result = scope(repo(*changed), UX_PATHS)
    assert (result.returncode, result.stdout) == (0, out)


def test_scope_empty_regex_always_runs(repo):
    result = scope(repo("app.py"), "")
    assert (result.returncode, result.stdout) == (0, "run=true\n")


@pytest.mark.parametrize("regex", ["", UX_PATHS])
def test_scope_bad_range_fails_instead_of_skipping(repo, regex):
    result = scope(repo("app.py"), regex, "main...missing")
    assert result.returncode != 0
    assert result.stdout == ""


def test_scope_bad_regex_fails_instead_of_skipping(repo):
    result = scope(repo("app.py"), "(")
    assert result.returncode != 0
    assert result.stdout == ""


def test_lanes():
    assert {name: {k: v for k, v in lane.items() if k != "paths"} for name, lane in LANES.items()} == {
        "thermo-nuclear": {"check": "thermo-nuclear", "skill": "/thermo-nuclear-code-quality-review", "model": "opus"},
        "ponytail-review": {"check": "ponytail-review", "skill": "/ponytail-review", "model": "sonnet"},
        "ux-laws": {"check": "ux-laws", "skill": "/ux-laws", "model": "sonnet"},
    }
    assert [name for name, lane in LANES.items() if "paths" in lane] == ["ux-laws"]


def test_no_step_branches_on_the_lane_name():
    assert [step["if"] for step in JOB["steps"] if "matrix.check" in step.get("if", "")] == []


def test_review_runs_only_in_scope_and_judges_with_verdict_sh():
    steps = {step.get("name"): step for step in JOB["steps"]}
    assert steps["Review"]["if"] == "steps.scope.outputs.run == 'true'"
    assert 'factory/qa/verdict.sh "$RUNNER_TEMP/review.md"' in steps["Review"]["run"]
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in str(steps["Skip the review"])


def test_skipped_lane_writes_a_passing_review(tmp_path):
    skip = next(step for step in JOB["steps"] if step.get("name") == "Skip the review")
    subprocess.run(["bash", "-ec", skip["run"]], env={"RUNNER_TEMP": str(tmp_path), "PATH": "/usr/bin:/bin"},
                   check=True)
    assert subprocess.run([VERDICT, tmp_path / "review.md"]).returncode == 0
