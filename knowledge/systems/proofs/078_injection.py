"""Injection: data treated as code.
A. SQL (sqlite3): string-built queries let input rewrite the query; parameters keep input as data.
B. Shell: a branch name git accepts can carry a command. GitHub substitutes ${{ github.base_ref }} into the
   script text before bash runs it (emulated here); passing it through an environment variable keeps it data.
C. Argument injection: a value starting with '-' becomes an option; '--' or a strict pattern stops it."""
import os
import re
import sqlite3
import subprocess
import tempfile

db = sqlite3.connect(":memory:")
db.executescript("""
CREATE TABLE users(name TEXT, password TEXT);
INSERT INTO users VALUES ('operator', 's3cret');
CREATE TABLE tokens(name TEXT, value TEXT);
INSERT INTO tokens VALUES ('claude', 'tok-123');
""")


def login_concat(name, password):
    return db.execute(f"SELECT name FROM users WHERE name = '{name}' AND password = '{password}'").fetchall()


def login_param(name, password):
    return db.execute("SELECT name FROM users WHERE name = ? AND password = ?", (name, password)).fetchall()


def search_concat(term):
    return db.execute(f"SELECT name FROM users WHERE name LIKE '%{term}%'").fetchall()


print("A  login with password \"' OR '1'='1\":")
print(f"A    string-built: {login_concat('operator', chr(39) + ' OR ' + chr(39) + '1' + chr(39) + '=' + chr(39) + '1')}")
print(f"A    parameters:   {login_param('operator', chr(39) + ' OR ' + chr(39) + '1' + chr(39) + '=' + chr(39) + '1')}")
print(f"A  search \"x' UNION SELECT value FROM tokens --\": {search_concat(chr(39).join(['x', ' UNION SELECT value FROM tokens --']))}")
ORDER = {"name": "name", "newest": "rowid DESC"}  # allow-list for what cannot be a parameter
print(f"A  ORDER BY via allow-list, input 'name; DROP TABLE users': {ORDER.get('name; DROP TABLE users', 'rejected')}")

with tempfile.TemporaryDirectory() as repo:
    evil = "main$(touch${IFS}pwned)"
    ok = subprocess.run(["git", "check-ref-format", "--branch", evil], capture_output=True, text=True)
    print(f"\nB  git accepts the branch name {evil!r}: {ok.returncode == 0}")
    script = 'echo "reviewing origin/${{ github.base_ref }}...pr-head"'
    substituted = script.replace("${{ github.base_ref }}", evil)  # what GitHub hands to bash
    subprocess.run(["bash", "-c", substituted], cwd=repo, capture_output=True)
    print(f"B  interpolated into run:   command ran (file 'pwned' created) = {os.path.exists(os.path.join(repo, 'pwned'))}")
    os.remove(os.path.join(repo, "pwned"))
    via_env = 'echo "reviewing origin/$BASE_REF...pr-head"'
    subprocess.run(["bash", "-c", via_env], cwd=repo, env={**os.environ, "BASE_REF": evil}, capture_output=True)
    print(f"B  passed via env var:      command ran = {os.path.exists(os.path.join(repo, 'pwned'))}")

    subprocess.run(["git", "init", "-q", repo], check=True)
    for args, label in ((["git", "-C", repo, "log", "--output=" + os.path.join(repo, "clobbered")], "value '--output=...' as an argument"),
                        (["git", "-C", repo, "log", "--", "--output=" + os.path.join(repo, "clobbered2")], "same value after '--'")):
        subprocess.run(args, capture_output=True)
    print(f"\nC  {'value --output=... as an argument':<36} wrote a file: {os.path.exists(os.path.join(repo, 'clobbered'))}")
    print(f"C  {'same value after --':<36} wrote a file: {os.path.exists(os.path.join(repo, 'clobbered2'))}")
    pattern = re.compile(r"^factory/[A-Za-z0-9][A-Za-z0-9._/-]*$")
    print(f"C  factory's branch pattern accepts '--output=x': {bool(pattern.match('--output=x'))}, '{evil}': {bool(pattern.match(evil))}")
