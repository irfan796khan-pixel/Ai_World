# Brain dot: green dot = brain connected, red dot = no brain (checks every 5 s, top of the page).
# Run after every update: python tools/braindot_patch.py Girl_Room.html   (safe to run twice)
import sys
p = sys.argv[1]
raw = open(p, 'rb').read().decode('utf-8')
crlf = '\r\n' in raw
s = raw.replace('\r\n', '\n')
if 'id="brainDot"' in s:
    print('brain dot: already in Girl_Room.html'); sys.exit(0)
if s.count('</body>') != 1:
    print('brain dot: could not find </body>, nothing changed'); sys.exit(0)
DOT = '''<div id="brainDot" title="Brain" style="position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:9999;display:flex;align-items:center;gap:7px;padding:5px 12px;border-radius:999px;background:rgba(0,0,0,.55);color:#fff;font:600 13px system-ui,sans-serif;pointer-events:none">
  <span id="brainDotLight" style="width:12px;height:12px;border-radius:50%;background:#ef4444;box-shadow:0 0 8px #ef4444"></span>
  <span id="brainDotText">Brain: off</span>
</div>
<script>
// Brain dot: asks the brain every 5 s. Green = connected, red = not connected.
(function () {
  const light = document.getElementById('brainDotLight'), txt = document.getElementById('brainDotText');
  const ask = (url) => fetch(url, { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null);
  async function check() {
    let j = await ask('brain/health'), url = 'brain';
    if (!j || !j.brain) { j = await ask('http://localhost:5005/health'); url = 'http://localhost:5005/brain'; }
    const on = !!(j && j.brain);
    light.style.background = on ? '#22c55e' : '#ef4444';
    light.style.boxShadow = '0 0 8px ' + (on ? '#22c55e' : '#ef4444');
    txt.textContent = on ? 'Brain: on (' + (j.provider || j.brain) + ')' : 'Brain: off';
    // brain started after the page loaded: connect it now (no reload needed)
    if (on && window.AIWorld && !window.AIWorld.brainUrl && typeof window.AIWorld.onUnmatched !== 'function') window.AIWorld.brainUrl = url;
  }
  check(); setInterval(check, 5000);
})();
</script>
</body>'''
s = s.replace('</body>', DOT)
if crlf: s = s.replace('\n', '\r\n')
open(p, 'wb').write(s.encode('utf-8'))
print('brain dot: added to Girl_Room.html')
