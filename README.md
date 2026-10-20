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
- `Girl_character_mixamo.glb` — the girl (65-bone Mixamo skeleton incl. fingers, 10 face shapes).
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

## The face door (for Guy 3 — Voice / Audio2Face)
```js
AIWorld.morphNames();            // jawOpen, mouthClose, mouthFunnel, mouthPucker, mouthSmileLeft,
                                 // mouthSmileRight, mouthFrownLeft, mouthFrownRight, eyeBlinkLeft, eyeBlinkRight
AIWorld.setMorph("jawOpen", 0.6);   // 0..1 — feed Audio2Face / viseme values here every frame
AIWorld.onFrame.push((t, dt) => { /* runs every frame */ });
AIWorld.idle = false;            // turns off the built-in breathing + blinking
```
Only these 10 face shapes exist in the model now. Full ARKit (52 shapes) is not in the model yet.

## Known limits (facts)
- Walking goes around the sofa, coffee table and plant (grid path search).
- Movements are code (procedural), not motion-capture clips.
- Physics is simple and home-made (falling, bouncing, rolling, the glass breaking) — no physics library.
- No fingers move. Hair does not swing yet.
- Tested in a headless Chromium browser (all actions, incl. the clumsy moves). Not yet tested on the Windows PC.
