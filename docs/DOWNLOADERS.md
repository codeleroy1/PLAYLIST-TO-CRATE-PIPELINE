# Downloaders

`dj_pipeline/downloaders.py` defines a small plugin interface for "how do
missing tracks actually get onto disk." Two ship by default:

| Name | Class | Behavior |
|---|---|---|
| `ytdlp` (alias `auto`) | `YtDlpAutoDownloader` | Searches YouTube, picks the best match, downloads and converts to MP3 directly into your download folder. Fully hands-off. |
| `manual` (alias `4k`) | `ManualUrlListDownloader` | Searches and scores candidates like above, but only writes a `*_4K_DOWNLOAD.txt` URL list — you paste URLs into 4K YouTube to MP3 or any other GUI downloader yourself. |

Both share the same search/scoring logic (`find_best_url`, `score_result`
in the same module), so match *quality* is identical either way — only
who fetches the bytes differs.

## Adding your own downloader

Say you want to use `yt-dlp` but route through a different extractor, or
you want a backend for a completely different tool (SoundCloud downloader,
a local Beatport purchase-matching flow, etc.). Subclass `BaseDownloader`:

```python
# dj_pipeline/downloaders.py

class MyCustomDownloader(BaseDownloader):
    name = "mytool"
    description = "Fetches audio via MyTool instead of yt-dlp"

    def resolve_missing(self, missing_tracks, download_folder, search_delay=1.0):
        high, low, not_found = [], [], []
        for track in missing_tracks:
            # ... your acquisition logic ...
            # append to high/low/not_found in the same shape as the
            # built-in downloaders (see YtDlpAutoDownloader for the
            # exact dict shape expected)
            pass
        return {
            "high_confidence": high,
            "low_confidence": low,
            "not_found": not_found,
            "auto_downloaded": True,   # or False if the user still needs to fetch manually
            "next_step": "Human-readable instructions for what to do next.",
        }
```

Then register it:

```python
DOWNLOADERS["mytool"] = MyCustomDownloader
```

It's immediately available as `--downloader mytool` from Part 1 — no
other changes needed. `scripts/playlist_part1_get_urls.py` builds its
`--downloader` choices dynamically from `DOWNLOADERS.keys()`.

## Why not just always auto-download?

Some DJs specifically want 4K YouTube to MP3 (or another GUI tool) in
the loop — for its own normalization, its own metadata handling, or
just because that's the workflow they trust. The `manual` backend keeps
that fully supported; it's the same search/scoring engine, just without
taking the download step away from you.
