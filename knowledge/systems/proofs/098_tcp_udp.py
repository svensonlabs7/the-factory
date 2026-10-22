"""TCP vs UDP, with real kernel sockets on loopback.

A. UDP (RFC 768: "delivery and duplicate protection are not guaranteed"). Sender -> a lossy relay that
   drops ~30% of datagrams and forwards the rest immediately -> receiver. Shows loss (gone for good, no
   retransmit) and that the app sees only whatever arrived; datagram boundaries are preserved.
B. TCP (RFC 9293: "reliable, in-order, byte-stream"; "no correlation between the boundaries of TCP segments
   sent and received"). Three separate send() calls are read back as one stream: in order and complete, but
   the message boundaries are gone -> the classic framing bug. Fix: length-prefixed framing.
No external network; everything is 127.0.0.1."""
import random
import socket
import struct
import threading

random.seed(7)


# ---- A. UDP through a lossy relay ---------------------------------------------------------------
def udp_demo(n=10, drop=0.3):
    recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv.bind(("127.0.0.1", 0))
    recv.settimeout(0.3)
    relay = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    relay.bind(("127.0.0.1", 0))
    relay.settimeout(0.3)
    sent = list(range(n))

    def run_relay():  # forward datagrams, dropping some; UDP has no retransmission to recover them
        kept = 0
        while kept < n:
            try:
                data, _ = relay.recvfrom(1024)
            except socket.timeout:
                break
            kept += 1
            if random.random() >= drop:
                relay.sendto(data, recv.getsockname())

    t = threading.Thread(target=run_relay)
    t.start()
    send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for i in sent:
        send.sendto(struct.pack("!I", i), relay.getsockname())
    got = []
    while True:
        try:
            got.append(struct.unpack("!I", recv.recv(1024)[:4])[0])
        except socket.timeout:
            break
    t.join()
    lost = [i for i in sent if i not in got]
    print(f"A  UDP: sent {sent}")
    print(f"A  UDP: received {got}  -> {len(lost)} datagram(s) lost for good {lost}, no retransmit")
    for s in (recv, relay, send):
        s.close()


# ---- B. TCP: ordered byte stream, no message boundaries -----------------------------------------
def tcp_demo():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    msgs = [b"AAAA", b"BBBB", b"CCCC"]

    done = threading.Event()

    def client():
        c = socket.create_connection(srv.getsockname())
        for m in msgs:  # three distinct application messages, three send() calls
            c.sendall(m)
        done.set()  # let the receiver read only after all three have been sent
        c.shutdown(socket.SHUT_WR)
        c.close()

    t = threading.Thread(target=client)
    t.start()
    conn, _ = srv.accept()
    done.wait(1.0)
    first = conn.recv(4096)  # one read can span several messages: boundaries are gone
    rest = b""
    while chunk := conn.recv(4096):
        rest += chunk
    stream = first + rest
    t.join()
    conn.close()
    srv.close()
    merged = len(first) > len(msgs[0])  # the first read already pulled in >1 message
    print(f"B  TCP: three sends {msgs}; first recv returned {first!r} "
          f"({'multiple messages merged -> boundaries gone' if merged else 'one message'})")
    print(f"B  TCP: full stream {stream!r} -> in order and complete "
          f"({'=' if stream == b''.join(msgs) else '!='} concatenation of the sends)")
    print("B  fix: length-prefix each message (struct.pack('!I', len(m)) + m) and read exactly that many bytes")


udp_demo()
tcp_demo()
