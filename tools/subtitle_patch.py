# Subtitle fix: the text bubble always sits ABOVE the command bar (the bar gets taller when its buttons wrap to 2 lines).
# Run after every update: python tools/subtitle_patch.py Girl_Room.html   (safe to run twice)
import sys
p = sys.argv[1]
raw = open(p, 'rb').read().decode('utf-8')
crlf = '\r\n' in raw
s = raw.replace('\r\n', '\n')
if 'id="subtitleFix"' in s:
    print('subtitle fix: already in Girl_Room.html'); sys.exit(0)
if s.count('</body>') != 1:
    print('subtitle fix: could not find </body>, nothing changed'); sys.exit(0)
FIX = '''<script id="subtitleFix">
// Subtitle fix: keep the text bubble 14 px above the top of the command bar, whatever its height.
(function () {
  const bar = document.getElementById('bar'), bub = document.getElementById('bubble');
  if (!bar || !bub) return;
  bub.style.fontSize = '14px'; bub.style.padding = '6px 12px'; bub.style.borderRadius = '14px'; bub.style.maxWidth = 'min(60vw, 520px)';   // smaller subtitle
  function place() { bub.style.bottom = (window.innerHeight - bar.getBoundingClientRect().top + 10) + 'px'; bub.style.zIndex = 11; }
  place(); window.addEventListener('resize', place);
  if (window.ResizeObserver) new ResizeObserver(place).observe(bar);
  setInterval(place, 1000);
})();
</script>
</body>'''
s = s.replace('</body>', FIX)
if crlf: s = s.replace('\n', '\r\n')
open(p, 'wb').write(s.encode('utf-8'))
print('subtitle fix: added to Girl_Room.html')
