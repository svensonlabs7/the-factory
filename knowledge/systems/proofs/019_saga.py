"""Sagas: a trip booking as an orchestrated saga of three local transactions on three SQLite files (flight, hotel, card),
each with a compensating transaction. Run it four ways.
A. The card is declined: compensations run in reverse, nothing is left reserved.
B. The orchestrator crashes after two steps. Without a durable saga log the reservations are orphaned; with one, a
   recovery pass reads the log and compensates.
C. Isolation: another process reads the hotel between T2 and its compensation. Without a semantic lock it sees a
   CONFIRMED booking that is later cancelled; with one (status PENDING until the saga ends) it does not.
D. A compensation fails transiently: it is retried, and running it twice is harmless (idempotent)."""
import json
import os
import sqlite3
import tempfile

D = tempfile.mkdtemp()
LOG = os.path.join(D, "saga.log")


def db(name):
    conn = sqlite3.connect(os.path.join(D, f"{name}.db"), isolation_level=None)
    conn.execute("CREATE TABLE IF NOT EXISTS res(trip TEXT PRIMARY KEY, status TEXT)")
    return conn


def reset():
    for n in ("flight", "hotel", "card"):
        db(n).execute("DELETE FROM res")
    if os.path.exists(LOG):
        os.unlink(LOG)


def reserve(name, trip, status="CONFIRMED", fail=False):
    if fail:
        raise RuntimeError(f"{name} declined")
    db(name).execute("INSERT INTO res VALUES (?, ?)", (trip, status))


flaky = {"left": 0}


def cancel(name, trip):
    if flaky["left"] > 0:
        flaky["left"] -= 1
        raise ConnectionError(f"{name} unavailable")
    db(name).execute("DELETE FROM res WHERE trip = ?", (trip,))   # deleting twice is a no-op: idempotent


def log(entry):
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def compensate(done, trip):
    for name in reversed(done):
        for attempt in range(1, 6):
            try:
                cancel(name, trip)
                break
            except ConnectionError:
                continue
        log({"trip": trip, "compensated": name})


def saga(trip, decline=False, crash_after=None, durable=True, status="CONFIRMED"):
    done = []
    for name in ("flight", "hotel", "card"):
        if crash_after is not None and len(done) == crash_after:
            return "crashed"
        try:
            reserve(name, trip, status, fail=(decline and name == "card"))
        except RuntimeError:
            compensate(done, trip)
            return "compensated"
        done.append(name)
        if durable:
            log({"trip": trip, "done": name})
    for name in ("flight", "hotel"):
        db(name).execute("UPDATE res SET status = 'CONFIRMED' WHERE trip = ?", (trip,))
    return "completed"


def left_reserved():
    return {n: db(n).execute("SELECT count(*) FROM res").fetchone()[0] for n in ("flight", "hotel", "card")}


reset()
print(f"A  card declined: saga {saga('t1', decline=True)}; left reserved {left_reserved()}")

for durable in (False, True):
    reset()
    outcome = saga("t2", crash_after=2, durable=durable)
    done = [json.loads(l)["done"] for l in open(LOG)] if os.path.exists(LOG) else []
    compensate(done, "t2")                    # recovery pass: only what the log says was done
    print(f"B  crash after 2 steps, {'durable saga log' if durable else 'no saga log    '}: recovery found {done}; left reserved {left_reserved()}")

for status in ("CONFIRMED", "PENDING"):
    reset()
    reserve("flight", "t3", status)
    reserve("hotel", "t3", status)
    seen = db("hotel").execute("SELECT status FROM res WHERE trip = 't3'").fetchone()[0]   # another reader, mid-saga
    acted = seen == "CONFIRMED"                                                              # e.g. emails the guest
    compensate(["flight", "hotel"], "t3")                                                    # the card is then declined
    print(f"C  {'no semantic lock' if status == 'CONFIRMED' else 'semantic lock   '}: reader saw {seen}, acted on a booking that was cancelled: {acted}")

reset()
flaky["left"] = 2
print(f"D  compensation fails twice, then succeeds: saga {saga('t4', decline=True)}; left reserved {left_reserved()}; cancelling again: {cancel('hotel', 't4') or 'no-op'}")
