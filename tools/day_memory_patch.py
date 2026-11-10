# Day memory (fast): the brain sends only the last 20 back-and-forths word for word + a short SUMMARY of the whole day.
# The summary is updated in the background every 10 messages. Everything is saved in brain_memory/ and loaded after a restart.
# Run after every update: python tools/day_memory_patch.py Brain.py   (safe to run twice)
import sys
p = sys.argv[1]
raw = open(p, 'rb').read().decode('utf-8')
crlf = '\r\n' in raw
s = raw.replace('\r\n', '\n')
if 'DAY_MEMORY_V2' in s:
    print('day memory: already in ' + p); sys.exit(0)
if 'DAY_MEMORY' in s:
    print('day memory: old version found - start from the GitHub Brain.py (Start button does this)'); sys.exit(0)
steps = [
    ('MAX_HISTORY_MESSAGES = 20\n', 'MAX_HISTORY_MESSAGES = 40   # DAY_MEMORY_V2: last 20 back-and-forths word for word (the rest is in the day summary)\n'),
    ('"num_ctx": 4096', '"num_ctx": 8192'),
    ('"content": PERSONALITY\n', '"content": PERSONALITY + day_summary_text()\n'),
    ('"system": PERSONALITY,', '"system": PERSONALITY + day_summary_text(),'),
    ('history = []\n', '''history = []

# DAY_MEMORY_V2: the whole day is saved in brain_memory/<date>.json (every message)
# and brain_memory/<date>_summary.txt (a short summary the model keeps up to date).
# Fast: each reply sends only the last 20 back-and-forths + the summary, not the whole day.
import datetime
import threading
MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain_memory")
SUMMARY_EVERY = 10          # update the summary after every 10 new messages
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
            lines = f.read().split("\\n", 1)
        summary_done[0] = int(lines[0].replace("#done=", "")) if lines[0].startswith("#done=") else 0
        day_summary[0] = lines[1].strip() if len(lines) > 1 else ""
    except FileNotFoundError:
        pass
    except Exception as error:
        print("Day summary could not be loaded:", error)


def day_summary_text():
    if not day_summary[0]:
        return ""
    return ("\\n\\nWHAT HAPPENED EARLIER TODAY (your memory of today, use it naturally, "
            "bring old things back for callbacks and roasts):\\n" + day_summary[0] + "\\n")


def message_text(m):
    text = m.get("content", "")
    if m.get("role") == "assistant":
        try:
            text = json.loads(text).get("response", text)
        except Exception:
            pass
    return ("Him: " if m.get("role") == "user" else "Her: ") + text


def update_summary():
    # runs in the background, so the next reply does not wait for it
    if not summary_busy.acquire(blocking=False):
        return
    try:
        new = day_log[summary_done[0]:]
        if not new:
            return
        chat = "\\n".join(message_text(m) for m in new)
        prompt = ("Old summary of today:\\n" + (day_summary[0] or "(nothing yet)") +
                  "\\n\\nNew chat lines:\\n" + chat +
                  "\\n\\nWrite the new summary of today: at most 12 short lines. Keep facts about him "
                  "(name, what he works on, what he likes and hates, plans), running jokes, roasts that landed, "
                  "and promises. Drop small talk. Plain text, no intro.")
        data = send_json(OLLAMA_URL, {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "system", "content": "You keep a short, factual memory summary of a chat."},
                         {"role": "user", "content": prompt}],
            "stream": False, "think": False,
            "options": {"temperature": 0.2, "num_ctx": 8192}
        }, {"Content-Type": "application/json"})
        text = (data.get("message") or {}).get("content", "").strip()
        if text:
            day_summary[0] = text
            summary_done[0] += len(new)
            write_file(memory_file("_summary.txt"), "#done=%d\\n%s" % (summary_done[0], text))
    except Exception as error:
        print("Day summary could not be updated:", error)
    finally:
        summary_busy.release()


def save_day_memory(new_messages):
    day_log.extend(new_messages)
    try:
        write_file(memory_file(), json.dumps(day_log, ensure_ascii=False, indent=1))
    except Exception as error:
        print("Day memory could not be saved:", error)
    if len(day_log) - summary_done[0] >= SUMMARY_EVERY:
        threading.Thread(target=update_summary, daemon=True).start()


load_day_memory()
'''),
    ('            # Old messages get removed when memory gets too large.\n',
     '            save_day_memory(history[-2:])   # DAY_MEMORY_V2\n\n            # Old messages get removed when memory gets too large.\n'),
]
for old, new in steps:
    if s.count(old) != 1:
        print('day memory: Brain.py has changed (' + old.strip()[:40] + '), nothing changed'); sys.exit(0)
for old, new in steps:
    s = s.replace(old, new)
if crlf: s = s.replace('\n', '\r\n')
open(p, 'wb').write(s.encode('utf-8'))
print('day memory (fast, with summary): added to ' + p)
