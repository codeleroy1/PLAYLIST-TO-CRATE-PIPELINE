#!/usr/bin/env python3
"""
playlist_part1_get_urls.py — Step 1 of 2

Matches an Exportify playlist CSV (or several) against your existing DJ
Library, then resolves whatever's missing using the downloader backend
you choose (fully automated yt-dlp, or a manual URL list for 4K / any
other GUI downloader).

No script editing required — everything is a flag. Run with -h to see
every option and its default.

Examples:
  # One CSV, fully automated download
  python3 scripts/playlist_part1_get_urls.py \\
      --csv ~/Desktop/EXPORTIFY/HOUSE_DANCE/My_Playlist.csv \\
      --name "My Playlist" --downloader ytdlp

  # Several CSVs merged into one crate, manual 4K workflow (old default)
  python3 scripts/playlist_part1_get_urls.py \\
      --csv playlist1.csv --csv playlist2.csv \\
      --name "Summer Mix" --downloader manual
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dj_pipeline.config import load_or_create_config, DEFAULTS
from dj_pipeline.downloaders import get_downloader, DOWNLOADERS
from dj_pipeline.matching import scan_library, find_in_library


def parse_args():
    p = argparse.ArgumentParser(
        description="Step 1: match a Spotify/Exportify playlist against your library "
                     "and resolve missing tracks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--csv", action="append", required=True, dest="csvs",
                    help="Exportify CSV path. Repeat --csv to merge several playlists "
                         "into one crate/session.")
    p.add_argument("--name", required=True,
                    help="Playlist / crate name. Becomes the session ID and the "
                         "eventual crate/playlist file name.")
    p.add_argument("--downloader", default="ytdlp", choices=sorted(set(DOWNLOADERS.keys())),
                    help="How missing tracks get fetched. 'ytdlp' = fully automatic "
                         "(default). 'manual' (alias '4k') = search only, writes a URL "
                         "list for you to paste into 4K YouTube to MP3 or similar.")
    p.add_argument("--download-folder", default=None,
                    help=f"Where downloads land. Default: {DEFAULTS['download_folder']}")
    p.add_argument("--library", default=None,
                    help=f"Your DJ library root. Default: {DEFAULTS['dj_library']}")
    p.add_argument("--data-dir", default=None,
                    help=f"Where session handoff files are kept. Default: {DEFAULTS['data_dir']}")
    p.add_argument("--search-delay", type=float, default=1.0,
                    help="Seconds to wait between YouTube searches (be polite). Default: 1.0")
    return p.parse_args()


def load_playlist(csv_paths):
    seen_uris = set()
    playlist = []
    for csv_path in csv_paths:
        path = Path(csv_path).expanduser()
        if not path.exists():
            print(f"\u26a0\ufe0f  CSV not found, skipping: {path}")
            continue
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                uri = row.get("Track URI", "")
                key = uri if uri else f"{row.get('Artist Name(s)', '')}{row.get('Track Name', '')}"
                if key not in seen_uris:
                    seen_uris.add(key)
                    playlist.append(row)
    return playlist


def main():
    args = parse_args()
    cfg = load_or_create_config(
        playlist_name=args.name,
        csv_paths=args.csvs,
        download_folder=args.download_folder,
        dj_library=args.library,
        data_dir=args.data_dir,
    )

    print(f"\n{'=' * 60}\nPART 1: {cfg.playlist_name}\n{'=' * 60}\n")
    print(f"Session ID:     {cfg.playlist_slug}")
    print(f"Downloader:     {args.downloader}")
    print(f"Downloads from: {cfg.download_folder}")
    print(f"Library:        {cfg.dj_library}\n")

    playlist = load_playlist(cfg.csv_paths)
    print(f"Total unique tracks across all CSVs: {len(playlist)}")

    print("\nScanning DJ Library...")
    file_index = scan_library(cfg.dj_library)

    matched, missing = [], []
    for track in playlist:
        artist = track["Artist Name(s)"].split(";")[0].strip()
        name = track["Track Name"]
        found = find_in_library(track, file_index)
        if found:
            matched.append({"track": track, "path": found})
            print(f"  \u2705 {artist} - {name}")
        else:
            missing.append(track)
            print(f"  \u274c {artist} - {name}")

    print(f"\nIn library: {len(matched)} | Missing: {len(missing)}\n")

    downloader = get_downloader(args.downloader)
    print(f"Resolving {len(missing)} missing tracks via '{downloader.name}'...\n")
    result = downloader.resolve_missing(missing, cfg.download_folder, args.search_delay)

    high_conf = result["high_confidence"]
    low_conf = result["low_confidence"]
    not_found = result["not_found"]

    # Save handoff data for Part 2
    import json
    with open(cfg.matched_json, "w") as f:
        json.dump([{"path": m["path"], "track": m["track"]} for m in matched], f, indent=2)
    with open(cfg.youtube_json, "w") as f:
        json.dump(
            [{"url": e["url"], "yt_title": e["yt_title"], "score": e["score"], "track": e["track"]}
             for e in high_conf + low_conf],
            f, indent=2,
        )

    # Only write a manual URL list if the downloader didn't already fetch files
    if not result["auto_downloaded"]:
        with open(cfg.download_url_list, "w", encoding="utf-8") as f:
            f.write(f"# {cfg.playlist_name} \u2014 paste URLs into your downloader ONE AT A TIME\n")
            f.write(f"# Save downloads to: {cfg.download_folder}\n\n")
            f.write(f"# \u2500\u2500 HIGH CONFIDENCE ({len(high_conf)} tracks) \u2500\u2500\n\n")
            for e in high_conf:
                f.write(f"# {e['artist']} - {e['title']}\n# YouTube: {e['yt_title']}\n{e['url']}\n\n")
            if low_conf:
                f.write(f"\n# \u2500\u2500 LOW CONFIDENCE ({len(low_conf)} tracks) \u2014 review first \u2500\u2500\n\n")
                for e in low_conf:
                    f.write(f"# {e['artist']} - {e['title']}\n# YouTube: {e['yt_title']} [score:{e['score']}]\n{e['url']}\n\n")

    print(f"\n{'=' * 60}\nSUMMARY\n{'=' * 60}")
    print(f"Already in library:   {len(matched)}")
    print(f"HIGH confidence:      {len(high_conf)}")
    print(f"LOW confidence:       {len(low_conf)}")
    print(f"Not found:            {len(not_found)}")
    print(f"\nNEXT STEP:\n{result['next_step']}")
    if not result["auto_downloaded"]:
        print(f"\n\U0001F4C4 URL list: {cfg.download_url_list}")
    print(f"\nThen run Part 2:\n  python3 scripts/playlist_part2_process.py --name \"{cfg.playlist_name}\"\n")


if __name__ == "__main__":
    main()
