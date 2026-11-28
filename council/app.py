"""
AI Council Chat - Imran's own chat app.
Talks to Claude (Claude Code, your Claude plan) and Gemini (Antigravity CLI, your Google AI plan).
Projects, saved chats, memory, and a LOCAL API (this laptop only).
Standard Python only - no extra packages needed.
"""
import atexit
import json
import queue
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import webbrowser
from datetime import datetime, date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# ---------------- Settings ----------------
HOST = "127.0.0.1"          # this laptop only - never 0.0.0.0
PORT = int(os.environ.get("AICHAT_PORT", "8765"))
MIN_GAP_SECONDS = 1          # wait between AI calls
DAILY_CALL_LIMIT = 300       # max AI calls per day (all modes)
HISTORY_TURNS = 12           # recent messages sent with each question
MAX_PROMPT_CHARS = 20000     # keep prompts a safe size
CALL_TIMEOUT = 300           # seconds before an AI call is stopped
SESSION_TURNS = 12           # start a fresh Claude / Gemini session after this many replies (keeps them quick)
# -------------------------------------------

HOME = os.path.expanduser("~")
DATA = os.environ.get("AICHAT_DATA") or os.path.join(HOME, "Documents", "ai-council", "app-data")
PROJECTS_DIR = os.path.join(DATA, "projects")
WORK_DIR = os.path.join(DATA, "work")   # empty folder so the tools have no files to touch
for d in (DATA, PROJECTS_DIR, WORK_DIR):
    os.makedirs(d, exist_ok=True)

KEY_FILE = os.path.join(DATA, "api_key.txt")
if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, "w", encoding="utf-8") as f:
        f.write("aic_" + secrets.token_hex(16))
with open(KEY_FILE, encoding="utf-8") as f:
    API_KEY = f.read().strip()

GLOBAL_MEMORY = os.path.join(DATA, "global_memory.md")
USAGE_FILE = os.path.join(DATA, "usage.json")
SETTINGS_FILE = os.path.join(DATA, "settings.json")
DEEPSEEK_BASE = "https://api.deepseek.com"   # DeepSeek official API (OpenAI-style)

# Free cloud AI (runs on their servers, not your PC). You paste your own free keys in Settings.
CLOUD = {
    "deepseek": {"name": "DeepSeek (free, OpenRouter)", "base": "https://openrouter.ai/api/v1",
                 "key": "openrouter_key", "models_setting": "openrouter_models",
                 "default_models": ["deepseek/deepseek-chat-v3:free", "deepseek/deepseek-r1-0528:free",
                                    "openrouter/free"]},
    "grok": {"name": "Grok (OpenRouter)", "base": "https://openrouter.ai/api/v1",
             "key": "openrouter_key", "models_setting": "grok_models",
             "default_models": ["x-ai/grok-4.1-fast:free", "x-ai/grok-4.1-fast"]},
}

RULES = ("You are a helpful assistant inside Imran's own chat app. Answer in plain, simple English. "
         "Do not use any tools, do not run commands, do not create or edit files. Only give the answer.")

_call_lock = threading.Lock()
_last_call = [0.0]
_file_lock = threading.Lock()


# ---------------- helpers ----------------
def safe_name(name):
    name = re.sub(r"[^A-Za-z0-9 _\-]", "", (name or "").strip())[:60].strip()
    return name or "General"


def project_dir(name):
    p = os.path.join(PROJECTS_DIR, safe_name(name))
    os.makedirs(p, exist_ok=True)
    return p


def read_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def write_text(path, text):
    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def load_history(project):
    path = os.path.join(project_dir(project), "history.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_history(project, history):
    path = os.path.join(project_dir(project), "history.json")
    with _file_lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=1)


def list_projects():
    names = [n for n in os.listdir(PROJECTS_DIR) if os.path.isdir(os.path.join(PROJECTS_DIR, n))]
    if "General" not in names:
        project_dir("General")
        names.append("General")
    return sorted(names, key=lambda n: (n != "General", n.lower()))


def usage_today():
    try:
        with open(USAGE_FILE, encoding="utf-8") as f:
            u = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        u = {}
    return u if u.get("date") == str(date.today()) else {"date": str(date.today()), "calls": 0}


def count_call():
    u = usage_today()
    u["calls"] += 1
    with _file_lock:
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(u, f)


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_settings(new):
    s = load_settings()
    for k, v in new.items():
        if k.endswith("_key") and (v is None or "..." in str(v)):
            continue   # masked value sent back unchanged
        if k.endswith("_models") and isinstance(v, str):
            v = [m.strip() for m in v.split(",") if m.strip()]
        s[k] = v
    with _file_lock:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1)


def mask(key):
    return (key[:6] + "..." + key[-4:]) if key and len(key) > 12 else ("set" if key else "")


def run_cloud(which, prompt):
    """Call a free cloud model (OpenAI-style API). Tries each model in order until one answers."""
    cfg = CLOUD[which]
    st = load_settings()
    errors = []
    if which == "deepseek" and st.get("deepseek_key"):   # DEEPSEEK_OFFICIAL_V1: your own DeepSeek key first (paid, cheap)
        try:
            return call_openai_style(DEEPSEEK_BASE, st["deepseek_key"], ["deepseek-flash"], prompt)
        except RuntimeError as e:
            errors.append("DeepSeek official: " + str(e))
    key = st.get(cfg["key"], "")
    if not key:
        raise RuntimeError(" | ".join(errors + [f"No key for {cfg['name']}. Open Settings in the app and paste your key."]))
    models = st.get(cfg["models_setting"]) or cfg["default_models"]
    try:
        return call_openai_style(cfg["base"], key, models, prompt)
    except RuntimeError as e:
        raise RuntimeError(f"{cfg['name']} failed. " + " | ".join(errors + [str(e)]))


def call_openai_style(base, key, models, prompt):
    """One OpenAI-style chat call; tries each model in order. Returns (text, model)."""
    errors = []
    for model in models:
        body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
        req = urllib.request.Request(base + "/chat/completions", data=body, method="POST", headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json",
            "HTTP-Referer": "http://127.0.0.1", "X-Title": "AI Council Chat"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode("utf-8"))
            text = (data["choices"][0]["message"].get("content") or "").strip()
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()   # hide reasoning notes
            if text:
                return text, model
            errors.append(f"{model}: empty answer")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            errors.append(f"{model}: HTTP {e.code} {detail}")
        except Exception as e:
            errors.append(f"{model}: {e}")
    raise RuntimeError(" | ".join(errors))


def find_tool(name):
    found = shutil.which(name)
    if found:
        return found
    candidates = [
        os.path.join(HOME, ".local", "bin", name + ".exe"),
        os.path.join(HOME, ".local", "bin", name),
        os.path.join(HOME, "AppData", "Local", "Programs", name, name + ".exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


# SPEED_V1 (Imran, 27 Nov: "make council fast as if I'm using API"). Claude Code normally sends a very big coding
# system prompt, all its tool definitions and MCP servers with EVERY message. A chat does not need any of that, so:
# a tiny system prompt, no tools, no MCP servers, no skills, nothing saved to disk. Fewer words to read = faster
# first word. Still your Claude PLAN (never an API key). If this Claude Code version rejects a flag, the app
# switches back to the normal way by itself.
LITE_SYSTEM = "You are a fast, helpful chat assistant. Answer directly. No tools."
CLAUDE_FAST_FLAGS = ["--system-prompt", LITE_SYSTEM, "--tools", "", "--strict-mcp-config",
                     "--disable-slash-commands", "--no-session-persistence"]
FAST_OK = {"claude": True, "agy": True}


AGY_AUTO_MODEL = {"slug": None}   # found once from 'agy models'


def find_flash_model():
    """SPEED_V1 (Gemini): pick the fastest everyday Gemini model on your plan from 'agy models' (a Flash model,
    not Lite, not an image model). Returns "" if none is found - then agy keeps its own choice."""
    if AGY_AUTO_MODEL["slug"] is not None:
        return AGY_AUTO_MODEL["slug"]
    slug = ""
    exe = find_tool("agy")
    if exe:
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            r = subprocess.run([exe, "models"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=60, creationflags=flags, cwd=WORK_DIR)
            names = re.findall(r"\b(gemini-[a-z0-9.\-]*flash[a-z0-9.\-]*)", r.stdout or "", re.I)
            plain = [n for n in names if "lite" not in n.lower() and "image" not in n.lower()]
            slug = (plain or [n for n in names if "image" not in n.lower()] or [""])[0]
        except Exception:
            slug = ""
    AGY_AUTO_MODEL["slug"] = slug
    print(" Gemini fast model:", slug or "(agy default)")
    return slug


def agy_model_flags():
    """SPEED_V1 (Gemini): low thinking effort, no slash/skill expansion, and the Flash model.
    Settings key agy_model (or AICHAT_AGY_MODEL) picks the model yourself; otherwise it is found from 'agy models'."""
    if not FAST_OK["agy"]:
        return []
    m = (load_settings().get("agy_model") or os.environ.get("AICHAT_AGY_MODEL") or "").strip() or find_flash_model()
    return ["--effort", "low", "--disable-slash-commands"] + (["--model", m] if m else [])


class ToolSession:
    """WARM_SESSIONS_V1: keeps Claude Code / Antigravity OPEN between replies (no start-up wait each time)
    and streams the answer as it is written. One reply at a time per tool."""

    def __init__(self, tool):
        self.tool, self.proc, self.lines, self.turns = tool, None, None, 0
        self.lock = threading.Lock()
        self.err_tail = []

    def _start(self):
        exe = find_tool(self.tool)
        if not exe:
            raise RuntimeError(f"'{self.tool}' is not installed or not found. Run AI Council Setup first.")
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)   # always use the Claude PLAN, never an API key
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        if self.tool == "claude":
            args = [exe, "-p", "--input-format", "stream-json", "--output-format", "stream-json",
                    "--verbose", "--include-partial-messages"] + (CLAUDE_FAST_FLAGS if FAST_OK["claude"] else [])
        else:  # agy
            args = [exe, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--mode", "plan"] + agy_model_flags()
        self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding="utf-8", errors="replace", bufsize=1,
                                     cwd=WORK_DIR, env=env, creationflags=flags)
        self.lines, self.turns, self.err_tail = queue.Queue(), 0, []
        threading.Thread(target=self._pump, args=(self.proc.stdout, self.lines), daemon=True).start()
        threading.Thread(target=self._pump_err, args=(self.proc.stderr,), daemon=True).start()

    @staticmethod
    def _pump(stream, q):
        try:
            for line in stream:
                q.put(line)
        finally:
            q.put(None)              # the program closed

    def _pump_err(self, stream):
        for line in stream:
            self.err_tail = (self.err_tail + [line.rstrip()])[-15:]

    def stop(self):
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            try:
                p.stdin.close()
                p.wait(timeout=3)
            except Exception:
                p.kill()

    def ask(self, prompt):
        """Yields the answer in pieces as it is written."""
        with self.lock:
            if self.proc is None or self.proc.poll() is not None or self.turns >= SESSION_TURNS:
                self.stop()
                self._start()
            if self.tool == "claude":
                msg = {"type": "user", "message": {"role": "user", "content": prompt}}
            else:
                msg = {"event": "user", "message": {"content": prompt}}
            try:
                self.proc.stdin.write(json.dumps(msg) + "\n")
                self.proc.stdin.flush()
            except OSError:
                self.stop()
                raise RuntimeError(f"{self.tool} closed: " + " | ".join(self.err_tail[-3:]))
            self.turns += 1
            finished, said, deadline = False, [], time.time() + CALL_TIMEOUT
            try:
                while True:
                    left = deadline - time.time()
                    if left <= 0:
                        raise RuntimeError(f"{self.tool} took longer than {CALL_TIMEOUT} s")
                    try:
                        line = self.lines.get(timeout=left)
                    except queue.Empty:
                        continue
                    if line is None:
                        if not said and FAST_OK[self.tool] and self.turns == 1 and re.search(
                                r"unknown (option|flag|argument)|unrecognized|invalid (option|flag)", " ".join(self.err_tail), re.I):
                            FAST_OK[self.tool] = False
                            print(f"{self.tool}: speed flags not accepted - using the normal way from now on")
                        raise RuntimeError(f"{self.tool} stopped: " + (" | ".join(self.err_tail[-3:]) or "no details"))
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    if self.tool == "claude":
                        if d.get("type") == "stream_event":
                            ev = d.get("event") or {}
                            delta = ev.get("delta") or {}
                            if ev.get("type") == "content_block_delta" and delta.get("type") == "text_delta" and delta.get("text"):
                                said.append(delta["text"])
                                yield delta["text"]
                        elif d.get("type") == "result":
                            if d.get("is_error"):
                                raise RuntimeError("claude failed: " + str(d.get("result") or d.get("subtype")))
                            if not said and d.get("result"):
                                yield d["result"]
                            finished = True
                            return
                    else:
                        if d.get("event") == "step_update":
                            su = d.get("step_update") or {}
                            if su.get("step_type") == "agent_response" and su.get("text_delta"):
                                said.append(su["text_delta"])
                                yield su["text_delta"]
                        elif d.get("event") == "result":
                            r = d.get("result") or {}
                            if r.get("status") not in (None, "SUCCESS"):
                                raise RuntimeError("gemini failed: " + str(r.get("status")))
                            if not said and r.get("response"):
                                yield r["response"]
                            finished = True
                            return
            finally:
                if not finished:     # stopped half way: this session has leftover output, start fresh next time
                    self.stop()


SESSIONS = {"claude": ToolSession("claude"), "agy": ToolSession("agy")}
atexit.register(lambda: [s.stop() for s in SESSIONS.values()])


def run_tool_stream(tool, prompt):
    """Streams one answer from your plan (Claude Code / Antigravity). Daily cap and a short gap between calls."""
    with _call_lock:
        if usage_today()["calls"] >= DAILY_CALL_LIMIT:
            raise RuntimeError(f"Daily limit of {DAILY_CALL_LIMIT} AI calls reached. Try again tomorrow.")
        wait = MIN_GAP_SECONDS - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        count_call()
    said = False
    try:
        for piece in SESSIONS[tool].ask(prompt):
            said = True
            yield piece
    except Exception as error:
        if said:
            raise
        print(f"{tool} warm session failed ({error}) - using the one-shot way for this reply")
        yield run_tool_once(tool, prompt)


def run_tool_once(tool, prompt, model=None):
    """The old way (start, answer, close). Backup if the warm session does not work on this PC.
    model: CLAUDE_CHEAP_V1 - e.g. "haiku", Claude's cheapest model on the same Claude plan."""
    exe = find_tool(tool)
    if not exe:
        raise RuntimeError(f"'{tool}' is not installed or not found. Run AI Council Setup first.")
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    if tool == "claude":
        args, stdin = [exe, "-p", "--output-format", "text"] + (["--model", model] if model else []), prompt
        fast = CLAUDE_FAST_FLAGS if FAST_OK["claude"] else []
    else:
        args, stdin = [exe, "-p", prompt, "--mode", "plan", "--output-format", "text"], None
        fast = agy_model_flags()
    r = subprocess.run(args + fast, input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=WORK_DIR, env=env, timeout=CALL_TIMEOUT, creationflags=flags)
    bad_flag = re.search(r"unknown (option|flag|argument)|unrecognized|invalid (option|flag)", (r.stderr or "") + (r.stdout or ""), re.I)
    if r.returncode != 0 and fast and bad_flag:   # SPEED_V1: this version rejected a speed flag - normal way, and remember it
        FAST_OK[tool] = False
        r = subprocess.run(args, input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd=WORK_DIR, env=env, timeout=CALL_TIMEOUT, creationflags=flags)
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"{tool} failed: " + (r.stderr or out or "no details").strip()[-800:])
    return out or "(empty answer)"


def run_tool(tool, prompt):
    return "".join(run_tool_stream(tool, prompt)).strip() or "(empty answer)"


def build_prompt(project, message):
    parts = [RULES]
    g = read_text(GLOBAL_MEMORY).strip()
    if g:
        parts.append("THINGS TO REMEMBER (all projects):\n" + g)
    pm = read_text(os.path.join(project_dir(project), "memory.md")).strip()
    if pm:
        parts.append(f"THINGS TO REMEMBER (project '{safe_name(project)}'):\n" + pm)
    hist = load_history(project)[-HISTORY_TURNS:]
    if hist:
        lines = []
        for h in hist:
            who = "Imran" if h["role"] == "user" else h.get("model", "AI")
            lines.append(f"{who}: {h['text']}")
        parts.append("RECENT CHAT:\n" + "\n".join(lines))
    parts.append("NEW MESSAGE FROM IMRAN:\n" + message)
    prompt = "\n\n".join(parts)
    if len(prompt) > MAX_PROMPT_CHARS:   # trim oldest chat first
        prompt = RULES + "\n\n...(older chat trimmed)...\n\n" + prompt[-(MAX_PROMPT_CHARS - 200):]
    return prompt


def add_memory(project, text, scope):
    path = GLOBAL_MEMORY if scope == "global" else os.path.join(project_dir(project), "memory.md")
    old = read_text(path).rstrip()
    write_text(path, (old + "\n" if old else "") + "- " + text.strip() + "\n")


def chat_stream(project, mode, message):
    """Like chat(), but yields the answer in pieces. Modes: gemini, claude, deepseek, grok."""
    message = (message or "").strip()
    if not message:
        raise ValueError("Empty message.")
    if mode not in ("gemini", "claude") or re.match(r"^(remember|remember all)\s*:", message, re.I):
        for r in chat(project, mode, message):     # no stream for these: one piece
            yield r["text"]
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    prompt = build_prompt(project, message)
    parts = []
    for piece in run_tool_stream("claude" if mode == "claude" else "agy", prompt):
        parts.append(piece)
        yield piece
    history = load_history(project)
    history.append({"role": "user", "text": message, "time": now, "mode": mode})
    history.append({"role": "ai", "model": "Claude" if mode == "claude" else "Gemini", "text": "".join(parts).strip(), "time": now})
    save_history(project, history)


def chat(project, mode, message):
    message = (message or "").strip()
    if not message:
        raise ValueError("Empty message.")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    history = load_history(project)
    replies = []

    # "remember: ..." saves to memory without calling any AI
    m = re.match(r"^(remember|remember all)\s*:\s*(.+)$", message, re.I | re.S)
    if m:
        scope = "global" if m.group(1).lower() == "remember all" else "project"
        add_memory(project, m.group(2), scope)
        where = "all projects" if scope == "global" else f"project '{safe_name(project)}'"
        replies.append({"role": "ai", "model": "Memory", "text": f"Saved to memory for {where}.", "time": now})
        history.append({"role": "user", "text": message, "time": now})
        history.extend(replies)
        save_history(project, history)
        return replies

    if mode == "claude_cheap":   # CLAUDE_CHEAP_V1: Claude Haiku, plain one-shot job (TV drawings), no memory or history
        return [{"role": "ai", "model": "Claude Haiku", "text": run_tool_once("claude", message, model="haiku"), "time": now}]
    prompt = build_prompt(project, message)
    if mode == "claude":
        replies.append({"role": "ai", "model": "Claude", "text": run_tool("claude", prompt), "time": now})
    elif mode == "gemini":
        replies.append({"role": "ai", "model": "Gemini", "text": run_tool("agy", prompt), "time": now})
    elif mode in CLOUD:
        text, model = run_cloud(mode, prompt)
        label = "DeepSeek (your key)" if model == "deepseek-flash" else CLOUD[mode]['name']
        replies.append({"role": "ai", "model": f"{label} - {model}", "text": text, "time": now})
    elif mode == "both":
        replies.append({"role": "ai", "model": "Gemini", "text": run_tool("agy", prompt), "time": now})
        replies.append({"role": "ai", "model": "Claude", "text": run_tool("claude", prompt), "time": now})
    else:  # council: Gemini answers, Claude checks, Gemini fixes once
        answer = run_tool("agy", prompt)
        check = run_tool("claude", RULES + "\n\nYou are a strict checker. Check the ANSWER against the "
                         "REQUEST. Look for wrong facts, wrong math, missing items, unclear parts. Your FIRST "
                         "line must be exactly APPROVED or NEEDS FIX. If NEEDS FIX, list each mistake and how "
                         f"to fix it.\n\nREQUEST:\n{message}\n\nANSWER:\n{answer}")
        status = "APPROVED"
        if not check.strip().upper().startswith("APPROVED"):
            answer = run_tool("agy", prompt + "\n\nYOUR LAST ANSWER:\n" + answer +
                              "\n\nA CHECKER FOUND THESE MISTAKES:\n" + check +
                              "\n\nWrite the full corrected answer.")
            status = "FIXED after checker notes"
        replies.append({"role": "ai", "model": f"Council ({status})", "text": answer,
                        "check": check, "time": now})

    history.append({"role": "user", "text": message, "time": now, "mode": mode})
    history.extend(replies)
    save_history(project, history)
    return replies


# ---------------- web server ----------------
class Handler(BaseHTTPRequestHandler):
    server_version = "AICouncilChat/1.0"

    def log_message(self, fmt, *args):
        sys.stdout.write("%s  %s\n" % (datetime.now().strftime("%H:%M:%S"), fmt % args))

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _cors(self):
        # Let your own local web apps (like Ai_World) call this API from the browser
        origin = self.headers.get("Origin", "")
        if origin == "null" or re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$", origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _authed(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            return False
        return secrets.compare_digest(self.headers.get("X-API-Key", ""), API_KEY)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 2_000_000:
            raise ValueError("Request too big.")
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, PAGE.replace("__API_KEY__", API_KEY).replace("__PORT__", str(PORT))
                              .encode("utf-8"), "text/html")
        if not self._authed():
            return self._send(401, {"error": "Missing or wrong X-API-Key"})
        q = parse_qs(u.query)
        project = q.get("project", ["General"])[0]
        if u.path == "/api/projects":
            return self._send(200, {"projects": list_projects()})
        if u.path == "/api/history":
            return self._send(200, {"project": safe_name(project), "history": load_history(project)})
        if u.path == "/api/memory":
            return self._send(200, {"global": read_text(GLOBAL_MEMORY),
                                    "project": read_text(os.path.join(project_dir(project), "memory.md"))})
        if u.path == "/api/settings":
            st = load_settings()
            return self._send(200, {
                "openrouter_key": mask(st.get("openrouter_key", "")),
                "deepseek_key": mask(st.get("deepseek_key", "")),
                "openrouter_models": ", ".join(st.get("openrouter_models") or CLOUD["deepseek"]["default_models"]),
                "grok_models": ", ".join(st.get("grok_models") or CLOUD["grok"]["default_models"])})
        if u.path == "/api/status":
            return self._send(200, {"claude": bool(find_tool("claude")), "gemini": bool(find_tool("agy")),
                                    "calls_today": usage_today()["calls"], "daily_limit": DAILY_CALL_LIMIT})
        return self._send(404, {"error": "Not found"})

    def do_POST(self):
        u = urlparse(self.path)
        if not self._authed():
            return self._send(401, {"error": "Missing or wrong X-API-Key"})
        try:
            b = self._body()
            if u.path == "/api/projects":
                name = safe_name(b.get("name"))
                project_dir(name)
                return self._send(200, {"project": name, "projects": list_projects()})
            if u.path == "/api/memory":
                project = b.get("project", "General")
                if "global" in b:
                    write_text(GLOBAL_MEMORY, b["global"])
                if "project_memory" in b:
                    write_text(os.path.join(project_dir(project), "memory.md"), b["project_memory"])
                return self._send(200, {"ok": True})
            if u.path == "/api/settings":
                save_settings(b)
                return self._send(200, {"ok": True})
            if u.path == "/api/chat_stream":
                # one JSON line per piece: {"delta": "..."}, then {"done": true}
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self._cors()
                self.end_headers()
                try:
                    for piece in chat_stream(b.get("project", "General"), b.get("mode", "gemini"), b.get("message", "")):
                        self.wfile.write((json.dumps({"delta": piece}, ensure_ascii=False) + "\n").encode("utf-8"))
                        self.wfile.flush()
                    self.wfile.write(b'{"done": true}\n')
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as e:
                    try:
                        self.wfile.write((json.dumps({"error": str(e)}) + "\n").encode("utf-8"))
                    except OSError:
                        pass
                return
            if u.path == "/api/chat":
                mode = b.get("mode", "council")
                if mode not in ("claude", "claude_cheap", "gemini", "both", "council") and mode not in CLOUD:
                    mode = "council"
                replies = chat(b.get("project", "General"), mode, b.get("message", ""))
                return self._send(200, {"replies": replies})
            return self._send(404, {"error": "Not found"})
        except Exception as e:  # show the reason in the app instead of crashing
            return self._send(500, {"error": str(e)})


PAGE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AI Council Chat</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#0f1115;color:#e7e9ee;display:flex;height:100vh}
#side{width:250px;background:#171a21;padding:14px;display:flex;flex-direction:column;gap:10px;border-right:1px solid #262b36}
#side h1{font-size:17px;margin:0 0 6px}#projects{flex:1;overflow:auto}
.proj{padding:8px 10px;border-radius:8px;cursor:pointer;margin-bottom:4px}.proj:hover{background:#222733}.proj.on{background:#2c3a5c}
button{background:#3b5bdb;color:#fff;border:0;border-radius:8px;padding:8px 12px;cursor:pointer;font-size:14px}
button.ghost{background:#262b36}button:disabled{opacity:.5;cursor:wait}
#main{flex:1;display:flex;flex-direction:column;min-width:0}
#top{padding:10px 16px;border-bottom:1px solid #262b36;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
#top b{font-size:16px}select,input,textarea{background:#1d212b;color:#e7e9ee;border:1px solid #333a48;border-radius:8px;padding:8px;font-size:14px;font-family:inherit}
#msgs{flex:1;overflow:auto;padding:18px}
.m{max-width:820px;margin:0 0 14px;padding:10px 14px;border-radius:12px;white-space:pre-wrap;line-height:1.45}
.u{background:#2c3a5c;margin-left:auto}.a{background:#1d212b;border:1px solid #2a3040}
.who{font-size:12px;opacity:.7;margin-bottom:4px}details{margin-top:8px;font-size:13px;opacity:.85}
#bar{display:flex;gap:10px;padding:12px 16px;border-top:1px solid #262b36}#bar textarea{flex:1;height:70px;resize:vertical}
#panel{display:none;padding:16px;overflow:auto;flex:1}#panel textarea{width:100%;height:160px}
code{background:#1d212b;padding:2px 6px;border-radius:6px}pre{background:#1d212b;padding:10px;border-radius:8px;white-space:pre-wrap}
.small{font-size:12px;opacity:.7}
</style></head><body>
<div id="side"><h1>AI Council Chat</h1>
<div style="display:flex;gap:6px"><input id="newp" placeholder="New project" style="flex:1;min-width:0"><button onclick="newProject()">+</button></div>
<div id="projects"></div>
<button class="ghost" onclick="show('chat')">Chat</button>
<button class="ghost" onclick="show('memory')">Memory</button>
<button class="ghost" onclick="show('api')">API</button>
<button class="ghost" onclick="show('settings')">Settings</button>
<div class="small" id="stat"></div></div>
<div id="main">
<div id="top"><b id="ptitle">General</b>
<label>Talk to: <select id="mode">
<option value="council">Council (Gemini answers, Claude checks)</option>
<option value="both">Both (two answers)</option>
<option value="claude">Claude only</option>
<option value="claude_cheap">Claude Haiku (cheapest)</option>
<option value="gemini">Gemini only</option>
<option value="deepseek">DeepSeek</option>
<option value="grok">Grok (OpenRouter)</option></select></label>
<span class="small">Tip: start a message with <code>remember:</code> to save it for this project, or <code>remember all:</code> for every project.</span></div>
<div id="msgs"></div>
<div id="panel"></div>
<div id="bar"><textarea id="txt" placeholder="Type a message. Enter = send, Shift+Enter = new line"></textarea><button id="send" onclick="send()">Send</button></div>
</div>
<script>
const KEY="__API_KEY__";let project="General";
const H={"Content-Type":"application/json","X-API-Key":KEY};
async function api(path,body){const r=await fetch(path,body?{method:"POST",headers:H,body:JSON.stringify(body)}:{headers:H});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);return j}
function esc(s){return (s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]))}
async function loadProjects(){const j=await api("/api/projects");const box=document.getElementById("projects");box.innerHTML="";
j.projects.forEach(p=>{const d=document.createElement("div");d.className="proj"+(p===project?" on":"");d.textContent=p;d.onclick=()=>openProject(p);box.appendChild(d)})}
async function newProject(){const n=document.getElementById("newp").value.trim();if(!n)return;const j=await api("/api/projects",{name:n});document.getElementById("newp").value="";openProject(j.project)}
async function openProject(p){project=p;document.getElementById("ptitle").textContent=p;await loadProjects();show("chat");const j=await api("/api/history?project="+encodeURIComponent(p));const box=document.getElementById("msgs");box.innerHTML="";j.history.forEach(add);status()}
function add(h){const box=document.getElementById("msgs");const d=document.createElement("div");d.className="m "+(h.role==="user"?"u":"a");
d.innerHTML='<div class="who">'+(h.role==="user"?"You":esc(h.model))+(h.time?" · "+esc(h.time):"")+'</div>'+esc(h.text)+(h.check?'<details><summary>Checker notes</summary>'+esc(h.check)+'</details>':"");box.appendChild(d);box.scrollTop=box.scrollHeight;return d}
async function send(){const t=document.getElementById("txt");const msg=t.value.trim();if(!msg)return;const b=document.getElementById("send");b.disabled=true;t.value="";
add({role:"user",text:msg});const wait=add({role:"ai",model:"Thinking",text:"Working on it... (Council and Both take a little longer)"});
try{const j=await api("/api/chat",{project,mode:document.getElementById("mode").value,message:msg});wait.remove();j.replies.forEach(add)}
catch(e){wait.remove();add({role:"ai",model:"Error",text:e.message})}b.disabled=false;t.focus();status()}
document.getElementById("txt").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}});
async function show(v){const p=document.getElementById("panel"),m=document.getElementById("msgs"),bar=document.getElementById("bar");
if(v==="chat"){p.style.display="none";m.style.display="block";bar.style.display="flex";return}
m.style.display="none";bar.style.display="none";p.style.display="block";
if(v==="memory"){const j=await api("/api/memory?project="+encodeURIComponent(project));
p.innerHTML='<h3>Memory for all projects</h3><textarea id="gm">'+esc(j.global)+'</textarea><h3>Memory for project: '+esc(project)+'</h3><textarea id="pm">'+esc(j.project)+'</textarea><p><button onclick="saveMem()">Save memory</button> <span id="ms" class="small"></span></p><p class="small">Everything here is sent with every message so the AIs remember it. Keep passwords and card numbers out.</p>'}
if(v==="settings"){const s=await api("/api/settings");
p.innerHTML='<h3>OpenRouter key</h3><p>One key for DeepSeek and Grok (and the Ai_World fast brain). Runs on their computers, not your PC.</p>'+
'<p><b>OpenRouter key</b> - get it at openrouter.ai/keys<br><input id="ork" style="width:100%" placeholder="sk-or-..." value="'+esc(s.openrouter_key)+'"></p>'+
'<h3>DeepSeek key (official, optional)</h3><p>From platform.deepseek.com. Paid but cheap: DeepSeek uses it first, then the free OpenRouter models. It only works after you top up.</p>'+
'<input id="dsk" style="width:100%" placeholder="sk-..." value="'+esc(s.deepseek_key)+'">'+
'<p class="small">DeepSeek models tried in order (free ones change over time):</p><input id="orm" style="width:100%" value="'+esc(s.openrouter_models)+'">'+
'<p class="small">Grok models tried in order:</p><input id="gm2" style="width:100%" value="'+esc(s.grok_models)+'">'+
'<p><button onclick="saveSettings()">Save</button> <span id="ss" class="small"></span></p>'+
'<p class="small">Free limits: OpenRouter free models about 50 messages a day. Free services may use what you send to improve their AI, so keep customer data, passwords and card numbers out.</p>'}
if(v==="api"){p.innerHTML='<h3>Your local API</h3><p>Works only for programs on <b>this laptop</b>. Do not share it with other people or computers: that would break your Claude and Google subscription rules.</p>'+
'<p>Address: <code>http://127.0.0.1:__PORT__/api/chat</code></p><p>Key (header <code>X-API-Key</code>): <code>'+KEY+'</code></p>'+
'<pre>POST /api/chat\nHeaders: X-API-Key: '+KEY+'\nBody (JSON): {"project": "General", "mode": "council", "message": "your question"}\nmode = council | both | claude | gemini\n\nOther: GET /api/projects, GET /api/history?project=NAME, GET /api/memory?project=NAME, GET /api/status</pre>'+
'<p>PowerShell test:</p><pre>Invoke-RestMethod -Uri http://127.0.0.1:__PORT__/api/chat -Method Post -Headers @{"X-API-Key"="'+KEY+'"} -ContentType "application/json" -Body \'{"mode":"claude","message":"hello"}\'</pre>'}}
async function saveSettings(){const v=id=>document.getElementById(id).value;await api("/api/settings",{openrouter_key:v("ork"),deepseek_key:v("dsk"),openrouter_models:v("orm"),grok_models:v("gm2")});document.getElementById("ss").textContent="Saved.";show("settings")}
async function saveMem(){await api("/api/memory",{project,global:document.getElementById("gm").value,project_memory:document.getElementById("pm").value});document.getElementById("ms").textContent="Saved."}
async function status(){try{const s=await api("/api/status");document.getElementById("stat").textContent="Claude: "+(s.claude?"ready":"missing")+" · Gemini: "+(s.gemini?"ready":"missing")+" · Calls today: "+s.calls_today+"/"+s.daily_limit}catch(e){}}
openProject("General");
</script></body></html>"""


def main():
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print(f"AI Council Chat is already running. Opening http://{HOST}:{PORT}")
        webbrowser.open(f"http://{HOST}:{PORT}")
        time.sleep(3)
        return
    url = f"http://{HOST}:{PORT}"
    print("=" * 60)
    print(" AI Council Chat is running at", url)
    print(" Data folder:", DATA)
    print(" Keep this window open. Close it to stop the app.")
    print("=" * 60)
    # SPEED_V1: open Claude and Gemini now, in the background, so the FIRST question does not wait for them to start
    def prewarm():
        if find_tool("agy"):
            find_flash_model()
        for name, sess in SESSIONS.items():
            if find_tool(name):
                try:
                    with sess.lock:
                        if sess.proc is None:
                            sess._start()
                    print(f" {name} is open and waiting")
                except Exception as e:
                    print(f" {name} could not be opened early: {e}")
    threading.Thread(target=prewarm, daemon=True).start()
    if not os.environ.get("AICHAT_NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
