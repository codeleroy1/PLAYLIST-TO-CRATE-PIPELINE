# Leroy: exact folder mapping

Exportify root:
`/Users/leroy/Music/DJ LEROY/DJ Admin - LEROY/Tools & Scripts/LEROY PLAYLISTING/EXPORTIFY`

Canonical library:
`/Users/leroy/Music/DJ LEROY/DJ Library - LEROY`

Serato database folder:
`/Users/leroy/Library/Application Support/Serato/Library`

All JSONs and exports are saved beside their source CSV. Audio alone goes into the canonical library's Artist/Album folders.

## Prepare every playlist

Run from the repository using its virtual environment:

```sh
.venv/bin/python scripts/prepare_exportify.py \
  --exportify-root "/Users/leroy/Music/DJ LEROY/DJ Admin - LEROY/Tools & Scripts/LEROY PLAYLISTING/EXPORTIFY" \
  --library "/Users/leroy/Music/DJ LEROY/DJ Library - LEROY" \
  --report "/Users/leroy/Music/DJ LEROY/DJ Admin - LEROY/Tools & Scripts/LEROY PLAYLISTING/EXPORTIFY/pipeline-install-report.json" \
  --install --backup-existing
```

## Run one playlist

Use the absolute path to your repository's `.venv/bin/python` if you are outside the repository. The copied scripts locate their own config automatically:

```sh
/path/to/repository/.venv/bin/python "/path/to/playlist/playlist_part1_get_urls.py"
```

Import that folder's `*_pipeline_4K_IMPORT.json` in 4K and explicitly select its `Downloads` folder in 4K. Review unresolved tracks before declaring downloads complete.

After 4K finishes and Serato is closed:

```sh
/path/to/repository/.venv/bin/python "/path/to/playlist/playlist_part2_process.py"
/path/to/repository/.venv/bin/python "/path/to/playlist/playlist_part2_process.py" --apply
```

Part 2 defaults to preview. It does not delete unrecognized files. The successful final state has music in DJ Library and no Downloads directory if it was emptied.

For Aug - 26 the target is:
`LEROY CRATE LIBRARY / EXPORTIFY CRATES / MULTI_GENRE / MONTHS / Aug_-_26`

A playlist folder is the crate name, even if the CSV filename is formatted differently. If multiple CSVs share one folder, a child crate named after each CSV distinguishes them. The script refuses conflicting local configurations; inspect rather than force an overwrite.

## Older Aug - 26 reports

The earlier Aug files remain as evidence. New `pipeline_` JSONs keep old results separate. Existing library tracks are rediscovered by Part 1. A previous flattened Aug crate is preserved; the new nested crate is additive. Visibility must be checked in Serato.
