"""Local HTTP/1.1 server for qa_api_pool.gd: counts TCP connections, can drop idle ones."""
import gzip, json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

connections = 0
lock = threading.Lock()
sockets = []

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    wbufsize = -1  # one TCP segment per response, like production servers
    def setup(self):
        global connections
        super().setup()
        with lock:
            connections += 1
            sockets.append(self.connection)
    def log_message(self, *args):
        pass
    def reply(self, body: bytes, extra=None, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        self.handle_any(b"")
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.handle_any(self.rfile.read(length))
    def handle_any(self, payload):
        path = self.path
        if path == "/stats":
            self.reply(json.dumps({"connections": connections}).encode())
        elif path == "/drop":
            # Answer, then close every open connection (simulates an idle keep-alive timeout).
            self.reply(b'{"ok":true}', {"Connection": "close"})
            self.close_connection = True
            with lock:
                for s in sockets:
                    if s is not self.connection:
                        try: s.shutdown(2)
                        except OSError: pass
        elif path == "/close":
            self.reply(b'{"closed":true}', {"Connection": "close"})
            self.close_connection = True
        elif path == "/gzip":
            self.reply(gzip.compress(json.dumps({"city": {"big": "x" * 5000}}).encode()), {"Content-Encoding": "gzip"})
        elif path == "/slow":
            time.sleep(3)
            self.reply(b'{"late":true}')
        else:
            echo = {"path": path, "method": self.command, "key": self.headers.get("Idempotency-Key", ""),
                    "body": payload.decode() if payload else ""}
            self.reply(json.dumps(echo).encode())

server = ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler)
server.daemon_threads = True
server.serve_forever()
