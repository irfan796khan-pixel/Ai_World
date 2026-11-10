# Talk-mix: her talking moves change every time (random start/speed/strength + random hand accents).
# Run after every update: python tools/talkmix_patch.py Girl_Room.html   (safe to run twice)
import sys
p = sys.argv[1]
raw = open(p, 'rb').read().decode('utf-8')
crlf = '\r\n' in raw
s = raw.replace('\r\n', '\n')
if 'function talkAccents' in s:
    print('talk-mix: already in Girl_Room.html'); sys.exit(0)
def rep(old, new):
    global s
    if s.count(old) != 1:
        print('talk-mix: Girl_Room.html has changed on GitHub, could not add the talk-mix. Nothing was changed.'); sys.exit(0)
    s = s.replace(old, new)

# 1. talking clip: new start, speed and strength for every new reply
rep("""  for (const k in MOCAP.layers) {
    const L = MOCAP.layers[k];
    if (k === want) {
      if (L.w < 0.01) L.t = k === 'talking' ? Math.random() * 10 : 0;   // talking: start somewhere new in the clip, so the hands do not repeat the same move
      L.speed = k === 'talking' ? 0.8 + 0.15 * (0.5 + 0.5 * Math.sin(t * 0.13)) : speed;
    }
    // talking: the clip moves her only 55% (the rest stays relaxed idle), so the hands are calmer, like a real chat
    const goal = want === 'talking' ? (k === 'talking' ? 0.55 : k === 'idle' ? 0.45 : 0) : (k === want ? 1 : 0);""",
"""  if (want !== 'talking') MOCAP.talkOn = false;
  for (const k in MOCAP.layers) {
    const L = MOCAP.layers[k];
    if (k === want) {
      if (k === 'talking') {
        if (!MOCAP.talkOn) {               // a NEW reply: random start point, speed and strength, so no two replies move the same
          MOCAP.talkOn = true;
          L.t = Math.random() * (MOCAP.clips.talking.frames / 30);
          MOCAP.talkSpeed = 0.75 + Math.random() * 0.3;
          MOCAP.talkAmt = 0.4 + Math.random() * 0.25;
        }
      } else if (L.w < 0.01) L.t = 0;
      L.speed = k === 'talking' ? MOCAP.talkSpeed * (0.92 + 0.08 * Math.sin(t * 0.37)) : speed;
    }
    // talking: the clip moves her only part of the way (the rest stays relaxed idle), so the hands are calmer, like a real chat
    const tA = MOCAP.talkAmt || 0.55;
    const goal = want === 'talking' ? (k === 'talking' ? tA : k === 'idle' ? 1 - tA : 0) : (k === want ? 1 : 0);""")

# 2. random hand accents while talking (left or right hand, random size and length)
rep("""function startBody(name, secs) {
  const n = gestureName(name); if (!n) { console.warn('AIWorld: unknown body gesture "' + name + '". Known: ' + Object.keys(GESTURES).join(', ')); return false; }
  GEST.name = n;""",
"""// While she talks, small random hand moves are added every few seconds (random gesture, random hand,
// random size and length), so her talking never loops the same way. A gesture from the brain always wins.
const TALK_ACCENTS = ['conversation', 'question', 'question2', 'conversation', 'question'];
function talkAccents(dt) {
  const busy = act.walking || (act.cur && act.cur._kind) || act.pointing > 0 || act.waving > 0;
  if (FX.talkW < 0.5 || busy) { GEST.nextAuto = 0.8 + Math.random() * 1.5; return; }
  if (GEST.name && GEST.left > 0) return;
  GEST.nextAuto = (GEST.nextAuto ?? 1) - dt;
  if (GEST.nextAuto > 0) return;
  let n; do { n = TALK_ACCENTS[Math.floor(Math.random() * TALK_ACCENTS.length)]; } while (n === GEST.lastAuto && Math.random() < 0.8);
  GEST.lastAuto = n; GEST.name = n; GEST.left = 1.6 + Math.random() * 1.8; GEST.t = Math.random() * 6;
  GEST.amp = 0.45 + Math.random() * 0.35; GEST.mirror = Math.random() < 0.5; GEST.auto = true;
  GEST.nextAuto = 0.6 + Math.random() * 2.2;
}
function startBody(name, secs) {
  const n = gestureName(name); if (!n) { console.warn('AIWorld: unknown body gesture "' + name + '". Known: ' + Object.keys(GESTURES).join(', ')); return false; }
  GEST.amp = 1; GEST.mirror = false; GEST.auto = false;
  GEST.name = n;""")

rep("""function gestureTick(t, dt) {
  if (!loaded) return;""", """function gestureTick(t, dt) {
  if (!loaded) return;
  talkAccents(dt);""")

rep("""  const R = GEST.R, L = R === 'R' ? 'L' : 'R';""",
"""  const R = GEST.mirror ? (GEST.R === 'R' ? 'L' : 'R') : GEST.R, L = R === 'R' ? 'L' : 'R';   // mirror = same move with the other hand""")

rep("""    _gq.setFromEuler(_ge.set(o[0] * GEST.w, o[1] * GEST.w, o[2] * GEST.w));   // fade in / out""",
"""    const k = GEST.w * (GEST.amp ?? 1), m = GEST.mirror ? -1 : 1;   // fade in / out, size, mirror (turn and sideways flip)
    _gq.setFromEuler(_ge.set(o[0] * k, o[1] * k * m, o[2] * k * m));""")
if crlf: s = s.replace('\n', '\r\n')
open(p, 'wb').write(s.encode('utf-8'))
print('talk-mix: added to Girl_Room.html')
