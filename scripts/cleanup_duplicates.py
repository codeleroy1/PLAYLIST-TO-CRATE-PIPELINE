#!/usr/bin/env python3
"""
cleanup_duplicates.py

Removes '_new' / '_downloaded' duplicate suffixes created when a track
already existed in the library under a slightly different filename.
Only touches files modified today by default, so it's safe to run after
every session without clobbering older library files.

Usage:
  python3 scripts/cleanup_duplicates.py
  python3 scripts/cleanup_duplicates.py --library ~/Music/DJ\\ Library --all-dates
"""
import argparse
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dj_pipeline.config import DEFAULTS


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--library", default=DEFAULTS["dj_library"], help="DJ library root to clean")
    p.add_argument("--all-dates", action="store_true",
                    help="Clean matching files regardless of modification date "
                         "(use with care — reviews nothing, just deletes+renames)")
    p.add_argument("--dry-run", action="store_true", help="Print what would happen, change nothing")
    args = p.parse_args()

    library = Path(args.library).expanduser()
    today = date.today()
    deleted, renamed = 0, 0

    for dirpath, _dirs, files in os.walk(library):
        for fname in files:
            lower = fname.lower()
            if "_new.mp3" not in lower and "_downloaded.mp3" not in lower:
                continue
            fpath = os.path.join(dirpath, fname)
            if not args.all_dates and date.fromtimestamp(os.path.getmtime(fpath)) != today:
                continue

            original_fname = fname.replace("_new.mp3", ".mp3").replace("_downloaded.mp3", ".mp3")
            original_path = os.path.join(dirpath, original_fname)

            if args.dry_run:
                print(f"  [dry-run] would replace {original_fname} with {fname}")
                continue

            if os.path.exists(original_path):
                os.remove(original_path)
                deleted += 1
            os.rename(fpath, original_path)
            renamed += 1
            print(f"  \u2705 {original_fname}")

    print(f"\nDeleted old: {deleted} | Renamed: {renamed}")


if __name__ == "__main__":
    main()
