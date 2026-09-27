#!/usr/bin/env python3
"""Inventory every Exportify CSV. --install copies scripts and writes local configs."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dj_pipeline.workspace import prepare, tracks, save

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exportify-root',required=True,type=Path)
    p.add_argument('--library',required=True,type=Path)
    p.add_argument('--serato-folder',type=Path,default=Path.home()/'Library/Application Support/Serato/Library')
    p.add_argument('--install',action='store_true')
    p.add_argument('--backup-existing',action='store_true')
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args(); rows=[]; root=a.exportify_root.expanduser().resolve(strict=True)
    for csv in sorted(root.rglob('*.csv')):
        if any(x.startswith('pipeline-script-backup-') for x in csv.parts): continue
        try: count=len(tracks(csv))
        except (ValueError,UnicodeError): continue
        row={'csv':str(csv),'relative_path':str(csv.relative_to(root)),'tracks':count,'scripts_installed':False}
        if a.install:
            try:
                row['config']=prepare(csv,a.library,root,a.serato_folder,backup_existing=a.backup_existing)
                row['scripts_installed']=True
            except Exception as e: row['error']=str(e)
        rows.append(row)
        save(a.report,rows)
    print(json.dumps({'playlists':len(rows),'installed':sum(x['scripts_installed'] for x in rows),'errors':sum('error' in x for x in rows)},indent=2))
    if any('error' in x for x in rows): sys.exit(1)

if __name__=='__main__': main()
