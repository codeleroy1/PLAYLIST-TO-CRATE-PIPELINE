#!/usr/bin/env python3
"""Preview verified moves; --apply moves audio and updates macOS Serato 4."""
import argparse
import json
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE if (HERE/'dj_pipeline').is_dir() else HERE.parent))
from dj_pipeline.workspace import load_config,part2

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path)
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    configs=[a.config] if a.config else list(HERE.glob('*_pipeline_config.json'))
    if len(configs)!=1: p.error('Specify --config: exactly one workspace must be selected')
    print(json.dumps(part2(load_config(configs[0]),apply=a.apply),indent=2))

if __name__=='__main__': main()
