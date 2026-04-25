from flask import Flask, jsonify, send_file, render_template, abort, request, Response
import os, re, shutil, hashlib, subprocess, json, sys, logging
from mimetypes import guess_type

logging.getLogger('werkzeug').setLevel(logging.ERROR)

VERSION = "1.0.0"

def _app_dir():
    """Folder containing the exe (or script during dev). Music files live here."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _res_dir():
    """Folder containing bundled resources (templates). Uses _MEIPASS when frozen."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

app            = Flask(__name__, template_folder=os.path.join(_res_dir(), 'templates'))
CACHE_DIR      = os.path.join(_app_dir(), ".audio_cache")
PLAYLISTS_FILE = os.path.join(_app_dir(), "playlists.json")
CONFIG_FILE    = os.path.join(_app_dir(), "config.json")

def load_config():
    if not os.path.exists(CONFIG_FILE): return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_config(data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

MUSIC_DIR = load_config().get('music_dir', '')
SUPPORTED     = ('.mp3', '.wma', '.flac', '.ogg', '.wav', '.m4a', '.aac')
TRANSCODE_EXTS = {'.wma', '.aac'}

ID3_GENRES = [
    "Blues","Classic Rock","Country","Dance","Disco","Funk","Grunge","Hip-Hop","Jazz",
    "Metal","New Age","Oldies","Other","Pop","R&B","Rap","Reggae","Rock","Techno",
    "Industrial","Alternative","Ska","Death Metal","Pranks","Soundtrack","Euro-Techno",
    "Ambient","Trip-Hop","Vocal","Jazz+Funk","Fusion","Trance","Classical","Instrumental",
    "Acid","House","Game","Sound Clip","Gospel","Noise","AlternRock","Bass","Soul","Punk",
    "Space","Meditative","Instrumental Pop","Instrumental Rock","Ethnic","Gothic","Darkwave",
    "Techno-Industrial","Electronic","Pop-Folk","Eurodance","Dream","Southern Rock","Comedy",
    "Cult","Gangsta","Top 40","Christian Rap","Pop/Funk","Jungle","Native American","Cabaret",
    "New Wave","Psychedelic","Rave","Showtunes","Trailer","Lo-Fi","Tribal","Acid Punk",
    "Acid Jazz","Polka","Retro","Musical","Rock & Roll","Hard Rock",
]

# ── Helpers ───────────────────────────────────────────────

def resolve_genre(raw):
    if not raw: return "Unknown"
    raw = raw.strip()
    m = re.match(r'^\(?(\d+)\)?$', raw)
    if m:
        idx = int(m.group(1))
        return ID3_GENRES[idx] if idx < len(ID3_GENRES) else "Unknown"
    m = re.match(r'^\((\d+)\)\s*(.*)', raw)
    if m:
        text = m.group(2).strip()
        if text: return text
        idx = int(m.group(1))
        return ID3_GENRES[idx] if idx < len(ID3_GENRES) else "Unknown"
    return raw or "Unknown"


def get_metadata(filepath):
    ext      = os.path.splitext(filepath)[1].lower()
    filename = os.path.basename(filepath)
    title    = os.path.splitext(filename)[0]
    artist   = "Unknown Artist"
    album    = "Unknown Album"
    genre    = "Unknown"
    duration = 0
    try:
        if ext == ".mp3":
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, ID3NoHeaderError
            audio = MP3(filepath)
            duration = int(audio.info.length)
            try:
                tags = ID3(filepath)
                t = tags.get("TIT2"); a = tags.get("TPE1")
                al = tags.get("TALB"); g = tags.get("TCON")
                if t: title  = str(t)
                if a: artist = str(a)
                if al: album = str(al)
                if g: genre  = resolve_genre(str(g))
            except ID3NoHeaderError:
                pass
        elif ext == ".wma":
            from mutagen.asf import ASF
            audio = ASF(filepath)
            duration = int(audio.info.length)
            t  = audio.tags.get("Title");         a  = audio.tags.get("Author")
            al = audio.tags.get("WM/AlbumTitle"); g  = audio.tags.get("WM/Genre")
            if t:  title  = str(t[0])
            if a:  artist = str(a[0])
            if al: album  = str(al[0])
            if g:  genre  = str(g[0])
        elif ext in (".flac", ".ogg", ".m4a", ".aac"):
            from mutagen import File
            audio = File(filepath)
            if audio:
                duration = int(audio.info.length)
                tags = audio.tags or {}
                def tag(k):
                    v = tags.get(k); return str(v[0]) if v else None
                t  = tag("title")  or tag("TITLE")
                a  = tag("artist") or tag("ARTIST")
                al = tag("album")  or tag("ALBUM")
                g  = tag("genre")  or tag("GENRE")
                if t:  title  = t
                if a:  artist = a
                if al: album  = al
                if g:  genre  = resolve_genre(g)
    except Exception:
        pass
    return {"title": title, "artist": artist, "album": album,
            "genre": genre, "duration": duration, "filename": filename}


def extract_art(filepath):
    """Return (bytes, mime) for embedded album art, or (None, None)."""
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".mp3":
            from mutagen.id3 import ID3, ID3NoHeaderError
            try:
                tags = ID3(filepath)
                pics = tags.getall("APIC")
                if pics:
                    return pics[0].data, pics[0].mime or "image/jpeg"
            except ID3NoHeaderError:
                pass
        elif ext == ".flac":
            from mutagen.flac import FLAC
            audio = FLAC(filepath)
            if audio.pictures:
                p = audio.pictures[0]
                return p.data, p.mime or "image/jpeg"
        elif ext in (".m4a", ".mp4"):
            from mutagen.mp4 import MP4
            audio = MP4(filepath)
            if audio.tags and "covr" in audio.tags:
                return bytes(audio.tags["covr"][0]), "image/jpeg"
    except Exception:
        pass
    return None, None


def find_ffmpeg():
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def cache_path_for(source):
    stat = os.stat(source)
    key  = hashlib.md5(f"{source}|{stat.st_mtime}|{stat.st_size}".encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{key}.mp3")


def transcode_to_mp3(source, dest):
    ff = find_ffmpeg()
    if not ff: return False
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = dest + ".tmp"
    try:
        r = subprocess.run(
            [ff, "-y", "-i", source, "-codec:a", "libmp3lame", "-q:a", "2",
             "-loglevel", "error", tmp],
            capture_output=True, timeout=120)
        if r.returncode == 0 and os.path.exists(tmp):
            os.replace(tmp, dest); return True
    except Exception:
        pass
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except Exception: pass
    return False


def stream_file(filepath, mime):
    size         = os.path.getsize(filepath)
    range_header = request.headers.get("Range")
    if not range_header:
        resp = send_file(filepath, mimetype=mime)
        resp.headers["Accept-Ranges"] = "bytes"
        return resp
    m = re.search(r"bytes=(\d+)-(\d*)", range_header)
    if not m: abort(416)
    start  = int(m.group(1))
    end    = int(m.group(2)) if m.group(2) else min(start + 1024 * 1024, size - 1)
    length = end - start + 1
    def generate():
        with open(filepath, "rb") as f:
            f.seek(start); remaining = length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk: break
                remaining -= len(chunk); yield chunk
    resp = Response(generate(), status=206, mimetype=mime, direct_passthrough=True)
    resp.headers.update({"Content-Range": f"bytes {start}-{end}/{size}",
                         "Accept-Ranges": "bytes", "Content-Length": str(length)})
    return resp


# ── Playlist helpers ───────────────────────────────────────

def load_playlists():
    if not os.path.exists(PLAYLISTS_FILE): return {}
    try:
        with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_playlists(data):
    with open(PLAYLISTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def song_map():
    if not MUSIC_DIR or not os.path.isdir(MUSIC_DIR): return {}
    m = {}
    for fn in os.listdir(MUSIC_DIR):
        if fn.lower().endswith(SUPPORTED):
            m[fn] = get_metadata(os.path.join(MUSIC_DIR, fn))
    return m


# ── Routes ────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/version")
def get_version():
    return jsonify({"version": VERSION})


@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({"music_dir": MUSIC_DIR,
                    "configured": bool(MUSIC_DIR and os.path.isdir(MUSIC_DIR))})


@app.route("/api/config", methods=["POST"])
def set_config():
    global MUSIC_DIR
    path = (request.json or {}).get("music_dir", "").strip().strip('"').strip("'")
    if not path:
        return jsonify({"error": "Path required"}), 400
    if not os.path.isdir(path):
        return jsonify({"error": f"Folder not found: {path}"}), 400
    MUSIC_DIR = path
    cfg = load_config()
    cfg["music_dir"] = path
    save_config(cfg)
    return jsonify({"music_dir": path, "configured": True})


@app.route("/api/songs")
def get_songs():
    if not MUSIC_DIR or not os.path.isdir(MUSIC_DIR): return jsonify([])
    songs = []
    for fn in sorted(os.listdir(MUSIC_DIR)):
        if fn.lower().endswith(SUPPORTED):
            songs.append(get_metadata(os.path.join(MUSIC_DIR, fn)))
    return jsonify(songs)


@app.route("/api/ffmpeg")
def ffmpeg_status():
    return jsonify({"available": bool(find_ffmpeg())})


@app.route("/api/art/<path:filename>")
def get_art(filename):
    filepath = os.path.join(MUSIC_DIR, filename)
    if not os.path.abspath(filepath).startswith(os.path.abspath(MUSIC_DIR)): abort(403)
    if not os.path.exists(filepath): abort(404)
    data, mime = extract_art(filepath)
    if not data: abort(404)
    return Response(data, mimetype=mime, headers={"Cache-Control": "public, max-age=86400"})


@app.route("/audio/<path:filename>")
def serve_audio(filename):
    filepath = os.path.join(MUSIC_DIR, filename)
    if not os.path.abspath(filepath).startswith(os.path.abspath(MUSIC_DIR)): abort(403)
    if not os.path.exists(filepath): abort(404)
    ext = os.path.splitext(filename)[1].lower()
    if ext in TRANSCODE_EXTS:
        cached = cache_path_for(filepath)
        if not os.path.exists(cached):
            if not transcode_to_mp3(filepath, cached):
                return stream_file(filepath, guess_type(filepath)[0] or "audio/x-ms-wma")
        return stream_file(cached, "audio/mpeg")
    return stream_file(filepath, guess_type(filepath)[0] or "audio/mpeg")


# ── Playlist routes ────────────────────────────────────────

@app.route("/api/playlists", methods=["GET"])
def get_playlists():
    pls  = load_playlists()
    smap = song_map()
    return jsonify({name: [smap[f] for f in songs if f in smap]
                    for name, songs in pls.items()})


@app.route("/api/playlists", methods=["POST"])
def create_playlist():
    name = (request.json or {}).get("name", "").strip()
    if not name: return jsonify({"error": "Name required"}), 400
    pls = load_playlists()
    if name in pls: return jsonify({"error": "Already exists"}), 409
    pls[name] = []
    save_playlists(pls)
    return jsonify({"name": name, "songs": []}), 201


@app.route("/api/playlists/<string:name>", methods=["PUT"])
def rename_playlist(name):
    new_name = (request.json or {}).get("name", "").strip()
    if not new_name: return jsonify({"error": "Name required"}), 400
    pls = load_playlists()
    if name not in pls: abort(404)
    if new_name != name and new_name in pls: return jsonify({"error": "Name taken"}), 409
    pls[new_name] = pls.pop(name)
    save_playlists(pls)
    return jsonify({"name": new_name})


@app.route("/api/playlists/<string:name>", methods=["DELETE"])
def delete_playlist(name):
    pls = load_playlists()
    if name not in pls: abort(404)
    del pls[name]
    save_playlists(pls)
    return "", 204


@app.route("/api/playlists/<string:name>/songs", methods=["POST", "DELETE"])
def playlist_songs(name):
    filename = (request.json or {}).get("filename", "").strip()
    pls = load_playlists()
    if name not in pls: abort(404)
    if request.method == "POST":
        if filename and filename not in pls[name]:
            pls[name].append(filename)
    else:
        if filename in pls[name]:
            pls[name].remove(filename)
    save_playlists(pls)
    return jsonify({"count": len(pls[name])})


if __name__ == "__main__":
    import webbrowser, threading, time
    ff = find_ffmpeg()
    print(f"\n  ★  Aria v{VERSION}")
    print(f"  {'─'*36}")
    print(f"  FFmpeg: {'found ✓' if ff else 'NOT FOUND — WMA/AAC may not play'}")
    if not ff:
        print("  Install:  winget install --id Gyan.FFmpeg -e")
    def open_browser():
        time.sleep(1.2)
        webbrowser.open("http://localhost:5000")
    threading.Thread(target=open_browser, daemon=True).start()
    print(f"\n  Running at http://localhost:5000  (Ctrl+C to stop)\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
