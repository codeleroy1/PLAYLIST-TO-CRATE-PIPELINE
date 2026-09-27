#!/usr/bin/env python3
"""Prepare one CSV beside its source; search URLs for 4K without downloading."""
import argparse
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE/'dj_pipeline').is_dir() else HERE.parent))
from dj_pipeline.workspace import prepare, load_config, part1

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', type=Path)
    p.add_argument('--config', type=Path)
    p.add_argument('--exportify-root', type=Path)
    p.add_argument('--library', type=Path)
    p.add_argument('--serato-folder', type=Path, default=Path.home()/'Library/Application Support/Serato/Library')
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--backup-existing', action='store_true')
    a=p.parse_args()
    if a.csv and a.config: p.error('Use --csv or --config, not both')
    if a.csv:
        if not a.library or not a.exportify_root: p.error('--csv requires --library and --exportify-root')
        cfg=prepare(a.csv,a.library,a.exportify_root,a.serato_folder,backup_existing=a.backup_existing)
    else:
        configs=[a.config] if a.config else list(HERE.glob('*_pipeline_config.json'))
        if len(configs)!=1: p.error('Specify --config: exactly one workspace must be selected')
        cfg=load_config(configs[0])
    print(json.dumps(cfg if a.prepare_only else part1(cfg),indent=2))

if __name__=='__main__': main()
