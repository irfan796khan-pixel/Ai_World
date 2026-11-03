"""Serves the AI World folder on http://localhost:8081 and passes voice requests to VoiceStudio.

Why: the page (port 8081) and VoiceStudio (port 3900) are different addresses, so the browser
blocks the page from calling VoiceStudio directly. The page calls /v1/audio/... on THIS server
instead, and this server forwards it to VoiceStudio on 127.0.0.1:3900. No extra packages needed.

Run:  python page_server.py            (port 8081)
      python page_server.py 8090       (another port)
"""
import hashlib
import http.server
import os
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.request

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
VOICESTUDIO = "http://127.0.0.1:3900"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "voice_cache")   # every line VoiceStudio made once is kept here: the same line plays at once next time
ONE_AT_A_TIME = threading.Lock()            # VoiceStudio has one worker: send it one line at a time (no "queue full" errors)


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if self.path.startswith("/v1/"):
            sys.stderr.write("voice: " + (fmt % args) + "\n")

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # always load the newest Girl_Room.html
        super().end_headers()

    def _voice(self, method):
        body = None
        if method == "POST":
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
        key = None
        if method == "POST" and self.path.startswith("/v1/audio/speech"):
            key = os.path.join(CACHE, hashlib.sha1(body).hexdigest() + ".mp3")
            if os.path.exists(key):                       # made before: send it at once
                with open(key, "rb") as f:
                    return self._send(200, "audio/mpeg", f.read(), "hit")
        data, status, ctype = self._ask_voicestudio(method, body)
        if key and status == 200 and data:
            os.makedirs(CACHE, exist_ok=True)
            with open(key + ".part", "wb") as f:
                f.write(data)
            os.replace(key + ".part", key)
        return self._send(status, ctype, data, "made" if key else "")

    def _ask_voicestudio(self, method, body):
        for attempt in range(6):
            req = urllib.request.Request(VOICESTUDIO + self.path, data=body, method=method)
            for h in ("Content-Type", "Authorization", "Accept"):
                if self.headers.get(h):
                    req.add_header(h, self.headers[h])
            try:
                with ONE_AT_A_TIME:
                    with urllib.request.urlopen(req, timeout=300) as res:
                        return res.read(), res.status, res.headers.get("Content-Type", "application/octet-stream")
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 5:          # VoiceStudio busy: wait and try again
                    time.sleep(2)
                    continue
                return e.read(), e.code, e.headers.get("Content-Type", "text/plain")
            except Exception as e:   # VoiceStudio is closed
                return ("VoiceStudio is not reachable on " + VOICESTUDIO + ": " + str(e)).encode(), 502, "text/plain"

    def _send(self, status, ctype, data, cache=""):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if cache:
            self.send_header("X-Voice-Cache", cache)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/v1/"):
            return self._voice("GET")
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/v1/"):
            return self._voice("POST")
        self.send_error(404)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print("AI World page: http://localhost:%d/Girl_Room.html   (voice goes to VoiceStudio on %s)" % (PORT, VOICESTUDIO))
    Server(("", PORT), Handler).serve_forever()
