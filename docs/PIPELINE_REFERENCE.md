# Workspace contract and progress evidence

The active entrypoints are scripts/playlist_part1_get_urls.py, scripts/playlist_part2_process.py and scripts/prepare_exportify.py. All use dj_pipeline/workspace.py.

## Path resolution

Preparation resolves the source CSV, Exportify root, library root, and Serato folder explicitly. Relative CSV ancestry defines the crate hierarchy. There is no fallback to the newest unrelated playlist or a Desktop download folder.

The saved config uses version 2. When loaded, CSV basename and Downloads are resolved relative to the config's current folder. Canonical library and Serato destinations remain explicitly configured. Moving the entire playlist folder therefore preserves local artifact mapping without silently redirecting the music library.

Legacy *_config.json and older JSON exports are not changed; the new config is *_pipeline_config.json. Script upgrades require --backup-existing when files differ. All changed scripts are copied into a timestamped backup beside the CSV before replacement.

## Verified progress

| Stage | Evidence |
| --- | --- |
| CSV inventoried | Valid Exportify headers and unique track count |
| Scripts installed | Files copied and config checked; does not imply Part 1 ran |
| URLs prepared | matched/youtube/review JSONs and 4K export |
| Downloaded | Actual complete audio, not queued 4K items |
| Moved | Destination payload hash, tags, source removal and moves journal |
| Serato database updated | Successful backed-up transaction and memberships |
| Visible in Serato | User-interface check after reopening Serato |
| Analyzed | BPM/key analysis verified in Serato |

Partial playlists may have an imported crate and still have unresolved tracks. Keep Health = Needs review and completion unchecked. Do not infer completion from a directory count.

## Serato integration boundary

This unofficial implementation is based on the observed macOS Serato DJ Pro 4.0.7 root.sqlite schema. Schema checks and process guards reject incompatible environments. root.sqlite and master.sqlite are backed up with SQLite's backup API before writes. The transaction appends containers/assets/memberships and advances revisions without replacing existing containers. Serato rebuilds its master aggregate on launch.

Tests validate a representative schema and a disposable copy of the observed real schema. They do not guarantee future Serato releases or UI import behavior. The returned ui_verified value remains false.

Related implementation investigated during development: [LegendT/serato-crates-sync](https://github.com/LegendT/serato-crates-sync).

## Recovery

If a move stops after publication, the journal verifies destination payload and Spotify identity before removing the surviving source on retry. If tagging fails or a destination exists without a matching journal, the original download remains. Inspect a leftover .pipeline-stage or processing.lock before removing it; recovery never guesses that an unknown file is disposable.

Legacy session utilities and cleanup_duplicates.py are outside this workflow. Do not run bulk deletion to make a download folder appear complete.
