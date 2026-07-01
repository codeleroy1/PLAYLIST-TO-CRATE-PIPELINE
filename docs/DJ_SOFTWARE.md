# DJ Software / Crate Writers

`dj_pipeline/crate_writers.py` defines a small plugin interface for "how
does this playlist get into your DJ software." Two writers ship by
default, covering everything the pipeline currently supports:

| `--dj-software` value | Class | Output |
|---|---|---|
| `serato` | `SeratoCrateWriter` | Native binary `.crate`, written straight into Serato's `Subcrates` folder |
| `rekordbox`, `traktor`, `engine`/`enginedj`, `virtualdj`, `m3u` | `M3U8CrateWriter` | Standard extended `.m3u8` playlist |

Rekordbox, Traktor, Engine DJ, and VirtualDJ all import `.m3u8` natively,
so one writer covers all of them. Serato needs its own binary format,
which is implemented from scratch (see `docs/PIPELINE_REFERENCE.md` for
the byte layout).

## Adding your own crate writer

Want native Traktor `.nml` playlists instead of the `.m3u8` fallback, or
support for a tool not listed above? Subclass `BaseCrateWriter`:

```python
# dj_pipeline/crate_writers.py

class TraktorNMLWriter(BaseCrateWriter):
    name = "traktor-nml"
    description = "Native Traktor NML playlist entries"
    file_extension = ".nml"

    def write(self, track_paths, playlist_name, output_dir):
        # build/merge into Traktor's collection.nml here
        ...
        return output_path

    def post_instructions(self, output_path):
        return f"Import {output_path} into Traktor via File -> Import Playlist"
```

Then register it:

```python
CRATE_WRITERS["traktor-nml"] = TraktorNMLWriter
```

It's immediately available as `--dj-software traktor-nml` from Part 2 —
`scripts/playlist_part2_process.py` builds its `--dj-software` choices
dynamically from `CRATE_WRITERS.keys()`.

## Why M3U8 as the shared fallback?

It's the closest thing to a universal DJ-software playlist format:
Rekordbox, Traktor, Engine DJ, VirtualDJ, Mixxx, and most others can
import it without a plugin. It doesn't carry hot cues, memory points, or
per-track color coding the way each app's native format could — that's
the tradeoff for "works everywhere out of the box." If you need that
richer per-app data, write a dedicated backend as shown above.
