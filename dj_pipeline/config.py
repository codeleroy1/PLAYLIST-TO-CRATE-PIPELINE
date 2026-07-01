"""
dj_pipeline.config

Centralizes every path the pipeline touches, so:
  - Part 1 and Part 2 always agree on where things live
  - a new user can override everything via CLI flags or environment
    variables instead of editing script internals
  - "which playlist is this?" is answered by a slug + JSON handoff file,
    not by a uniquely-named script per playlist
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path


def slugify(name: str) -> str:
    """Turn a playlist name into a filesystem/JSON-safe identifier."""
    return re.sub(r"[^\w]", "_", name).strip("_")


DEFAULTS = {
    # Where 4K MP3 Downloader / yt-dlp output lands before processing.
    "download_folder": os.environ.get(
        "DJ_PIPELINE_DOWNLOAD_FOLDER", str(Path.home() / "Desktop" / "4k YOUTUBE TO MP3")
    ),
    # The canonical, tagged, Serato-facing library.
    "dj_library": os.environ.get(
        "DJ_PIPELINE_LIBRARY", str(Path.home() / "Music" / "DJ Library")
    ),
    # Where Serato looks for .crate files.
    "serato_crates": os.environ.get(
        "DJ_PIPELINE_SERATO_CRATES", str(Path.home() / "Music" / "_Serato_" / "Subcrates")
    ),
    # Where this pipeline's own working/handoff files live. Kept off the
    # Desktop on purpose so sessions don't clutter it — override with
    # --data-dir or $DJ_PIPELINE_DATA_DIR if you want the old behavior.
    "data_dir": os.environ.get(
        "DJ_PIPELINE_DATA_DIR", str(Path.home() / ".dj_pipeline" / "sessions")
    ),
}


@dataclass
class PipelineConfig:
    playlist_name: str
    playlist_slug: str
    csv_paths: list
    download_folder: str
    dj_library: str
    serato_crates: str
    data_dir: str

    @property
    def matched_json(self) -> Path:
        return Path(self.data_dir) / f"{self.playlist_slug}_matched.json"

    @property
    def youtube_json(self) -> Path:
        return Path(self.data_dir) / f"{self.playlist_slug}_youtube.json"

    @property
    def config_json(self) -> Path:
        return Path(self.data_dir) / f"{self.playlist_slug}_config.json"

    @property
    def download_url_list(self) -> Path:
        return Path(self.data_dir) / f"{self.playlist_slug}_4K_DOWNLOAD.txt"

    def ensure_dirs(self):
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.download_folder).mkdir(parents=True, exist_ok=True)
        Path(self.dj_library).mkdir(parents=True, exist_ok=True)

    def save(self):
        self.ensure_dirs()
        with open(self.config_json, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, slug: str, data_dir: str = None) -> "PipelineConfig":
        data_dir = data_dir or DEFAULTS["data_dir"]
        path = Path(data_dir) / f"{slug}_config.json"
        if not path.exists():
            raise FileNotFoundError(
                f"No saved session found for '{slug}' in {data_dir}. "
                f"Run playlist_part1_get_urls.py first."
            )
        with open(path) as f:
            return cls(**json.load(f))


def load_or_create_config(
    playlist_name: str,
    csv_paths: list,
    download_folder: str = None,
    dj_library: str = None,
    serato_crates: str = None,
    data_dir: str = None,
) -> PipelineConfig:
    cfg = PipelineConfig(
        playlist_name=playlist_name,
        playlist_slug=slugify(playlist_name),
        csv_paths=[str(Path(p).expanduser()) for p in csv_paths],
        download_folder=str(Path(download_folder or DEFAULTS["download_folder"]).expanduser()),
        dj_library=str(Path(dj_library or DEFAULTS["dj_library"]).expanduser()),
        serato_crates=str(Path(serato_crates or DEFAULTS["serato_crates"]).expanduser()),
        data_dir=str(Path(data_dir or DEFAULTS["data_dir"]).expanduser()),
    )
    cfg.save()
    return cfg


def find_latest_session(data_dir: str = None) -> str:
    """Return the slug of the most recently touched session, for the
    common case of 'just run part 2, I only worked on one playlist'."""
    data_dir = Path(data_dir or DEFAULTS["data_dir"])
    if not data_dir.exists():
        return None
    configs = sorted(data_dir.glob("*_config.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not configs:
        return None
    return configs[0].name.replace("_config.json", "")
