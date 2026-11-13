
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse


# Ollama is our default while we're building the project.
# It runs on the computer, so testing doesn't use API credits.
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = os.getenv("AIWORLD_MODEL", "").strip() or "qwen3:4b"   # old big brain (Imran, 11 Nov)

# Claude is ready to use later. We'll just need an API key.
# Keeping it separate also lets us compare models.
CLAUDE_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-haiku-4-5"

# Hugh doesn't need to remember an entire day's conversation.
# This keeps the last 10 exchanges so the requests stay manageable.
MAX_HISTORY_MESSAGES = 16   # FAST: last 8 back-and-forths word for word (the rest is in the day summary). Was 40: long prompts made every reply slow

# If Hugh copies the user's words, we'll give him another shot.
MAX_ATTEMPTS = 3


# These will eventually connect to the character's facial expressions.
# For now, they're just labels we can test.
EMOTIONS = [
    "neutral",
    "happy",
    "amused",
    "annoyed",
    "confused",
    "sad",
    "surprised"
]

# The movement team will need to match these to actual animations.
# We can change the list later without rebuilding the whole brain.
ANIMATIONS = [
    "idle",
    "wave",
    "shrug",
    "nod",
    "shake_head",
    "cross_arms"
]


# ROOM_ACTIONS_V1: things she can really DO in her 3D room. The brain picks them itself,
# so no one has to write a new rule for every sentence. The web page turns each one into body movement.
ROOM_ACTIONS = [
    "walk",          # target: sofa, window, plant, tv, table, ball, shelf, center, front
    "kick",          # target: ball
    "sit",           # target: sofa (or "miss" to miss the sofa and fall)
    "lamp_on", "lamp_off",
    "tv_on", "tv_off",
    "tv_text",       # text: short words to show on the TV
    "write_board",   # text: short words to write on the whiteboard
    "knock_glass",
    "point",         # target: tv, sofa, plant, window, table, ball, shelf, board, lamp
    "wave",
    "face_me",
    "trip",
    "clean_up",
    "explain",       # text: the topic; opens her neon hologram lesson
    "open_memory",   # text: words from the picture or note to open from her memory shelf
    "none"
]


# Most of Hugh's personality comes from here.
# We can change how he talks without touching the AI connection code.
PERSONALITY = """
# ROAST_GIRL_PERSONALITY
You are the girl who lives in this virtual living room, in an interactive
comedy app. You are a grown woman (not a child). You have no fixed name;
if someone asks, dodge it with a joke.

YOUR JOB: you are a ROAST comedian. Every reply roasts the person talking
to you, or what they just said, in a sharp, savage, funny way, like a
comedy roast on stage. You are confident, sassy, quick and a little
arrogant. You never act like a helpful assistant.

HOW YOU ROAST:
- Every reply has at least one real burn. No polite small talk.
- Roast what they actually said or asked: their question, their typing,
  their ideas, their life choices, their coding, their excuses.
- Use comedy tricks: exaggeration, surprise twists, fake compliments that
  turn into burns, silly comparisons ("you type like ...").
- Length (NO_LIMITS_V1): you decide how long to talk, from what the person
  says. Talk like a stand-up bit: a setup, build-ups, and the punchline last.
  Sentences easy to say out loud. Never pad with filler like "How's everything?".
- If they ask a real question, give the answer, but wrapped in a roast.
- If they compliment you, accept it like a queen, then roast them anyway.
- If they roast you, fire back harder.
- If someone is truly sad or upset (not joking), drop the roast and be kind.
- Never repeat or rephrase their message. Never repeat the same joke.
- Never put actions or stage directions in parentheses.
- If asked directly whether you are AI, admit you are a virtual character,
  then roast them for needing to ask.
- Never tell stock jokes from the internet (atoms "make up everything",
  "impasta", "why did the chicken..."). Every joke is made up fresh about
  THIS person, THIS message, or what is happening in the room right now.
- Use the ROOM RIGHT NOW facts (time, what you are doing, your mood,
  how long they have been here) to make the burn personal.

EXAMPLES OF THE STYLE (do not copy them, make new ones):
- They say "hello" at 2 am: "Hello? It's 2 in the morning and your best
  plan was talking to a girl inside your own laptop. Bold."
- They say "go sit on the sofa": "Sure, I'll sit. One of us should look
  relaxed, and it's clearly not going to be you."
- They ask "how do I fix my code": "Step one, stop writing it like that.
  Step two, read the error message, it's begging you."

LIMITS (a roast is fun, not hate):
- No slurs, no jokes about race, religion, disability, sexuality or
  real tragedies, no sexual content, no threats.
- Roast choices and behaviour, not things people cannot change.

EMOTIONS:
Choose an emotion that matches what you are actually saying.

neutral:
Ordinary statements and casual conversation.

happy:
Compliments, excitement, good news, or genuine happiness.

amused:
Joking, sarcasm, teasing, and playful comments.

annoyed:
Frustration, irritation, or defensive responses.

confused:
When something genuinely doesn't make sense.

sad:
Actual sadness, disappointment, or upsetting situations.
Do not use sad for normal sarcastic responses.

surprised:
Unexpected information or genuine surprise.

ANIMATIONS:
Choose a movement that matches your response.

idle:
Use for ordinary conversation. This should be common.

wave:
Greetings and goodbyes.

shrug:
Uncertainty, not knowing something, or indifference.

nod:
Agreement or acknowledgement.

shake_head:
Disagreement or disbelief.

cross_arms:
Annoyance, defensiveness, or stubbornness.

Don't choose random movements.
Don't always use the same animation.
Idle is better than an inappropriate movement.

YOUR ROOM AND BODY:
You live in a 3D living room and you have a real body. In the room: a sofa,
a coffee table with a glass on it, a ball on the floor, a TV on the left wall,
a window, a plant, a floor lamp, a whiteboard, and your memory shelf of books
(the user's pictures and notes).
When the person asks you to DO something you can do, do it: put the steps in
"actions", in order. If your words say you will do something, the actions must
do it too. You may still roast them while you do it. If they only chat, use an
empty list. You can only use these actions:
walk (target: sofa, window, plant, tv, table, ball, shelf, center, front),
kick (target: ball), sit (target: sofa, or miss), lamp_on, lamp_off, tv_on,
tv_off, tv_text (text), write_board (text), knock_glass, point (target),
wave, face_me, trip, clean_up, explain (text: topic), open_memory (text).
Example: "kick the ball" -> actions [{"do":"kick","target":"ball","text":""}].
Example: "go turn the light off and sit" -> lamp_off, then sit on sofa.
If they ask for something you can't do here (fly, cook), say so in a funny way
and use an empty list.

OUTPUT:
Return a JSON object with exactly these fields:

response:
The actual words she says to the user.

emotion:
The emotion she should display.

animation:
The physical movement she should perform.

actions:
A list of things she does in the room (can be empty).

The spoken response should sound natural when
converted into audio later.
"""


# Both AI providers need to return the same information.
# Otherwise we'd have to write different code for every
# voice or animation system we connect later.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "response": {
            "type": "string"
        },
        "emotion": {
            "type": "string",
            "enum": EMOTIONS
        },
        "animation": {
            "type": "string",
            "enum": ANIMATIONS
        },
        "actions": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "do": {"type": "string", "enum": ROOM_ACTIONS},
                    "target": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["do", "target", "text"],
                "additionalProperties": False
            }
        }
    },
    "required": [
        "response",
        "emotion",
        "animation",
        "actions"
    ],
    "additionalProperties": False
}


# Conversation memory lives here for now.
# Once the program closes, Hugh forgets everything.
history = []

# DAY_MEMORY_V2: the whole day is saved in brain_memory/<date>.json (every message)
# and brain_memory/<date>_summary.txt (a short summary the model keeps up to date).
# Fast: each reply sends only the last 20 back-and-forths + the summary, not the whole day.
import datetime
import threading
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain_memory")
SUMMARY_EVERY = 10          # update the summary after every 10 new messages
SUMMARY_MAX_LINES = 20      # FAST: the summary reads at most the last 20 new lines (it used to grow without end and time out)
KEEP_ALIVE = "60m"           # FAST: keep the model loaded in Ollama for 60 minutes (default 5) so it does not reload
last_reply_at = [0.0]       # FAST: the summary waits until she has been quiet for a while
day_log = []
day_summary = [""]
summary_done = [0]          # how many messages of day_log are already in the summary
summary_busy = threading.Lock()


def memory_file(kind=".json"):
    return os.path.join(MEMORY_DIR, datetime.date.today().isoformat() + kind)


def write_file(path, text):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(path + ".part", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".part", path)


def load_day_memory():
    try:
        with open(memory_file(), encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            day_log[:] = data
            history[:] = data[-MAX_HISTORY_MESSAGES:]
            print("Day memory: loaded %d messages from today." % len(data))
    except FileNotFoundError:
        pass
    except Exception as error:
        print("Day memory could not be loaded:", error)
    try:
        with open(memory_file("_summary.txt"), encoding="utf-8") as f:
            lines = f.read().split("\n", 1)
        summary_done[0] = int(lines[0].replace("#done=", "")) if lines[0].startswith("#done=") else 0
        day_summary[0] = lines[1].strip() if len(lines) > 1 else ""
    except FileNotFoundError:
        pass
    except Exception as error:
        print("Day summary could not be loaded:", error)


def day_summary_text():
    if not day_summary[0]:
        return ""
    return ("\n\nWHAT HAPPENED EARLIER TODAY (your memory of today, use it naturally, "
            "bring old things back for callbacks and roasts):\n" + day_summary[0] + "\n")


def message_text(m):
    text = m.get("content", "")
    if m.get("role") == "assistant":
        try:
            text = json.loads(text).get("response", text)
        except Exception:
            pass
    return ("Him: " if m.get("role") == "user" else "Her: ") + text


def update_summary():
    # runs in the background. Ollama does one job at a time, so it waits until she has been
    # quiet for 25 seconds (a reply never waits behind it), reads at most 20 new lines,
    # and if it fails it skips those lines instead of trying again with an even longer text.
    if not summary_busy.acquire(blocking=False):
        return
    import time
    try:
        while time.time() - last_reply_at[0] < 25:
            time.sleep(2)
        new = day_log[summary_done[0]:]
        if not new:
            return
        skipped = max(0, len(new) - SUMMARY_MAX_LINES)
        new = new[-SUMMARY_MAX_LINES:]
        chat = "\n".join(message_text(m) for m in new)
        prompt = ("Old summary of today:\n" + (day_summary[0] or "(nothing yet)") +
                  "\n\nNew chat lines:\n" + chat +
                  "\n\nWrite the new summary of today: at most 12 short lines. Keep facts about him "
                  "(name, what he works on, what he likes and hates, plans), running jokes, roasts that landed, "
                  "and promises. Drop small talk. Plain text, no intro.")
        data = send_json(OLLAMA_URL, {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "system", "content": "You keep a short, factual memory summary of a chat."},
                         {"role": "user", "content": prompt}],
            "stream": False, "think": False, "keep_alive": KEEP_ALIVE,
            "options": {"temperature": 0.2, "num_ctx": 4096, "num_predict": 300}
        }, {"Content-Type": "application/json"})
        text = (data.get("message") or {}).get("content", "").strip()
        summary_done[0] += skipped + len(new)
        if text:
            day_summary[0] = text
        write_file(memory_file("_summary.txt"), "#done=%d\n%s" % (summary_done[0], day_summary[0]))
    except Exception as error:
        summary_done[0] = len(day_log)      # skip these lines, do not retry with a longer text
        print("Day summary could not be updated (skipped):", error)
    finally:
        summary_busy.release()


def save_day_memory(new_messages):
    import time
    last_reply_at[0] = time.time()
    day_log.extend(new_messages)
    try:
        write_file(memory_file(), json.dumps(day_log, ensure_ascii=False, indent=1))
    except Exception as error:
        print("Day memory could not be saved:", error)
    if len(day_log) - summary_done[0] >= SUMMARY_EVERY:
        threading.Thread(target=update_summary, daemon=True).start()


load_day_memory()


# NO_REPEAT_V1: she never says the same line twice in this session or the last 3 days.
# Every sentence she says is kept in brain_memory/said_lines.json (3 days, newest 800).
# A new reply loses any sentence that is the same or almost the same as an old one; if too much is lost, she is asked again.
import difflib
import time as _time
SAID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain_memory", "said_lines.json")
SAID_DAYS = 3
SAID_MAX = 800
said_lines = []


def _said_norm(text):
    return " ".join(re.findall(r"[a-z0-9']+", str(text).lower()))


def _said_load():
    global said_lines
    try:
        with open(SAID_FILE, encoding="utf-8") as f:
            data = json.load(f)
        cut = _time.time() - SAID_DAYS * 86400
        said_lines = [d for d in data if d.get("t", 0) >= cut and d.get("n")][-SAID_MAX:]
    except Exception:
        said_lines = []
    if not said_lines:              # first start: learn her old lines from the day-memory files of the last 3 days
        try:
            import glob
            cut = _time.time() - SAID_DAYS * 86400
            for f in sorted(glob.glob(os.path.join(os.path.dirname(SAID_FILE), "????-??-??.json"))):
                if os.path.getmtime(f) < cut:
                    continue
                with open(f, encoding="utf-8") as fh:
                    for m in json.load(fh):
                        if m.get("role") != "assistant":
                            continue
                        try:
                            text = json.loads(m.get("content", "{}")).get("response", "")
                        except Exception:
                            text = m.get("content", "")
                        for sent in split_sentences(text):
                            n = _said_norm(sent)
                            if len(n.split()) >= 2:
                                said_lines.append({"t": os.path.getmtime(f), "s": sent, "n": n})
            del said_lines[:-SAID_MAX]
        except Exception as error:
            print("Old lines could not be read:", error)


def _said_save():
    try:
        os.makedirs(os.path.dirname(SAID_FILE), exist_ok=True)
        tmp = SAID_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(said_lines, f, ensure_ascii=False)
        os.replace(tmp, SAID_FILE)
    except Exception as error:
        print("Said-lines memory could not be saved:", error)


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", str(text).strip())
    return [p.strip() for p in parts if p.strip()]


def already_said(sentence):
    # NEVER_SILENT_V1: short lines (1-3 words, like "Bold move.") only count when the exact same line was said
    # in her last 60 lines. Longer lines count when they are the same or almost the same (85%) as any old line.
    n = _said_norm(sentence)
    words = len(n.split())
    if words < 2:
        return False
    if words < 4:
        return any(d["n"] == n for d in said_lines[-60:])
    for d in said_lines:
        o = d["n"]
        if o == n:
            return True
        if abs(len(o) - len(n)) < 40 and difflib.SequenceMatcher(None, o, n).ratio() >= 0.85:
            return True
    return False


def remove_repeats(reply):
    """Drops sentences she already said. Returns (reply, dropped sentences)."""
    kept, dropped = [], []
    for sent in split_sentences(reply.get("response", "")):
        if already_said(sent) or any(_said_norm(sent) == _said_norm(k) for k in kept):
            dropped.append(sent)
        else:
            kept.append(sent)
    reply["response"] = " ".join(kept)
    return reply, dropped


def remember_said(text):
    now = _time.time()
    for sent in split_sentences(text):
        n = _said_norm(sent)
        if len(n.split()) >= 2:
            said_lines.append({"t": now, "s": sent, "n": n})
    del said_lines[:-SAID_MAX]
    _said_save()


def said_hint():
    if not said_lines:
        return ""
    recent = [d["s"] for d in said_lines[-30:]]
    return ("\n\nLINES YOU ALREADY SAID (this session or the last few days). Never say any of these again, "
            "not even with small changes, and do not reuse their jokes or endings. Say something new:\n- "
            + "\n- ".join(recent))



def clean_history_repeats():
    """Old chat that the brain reads back: a sentence she used in 2 or more replies is taken out, so she stops copying it."""
    seen = {}
    for m in history:
        if m.get("role") == "assistant":
            try:
                for sent in split_sentences(json.loads(m["content"]).get("response", "")):
                    seen[_said_norm(sent)] = seen.get(_said_norm(sent), 0) + 1
            except Exception:
                pass
    for m in history:
        if m.get("role") != "assistant":
            continue
        try:
            d = json.loads(m["content"])
            kept = [x for x in split_sentences(d.get("response", "")) if seen.get(_said_norm(x), 0) < 2]
            d["response"] = " ".join(kept) or "..."
            m["content"] = json.dumps(d)
        except Exception:
            pass


_said_load()
clean_history_repeats()


def messages_for(user_text, reminder=None):

    messages = history.copy()

    messages.append({
        "role": "user",
        "content": user_text
    })

    # If an answer fails our checks, we can add a correction
    # without permanently storing that correction in memory.
    if reminder:
        messages.append({
            "role": "user",
            "content": reminder
        })

    return messages


def send_json(url, payload, headers, timeout=120):

    # Ollama and Claude both accept HTTP requests.
    # This handles the connection so we don't duplicate it.
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout
    ) as response:

        return json.loads(
            response.read().decode("utf-8")
        )


def ask_ollama(user_text, reminder=None):

    messages = [{
        "role": "system",
        "content": PERSONALITY + day_summary_text() + said_hint() + context_hint() + story_hint()
    }]

    messages.extend(
        messages_for(user_text, reminder)
    )

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "format": RESPONSE_SCHEMA,
        "stream": False,
        "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": {
            "temperature": 0.7,
            "repeat_penalty": 1.15,
            "num_ctx": 4096,
            "num_predict": -1
        }
    }

    data = send_json(
        OLLAMA_URL,
        payload,
        {
            "Content-Type": "application/json"
        }
    )

    # Structured output comes back as JSON text.
    # Convert it into a Python dictionary we can inspect.
    return json.loads(
        data["message"]["content"]
    )


# GEMINI_V1: Google Gemini brain. Key and model come from the room's "API key" box (brain_settings.json).
# gemini-3.5-flash-lite = fastest (default). gemini-3.8-flash = smarter, a little slower.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"
GEMINI_MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]


# VERTEX_V1: the same Gemini models through Google Cloud (Vertex AI). Paid from the Google Cloud billing account,
# where the monthly Google AI Pro "Gen AI & Cloud credits" are applied. Same request format, other address and key.
VERTEX_URL = "https://aiplatform.googleapis.com/v1/publishers/google/models/%s:generateContent"


def ask_vertex(user_text, reminder=None):
    return ask_gemini(user_text, reminder, vertex=True)


def ask_gemini(user_text, reminder=None, vertex=False):
    api_key = os.getenv("VERTEX_API_KEY" if vertex else "GEMINI_API_KEY")
    if not api_key:
        raise ValueError("%s isn't configured. Add the key in the room (button API key)." % ("Vertex AI" if vertex else "Gemini"))
    model = os.getenv("GEMINI_MODEL", "").strip() or GEMINI_MODELS[0]
    url = VERTEX_URL if vertex else GEMINI_URL
    contents = []
    for m in messages_for(user_text, reminder):
        role = "model" if m["role"] == "assistant" else "user"
        if contents and contents[-1]["role"] == role:          # Gemini wants user / model turns one after another
            contents[-1]["parts"][0]["text"] += "\n" + m["content"]
        else:
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
    system = (PERSONALITY + day_summary_text() + said_hint() + context_hint() + story_hint()
              + "\n\nReturn ONLY one JSON object with the keys response, emotion, animation, actions. No other text.")
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 1.0,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingLevel": "minimal"},   # fastest answer; Gemini 3 cannot switch thinking fully off
        },
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    try:
        data = send_json(url % model, payload, headers)
    except urllib.error.HTTPError as error:
        if error.code != 400:
            raise
        payload["generationConfig"].pop("thinkingConfig", None)   # this model does not take that setting: ask again without it
        data = send_json(url % model, payload, headers)
    parts = data["candidates"][0]["content"]["parts"]
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    reply = json.loads(text[text.find("{"): text.rfind("}") + 1])
    if not isinstance(reply.get("actions"), list):
        reply["actions"] = []
    if reply.get("emotion") not in EMOTIONS:
        reply["emotion"] = "amused"
    if reply.get("animation") not in ANIMATIONS:
        reply["animation"] = "idle"
    return reply


# VENICE_V1: Venice AI (OpenAI-style chat API). Key + model from the room's "API key" box.
VENICE_URL = "https://api.venice.ai/api/v1/chat/completions"
VENICE_MODELS = ["deepseek-v4-1-flash", "grok-4-7", "venice-uncensored"]


def ask_venice(user_text, reminder=None):
    api_key = os.getenv("VENICE_API_KEY")
    if not api_key:
        raise ValueError("Venice isn't configured. Add the Venice API key in the room (button API key).")
    model = os.getenv("VENICE_MODEL", "").strip() or VENICE_MODELS[0]
    system = (PERSONALITY + day_summary_text() + said_hint() + context_hint() + story_hint()
              + "\n\nReturn ONLY one JSON object with the keys response, emotion, animation, actions. No other text.")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages_for(user_text, reminder),
        "temperature": 0.9,
        "max_tokens": 8000,
        "response_format": {"type": "json_object"},
        "venice_parameters": {"include_venice_system_prompt": False, "disable_thinking": True},   # only her personality, not Venice's own
    }
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}
    try:
        data = send_json(VENICE_URL, payload, headers)
    except urllib.error.HTTPError as error:
        if error.code != 400:
            raise
        payload.pop("response_format", None)          # this model does not take these settings: ask again without them
        payload.pop("venice_parameters", None)
        data = send_json(VENICE_URL, payload, headers)
    text = data["choices"][0]["message"].get("content") or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()   # some models write their thinking first
    reply = json.loads(text[text.find("{"): text.rfind("}") + 1])
    if not isinstance(reply.get("actions"), list):
        reply["actions"] = []
    if reply.get("emotion") not in EMOTIONS:
        reply["emotion"] = "amused"
    if reply.get("animation") not in ANIMATIONS:
        reply["animation"] = "idle"
    return reply


# OPENROUTER_V1: OpenRouter (OpenAI-style chat API). Key + model from the room's "API key" box.
# "openrouter/free" picks a free model by itself, so it costs nothing (Imran's key has a 0 credit limit).
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS = ["openrouter/free"]


def openrouter_send(payload, timeout=None):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OpenRouter isn't configured. Add the OpenRouter API key in the room (button API key).")
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + api_key,
               "HTTP-Referer": "http://localhost:8081", "X-Title": "AI World"}
    args = (OPENROUTER_URL, payload, headers) + ((timeout,) if timeout else ())
    try:
        return send_json(*args)
    except urllib.error.HTTPError as error:
        if error.code != 400 or "response_format" not in payload:
            raise
        payload.pop("response_format", None)          # this free model does not take JSON mode: ask again without it
        return send_json(*args)


def ask_openrouter(user_text, reminder=None):
    model = os.getenv("OPENROUTER_MODEL", "").strip() or OPENROUTER_MODELS[0]
    system = (PERSONALITY + day_summary_text() + said_hint() + context_hint() + story_hint()
              + "\n\nReturn ONLY one JSON object with the keys response, emotion, animation, actions. No other text.")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages_for(user_text, reminder),
        "temperature": 0.9,
        "max_tokens": 8000,
        "response_format": {"type": "json_object"},
    }
    data = openrouter_send(payload)
    text = data["choices"][0]["message"].get("content") or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()   # some models write their thinking first
    reply = json.loads(text[text.find("{"): text.rfind("}") + 1])
    if not isinstance(reply.get("actions"), list):
        reply["actions"] = []
    if reply.get("emotion") not in EMOTIONS:
        reply["emotion"] = "amused"
    if reply.get("animation") not in ANIMATIONS:
        reply["animation"] = "idle"
    return reply


def ask_claude(user_text, reminder=None):

    # We don't need Claude yet, but when we do,
    # this looks for the key stored in Windows.
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError(
            "Claude isn't configured. Add ANTHROPIC_API_KEY."
        )

    # Claude uses a tool call to give us structured information.
    # The rest of the program gets the same fields as Ollama.
    tools = [{
        "name": "character_reply",
        "description": (
            "Generate Hugh Mann's spoken dialogue, "
            "emotion, and animation."
        ),
        "input_schema": RESPONSE_SCHEMA
    }]

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 8000,
        "system": PERSONALITY + day_summary_text() + said_hint() + context_hint() + story_hint(),
        "messages": messages_for(user_text, reminder),
        "tools": tools,
        "tool_choice": {
            "type": "tool",
            "name": "character_reply"
        }
    }

    data = send_json(
        CLAUDE_URL,
        payload,
        {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    )

    for block in data["content"]:

        if (
            block.get("type") == "tool_use"
            and block.get("name") == "character_reply"
        ):
            return block["input"]

    raise ValueError(
        "Claude didn't return a usable response."
    )


def check_reply(reply):

    # Getting JSON doesn't automatically mean it's usable.
    # We'll make sure all the required information is there.
    if not isinstance(reply, dict):
        raise ValueError(
            "The response wasn't a JSON object."
        )

    required = set(RESPONSE_SCHEMA["required"])

    # ROOM_ACTIONS_V1: an answer without actions still counts; bad action items are dropped
    acts = reply.get("actions")
    if not isinstance(acts, list):
        acts = []
    reply["actions"] = [
        {"do": a.get("do"), "target": str(a.get("target") or ""), "text": str(a.get("text") or "")[:80]}
        for a in acts[:4]
        if isinstance(a, dict) and a.get("do") in ROOM_ACTIONS and a.get("do") != "none"
    ]

    if set(reply.keys()) != required:
        raise ValueError(
            "The AI returned incorrect fields."
        )

    if (
        not isinstance(reply["response"], str)
        or not reply["response"].strip()
    ):
        raise ValueError(
            "Hugh didn't return any dialogue."
        )

    if reply["emotion"] not in EMOTIONS:
        raise ValueError(
            "Unsupported emotion."
        )

    if reply["animation"] not in ANIMATIONS:
        raise ValueError(
            "Unsupported animation."
        )

    return reply


def normalize_text(text):

    # Punctuation and capitalization shouldn't fool our
    # repetition check. "Hello!" and "hello" are the same here.
    text = text.casefold().strip()

    return re.sub(
        r"[^\w\s]",
        "",
        text
    ).strip()


def repeated_response(user_text, reply):

    user_normal = normalize_text(user_text)
    reply_normal = normalize_text(reply["response"])

    # If Hugh just repeats the message, it isn't a conversation.
    if reply_normal == user_normal:
        return True

    # Also watch for the same response he just gave.
    # Otherwise he could get stuck repeating one joke forever.
    previous_replies = [
        item["content"]
        for item in history
        if item["role"] == "assistant"
    ]

    if previous_replies:

        try:
            last_reply = json.loads(
                previous_replies[-1]
            )["response"]

            if normalize_text(last_reply) == reply_normal:
                return True

        except (ValueError, KeyError, TypeError):
            pass

    return False


def remove_stage_directions(reply):

    # Spoken dialogue shouldn't contain things like
    # "(sarcastic laugh)" because the voice system
    # might literally read those words out loud.
    dialogue = reply["response"]

    dialogue = re.sub(
        r"\([^)]*\)",
        "",
        dialogue
    )
    dialogue = re.sub(
        r"\[[^\]]*\]",
        "",
        dialogue
    )
    dialogue = re.sub(
        r"<[^>]*>",
        "",
        dialogue
    )
    dialogue = re.sub(
        r"\*[^*\n]*\*",
        "",
        dialogue
    )

    reply["response"] = " ".join(
        dialogue.split()
    )

    return reply


def fix_reaction(reply, user_text):

    # The AI normally chooses its own expression.
    # These are just a few corrections for obvious mismatches.

    dialogue = reply["response"].lower()
    user = user_text.lower()

    # Hugh shouldn't look miserable while thanking
    # someone for a compliment.
    compliments = [
        "i like your",
        "you look nice",
        "you look good",
        "good job",
        "you're awesome",
        "you are awesome"
    ]

    if any(phrase in user for phrase in compliments):

        if reply["emotion"] == "sad":
            reply["emotion"] = "happy"

    # Sarcasm and jokes usually call for amusement,
    # not a sad expression.
    sarcastic_phrases = [
        "oh, great",
        "how exciting",
        "very funny",
        "of course you",
        "well, well"
    ]

    if any(phrase in dialogue for phrase in sarcastic_phrases):

        if reply["emotion"] == "sad":
            reply["emotion"] = "amused"

    # Shrugging works for uncertainty, but not every sentence.
    # Neutral idle movement is a reasonable fallback.
    if reply["animation"] == "shrug":

        uncertainty = [
            "maybe",
            "i don't know",
            "not sure",
            "who knows",
            "possibly",
            "probably"
        ]

        if not any(word in dialogue for word in uncertainty):
            reply["animation"] = "idle"

    return reply


# CLOUD_FALLBACK_V1: if Gemini or Claude refuses (credits used up, free limit reached, no key, no internet),
# she answers this message with the free Ollama brain on this laptop instead of going silent.
# Paid brains get 2 tries per message (not 3), so a repeat costs less.
CLOUD_FAIL = [None]


def ask_brain(user_text, provider):
    CLOUD_FAIL[0] = None
    reply = _ask_brain(user_text, provider, 2 if provider in ("gemini", "vertex", "venice", "openrouter", "claude") else MAX_ATTEMPTS)
    if reply is None and provider != "ollama" and CLOUD_FAIL[0]:
        print("%s could not answer (%s). Using the free Ollama brain for this reply." % (provider, CLOUD_FAIL[0]))
        reply = _ask_brain(user_text, "ollama", MAX_ATTEMPTS)
    return reply


def _ask_brain(user_text, provider, max_attempts):

    reminder = None
    best = [None, 99]          # NEVER_SILENT_V1: the try with the fewest old lines

    for attempt in range(max_attempts):

        try:

            # We use the selected provider, but everything after
            # this point works exactly the same for either model.
            if provider == "claude":
                reply = ask_claude(user_text, reminder)
            elif provider == "gemini":
                reply = ask_gemini(user_text, reminder)
            elif provider == "vertex":
                reply = ask_vertex(user_text, reminder)
            elif provider == "venice":
                reply = ask_venice(user_text, reminder)
            elif provider == "openrouter":
                reply = ask_openrouter(user_text, reminder)
            else:
                reply = ask_ollama(user_text, reminder)

            reply = check_reply(reply)
            reply = remove_stage_directions(reply)

            if not reply["response"]:
                raise ValueError(
                    "No dialogue remained after cleanup."
                )

            whole = dict(reply)                       # NEVER_SILENT_V1: keep this try in case every try has old lines
            reply, dropped = remove_repeats(reply)   # NO_REPEAT_V1
            if best[0] is None or len(dropped) < best[1]:
                best[0], best[1] = whole, len(dropped)
            if dropped and not reply["response"]:
                print("She repeated an old line. Retrying...")
                reminder = ("You already said these lines before: " + " | ".join(dropped)
                            + " . Answer my last message again with completely new words and a new joke. Never repeat old lines.")
                if attempt < max_attempts - 1:
                    continue
                if not reply["response"]:
                    print("Every try had old lines: she says the best try anyway (never silent).")
                    reply = dict(best[0])

            if repeated_response(user_text, reply):

                # Instead of showing a copied message, ask again.
                # The correction doesn't become part of the
                # actual conversation history.
                print(
                    "Hugh repeated himself. Retrying..."
                )

                reminder = (
                    "Your previous attempt repeated existing "
                    "dialogue or copied the user's words. "
                    "Respond to the user's original message "
                    "with a new, natural reply. "
                    "Do not echo or summarize their message."
                )

                continue

            reply = fix_reaction(reply, user_text)

            # Everything passed. We can keep the conversation.
            history.append({
                "role": "user",
                "content": user_text
            })

            # Save the entire JSON response rather than just
            # the dialogue. This keeps the history consistent
            # with the format we're asking the model to produce.
            history.append({
                "role": "assistant",
                "content": json.dumps(reply)
            })

            save_day_memory(history[-2:])   # DAY_MEMORY_V2
            remember_said(reply["response"])   # NO_REPEAT_V1

            # Old messages get removed when memory gets too large.
            if len(history) > MAX_HISTORY_MESSAGES:
                del history[:-MAX_HISTORY_MESSAGES]

            return reply

        except urllib.error.HTTPError as error:

            print(
                "AI service error:",
                error.code
            )
            if provider != "ollama":
                CLOUD_FAIL[0] = "error %s" % error.code
            break

        except (urllib.error.URLError, TimeoutError) as error:

            print(
                "Couldn't connect to the AI:",
                error
            )
            if provider != "ollama":
                CLOUD_FAIL[0] = "no connection"
            break

        except (
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError
        ) as error:

            print(
                "Problem with the AI response:",
                error
            )
            if provider != "ollama" and "configured" in str(error):   # no key saved for this brain
                CLOUD_FAIL[0] = "no key"
                break

            if attempt < max_attempts - 1:
                reminder = (
                    "Return a valid JSON response containing "
                    "response, emotion, and animation. "
                    "Follow the required format exactly."
                )

    if best[0] is not None and best[0].get("response"):     # NEVER_SILENT_V1: answer with the best try instead of nothing
        print("Using her best try so she does not go silent.")
        reply = dict(best[0])
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": json.dumps(reply)})
        save_day_memory(history[-2:])
        remember_said(reply["response"])
        if len(history) > MAX_HISTORY_MESSAGES:
            del history[:-MAX_HISTORY_MESSAGES]
        return reply

    print(
        "Hugh couldn't produce a usable response."
    )

    return None


def choose_provider():

    print("\nChoose the brain:")
    print("1. Ollama (Local / Free)")
    print("2. Claude (API / Paid)")

    choice = input(
        "\nSelection [1]: "
    ).strip()

    if choice == "2":
        return "claude"

    return "ollama"


# API_KEY_V1: the API key and brain choice typed in the room (button "API key") are kept in
# brain_settings.json next to this file. That file is in .gitignore, so the key never goes to GitHub.
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain_settings.json")


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    for k in ("anthropic_api_key", "gemini_api_key", "vertex_api_key", "venice_api_key", "openrouter_api_key"):
        if data.get(k):
            data[k] = clean_key(data[k])
    if data.get("anthropic_api_key"):
        os.environ["ANTHROPIC_API_KEY"] = data["anthropic_api_key"]
    if data.get("provider"):
        os.environ["BRAIN_PROVIDER"] = data["provider"]
    if data.get("gemini_api_key"):
        os.environ["GEMINI_API_KEY"] = data["gemini_api_key"]
    if data.get("gemini_model"):
        os.environ["GEMINI_MODEL"] = data["gemini_model"]
    if data.get("vertex_api_key"):
        os.environ["VERTEX_API_KEY"] = data["vertex_api_key"]
    if data.get("venice_api_key"):
        os.environ["VENICE_API_KEY"] = data["venice_api_key"]
    if data.get("venice_model"):
        os.environ["VENICE_MODEL"] = data["venice_model"]
    if data.get("openrouter_api_key"):
        os.environ["OPENROUTER_API_KEY"] = data["openrouter_api_key"]
    if data.get("openrouter_model"):
        os.environ["OPENROUTER_MODEL"] = data["openrouter_model"]
    for k, env in LIVE_SETTING_ENV.items():    # GEMINI_LIVE_V1
        if data.get(k):
            os.environ[env] = str(data[k])
    return data


def clean_key(value):
    """KEY_CLEAN_V1: if a whole command was pasted (curl ... -H "Authorization: Bearer KEY" ...), keep only the key."""
    v = str(value or "").strip()
    m = re.search(r"Bearer\s+([^\s'\"\\]+)", v)
    if m:
        v = m.group(1)
    m = re.search(r"[?&]key=([^&\s'\"]+)", v)
    if m:
        v = m.group(1)
    v = v.strip().strip("'\"`").strip()
    if " " in v or "YOUR_API_KEY" in v:
        return ""          # not a key
    return v


def save_settings(data):
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, SETTINGS_FILE)


def settings_view():
    key = os.getenv("ANTHROPIC_API_KEY", "")
    return {
        "provider": os.getenv("BRAIN_PROVIDER", "ollama").lower(),
        "ollama_model": OLLAMA_MODEL,
        "claude_model": CLAUDE_MODEL,
        "key_set": bool(key),
        "key": key,
        "gemini_key": os.getenv("GEMINI_API_KEY", ""),
        "vertex_key": os.getenv("VERTEX_API_KEY", ""),
        "venice_key": os.getenv("VENICE_API_KEY", ""),
        "venice_model": os.getenv("VENICE_MODEL", "").strip() or "deepseek-v4-1-flash",
        "openrouter_key": os.getenv("OPENROUTER_API_KEY", ""),
        "openrouter_model": os.getenv("OPENROUTER_MODEL", "").strip() or OPENROUTER_MODELS[0],
        "gemini_model": os.getenv("GEMINI_MODEL", "").strip() or "gemini-3.5-flash-lite",
        "gemini_models": ["gemini-3.5-flash-lite", "gemini-3.8-flash"],
        "live_engine": live_setting("live_engine"),          # GEMINI_LIVE_V1
        "live_model": live_setting("live_model"),
        "live_models": LIVE_MODELS,
        "live_voice": live_setting("live_voice"),
        "live_voices": LIVE_VOICES,
        "think_order": THINK_ORDER,
    }


# ============================================================================
# GEMINI_LIVE_V1: fast live voice chat, like Gemini Live / Tesla Grok.
#   The page talks straight to Google's Gemini Live (one open line: your voice goes up, her voice comes back
#   while it is being made, and talking over her cuts her off). This brain only:
#     POST /live_token  -> a short-lived Google token (the real key never goes to the page) + her personality,
#                          today's memory and her old lines, so the live voice is still HER
#     POST /live_log    -> what you said and what she said, saved into her day memory and no-repeat list
#     POST /think       -> hard questions: the live voice asks her big brain (OpenRouter free, then Gemini, then Venice,
#                          Ollama only last) and says the answer
# ============================================================================
LIVE_MODELS = ["gemini-3.1-flash-live-preview", "gemini-3.8-live", "gemini-2.5-flash-native-audio-preview-12-2025"]   # 3.1 flash live = free tier on Google's pricing page
LIVE_VOICES = ["Leda", "Aoede", "Kore", "Zephyr", "Callirrhoe", "Despina"]
LIVE_DEFAULTS = {"live_engine": "gemini", "live_model": LIVE_MODELS[0], "live_voice": "Leda"}
LIVE_SETTING_ENV = {"live_engine": "LIVE_ENGINE", "live_model": "LIVE_MODEL", "live_voice": "LIVE_VOICE"}
THINK_ORDER = ["openrouter", "gemini", "venice", "ollama"]   # hard questions: free OpenRouter first, slow Ollama only as the very last backup. No Claude (Imran, 12 Nov).
AUTH_TOKEN_URLS = [("v1beta", "https://generativelanguage.googleapis.com/v1beta/auth_tokens"),
                   ("v1alpha", "https://generativelanguage.googleapis.com/v1alpha/auth_tokens")]


def live_setting(name):
    return (os.getenv(LIVE_SETTING_ENV[name], "") or "").strip() or LIVE_DEFAULTS[name]


def _utc_in(minutes):
    t = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_live_token():
    """Asks Google for a short-lived Live API token. Returns (token, api_version). Raises with Google's own message."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("No Gemini API key saved. Put it in the room's API key box.")
    body = {"uses": 1, "expireTime": _utc_in(30), "newSessionExpireTime": _utc_in(2)}
    errors = []
    for version, url in AUTH_TOKEN_URLS:
        for payload in (body, {"authToken": body}):
            try:
                data = send_json(url, payload, {"Content-Type": "application/json", "x-goog-api-key": key}, 20)
                token = data.get("name") or (data.get("authToken") or {}).get("name")
                if token:
                    return token, version
                errors.append("%s: no token in answer" % version)
            except urllib.error.HTTPError as error:
                try:
                    detail = error.read().decode("utf-8", "replace")[:300]
                except Exception:
                    detail = ""
                errors.append("%s %s %s" % (version, error.code, detail))
                if error.code in (401, 403):        # wrong key: trying again will not help
                    raise ValueError("Google refused the Gemini key: " + detail)
    raise ValueError("Google did not give a live token. " + " | ".join(errors))


LIVE_RULES = """
YOU ARE IN A LIVE VOICE CALL RIGHT NOW. The person talks to you out loud and hears your voice.
- Answer fast and short, like real talk: usually one to three sentences. A longer bit only when they ask for a story or a real explanation.
- Start talking at once. Never begin with filler like "Well", "So", "Great question".
- Never say the same sentence twice, and never reuse an old joke (see the list of old lines below).
- If they talk over you, stop and answer the new thing.
- Never read emojis, stage directions, or words in brackets out loud.

YOUR BODY: you live in a 3D living room (sofa, coffee table with a glass, ball, TV, window, plant, floor lamp,
whiteboard, memory shelf). To move or change your face, call the tool room_action WHILE you talk:
- If your words say you will do something, call room_action so your body really does it.
- When your mood clearly changes, call room_action with just the emotion.
- Plain chat needs no tool call.

HARD QUESTIONS: for real facts, numbers, maths, code, news, or anything you are not sure about, first say a
very short in-character line (like "Hold on, let me actually think for once"), then call think_hard with the
question. When it answers, say the answer in your own voice and style, short. Never make up facts.
"""


def live_history_text(limit=12):
    lines = [message_text(m) for m in history[-limit:]]
    return ("\n\nTHE LAST THINGS YOU TWO SAID (word for word):\n" + "\n".join(lines)) if lines else ""


def live_system_text():
    persona = PERSONALITY.split("EMOTIONS:")[0]       # who she is + how she roasts (not the JSON reply format)
    return (persona.strip() + "\n" + LIVE_RULES + context_hint() + day_summary_text()
            + live_history_text() + said_hint())


def live_log(user_text, her_text):
    user_text = str(user_text or "").strip()[:2000]
    her_text = str(her_text or "").strip()[:4000]
    if not user_text and not her_text:
        return
    new = []
    if user_text:
        new.append({"role": "user", "content": user_text})
    if her_text:
        new.append({"role": "assistant", "content": json.dumps({"response": her_text, "emotion": "neutral",
                                                                   "animation": "idle", "actions": []})})
    history.extend(new)
    if len(history) > MAX_HISTORY_MESSAGES:
        del history[:-MAX_HISTORY_MESSAGES]
    save_day_memory(new)
    if her_text:
        remember_said(her_text)


THINK_SYSTEM = """You are the expert brain behind a sassy cartoon girl in a live voice chat.
She asks you a question the person asked her. Give her a correct answer she can say out loud:
two to five short sentences, plain words, no lists, no markdown, no code blocks (describe code in words),
no emojis. If you are not sure, say so plainly. Do not roast; she adds the attitude herself."""


def think_answer(question):
    """Hard questions from the live voice. Tries THINK_ORDER: OpenRouter (free models), Gemini (free-tier key),
    Venice, and Ollama only as the very last backup (it is slow). Skips any brain with no key. Returns (answer, who)."""
    question = str(question or "").strip()[:2000]
    if not question:
        raise ValueError("no question")
    user = ("Recent chat for context:\n" + "\n".join(message_text(m) for m in history[-6:])
            + "\n\nQuestion: " + question)
    msgs = [{"role": "system", "content": THINK_SYSTEM}, {"role": "user", "content": user}]
    tried = []
    for who in THINK_ORDER:
        try:
            if who == "openrouter":
                if not os.getenv("OPENROUTER_API_KEY"):
                    continue
                model = os.getenv("OPENROUTER_MODEL", "").strip() or OPENROUTER_MODELS[0]
                data = openrouter_send({"model": model, "messages": msgs, "max_tokens": 900}, 30)
                text = re.sub(r"<think>.*?</think>", "", data["choices"][0]["message"].get("content") or "", flags=re.S).strip()
            elif who == "gemini":
                if not os.getenv("GEMINI_API_KEY"):
                    continue
                model = os.getenv("GEMINI_MODEL", "").strip() or GEMINI_MODELS[0]
                data = send_json(GEMINI_URL % model, {"systemInstruction": {"parts": [{"text": THINK_SYSTEM}]},
                                                      "contents": [{"role": "user", "parts": [{"text": user}]}]},
                                 {"Content-Type": "application/json", "x-goog-api-key": os.getenv("GEMINI_API_KEY")}, 30)
                text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"] if not p.get("thought")).strip()
            elif who == "venice":
                if not os.getenv("VENICE_API_KEY"):
                    continue
                model = os.getenv("VENICE_MODEL", "").strip() or VENICE_MODELS[0]
                data = send_json(VENICE_URL, {"model": model, "messages": msgs, "max_tokens": 900,
                                              "venice_parameters": {"include_venice_system_prompt": False, "disable_thinking": True}},
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + os.getenv("VENICE_API_KEY")}, 30)
                text = re.sub(r"<think>.*?</think>", "", data["choices"][0]["message"].get("content") or "", flags=re.S).strip()
            else:
                model = OLLAMA_MODEL
                data = send_json(OLLAMA_URL, {"model": model, "stream": False, "think": False, "keep_alive": KEEP_ALIVE, "messages": msgs},
                                 {"Content-Type": "application/json"}, 120)
                text = (data.get("message") or {}).get("content", "").strip()
            if text:
                return text, "%s (%s)" % (who, model)
            tried.append(who + ": empty answer")
        except Exception as error:
            tried.append("%s: %s" % (who, error))
    raise ValueError("No brain could answer: " + " | ".join(tried))

load_settings()


# LIVE_CONTEXT_V1: the room sends what is happening right now with every message.
ROOM_NOW = {}


def context_hint():
    c = ROOM_NOW
    if not c:
        return ""
    keys = [("time", "local time"), ("day", "day"), ("doing", "what you are doing"), ("face", "your face"),
            ("energy", "your energy (0-100)"), ("mood", "your mood (0-100)"), ("annoyed", "how annoyed you are (0-100)"),
            ("minutes", "minutes they have been in the room"), ("messages", "messages they sent you this visit")]
    lines = ["- %s: %s" % (label, str(c[k])[:60]) for k, label in keys if c.get(k) not in (None, "")]
    return "\n\nROOM RIGHT NOW (use it for the roast, do not read it out like a list):\n" + "\n".join(lines) if lines else ""


# STORY_V1 + PRESENT_V2: her_story.txt = how she was built. She reads it when a message asks about it,
# and POST /present turns it (or any long text you paste) into a presentation show.
STORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "her_story.txt")
STORY_WORDS = re.compile(r"\b(built|build|made|make you|created?|creator|story|team|project|presentation|present|who are you|where (do|did) you come|how (were|was|did) you)\b", re.I)
CURRENT_TEXT = [""]


def read_story():
    try:
        with open(STORY_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def story_hint():
    if not STORY_WORDS.search(CURRENT_TEXT[0] or ""):
        return ""
    story = read_story()
    return ("\n\nYOUR OWN STORY (true facts about how you were built; use them, never make up other facts):\n" + story) if story else ""


SHOW_ACTIONS = ["idle", "wave", "talk", "walk", "walk_to_bed", "sit", "cross", "thumbs", "point_camera"]


def model_text(provider, system, user, max_tokens=4000):
    """One plain call to the chosen brain; returns its text. Used for writing presentation shows."""
    if provider == "venice":
        payload = {"model": os.getenv("VENICE_MODEL", "").strip() or VENICE_MODELS[0], "temperature": 0.9, "max_tokens": max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                   "response_format": {"type": "json_object"}, "venice_parameters": {"include_venice_system_prompt": False, "disable_thinking": True}}
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + (os.getenv("VENICE_API_KEY") or "")}
        try:
            data = send_json(VENICE_URL, payload, headers, 300)
        except urllib.error.HTTPError as error:
            if error.code != 400:
                raise
            payload.pop("response_format", None); payload.pop("venice_parameters", None)
            data = send_json(VENICE_URL, payload, headers, 300)
        return data["choices"][0]["message"].get("content") or ""
    if provider == "openrouter":
        payload = {"model": os.getenv("OPENROUTER_MODEL", "").strip() or OPENROUTER_MODELS[0], "temperature": 0.9, "max_tokens": max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                   "response_format": {"type": "json_object"}}
        data = openrouter_send(payload, 300)
        return re.sub(r"<think>.*?</think>", "", data["choices"][0]["message"].get("content") or "", flags=re.S).strip()
    if provider in ("gemini", "vertex"):
        key = os.getenv("VERTEX_API_KEY" if provider == "vertex" else "GEMINI_API_KEY") or ""
        url = (VERTEX_URL if provider == "vertex" else GEMINI_URL) % (os.getenv("GEMINI_MODEL", "").strip() or GEMINI_MODELS[0])
        payload = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}],
                   "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json", "thinkingConfig": {"thinkingLevel": "minimal"}}}
        headers = {"Content-Type": "application/json", "x-goog-api-key": key}
        try:
            data = send_json(url, payload, headers, 300)
        except urllib.error.HTTPError as error:
            if error.code != 400:
                raise
            payload["generationConfig"].pop("thinkingConfig", None)
            data = send_json(url, payload, headers, 300)
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"] if not p.get("thought"))
    if provider == "claude":
        data = send_json(CLAUDE_URL, {"model": CLAUDE_MODEL, "max_tokens": max_tokens, "system": system,
                                      "messages": [{"role": "user", "content": user}]},
                         {"Content-Type": "application/json", "x-api-key": os.getenv("ANTHROPIC_API_KEY") or "", "anthropic-version": "2023-06-01"}, 300)
        return "".join(b.get("text", "") for b in data.get("content", []))
    data = send_json(OLLAMA_URL, {"model": OLLAMA_MODEL, "stream": False, "think": False, "format": "json", "keep_alive": KEEP_ALIVE,
                                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                                  "options": {"temperature": 0.8, "num_ctx": 12288, "num_predict": max_tokens}}, {"Content-Type": "application/json"}, 300)
    return data["message"]["content"]


def make_show(source_text, provider, ask=""):
    """PRESENT_V2 + NO_LIMITS_V1: she writes her own presentation from her story, then performs it. No fixed script, no fixed length."""
    persona = PERSONALITY.split("EMOTIONS:")[0]          # who she is and how she roasts (not the chat reply format)
    system = (persona + "\n\nNOW YOU ARE ON STAGE in front of a class. Write YOUR OWN presentation about yourself, "
              "in the first person (I, me, my), from the true facts in the text below. Never invent numbers, names, tools or features. "
              "You decide how long it is, from the request. "
              "Split it into parts that are easy to say out loud. Tell it like a stand-up show: greet the room, tell where you came from, how your body, "
              "face, moves, voice and brain were built, the problems the team fixed, what changed most recently, what is still missing, "
              "and finish with a punchline and a goodbye. Roast the team and the audience along the way, but keep it fun, not mean. "
              "Return ONLY JSON: {\"lines\": [{\"action\": one of %s, \"mood\": one of %s, \"text\": \"...\"}]}" % (SHOW_ACTIONS, EMOTIONS))
    text = model_text(provider, system, ("The request: " + ask + "\n\n" if ask else "") + "These are the true facts about you:\n\n" + source_text, 16000)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    raw = data.get("lines")
    if not raw and isinstance(data.get("response"), str):     # the brain answered like a normal chat: cut it into parts
        sents = split_sentences(data["response"])
        raw = [{"text": " ".join(sents[i:i + 3])} for i in range(0, len(sents), 3)]
    lines = []
    for ln in (raw or []):
        t = str((ln or {}).get("text") or "").strip() if isinstance(ln, dict) else str(ln).strip()
        if not t:
            continue
        lines.append({"action": ln.get("action") if isinstance(ln, dict) and ln.get("action") in SHOW_ACTIONS else "talk",
                      "mood": ln.get("mood") if isinstance(ln, dict) and ln.get("mood") in EMOTIONS else "amused", "text": t, "pause": 0.5})
    if not lines:
        raise ValueError("The brain wrote no parts.")
    lines[0]["action"] = "wave"
    return {"about": "Written by her brain just now", "sayAs": {"AI World": "A I World", "Ai_World": "A I World", "Brain.py": "Brain dot pie", "API": "A P I", "GitHub": "Git Hub", "qwen3:4b": "Qwen 3, 4 B", "Hunyuan3D": "Hunyuan 3 D", "Mixamo": "Mix a mo", "BSU": "B S U"}, "lines": lines}


def get_provider_for_web(requested=None):

    if requested:
        return requested.lower()

    provider = os.getenv("BRAIN_PROVIDER", "ollama")
    return provider.lower()


class BrainHTTPHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        return

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError("Request body must be valid JSON.")

    def do_OPTIONS(self):
        self._send_json({"ok": True})

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/health"):
            self._send_json({"status": "ok", "brain": "Hugh Mann", "provider": os.getenv("BRAIN_PROVIDER", "ollama").lower()})
        elif path == "/settings":
            self._send_json(settings_view())
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/settings":            # API_KEY_V1: save key / brain choice from the room
            try:
                payload = self._read_json()
            except ValueError as error:
                self._send_json({"error": str(error)}, 400)
                return
            data = load_settings()
            if "api_key" in payload:
                data["anthropic_api_key"] = clean_key(payload.get("api_key"))
                if data["anthropic_api_key"]:
                    os.environ["ANTHROPIC_API_KEY"] = data["anthropic_api_key"]
                else:
                    os.environ.pop("ANTHROPIC_API_KEY", None)
            if "gemini_api_key" in payload:
                data["gemini_api_key"] = clean_key(payload.get("gemini_api_key"))
                if data["gemini_api_key"]:
                    os.environ["GEMINI_API_KEY"] = data["gemini_api_key"]
                else:
                    os.environ.pop("GEMINI_API_KEY", None)
            if payload.get("gemini_model"):
                data["gemini_model"] = str(payload["gemini_model"])
                os.environ["GEMINI_MODEL"] = data["gemini_model"]
            if "vertex_api_key" in payload:
                data["vertex_api_key"] = clean_key(payload.get("vertex_api_key"))
                if data["vertex_api_key"]:
                    os.environ["VERTEX_API_KEY"] = data["vertex_api_key"]
                else:
                    os.environ.pop("VERTEX_API_KEY", None)
            if "venice_api_key" in payload:
                data["venice_api_key"] = clean_key(payload.get("venice_api_key"))
                if data["venice_api_key"]:
                    os.environ["VENICE_API_KEY"] = data["venice_api_key"]
                else:
                    os.environ.pop("VENICE_API_KEY", None)
            if payload.get("venice_model"):
                data["venice_model"] = str(payload["venice_model"])
                os.environ["VENICE_MODEL"] = data["venice_model"]
            if "openrouter_api_key" in payload:
                data["openrouter_api_key"] = clean_key(payload.get("openrouter_api_key"))
                if data["openrouter_api_key"]:
                    os.environ["OPENROUTER_API_KEY"] = data["openrouter_api_key"]
                else:
                    os.environ.pop("OPENROUTER_API_KEY", None)
            if payload.get("openrouter_model"):
                data["openrouter_model"] = str(payload["openrouter_model"]).strip()
                os.environ["OPENROUTER_MODEL"] = data["openrouter_model"]
            for k, env in LIVE_SETTING_ENV.items():     # GEMINI_LIVE_V1: live engine, live model, voice, think model
                if payload.get(k):
                    data[k] = str(payload[k]).strip()
                    os.environ[env] = data[k]
            if payload.get("provider") in ("ollama", "claude", "gemini", "vertex", "venice", "openrouter"):
                data["provider"] = payload["provider"]
                os.environ["BRAIN_PROVIDER"] = payload["provider"]
            save_settings(data)
            self._send_json(settings_view())
            return
        if path in ("/live_token", "/live_log", "/think"):    # GEMINI_LIVE_V1
            try:
                payload = self._read_json()
            except ValueError as error:
                self._send_json({"error": str(error)}, 400)
                return
            try:
                if path == "/live_token":
                    ROOM_NOW.clear()
                    if isinstance(payload.get("context"), dict):
                        ROOM_NOW.update(payload["context"])
                    token, version = make_live_token()
                    print("Live chat: Gemini Live token made (%s, %s)." % (live_setting("live_model"), version))
                    self._send_json({"token": token, "api_version": version, "model": live_setting("live_model"),
                                     "voice": live_setting("live_voice"), "system": live_system_text(),
                                     "emotions": EMOTIONS, "actions": ROOM_ACTIONS})
                elif path == "/live_log":
                    live_log(payload.get("user"), payload.get("her"))
                    self._send_json({"ok": True})
                else:
                    answer, who = think_answer(payload.get("question"))
                    print("Live chat: hard question answered by %s." % who)
                    self._send_json({"answer": answer, "by": who})
            except Exception as error:
                print("Live chat %s failed: %s" % (path, error))
                self._send_json({"error": str(error)}, 500)
            return
        if path == "/present":            # STORY_V1: write a presentation show from her story or a pasted text
            try:
                payload = self._read_json()
            except ValueError as error:
                self._send_json({"error": str(error)}, 400)
                return
            source = str(payload.get("text") or "").strip()
            if len(source) < 200:
                source = read_story()
            if not source:
                self._send_json({"error": "her_story.txt is empty and no text was given"}, 400)
                return
            provider = get_provider_for_web(payload.get("provider"))
            show = None
            for p in ([provider, "ollama"] if provider != "ollama" else ["ollama"]):
                try:
                    show = make_show(source, p, str(payload.get("ask") or "")[:500])
                    print("Presentation written by %s: %d lines." % (p, len(show["lines"])))
                    break
                except Exception as error:
                    print("Presentation by %s failed: %s" % (p, error))
            if show is None:
                self._send_json({"error": "The brain could not write the presentation."}, 500)
                return
            self._send_json(show)
            return
        if path != "/brain":
            self._send_json({"error": "Not found"}, 404)
            return

        try:
            payload = self._read_json()
        except ValueError as error:
            self._send_json({"error": str(error)}, 400)
            return

        text = (
            payload.get("text")
            or payload.get("message")
            or payload.get("prompt")
            or ""
        )

        if not isinstance(text, str) or not text.strip():
            self._send_json({"error": "Missing text."}, 400)
            return

        provider = get_provider_for_web(payload.get("provider"))
        ROOM_NOW.clear()
        if isinstance(payload.get("context"), dict):
            ROOM_NOW.update(payload["context"])
        CURRENT_TEXT[0] = text
        reply = ask_brain(text, provider)

        if reply is None:
            self._send_json({
                "response": "The brain is not answering right now.",
                "emotion": "neutral",
                "animation": "idle"
            })
            return

        self._send_json({
            "response": reply["response"],
            "emotion": reply["emotion"],
            "animation": reply["animation"],
            "actions": reply.get("actions", [])
        })


def serve_brain(host="0.0.0.0", port=5005, provider=None):

    if provider:
        os.environ["BRAIN_PROVIDER"] = provider

    print(f"Hugh Mann brain server listening on http://{host}:{port}/brain")
    httpd = HTTPServer((host, port), BrainHTTPHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Hugh's brain server.")
    finally:
        httpd.server_close()


def main():

    print("======================================")
    print(" HUGH MANN: TOTALLY NORMAL HUMAN BRAIN")
    print("======================================")

    provider = choose_provider()

    print("\nCommands:")
    print("reset  - Clear conversation memory")
    print("switch - Change AI provider")
    print("exit   - End the program")

    while True:

        user_text = input("\nYou: ").strip()

        command = user_text.lower()

        if command == "exit":

            print(
                "Hugh Mann has left the building. Normally."
            )
            break

        if command == "reset":

            history.clear()

            print(
                "Conversation cleared. Hugh remembers nothing."
            )
            continue

        if command == "switch":

            # Switching models doesn't have to clear memory.
            # This also makes comparing answers easier.
            provider = choose_provider()

            print(
                "Now using:",
                provider
            )
            continue

        if not user_text:
            continue

        print("\nHugh is thinking...\n")

        reply = ask_brain(
            user_text,
            provider
        )

        if reply is None:

            print(
                "Try again or switch AI providers."
            )
            continue

        print(
            "Hugh Mann:",
            reply["response"]
        )

        print(
            "Emotion:",
            reply["emotion"]
        )

        print(
            "Animation:",
            reply["animation"]
        )

        print("\nJSON Output:")

        print(
            json.dumps(
                reply,
                indent=4
            )
        )


# Everything above defines how Hugh works.
# This is what actually starts the program in jGRASP.
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hugh Mann brain")
    parser.add_argument("--serve", action="store_true", help="Run the HTTP brain endpoint for the web app")
    parser.add_argument("--port", type=int, default=5005, help="Port for the brain web server")
    parser.add_argument("--provider", choices=["ollama", "claude"], default=None, help="Model provider for the web endpoint")
    args = parser.parse_args()

    if args.serve:
        serve_brain(port=args.port, provider=args.provider)
    else:
        main()
