"""Her memory shelf: the books on her bookshelf are your own files.

Put pictures (.jpg .png .gif .webp) or notes (.txt .md) in the folder  memory_books/
next to Girl_Room.html (from your computer, or with the "Add to shelf" button on the page,
which also works from a phone browser). Each file becomes one book on her shelf.
Say "open the picture of the beach" and she pulls that book and shows it on the TV.

Used by page_server.py and brain_server.py:
  GET  /api/books              -> {"books": [{"name", "title", "kind", "url", "size", "time"}]}
  POST /api/books?name=a.jpg   -> body = the file bytes, saved into memory_books/  -> {"ok": true, "book": {...}}
memory_books/ is in .gitignore: your files never go to GitHub.
"""
import json
import os
import re
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
BOOKS = os.path.join(HERE, "memory_books")
PICTURE = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
NOTE = {".txt", ".md"}
MAX_BYTES = 25 * 1024 * 1024


def kind_of(name):
    ext = os.path.splitext(name)[1].lower()
    return "picture" if ext in PICTURE else "note" if ext in NOTE else ""


def title_of(name):
    stem = os.path.splitext(name)[0]
    return re.sub(r"[_\-.]+", " ", stem).strip() or name


def book_info(name):
    path = os.path.join(BOOKS, name)
    st = os.stat(path)
    return {"name": name, "title": title_of(name), "kind": kind_of(name),
            "url": "memory_books/" + urllib.parse.quote(name), "size": st.st_size, "time": int(st.st_mtime)}


def list_books():
    os.makedirs(BOOKS, exist_ok=True)
    out = []
    for name in os.listdir(BOOKS):
        if name.startswith(".") or not kind_of(name) or not os.path.isfile(os.path.join(BOOKS, name)):
            continue
        out.append(book_info(name))
    out.sort(key=lambda b: -b["time"])   # newest first
    return out


def safe_name(name):
    name = os.path.basename(urllib.parse.unquote(name or "")).strip()
    name = re.sub(r"[^A-Za-z0-9 ._\-()]+", "_", name)[:120]
    if not name or name.startswith(".") or not kind_of(name):
        return ""
    base, ext = os.path.splitext(name)
    final, n = name, 2
    while os.path.exists(os.path.join(BOOKS, final)):   # never overwrite an older book
        final = "%s (%d)%s" % (base, n, ext)
        n += 1
    return final


def _json(handler, code, obj):
    body = json.dumps(obj).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_get(handler):
    """True if this GET was a shelf request (and was answered)."""
    if handler.path.split("?")[0].rstrip("/") != "/api/books":
        return False
    _json(handler, 200, {"books": list_books()})
    return True


def handle_post(handler):
    """True if this POST was a shelf upload (and was answered)."""
    parts = urllib.parse.urlsplit(handler.path)
    if parts.path.rstrip("/") != "/api/books":
        return False
    size = int(handler.headers.get("Content-Length") or 0)
    name = safe_name(urllib.parse.parse_qs(parts.query).get("name", [""])[0])
    if not name:
        _json(handler, 400, {"ok": False, "error": "only pictures (jpg png gif webp bmp) and notes (txt md) can go on the shelf"})
        return True
    if size <= 0 or size > MAX_BYTES:
        _json(handler, 400, {"ok": False, "error": "file is empty or bigger than 25 MB"})
        return True
    os.makedirs(BOOKS, exist_ok=True)
    data = handler.rfile.read(size)
    tmp = os.path.join(BOOKS, ".upload-%d" % time.time_ns())
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, os.path.join(BOOKS, name))
    _json(handler, 200, {"ok": True, "book": book_info(name)})
    return True
