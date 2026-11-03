"""AI World: one small server for the page AND the brain.

run_girl_room.bat starts this. It does two jobs on http://localhost:8081 :
  1. serves the room files (Girl_Room.html, the model, moves.json ...), like "python -m http.server" did
  2. POST /brain   {"text": "..."}  ->  asks Brain.py  ->  {"response", "emotion", "animation"}
     GET  /brain/health             ->  is the brain there, which AI, is it reachable

Same port for both, so the browser never blocks the page from talking to the brain.

Pick the AI:  python brain_server.py ollama   (default, free, needs Ollama running with qwen3:4b)
              python brain_server.py claude   (needs the ANTHROPIC_API_KEY setting in Windows)
"""

import json
import os
import sys
import threading
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import Brain  # noqa: E402  (the partner's brain file, used as it is)

PORT = int(os.getenv("AIWORLD_PORT", "8081"))
PROVIDER = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("BRAIN_PROVIDER", "ollama")).lower()
if PROVIDER not in ("ollama", "claude"):
    PROVIDER = "ollama"

LOCK = threading.Lock()   # Brain.py keeps one shared chat history, so one question at a time


def brain_problem():
    """Empty string when the chosen AI looks reachable, else a short reason."""
    if PROVIDER == "claude":
        return "" if os.getenv("ANTHROPIC_API_KEY") else "ANTHROPIC_API_KEY is not set"
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            names = [m.get("name", "") for m in json.loads(r.read().decode("utf-8")).get("models", [])]
        if not any(n == Brain.OLLAMA_MODEL or n.startswith(Brain.OLLAMA_MODEL + "-") for n in names):
            return "Ollama is running but the model " + Brain.OLLAMA_MODEL + " is missing (run: ollama pull " + Brain.OLLAMA_MODEL + ")"
        return ""
    except Exception:
        return "Ollama is not running (start the Ollama app)"


def offline_reply(problem):
    # learn:false so the page never saves this as a quick reply
    return {"response": "My brain is offline right now. " + problem + ".", "emotion": "confused",
            "animation": "shrug", "error": problem, "learn": False}


from page_server import Handler as _VoiceHandler   # passes /v1/audio/... to VoiceStudio (port 3900)


class Handler(SimpleHTTPRequestHandler):
    _voice = _VoiceHandler._voice

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def send_json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/v1/"):
            return self._voice("GET")
        if self.path.split("?")[0].rstrip("/") == "/brain/health":
            problem = brain_problem()
            model = Brain.CLAUDE_MODEL if PROVIDER == "claude" else Brain.OLLAMA_MODEL
            return self.send_json(200, {"brain": True, "provider": PROVIDER, "model": model,
                                        "ready": not problem, "problem": problem})
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/v1/"):
            return self._voice("POST")
        if self.path.split("?")[0].rstrip("/") != "/brain":
            return self.send_json(404, {"error": "unknown address"})
        try:
            size = int(self.headers.get("Content-Length") or 0)
            text = str(json.loads(self.rfile.read(size).decode("utf-8") or "{}").get("text", "")).strip()
        except Exception:
            return self.send_json(400, {"error": "send JSON like {\"text\": \"hi\"}"})
        if not text:
            return self.send_json(400, {"error": "empty text"})
        if text.lower().strip(" .!?") in ("new chat", "forget our chat"):   # ("reset" alone is the room's clean-up quick reply)
            Brain.history.clear()
            return self.send_json(200, {"response": "Okay. Fresh start.", "emotion": "neutral", "animation": "idle", "learn": False})
        problem = brain_problem()
        if problem:
            print("brain offline:", problem)
            return self.send_json(200, offline_reply(problem))
        with LOCK:
            reply = Brain.ask_brain(text, PROVIDER)
        if reply is None:
            return self.send_json(200, offline_reply("The AI did not give a usable answer, try again"))
        print("You:", text, "| Her:", reply["response"], "|", reply["emotion"], "/", reply["animation"])
        return self.send_json(200, reply)

    def log_message(self, fmt, *args):   # keep the window readable: only show brain calls and errors
        if "/brain" in (args[0] if args else "") or (len(args) > 1 and str(args[1])[:1] in "45"):
            super().log_message(fmt, *args)


def main():
    problem = brain_problem()
    print("==============================================")
    print(" AI WORLD  -  room + brain on http://localhost:%d/Girl_Room.html" % PORT)
    print(" Brain: %s  -  %s" % (PROVIDER, "ready" if not problem else "NOT READY: " + problem))
    print(" Close this window to stop.")
    print("==============================================")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
