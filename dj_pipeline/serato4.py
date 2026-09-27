"""Additive, backed-up writer for the observed macOS Serato 4 root schema.

This is an unofficial integration, not a promise of future schema compatibility.
Only root.sqlite is changed; Serato rebuilds its master aggregate on launch.
"""
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path


def preflight(folder):
    if sys.platform != 'darwin':
        raise RuntimeError('Serato 4 direct integration currently supports macOS only')
    process = subprocess.run(['pgrep', '-x', 'Serato DJ Pro'], capture_output=True)
    if process.returncode != 1:
        raise RuntimeError('Quit Serato DJ Pro before Part 2 can update its library')
    root = Path(folder).expanduser().resolve() / 'root.sqlite'
    if not root.is_file():
        raise FileNotFoundError(f'Serato 4 root.sqlite not found: {root}')
    with closing(sqlite3.connect(root.as_uri()+'?mode=ro', uri=True)) as conn:
        required = {'container': {'id','name','type','parent_id','space_id','revision','list_order'},
                    'asset': {'id','type','format','name','portable_id','revision','file_name','file_size'},
                    'container_asset': {'id','list_order','space_asset_id','container_id','revision'},
                    'space_asset': {'id','asset_id','space_id'}, 'space': {'id','name','revision'},
                    'serato': {'revision'}, 'master': {'revision'}}
        for table, columns in required.items():
            found = {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
            if not columns <= found:
                raise RuntimeError(f'Unsupported Serato schema: {table}')
        if conn.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise RuntimeError('Serato library integrity check failed')
    return root


def write_crate(paths, hierarchy, folder):
    root = preflight(folder)
    if not hierarchy or any(not x or x in ('.','..') or '/' in x for x in hierarchy):
        raise ValueError('Crate hierarchy must contain separate, nonempty names')
    paths = list(dict.fromkeys(str(Path(p).resolve(strict=True)) for p in paths))
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backups = []
    for db in (root, root.with_name('master.sqlite')):
        if not db.exists(): continue
        target = db.with_name(db.name+'.pipeline-backup.'+stamp)
        with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as src, closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed')
        backups.append(str(target))
    preflight(folder)
    with closing(sqlite3.connect(root, timeout=5)) as conn, conn:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('BEGIN IMMEDIATE')
        anchor = conn.execute("SELECT c.id,s.id FROM container c JOIN space s ON c.space_id=s.id WHERE s.name='Serato Library' AND c.type=0 AND (c.parent_id=0 OR c.parent_id IS NULL)").fetchall()
        if len(anchor)!=1: raise RuntimeError('Ambiguous Serato Library root')
        parent, space = anchor[0]
        revision = conn.execute('SELECT revision FROM serato').fetchone()[0]+1
        conn.execute('UPDATE serato SET revision=?',(revision,))
        conn.execute('UPDATE master SET revision=?',(revision,))
        for name in hierarchy:
            row = conn.execute('SELECT id,type FROM container WHERE parent_id=? AND name=? COLLATE NOCASE',(parent,name)).fetchall()
            if row:
                if len(row)!=1 or row[0][1]!=1: raise RuntimeError('Crate name conflicts with a nonstandard container')
                parent = row[0][0]
            else:
                order = conn.execute('SELECT coalesce(max(list_order),0)+1 FROM container WHERE parent_id=?',(parent,)).fetchone()[0]
                parent = conn.execute('INSERT INTO container (revision,parent_id,name,type,list_order,space_id) VALUES (?,?,?,1,?,?)',(revision,parent,name,order,space)).lastrowid
        added = 0
        for raw in paths:
            p = Path(raw); portable = raw.lstrip('/')
            row = conn.execute('SELECT id FROM asset WHERE portable_id=? COLLATE NOCASE',(portable,)).fetchone()
            asset = row[0] if row else conn.execute('INSERT INTO asset (revision,portable_id,file_name,file_size,type,format,name) VALUES (?,?,?,?,?,?,?)',(revision,portable,p.name,p.stat().st_size,'audio',p.suffix[1:],p.stem)).lastrowid
            row = conn.execute('SELECT id FROM space_asset WHERE asset_id=? AND space_id=?',(asset,space)).fetchone()
            sa = row[0] if row else conn.execute('INSERT INTO space_asset (asset_id,space_id) VALUES (?,?)',(asset,space)).lastrowid
            if not conn.execute('SELECT 1 FROM container_asset WHERE container_id=? AND space_asset_id=?',(parent,sa)).fetchone():
                order = conn.execute('SELECT coalesce(max(list_order),0)+1 FROM container_asset WHERE container_id=?',(parent,)).fetchone()[0]
                conn.execute('INSERT INTO container_asset (revision,container_id,space_asset_id,list_order) VALUES (?,?,?,?)',(revision,parent,sa,order))
                added += 1
        conn.execute('UPDATE space SET revision=? WHERE id=?',(revision,space))
        if conn.execute('PRAGMA foreign_key_check').fetchall() or conn.execute('PRAGMA quick_check').fetchone()[0]!='ok':
            raise RuntimeError('Serato transaction failed integrity validation')
        actual = {r[0] for r in conn.execute('SELECT a.portable_id FROM container_asset ca JOIN space_asset sa ON sa.id=ca.space_asset_id JOIN asset a ON a.id=sa.asset_id WHERE ca.container_id=?',(parent,))}
        if not {p.lstrip('/') for p in paths} <= actual: raise RuntimeError('Crate membership verification failed')
    return {'container_id':parent,'hierarchy':hierarchy,'tracks_added':added,'requested_tracks':len(paths),'backups':backups,'ui_verified':False}
