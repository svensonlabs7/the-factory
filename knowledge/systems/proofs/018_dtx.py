"""Distributed transactions on two SQLite files ("bank A" and "bank B"), moving 100 from A to B.
A. Two independent commits with a crash in between: money disappears.
B. One transaction over both files (ATTACH; SQLite commits multi-file transactions atomically through a super-journal):
   the same crash rolls back both.
C. Two-phase commit's blocking problem: B is prepared (its write transaction holds the database lock) and the
   coordinator dies before deciding. Any other writer to B now waits, then fails, until someone resolves B."""
import os
import sqlite3
import tempfile

d = tempfile.mkdtemp()
A, B = os.path.join(d, "a.db"), os.path.join(d, "b.db")


def reset():
    for path, bal in ((A, 1000), (B, 1000)):
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE IF NOT EXISTS acct(id INTEGER PRIMARY KEY, bal INTEGER)")
        db.execute("DELETE FROM acct")
        db.execute("INSERT INTO acct VALUES (1, ?)", (bal,))
        db.commit()
        db.close()


def total():
    return sum(sqlite3.connect(p).execute("SELECT bal FROM acct").fetchone()[0] for p in (A, B))


reset()
a, b = sqlite3.connect(A), sqlite3.connect(B)
a.execute("UPDATE acct SET bal = bal - 100")
a.commit()                                   # step 1 committed
try:
    raise SystemExit("crash")                # the process dies before step 2
except SystemExit:
    pass
print(f"A  two independent commits, crash between them: total {total()} (was 2000)")

reset()
db = sqlite3.connect(A, isolation_level=None)
db.execute("ATTACH DATABASE ? AS b", (B,))
db.execute("BEGIN")
db.execute("UPDATE main.acct SET bal = bal - 100")
db.execute("UPDATE b.acct SET bal = bal + 100")
db.execute("ROLLBACK")                       # the crash before COMMIT: SQLite undoes both files
db.close()
after_rollback = total()
db = sqlite3.connect(A, isolation_level=None)
db.execute("ATTACH DATABASE ? AS b", (B,))
db.execute("BEGIN")
db.execute("UPDATE main.acct SET bal = bal - 100")
db.execute("UPDATE b.acct SET bal = bal + 100")
db.execute("COMMIT")
print(f"B  one transaction across both files: after a rollback total {after_rollback}, after a commit total {total()}, A={sqlite3.connect(A).execute('SELECT bal FROM acct').fetchone()[0]}")

reset()
participant = sqlite3.connect(B, isolation_level=None)
participant.execute("BEGIN IMMEDIATE")       # phase 1: B votes yes and holds its write lock until the decision
participant.execute("UPDATE acct SET bal = bal + 100")
# The coordinator dies here, before sending COMMIT or ROLLBACK.
other = sqlite3.connect(B, timeout=0.5)
try:
    other.execute("UPDATE acct SET bal = bal - 1")
    other.commit()
    blocked = "succeeded"
except sqlite3.OperationalError as exc:
    blocked = f"OperationalError: {exc}"
print(f"C  coordinator gone with B prepared: another writer to B -> {blocked}")
participant.execute("ROLLBACK")              # recovery: someone must decide for the lost coordinator
print(f"C  after a recovery process rolls B back: total {total()}")
