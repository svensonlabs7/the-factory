"""DDoS resilience, simulated in virtual time (no network traffic). An origin has 20 connection slots.
For 60 s, 5 slow connections a second arrive that send their request over 300 s, alongside 10 normal requests a
second that need 0.05 s each. Measure how many normal requests the origin serves in three set-ups:
1. exposed directly, no timeout on reading a request;
2. exposed directly, closing any connection that has not sent a full request within 10 s;
3. behind an edge proxy that buffers the whole request before forwarding (as Cloudflare does), so the origin only
   ever sees complete requests."""
import heapq

SLOTS, DURATION, SLOW_RATE, SLOW_TIME, LEGIT_RATE, LEGIT_TIME = 20, 60, 5, 300, 10, 0.05


def run(header_timeout=None, edge_buffers=False):
    events = []
    for i in range(int(DURATION * SLOW_RATE)):
        heapq.heappush(events, (i / SLOW_RATE, "slow"))
    for i in range(int(DURATION * LEGIT_RATE)):
        heapq.heappush(events, (i / LEGIT_RATE + 0.001, "legit"))
    busy, served, refused = [], 0, 0  # busy: heap of times slots free up
    while events:
        t, kind = heapq.heappop(events)
        while busy and busy[0] <= t:
            heapq.heappop(busy)
        if kind == "slow" and edge_buffers:
            continue  # the edge holds the slow upload; the origin never sees an incomplete request
        if len(busy) >= SLOTS:
            refused += kind == "legit"
            continue
        if kind == "slow":
            hold = min(SLOW_TIME, header_timeout) if header_timeout else SLOW_TIME
            heapq.heappush(busy, t + hold)
        else:
            heapq.heappush(busy, t + LEGIT_TIME)
            served += 1
    return served, refused


total = DURATION * LEGIT_RATE
for label, kwargs in (("direct, no read timeout", {}), ("direct, 10 s read timeout", {"header_timeout": 10}), ("direct, 2 s read timeout", {"header_timeout": 2}),
                      ("behind a buffering edge", {"edge_buffers": True})):
    served, refused = run(**kwargs)
    print(f"{label:<28} normal requests served {served:>4}/{total}  ({served / total:.0%})")
