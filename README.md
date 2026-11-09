# AI World

A cartoon 3D girl who lives in a living room on a web page. You talk to her, the brain decides what she says and does, and her body, face and voice do it.

## The loop
```
we talk  >  brain thinks  >  brain sends words + emotion + action  >  she speaks, makes the face and moves
```

## 2-person team
| Part | Who | Job |
|---|---|---|
| Brain | Steven (`Brain.py`) | Decides what she says, her emotion and her move (Ollama `qwen3:4b` now, Claude ready for later) |
| Body, room, face and voice | Imran (`Girl_Room.html` + servers) | 3D model, movements, the room, face shapes, VoiceStudio voice, quick replies, Presentation show |

The voice and the face are now part of the body side (VoiceStudio + the face system in the page). MetaHuman (realistic) is dropped; she stays cartoon style.

## Run it (Windows) — one click
Double-click `run_girl_room.bat` (or the **Start AI World** shortcut on the Desktop, or VS Code: Terminal → Run Task → "AI World: start"). It:
1. opens **VoiceStudio** if it is not open yet, and waits (up to 90 s) until her voice answers on port 3900,
2. starts the brain: `Brain.py --serve --port 5005` (Ollama `qwen3:4b`; run `ollama pull qwen3:4b` once),
3. starts `page_server.py` on port 8081 (the room + her voice passed through to VoiceStudio, so the browser does not block it),
4. opens http://localhost:8081/Girl_Room.html.
If a part is already running it is not started twice. Keep the black windows open while you use her.

Her voice: the VoiceStudio profile **AI World Girl** (female, young adult, moderate pitch, American accent). Every line VoiceStudio makes is saved in `voice_cache/` and plays at once next time; the presentation lines are made in the background after the page opens (the button shows `Presentation (voice x/45)`). VoiceStudio is much faster on the NVIDIA GPU (about 2 s a line) than on the CPU (10–30 s).

Other way to start: `python brain_server.py ollama` serves the room and the brain together on 8081 (also passes the voice through).

How a sentence travels: you type → a quick reply answers at once if one matches → otherwise the page sends it to the brain → Brain.py answers `{response, emotion, animation}` → bubble + voice + face mood + move (wave, nod, shake_head, shrug, cross_arms, idle).
Type `new chat` to clear the brain's memory of the chat (`reset` alone cleans up the room).
`Girl_Room.html?proposal` starts the class presentation script by itself.
Opening the html file directly (file:///) does not work: the browser blocks loading `Girl_character_mixamo.glb` and her voice.

## Files
- `Girl_Room.html` — the room + the girl + the action door. One file, three.js r147 from CDN (r128 could only blend 8 face shapes at once, so moods with many shapes lost the jaw).
- `Girl_character_mixamo.glb` — the girl (65-bone Mixamo skeleton incl. fingers, 31 face shapes, a real openable mouth with teeth and tongue).
- `Girl_character_mixamo_packed.glb` — the same girl packed with meshopt (14.6 MB instead of 62.6 MB). The page loads this one first; `Girl_Room.html?model=original` forces the big one.
- `moves.json` — real motion from Imran's Mixamo clips (Idle, Walking, Running, Waving, Talking), baked so they fit her bones.
- `quick_replies.json` — 81 instant replies (496 trigger phrases, 243 answers), each tied to a face mood and body moves.
- `run_girl_room.bat` — one click: VoiceStudio + brain + room.
- `page_server.py` — serves the room on 8081 and passes `/v1/audio/...` to VoiceStudio (saves every made line in `voice_cache/`).
- `wait_for.py` — small helper the start file uses to wait until VoiceStudio / the brain answers.
- `brain_server.py` — serves the page and connects it to `Brain.py` (`/brain`, `/brain/health`).
- `Brain.py` — the brain (Ollama or Claude). Its character prompt is still the placeholder "Hugh Mann".
- `BrainWithScript.py` — the same brain plus a `script` command that reads a fixed intro text.
- `roast_script.json` — the show for the **Presentation** button: she performs the lines in order (voice, one-sentence subtitles, moves). Edit the text/actions freely; `sayAs` fixes how the voice reads words like Brain.py. Press Presentation again to stop. `AIWorld.show.run('other.json')` plays another script.
- `VOICESTUDIO.md` — her voice: free local VoiceStudio (built into the page), with the browser voice as backup.
- `tools/` — the Python scripts that rebuilt the face (cut the lips open, added teeth/tongue/mouth, new face shapes). Run `python build_face.py out.glb` with the old model saved as `orig.glb` (paths inside the script point to /home/claude/work).

## The action door (for the brain)
Everything goes through `window.AIWorld` in the page.

```js
AIWorld.act([
  { walk: "sofa" },          // walk to a spot: center, sofa, window, plant, front, tv, ball — or {walk:{x:1, z:-2}}. Over 5 m she runs (run:true / run:false to force)
  { face: "camera" },        // turn to the person (or a number in degrees)
  { wave: 2 },               // wave for 2 seconds (Mixamo waving clip)
  { point: "tv" },           // point at it with arm + index finger: tv, sofa, plant, window, table, ball, lamp, board, camera (time: 3)
  { thumbs: 2 },             // thumbs-up for 2 seconds
  { lamp: true },            // lamp on / off
  { tv: "hello" },           // TV on with text, or true / false
  { board: "Hi Irfan" },     // write on the whiteboard
  { wait: 1.5 },             // stand still

  // funny / clumsy moves
  { trip: true },            // stumbles, falls flat on her face, gets back up
  { sit: "sofa", time: 3 },  // walks to the sofa and sits for 3 s
  { sit: "miss" },           // tries to sit, misses the sofa, lands on the floor
  { knock: "glass" },        // walks to the coffee table and knocks the glass off (it shatters)
  { tv: "glitch", time: 4 }, // TV goes crazy by itself, she jumps in fright, then "BOO!"
  { reset: true }            // puts ball, glass and book back, removes the shards
]);
// Walking into the ball kicks it. Spots now also include "table" (next to the coffee table).
AIWorld.onActionDone = (a) => console.log("done", a);   // called after each action (a "sit" or "knock" reports once, when fully done)
AIWorld.busy();   // true while she is doing something
AIWorld.stop();   // clear everything
```
Actions run one after another. Unknown actions are skipped with a console warning.

## Her own mind (sass, stats, chaos)
She has 4 bars (top right): **Energy, Mood, Focus, Annoyed**. They change by themselves and with what you say.
- **Bossing her around** raises Annoyed (more orders in a row = more). "please" lowers it. Compliments raise Mood and lower Annoyed, insults do the opposite.
- **Rebels** when Annoyed is very high: crosses her arms + eye roll, walks up and taps on your screen (ripple + tap sound), or throws the glass at you (the screen cracks).
- **Hostage:** too many "walk" orders and she picks up the glass, holds it out, stares into the camera: "Ask me to walk one more time and the glass dies." Type anything and she drops it.
- **Tantrum:** missing the sofa or stubbing her toe on the ball. She throws the book at the camera (THWACK), flips the coffee table upside down, flails every bone on the floor, then stands up calmly: "Anyway."
- **On her own:** when nobody talks to her she decides what to do. Tired = slow walk to the sofa and a nap. Bored = window, plant, TV, whiteboard, ball. Happy = waves.
- **Room builder:** "spawn a red box on the table", "add three big blue balls near the plant", "make it rain balls", "clear all the stuff". She "types" the three.js code on screen and the objects drop in with physics. The code shown comes from a fixed recipe; AI-written code is never run (one bad line could break the page, and live-chat viewers could abuse it).
- Screen effects and sound effects are recorded by the Clip button too.

```js
AIWorld.stats();                         // {energy, mood, focus, annoyed, hostage, tantrum}
AIWorld.setStats({ energy: 20 });
AIWorld.sassy(0);                        // 0 = obeys everything, 1 = normal, 2 = extra rebellious
AIWorld.autonomous(false);               // stop her deciding things on her own
AIWorld.showStats(false);
AIWorld.act([{ tantrum: true }]);        // also: {hostage:"glass"}, {rebel:"cross"|"tap"|"throw"}, {spawn:{shape:"ball", color:"pink", size:0.3, count:3, at:"on the table"}}, {clearSpawned:true}
AIWorld.build("spawn a red box on the table");
```
Her model has no eye-look face shapes, so the eye roll is faked with the head and heavy lids. The flailing is code (strong random turns on every bone), not real ragdoll physics.

## Quick replies + talk bar (fast answers, no waiting for the brain)
Type in the bar at the bottom (or call `AIWorld.hear(text)`). If the text matches `quick_replies.json`, she answers at once: speech bubble, voice, face mood, and the moves. Voice order: `AIWorld.onSay(text)` if set, else VoiceStudio on localhost:3900 (see `VOICESTUDIO.md`), else the browser voice. The **Voice** button switches Studio → browser → off.
If nothing matches, the text goes to the brain:
```js
AIWorld.onUnmatched = (text) => { /* send to the brain, then AIWorld.reply({...}) */ };
// or a small web door: POST {text} to this URL, it must answer with the Brain.py JSON ({response, emotion, animation | actions})
AIWorld.brainUrl = "http://localhost:5005/brain";
AIWorld.learn({ match: ["what is two plus two"], say: ["Four. Easy."], mood: "amused", actions: [{ thumbs: 2 }] });  // new reply, kept in this browser
AIWorld.say("Hello!");        // speech bubble + voice (onSay, else VoiceStudio, else browser voice)
AIWorld.voice.mode = "off";   // "studio" | "browser" | "off"
AIWorld.onSay = (text) => { /* another voice: make the audio, then AIWorld.speak(audio) */ };
```
Answers from the brain through `brainUrl` are saved as new quick replies automatically, so the second time is instant.

## Her voice (teen girl, Piper)
Her voice is made on the laptop by `girl_voice.py` with **Piper** (free, offline, the same engine as the Adam Voice phone app v3). VoiceStudio is no longer needed for her voice.
- Voice: Piper `en_US-hfc_female-medium` (the highest of the 5 US female Piper voices we measured: 235 Hz), lifted about 2 semitones for a teen sound (`LIFT = 1.12` in `girl_voice.py`; 1.0 = normal).
- `run_girl_room.bat` runs `python girl_voice.py --setup` first: the first time it installs `piper-tts` and downloads the voice (about 63 MB, into `voices/`).
- `page_server.py` answers `/v1/audio/speech` with Piper (a line takes about 0.3 s) and keeps every line in `voice_cache/`. If Piper is not ready it still forwards to VoiceStudio.
- Long answers are cut into pieces: the first sentence alone, the rest in pieces of up to about 150 letters. She starts talking as soon as the first piece is ready, and the next pieces are made in the background while she talks. Test: a 16.7 s answer took 1.75 s to make in one go; the first piece took 0.19 s.
- Live chat speech-to-text still uses VoiceStudio if it is running; if not, Live chat uses the browser's speech recognition from the first sentence.

## Live chat (hands-free, button "Live chat")
Press **Live chat** once, allow the microphone, then just talk. No typing.
1. **Silero VAD** ([ricky0123/vad](https://github.com/ricky0123/vad), ISC licence, loaded from the CDN) hears when you start and stop talking.
2. **VoiceStudio's local Whisper** (`/v1/audio/transcriptions`, passed through `page_server.py`) turns your words into text on the PC. Free, nothing leaves the laptop.
3. The text goes into `hear()` like typed text: quick reply first, else the brain. She answers with voice, face and moves.

The button shows **Live chat: on**, **Listening…** and **Thinking…**. What you said shows in the text box as "you said: …".
While she talks the mic is ignored, so she does not hear her own voice through the speakers. Headphones work best.
If VoiceStudio's speech-to-text fails twice, it switches to the browser's own speech recognition (Chrome or Edge; that one sends your voice to Google or Microsoft). The button then says **Live chat: on (browser)**.

```js
AIWorld.live.start();             // same as pressing Live chat ("browser" = force the browser recognition)
AIWorld.live.stop();
AIWorld.live.bargeIn = true;      // let you cut her off by talking (best with headphones)
AIWorld.live.lang = "en";         // language sent to Whisper
AIWorld.live.heard();             // the last 50 things she heard
AIWorld.onHeard = (text) => {};   // called with every heard sentence
```
Tested in headless Chrome with a fake microphone and real Whisper (tiny.en): she heard "Can you wave at me please?" and answered with the wave quick reply. Not yet tested with a real mic on the Windows laptop, and the Whisper model name VoiceStudio wants was not found in its docs (the page sends `whisper-1`).

## Talking gestures (body language)
8 gestures from Imran's GestureType list, added **on top of** her Mixamo clips, so idle, talking and walking keep running underneath. They fade in and out.
| Name | What she does |
|---|---|
| `secret` | hunches, turns, right hand cupped at her mouth |
| `arguing` | leans in, chops with the right hand |
| `funny` | head back, chest shakes with laughter |
| `conversation` | weight shift, small nods, easy forearms |
| `question` | one hand up, palm rolling, head tilt |
| `question2` | both forearms out, palms open |
| `phone` | right hand at her ear with a small phone, left arm across her waist |
| `phone_pacing` | the phone pose while she walks back and forth |

```js
AIWorld.act([{ body: "arguing", time: 4 }]);   // does not hold up the next action, so she can talk at the same time
AIWorld.body("secret", 3);                      // same thing, direct
AIWorld.bodyGestures();                         // the list
// the brain can send them as "animation": arguing, question, question_two_hands, secret, laugh, talk, phone, phone_pacing
```
The original names work too (`ARGUING`, `TELLING_SECRET`, `TWO_HAND_QUESTION` …).
The pasted numbers were made for another skeleton, so on her some arms went the wrong way (arguing hit her back, the secret hand stayed in front). Each one was re-tuned by its description and checked in pictures. Her file has the `.R` arm on her LEFT side; the code finds the real right arm itself. `phone` and `phone_pacing` were listed but had no code, so they were written new. Gestures pause during clumsy moves and pointing, and (except pacing) while she walks.

## Clip button (TikTok)
"Clip 15s" records 15 seconds of the room as a vertical 9:16 video (720 x 1280, 30 fps) with her voice if `AIWorld.speak` is playing, and downloads it as `.webm`.
`await AIWorld.record(15, { download: false })` gives the video Blob instead.

## Real motion (Mixamo)
Idle, walking, running, waving and talking now come from Imran's Mixamo clips (`moves.json`). Her bones have other names (spine, thigh.L …) and some finger names are on the opposite hand in the file, so bones are matched by where they are on her body.
Turning on the spot uses small walking steps, and her head turns first toward where she goes. The clumsy moves (trip, sit, knock, TV scare) still use the code moves, and the clips fade out while they run.
To add a clip: download it from Mixamo as FBX, bake it with the same method into `moves.json` (new key), then use it in `mocapTick`.

## The face door (voice and brain plug in here)
Her face runs by itself with 4 layers mixed every frame: **mood** (from the brain's emotion), **alive** (natural blinks, sometimes double, tiny uneven movement), **talking** (mouth, brows and head follow her voice) and **action** (the clumsy moves set their own face).

```js
AIWorld.mood("happy");                 // neutral, happy, laugh, amused, annoyed, angry, confused, sad, surprised, ew, unimpressed
                                       // (also: sassy, skeptical, shocked, bored, laughing, mad)
AIWorld.mood("annoyed", 0.6, 3);       // strength 0..1, back to neutral after 3 s
AIWorld.gesture("nod");                // or "shake"
await AIWorld.speak(blobOrUrl);        // plays her voice (e.g. the MP3 Blob from VoiceStudio) — mouth, brows and head follow the sound
AIWorld.stopSpeaking();
AIWorld.speakLevel(0.7);               // if the voice plays somewhere else: feed loudness 0..1 every frame, null to stop
AIWorld.talking();                     // true while she talks

// the whole brain package in one call (matches Brain.py: response / emotion / animation)
AIWorld.reply({ response: "Oh great.", emotion: "amused", animation: "wave", audio: mp3Blob });
AIWorld.reply({ response: "Fine.", emotion: "annoyed", actions: [{walk:"sofa"}, {sit:"miss"}] });
// animation: wave -> waves, nod / shake_head -> head gesture, idle -> nothing. shrug / cross_arms: no body move yet.

AIWorld.morphNames();                  // 28 face shapes (ARKit names), see below
AIWorld.idle = false;                  // hand the face to an outside driver; then use AIWorld.setMorph(name, 0..1)
```
Sound only plays after the person clicks or presses a key once on the page (browser rule).

Face shapes in the model (31 = 28 ARKit names + mouthUpperUp, mouthLowerDown, mouthShrugLower; all re-made stronger, the mouth shapes are new): jawOpen, mouthClose, mouthFunnel, mouthPucker, mouthSmileLeft/Right, mouthFrownLeft/Right, eyeBlinkLeft/Right,
browInnerUp, browDownLeft/Right, browOuterUpLeft/Right, eyeWideLeft/Right, eyeSquintLeft/Right, cheekSquintLeft/Right, cheekPuff, noseSneerLeft/Right,
mouthLeft/Right, mouthStretchLeft/Right. "Left" shapes sit on the model's +x side. The full ARKit set is 52.

## Known limits (facts)
- The mouth: lips are cut along the lip line; jaw opens up to about 2.9 cm at jawOpen = 1. Teeth are simple rounded blocks, the tongue a flat blob. No tears on the sad face. Eyes: the white of the eyeball can show at the corners when she laughs.
- Not yet tested on the Windows PC (the model has 737k vertices; r147 keeps 31 morph targets as textures, about 365 MB of GPU memory).
- Walking goes around the sofa, coffee table and plant (grid path search).
- Idle, walk, run, wave and talk are Mixamo clips. Trip, sit, knock, TV scare, point and thumbs-up are code moves.
- Physics is simple and home-made (falling, bouncing, rolling, the glass breaking) — no physics library.
- Fingers move (from the clips, plus point and thumbs-up). Hair and clothes do not swing yet.
- Face: 28 of the 52 ARKit shapes. The other 24 (eye look, tongue, jaw sideways, lip roll and press …) need sculpting in Blender.
- Tested in a headless Chromium browser (all actions, the clips, point, thumbs-up, quick replies, the clip recorder, packed vs original file). Not yet tested on the Windows PC.
