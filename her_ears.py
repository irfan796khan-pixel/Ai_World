"""Her ears: Whisper large-v3-turbo (OpenAI, MIT license) on this laptop's NVIDIA card. HER_EARS_V1

Why: Live chat used VoiceStudio's speech-to-text, but VoiceStudio keeps crashing, so the page fell back to the
browser's own speech recognition, which mishears a lot. This small server does only the listening part.
  - Same address style as VoiceStudio / OpenAI: POST /v1/audio/transcriptions (form field "file" = WAV) -> {"text": "..."}
  - GET /health -> 200 when the model is loaded (503 while it loads)
  - page_server.py sends Live chat speech here first (VoiceStudio only if this is not running).
  - The page finds where you start and stop talking with Silero VAD, then sends only your words here.
  - Model: openai/whisper-large-v3-turbo, about 1.6 GB of GPU memory in fp16. English by default.

Setup once: double-click setup_her_ears.bat (makes ears_env/, installs PyTorch for NVIDIA + transformers, downloads the model).
Run:        ears_env\\Scripts\\python her_ears.py          (run_girl_room.bat starts it by itself)
Test:       ears_env\\Scripts\\python her_ears.py --test some.wav
Settings (environment): HER_EARS_MODEL (default openai/whisper-large-v3-turbo), HER_EARS_LANG (default en; "auto" = any language),
                        HER_EARS_PORT (default 3902)
"""
import argparse
import io
import json
import os
import re
import sys
import threading
import time
import wave
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("HER_EARS_PORT", "3902"))
MODEL_ID = os.getenv("HER_EARS_MODEL", "openai/whisper-large-v3-turbo")
LANG = os.getenv("HER_EARS_LANG", "en")
STATE = {"model": None, "proc": None, "device": None, "dtype": None, "error": None, "ready": False, "heard": 0}
LOCK = threading.Lock()          # one clip at a time on the GPU

# Whisper sometimes "hears" these from noise or silence (known Whisper habit): never send them on
JUNK = re.compile(r"^\W*(you|thank you|thanks for watching|thank you for watching|bye|okay|so|um+|uh+|hmm+|"
                  r"please subscribe|subtitles by.*|\[.*\]|\(.*\)|music|♪+)\W*$", re.I)


def log(*a):
    print("her ears:", *a, flush=True)


def load_model():
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if dev == "cuda" else torch.float32
    log("loading", MODEL_ID, "on", dev, (torch.cuda.get_device_name(0) if dev == "cuda" else "(no NVIDIA card found: slow)"))
    t = time.time()
    proc = WhisperProcessor.from_pretrained(MODEL_ID)
    model = WhisperForConditionalGeneration.from_pretrained(MODEL_ID).to(dev, dtype).eval()
    STATE.update(model=model, proc=proc, device=dev, dtype=dtype, ready=True)
    log("ready in %.0f s" % (time.time() - t))
    transcribe([0.0] * 16000)    # warm up the GPU so the first real line is quick


def to_f32(wav_bytes):
    """WAV (16-bit PCM, any rate, mono or stereo) -> list of float samples at 16 kHz."""
    import numpy as np
    with wave.open(io.BytesIO(wav_bytes)) as w:
        rate, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if width != 2:
        raise ValueError("only 16-bit WAV is supported")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if rate != 16000 and len(x):
        idx = np.arange(0, len(x), rate / 16000.0)
        x = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
    return x


def transcribe(audio):
    import numpy as np
    import torch
    x = np.asarray(audio, dtype=np.float32)
    if len(x) < 1600 or float(np.sqrt(np.mean(x * x))) < 0.002:   # under 0.1 s or near silence: nothing said
        return ""
    proc, model = STATE["proc"], STATE["model"]
    feats = proc(x, sampling_rate=16000, return_tensors="pt").input_features.to(STATE["device"], STATE["dtype"])
    kw = {}
    if getattr(model.generation_config, "is_multilingual", True):   # English-only models take no language / task
        kw["task"] = "transcribe"
        if LANG and LANG != "auto":
            kw["language"] = LANG
    with LOCK, torch.inference_mode():
        ids = model.generate(feats, **kw)
    text = proc.batch_decode(ids, skip_special_tokens=True)[0].strip()
    return "" if JUNK.match(text) else text


def file_from_request(handler, body):
    ctype = handler.headers.get("Content-Type", "")
    if ctype.startswith("multipart/form-data"):
        msg = BytesParser(policy=email_policy).parsebytes(b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + body)
        for part in msg.iter_parts():
            if part.get_param("name", header="content-disposition") == "file":
                return part.get_payload(decode=True)
        raise ValueError("no 'file' field in the form")
    return body          # plain WAV body also works


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/health"):
            if STATE["ready"]:
                return self._send(200, {"ready": True, "model": MODEL_ID, "device": STATE["device"], "heard": STATE["heard"]})
            return self._send(503, {"ready": False, "error": STATE["error"] or "loading"})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/v1/audio/transcriptions"):
            return self._send(404, {"error": "not found"})
        if not STATE["ready"]:
            return self._send(503, {"error": STATE["error"] or "her ears are still loading"})
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
            t = time.time()
            text = transcribe(to_f32(file_from_request(self, body)))
            STATE["heard"] += 1
            log("heard in %.2f s: %s" % (time.time() - t, text or "(nothing)"))
            self._send(200, {"text": text})
        except Exception as e:
            log("error:", e)
            self._send(500, {"error": str(e)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", nargs="?", const="", help="load the model; with a WAV file, write down what it says")
    a = ap.parse_args()
    if a.test is not None:
        load_model()
        if a.test:
            with open(a.test, "rb") as f:
                t = time.time()
                print("TEXT:", transcribe(to_f32(f.read())), "(%.2f s)" % (time.time() - t))
        print("Her ears work.")
        return
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    log("listening on http://127.0.0.1:%d (model loads now)" % PORT)

    def bg():
        try:
            load_model()
        except Exception as e:
            STATE["error"] = str(e)
            log("could not load:", e)
    threading.Thread(target=bg, daemon=True).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
