# VoiceStudio — free local voice for our characters

Hey team, found this: **VoiceStudio** (github.com/debpalash/VoiceStudio, site: voicestudio.sh). It's a free, open source voice tool that runs right on our own PC, kind of like ElevenLabs but local.

It could handle the voice part for us. The brain sends text, VoiceStudio turns it into speech, and the body plays it with `AIWorld.speak()` — her mouth, brows and head already follow the sound.

## Why it's cool
- Free, no limits, no API key.
- Our voice data stays on our PC.
- It can clone a voice from a short sample, or make a new one from a text description, so any character can have its own voice.
- 646 languages.
- Local API at `http://localhost:3900/v1` that works like OpenAI's speech API, so hooking it up is easy.
- Windows 10/11 installer.

## The loop with VoiceStudio
```
we talk  >  brain (Brain.py) writes the reply  >  VoiceStudio makes the MP3  >  AIWorld.speak(mp3)  >  she talks
```

## 1. Install (Windows)
Download the installer from voicestudio.sh, or run this in PowerShell (command from their site):
```
powershell -ep bypass -c "irm https://voicestudio.sh/install.ps1|iex"
```
Open VoiceStudio once so its local API starts on port 3900.

## 2. Quick test from the PC (Python, no extra packages)
Save as `voicestudio_test.py` and run `python voicestudio_test.py`. It should make `test_voice.mp3`.
```python
import json
import urllib.request

VOICESTUDIO_URL = "http://localhost:3900/v1/audio/speech"


def voicestudio_tts(text, voice="alloy", out_path="test_voice.mp3"):
    body = json.dumps({"model": "tts-1", "voice": voice, "input": text}).encode("utf-8")
    req = urllib.request.Request(
        VOICESTUDIO_URL,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as res:
        audio = res.read()
    with open(out_path, "wb") as f:
        f.write(audio)
    return out_path


if __name__ == "__main__":
    print("Saved:", voicestudio_tts("Hi, I live in AI World. Nice to meet you!"))
```

## 3. Make her talk in Girl_Room.html
Paste this in the browser console (or add it to the page). Click the page once first — the browser only plays sound after a click.
```js
async function sayWithVoiceStudio(text, voice = "alloy") {
  const res = await fetch("http://localhost:3900/v1/audio/speech", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": "Bearer local" },
    body: JSON.stringify({ model: "tts-1", voice: voice, input: text })
  });
  if (!res.ok) throw new Error("VoiceStudio error " + res.status);
  const mp3 = await res.blob();
  await AIWorld.speak(mp3);   // plays the voice, face follows the sound
}

// one character, one voice
sayWithVoiceStudio("Oh great, another visitor.", "alloy");

// full brain package (text + emotion + move + voice)
async function replyWithVoice(brain, voice = "alloy") {
  const res = await fetch("http://localhost:3900/v1/audio/speech", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": "Bearer local" },
    body: JSON.stringify({ model: "tts-1", voice: voice, input: brain.response })
  });
  const mp3 = await res.blob();
  await AIWorld.reply({ response: brain.response, emotion: brain.emotion, animation: brain.animation, audio: mp3 });
}
```

## 4. One voice per character
Make or clone a voice in the VoiceStudio app (Voice Design or Voice Clone screen), then pass that voice's name as `voice` above. Example: Mia gets one voice, Max gets another.

## Not tested yet (check on the PC)
- How fast it speaks a reply (for live chat).
- What graphics card / VRAM it needs, and if it runs next to Ollama on the 8 GB laptop GPU.
- If the page (localhost:8081) is allowed to call localhost:3900 directly. If the browser blocks it, the Python test still works and we pass the MP3 to the page another way.
- The exact voice names VoiceStudio uses (only `alloy` is shown in their example).
- License is AGPL-3.0 — fine for us testing; read it before selling anything.

What do you guys think?
