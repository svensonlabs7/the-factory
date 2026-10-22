"""Pub/sub delivery, with real sockets: a publisher fans each event out to every subscriber connected at that moment
(Redis PUBLISH semantics: at-most-once, nothing stored). One subscriber is disconnected for part of the run.
A. Fire-and-forget fan-out: the reconnecting subscriber misses what was published while it was away.
B. Durable subscription: events are kept in a log and each subscriber reads from its own offset, so it catches up.
C. Edge vs level: a watcher that tracks a PR's state from events alone is stuck on the missed transition; one that
   polls the current state (what the factory does with `gh pr checks`) is right on its next poll."""
import socket
import threading
import time

EVENTS = ["checks: pending", "checks: running", "checks: completed (pass)", "pr: merged"]


class Broker:
    def __init__(self):
        self.subs, self.log = [], []
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            conn, _ = self.server.accept()
            self.subs.append(conn)

    def publish(self, event):
        self.log.append(event)
        for conn in list(self.subs):           # fan out to whoever is connected now
            try:
                conn.sendall(event.encode() + b"\n")
            except OSError:
                self.subs.remove(conn)


def subscriber(port, received, stop):
    s = socket.create_connection(("127.0.0.1", port))
    s.settimeout(0.05)
    buf = b""
    while not stop.is_set():
        try:
            chunk = s.recv(1024)
            if not chunk:
                break
            buf += chunk
        except socket.timeout:
            continue
    received.extend(buf.decode().splitlines())
    s.close()


broker = Broker()
steady, flaky_a, flaky_b = [], [], []
stop_steady, stop_a, stop_b = threading.Event(), threading.Event(), threading.Event()
threading.Thread(target=subscriber, args=(broker.port, steady, stop_steady)).start()
threading.Thread(target=subscriber, args=(broker.port, flaky_a, stop_a)).start()
time.sleep(0.1)
broker.publish(EVENTS[0])
time.sleep(0.1)
stop_a.set()                                    # the flaky subscriber drops (deploy, network blip)
time.sleep(0.1)
broker.publish(EVENTS[1])
broker.publish(EVENTS[2])
threading.Thread(target=subscriber, args=(broker.port, flaky_b, stop_b)).start()   # it reconnects
time.sleep(0.1)
broker.publish(EVENTS[3])
time.sleep(0.1)
stop_steady.set()
stop_b.set()
time.sleep(0.2)
flaky = flaky_a + flaky_b
print(f"A  fire-and-forget: steady subscriber got {len(steady)}/4; flaky subscriber got {len(flaky)}/4 -> {flaky}")

offset = len(flaky_a)                           # a durable subscription remembers where this subscriber stopped
print(f"B  durable log + offset: flaky subscriber reads from offset {offset} on reconnect -> {broker.log[offset:]}")

edge_state = next((e for e in reversed(flaky) if e.startswith("checks")), None)
level_state = broker.log[2]                     # polling asks for the current check state, whatever was missed
print(f"C  edge-triggered checks state from events: {edge_state!r}; level-triggered poll of current state: {level_state!r}")
