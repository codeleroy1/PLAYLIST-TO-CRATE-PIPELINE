"""
dj_pipeline.crate_writers

Pluggable "how does this playlist get into your DJ software" backends.

Serato uses a proprietary binary .crate format (implemented natively
here). Rekordbox, Traktor, and Engine DJ all happily import standard
.m3u8 playlists, so they share one writer. Add a new one by subclassing
BaseCrateWriter and registering it in CRATE_WRITERS.
"""
from __future__ import annotations

import os
import struct
from pathlib import Path


class BaseCrateWriter:
    name = "base"
    description = ""
    file_extension = ""

    def write(self, track_paths: list, playlist_name: str, output_dir: str) -> str:
        """Write the crate/playlist file and return its path."""
        raise NotImplementedError

    def post_instructions(self, output_path: str) -> str:
        return f"Crate/playlist written to: {output_path}"


def _sanitize(name: str) -> str:
    import re
    return re.sub(r'[<>:"/\\|?*]', "_", str(name)).strip()[:100]


class SeratoCrateWriter(BaseCrateWriter):
    """Serato DJ Pro / Lite native binary .crate format."""
    name = "serato"
    description = "Serato DJ Pro/Lite (.crate)"
    file_extension = ".crate"

    @staticmethod
    def _encode_str(s):
        return s.encode("utf-16-be")

    @staticmethod
    def _make_field(tag, data):
        return tag.encode("ascii") + struct.pack(">I", len(data)) + data

    def _make_crate_bytes(self, track_paths):
        version = "1.0/Serato ScratchLive Crate"
        buf = b"vrsn" + struct.pack(">I", len(version) * 2) + self._encode_str(version)
        for path in track_paths:
            if path.startswith("/"):
                path = path[1:]  # Serato stores paths without a leading slash
            buf += self._make_field("otrk", self._make_field("ptrk", self._encode_str(path)))
        return buf

    def write(self, track_paths, playlist_name, output_dir):
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        out_path = os.path.join(output_dir, _sanitize(playlist_name) + self.file_extension)
        with open(out_path, "wb") as f:
            f.write(self._make_crate_bytes(track_paths))
        return out_path

    def post_instructions(self, output_path):
        return (
            f"Crate written to: {output_path}\n"
            "  1. Close Serato completely and reopen it\n"
            f"  2. Find the crate in your Crates panel\n"
            "  3. Select all -> right-click -> Rescan ID Tags\n"
            "  4. Run Analyze Files to get BPM + Key"
        )


class M3U8CrateWriter(BaseCrateWriter):
    """Standard extended M3U8 playlist. Importable by Rekordbox, Traktor,
    Engine DJ, Denon StagelinQ software, VirtualDJ, and most others."""
    name = "m3u"
    description = "Generic .m3u8 playlist (Rekordbox / Traktor / Engine DJ / VirtualDJ)"
    file_extension = ".m3u8"

    def write(self, track_paths, playlist_name, output_dir):
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        out_path = os.path.join(output_dir, _sanitize(playlist_name) + self.file_extension)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for path in track_paths:
                title = os.path.splitext(os.path.basename(path))[0]
                f.write(f"#EXTINF:-1,{title}\n{path}\n")
        return out_path

    def post_instructions(self, output_path):
        return (
            f"Playlist written to: {output_path}\n"
            "  Rekordbox: File -> Import Playlist -> select the .m3u8\n"
            "  Traktor:   drag the .m3u8 into a Traktor playlist folder\n"
            "  Engine DJ: File -> Import -> Playlist File"
        )


CRATE_WRITERS = {
    "serato": SeratoCrateWriter,
    "rekordbox": M3U8CrateWriter,
    "traktor": M3U8CrateWriter,
    "engine": M3U8CrateWriter,
    "enginedj": M3U8CrateWriter,
    "virtualdj": M3U8CrateWriter,
    "m3u": M3U8CrateWriter,
}


def get_crate_writer(name: str) -> BaseCrateWriter:
    cls = CRATE_WRITERS.get(name.lower())
    if not cls:
        valid = ", ".join(sorted(set(CRATE_WRITERS.keys())))
        raise ValueError(f"Unknown DJ software '{name}'. Choose from: {valid}")
    return cls()
