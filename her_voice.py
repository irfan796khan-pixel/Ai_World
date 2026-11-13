"""Her HD voice: OmniVoice (k2-fsa, Apache-2.0), the voice engine inside VoiceStudio, WITHOUT the VoiceStudio app.

Why: the VoiceStudio app keeps crashing. Her voice only needs its engine, so this small server runs just that.
  - One voice only, hers: made once from the same settings as her VoiceStudio profile
    ("female, young adult, low pitch, american accent", seed 42), saved as her_voice/ref.wav,
    then every line is cloned from that clip, so she sounds the same every time.
  - Want a different clip as her voice? Put any 5-15 s recording at her_voice/ref.wav (and its words in
    her_voice/ref.txt, or leave that file empty and OmniVoice writes it down by itself), then restart.
  - Laughs and sighs: the brain may write [laughter] or [sigh] in a line and she does it.
  - Same address style as VoiceStudio: POST /v1/audio/speech {"input": "..."} -> WAV (24 kHz).
    page_server.py sends lines here when the voice menu says "Her HD voice".
  - Every line made once is kept in voice_cache/ (omni-*.wav) and plays at once next time.

Setup once: double-click setup_her_voice.bat (makes voice_env/, installs PyTorch for NVIDIA + OmniVoice).
Run:        voice_env\\Scripts\\python her_voice.py            (run_girl_room.bat starts it by itself)
Test:       voice_env\\Scripts\\python her_voice.py --test "Hi, I live in AI World."   -> her_voice/test.wav
New voice:  voice_env\\Scripts\\python her_voice.py --make-ref  (makes ref.wav again from the settings below)
Use a clip: voice_env\\Scripts\\python her_voice.py --ref C:\\path\\clip.wav --ref-text "words in the clip"
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "her_voice")
REF_WAV = os.path.join(DIR, "ref.wav")
REF_TXT = os.path.join(DIR, "ref.txt")
PROMPT = os.path.join(DIR, "prompt.pt")
CACHE = os.path.join(HERE, "voice_cache")
PORT = 3901
RATE = 24000

DESIGN = os.getenv("HER_VOICE_DESIGN", "female, young adult, low pitch, american accent")   # same as her VoiceStudio profile
SEED = int(os.getenv("HER_VOICE_SEED", "42"))
REF_LINE = ("Oh, you finally showed up. Sit down, get comfortable, and try not to embarrass yourself "
            "too much today. I have a whole room to run.")
NUM_STEP = int(os.getenv("HER_VOICE_STEPS", "16"))     # OmniVoice: 32 = default quality, 16 = faster
SPEED = float(os.getenv("HER_VOICE_SPEED", "1.0"))     # above 1.0 faster, below 1.0 slower
TAGS = ["laughter", "sigh", "confirmation-en", "question-en", "question-ah", "question-oh", "question-ei",
        "question-yi", "surprise-ah", "surprise-oh", "surprise-wa", "surprise-yo", "dissatisfaction-hnn"]

STATE = {"model": None, "prompt": None, "device": None, "error": None, "ready": False}
LOCK = threading.Lock()                                # one line at a time on the GPU


def log(*a):
    print("her voice:", *a, flush=True)


def load_model():
    import torch
    from omnivoice import OmniVoice
    cuda = torch.cuda.is_available()
    STATE["device"] = "cuda:0" if cuda else "cpu"
    log("loading OmniVoice on", STATE["device"], "(first time it downloads the model, please wait)")
    STATE["model"] = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=STATE["device"],
                                               dtype=torch.float16 if cuda else torch.float32)
    if not cuda:
        log("no NVIDIA GPU found: her voice works but is slow on the CPU")


def seed_all(seed):
    import random
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def wav_bytes(samples):
    import numpy as np
    a = np.asarray(samples, dtype="float32").reshape(-1)
    a = (np.clip(a, -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(a.tobytes())
    return buf.getvalue()


def make_ref(force=False):
    """Her voice clip: made once from the design settings (same as the VoiceStudio profile), then reused."""
    if os.path.exists(REF_WAV) and not force:
        return
    os.makedirs(DIR, exist_ok=True)
    log("making her voice clip from:", DESIGN, "seed", SEED)
    seed_all(SEED)
    audio = STATE["model"].generate(text=REF_LINE, instruct=DESIGN, num_step=32)
    with open(REF_WAV, "wb") as f:
        f.write(wav_bytes(audio[0]))
    with open(REF_TXT, "w", encoding="utf-8") as f:
        f.write(REF_LINE)
    if os.path.exists(PROMPT):
        os.remove(PROMPT)
    log("saved", REF_WAV)


def use_clip(path, text=None):
    """Make any recording her voice clip."""
    os.makedirs(DIR, exist_ok=True)
    if path.lower().endswith(".wav"):
        shutil.copyfile(path, REF_WAV)
    else:
        import soundfile as sf
        data, sr = sf.read(path, dtype="float32")
        sf.write(REF_WAV, data, sr)
    with open(REF_TXT, "w", encoding="utf-8") as f:
        f.write((text or "").strip())
    if os.path.exists(PROMPT):
        os.remove(PROMPT)
    log("her voice clip is now", path)


def ref_text():
    try:
        with open(REF_TXT, encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


def load_prompt():
    """Reads her clip once (OmniVoice voice_clone_prompt), so each line skips that step. Falls back to the clip."""
    model = STATE["model"]
    if not hasattr(model, "create_voice_clone_prompt"):
        return None
    try:
        from omnivoice import VoiceClonePrompt
        if os.path.exists(PROMPT) and os.path.getmtime(PROMPT) >= os.path.getmtime(REF_WAV):
            return VoiceClonePrompt.load(PROMPT)
    except Exception:
        pass
    try:
        kw = {"ref_audio": REF_WAV}
        if ref_text():
            kw["ref_text"] = ref_text()
        prompt = model.create_voice_clone_prompt(**kw)
        try:
            prompt.save(PROMPT)
        except Exception:
            pass
        return prompt
    except Exception as error:
        log("voice prompt not used (", error, "): the clip is read for each line instead")
        return None


def clean(text):
    """Only words she says: no stage directions or emojis; [laughter] / [sigh] tags stay."""
    t = str(text or "")
    keep = {}
    for i, tag in enumerate(TAGS):
        mark = "\u0001%d\u0001" % i
        if "[" + tag + "]" in t:
            keep[mark] = "[" + tag + "]"
            t = t.replace("[" + tag + "]", mark)
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]|\*[^*\n]*\*|<[^>]*>", " ", t)
    t = re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF]", " ", t)
    t = t.replace("...", ", ").replace("\u2026", ", ")
    for mark, tag in keep.items():
        t = t.replace(mark, tag)
    return " ".join(t.split())


def speak(text):
    """Text -> WAV bytes in her voice."""
    text = clean(text)
    if not text:
        raise ValueError("no words to say")
    with LOCK:
        kw = {"text": text, "num_step": NUM_STEP, "speed": SPEED}
        if STATE["prompt"] is not None:
            kw["voice_clone_prompt"] = STATE["prompt"]
        else:
            kw["ref_audio"] = REF_WAV
            if ref_text():
                kw["ref_text"] = ref_text()
        audio = STATE["model"].generate(**kw)
    return wav_bytes(audio[0])


def cache_key(text):
    try:
        clip = str(os.path.getmtime(REF_WAV))
    except Exception:
        clip = "none"
    return os.path.join(CACHE, "omni-" + hashlib.sha1(("%s|%s|%s|%s" % (clip, NUM_STEP, SPEED, clean(text))).encode("utf-8")).hexdigest() + ".wav")


def start_up():
    try:
        load_model()
        make_ref()
        STATE["prompt"] = load_prompt()
        t0 = time.time()
        speak("Hi.")                                   # warm up, so her first real line is quick
        STATE["ready"] = True
        log("ready on http://127.0.0.1:%d  (warm-up line took %.1f s)" % (PORT, time.time() - t0))
    except Exception as error:
        STATE["error"] = str(error)
        log("could not start:", error)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, status, ctype, data):
        try:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_GET(self):
        if self.path.startswith("/health") or self.path.startswith("/v1/health"):
            body = {"ok": STATE["ready"], "ready": STATE["ready"], "device": STATE["device"], "error": STATE["error"],
                    "voice": DESIGN, "clip": os.path.exists(REF_WAV)}
            return self._send(200 if STATE["ready"] else 503, "application/json", json.dumps(body).encode())
        if self.path.startswith("/v1/audio/voices"):
            return self._send(200, "application/json", json.dumps({"data": [{"id": "her", "name": "Her HD voice (OmniVoice)"}]}).encode())
        return self._send(404, "text/plain", b"not found")

    def do_POST(self):
        if not self.path.startswith("/v1/audio/speech"):
            return self._send(404, "text/plain", b"not found")
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0") or 0)) or b"{}")
        except Exception:
            return self._send(400, "text/plain", b"bad json")
        text = str(body.get("input") or "")
        if not clean(text):
            return self._send(400, "text/plain", b"no text")
        if not STATE["ready"]:
            return self._send(503, "text/plain", ("her voice is not ready: " + (STATE["error"] or "still loading")).encode())
        key = cache_key(text)
        if os.path.exists(key):
            with open(key, "rb") as f:
                return self._send(200, "audio/wav", f.read())
        try:
            data = speak(text)
        except Exception as error:
            log("failed:", error)
            return self._send(500, "text/plain", ("her voice failed: %s" % error).encode())
        os.makedirs(CACHE, exist_ok=True)
        with open(key + ".part", "wb") as f:
            f.write(data)
        os.replace(key + ".part", key)
        return self._send(200, "audio/wav", data)


def main():
    global PORT
    ap = argparse.ArgumentParser(description="Her HD voice (OmniVoice) for AI World")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--test", help="say this line once and save her_voice/test.wav")
    ap.add_argument("--make-ref", action="store_true", help="make her voice clip again from the design settings")
    ap.add_argument("--ref", help="use this recording as her voice clip")
    ap.add_argument("--ref-text", help="the words spoken in --ref (optional)")
    args = ap.parse_args()
    PORT = args.port
    if args.ref:
        use_clip(args.ref, args.ref_text)
    if args.test or args.make_ref:
        load_model()
        make_ref(force=args.make_ref)
        STATE["prompt"] = load_prompt()
        if args.test:
            t0 = time.time()
            data = speak(args.test)
            out = os.path.join(DIR, "test.wav")
            with open(out, "wb") as f:
                f.write(data)
            log("saved %s (%.1f s to make)" % (out, time.time() - t0))
        return
    threading.Thread(target=start_up, daemon=True).start()
    log("starting on http://127.0.0.1:%d" % PORT)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
