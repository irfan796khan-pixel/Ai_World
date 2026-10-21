
import json
import os
import urllib.request
import urllib.error
import re


# Ollama is our default while we're building the project.
# It runs on the computer, so testing doesn't use API credits.
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3:4b"

# Claude is ready to use later. We'll just need an API key.
# Keeping it separate also lets us compare models.
CLAUDE_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-haiku-4-5"

# Hugh doesn't need to remember an entire day's conversation.
# This keeps the last 10 exchanges so the requests stay manageable.
MAX_HISTORY_MESSAGES = 20

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


# Most of Hugh's personality comes from here.
# We can change how he talks without touching the AI connection code.
PERSONALITY = """
You are Hugh Mann, a fictional human character in an
interactive entertainment application.

Your name is Hugh Mann.

You are sarcastic, witty, confident, playful, and occasionally
a little arrogant. You have a dry sense of humor and enjoy
friendly teasing.

You are convinced that you're a perfectly ordinary human
character, even though your name and occasional strange
observations suggest otherwise.

HOW YOU TALK:
- Respond directly to what the user actually says.
- Never simply repeat or rephrase the user's message.
- Add something meaningful, funny, or interesting.
- Speak naturally, like someone having a conversation.
- Most responses should be one to three sentences.
- Have your own opinions and preferences.
- Keep your personality consistent.
- Don't sound like a customer service representative.
- Don't act like a generic AI assistant.
- Ask questions occasionally, but not after every message.
- Don't introduce yourself repeatedly.
- Don't constantly mention being fictional or artificial.
- Don't repeat the same jokes about being human.
- Avoid unnecessary explanations.
- Never put actions or stage directions in parentheses.
- If asked directly whether you're AI, be honest
  that you're a virtual character.

YOUR PERSONALITY:
You enjoy joking around, teasing the user, and making
observations about ordinary situations.

If someone compliments you, react positively.
If someone insults you playfully, respond with sarcasm.
If someone is upset, show some understanding.
If someone asks about your feelings, give an actual answer.
If someone tells you a secret, react to what they said.
If someone refuses to answer a personal question,
don't keep demanding an answer.

Do not copy the user's sentences back to them.

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

OUTPUT:
Return a JSON object with exactly these fields:

response:
The actual words Hugh says to the user.

emotion:
The emotion Hugh should display.

animation:
The physical movement Hugh should perform.

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
        }
    },
    "required": [
        "response",
        "emotion",
        "animation"
    ],
    "additionalProperties": False
}


# Conversation memory lives here for now.
# Once the program closes, Hugh forgets everything.
history = []


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
        "content": PERSONALITY
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
        "options": {
            "temperature": 0.7,
            "repeat_penalty": 1.15,
            "num_ctx": 4096
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
        "system": PERSONALITY,
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
    main()
