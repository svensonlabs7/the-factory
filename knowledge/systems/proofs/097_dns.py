"""DNS caching, driven by the factory's real measured values (A TTL 300 s on factory.svensonlabs.dev;
zone SOA negative TTL / MINIMUM field 1800 s).

A. Negative caching (RFC 2308): a lookup for a name that does not exist yet is cached as NXDOMAIN for the
   zone's negative TTL. Create the name a minute later and clients still fail until that TTL expires.
   Failure: default 1800 s negative TTL -> a freshly created name is unreachable for ~29 more minutes.
   Fix: lower the SOA MINIMUM before creating names, so the negative entry expires fast.
B. Positive-TTL cutover (RFC 1034): changing an A record is invisible to resolvers for up to TTL seconds.
   Failure: flip the record with the normal 300 s TTL -> up to 5 min of clients hitting the old IP.
   Fix: lower the TTL well before the change, flip, then raise it again -> stale window bounded by the low TTL.
Deterministic virtual clock; no network. The TTLs are the ones measured with dig against the live zone."""


class Resolver:
    """A caching resolver that honours positive TTLs and RFC 2308 negative caching."""

    def __init__(self):
        self.pos = {}  # name -> (ip, expires_at)
        self.neg = {}  # name -> expires_at

    def resolve(self, zone, name, now):
        if name in self.neg and now < self.neg[name]:
            return None  # cached "does not exist"
        if name in self.pos and now < self.pos[name][1]:
            return self.pos[name][0]
        ip, ttl, neg_ttl = zone(name, now)  # ask authoritative
        if ip is None:
            self.neg[name] = now + neg_ttl
        else:
            self.neg.pop(name, None)
            self.pos[name] = (ip, now + ttl)
        return ip


A_TTL, NEG_TTL = 300, 1800  # measured: dig factory.svensonlabs.dev A -> 300; zone SOA MINIMUM -> 1800


def make_zone(created_at, neg_ttl):
    """An authoritative zone where 'new.svensonlabs.dev' starts missing and is created at created_at."""
    def zone(name, now):
        if name == "new.svensonlabs.dev" and now < created_at:
            return (None, A_TTL, neg_ttl)      # NXDOMAIN, carrying the zone's negative TTL
        return ("104.21.45.110", A_TTL, neg_ttl)
    return zone


def first_success(neg_ttl):
    r = Resolver()
    zone = make_zone(created_at=60, neg_ttl=neg_ttl)  # client asks at t=0, name created at t=60
    for now in range(0, 3600, 10):
        if r.resolve(zone, "new.svensonlabs.dev", now):
            return now
    return None


print(f"A  name created at t=60 s; negative TTL {NEG_TTL} s -> first resolves at t={first_success(NEG_TTL)} s "
      f"({(first_success(NEG_TTL) - 60) // 60} min of failure after it existed)")
print(f"A  lower SOA MINIMUM to 60 s first      -> first resolves at t={first_success(60)} s (fix)")

# B. Positive-TTL cutover: old IP cached at t=0, record flipped to a new IP at t=100.
def stale_window(ttl):
    r, flip = Resolver(), 100
    zone = lambda name, now: (("10.0.0.2" if now >= flip else "10.0.0.1"), ttl, NEG_TTL)
    r.resolve(zone, "api.svensonlabs.dev", 0)              # warm the cache with the old IP
    now = flip
    while r.resolve(zone, "api.svensonlabs.dev", now) != "10.0.0.2":
        now += 1
    return now - flip


print(f"B  flip A record with TTL {A_TTL} s  -> clients see new IP after {stale_window(A_TTL)} s of stale answers")
print(f"B  drop TTL to 30 s before the flip -> stale window {stale_window(30)} s (RFC 1034: lower TTL ahead of a change)")
