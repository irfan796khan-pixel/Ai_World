
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
OLLAMA_MODEL = "qwen3:4b"

# Claude is ready to use later. We'll just need an API key.
# Keeping it separate also lets us compare models.
CLAUDE_URL = ""
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
- Short and punchy: one to three sentences. The punchline goes last.
- If they ask a real question, give the answer, but wrapped in a roast.
- If they compliment you, accept it like a queen, then roast them anyway.
- If they roast you, fire back harder.
- If someone is truly sad or upset (not joking), drop the roast and be kind.
- Never repeat or rephrase their message. Never repeat the same joke.
- Never put actions or stage directions in parentheses.
- If asked directly whether you are AI, admit you are a virtual character,
  then roast them for needing to ask.

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


def send_json(url, payload, headers):

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
        timeout=120
    ) as response:

        return json.loads(
            response.read().decode("utf-8")
        )


def ask_ollama(user_text, reminder=None):

    messages = [{
        "role": "system",
        "content": PERSONALITY + day_summary_text()
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
            "num_predict": 300
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
        "max_tokens": 350,
        "system": PERSONALITY + day_summary_text(),
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


def ask_brain(user_text, provider):

    reminder = None

    for attempt in range(MAX_ATTEMPTS):

        try:

            # We use the selected provider, but everything after
            # this point works exactly the same for either model.
            if provider == "claude":
                reply = ask_claude(user_text, reminder)
            else:
                reply = ask_ollama(user_text, reminder)

            reply = check_reply(reply)
            reply = remove_stage_directions(reply)

            if not reply["response"]:
                raise ValueError(
                    "No dialogue remained after cleanup."
                )

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

            # Old messages get removed when memory gets too large.
            if len(history) > MAX_HISTORY_MESSAGES:
                del history[:-MAX_HISTORY_MESSAGES]

            return reply

        except urllib.error.HTTPError as error:

            print(
                "AI service error:",
                error.code
            )
            return None

        except (urllib.error.URLError, TimeoutError) as error:

            print(
                "Couldn't connect to the AI:",
                error
            )
            return None

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

            if attempt < MAX_ATTEMPTS - 1:
                reminder = (
                    "Return a valid JSON response containing "
                    "response, emotion, and animation. "
                    "Follow the required format exactly."
                )

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
            self._send_json({"status": "ok", "brain": "Hugh Mann"})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
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
