"""HTTP/2 vs HTTP/3: head-of-line blocking.

Both multiplex many logical streams onto one connection, so neither has HTTP/1.1's request-level HOL blocking
(where a slow response holds the whole connection). The difference is the transport under the multiplexing:
- HTTP/2 runs over ONE TCP connection. TCP delivers one ordered byte stream, so a single lost segment holds
  back every byte behind it -- across ALL multiplexed streams (RFC 9113 notes this is why HTTP/3 exists).
- HTTP/3 runs over QUIC (UDP), which has independent per-stream delivery, so a loss on one stream delays only
  that stream (RFC 9114 / RFC 9000).

Model: 3 streams x 4 segments, round-robin interleaved on the wire, one segment arriving per tick. The 4th
segment on the wire (stream 0's 2nd) is lost and its retransmit arrives RTT=10 ticks later. A segment is
deliverable to the app when it and everything it must wait behind have arrived. Compute each stream's
completion tick under each transport's ordering rule. Deterministic; no network."""
STREAMS, PER, RTT = 3, 4, 10

# Round-robin interleave: wire[k] = (stream, seq). One arrives per tick, tick = k+1.
wire = [(k % STREAMS, k // STREAMS) for k in range(STREAMS * PER)]
LOST = 3  # wire index of the lost segment -> stream 0, seq 1
arrival = {}
for k, seg in enumerate(wire):
    arrival[seg] = (k + 1) + (RTT if k == LOST else 0)  # the lost one is retransmitted RTT ticks later


def completion(dep):
    """dep(seg) -> the set of segments that must have arrived before seg is deliverable (transport-specific)."""
    done = {}
    for seg in wire:
        done[seg] = max([arrival[seg]] + [done[d] for d in dep(seg)])
    return {s: max(done[(s, q)] for q in range(PER)) for s in range(STREAMS)}


# HTTP/2 over TCP: one ordered byte stream -> a segment waits behind EVERY earlier segment on the wire.
h2 = completion(lambda seg: [w for w in wire[:wire.index(seg)]])
# HTTP/3 over QUIC: independent streams -> a segment waits only behind earlier segments of its OWN stream.
h3 = completion(lambda seg: [(seg[0], q) for q in range(seg[1])])

print(f"lost segment: wire index {LOST} = stream {wire[LOST][0]} seq {wire[LOST][1]}; retransmit +{RTT} ticks")
for s in range(STREAMS):
    note = "  <- stalled by stream 0's loss" if h2[s] > h3[s] else ""
    print(f"  stream {s}: HTTP/2 done at t={h2[s]:2d}   HTTP/3 done at t={h3[s]:2d}{note}")
mean2, mean3 = sum(h2.values()) / STREAMS, sum(h3.values()) / STREAMS
print(f"mean completion: HTTP/2 t={mean2:.2f}, HTTP/3 t={mean3:.2f} "
      f"(one stream's loss adds {mean2 - mean3:.2f} ticks to the average under HTTP/2; the tail t={max(h2.values())} "
      f"is the lost stream itself, same either way)")
