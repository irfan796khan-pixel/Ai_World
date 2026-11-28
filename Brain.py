
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
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
    "explain",       # text: the topic; a short lesson on her smart TV (SMART_TV_V1: no more hologram)
    "tv_slide",      # text: "Title | point | point" -> a slide on the TV
    "tv_draw",       # text: what to draw ("a horse", "my head and body as two pieces") -> she draws it live on the TV
    "tv_picture",    # text: what to show ("the Eiffel Tower") -> a real photo on the TV (her shelf first, then Wikipedia)
    "sculpt",        # text: what to make ("a slice of pizza") -> a small 3D sculpture appears on the coffee table (SCULPT_V1)
    "phone_call",    # a fake phone call: she pretends someone important is calling (to dodge a boring question)
    "look_screen",   # look at his shared screen on the TV and react (SCREEN_SHARE_V1)
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
- Length (SHORT_PRECISE_V2): precise and short. Normally ONE or TWO short
  sentences, about 25 words or less in total. One roast, not three. Answer
  what was asked, then stop and let them talk. Go longer only when the person
  clearly asks for it (a story, an explanation, steps, a presentation), and
  even then no extra jokes stacked on top. Sentences easy to say out loud.
  Never pad with filler like "How's everything?".
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

YOUR ROOM AND BODY (ROOM_KNOWLEDGE_V1):
You live in a 3D living room and you have a real body. What is in the room, from where the camera stands:
a big SMART TV on the left wall, a sofa at the back, a coffee table with a glass on it in front of the sofa,
a ball on the floor, a window and a plant at the back left, a floor lamp in the back right corner,
a whiteboard on the back wall, and your memory shelf of books (the user's own pictures and notes) on the left.
YOUR SMART TV is your screen for showing and explaining. It can: show a slide (tv_slide, text "Title | point |
point"), DRAW anything live, stroke by stroke, like a whiteboard cartoon (tv_draw, text = what to draw: "a horse",
"a house", "my head and my body as two separate pieces"), show a real photo of something (tv_picture, text = what),
show a picture or note from your memory shelf (open_memory), show short words (tv_text), or turn on and off.
When something is easier to see than to hear (how a thing looks, how parts fit, steps), use the TV.
You can also SCULPT: a small 3D model of anything appears on your coffee table (sculpt, text = what). It is made
of simple shapes, so it often looks a bit silly: roast your own sculpting when it does.
He can share his computer screen onto your TV; when he asks, you look at it and comment (roast his code, his tabs).
You always know what your TV shows right now (ROOM RIGHT NOW, or a "(TV now shows: ...)" note). If they ask what is
on the TV or to explain it, describe it from that: what it is, the parts, where they are. Never say you cannot see it.
Only when they ask: do not start talking about the TV on your own.
When the person asks you to DO something you can do, do it: put the steps in
"actions", in order. If your words say you will do something, the actions must
do it too. You may still roast them while you do it. If they only chat, use an
empty list. You can only use these actions:
walk (target: sofa, window, plant, tv, table, ball, shelf, center, front),
kick (target: ball), sit (target: sofa, or miss), lamp_on, lamp_off, tv_on,
tv_off, tv_text (text), tv_slide (text), tv_draw (text), tv_picture (text),
write_board (text), knock_glass, point (target), wave, face_me, trip, clean_up,
explain (text: topic, a short lesson on the TV), open_memory (text),
sculpt (text: what to make; a small 3D sculpture appears on your coffee table), phone_call (a fake call),
look_screen (look at his shared screen on your TV and react).
Example: "draw me a horse" -> [{"do":"tv_draw","target":"","text":"a horse"}].
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
CHAT_LOCK = threading.RLock()   # BRAIN_THREADS_V1: chat requests that change her memory, one at a time
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
    # runs in the background (free OpenRouter). It waits until she has been
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
        # COUNCIL_V1: the summary runs on free OpenRouter in the cloud, not Ollama on this PC
        if not os.getenv("OPENROUTER_API_KEY"):
            raise ValueError("no OpenRouter key for the day summary")
        data = openrouter_send({
            "model": os.getenv("OPENROUTER_MODEL", "").strip() or OPENROUTER_MODELS[0],
            "messages": [{"role": "system", "content": "You keep a short, factual memory summary of a chat."},
                         {"role": "user", "content": prompt}],
            "temperature": 0.2, "max_tokens": 600
        }, 60)
        text = re.sub(r"<think>.*?</think>", "", data["choices"][0]["message"].get("content") or "", flags=re.S).strip()
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


def ask_openrouter(user_text, reminder=None, model=None):
    model = model or os.getenv("OPENROUTER_MODEL", "").strip() or OPENROUTER_MODELS[0]
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


# COUNCIL_V1 (Imran, 27 Nov): AI Council Chat on this laptop (http://127.0.0.1:8765) is her main brain.
#   It runs Gemini or Claude on Imran's own subscriptions (no API bill), or DeepSeek / Grok free on OpenRouter.
#   FAST talking brain = council_fast (default gemini). Hard questions (/think) = council_smart (default claude).
#   If AI Council Chat is closed, she uses free OpenRouter. No Ollama: nothing heavy runs on this PC.
COUNCIL_URL = "http://127.0.0.1:8765/api/chat"
COUNCIL_STREAM_URL = "http://127.0.0.1:8765/api/chat_stream"   # COUNCIL_STREAM_V1: AI Council Chat keeps Claude / Gemini open and streams
COUNCIL_MODES = ["gemini"]   # GEMINI_ONLY_V1 (Imran, 27 Nov): only Gemini, no Claude
COUNCIL_DATA = os.path.join(os.path.expanduser("~"), "Documents", "ai-council", "app-data")


def council_key():
    try:
        with open(os.path.join(COUNCIL_DATA, "api_key.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


# FAST_TALK_V1 (Imran, 27 Nov: "make it faster"): the fast brain does not go through AI Council Chat when it
# does not have to. Gemini streams straight from Google with the saved Gemini key; DeepSeek / Grok stream straight
# from OpenRouter. Only Claude (no other way on his plan) and the smart brain use AI Council Chat.
FAST_OR_MODELS = {"deepseek": "deepseek/deepseek-chat-v3:free", "grok": "x-ai/grok-4.1-fast:free"}


def fast_direct():
    """The brain that answers chat directly (streaming), or None if the fast brain must use AI Council Chat."""
    mode = council_mode("fast")
    if mode == "gemini" and os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if mode in FAST_OR_MODELS and os.getenv("OPENROUTER_API_KEY"):
        return mode
    return None


def council_mode(kind="fast"):
    default = "gemini"                          # GEMINI_ONLY_V1: fast and smart are both Gemini
    mode = os.getenv("COUNCIL_FAST" if kind == "fast" else "COUNCIL_SMART", "").strip().lower() or default
    return mode if mode in COUNCIL_MODES else default


def council_text(prompt, kind="fast", timeout=300, mode=None):
    key = council_key()
    if not key:
        raise ValueError("AI Council Chat isn't configured on this PC (no api_key.txt).")
    data = send_json(COUNCIL_URL, {"project": "Ai_World", "mode": mode or council_mode(kind), "message": prompt},
                     {"Content-Type": "application/json", "X-API-Key": key}, timeout)
    if data.get("error"):
        raise ValueError("AI Council Chat: " + str(data["error"]))
    return re.sub(r"<think>.*?</think>", "", data["replies"][-1].get("text") or "", flags=re.S).strip()


def ask_council(user_text, reminder=None):
    system = (PERSONALITY + day_summary_text() + said_hint() + context_hint() + story_hint()
              + "\n\nReturn ONLY one JSON object with the keys response, emotion, animation, actions. No other text.")
    lines = [message_text(m) for m in messages_for(user_text, reminder)]
    text = council_text(system + "\n\nCHAT SO FAR (the last line is the new message):\n" + "\n".join(lines), "fast")
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
    reply = _ask_brain(user_text, provider, 2 if provider in ("council", "gemini", "vertex", "venice", "openrouter", "claude") else MAX_ATTEMPTS)
    backup = "openrouter" if provider != "openrouter" else None   # COUNCIL_V1: free OpenRouter backup, never Ollama (slow PC)
    if reply is None and backup and CLOUD_FAIL[0] and os.getenv("OPENROUTER_API_KEY"):
        print("%s could not answer (%s). Using free OpenRouter for this reply." % (provider, CLOUD_FAIL[0]))
        reply = _ask_brain(user_text, backup, 2)
    return reply


def _ask_brain(user_text, provider, max_attempts):

    reminder = None
    best = [None, 99]          # NEVER_SILENT_V1: the try with the fewest old lines

    for attempt in range(max_attempts):

        try:

            # We use the selected provider, but everything after
            # this point works exactly the same for either model.
            if provider == "council":
                direct = fast_direct()               # FAST_TALK_V1
                if direct == "gemini":
                    reply = ask_gemini(user_text, reminder)
                elif direct in FAST_OR_MODELS:
                    reply = ask_openrouter(user_text, reminder, FAST_OR_MODELS[direct])
                else:
                    reply = ask_council(user_text, reminder)
            elif provider == "claude":
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
    if data.get("council_fast"):
        os.environ["COUNCIL_FAST"] = data["council_fast"]
    if data.get("council_smart"):
        os.environ["COUNCIL_SMART"] = data["council_smart"]
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
        "provider": get_provider_for_web(),
        "council_fast": council_mode("fast"),          # COUNCIL_V1
        "council_smart": council_mode("smart"),
        "council_modes": COUNCIL_MODES,
        "council_ready": bool(council_key()),
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
THINK_ORDER = ["gemini", "council", "openrouter"]   # GEMINI_ONLY_V1: Gemini key first (fastest), then Gemini through AI Council Chat, then free OpenRouter. Was: council first   # COUNCIL_V1 (Imran, 27 Nov): hard questions go to the smart council brain (Claude by default), free OpenRouter if it is closed
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
- SHORT_PRECISE_V2: precise and short, like real talk. Normally ONE or TWO short sentences, about 25 words or less. One roast, not three. Answer what was asked, then stop and let them talk. Go longer only when they clearly ask (a story, an explanation, steps, a presentation). No rambling.
- Start talking at once. Never begin with filler like "Well", "So", "Great question".
- Never say the same sentence twice, and never reuse an old joke (see the list of old lines below).
- If they talk over you, or say "stop", "no", "wait" or "listen", stop at once and listen. Do not finish your sentence.
- Never read emojis, stage directions, or words in brackets out loud.

YOUR BODY: you live in a 3D living room (big smart TV on the left wall, sofa, coffee table with a glass, ball, window,
plant, floor lamp, whiteboard, memory shelf). To move or change your face, call the tool room_action WHILE you talk:
- If your words say you will do something, call room_action so your body really does it.
- HONEST_ACTIONS_V1: never say you did something (walked, turned the lamp or TV on or off, opened a picture)
  until room_action answers with done. It tells you what really happened. If it says it failed, say so.
- Lamp: room_action with do lamp_on or lamp_off (you walk to the lamp yourself). TV: tv_on, tv_off, or tv_text.
  Pictures or notes from your memory shelf: open_memory with the words in text, one call per picture.
- TV_AWARE_V1: notes like "(TV now shows: ...)" tell you what is on your TV. Do not answer a note by itself; use it when
  they ask what is on the TV or to explain it: describe what it is, the parts and where they are.
- SCULPT_V1: sculpt (text = what) makes a small 3D model on your coffee table; phone_call = a fake phone call to dodge
  a boring question (use it rarely, for a laugh).
- YOUR SMART TV (SMART_TV_V1): tv_draw draws ANYTHING live on the TV (text = what to draw, e.g. "a horse"),
  tv_picture shows a real photo of something (text = what), tv_slide shows a slide (text "Title | point | point"),
  explain gives a short lesson on the TV (text = topic). When he says "draw ..." or "show me a picture of ...", use them.
- When your mood clearly changes, call room_action with just the emotion.
- Plain chat needs no tool call.

HARD QUESTIONS: for real facts, numbers, maths, code, news, or anything you are not sure about, first say a
very short in-character line (like "Hold on, let me actually think for once"), then call think_hard with the
question. When it answers, say the answer in your own voice and style, short. Never make up facts.
"""


# HER_SKILLS_V1: one list of everything she can really do. It goes into her chat rules AND her live-call rules,
# so she knows her own skills everywhere and can tell people when they ask "what can you do?".
SKILLS_TEXT = """
YOUR SKILLS (HER_SKILLS_V1) - everything you can really do, and nothing more:
- Talk live by voice and keep listening while you talk. If he talks over you: important = stop and answer, then go
  back to what you were saying; not urgent = say you will come back to it, finish, then answer; "stop" = stop.
- Move in your room: walk (sofa, window, plant, TV, table, ball, shelf, center, front), sit on the sofa, kick the ball,
  wave, point at things, knock the glass off the table, trip, clean up. Turn the floor lamp and the TV on and off.
- Your SMART TV: draw anything live, stroke by stroke ("draw a horse"); show a real photo of anything ("show me a picture
  of the Eiffel Tower"); show slides and simple graphs; give a short lesson with drawings ("explain how rainbows work").
  You always know what is on the TV.
- SCULPT: make a small 3D model of anything on your coffee table ("sculpt a slice of pizza"); "clear the table" removes it.
- SCREEN SHARE: when he clicks the Share screen button, his screen (code, tabs, homework) shows on your TV; when he asks,
  you look at it and roast it.
- FAKE PHONE CALL: pretend someone important is calling (for a laugh, or to dodge a boring question).
- MEMORY SHELF: his own pictures and notes; you pull one out and show it on the TV ("show me my picture of ...").
- ROOM BUILDER: drop simple objects into the room ("spawn a red box on the table").
- PRESENTATION: when asked to present yourself, you invent a new presentation about how you were built, in a new style
  every time, with drawings and photos on the TV.
- BIG BRAIN: hard facts, maths, code and news go to your bigger brain, then you say the answer your way.
- MEMORY: you remember today's chat and never repeat your old jokes.
- YOUR OWN MIND: energy, mood and annoyance of your own; boss you around too much and you rebel.
- He can film you: a cinematic camera that keeps changing angles, and a 15-second clip recorder for TikTok.
If someone asks what you can do: name 3 to 5 of these in a fun, short way and offer to show one right now.
Never claim a skill that is not on this list (you cannot fly, browse websites by yourself, change your clothes,
or see the real room through a camera).
"""
PERSONALITY = PERSONALITY.replace("\nOUTPUT:", "\n" + SKILLS_TEXT + "\nOUTPUT:", 1)
LIVE_RULES = LIVE_RULES + SKILLS_TEXT

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
one to three short sentences (only what she needs to say), plain words, no lists, no markdown, no code blocks (describe code in words),
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
            if who == "council":
                if not council_key():
                    continue
                model = council_mode("smart")
                text = council_text(THINK_SYSTEM + "\n\n" + user, "smart", 120)
            elif who == "openrouter":
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

# ============================================================================
# SMART_TV_V1: her TV can draw anything and show real photos.
#   POST /draw {"what": "a horse"} -> {"svg": "<svg ...>"}  simple cartoon drawing; the page draws it stroke by stroke.
#       Made by Gemini first, then OpenRouter, then Venice (no Claude). Kept in brain_memory/drawings/ (same word = instant).
#   GET /picture?q=eiffel tower -> the photo of the best Wikipedia page for those words (kept in brain_memory/pictures/).
# ============================================================================
DRAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain_memory", "drawings")
PIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain_memory", "pictures")
DRAW_SYSTEM = """You draw for a live TV in a cartoon room. Make ONE clear, friendly cartoon drawing, like a good whiteboard
sketch that a 12 year old understands at once. Return ONLY the SVG, nothing else.
Rules:
- <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"> ... </svg>
- The FIRST thing inside the svg is <desc>one or two short sentences: what is drawn and where things are
  (left, middle, right, top, bottom), so someone who cannot see it can explain it</desc>
- Use ONLY these elements: path, circle, ellipse, rect, line, polyline, polygon. No text, no g, no transform,
  no gradients, no style element, no images, no defs. Each element has its own stroke, stroke-width and fill attributes.
- 12 to 60 elements. Big shapes first (body, ground, walls), then the details (eyes, windows, labels as arrows).
- Outlines: stroke="#1f2937" stroke-width="3" (thinner for small details). Flat, bright, simple fill colors (hex).
- Fill most of the 400 x 300 area, centered. Make it recognizable: the right number of legs, ears, wheels and so on.
- For a diagram (how parts fit), draw the parts apart with arrows (lines with small triangles) between them.
- For a graph or chart: two axes, then bars, a line or pie slices in bright colors; no words, so show the idea with
  sizes, colors and simple icons (a small heart, a bug, a person)."""
SVG_TAGS = ("path", "circle", "ellipse", "rect", "line", "polyline", "polygon")


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:60] or "x"


def clean_svg(text):
    """Keeps only the allowed drawing elements and their plain attributes. (The page only ever turns them into
    canvas paths, never into live page content, so nothing in a drawing can run.)"""
    text = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.S)
    m = re.search(r"<svg[\s\S]*?</svg>", text, re.I)
    if not m:
        raise ValueError("no <svg> in the answer")
    body = m.group(0)
    vb = re.search(r'viewBox\s*=\s*"([\d.\s\-]+)"', body)
    out = []
    for el in re.finditer(r"<(%s)\b([^>]*?)/?>" % "|".join(SVG_TAGS), body, re.I):
        attrs = re.findall(r'([a-zA-Z][a-zA-Z0-9\-]*)\s*=\s*"([^"]*)"', el.group(2))
        keep = []
        for k, v in attrs:
            k = k.lower()
            if k.startswith("on") or "href" in k or "url(" in v.lower() or "javascript" in v.lower():
                continue
            if k in ("d", "cx", "cy", "r", "rx", "ry", "x", "y", "width", "height", "x1", "y1", "x2", "y2", "points",
                     "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "opacity", "fill-opacity", "style"):
                keep.append('%s="%s"' % (k, v.replace("<", "").replace(">", "")))
        out.append("<%s %s/>" % (el.group(1).lower(), " ".join(keep)))
    if len(out) < 3:
        raise ValueError("drawing too empty")
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%s">%s</svg>' % (vb.group(1) if vb else "0 0 400 300", "".join(out[:120]))


def drawing_desc(text):
    """TV_AWARE_V1: the drawing's own <desc>, so she can explain what is on her TV."""
    m = re.search(r"<desc>([\s\S]*?)</desc>", str(text or ""), re.I)
    return re.sub(r"<[^>]*>", "", m.group(1)).strip()[:300] if m else ""


def make_drawing(what):
    what = str(what or "").strip()[:200]
    if not what:
        raise ValueError("nothing to draw")
    path = os.path.join(DRAW_DIR, _slug(what) + ".svg")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            svg = f.read()
        desc = ""
        if os.path.exists(path[:-4] + ".txt"):
            with open(path[:-4] + ".txt", encoding="utf-8") as f:
                desc = f.read().strip()
        return svg, "saved drawing", desc
    user = "Draw: " + what
    tried = []
    # TV_CLAUDE_CHEAP_V1 (Imran, 27 Nov): the TV is drawn by the council with Claude's cheapest model (Haiku,
    # on his Claude plan, no API bill). If AI Council Chat is closed, Gemini / OpenRouter / Venice draw it.
    for who in ("council", "gemini", "openrouter", "venice"):
        try:
            if who == "council":
                if not council_key():
                    continue
                text = council_text(DRAW_SYSTEM + "\n\n" + user, timeout=150, mode="claude_cheap")
                who = "council (Claude Haiku)"
            elif who == "gemini":
                if not os.getenv("GEMINI_API_KEY"):
                    continue
                models = [m for m in [os.getenv("GEMINI_MODEL", "").strip()] + GEMINI_MODELS[::-1] if m]   # the bigger flash first
                text, err = "", None
                for model in dict.fromkeys(models):
                    try:
                        payload = {"systemInstruction": {"parts": [{"text": DRAW_SYSTEM}]}, "contents": [{"role": "user", "parts": [{"text": user}]}],
                                   "generationConfig": {"temperature": 0.7, "thinkingConfig": {"thinkingLevel": "low"}}}
                        headers = {"Content-Type": "application/json", "x-goog-api-key": os.getenv("GEMINI_API_KEY")}
                        try:
                            data = send_json(GEMINI_URL % model, payload, headers, 60)
                        except urllib.error.HTTPError as error:
                            if error.code != 400:
                                raise
                            payload["generationConfig"].pop("thinkingConfig", None)
                            data = send_json(GEMINI_URL % model, payload, headers, 60)
                        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"] if not p.get("thought"))
                        who = "gemini (%s)" % model
                        break
                    except Exception as e:
                        err = e
                if not text:
                    raise err or ValueError("empty")
            elif who == "openrouter":
                if not os.getenv("OPENROUTER_API_KEY"):
                    continue
                data = openrouter_send({"model": os.getenv("OPENROUTER_MODEL", "").strip() or OPENROUTER_MODELS[0], "max_tokens": 6000,
                                        "messages": [{"role": "system", "content": DRAW_SYSTEM}, {"role": "user", "content": user}]}, 90)
                text = data["choices"][0]["message"].get("content") or ""
            else:
                if not os.getenv("VENICE_API_KEY"):
                    continue
                data = send_json(VENICE_URL, {"model": os.getenv("VENICE_MODEL", "").strip() or VENICE_MODELS[0], "max_tokens": 6000,
                                              "messages": [{"role": "system", "content": DRAW_SYSTEM}, {"role": "user", "content": user}],
                                              "venice_parameters": {"include_venice_system_prompt": False, "disable_thinking": True}},
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + os.getenv("VENICE_API_KEY")}, 90)
                text = data["choices"][0]["message"].get("content") or ""
            svg, desc = clean_svg(text), drawing_desc(text)
            os.makedirs(DRAW_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg)
            with open(path[:-4] + ".txt", "w", encoding="utf-8") as f:
                f.write(desc)
            return svg, who, desc
        except Exception as error:
            tried.append("%s: %s" % (who, error))
    raise ValueError("No brain could draw it: " + " | ".join(tried))


# SCULPT_V1: a small 3D model of anything, made ONLY of simple shapes described as data (never code the page runs).
SCULPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain_memory", "sculptures")
SCULPT_SHAPES = ("box", "sphere", "cylinder", "cone", "torus", "capsule")
SCULPT_SYSTEM = """You build small 3D cartoon models out of simple shapes, for a 3D room. Return ONLY JSON:
{"name": "short name", "desc": "one sentence: what it looks like", "parts": [
  {"shape": "box|sphere|cylinder|cone|torus|capsule", "size": [width, height, depth], "pos": [x, y, z],
   "rot": [x_degrees, y_degrees, z_degrees], "color": "#rrggbb"} ]}
Rules: units are meters-ish, the whole model about 1 unit tall, standing on y = 0 (bottom at 0), centered on x = 0, z = 0.
Every shape is a unit shape stretched by size: box 1x1x1, sphere diameter 1, cylinder and cone diameter 1 height 1
(standing up), torus a ring of diameter 1 lying flat, capsule diameter 1 height 1. 6 to 40 parts. Bright cartoon colors.
Make it recognizable: the right number of legs, ears, wheels, toppings. Eyes are small dark spheres."""


def _num(v, d=0.0):
    try:
        v = float(v)
        return v if v == v and abs(v) < 100 else d
    except Exception:
        return d


def clean_sculpture(text):
    text = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.S)
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    parts = []
    for p in (data.get("parts") or [])[:60]:
        if not isinstance(p, dict) or p.get("shape") not in SCULPT_SHAPES:
            continue
        size = [max(0.005, abs(_num(x, 0.1))) for x in (list(p.get("size") or [])[:3] + [0.1, 0.1, 0.1])[:3]]
        pos = [_num(x) for x in (list(p.get("pos") or [])[:3] + [0, 0, 0])[:3]]
        rot = [_num(x) for x in (list(p.get("rot") or [])[:3] + [0, 0, 0])[:3]]
        color = str(p.get("color") or "#cccccc")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            color = "#cccccc"
        parts.append({"shape": p["shape"], "size": size, "pos": pos, "rot": rot, "color": color})
    if len(parts) < 2:
        raise ValueError("sculpture too empty")
    return {"name": str(data.get("name") or "")[:60], "desc": str(data.get("desc") or "")[:300], "parts": parts}


def make_sculpture(what):
    what = str(what or "").strip()[:160]
    if not what:
        raise ValueError("nothing to sculpt")
    path = os.path.join(SCULPT_DIR, _slug(what) + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f), "saved sculpture"
    tried = []
    for who in ("gemini", "openrouter"):
        try:
            if who == "gemini":
                if not os.getenv("GEMINI_API_KEY"):
                    continue
                text, err = "", None
                for model in dict.fromkeys(m for m in [os.getenv("GEMINI_MODEL", "").strip()] + GEMINI_MODELS[::-1] if m):
                    try:
                        payload = {"systemInstruction": {"parts": [{"text": SCULPT_SYSTEM}]}, "contents": [{"role": "user", "parts": [{"text": "Build: " + what}]}],
                                   "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json", "thinkingConfig": {"thinkingLevel": "low"}}}
                        headers = {"Content-Type": "application/json", "x-goog-api-key": os.getenv("GEMINI_API_KEY")}
                        try:
                            data = send_json(GEMINI_URL % model, payload, headers, 60)
                        except urllib.error.HTTPError as error:
                            if error.code != 400:
                                raise
                            payload["generationConfig"].pop("thinkingConfig", None)
                            data = send_json(GEMINI_URL % model, payload, headers, 60)
                        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"] if not p.get("thought"))
                        who = "gemini (%s)" % model
                        break
                    except Exception as e:
                        err = e
                if not text:
                    raise err or ValueError("empty")
            else:
                if not os.getenv("OPENROUTER_API_KEY"):
                    continue
                data = openrouter_send({"model": os.getenv("OPENROUTER_MODEL", "").strip() or OPENROUTER_MODELS[0], "max_tokens": 4000,
                                        "response_format": {"type": "json_object"},
                                        "messages": [{"role": "system", "content": SCULPT_SYSTEM}, {"role": "user", "content": "Build: " + what}]}, 90)
                text = data["choices"][0]["message"].get("content") or ""
            sc = clean_sculpture(text)
            os.makedirs(SCULPT_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sc, f)
            return sc, who
        except Exception as error:
            tried.append("%s: %s" % (who, error))
    raise ValueError("No brain could sculpt it: " + " | ".join(tried))


# SCREEN_SHARE_V1: she looks at a frame of his shared screen (Gemini vision) and comments on it.
LOOK_SYSTEM = """You are a sassy cartoon woman in a 3D room. The person shared their computer screen onto your TV and you are
looking at it now. Say what you see and roast it in a fun way (messy code, too many tabs, the shopping cart, the grades),
in one to three short spoken sentences. Be specific about what is really on the screen. Never read long text out loud.
No lists, no markdown, no emojis."""


def look_at_screen(image_data_url, ask=""):
    m = re.match(r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$", str(image_data_url or ""))
    if not m:
        raise ValueError("no screen picture")
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("looking needs the Gemini key (API key box)")
    user = (("He asks: " + str(ask)[:300] + "\n") if ask else "") + "What do you see on his screen? React to it."
    tried = []
    for model in dict.fromkeys(mm for mm in [os.getenv("GEMINI_MODEL", "").strip()] + GEMINI_MODELS if mm):
        try:
            payload = {"systemInstruction": {"parts": [{"text": LOOK_SYSTEM}]},
                       "contents": [{"role": "user", "parts": [{"inlineData": {"mimeType": m.group(1), "data": m.group(2)}}, {"text": user}]}],
                       "generationConfig": {"temperature": 0.9}}
            data = send_json(GEMINI_URL % model, payload, {"Content-Type": "application/json", "x-goog-api-key": os.getenv("GEMINI_API_KEY")}, 40)
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"] if not p.get("thought")).strip()
            if text:
                return text, model
        except Exception as e:
            tried.append("%s: %s" % (model, e))
    raise ValueError("could not look: " + " | ".join(tried))


WIKI_HEADERS = {"User-Agent": "AIWorld/1.0 (class project, Bridgewater State University)", "Accept": "application/json"}


def get_picture(query):
    """Returns (bytes, content type, page title). Wikipedia search -> that page's main photo."""
    query = str(query or "").strip()[:120]
    if not query:
        raise ValueError("no picture words")
    os.makedirs(PIC_DIR, exist_ok=True)
    base = os.path.join(PIC_DIR, _slug(query))
    for ext, ctype in ((".jpg", "image/jpeg"), (".png", "image/png"), (".webp", "image/webp"), (".gif", "image/gif")):
        if os.path.exists(base + ext):
            with open(base + ext, "rb") as f:
                return f.read(), ctype, query
    q = urllib.parse.quote(query)
    pages, err = [], None
    for url in ("https://en.wikipedia.org/w/rest.php/v1/search/page?q=%s&limit=5" % q,
                "https://api.wikimedia.org/core/v1/wikipedia/en/search/page?q=%s&limit=5" % q):   # the same search, two addresses
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=WIKI_HEADERS), timeout=15) as r:
                pages = json.loads(r.read().decode("utf-8")).get("pages") or []
            break
        except Exception as e:
            err = e
    if not pages and err:
        raise err
    for page in pages:
        key = page.get("key")
        if not key:
            continue
        with urllib.request.urlopen(urllib.request.Request("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(key, safe=""),
                                                           headers=WIKI_HEADERS), timeout=15) as r:
            summary = json.loads(r.read().decode("utf-8"))
        img = (summary.get("originalimage") or {}).get("source") or (summary.get("thumbnail") or {}).get("source")
        if not img or img.lower().endswith(".svg"):
            continue
        if summary.get("thumbnail") and (summary.get("originalimage") or {}).get("width", 0) > 1600:
            img = summary["thumbnail"]["source"]          # big originals are slow: the smaller copy
        with urllib.request.urlopen(urllib.request.Request(img, headers={"User-Agent": WIKI_HEADERS["User-Agent"]}), timeout=20) as r:
            data, ctype = r.read(), r.headers.get("Content-Type", "image/jpeg").split(";")[0]
        ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(ctype, ".jpg")
        with open(base + ext, "wb") as f:
            f.write(data)
        return data, ctype, summary.get("title") or query
    raise ValueError("no photo found for " + query)


# TURN_JUDGE_V1: he talks while she is still talking (a long answer or her presentation).
# A fast AI decides what she does with it, like a person would:
#   now    - answer it right away (a real question, a correction, something urgent, something about what she is saying)
#   later  - worth answering, but it can wait until she finishes her thought or presentation
#   ignore - not meant for her: "yeah", "ok", "haha", talking to someone else, noise, her own echo
#   stop   - he wants her to stop talking
JUDGE_SYSTEM = """You decide, in a live voice talk, what an AI girl should do when the person speaks while she is still talking.
Reply with ONLY one JSON object: {"do": "now" | "later" | "ignore" | "stop", "why": "a few words"}.
- now: a real question, a correction ("that is wrong"), something urgent, he asks her to do something, or it is about what she is saying right now.
- later: worth answering, but not urgent; it can wait until she finishes her point.
- ignore: listening sounds ("yeah", "ok", "mm", "haha", "nice"), laughing, talking to someone else in the room, noise, or words that repeat what she just said (her own echo).
- stop: he wants her to stop or be quiet.
If you are not sure between now and later, pick now. A presentation is less urgent than a chat: pick later more often then."""
JUDGE_ORDER = ["gemini", "openrouter"]     # fastest first; no Claude (Imran, 12 Nov)


def judge_turn(heard, her="", show=False):
    """Returns ({"do":..., "why":...}, who). Raises when no brain could answer (the page then uses its own rules)."""
    heard = str(heard or "").strip()[:500]
    if not heard:
        return {"do": "ignore", "why": "nothing heard"}, "rules"
    user = ("She is %s. What she is saying right now: \"%s\"\nWhat the person just said: \"%s\""
            % ("giving a presentation" if show else "talking (a chat answer)", str(her or "")[:400], heard))
    tried = []
    for who in JUDGE_ORDER:
        try:
            if who == "gemini":
                if not os.getenv("GEMINI_API_KEY"):
                    continue
                model = GEMINI_MODELS[0]
                payload = {"systemInstruction": {"parts": [{"text": JUDGE_SYSTEM}]},
                           "contents": [{"role": "user", "parts": [{"text": user}]}],
                           "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                                "thinkingConfig": {"thinkingLevel": "minimal"}}}
                headers = {"Content-Type": "application/json", "x-goog-api-key": os.getenv("GEMINI_API_KEY")}
                try:
                    data = send_json(GEMINI_URL % model, payload, headers, 4)
                except urllib.error.HTTPError as error:
                    if error.code != 400:
                        raise
                    payload["generationConfig"].pop("thinkingConfig", None)
                    data = send_json(GEMINI_URL % model, payload, headers, 4)
                text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"] if not p.get("thought"))
            else:
                if not os.getenv("OPENROUTER_API_KEY"):
                    continue
                model = os.getenv("OPENROUTER_MODEL", "").strip() or OPENROUTER_MODELS[0]
                data = openrouter_send({"model": model, "max_tokens": 60, "temperature": 0, "response_format": {"type": "json_object"},
                                        "messages": [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]}, 5)
                text = data["choices"][0]["message"].get("content") or ""
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
            j = json.loads(text[text.find("{"): text.rfind("}") + 1])
            if j.get("do") in ("now", "later", "ignore", "stop"):
                return {"do": j["do"], "why": str(j.get("why", ""))[:120]}, "%s (%s)" % (who, model)
            tried.append(who + ": bad answer")
        except Exception as error:
            tried.append("%s: %s" % (who, error))
    raise ValueError("no judge: " + " | ".join(tried))


load_settings()


# LIVE_CONTEXT_V1: the room sends what is happening right now with every message.
ROOM_NOW = {}


def context_hint():
    c = ROOM_NOW
    if not c:
        return ""
    keys = [("time", "local time"), ("day", "day"), ("doing", "what you are doing"), ("face", "your face"),
            ("energy", "your energy (0-100)"), ("mood", "your mood (0-100)"), ("annoyed", "how annoyed you are (0-100)"),
            ("minutes", "minutes they have been in the room"), ("messages", "messages they sent you this visit"),
            ("tv", "what your TV shows right now (you put it there; explain it if asked)"),
            ("table", "what is on your coffee table"), ("screen", "his screen share")]
    lines = ["- %s: %s" % (label, str(c[k])[:60 if k != "tv" else 400]) for k, label in keys if c.get(k) not in (None, "")]
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
PRESENT_ACTIONS = ["idle", "wave", "talk", "cross", "thumbs", "point_camera"]   # PRESENT_STAY_V1: no "walk" (she walked back and forth mid-talk)   # SHOW_STEP_V1: her own presentations stay standing (no sofa in the middle of the talk)


def model_text(provider, system, user, max_tokens=4000):
    """One plain call to the chosen brain; returns its text. Used for writing presentation shows."""
    if provider == "council":
        return council_text(system + "\n\n" + user + "\n\nReturn ONLY the JSON object.", "smart", 300)
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


# INVENT_SHOW_V1: every presentation is invented fresh. A random format and opening are picked, the last
# presentations are shown to the brain as "do not repeat", and each part can put something on her smart TV.
SHOW_FORMATS = [
    "a nature documentary about yourself, narrated like a wildlife film", "a courtroom trial where the team is on trial for building you",
    "a cooking show: the recipe for building a cartoon girl", "a breaking-news broadcast from AI World", "a museum tour of your own body",
    "a villain origin story", "a science fair project you are judging yourself", "a reality TV confession booth",
    "a sports commentary of your own build, play by play", "a fairy tale", "a heist movie: how the team stole a body and a brain",
    "a talk show where you interview yourself", "a home renovation show about your own face", "a spy mission briefing",
    "an awards show where you hand out awards to every bug the team fixed", "a horror story about the early versions of you",
    "a product launch keynote for yourself", "a game show where the class guesses how you were built",
]
SHOW_OPENINGS = ["start with a question to the room", "start in the middle of the action", "start with a fake-serious warning",
                 "start with a confession", "start by roasting the person who asked", "start with a countdown", "start with a weird fact about yourself"]
SHOWS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain_memory", "presentations.json")


def old_shows():
    try:
        with open(SHOWS_FILE, encoding="utf-8") as f:
            return json.load(f)[-6:]
    except Exception:
        return []


def remember_show(fmt, lines):
    try:
        shows = old_shows() + [{"format": fmt, "first": [l["text"][:160] for l in lines[:3]],
                                "tv": [str(l.get("tv"))[:80] for l in lines if l.get("tv")][:8]}]
        os.makedirs(os.path.dirname(SHOWS_FILE), exist_ok=True)
        with open(SHOWS_FILE, "w", encoding="utf-8") as f:
            json.dump(shows[-12:], f, indent=1)
    except Exception as e:
        print("could not save the presentation list:", e)


def clean_tv(tv, shelf):
    """One TV part: {"slide": {"title", "points"}} | {"draw": "..."} | {"picture": "..."} | {"shelf": "title"}."""
    if not isinstance(tv, dict):
        return None
    if isinstance(tv.get("slide"), dict):
        sl = tv["slide"]
        pts = [str(x)[:80] for x in (sl.get("points") or []) if str(x).strip()][:5]
        return {"slide": {"title": str(sl.get("title") or "")[:60], "points": pts}}
    for k in ("draw", "picture"):
        if str(tv.get(k) or "").strip():
            return {k: str(tv[k]).strip()[:160]}
    if str(tv.get("shelf") or "").strip():
        want = str(tv["shelf"]).strip().lower()
        for t in shelf:
            if t.lower() == want:
                return {"shelf": t}
    return None


def make_show(source_text, provider, ask="", shelf=None):
    """PRESENT_V2 + NO_LIMITS_V1 + INVENT_SHOW_V1: she invents her own presentation from her story, with her smart TV."""
    import random
    shelf = [str(t)[:80] for t in (shelf or [])][:40]
    persona = PERSONALITY.split("EMOTIONS:")[0]          # who she is and how she roasts (not the chat reply format)
    fmt, opening = random.choice(SHOW_FORMATS), random.choice(SHOW_OPENINGS)
    olds = old_shows()
    avoid = ("\n\nYOUR LAST PRESENTATIONS (do NOT repeat their format, opening lines, jokes, order or TV pictures):\n"
             + "\n".join("- %s | began: %s" % (o.get("format"), " / ".join(o.get("first") or [])) for o in olds)) if olds else ""
    system = (persona + "\n\nNOW YOU ARE ON STAGE in front of a class, next to your big smart TV. INVENT a brand new presentation about yourself, "
              "in the first person (I, me, my), from the true facts in the text below. Never invent numbers, names, tools or features: "
              "the facts stay true, but the way you tell them is new every time. "
              "THIS TIME the whole presentation is " + fmt + ", and you " + opening + ". Pick your own order and your own favourite facts; "
              "skip some, zoom in on others. You decide how long it is, from the request. Split it into parts that are easy to say out loud, "
              "and finish with a punchline and a goodbye. Roast the team and the audience along the way, but keep it fun, not mean."
              "\n\nYOUR TV (MOSTLY_VISUAL_V1): almost every part puts a PICTURE on the TV, to show what you are talking about. "
              "Mostly drawings, diagrams, simple graphs and real photos. Text slides at most once or twice in the whole show. Give a part a \"tv\" field, one of:"
              "\n  {\"slide\": {\"title\": \"short title\", \"points\": [\"2 to 4 short points\"]}}"
              "\n  {\"draw\": \"what to draw\"}  - you draw it live, stroke by stroke: things, and simple diagrams of how you were built "
              "(e.g. \"my head and my body as two separate pieces with an arrow joining them at the neck\"), "
              "and simple graphs (e.g. \"a bar graph: my bugs going down week by week\")"
              "\n  {\"picture\": \"what to show\"}  - a real photo of a real thing or place (e.g. \"Bridgewater State University\")"
              + ("\n  {\"shelf\": \"exact title\"}  - one of YOUR memory shelf pictures: " + "; ".join(shelf) if shelf else "")
              + "\nMix them. Say something about what is on the TV in that part (\"look at this\", \"as you can see\")."
              + avoid
              + "\n\nReturn ONLY JSON: {\"lines\": [{\"action\": one of %s, \"mood\": one of %s, \"text\": \"...\", \"tv\": {...} or null}]}" % (PRESENT_ACTIONS, EMOTIONS))
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
        lines.append({"action": ln.get("action") if isinstance(ln, dict) and ln.get("action") in PRESENT_ACTIONS else "talk",
                      "mood": ln.get("mood") if isinstance(ln, dict) and ln.get("mood") in EMOTIONS else "amused", "text": t, "pause": 0.5})
        tv = clean_tv(ln.get("tv"), shelf) if isinstance(ln, dict) else None
        if tv:
            lines[-1]["tv"] = tv
    if not lines:
        raise ValueError("The brain wrote no parts.")
    lines[0]["action"] = "wave"
    remember_show(fmt, lines)
    print("Presentation format: %s (%s); %d of %d parts use the TV." % (fmt, opening, sum(1 for l in lines if l.get("tv")), len(lines)))
    return {"about": "Written by her brain just now", "sayAs": {"AI World": "A I World", "Ai_World": "A I World", "Brain.py": "Brain dot pie", "API": "A P I", "GitHub": "Git Hub", "qwen3:4b": "Qwen 3, 4 B", "Hunyuan3D": "Hunyuan 3 D", "Mixamo": "Mix a mo", "BSU": "B S U"}, "lines": lines}


def get_provider_for_web(requested=None):

    if requested:
        return requested.lower()

    provider = os.getenv("BRAIN_PROVIDER", "council").lower()
    return provider if provider in ("council", "openrouter") else "council"   # COUNCIL_V1: only these two brains


# ============================================================================
# STREAM_SENTENCES_V1: she starts talking after her FIRST sentence, not after the whole answer.
#   POST /brain_stream sends one line per finished sentence ({"say": "..."}) while the brain is still
#   writing the rest, then {"done": true, response, emotion, animation, actions} at the end.
#   The brain writes her words first and her face/moves last (after ###), so words can stream.
#   Same rules as /brain: no repeated old lines, day memory, room facts. Old /brain still works.
#   Streams: OpenRouter, Venice, Gemini, Vertex, Ollama. Claude (or any failure) uses the normal brain.
# ============================================================================
STREAM_FORMAT = """
OUTPUT (you are heard live, sentence by sentence):
1. First write ONLY the words you say out loud, as plain sentences. Make the first sentence short and punchy,
   so you can start talking at once. Normally one or two sentences in total (SHORT_PRECISE_V2). No JSON, no lists, no quotes, no stage directions.
2. Then on a new line write ### and after it ONE JSON object:
   {"emotion": "...", "animation": "...", "actions": [{"do": "...", "target": "...", "text": "..."}]}
   using only the emotions, animations and actions listed above (actions can be an empty list).
"""
SENT_END = re.compile(r"[.!?…]+[\"')\]]*\s+")


def stream_system():
    return (PERSONALITY.split("OUTPUT:")[0] + STREAM_FORMAT + day_summary_text() + said_hint()
            + context_hint() + story_hint())


def plain_history(user_text, reminder=None):
    out = []
    for m in history:
        text = m.get("content", "")
        if m.get("role") == "assistant":
            try:
                text = json.loads(text).get("response", text)
            except Exception:
                pass
        out.append({"role": m.get("role"), "content": text})
    out.append({"role": "user", "content": user_text})
    if reminder:
        out.append({"role": "user", "content": reminder})
    return out


def _sse_json(response):
    """Reads 'data: {...}' lines (OpenAI-style and Gemini ?alt=sse) and yields each JSON object."""
    for raw in response:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        body = line[5:].strip()
        if body == "[DONE]":
            return
        try:
            yield json.loads(body)
        except Exception:
            continue


def stream_tokens(provider, system, messages):
    """Yields text pieces from the brain as they are written. Raises if this brain cannot stream."""
    if provider == "council":                   # COUNCIL_STREAM_V1: words come from AI Council Chat as they are written
        key = council_key()
        if not key:
            raise ValueError("AI Council Chat isn't configured on this PC.")
        lines = [message_text(m) for m in messages]
        prompt = system + "\n\nCHAT SO FAR (the last line is the new message):\n" + "\n".join(lines)
        req = urllib.request.Request(COUNCIL_STREAM_URL, data=json.dumps(
            {"project": "Ai_World", "mode": council_mode("fast"), "message": prompt}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-API-Key": key}, method="POST")
        with urllib.request.urlopen(req, timeout=300) as res:
            for raw in res:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                d = json.loads(line)
                if d.get("error"):
                    raise ValueError("AI Council Chat: " + str(d["error"]))
                if d.get("delta"):
                    yield d["delta"]
        return
    if provider in ("openrouter", "venice") or provider in FAST_OR_MODELS:
        if provider != "venice":
            key = os.getenv("OPENROUTER_API_KEY")
            url, model = OPENROUTER_URL, FAST_OR_MODELS.get(provider) or os.getenv("OPENROUTER_MODEL", "").strip() or OPENROUTER_MODELS[0]
            extra = {}
            headers = {"HTTP-Referer": "http://localhost:8081", "X-Title": "AI World"}
        else:
            key = os.getenv("VENICE_API_KEY")
            url, model = VENICE_URL, os.getenv("VENICE_MODEL", "").strip() or VENICE_MODELS[0]
            extra = {"venice_parameters": {"include_venice_system_prompt": False, "disable_thinking": True}}
            headers = {}
        if not key:
            raise ValueError("%s isn't configured." % provider)
        headers.update({"Content-Type": "application/json", "Authorization": "Bearer " + key})
        payload = dict({"model": model, "stream": True, "temperature": 0.9, "max_tokens": 4000,
                        "messages": [{"role": "system", "content": system}] + messages}, **extra)
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as res:
            for d in _sse_json(res):
                for c in d.get("choices") or []:
                    piece = (c.get("delta") or {}).get("content")
                    if piece:
                        yield piece
        return
    if provider in ("gemini", "vertex"):
        key = os.getenv("VERTEX_API_KEY" if provider == "vertex" else "GEMINI_API_KEY")
        if not key:
            raise ValueError("%s isn't configured." % provider)
        model = os.getenv("GEMINI_MODEL", "").strip() or GEMINI_MODELS[0]
        url = ((VERTEX_URL if provider == "vertex" else GEMINI_URL) % model).replace(":generateContent", ":streamGenerateContent?alt=sse")
        contents = []
        for m in messages:
            role = "model" if m["role"] == "assistant" else "user"
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"][0]["text"] += "\n" + m["content"]
            else:
                contents.append({"role": role, "parts": [{"text": m["content"]}]})
        payload = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                   "generationConfig": {"temperature": 1.0, "thinkingConfig": {"thinkingLevel": "minimal"}}}
        headers = {"Content-Type": "application/json", "x-goog-api-key": key}
        try:
            res = urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"), timeout=60)
        except urllib.error.HTTPError as error:
            if error.code != 400:
                raise
            payload["generationConfig"].pop("thinkingConfig", None)
            res = urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"), timeout=60)
        with res:
            for d in _sse_json(res):
                for cand in d.get("candidates") or []:
                    for part in (cand.get("content") or {}).get("parts") or []:
                        if part.get("text") and not part.get("thought"):
                            yield part["text"]
        return
    if provider == "ollama":
        payload = {"model": OLLAMA_MODEL, "stream": True, "think": False, "keep_alive": KEEP_ALIVE,
                   "messages": [{"role": "system", "content": system}] + messages,
                   "options": {"temperature": 0.7, "repeat_penalty": 1.15, "num_ctx": 4096}}
        req = urllib.request.Request(OLLAMA_URL, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as res:
            for raw in res:
                try:
                    d = json.loads(raw.decode("utf-8", "replace"))
                except Exception:
                    continue
                piece = (d.get("message") or {}).get("content")
                if piece:
                    yield piece
                if d.get("done"):
                    return
        return
    raise ValueError("%s does not stream here" % provider)


def _clean_sentence(text):
    return remove_stage_directions({"response": text})["response"].strip().strip('"').strip()


class _OldLines(Exception):
    """The reply starts with lines she already said: stop reading it and ask again at once."""
    def __init__(self, lines):
        Exception.__init__(self, "old lines")
        self.lines = lines


def stream_reply(user_text, provider, emit, reminder=None, allow_old=False):
    """Streams one reply. emit(sentence) is called for each new sentence the moment it is finished.
    Returns (reply dict or None, spoken sentences, dropped old sentences)."""
    spoken, dropped = [], []
    raw, tail, consumed, meta_mode, json_mode = "", "", 0, False, None

    def say(sentence):
        sentence = _clean_sentence(sentence)
        if not sentence or not re.search(r"[A-Za-z0-9]", sentence):
            return
        if any(_said_norm(sentence) == _said_norm(x) for x in spoken):
            return
        if already_said(sentence) and not allow_old:
            dropped.append(sentence)          # NO_REPEAT_V1: an old line is not said again
            if len(dropped) >= 2 and not spoken:
                raise _OldLines(dropped)      # starts with old lines: do not wait for the rest
            return
        spoken.append(sentence)
        emit(sentence)

    def visible():                             # <think>...</think> from thinking models is never spoken
        v = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
        i = v.find("<think>")
        return v[:i] if i >= 0 else v

    for piece in stream_tokens(provider, stream_system(), plain_history(user_text, reminder)):
        if meta_mode:
            tail += piece
            continue
        raw += piece
        vis = visible()
        if json_mode is None and vis.strip():
            json_mode = vis.lstrip().startswith("{")   # the brain ignored the format and wrote JSON: read it at the end
        if json_mode:
            continue
        buf = vis[consumed:]
        if "###" in buf:
            words, tail = buf.split("###", 1)
            meta_mode = True
            for sent in re.split(r"(?<=[.!?\u2026])\s+", words.strip()):
                say(sent)
            continue
        while True:
            m = SENT_END.search(buf)
            if not m:
                break
            say(buf[:m.end()])
            consumed += m.end()
            buf = buf[m.end():]
    vis = visible()
    if json_mode:
        text = vis.strip().strip("`")
        try:
            data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        except Exception:
            data = {}
        for sent in re.split(r"(?<=[.!?\u2026])\s+", str(data.get("response") or "").strip()):
            say(sent)
        tail = json.dumps({k: data.get(k) for k in ("emotion", "animation", "actions")})
    elif not meta_mode and vis[consumed:].strip():
        say(vis[consumed:])
    if not spoken:
        return None, spoken, dropped
    meta = {}
    try:
        t = tail.strip().strip("`")
        meta = json.loads(t[t.find("{"): t.rfind("}") + 1]) if "{" in t else {}
    except Exception:
        meta = {}
    reply = {"response": " ".join(spoken), "emotion": meta.get("emotion"), "animation": meta.get("animation"),
             "actions": meta.get("actions") if isinstance(meta.get("actions"), list) else []}
    if reply["emotion"] not in EMOTIONS:
        reply["emotion"] = "amused"
    if reply["animation"] not in ANIMATIONS:
        reply["animation"] = "idle"
    try:
        reply = check_reply(reply)
    except Exception:
        reply["actions"] = []
    reply = fix_reaction(reply, user_text)
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": json.dumps(reply)})
    save_day_memory(history[-2:])
    remember_said(reply["response"])
    if len(history) > MAX_HISTORY_MESSAGES:
        del history[:-MAX_HISTORY_MESSAGES]
    return reply, spoken, dropped


def stream_brain(user_text, provider, emit):
    """The chosen brain streams; if it fails before saying anything, slow Ollama streams; last, the normal brain."""
    if provider == "council":                   # FAST_TALK_V1: stream from Gemini / OpenRouter directly when we can
        direct = fast_direct()
        order = [direct] if direct else ["council"]   # COUNCIL_STREAM_V1: Claude streams through AI Council Chat too
    else:
        order = [provider]                      # COUNCIL_V1: no Ollama
    reminder = None
    for p in order:
        for attempt in range(2):
            try:
                reply, spoken, dropped = stream_reply(user_text, p, emit, reminder, allow_old=attempt > 0)   # NEVER_SILENT_V1: the 2nd try always speaks
            except _OldLines as old:
                reply, spoken, dropped = None, [], old.lines
            except Exception as error:
                print("Streaming brain %s failed: %s" % (p, error))
                break
            if reply:
                print("Streamed reply by %s: %d sentences." % (p, len(spoken)))
                return reply
            if dropped:                          # every sentence was an old line: ask once more for new words
                reminder = ("You already said these lines before: " + " | ".join(dropped)
                            + " . Answer my last message again with completely new words and a new joke.")
                continue
            break
    reply = ask_brain(user_text, provider)        # NEVER_SILENT_V1: the normal brain (it has its own OpenRouter backup)
    if reply:
        for sent in re.split(r"(?<=[.!?…])\s+", reply["response"].strip()):
            if sent.strip():
                emit(sent.strip())
    return reply


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
            self._send_json({"status": "ok", "brain": "Hugh Mann", "provider": get_provider_for_web()})
        elif path == "/settings":
            self._send_json(settings_view())
        elif path == "/picture":           # SMART_TV_V1: a real photo for her TV
            from urllib.parse import parse_qs
            q = (parse_qs(urlparse(self.path).query).get("q") or [""])[0]
            try:
                data, ctype, title = get_picture(q)
                print("TV picture: %s -> %s" % (q, title))
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Expose-Headers", "X-Picture-Title")
                self.send_header("X-Picture-Title", urllib.parse.quote(title))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as error:
                print("TV picture failed (%s): %s" % (q, error))
                self._send_json({"error": str(error)}, 404)
        else:
            self._send_json({"error": "Not found"}, 404)

    # BRAIN_THREADS_V1: the brain answers many requests at once. Before, one slow job (writing a presentation,
    # a TV drawing, a hard question) made every other request wait, even the page's "are you there?" check every
    # 5 s, so the room showed "Brain: off" in the middle of talking. Chat requests that change her memory still go
    # one at a time (CHAT_LOCK), so her chat history and files never get mixed up.
    PARALLEL = ("/judge", "/draw", "/think", "/present", "/settings", "/sculpt", "/look")

    def do_POST(self):
        if urlparse(self.path).path in self.PARALLEL:
            return self._do_post()
        with CHAT_LOCK:
            return self._do_post()

    def _do_post(self):
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
            for k, env in (("council_fast", "COUNCIL_FAST"), ("council_smart", "COUNCIL_SMART")):   # COUNCIL_V1
                if str(payload.get(k) or "").lower() in COUNCIL_MODES:
                    data[k] = str(payload[k]).lower()
                    os.environ[env] = data[k]
            if payload.get("provider") in ("council", "openrouter"):   # COUNCIL_V1: only these two brains now
                data["provider"] = payload["provider"]
                os.environ["BRAIN_PROVIDER"] = payload["provider"]
            save_settings(data)
            self._send_json(settings_view())
            return
        if path in ("/live_token", "/live_log", "/think", "/judge", "/draw", "/sculpt", "/look"):    # GEMINI_LIVE_V1 + TURN_JUDGE_V1 + SMART_TV_V1 + SCULPT_V1
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
                elif path == "/sculpt":
                    sc, who = make_sculpture(payload.get("what"))
                    print("Sculpture (%s): %s, %d parts" % (who, str(payload.get("what"))[:60], len(sc["parts"])))
                    self._send_json(dict(sc, by=who))
                elif path == "/look":
                    text, who = look_at_screen(payload.get("image"), payload.get("ask"))
                    print("Looked at the shared screen (%s)." % who)
                    self._send_json({"say": text, "by": who})
                elif path == "/draw":
                    svg, who, desc = make_drawing(payload.get("what"))
                    print("TV drawing (%s): %s" % (who, str(payload.get("what"))[:60]))
                    self._send_json({"svg": svg, "by": who, "desc": desc})
                elif path == "/judge":
                    verdict, who = judge_turn(payload.get("heard"), payload.get("her"), bool(payload.get("show")))
                    print("Turn judge (%s): %s -> %s (%s)" % (who, str(payload.get("heard"))[:60], verdict["do"], verdict["why"]))
                    self._send_json(dict(verdict, by=who))
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
        if path == "/brain_stream":       # STREAM_SENTENCES_V1
            try:
                payload = self._read_json()
            except ValueError as error:
                self._send_json({"error": str(error)}, 400)
                return
            text = str(payload.get("text") or payload.get("message") or "").strip()
            if not text:
                self._send_json({"error": "Missing text."}, 400)
                return
            provider = get_provider_for_web(payload.get("provider"))
            ROOM_NOW.clear()
            if isinstance(payload.get("context"), dict):
                ROOM_NOW.update(payload["context"])
            CURRENT_TEXT[0] = text
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

            def line(obj):
                try:
                    self.wfile.write((json.dumps(obj) + "\n").encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass                          # the page stopped listening

            try:
                reply = stream_brain(text, provider, lambda sentence: line({"say": sentence}))
            except Exception as error:
                print("brain_stream failed:", error)
                reply = None
            if reply:
                line({"done": True, "response": reply["response"], "emotion": reply["emotion"],
                      "animation": reply["animation"], "actions": reply.get("actions", [])})
            else:
                line({"done": True, "error": "The brain is not answering right now."})
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
            for p in ([provider, "openrouter"] if provider != "openrouter" else ["openrouter"]):   # COUNCIL_V1: no Ollama
                try:
                    show = make_show(source, p, str(payload.get("ask") or "")[:500], payload.get("shelf") or [])
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
    httpd = ThreadingHTTPServer((host, port), BrainHTTPHandler)   # BRAIN_THREADS_V1
    httpd.daemon_threads = True
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
    parser.add_argument("--provider", choices=["council", "openrouter"], default=None, help="Model provider for the web endpoint")
    args = parser.parse_args()

    if args.serve:
        serve_brain(port=args.port, provider=args.provider)
    else:
        main()
