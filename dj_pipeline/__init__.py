"""
dj_pipeline — shared helpers for the DJ Leroy Spotify → Serato pipeline.

This tiny package exists so Part 1 and Part 2 don't duplicate path logic,
and so a new user can point the whole pipeline at their own machine by
setting a few environment variables or CLI flags instead of hand-editing
script internals.
"""
from .config import PipelineConfig, load_or_create_config, slugify

__all__ = ["PipelineConfig", "load_or_create_config", "slugify"]
