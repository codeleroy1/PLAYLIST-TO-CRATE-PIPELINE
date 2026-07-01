"""
dj_pipeline.matching

Fuzzy text matching between Spotify track data, filenames on disk, and
YouTube search results. Shared by both pipeline steps so "is this track
already in my library" and "does this download match this Spotify track"
use one consistent definition.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict

AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aiff", ".flac"}

EDIT_WORDS = [
    "remix", "edit", "amapiano", "afro", "bounce", "flip",
    "rework", "mashup", "blend", "jersey club", "moombah",
]

BAD_DOWNLOAD_KEYWORDS = [
    "official video", "official music video", "music video", "visualizer",
    "bass boost", "8d audio", "slowed", "reverb", "karaoke", "instrumental",
    "clean version", "clean edit", "radio edit", "432hz", "sped up", "nightcore",
]


def clean_str(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\(feat\..*?\)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\[.*?\]", "", s)
    s = re.sub(r"[^\w\s]", "", s)
    return s.strip()


def clean_downloaded_name(fname: str) -> str:
    name = os.path.splitext(fname)[0]
    for pattern in [
        r"\(Official Audio\)", r"\[Official Audio\]",
        r"\(Audio\)", r"\[Audio\]",
        r"\(Lyric Video\)", r"\[Lyric Video\]",
        r"\(Lyrics\)", r"\[Lyrics\]",
        r"\(Official Lyric Video\)", r"\(Official\)",
        r"\(HD\)", r"\[HD\]", r"\|\s*.*$",
        r"HQ\s*\(Audio\)", r"\(Audio\s*\+\s*DOWNLOAD\)",
    ]:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE).strip()
    return name.strip(" -_")


def is_edit(fname: str) -> bool:
    return any(w in fname.lower() for w in EDIT_WORDS)


def scan_library(dj_library: str) -> defaultdict:
    """Index every audio file in the library by a truncated cleaned key,
    for fast fuzzy lookups."""
    file_index = defaultdict(list)
    for dirpath, _dirs, files in os.walk(dj_library):
        for fname in files:
            if os.path.splitext(fname)[1].lower() in AUDIO_EXTS:
                norm = clean_str(os.path.splitext(fname)[0])
                file_index[norm[:25]].append(os.path.join(dirpath, fname))
    return file_index


def find_in_library(track: dict, file_index: dict) -> str | None:
    """Return the best existing-library path for a Spotify track row, or
    None if it isn't already downloaded. Prefers non-edit versions."""
    name = track["Track Name"]
    primary = track["Artist Name(s)"].split(";")[0].strip()
    nt, na = clean_str(name), clean_str(primary)

    candidates = []
    for key, fpaths in file_index.items():
        if nt[:15] in key or key[:15] in nt:
            if not na or na[:10] in key or key[:10] in na:
                candidates.extend(fpaths)

    originals = [p for p in candidates if not is_edit(os.path.basename(p))]
    if originals:
        return originals[0]
    return candidates[0] if candidates else None


def match_download_to_track(fname: str, spotify_lookup: dict, min_overlap: int = 2):
    """Fuzzy-match a downloaded filename against a {key: track} lookup
    built from clean_str(f'{artist} {title}')[:35]."""
    clean_name = clean_downloaded_name(fname)
    clean_key = clean_str(clean_name)[:35]
    fw = set(k for k in clean_key.split() if len(k) > 2)

    best_match, best_overlap = None, 0
    for key, track in spotify_lookup.items():
        kw = set(k for k in key.split() if len(k) > 2)
        overlap = len(kw & fw)
        if overlap > best_overlap and overlap >= min_overlap:
            best_overlap, best_match = overlap, track
    return best_match, clean_name
