# AI World — Body / Surrounding (Guy 2)

This repo is only the **body and the room**. The brain and the voice are made by the other two team members.

## The loop
```
we talk  >  brain thinks  >  brain sends words + action  >  ACTION (this repo)
```

## 3-person team
| Part | Who | Job |
|---|---|---|
| Brain | Guy 1 (Claude API) | Decides what the character says and how she reacts |
| **Body / Surrounding** | **Guy 2 (this repo)** | 3D model, movements, room, walking to places |
| Voice / Face | Guy 3 (ElevenLabs + NVIDIA Audio2Face) | Speaks the words, moves the lips |

Planned later for the body: a cartoon-style (stylized, not realistic) character, plus Convai for conversation. MetaHuman (realistic) is dropped. What is here now: a three.js web version (girl + living room).

## Run it (Windows)
Double-click `run_girl_room.bat`. It opens http://localhost:8081/Girl_Room.html (needs Python, used only as a tiny local file server).
Opening the html file directly does not work: the browser blocks loading `Girl_character_mixamo.glb` from disk.

## Files
- `Girl_Room.html` — the room + the girl + the action door. One file, three.js r128 from CDN.
- `Girl_character_mixamo.glb` — the girl (65-bone Mixamo skeleton incl. fingers, 28 face shapes), 83 MB.
- `Girl_character_mixamo_packed.glb` — the same girl packed with meshopt (17 MB). The page loads this one first (about 5x less to download); `Girl_Room.html?model=original` forces the big one.
- `moves.json` — real motion from Imran's Mixamo clips (Idle, Walking, Running, Waving, Talking), baked so they fit her bones.
- `quick_replies.json` — about 80 instant replies (around 490 trigger phrases, 240 answers), each tied to a face mood and body moves.
- `run_girl_room.bat` — starts it.
- `VOICESTUDIO.md` — idea: free local voice (VoiceStudio) for the characters, with test code.

## The action door (for Guy 1 — Brain)
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
Type in the bar at the bottom (or call `AIWorld.hear(text)`). If the text matches `quick_replies.json`, she answers at once: speech bubble, browser voice with mouth movement, face mood, and the moves.
If nothing matches, the text goes to the brain:
```js
AIWorld.onUnmatched = (text) => { /* Guy 1: send to the brain, then AIWorld.reply({...}) */ };
// or a small web door: POST {text} to this URL, it must answer with the Brain.py JSON ({response, emotion, animation | actions})
AIWorld.brainUrl = "http://localhost:5005/brain";
AIWorld.learn({ match: ["what is two plus two"], say: ["Four. Easy."], mood: "amused", actions: [{ thumbs: 2 }] });  // new reply, kept in this browser
AIWorld.say("Hello!");        // bubble + browser voice
AIWorld.quick.voice = false;  // turn the browser voice off when the real voice (ElevenLabs / VoiceStudio) is wired in
```
Answers from the brain through `brainUrl` are saved as new quick replies automatically, so the second time is instant.

## Clip button (TikTok)
"Clip 15s" records 15 seconds of the room as a vertical 9:16 video (720 x 1280, 30 fps) with her voice if `AIWorld.speak` is playing, and downloads it as `.webm`.
`await AIWorld.record(15, { download: false })` gives the video Blob instead.

## Real motion (Mixamo)
Idle, walking, running, waving and talking now come from Imran's Mixamo clips (`moves.json`). Her bones have other names (spine, thigh.L …) and some finger names are on the opposite hand in the file, so bones are matched by where they are on her body.
Turning on the spot uses small walking steps, and her head turns first toward where she goes. The clumsy moves (trip, sit, knock, TV scare) still use the code moves, and the clips fade out while they run.
To add a clip: download it from Mixamo as FBX, bake it with the same method into `moves.json` (new key), then use it in `mocapTick`.

## The face door (for Guy 3 — Voice, and for the Brain)
Her face runs by itself with 4 layers mixed every frame: **mood** (from the brain's emotion), **alive** (natural blinks, sometimes double, tiny uneven movement), **talking** (mouth, brows and head follow her voice) and **action** (the clumsy moves set their own face).

```js
AIWorld.mood("happy");                 // neutral, happy, amused, annoyed, confused, sad, surprised, ew, unimpressed
                                       // (also: sassy, skeptical, angry, shocked, bored)
AIWorld.mood("annoyed", 0.6, 3);       // strength 0..1, back to neutral after 3 s
AIWorld.gesture("nod");                // or "shake"
await AIWorld.speak(blobOrUrl);        // plays her voice (e.g. the MP3 Blob from ElevenLabs) — mouth, brows and head follow the sound
AIWorld.stopSpeaking();
AIWorld.speakLevel(0.7);               // if the voice plays somewhere else: feed loudness 0..1 every frame, null to stop
AIWorld.talking();                     // true while she talks

// the whole brain package in one call (matches Brain.py: response / emotion / animation)
AIWorld.reply({ response: "Oh great.", emotion: "amused", animation: "wave", audio: mp3Blob });
AIWorld.reply({ response: "Fine.", emotion: "annoyed", actions: [{walk:"sofa"}, {sit:"miss"}] });
// animation: wave -> waves, nod / shake_head -> head gesture, idle -> nothing. shrug / cross_arms: no body move yet.

AIWorld.morphNames();                  // 28 face shapes (ARKit names), see below
AIWorld.idle = false;                  // hand the face to someone else (e.g. Audio2Face); then use AIWorld.setMorph(name, 0..1)
```
Sound only plays after the person clicks or presses a key once on the page (browser rule).

Face shapes in the model (28, ARKit names): jawOpen, mouthClose, mouthFunnel, mouthPucker, mouthSmileLeft/Right, mouthFrownLeft/Right, eyeBlinkLeft/Right,
browInnerUp, browDownLeft/Right, browOuterUpLeft/Right, eyeWideLeft/Right, eyeSquintLeft/Right, cheekSquintLeft/Right, cheekPuff, noseSneerLeft/Right,
mouthLeft/Right, mouthStretchLeft/Right. "Left" shapes sit on the model's +x side. The full ARKit set is 52.

## Known limits (facts)
- Walking goes around the sofa, coffee table and plant (grid path search).
- Idle, walk, run, wave and talk are Mixamo clips. Trip, sit, knock, TV scare, point and thumbs-up are code moves.
- Physics is simple and home-made (falling, bouncing, rolling, the glass breaking) — no physics library.
- Fingers move (from the clips, plus point and thumbs-up). Hair and clothes do not swing yet.
- Face: 28 of the 52 ARKit shapes. The other 24 (eye look, tongue, jaw sideways, lip roll and press …) need sculpting in Blender.
- The browser voice (speechSynthesis) gives no sound data, so its mouth movement is made up. A real voice through `AIWorld.speak` follows the sound.
- Tested in a headless Chromium browser (all actions, the clips, point, thumbs-up, quick replies, the clip recorder, packed vs original file). Not yet tested on the Windows PC.
