# Pipeline Reference

## Part 1 — `playlist_part1_get_urls.py`

```
python3 scripts/playlist_part1_get_urls.py --csv CSV --name NAME [options]
```

| Flag | Default | Description |
|---|---|---|
| `--csv` (repeatable) | *required* | Exportify CSV path. Repeat to merge several playlists into one session/crate, deduplicated by Spotify Track URI. |
| `--name` | *required* | Playlist/crate name. Becomes the session ID (slugified) and the eventual crate/playlist filename. |
| `--downloader` | `ytdlp` | `ytdlp` (auto-download) or `manual`/`4k` (URL list only). See `docs/DOWNLOADERS.md`. |
| `--download-folder` | `~/Desktop/4k YOUTUBE TO MP3` | Where downloaded/converted audio lands. |
| `--library` | `~/Music/DJ Library` | Your existing DJ library root, scanned for tracks you already own. |
| `--data-dir` | `~/.dj_pipeline/sessions` | Where session handoff JSON files are kept (deliberately off your Desktop). |
| `--search-delay` | `1.0` | Seconds between YouTube searches — raise this if you're getting rate-limited. |

**Outputs** (in `--data-dir`, named by session slug):
- `<slug>_matched.json` — tracks already in your library
- `<slug>_youtube.json` — resolved YouTube results for missing tracks
- `<slug>_config.json` — session config Part 2 reads automatically
- `<slug>_4K_DOWNLOAD.txt` — only written when `--downloader manual` is used

## Part 2 — `playlist_part2_process.py`

```
python3 scripts/playlist_part2_process.py --name NAME [options]
```

| Flag | Default | Description |
|---|---|---|
| `--name` | most recent session | Which session to process. Omit it to auto-pick your last Part 1 run. |
| `--dj-software` | `serato` | `serato`, `rekordbox`, `traktor`, `engine`, `virtualdj`, or `m3u`. See `docs/DJ_SOFTWARE.md`. |
| `--data-dir` | `~/.dj_pipeline/sessions` | Must match what Part 1 used. |
| `--skip-normalize` | off | Skip the `mp3gain` volume-normalization pass. |
| `--crate-output-dir` | Serato Subcrates folder, or `<library>/Playlists` for others | Override where the crate/playlist file is written. |

**What it does, in order:**
1. Scans the download folder, deletes obviously-bad versions (music videos, bass-boosted, sped up, etc.)
2. Fuzzy-matches downloaded files to Spotify rows from Part 1
3. Writes full Spotify metadata as ID3 tags, renames to `Artist - Title.mp3`, files into `Library/Artist/Album/`
4. Re-tags every track Part 1 found already in your library, so metadata stays fresh even for old files
5. Normalizes volume with `mp3gain` (unless `--skip-normalize`)
6. Builds a crate/playlist using the selected DJ-software backend

## Cleanup — `cleanup_duplicates.py`

Removes `_new`/`_downloaded` suffix duplicates created when Part 2 found a filename collision. Defaults to only touching files modified today.

```bash
python3 scripts/cleanup_duplicates.py --library ~/Music/DJ\ Library
python3 scripts/cleanup_duplicates.py --dry-run          # preview only
python3 scripts/cleanup_duplicates.py --all-dates         # ignore the date guard
```

## Tag rules

| Tag | ID3 frame | Rule |
|---|---|---|
| Title | TIT2 | Spotify Track Name, verbatim |
| Artist | TPE1 | All artists, comma-separated |
| Album Artist | TPE2 | Primary artist only, features stripped |
| Album | TALB | Spotify Album Name |
| Year | TDRC | First 4 chars of Release Date |
| Genre | TCON | **Exactly as Spotify provides it — never normalized or remapped** |
| Record Label | TPUB | Spotify Record Label |
| Spotify URI | TCOM | Spotify Track URI (repurposed field, intentional) |
| Comment | COMM (desc="Spotify") | Energy, Danceability, Valence, Loudness, Speechiness, Acousticness, Liveness, Time Signature, Mode, Explicit, Popularity, Date Added, Label |
| **BPM** | TBPM | **Never written.** Left for your DJ software / Mixed In Key to analyze from the actual audio. |
| **Key** | TKEY | **Never written.** Same reasoning — locally analyzed values are more reliable than Spotify's estimate. |

This is enforced in `dj_pipeline/tagging.py` — there is no code path in this repo that writes `TBPM` or `TKEY`.

## Serato crate binary format

```python
import struct

def encode_str(s):
    return s.encode('utf-16-be')

def make_field(tag, data):
    return tag.encode('ascii') + struct.pack('>I', len(data)) + data

def make_serato_crate(track_paths):
    version = '1.0/Serato ScratchLive Crate'
    buf = b'vrsn' + struct.pack('>I', len(version)*2) + encode_str(version)
    for path in track_paths:
        if path.startswith('/'):
            path = path[1:]  # no leading slash
        buf += make_field('otrk', make_field('ptrk', encode_str(path)))
    return buf
```

## YouTube match scoring (both downloader backends use this)

**Hard reject** (score = -999) if the title contains: official video, music video, clean/radio edit, instrumental, karaoke, snippet, reaction, live recordings, boiler room, bass boost/8D/slowed/reverb/nightcore/sped-up/432hz, etc. Lyric videos are explicitly **acceptable**.

**Scoring:**
- Duration within 5s of Spotify: +50 · within 15s: +25 · within 30s: +10 · further off: −20
- Artist name in title: +15 · in channel name: +20
- Each matched title word: +10
- "official audio"/"lyrics"/"explicit"/"hq": +20
- VEVO channel: +15
- "remix"/"amapiano"/"bounce"/"flip" in title: −25
- **HIGH confidence:** score ≥ 40 · **LOW confidence:** 0 < score < 40

Search queries tried in order: `Artist Title official audio` → `Artist Title lyrics` → `Artist Title`.

## Troubleshooting

**Crate shows in Serato but is empty**
Paths in the crate don't match actual file locations — re-run Part 2, it rebuilds the crate from a fresh filesystem scan.

**Tags not showing in Serato**
Select all tracks in the crate → right-click → Rescan ID Tags.

**`_new`/`_downloaded` files appearing**
Run `scripts/cleanup_duplicates.py`.

**yt-dlp search returns nothing**
Don't use `youtube-search-python` — it has known httpx proxy conflicts. This pipeline shells out to `yt-dlp` directly via `python -m yt_dlp`, which is the supported path.

**GUI downloader pulls a whole playlist instead of one track**
You pasted a YouTube search URL instead of a direct watch URL. The `manual` downloader backend only ever writes `youtube.com/watch?v=...` URLs — if you're seeing something else, check what generated the URL.

**`mp3gain: command not found`**
`brew install mp3gain` (macOS) or `apt install mp3gain` (Linux). Part 2 will skip normalization gracefully rather than crash if it's missing.

**`ffmpeg` not found (yt-dlp can't convert to MP3)**
`brew install ffmpeg` / `apt install ffmpeg`.
