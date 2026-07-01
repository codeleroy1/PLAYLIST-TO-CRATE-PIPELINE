"""
dj_pipeline.tagging

Writes Spotify metadata onto audio files.

HARD RULES — do not change without updating docs/TAG_RULES.md too:
  - BPM (TBPM) is NEVER written. Left for your DJ software / Mixed In Key.
  - Key (TKEY) is NEVER written. Left for your DJ software / Mixed In Key.
  - Genre is written EXACTLY as Spotify provides it. No normalization.
"""
from __future__ import annotations

import re

from mutagen.id3 import (
    ID3, ID3NoHeaderError,
    TIT2, TPE1, TPE2, TALB, TDRC, TCON, TPUB, TCOM, COMM,
)


def sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", str(name)).strip()[:100]


def get_primary_artist(artists_str: str) -> str:
    primary = artists_str.split(";")[0].strip()
    return re.split(r"\s+(?:feat\.|ft\.|featuring)\s+", primary, flags=re.IGNORECASE)[0].strip()


def build_comment(track: dict) -> str:
    sp_label = track.get("Record Label", "").strip()
    sp_uri = track.get("Track URI", "").strip()
    parts = []
    if sp_uri:
        parts.append(f"Spotify: {sp_uri}")
    if track.get("Explicit", "").strip():
        parts.append(f"Explicit: {track['Explicit'].strip()}")
    if track.get("Popularity", "").strip():
        parts.append(f"Popularity: {track['Popularity'].strip()}")
    if track.get("Energy", "").strip():
        parts.append(f"Energy: {track['Energy'].strip()}")
    if track.get("Danceability", "").strip():
        parts.append(f"Danceability: {track['Danceability'].strip()}")
    if track.get("Valence", "").strip():
        parts.append(f"Valence: {track['Valence'].strip()}")
    if track.get("Loudness", "").strip():
        parts.append(f"Loudness: {track['Loudness'].strip()} dB")
    if track.get("Speechiness", "").strip():
        parts.append(f"Speechiness: {track['Speechiness'].strip()}")
    if track.get("Acousticness", "").strip():
        parts.append(f"Acousticness: {track['Acousticness'].strip()}")
    if track.get("Liveness", "").strip():
        parts.append(f"Liveness: {track['Liveness'].strip()}")
    if track.get("Time Signature", "").strip():
        parts.append(f"Time Signature: {track['Time Signature'].strip()}/4")
    if track.get("Mode", "").strip():
        parts.append(f"Mode: {'Major' if track['Mode'].strip() == '1' else 'Minor'}")
    if sp_label:
        parts.append(f"Label: {sp_label}")
    if track.get("Added At", "").strip():
        parts.append(f"Added: {track['Added At'].strip()[:10]}")
    return " | ".join(parts)


def write_spotify_tags(filepath: str, track: dict) -> bool:
    """Write full Spotify metadata to an MP3. Never touches BPM or Key."""
    try:
        try:
            tags = ID3(filepath)
        except ID3NoHeaderError:
            tags = ID3()

        sp_artists = track["Artist Name(s)"].split(";")
        sp_artist = ", ".join(a.strip() for a in sp_artists)
        sp_aa = get_primary_artist(track["Artist Name(s)"])
        sp_title = track["Track Name"].strip()
        sp_album = track["Album Name"].strip()
        sp_year = track["Release Date"][:4] if track.get("Release Date") else ""
        sp_genres = track.get("Genres", "").strip()
        sp_label = track.get("Record Label", "").strip()
        sp_uri = track.get("Track URI", "").strip()
        comment = build_comment(track)

        tags.add(TIT2(encoding=3, text=sp_title))
        tags.add(TPE1(encoding=3, text=sp_artist))
        tags.add(TPE2(encoding=3, text=sp_aa))
        tags.add(TALB(encoding=3, text=sp_album))
        if sp_year:
            tags.add(TDRC(encoding=3, text=sp_year))
        if sp_genres:
            tags.add(TCON(encoding=3, text=sp_genres))
        if sp_label:
            tags.add(TPUB(encoding=3, text=sp_label))
        if comment:
            tags.add(COMM(encoding=3, lang="eng", desc="Spotify", text=comment))
        if sp_uri:
            tags.add(TCOM(encoding=3, text=sp_uri))

        # BPM (TBPM) and Key (TKEY) intentionally never written here.

        tags.save(filepath, v2_version=3)
        return True
    except Exception as e:
        print(f"    \u26a0\ufe0f  Tag error: {e}")
        return False


def write_easy_tags(filepath: str, track: dict) -> bool:
    """For non-MP3 files (M4A, AIFF, FLAC, etc.) — basic tags only."""
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(filepath, easy=True)
        if audio is None:
            return False
        sp_artists = track["Artist Name(s)"].split(";")
        audio["title"] = track["Track Name"].strip()
        audio["artist"] = ", ".join(a.strip() for a in sp_artists)
        audio["albumartist"] = get_primary_artist(track["Artist Name(s)"])
        audio["album"] = track["Album Name"].strip()
        if track.get("Release Date"):
            audio["date"] = track["Release Date"][:4]
        if track.get("Genres"):
            audio["genre"] = track["Genres"].strip()
        audio.save()
        return True
    except Exception as e:
        print(f"    \u26a0\ufe0f  Easy tag error: {e}")
        return False
