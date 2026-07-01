"""
dj_pipeline.downloaders

Pluggable "how do tracks actually get onto disk" backends.

Two strategies ship out of the box:

  ytdlp   — fully automated. yt-dlp searches AND downloads AND converts to
            mp3 directly into your download folder. No copy/paste. This is
            the recommended default for new users.

  manual  — the original workflow: yt-dlp only *searches and scores*
            candidates, writes a text file of watch URLs, and you paste
            them one at a time into whatever GUI downloader you use (4K
            YouTube to MP3, 4K Video Downloader, JDownloader, etc). Use
            this if you specifically want 4K's own audio normalization,
            or you're on a network where yt-dlp downloads are blocked but
            a browser-based tool isn't.

Both share the same search/scoring logic so match quality is identical
either way — the only difference is who actually pulls the bytes down.

Adding a new downloader: subclass BaseDownloader, implement
`resolve_missing()`, and register it in DOWNLOADERS at the bottom.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

EDIT_WORDS = [
    "remix", "edit", "amapiano", "afro", "bounce", "flip",
    "rework", "mashup", "blend", "jersey club", "moombah",
]

BAD_TITLE_WORDS = [
    "official video", "official music video", "(mv)", "[mv]", "music video",
    "clean version", "clean edit", "radio edit", "radio version",
    "(clean", "clean)", "instrumental", "karaoke", "snippet",
    "behind the scenes", "making of", "reaction", "interview",
    "live at ", "live from ", "boiler room", "skit",
    "bass boost", "8d audio", "slowed", "reverb", "432hz",
    "sped up", "nightcore", "visualizer",
]

GOOD_TITLE_WORDS = [
    "official audio", "(audio", "audio)", "lyric video",
    "lyrics", "explicit", "dirty", "hq", "original",
]


def clean_str(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\(feat\..*?\)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\(ft\..*?\)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\[.*?\]", "", s)
    s = re.sub(r"[^\w\s]", "", s)
    return s.strip()


def score_result(yt_title, yt_channel, yt_duration_s, target_artist, target_title, target_duration_ms):
    tl, cl = yt_title.lower(), yt_channel.lower()
    for bad in BAD_TITLE_WORDS:
        if bad in tl:
            return -999
    score = 0
    if target_duration_ms > 0 and yt_duration_s > 0:
        diff = abs(yt_duration_s * 1000 - target_duration_ms)
        if diff < 5000:
            score += 50
        elif diff < 15000:
            score += 25
        elif diff < 30000:
            score += 10
        else:
            score -= 20
    for w in clean_str(target_artist).split()[:2]:
        if len(w) > 3 and w in tl:
            score += 15
            break
    for w in clean_str(target_artist).split()[:2]:
        if len(w) > 3 and w in cl:
            score += 20
            break
    for w in clean_str(target_title).split()[:4]:
        if len(w) > 3 and w in tl:
            score += 10
    for g in GOOD_TITLE_WORDS:
        if g in tl:
            score += 20
            break
    if "vevo" in cl:
        score += 15
    if any(x in tl for x in ["remix", "amapiano", "afro edit", "bounce remix", "flip"]):
        score -= 25
    return score


def search_youtube(query: str, max_results: int = 8):
    cmd = [
        sys.executable, "-m", "yt_dlp",
        f"ytsearch{max_results}:{query}",
        "--dump-json", "--no-download",
        "--quiet", "--no-warnings", "--flat-playlist",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        entries = []
        for line in r.stdout.strip().split("\n"):
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
        return entries
    except Exception:
        return []


def find_best_url(artist: str, title: str, duration_ms: int, search_delay: float = 0.5):
    queries = [
        f"{artist} {title} official audio",
        f"{artist} {title} lyrics",
        f"{artist} {title}",
    ]
    best_score, best_entry = -999, None
    for query in queries:
        for e in search_youtube(query):
            score = score_result(
                e.get("title", ""), e.get("channel", "") or e.get("uploader", ""),
                e.get("duration") or 0, artist, title, duration_ms,
            )
            if score > best_score:
                best_score, best_entry = score, e
        if best_score >= 40:
            break
        time.sleep(search_delay)
    return best_entry, best_score


class BaseDownloader:
    """Interface every downloader backend implements."""
    name = "base"
    description = ""

    def resolve_missing(self, missing_tracks: list, download_folder: str, search_delay: float = 1.0) -> dict:
        """
        Given tracks not already in the library, either fetch them or
        prepare everything needed for the user to fetch them manually.

        Returns a dict:
          {
            "high_confidence": [...],
            "low_confidence": [...],
            "not_found": [...],
            "auto_downloaded": bool,   # True if files are now on disk
            "next_step": "human-readable instructions",
          }
        Each entry in high/low_confidence is:
          {"artist", "title", "url", "yt_title", "score", "confidence", "track"}
        """
        raise NotImplementedError


class YtDlpAutoDownloader(BaseDownloader):
    """Fully automated: search, pick the best match, download + convert to
    mp3 directly into the download folder. No manual pasting required."""
    name = "ytdlp"
    description = "Automated download via yt-dlp (no manual URL pasting)"

    def _download(self, url: str, dest_folder: str, out_basename: str) -> bool:
        Path(dest_folder).mkdir(parents=True, exist_ok=True)
        out_template = os.path.join(dest_folder, f"{out_basename}.%(ext)s")
        cmd = [
            sys.executable, "-m", "yt_dlp",
            url, "-x", "--audio-format", "mp3", "--audio-quality", "0",
            "-o", out_template, "--quiet", "--no-warnings",
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            return r.returncode == 0
        except Exception:
            return False

    def resolve_missing(self, missing_tracks, download_folder, search_delay=1.0):
        high, low, not_found = [], [], []
        for i, track in enumerate(missing_tracks, 1):
            artist = track["Artist Name(s)"].split(";")[0].strip()
            title = track["Track Name"].strip()
            duration_ms = int(track.get("Duration (ms)", 0) or 0)
            print(f"  [{i}/{len(missing_tracks)}] {artist} - {title}")

            best, score = find_best_url(artist, title, duration_ms, search_delay)
            if not best or score <= -900:
                not_found.append(track)
                print("    \u274c No match found")
                time.sleep(search_delay)
                continue

            url = f"https://www.youtube.com/watch?v={best.get('id', '')}"
            safe_name = re.sub(r'[<>:"/\\|?*]', "_", f"{artist} - {title}")[:120]
            ok = self._download(url, download_folder, safe_name)
            entry = {
                "artist": artist, "title": title, "url": url,
                "yt_title": best.get("title", ""), "score": score,
                "confidence": "HIGH" if score >= 40 else "LOW",
                "track": track, "downloaded": ok,
            }
            tag = "\u2705" if ok else "\u26a0\ufe0f  downloaded but conversion may have failed"
            print(f"    {tag} [{score}] {best.get('title', '')[:60]}")
            (high if score >= 40 else low).append(entry)
            time.sleep(search_delay)

        return {
            "high_confidence": high, "low_confidence": low, "not_found": not_found,
            "auto_downloaded": True,
            "next_step": "Files are already in your download folder. Run Part 2 next.",
        }


class ManualUrlListDownloader(BaseDownloader):
    """Original workflow: search + score only, write a URL list for the
    user to paste into 4K YouTube to MP3 (or any GUI downloader) by hand."""
    name = "manual"
    description = "Search only — writes a URL list for 4K/manual pasting"

    def resolve_missing(self, missing_tracks, download_folder, search_delay=1.0):
        high, low, not_found = [], [], []
        for i, track in enumerate(missing_tracks, 1):
            artist = track["Artist Name(s)"].split(";")[0].strip()
            title = track["Track Name"].strip()
            duration_ms = int(track.get("Duration (ms)", 0) or 0)
            print(f"  [{i}/{len(missing_tracks)}] {artist} - {title}")

            best, score = find_best_url(artist, title, duration_ms, search_delay)
            if best and score > -900:
                url = f"https://www.youtube.com/watch?v={best.get('id', '')}"
                entry = {
                    "artist": artist, "title": title, "url": url,
                    "yt_title": best.get("title", ""), "score": score,
                    "confidence": "HIGH" if score >= 40 else "LOW", "track": track,
                }
                (high if score >= 40 else low).append(entry)
                tag = "\u2705 HIGH" if score >= 40 else "\u26a0\ufe0f  LOW "
                print(f"    {tag} [{score}] {best.get('title', '')[:60]}")
            else:
                not_found.append(track)
                print("    \u274c No match found")
            time.sleep(search_delay)

        return {
            "high_confidence": high, "low_confidence": low, "not_found": not_found,
            "auto_downloaded": False,
            "next_step": (
                "Open the *_4K_DOWNLOAD.txt file and paste each URL, ONE AT A TIME, "
                f"into your downloader. Set its output folder to: {download_folder}"
            ),
        }


DOWNLOADERS = {
    "ytdlp": YtDlpAutoDownloader,
    "manual": ManualUrlListDownloader,
    # Aliases for discoverability
    "auto": YtDlpAutoDownloader,
    "4k": ManualUrlListDownloader,
}


def get_downloader(name: str) -> BaseDownloader:
    cls = DOWNLOADERS.get(name.lower())
    if not cls:
        valid = ", ".join(sorted(set(DOWNLOADERS.keys())))
        raise ValueError(f"Unknown downloader '{name}'. Choose from: {valid}")
    return cls()
