import importlib.util
import pathlib
import subprocess

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCOPE = ROOT / "factory/qa/scope.sh"
JOB = yaml.safe_load((ROOT / ".github/workflows/qa-gate.yml").read_text())["jobs"]["review"]
LANES = {lane["check"]: lane for lane in JOB["strategy"]["matrix"]["include"]}


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
        "thermo-nuclear": {"check": "thermo-nuclear", "skill": "/thermo-nuclear-code-quality-review", "model": "opus",
                           "systems": True},
        "ponytail-review": {"check": "ponytail-review", "skill": "/ponytail-review", "model": "sonnet"},
        "ux-laws": {"check": "ux-laws", "skill": "/ux-laws", "model": "sonnet"},
    }
    assert [name for name, lane in LANES.items() if "paths" in lane] == ["ux-laws"]


def test_no_step_branches_on_the_lane_name():
    assert [step["if"] for step in JOB["steps"] if "matrix.check" in step.get("if", "")] == []


def test_review_runs_only_in_scope():
    steps = {step.get("name"): step for step in JOB["steps"]}
    assert steps["Review"]["if"] == "steps.scope.outputs.run == 'true'"
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in str(steps["Skip the review"])


def test_skipped_lane_writes_a_passing_review(tmp_path):
    skip = next(step for step in JOB["steps"] if step.get("name") == "Skip the review")
    subprocess.run(["bash", "-ec", skip["run"]], env={"RUNNER_TEMP": str(tmp_path), "PATH": "/usr/bin:/bin"},
                   check=True)
    gate = next(line for line in next(step for step in JOB["steps"] if step.get("name") == "Review")["run"].splitlines() if line.lstrip().startswith("grep -E"))
    assert subprocess.run(["bash", "-o", "pipefail", "-c", gate], env={"RUNNER_TEMP": str(tmp_path), "PATH": "/usr/bin:/bin"}).returncode == 0


def test_only_the_systems_lane_routes_and_its_review_receives_the_checks():
    steps = {step.get("name"): step for step in JOB["steps"]}
    assert [name for name, lane in LANES.items() if lane.get("systems")] == ["thermo-nuclear"]
    route = steps["Route the systems checks"]
    assert route["if"] == "steps.scope.outputs.run == 'true' && matrix.systems"
    assert 'factory/qa/route.py "origin/${{ github.base_ref }}...pr-head"' in route["run"]
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in str(route)
    assert "${systems:+" in steps["Review"]["run"]


_spec = importlib.util.spec_from_file_location("rules", ROOT / "factory/qa/rules.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)


def test_the_repo_passes_every_rule():
    assert list(rules.findings()) == []


@pytest.mark.parametrize("name, bad, safe, card", [
    ("factory/a.py", "import subprocess\nsubprocess.run(['x'])\n", "import subprocess\nsubprocess.run(['x'], timeout=5)\n",
     "011-timeouts.md"),
    ("factory/a.py", "import subprocess\nsubprocess.run('x', shell=True, timeout=5)\n",
     "import subprocess\nsubprocess.run(['x'], timeout=5)\n", "078-sql-injection.md"),
    (".github/workflows/w.yml", "steps:\n  - uses: actions/checkout@v4\n",
     "steps:\n  - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4.4.0\n", "108-dependency-hell.md"),
    ("factory/a.html", "<script>el.innerHTML = data</script>\n", "<script>el.textContent = data</script>\n", "079-xss.md"),
])
def test_each_rule_catches_its_case_and_accepts_the_safe_form(tmp_path, name, bad, safe, card):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bad)
    assert [finding for finding in rules.findings(tmp_path) if card in finding]
    path.write_text(safe)
    assert list(rules.findings(tmp_path)) == []
