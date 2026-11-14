#!/usr/bin/env python3
"""QA only: forward http://127.0.0.1:PORT to a hosted DRENOVAR server (e.g. the
Cloudflare staging Worker) for a Godot client run in a container whose outbound
traffic must go through an HTTPS proxy (Godot's HTTPClient does not read
HTTPS_PROXY). Python's urllib does. Origin is rewritten to the target origin so the
server's same-origin check sees its own address. Nothing is logged but the status.

usage: qa-hosted-forwarder.py TARGET_URL [PORT]
"""
import sys, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TARGET = sys.argv[1].rstrip('/')
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8418
PASS = {'accept', 'accept-encoding', 'content-type', 'idempotency-key', 'x-drenovar-session',
        'x-drenovar-player', 'x-drenovar-staging-key', 'authorization'}

class Forward(BaseHTTPRequestHandler):
    def handle_one(self, method):
        length = int(self.headers.get('content-length') or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() in PASS}
        headers['User-Agent'] = 'drenovar-godot-qa/1.0'
        if self.headers.get('origin'):
            headers['Origin'] = TARGET
        req = urllib.request.Request(TARGET + self.path, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                status, data, ctype, enc = r.status, r.read(), r.headers.get('content-type'), r.headers.get('content-encoding')
        except urllib.error.HTTPError as e:
            status, data, ctype, enc = e.code, e.read(), e.headers.get('content-type'), e.headers.get('content-encoding')
        self.send_response(status)
        if ctype: self.send_header('Content-Type', ctype)
        if enc: self.send_header('Content-Encoding', enc)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self): self.handle_one('GET')
    def do_POST(self): self.handle_one('POST')
    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\n' % (self.command, args[1] if len(args) > 1 else ''))

ThreadingHTTPServer(('127.0.0.1', PORT), Forward).serve_forever()
