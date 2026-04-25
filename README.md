# ★ Aria

**A beautiful local music player that runs in your browser.**

No subscriptions. No cloud. No account. Just your music library — organized, visualized, and playable from any device on your home network.

---

## Features

- **Space-themed UI** — live starfield, real-time audio visualizer, glassy panels
- **Smart library** — instant search, sort by title / artist / genre / most played
- **Genre buckets** — auto-organized into 10 genres (Pop, Rock, Hip-Hop, EDM, R&B, Jazz, Classical, Country, Reggae, Metal)
- **Playlists** — create, manage, drag-and-drop songs, right-click context menu
- **Liked songs** — heart your favorites; persists across sessions
- **Queue system** — "Up Next" panel, inject songs mid-queue
- **Album art** — embedded art shown in the player bar with pulse animation
- **Universal format support** — MP3, FLAC, WMA, AAC, OGG, WAV (WMA/AAC transcoded via FFmpeg)
- **Works everywhere** — any browser, any device on your local network
- **Keyboard shortcuts** — Space, ←/→, S, R, M, Q

---

## Quick Start (Windows .exe)

1. Download the latest `Aria.zip` from [Releases](../../releases/latest)
2. Unzip it anywhere
3. Drop your music files into the `Aria/` folder
4. Run `Aria.exe`
5. Your browser opens automatically at `http://localhost:5000`

> **WMA / AAC support:** Install FFmpeg for full format support:
> ```
> winget install --id Gyan.FFmpeg -e
> ```

---

## Run from Source

**Requirements:** Python 3.9+

```bash
git clone https://github.com/YOUR_USERNAME/aria.git
cd aria

pip install flask mutagen

# Copy your music files into the folder, then:
python app.py
```

Or use the included launcher:

```
music.bat
```

**Optional — add a global `music` command in PowerShell:**

```powershell
# Add to your PowerShell profile ($PROFILE):
function music {
    & "C:\path\to\aria\music.bat"
}
```

---

## Build the .exe yourself

```
build.bat
```

Requires PyInstaller (`pip install pyinstaller`). Output lands in `release/Aria/`.

---

## Format Support

| Format | Playback | Metadata | Album Art |
|--------|----------|----------|-----------|
| MP3    | ✓        | ✓        | ✓         |
| FLAC   | ✓        | ✓        | ✓         |
| WMA    | ✓ (FFmpeg) | ✓      | —         |
| AAC    | ✓ (FFmpeg) | ✓      | ✓         |
| OGG    | ✓        | ✓        | —         |
| WAV    | ✓        | —        | —         |
| M4A    | ✓        | ✓        | ✓         |

---

## License

MIT — free to use, modify, and distribute.
