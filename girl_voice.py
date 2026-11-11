"""Her own voice: a teen girl voice made on THIS laptop with Piper (free, offline, fast).

Same engine as the "Adam Voice" phone app (v3, Piper). No VoiceStudio needed.
  voice   : Piper "en_US-hfc_female-medium" (the highest of the 5 US female Piper voices we measured)
  pitch   : LIFT 1.0 = the plain voice (chosen). LIFT 1.12 = made 12% slower, played 12% faster -> about 2 semitones higher
page_server.py uses it for /v1/audio/speech, so the page does not change.

Setup (run_girl_room.bat does this by itself, only the first time):
    python girl_voice.py --setup          installs piper-tts and downloads the voice (about 63 MB)
Test:
    python girl_voice.py "Hi, I live in AI World."      -> writes girl_voice_test.wav
"""
import io
import os
import subprocess
import sys
import threading
import urllib.request
import wave

VOICE = "en_US-hfc_female-medium"
VOICE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/" + VOICE
LIFT = 1.0                      # 1.0 = normal pitch (Imran chose "1 hfc female plain", 9 Nov). 1.12 = about 2 semitones higher (teen)
# VOICE_FIX_V1 (11 Nov): a little slower and clearer, a little more natural ups and downs, and no reading of symbols.
SPEED = 1.06                    # 1.0 = Piper normal speed. 1.06 = 6% slower, easier to follow
NOISE = 0.75                    # Piper default 0.667. A bit more = less flat, less robotic
NOISE_W = 0.9                   # Piper default 0.8. A bit more = less even, more human rhythm
HERE = os.path.dirname(os.path.abspath(__file__))
VOICE_DIR = os.path.join(HERE, "voices")
MODEL = os.path.join(VOICE_DIR, VOICE + ".onnx")

_voice = None
_lock = threading.Lock()        # one line at a time


def have_piper():
    try:
        import piper  # noqa: F401
        return True
    except Exception:
        return False


def ready():
    return have_piper() and os.path.exists(MODEL) and os.path.exists(MODEL + ".json")


def setup():
    """Install piper-tts and download the voice if they are missing. Returns True when ready."""
    if not have_piper():
        print("Installing Piper (her voice engine), only the first time...")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--disable-pip-version-check", "piper-tts"])
        if r.returncode != 0:
            print("Could not install piper-tts. She will use the browser voice.")
            return False
        import site, importlib
        try:
            sys.path.append(site.getusersitepackages())
        except Exception:
            pass
        importlib.invalidate_caches()
    os.makedirs(VOICE_DIR, exist_ok=True)
    for ext in (".onnx.json", ".onnx"):
        dst = os.path.join(VOICE_DIR, VOICE + ext)
        if os.path.exists(dst):
            continue
        print("Downloading her voice " + VOICE + ext + " ...")
        try:
            urllib.request.urlretrieve(VOICE_URL + ext, dst + ".part")
            os.replace(dst + ".part", dst)
        except Exception as e:
            print("Download failed: " + str(e) + "  (she will use the browser voice)")
            return False
    ok = os.path.exists(MODEL) and os.path.exists(MODEL + ".json")   # piper was found or just installed
    print("Her voice is ready." if ok else "Her voice is NOT ready (she will use the browser voice).")
    return ok


def _load():
    global _voice
    if _voice is None:
        from piper import PiperVoice
        _voice = PiperVoice.load(MODEL)
    return _voice


def clean_for_voice(text):
    """Removes things a voice should not read out: *stage words*, (laughs), emojis, links, ... and repeated !!!"""
    import re
    t = str(text)
    t = re.sub(r"\*[^*]{0,60}\*", " ", t)            # *rolls eyes*
    t = re.sub(r"\([^)]{0,40}\)", " ", t)            # (laughs)
    t = re.sub(r"https?://\S+", " link ", t)
    t = re.sub(r"[^\w\s.,!?'\-:;]", " ", t)          # emojis and symbols
    t = re.sub(r"\.{2,}", ", ", t)                   # "..." -> short pause
    t = re.sub(r"([!?])[!?]+", r"\1", t)             # "!!!" -> "!"
    return re.sub(r"\s+", " ", t).strip() or "Hmm."


def speak(text):
    """Text -> WAV bytes in her teen voice."""
    from piper import SynthesisConfig
    with _lock:
        v = _load()
        raw = io.BytesIO()
        with wave.open(raw, "wb") as w:
            v.synthesize_wav(clean_for_voice(text), w, syn_config=SynthesisConfig(length_scale=LIFT * SPEED, noise_scale=NOISE, noise_w_scale=NOISE_W))
        raw.seek(0)
        r = wave.open(raw)
        rate, frames = r.getframerate(), r.readframes(r.getnframes())
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate * LIFT))      # play faster -> higher pitch, back to normal speed
        w.writeframes(frames)
    return out.getvalue()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        sys.exit(0 if setup() else 1)
    if not ready() and not setup():
        sys.exit(1)
    text = " ".join(sys.argv[1:]) or "Oh my gosh, hi! I live in AI World."
    with open(os.path.join(HERE, "girl_voice_test.wav"), "wb") as f:
        f.write(speak(text))
    print("wrote girl_voice_test.wav")
