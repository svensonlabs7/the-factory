"""What an on-path observer sees. A local TCP relay records every byte between a client and a server.
A. Plain HTTP to a local server: the secret header is in the relay's capture.
B. TLS to github.com through the relay: the secret is not in the capture, but the hostname is (SNI in the ClientHello)."""
import http.server
import socket
import ssl
import threading

SECRET = "X-Api-Key: demo-secret-7f3a9c"


def relay(listen_port, target, captured):
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", listen_port))
    srv.listen(1)

    def pump(src, dst):
        try:
            while data := src.recv(65536):
                captured.extend(data)
                dst.sendall(data)
        except OSError:
            pass
        finally:
            dst.close()

    def run():
        client, _ = srv.accept()
        upstream = socket.create_connection(target)
        threading.Thread(target=pump, args=(client, upstream), daemon=True).start()
        pump(upstream, client)
    threading.Thread(target=run, daemon=True).start()


class Quiet(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


web = http.server.HTTPServer(("127.0.0.1", 0), Quiet)
threading.Thread(target=web.serve_forever, daemon=True).start()

plain = bytearray()
relay(9711, ("127.0.0.1", web.server_address[1]), plain)
with socket.create_connection(("127.0.0.1", 9711)) as s:
    s.sendall(f"GET / HTTP/1.1\r\nHost: local\r\n{SECRET}\r\nConnection: close\r\n\r\n".encode())
    while s.recv(4096):
        pass
print(f"A  plain HTTP: observer captured {len(plain)} bytes; secret visible = {SECRET.encode() in plain}")

tls = bytearray()
relay(9712, ("github.com", 443), tls)
ctx = ssl.create_default_context()
with socket.create_connection(("127.0.0.1", 9712)) as raw, ctx.wrap_socket(raw, server_hostname="github.com") as s:
    s.sendall(f"GET / HTTP/1.1\r\nHost: github.com\r\n{SECRET}\r\nConnection: close\r\n\r\n".encode())
    status = s.recv(64).split(b"\r\n")[0].decode()
    version = s.version()
print(f"B  TLS ({version}, server answered '{status}'): observer captured {len(tls)} bytes; "
      f"secret visible = {SECRET.encode() in tls}; hostname 'github.com' visible = {b'github.com' in tls}")
