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
- `Girl_character_mixamo.glb` — the girl (65-bone Mixamo skeleton incl. fingers, 28 face shapes).
- `run_girl_room.bat` — starts it.

## The action door (for Guy 1 — Brain)
Everything goes through `window.AIWorld` in the page.

```js
AIWorld.act([
  { walk: "sofa" },          // walk to a spot: center, sofa, window, plant, front, tv, ball — or {walk:{x:1, z:-2}}
  { face: "camera" },        // turn to the person (or a number in degrees)
  { wave: 2 },               // wave for 2 seconds
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
- Movements are code (procedural), not motion-capture clips.
- Physics is simple and home-made (falling, bouncing, rolling, the glass breaking) — no physics library.
- No fingers move. Hair does not swing yet.
- Tested in a headless Chromium browser (all actions, incl. the clumsy moves). Not yet tested on the Windows PC.
