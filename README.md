# Exportify → 4K → DJ Library → Serato 4

Each playlist has a self-contained workspace beside its Exportify CSV. Part 1 matches existing library tracks and prepares a 4K import. Part 2 previews, then moves verified MP3 downloads into Artist/Album folders and adds the library paths to a nested Serato crate.

**Python 3.10+; macOS Serato 4 integration.** The database writer targets the schema observed in Serato DJ Pro 4.0.7. It is unofficial, checks the schema, backs up databases, and requires Serato to be closed. A successful database write is **not** a verified visible crate: reopen Serato and check its hierarchy and tracks.

## Start here

Install dependencies in a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

See [QUICKSTART.md](QUICKSTART.md) for the exact Leroy mapping and single-playlist commands.

Inventory every playlist (no music moves):

```sh
.venv/bin/python scripts/prepare_exportify.py \
  --exportify-root "/path/to/EXPORTIFY" \
  --library "/path/to/DJ Library" \
  --report "/path/to/inventory.json"
```

Add `--install --backup-existing` to copy both scripts, their Python package, and requirements beside each CSV. Changed local scripts are backed up before replacement; older JSONs remain intact. Every playlist receives its own `*_pipeline_config.json`. Preparation does not download or move music.

## The two parts

1. Run the copied `playlist_part1_get_urls.py` with the same virtual-environment Python. With one config beside the script, no arguments are needed. It finds that folder independently of the current working directory.
2. Review `*_pipeline_review.json`. Ready matches require artist, title and duration checks, but listening/version verification still matters. To approve a reviewed candidate, update its entry in `*_pipeline_youtube.json` with the selected watch URL, exact `yt_title`, and `status: "ready"`, then rerun Part 1.
3. Import `*_pipeline_4K_IMPORT.json` into 4K YouTube to MP3, or use the URL text file. **Set 4K's actual destination to this playlist's Downloads folder and verify it in the app.** Importing the JSON alone may not apply its outputDir.
4. Wait for the intended downloads to finish. Quit Serato. Run copied Part 2 without arguments to preview, then with `--apply` to execute.
5. Reopen Serato and verify the nested crate, library locations, missing-track count, and BPM/key analysis.

Part 2 never blindly empties Downloads: it removes each source only after payload and tag checks, and deletes the directory only if empty. Unknown files remain for review. Incomplete playlists receive explicit pending/review counts; they are not automatically complete.

## Files beside each CSV

| File | Purpose |
| --- | --- |
| `NAME_pipeline_config.json` | Canonical library and Serato paths; local workspace mapping |
| `NAME_pipeline_matched.json` | Existing library matches |
| `NAME_pipeline_youtube.json` | URL decisions and candidates |
| `NAME_pipeline_4K_IMPORT.json` / `4K_DOWNLOAD.txt` | 4K queue and URL export |
| `NAME_pipeline_review.json` | Tracks needing review |
| `NAME_pipeline_moves.json` | Recovery journal and audio fingerprints |
| `NAME_pipeline_part2.json` | Library paths, database result and unresolved items |
| `Downloads/` | Temporary download destination; removed only if empty |
| Both scripts, `dj_pipeline/`, `requirements.txt` | Runnable local bundle |

The `pipeline_` namespace preserves old Aug-26/legacy handoff files. Legacy cache files are not automatically trusted or overwritten. New Part 1 rebuilds its validated handoff.

## Safety and repeatability

- Existing library files are reused without retagging. Destination collisions stop rather than overwrite.
- Download mapping uses an exact normalized video title. Ambiguous titles stop; no loose word-overlap matching.
- Only MP3 downloads are processed; unmatched files are retained.
- Tags retain BPM and key; analysis remains in Serato.
- MP3 payload hashes exclude ID3 metadata, so adding tags does not falsely flag changed audio.
- Audio publication uses no-clobber linking from a verified staging file. A durable journal precedes source removal.
- Reruns append missing crate membership only, preserving other crates and existing members.
- An interrupted staging file or stale processing lock requires inspection before retry; do not delete original downloads to bypass an error.
- Never run two processes for one playlist, or open Serato during a Part 2 run.

## Tracking in Notion

Maintain one row per relative CSV path. Link it through a two-way DJ Crate relation. Track CSV, installed scripts, URL validation, downloads, verified library moves, empty-folder cleanup, database membership, visible Serato verification, and analysis separately. Counts in inventories are playlist memberships, not globally unique songs. Blank verified counts mean unknown.

The scripts produce evidence JSONs; **they do not silently update Notion**. Update Notion from those reports using the connected workspace tools. See [docs/PIPELINE_REFERENCE.md](docs/PIPELINE_REFERENCE.md).

## Tests

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Real MP3 transfer tests use ffmpeg-generated test audio and skip if ffmpeg is unavailable. Tests use temporary libraries/databases, never your live Serato database.

Older downloader/config/crate modules remain for historical compatibility, but the current two entrypoints use the workspace workflow above. Do not use legacy cleanup utilities for this mission.
