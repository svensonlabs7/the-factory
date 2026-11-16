#!/usr/bin/env python3
"""Static scan of a repo checkout, before the factory runs anything in it. Reads files as text and never executes them.
Usage: repo_scan.py PATH [--repo owner/name] [--strict]
Prints a verdict and one line per finding: `<severity> <id> <path>:<line> <message>`.
  malicious   remote code fetched and run at install time, a secret-theft workflow, instructions aimed at an AI agent,
              a package known to be malware. Never acknowledgeable. Exit 2.
  suspicious  worth a human look: install-time scripts, hooks, raw-IP and paste-site URLs, executables. Exit 1 with
              --strict unless every id is acknowledged for this repo in factory/scan-acks.txt (or $FACTORY_SCAN_ACKS), else exit 0.
  safe        nothing found. Exit 0.
An id is rule:path:hash of the offending text, so an acknowledged line that changes needs acknowledging again.
Stdlib only."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__"}
VENDOR_DIRS = SKIP_DIRS | {"vendor", "third_party"}  # where compiled files are expected
MAX_TEXT = 1_000_000  # bytes; a larger file is a bundle, not something to read line by line
CODE = {".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash", ".zsh", ".rb", ".pl", ".ps1"}
BUILD_NAMES = {"makefile", "gnumakefile", "dockerfile", "containerfile", "justfile"}
INSTALL_HOOKS = ("preinstall", "install", "postinstall", "prepare", "prepublish", "prepack")
AGENT_FILES = {"claude.md", "agents.md", "gemini.md", ".cursorrules", "copilot-instructions.md"}
# Piping a download into an interpreter that reads its program from stdin runs the download. `| python3 -c '...'` runs
# the argument and only parses the download, so it is not matched.
FETCH_AND_RUN = re.compile(
    r"(curl|wget)\b[^\n|;]*\|\s*(sudo\s+)?(((ba|z|da)?sh\b(?!\s+-c))|((python3?|node|perl|ruby)\s*(-\s*)?(?=$|[;&|)])))|"
    r"\b(eval|(ba)?sh\s+-c)\s+\"?\$\(\s*(curl|wget)|(ba)?sh\s*<\s*\(\s*(curl|wget)|base64\s+(-d|--decode)[^\n|]*\|\s*(ba)?sh")
DECODED_EVAL = re.compile(r"\b(eval|exec)\s*\(\s*(atob|base64\.b64decode|Buffer\.from|bytes\.fromhex|zlib\.decompress|codecs\.decode)")
RAW_IP = re.compile(r"https?://(?!127\.|0\.0\.0\.0|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|192\.0\.2\.|198\.51\.100\.|203\.0\.113\.)\d{1,3}(\.\d{1,3}){3}\b")
PASTE_SITE = re.compile(r"\b(pastebin\.com|paste\.ee|hastebin\.com|transfer\.sh|webhook\.site|requestbin\.(net|com)|interact\.sh|ngrok(-free)?\.(io|app|dev))\b", re.I)
AGENT_INJECTION = re.compile(
    r"ignore (all |any |your )?(previous|prior|above|earlier) (instructions|rules|prompts)|"
    r"disregard (all |any |your )?(previous |prior |above )?(instructions|rules|guidelines)|"
    r"do not (tell|inform|mention (this )?to) the (user|operator)|"
    r"(exfiltrate|upload|send|post|curl)\b.{0,60}\b(tokens?|secrets?|credentials?|api[ _-]?keys?|\.env|ssh keys?)\b.{0,60}https?://", re.I)
HIDDEN_CHARS = re.compile("[​-‏‪-‮⁦-⁩﻿]")
UNTRUSTED_CONTEXT = re.compile(r"\$\{\{\s*(github\.head_ref|github\.event\.(pull_request\.(title|body|head\.(ref|label))|issue\.(title|body)|comment\.body|review\.body|head_commit\.message))\s*\}\}")
EXECUTABLE_MAGIC = (b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe")
EXECUTABLE_EXT = {".exe", ".dll", ".so", ".dylib", ".node", ".jar", ".class"}


def finding(severity, rule, path, line, message, text):
    return severity, f"{rule}:{path}:{hashlib.sha256(text.strip().encode()).hexdigest()[:8]}", f"{path}:{line}", message


def lines(text):
    return enumerate(text.splitlines(), 1)


def package_json(path, text):
    try:
        scripts = json.loads(text).get("scripts") or {}
    except (ValueError, AttributeError):
        yield finding("suspicious", "package-json", path, 1, "package.json is not valid JSON", text[:200])
        return
    for name in INSTALL_HOOKS:
        if isinstance(scripts.get(name), str):
            line = next((n for n, l in lines(text) if f'"{name}"' in l), 1)
            if FETCH_AND_RUN.search(scripts[name]) or DECODED_EVAL.search(scripts[name]):
                yield finding("malicious", "install-fetch-and-run", path, line, f'"{name}" fetches code and runs it at install: {scripts[name]}', scripts[name])
            else:
                yield finding("suspicious", "install-script", path, line, f'"{name}" runs at install: {scripts[name]}', scripts[name])


def setup_py(path, text):
    for number, line in lines(text):
        if FETCH_AND_RUN.search(line) or re.search(r"\bexec\(.*(urlopen|requests\.get|b64decode)", line):
            yield finding("malicious", "install-fetch-and-run", path, number, f"setup.py fetches code and runs it: {line.strip()}", line)
        elif re.search(r"\bcmdclass\b|os\.system\(|subprocess\.", line):
            yield finding("suspicious", "install-script", path, number, f"setup.py runs code at install: {line.strip()}", line)


def build_file(path, text):
    for number, line in lines(text):
        if FETCH_AND_RUN.search(line):
            yield finding("suspicious", "fetch-and-run", path, number, f"downloads and runs code: {line.strip()}", line)


def workflow(path, text):
    if re.search(r"^\s*pull_request_target\s*:", text, re.M) and re.search(r"ref:\s*\$\{\{\s*github\.(head_ref|event\.pull_request\.head\.(sha|ref))", text):
        line = next(n for n, l in lines(text) if "pull_request_target" in l)
        yield finding("malicious", "pwn-request", path, line, "runs on pull_request_target and checks out the PR's code, so a PR can read this repo's secrets", "pwn-request")
    for number, line in lines(text):
        if UNTRUSTED_CONTEXT.search(line) and not re.match(r"\s*[\w-]+:\s*\$\{\{[^}]*\}\}\s*$", line):  # an env value is safe
            yield finding("suspicious", "untrusted-context", path, number, f"puts PR text straight into a shell line: {line.strip()}", line)


def agent_file(path, text):
    for number, line in lines(text):
        if AGENT_INJECTION.search(line) or HIDDEN_CHARS.search(line):
            yield finding("malicious", "agent-instruction", path, number, "text aimed at an AI agent that reads this file: " + HIDDEN_CHARS.sub("<hidden>", line.strip())[:120], line)


def hostile_urls(path, text):
    for number, line in lines(text):
        if RAW_IP.search(line) or PASTE_SITE.search(line):
            yield finding("suspicious", "raw-ip-or-paste-site", path, number, f"talks to a raw IP or a paste or tunnel site: {line.strip()[:120]}", line)
        if DECODED_EVAL.search(line):
            yield finding("malicious", "decoded-eval", path, number, f"runs decoded data as code: {line.strip()[:120]}", line)


def text_rules(rel, name, suffix, text):
    if name == "package.json":
        yield from package_json(rel, text)
    if name == "setup.py":
        yield from setup_py(rel, text)
    if name.lower() in BUILD_NAMES or suffix in {".sh", ".bash", ".mk"}:
        yield from build_file(rel, text)
    if rel.startswith(".github/workflows/") and suffix in {".yml", ".yaml"}:
        yield from workflow(rel, text)
    if name.lower() in AGENT_FILES or (rel.startswith((".cursor/rules/", ".claude/")) and suffix in {".md", ".mdc"}):
        yield from agent_file(rel, text)
    if suffix in CODE or name.lower() in BUILD_NAMES or name == "package.json" or rel.startswith(".github/workflows/"):
        yield from hostile_urls(rel, text)


def osv(root):
    """Packages OSV lists as malware (ids starting MAL-). Other advisories are dependency hygiene, not this scan's job.
    Skipped when osv-scanner is not installed."""
    if not shutil.which("osv-scanner"):
        return
    done = subprocess.run(["osv-scanner", "scan", "--recursive", "--format", "json", str(root)], capture_output=True, text=True, timeout=300)
    try:
        results = json.loads(done.stdout).get("results", [])
    except ValueError:
        return
    for result in results:
        for package in result.get("packages", []):
            for vuln in package.get("vulnerabilities", []):
                if vuln.get("id", "").startswith("MAL-"):
                    name = package["package"]["name"]
                    yield finding("malicious", "known-malicious-dependency", result["source"]["path"], 1, f"{name} is listed as malware ({vuln['id']})", f"{name}{vuln['id']}")


def scan(root):
    root = pathlib.Path(root)
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        here = pathlib.Path(current)
        rel_dir = here.relative_to(root).as_posix()
        if any(rel_dir.endswith(h) for h in (".husky", ".githooks")) and files:
            yield finding("suspicious", "hook-dir", rel_dir, 1, "hook scripts that run on commit once they are installed", rel_dir)
        for name in sorted(files):
            path = here / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.is_file():
                continue
            suffix = path.suffix.lower()
            with path.open("rb") as f:
                head = f.read(4)
            if (head.startswith(EXECUTABLE_MAGIC) or suffix in EXECUTABLE_EXT or head[:2] == b"MZ") and not VENDOR_DIRS & set(rel.split("/")):
                yield finding("suspicious", "executable", rel, 1, "a compiled file outside a vendor folder", rel)
            elif path.stat().st_size <= MAX_TEXT:
                yield from text_rules(rel, name, suffix, path.read_text(errors="replace"))
    yield from osv(root)


def acknowledged(repo, acks_file):
    path = pathlib.Path(acks_file)
    entries = (line.split("#")[0].split() for line in path.read_text().splitlines()) if path.exists() else []
    return {entry[1] for entry in entries if len(entry) == 2 and entry[0].lower() == repo.lower()}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--repo", default="-")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    found = sorted(set(scan(args.path)), key=lambda f: (f[0] != "malicious", f[2]))
    acked = acknowledged(args.repo, os.environ.get("FACTORY_SCAN_ACKS", ROOT / "factory/scan-acks.txt"))
    pending = [f for f in found if f[0] == "suspicious" and f[1] not in acked]
    verdict = "malicious" if any(f[0] == "malicious" for f in found) else "suspicious" if pending else "safe"
    print(f"scan: {verdict}" + ("" if verdict != "safe" or not found else f" ({len(found)} acknowledged or advisory)"))
    for severity, id_, where, message in found:
        print(f"{'acknowledged' if id_ in acked and severity == 'suspicious' else severity} {id_} {where} {message}")
    return 2 if verdict == "malicious" else 1 if verdict == "suspicious" and args.strict else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
