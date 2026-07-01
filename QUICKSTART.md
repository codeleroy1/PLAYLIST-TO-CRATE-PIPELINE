# Quick Start

This walks you from "I found this on GitHub" to a tagged crate loaded in your DJ software.

## 1. Get the code

Pick one:

**Option A — Download ZIP (no git required)**
On the repo's GitHub page: **Code → Download ZIP**, then unzip it and open a terminal in that folder.

**Option B — Clone with git**
```bash
git clone https://github.com/YOUR_USERNAME/dj-leroy-pipeline.git
cd dj-leroy-pipeline
```

**Option C — Just grab one script**
Each script in `scripts/` imports from `dj_pipeline/`, so if you only want one file you still need the whole `dj_pipeline/` folder alongside it. Easiest to just use Option A or B.

## 2. Prerequisites

- **Python 3.9+**
- **ffmpeg** — required by yt-dlp to convert audio to MP3
- **mp3gain** — optional, used for volume normalization (Part 2 skips it gracefully if missing)

Install on macOS:
```bash
brew install mp3gain ffmpeg
```
Install on Ubuntu/Debian:
```bash
sudo apt install mp3gain ffmpeg
```
Install on Windows: grab [ffmpeg](https://ffmpeg.org/download.html) and [mp3gain](http://mp3gain.sourceforge.net/) binaries and put them on your `PATH`.

## 3. Install Python dependencies

```bash
pip install -r requirements.txt --break-system-packages
```
(Or use a virtual environment: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.)

Verify:
```bash
python3 -c "import mutagen; print('mutagen ok')"
yt-dlp --version
ffmpeg -version | head -1
mp3gain --version
```

## 4. First run — using the included example

The repo ships a mock Exportify CSV at `examples/sample_playlist_export.csv` with 5 fictional tracks, so you can try the whole pipeline before pointing it at your real library.

```bash
python3 scripts/playlist_part1_get_urls.py \
  --csv examples/sample_playlist_export.csv \
  --name "My First Crate" \
  --downloader ytdlp \
  --library ./demo_library \
  --download-folder ./demo_downloads
```

This scans `./demo_library` (empty on a fresh clone, so everything will show as "missing"), searches YouTube for each track, downloads and converts the best match to MP3, and saves a session file describing what happened.

Then:
```bash
python3 scripts/playlist_part2_process.py --name "My First Crate" --dj-software serato
```

This tags every downloaded file with the CSV's Spotify metadata, files it into `./demo_library/Artist/Album/Title.mp3`, and writes a crate file (default: your Serato Subcrates folder — override with `--crate-output-dir` for a demo run, e.g. `--crate-output-dir ./demo_crates`).

## 5. Real usage — your own playlist

1. Export a playlist from [exportify.net](https://exportify.net) (log in with Spotify → **Export All** or export one playlist → you get a CSV).
2. Run Part 1, pointing `--library` at your actual DJ library folder:
   ```bash
   python3 scripts/playlist_part1_get_urls.py \
     --csv ~/Downloads/My_Playlist.csv \
     --name "My Playlist" \
     --downloader ytdlp \
     --library ~/Music/DJ\ Library
   ```
3. If you used `--downloader manual` instead, open the generated `*_4K_DOWNLOAD.txt` and paste each URL into your downloader **one at a time** (pasting multiple URLs at once into some GUI tools makes them treat it as a playlist).
4. Run Part 2 with your DJ software of choice:
   ```bash
   python3 scripts/playlist_part2_process.py --name "My Playlist" --dj-software serato
   ```
5. Open your DJ software, find the new crate/playlist, and run its "analyze" step to get BPM and Key.

## Choosing a downloader

| Flag | What it does | When to use it |
|---|---|---|
| `--downloader ytdlp` (default) | Searches YouTube and downloads/converts automatically. No copy-pasting. | Most people, most of the time. |
| `--downloader manual` (alias `4k`) | Searches and scores candidates, writes a URL list, but downloads nothing. | You want to use 4K YouTube to MP3 or another GUI tool specifically, or your network blocks yt-dlp downloads. |

## Choosing a DJ-software target

| Flag | Output | Notes |
|---|---|---|
| `--dj-software serato` (default) | Native binary `.crate` | Written straight to your Serato `Subcrates` folder. |
| `--dj-software rekordbox` | `.m3u8` | Rekordbox: File → Import Playlist. |
| `--dj-software traktor` | `.m3u8` | Drag into a Traktor playlist folder. |
| `--dj-software engine` | `.m3u8` | Engine DJ: File → Import → Playlist File. |
| `--dj-software virtualdj` | `.m3u8` | VirtualDJ reads `.m3u8` natively. |
| `--dj-software m3u` | `.m3u8` | Generic fallback for anything else that reads M3U. |

## Troubleshooting

See [docs/PIPELINE_REFERENCE.md](docs/PIPELINE_REFERENCE.md#troubleshooting).
