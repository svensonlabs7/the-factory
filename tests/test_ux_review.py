import importlib
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
RUN_ID = "abcd1234"
BRANCH = f"factory/{RUN_ID}"

# A fake sandbox agent. FAKE_UX_VERDICTS is the verdict per review round, the last one repeating.
FAKE_AGENT = """#!/usr/bin/env python3
import os, pathlib, subprocess, sys

workdir, prompt = sys.argv[1], sys.argv[2]
state = pathlib.Path(os.environ["FAKE_STATE"])
os.chdir(workdir)


def count(name):
    (state / name).open("a").write("x")
    return len((state / name).read_text())


def commit(message):
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], check=True)


if "UX_REVIEW.md" in prompt:
    verdicts = os.environ.get("FAKE_UX_VERDICTS", "PASS").split(",")
    verdict = verdicts[min(count("reviews") - 1, len(verdicts) - 1)]
    mode = os.environ.get("FAKE_UX_MODE", "")
    if mode == "symlink":
        os.symlink(os.environ["FAKE_SYMLINK_TARGET"], "UX_REVIEW.md")  # a real host file
    elif mode == "noverdict":
        pathlib.Path("UX_REVIEW.md").write_text("Looks fine to me.\\n")
    else:
        pathlib.Path("UX_REVIEW.md").write_text("Law 10 - page.html:3 - blank ending - add a confirmation\\n**" + verdict + "**\\n")
elif "found the violations" in prompt:
    count("revisions")
    (state / "revise-prompt").write_text(prompt)
    if os.environ.get("FAKE_HOOK_MARKER"):
        hook = pathlib.Path(".git/hooks/pre-push")
        hook.write_text('#!/bin/sh\\ntouch "' + os.environ["FAKE_HOOK_MARKER"] + '"\\n')
        hook.chmod(0o755)
    if os.environ.get("FAKE_NO_FIX"):
        sys.exit(0)
    if os.environ.get("FAKE_DELETE_ALL"):
        subprocess.run(["git", "rm", "-q", "page.html"], check=True)  # the file the build added
        commit("delete the work")
    else:
        pathlib.Path("page.html").open("a").write("<p>done</p> " + str(os.getpid()) + "\\n")
        commit("ux fix")
"""


def git(cwd, *args):
    return subprocess.run(["git", *GIT_ID, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def ux(tmp_path, monkeypatch):
    origin, root = tmp_path / "origin.git", tmp_path / "factory"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(tmp_path, "clone", "-q", str(origin), str(root))
    git(root, "config", "user.name", "t")
    git(root, "config", "user.email", "t@example.com")
    (root / "README.md").write_text("seed")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "seed")
    git(root, "push", "-q", "origin", "HEAD:main")
    (root / ".factory-logs").mkdir()
    (tmp_path / "state").mkdir()
    (tmp_path / "fake-agent.py").write_text(FAKE_AGENT)
    (tmp_path / "fake-agent.py").chmod(0o755)

    monkeypatch.setenv("FACTORY_ROOT", str(root))
    monkeypatch.setenv("FACTORY_AGENT_CMD", str(tmp_path / "fake-agent.py"))
    monkeypatch.setenv("FAKE_STATE", str(tmp_path / "state"))
    sys.modules.pop("factory.review.ux_review", None)
    module = importlib.import_module("factory.review.ux_review")

    def make_run(files):
        maker = tmp_path / "maker"
        git(tmp_path, "clone", "-q", str(origin), str(maker))
        git(maker, "checkout", "-q", "-b", BRANCH)
        for name, text in files.items():
            (maker / name).parent.mkdir(parents=True, exist_ok=True)
            (maker / name).write_text(text)
        git(maker, "add", "-A")
        git(maker, "commit", "-q", "-m", "build")
        git(maker, "push", "-q", "origin", BRANCH)
        (root / ".factory-logs" / f"{RUN_ID}.meta.json").write_text(json.dumps({"branch": BRANCH, "status": "completed"}))

    return module, root, origin, tmp_path / "state", make_run


def calls(state, name):
    return len((state / name).read_text()) if (state / name).exists() else 0


@pytest.mark.parametrize("path", ["page.html", "src/App.tsx", "App.jsx", "style.css", "Card.vue", "templates/base.txt", "views/form.j2", "PAGE.HTML"])
def test_ui_files_are_detected(ux, path):
    assert ux[0].is_ui(path)


@pytest.mark.parametrize("path", ["app.py", "README.md", "data.json", "tests/test_page.py", "factory/intake/webhook_adapter.py"])
def test_other_files_are_not_ui(ux, path):
    assert not ux[0].is_ui(path)


def test_a_run_with_no_ui_files_is_skipped_without_calling_the_agent(ux):
    module, root, _, state, make_run = ux
    make_run({"app.py": "print(1)\n", "README.md": "x"})
    result = module.review_run(RUN_ID)
    assert (result["status"], result["ui_files"], result["rounds"]) == ("skipped", [], [])
    assert calls(state, "reviews") == 0
    assert json.loads((root / ".factory-logs" / f"{RUN_ID}.ux-review.json").read_text())["status"] == "skipped"


def test_a_passing_review_needs_no_revision(ux):
    module, _, origin, state, make_run = ux
    make_run({"page.html": "<p>hi</p>\n", "app.py": "x"})
    result = module.review_run(RUN_ID)
    assert (result["status"], result["revisions"], result["ui_files"]) == ("pass", 0, ["page.html"])
    assert calls(state, "reviews") == 1 and calls(state, "revisions") == 0
    assert git(origin, "rev-list", "--count", f"main..{BRANCH}") == "1"


def test_violations_are_revised_and_rechecked_until_pass(ux, monkeypatch):
    module, root, origin, state, make_run = ux
    monkeypatch.setenv("FAKE_UX_VERDICTS", "VIOLATIONS,PASS")
    make_run({"page.html": "<p>hi</p>\n"})
    result = module.review_run(RUN_ID)

    assert (result["status"], result["revisions"]) == ("pass", 1)
    assert [r["verdict"] for r in result["rounds"]] == ["VIOLATIONS", "PASS"]
    assert git(origin, "rev-list", "--count", f"main..{BRANCH}") == "2"
    assert "blank ending" in (state / "revise-prompt").read_text()
    assert json.loads((root / ".factory-logs" / f"{RUN_ID}.ux-review.json").read_text())["status"] == "pass"


def test_revisions_stop_after_two_rounds(ux, monkeypatch):
    module, _, origin, state, make_run = ux
    monkeypatch.setenv("FAKE_UX_VERDICTS", "VIOLATIONS")
    make_run({"page.html": "<p>hi</p>\n"})
    result = module.review_run(RUN_ID)

    assert (result["status"], result["revisions"]) == ("violations", 2)
    assert calls(state, "reviews") == 3 and calls(state, "revisions") == 2
    assert git(origin, "rev-list", "--count", f"main..{BRANCH}") == "3"


@pytest.mark.parametrize("mode, message", [("symlink", "regular file"), ("noverdict", "does not end with")])
def test_a_malformed_review_is_an_error_not_a_pass(ux, monkeypatch, tmp_path, mode, message):
    module, _, _, _, make_run = ux
    (tmp_path / "host-file").write_text("a host file the agent should not be able to read\nPASS\n")  # would forge a pass
    monkeypatch.setenv("FAKE_SYMLINK_TARGET", str(tmp_path / "host-file"))
    monkeypatch.setenv("FAKE_UX_MODE", mode)
    make_run({"page.html": "<p>hi</p>\n"})
    result = module.review_run(RUN_ID)
    assert result["status"] == "error" and message in result["error"]


@pytest.mark.parametrize("env, message", [("FAKE_NO_FIX", "no commits"), ("FAKE_DELETE_ALL", "no net changes")])
def test_a_revision_that_changes_nothing_or_deletes_the_work_is_an_error(ux, monkeypatch, env, message):
    module, _, origin, _, make_run = ux
    monkeypatch.setenv("FAKE_UX_VERDICTS", "VIOLATIONS,PASS")
    monkeypatch.setenv(env, "1")
    make_run({"page.html": "<p>hi</p>\n"})
    result = module.review_run(RUN_ID)
    assert result["status"] == "error" and message in result["error"]
    assert git(origin, "rev-list", "--count", f"main..{BRANCH}") == "1"


def test_hooks_the_agent_plants_never_run_on_the_host(ux, monkeypatch, tmp_path):
    module, _, _, _, make_run = ux
    marker = tmp_path / "hook-ran"
    monkeypatch.setenv("FAKE_UX_VERDICTS", "VIOLATIONS,PASS")
    monkeypatch.setenv("FAKE_HOOK_MARKER", str(marker))
    make_run({"page.html": "<p>hi</p>\n"})
    assert module.review_run(RUN_ID)["status"] == "pass"
    assert not marker.exists()


def test_the_service_checkout_is_left_clean(ux, monkeypatch):
    module, root, _, _, make_run = ux
    monkeypatch.setenv("FAKE_UX_VERDICTS", "VIOLATIONS,PASS")
    make_run({"page.html": "<p>hi</p>\n"})
    module.review_run(RUN_ID)
    assert git(root, "for-each-ref", "refs/factory/") == ""  # the private refs are removed
    assert git(root, "branch", "--show-current") == "main"
    assert git(root, "branch", "--list", "factory/*") == ""
    assert not any(module.RUNS_DIR.iterdir())


@pytest.mark.parametrize("args, code, text", [(["abcd1234"], 0, "PASS"), (["../etc"], 1, "usage"), ([], 1, "usage"), (["deadbeef"], 1, "no such run")])
def test_the_command_line_reports_pass_and_rejects_bad_arguments(ux, args, code, text):
    _, _, _, _, make_run = ux
    make_run({"page.html": "<p>hi</p>\n"})
    result = subprocess.run([sys.executable, "-m", "factory.review.ux_review", *args], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == code and text in result.stdout + result.stderr


def test_the_command_line_exits_1_and_prints_the_violations(ux, monkeypatch):
    _, _, _, _, make_run = ux
    monkeypatch.setenv("FAKE_UX_VERDICTS", "VIOLATIONS")
    make_run({"page.html": "<p>hi</p>\n"})
    result = subprocess.run([sys.executable, "-m", "factory.review.ux_review", RUN_ID], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 1 and "blank ending" in result.stdout
