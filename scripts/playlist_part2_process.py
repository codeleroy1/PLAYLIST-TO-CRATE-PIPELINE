#!/usr/bin/env python3
"""
playlist_part2_process.py — Step 2 of 2

Tags every downloaded file with full Spotify metadata, files it into your
DJ Library, refreshes tags on already-owned matches, normalizes volume,
and builds a crate/playlist in whichever DJ software you use.

Auto-reads the session saved by Part 1 (by playlist name / session ID) —
no manual config editing needed.

Examples:
  python3 scripts/playlist_part2_process.py --name "My Playlist"
  python3 scripts/playlist_part2_process.py --name "Summer Mix" --dj-software rekordbox
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dj_pipeline.config import PipelineConfig, DEFAULTS, find_latest_session, slugify
from dj_pipeline.crate_writers import get_crate_writer, CRATE_WRITERS
from dj_pipeline.matching import AUDIO_EXTS, BAD_DOWNLOAD_KEYWORDS, clean_str, match_download_to_track
from dj_pipeline.tagging import sanitize, get_primary_artist, write_spotify_tags, write_easy_tags


def parse_args():
    p = argparse.ArgumentParser(
        description="Step 2: tag, organize, and build a crate from Part 1's output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--name", default=None,
                    help="Playlist name used in Part 1. If omitted, uses the most "
                         "recently touched session.")
    p.add_argument("--dj-software", default="serato", choices=sorted(set(CRATE_WRITERS.keys())),
                    help="Which DJ software to build a crate/playlist for. Default: serato. "
                         "Rekordbox/Traktor/Engine DJ/VirtualDJ all use standard .m3u8.")
    p.add_argument("--data-dir", default=None,
                    help=f"Where session handoff files are kept. Default: {DEFAULTS['data_dir']}")
    p.add_argument("--skip-normalize", action="store_true",
                    help="Skip the mp3gain volume-normalization pass.")
    p.add_argument("--crate-output-dir", default=None,
                    help="Override where the crate/playlist file is written "
                         "(default: your configured Serato Subcrates folder, or "
                         "<library>/Playlists for other software).")
    return p.parse_args()


def main():
    args = parse_args()
    data_dir = args.data_dir or DEFAULTS["data_dir"]

    slug = slugify(args.name) if args.name else find_latest_session(data_dir)
    if not slug:
        print("\u274c No session found. Run playlist_part1_get_urls.py first, "
              "or pass --name to point at a specific session.")
        sys.exit(1)

    cfg = PipelineConfig.load(slug, data_dir)

    print(f"\n{'=' * 60}\nPART 2: {cfg.playlist_name}\n{'=' * 60}")
    print(f"Downloads from: {cfg.download_folder}")
    print(f"Library:        {cfg.dj_library}")
    print(f"DJ software:    {args.dj_software}\n")

    with open(cfg.matched_json) as f:
        matched_data = json.load(f)
    with open(cfg.youtube_json) as f:
        youtube_data = json.load(f)

    print(f"Library matches from Part 1: {len(matched_data)}")
    print(f"Tracks expected from downloads: {len(youtube_data)}")

    # ── Scan download folder, strip bad versions ──────────────────────
    print("\nScanning download folder...")
    if not os.path.exists(cfg.download_folder):
        print(f"\u274c Download folder not found: {cfg.download_folder}")
        sys.exit(1)

    downloaded_files, removed_bad = [], []
    for dirpath, _dirs, files in os.walk(cfg.download_folder):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in AUDIO_EXTS:
                continue
            fpath = os.path.join(dirpath, fname)
            if any(bad in fname.lower() for bad in BAD_DOWNLOAD_KEYWORDS):
                os.remove(fpath)
                removed_bad.append(fname)
                print(f"  \U0001F5D1\ufe0f  Removed bad version: {fname[:60]}")
            else:
                downloaded_files.append(fpath)

    print(f"  Clean files: {len(downloaded_files)}")
    if removed_bad:
        print(f"  Removed bad versions: {len(removed_bad)}")

    # ── Match downloads to Spotify rows ────────────────────────────────
    print("\nMatching downloads to Spotify data...")
    spotify_lookup = {}
    for entry in youtube_data:
        track = entry["track"]
        artist = track["Artist Name(s)"].split(";")[0].strip()
        title = track["Track Name"].strip()
        key = clean_str(f"{artist} {title}")[:35]
        spotify_lookup[key] = track

    matched_downloads, unmatched_downloads = [], []
    for fpath in downloaded_files:
        fname = os.path.basename(fpath)
        best_match, clean_name = match_download_to_track(fname, spotify_lookup, min_overlap=2)
        if best_match:
            matched_downloads.append({"path": fpath, "track": best_match})
        else:
            unmatched_downloads.append({"path": fpath, "clean_name": clean_name})

    print(f"  Matched to Spotify: {len(matched_downloads)}")
    print(f"  No Spotify match:   {len(unmatched_downloads)}")

    # ── Tag + rename + move into library ───────────────────────────────
    print("\nTagging and moving files into DJ Library...")
    newly_added = []

    for item in matched_downloads:
        fpath, track = item["path"], item["track"]
        if not os.path.exists(fpath):
            continue
        sp_artist = track["Artist Name(s)"].split(";")[0].strip()
        sp_title = track["Track Name"].strip()
        sp_album = track["Album Name"].strip()
        sp_aa = get_primary_artist(track["Artist Name(s)"])

        new_fname = sanitize(f"{sp_artist} - {sp_title}.mp3")
        dest_dir = os.path.join(cfg.dj_library, sanitize(sp_aa), sanitize(sp_album) if sp_album else "_Singles")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, new_fname)
        if os.path.exists(dest_path):
            dest_path = os.path.join(dest_dir, sanitize(f"{sp_artist} - {sp_title}_downloaded.mp3"))

        shutil.copy2(fpath, dest_path)
        success = write_spotify_tags(dest_path, track)
        newly_added.append(dest_path)
        print(f"  \u2705 {sp_artist} - {sp_title} [{'tagged' if success else 'tag error'}]")

    for item in unmatched_downloads:
        fpath, clean_name = item["path"], item["clean_name"]
        best_match, _ = match_download_to_track(os.path.basename(fpath), spotify_lookup, min_overlap=1)
        if best_match:
            sp_artist = best_match["Artist Name(s)"].split(";")[0].strip()
            sp_title = best_match["Track Name"].strip()
            sp_album = best_match["Album Name"].strip()
            sp_aa = get_primary_artist(best_match["Artist Name(s)"])
            new_fname = sanitize(f"{sp_artist} - {sp_title}.mp3")
            dest_dir = os.path.join(cfg.dj_library, sanitize(sp_aa), sanitize(sp_album) if sp_album else "_Singles")
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, new_fname)
            if os.path.exists(dest_path):
                dest_path = os.path.join(dest_dir, sanitize(f"{sp_artist} - {sp_title}_downloaded.mp3"))
            shutil.copy2(fpath, dest_path)
            success = write_spotify_tags(dest_path, best_match)
            newly_added.append(dest_path)
            print(f"  \u2705 (2nd pass) {sp_artist} - {sp_title} [{'tagged' if success else 'tag error'}]")
        else:
            dest_dir = os.path.join(cfg.dj_library, "Unknown Artist", "_Singles")
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, sanitize(clean_name) + ".mp3")
            shutil.copy2(fpath, dest_path)
            newly_added.append(dest_path)
            print(f"  \u26a0\ufe0f  Unmatched: {clean_name[:60]}")

    print(f"\n  Tagged & moved: {len(matched_downloads)}")
    print(f"  Unmatched moved: {len(unmatched_downloads)}")

    # ── Refresh tags on existing library matches ───────────────────────
    print(f"\nRefreshing tags on {len(matched_data)} existing library matches...")
    library_index = {}
    for dirpath, _dirs, files in os.walk(cfg.dj_library):
        for fname in files:
            if os.path.splitext(fname)[1].lower() in AUDIO_EXTS:
                library_index[fname.lower()] = os.path.join(dirpath, fname)

    tag_updated = tag_skipped = tag_not_found = 0
    for m in matched_data:
        fpath, track = m["path"], m["track"]
        artist = track["Artist Name(s)"].split(";")[0].strip()
        title = track["Track Name"].strip()

        if not os.path.exists(fpath):
            fpath = library_index.get(os.path.basename(fpath).lower())
        if not fpath or not os.path.exists(fpath):
            print(f"  \u26a0\ufe0f  Not found: {artist} - {title}")
            tag_not_found += 1
            continue

        ext = os.path.splitext(fpath)[1].lower()
        success = write_spotify_tags(fpath, track) if ext == ".mp3" else write_easy_tags(fpath, track)
        if success:
            tag_updated += 1
            print(f"  \U0001F3F7\ufe0f  {artist} - {title}")
        else:
            tag_skipped += 1

    print(f"\n  \u2705 Tags refreshed: {tag_updated}")
    if tag_skipped:
        print(f"  \u26a0\ufe0f  Tag errors:    {tag_skipped}")
    if tag_not_found:
        print(f"  \u274c Not found:      {tag_not_found}")

    # ── Volume normalize ────────────────────────────────────────────────
    if not args.skip_normalize:
        print("\nNormalizing volume with mp3gain...")
        mp3s = [p for p in newly_added if p.endswith(".mp3") and os.path.exists(p)]
        if mp3s and shutil.which("mp3gain"):
            for i in range(0, len(mp3s), 50):
                batch = mp3s[i:i + 50]
                subprocess.run(["mp3gain", "-r", "-k", "-s", "i"] + batch, capture_output=True)
                print(f"  Batch {i // 50 + 1} done ({len(batch)} files)")
            print(f"  \u2705 Normalized {len(mp3s)} files")
        elif mp3s:
            print("  \u26a0\ufe0f  mp3gain not found on PATH — skipping normalization "
                  "(install with `brew install mp3gain` or `apt install mp3gain`)")
        else:
            print("  No new MP3s to normalize")

    # ── Build crate / playlist for chosen DJ software ──────────────────
    print(f"\nBuilding {args.dj_software} crate/playlist: {cfg.playlist_name}...")

    file_index2 = {}
    for dirpath, _dirs, files in os.walk(cfg.dj_library):
        for fname in files:
            if os.path.splitext(fname)[1].lower() in AUDIO_EXTS:
                file_index2[fname.lower()] = os.path.join(dirpath, fname)

    crate_paths = []
    for m in matched_data:
        p = m["path"]
        if os.path.exists(p):
            crate_paths.append(p)
        else:
            found = file_index2.get(os.path.basename(p).lower())
            if found:
                crate_paths.append(found)
    for p in newly_added:
        if os.path.exists(p) and p not in crate_paths:
            crate_paths.append(p)

    writer = get_crate_writer(args.dj_software)
    output_dir = args.crate_output_dir or (
        cfg.serato_crates if args.dj_software == "serato"
        else os.path.join(cfg.dj_library, "Playlists")
    )
    crate_path = writer.write(crate_paths, cfg.playlist_name, output_dir)
    print(f"  \u2705 {writer.post_instructions(crate_path)}")

    print(f"""
{'=' * 60}
DONE — {cfg.playlist_name}
{'=' * 60}
Already in library (re-tagged): {len(matched_data)}
Downloaded & added:              {len(newly_added)}
Total in crate/playlist:         {len(crate_paths)}

Tags written from Spotify (ALL tracks):
  \u2705 Title, Artist (all features), Album Artist (primary)
  \u2705 Album, Year, Genre (exactly as Spotify)
  \u2705 Record Label (TPUB), Spotify URI (TCOM)
  \u2705 Comment: Energy, Danceability, Valence, Loudness,
              Speechiness, Acousticness, Liveness,
              Time Signature, Mode, Explicit,
              Popularity, Date Added, Label
  \u23ed\ufe0f  BPM — left for your DJ software / Mixed In Key
  \u23ed\ufe0f  Key — left for your DJ software / Mixed In Key
{'=' * 60}
""")


if __name__ == "__main__":
    main()
