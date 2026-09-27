"""Per-CSV workspaces. All local artifacts are rooted beside the source CSV."""
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from mutagen import File
from mutagen.id3 import ID3
from .tagging import sanitize, get_primary_artist, write_spotify_tags


def norm(text):
    return ''.join(c for c in text.casefold() if c.isalnum())


def save(path, value):
    path = Path(path)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, indent=2)
            f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if Path(name).exists(): Path(name).unlink()


def read(path, default=None):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


def tracks(csv_path):
    with Path(csv_path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not {'Track URI','Track Name','Artist Name(s)','Album Name'} <= set(reader.fieldnames or []):
            raise ValueError(f'Not an Exportify CSV: {csv_path}')
        return list({r['Track URI'] or r['Artist Name(s)']+'|'+r['Track Name']:r for r in reader}.values())


def artifact(cfg, suffix):
    return Path(cfg['csv']).parent / (Path(cfg['csv']).stem+'_pipeline_'+suffix)


def prepare(csv_path, library, exportify_root, serato_folder, prefix=('LEROY CRATE LIBRARY','EXPORTIFY CRATES'), backup_existing=False):
    csv_path=Path(csv_path).expanduser().resolve(strict=True)
    tracks(csv_path)
    root=Path(exportify_root).expanduser().resolve(strict=True)
    relative=csv_path.relative_to(root)
    hierarchy=list(prefix)+list(relative.parent.parts)
    if csv_path.parent==root or len(list(csv_path.parent.glob('*.csv')))>1:
        hierarchy.append(csv_path.stem)
    config={'version':2,'csv':str(csv_path),'library':str(Path(library).expanduser().resolve()),
            'exportify_root':str(root),'crate_hierarchy':hierarchy,
            'serato_folder':str(Path(serato_folder).expanduser().resolve()),
            'downloads':str(csv_path.parent/'Downloads')}
    path=artifact(config,'config.json')
    existing=read(path)
    if existing and existing!=config:
        raise ValueError(f'Config already exists with different paths: {path}; review it before replacing')
    bundle=csv_path.parent/'dj_pipeline'
    source=Path(__file__).parent
    # Preflight the whole bundle so user-edited scripts are never overwritten.
    payload={bundle/p.name:p.read_bytes() for p in source.glob('*.py')}
    scripts=source.parent/'scripts'
    for name in ('playlist_part1_get_urls.py','playlist_part2_process.py'):
        payload[csv_path.parent/name]=(scripts/name).read_bytes()
    payload[csv_path.parent/'requirements.txt']=(source.parent/'requirements.txt').read_bytes()
    changed=[target for target,data in payload.items() if target.exists() and target.read_bytes()!=data]
    if changed and not backup_existing:
        raise FileExistsError(f'Existing local scripts differ; use --backup-existing to preserve them before update: {changed[0]}')
    if changed:
        from datetime import datetime
        backup=csv_path.parent/('pipeline-script-backup-'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        for target in changed:
            preserved=backup/target.relative_to(csv_path.parent)
            preserved.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,preserved)
    for target,data in payload.items():
        target.parent.mkdir(exist_ok=True)
        if not target.exists() or target in changed: target.write_bytes(data)
    save(path,config)
    return config


def load_config(path):
    path=Path(path).expanduser().resolve(strict=True)
    cfg=read(path)
    if cfg.get('version')!=2: raise ValueError('Legacy session; prepare a version 2 workspace first')
    # Local artifacts follow the config/CSV if the complete workspace is relocated.
    cfg['csv']=str(path.parent/Path(cfg['csv']).name)
    cfg['downloads']=str(path.parent/'Downloads')
    if not Path(cfg['csv']).is_file(): raise FileNotFoundError(cfg['csv'])
    return cfg


def library_index(library):
    uri={}; tagged={}; filenames={}
    root=Path(library).resolve(strict=True)
    for p in root.rglob('*'):
        if p.suffix.lower() not in {'.mp3','.m4a','.flac','.wav','.aif','.aiff'} or not p.is_file(): continue
        if not p.resolve().is_relative_to(root): continue
        filenames.setdefault(norm(p.stem),[]).append(str(p.resolve()))
        try:
            a=File(p,easy=True)
            if a is None: continue
            for u in a.get('composer',[]): uri.setdefault(u,[]).append(str(p.resolve()))
            title=(a.get('title') or [''])[0]; artist=(a.get('artist') or [''])[0]
            if title and artist: tagged.setdefault((norm(artist),norm(title)),[]).append(str(p.resolve()))
        except Exception: continue
    return uri,tagged,filenames


def find_existing(t,index):
    uri,tags,names=index
    artist=t['Artist Name(s)'].split(';')[0].strip()
    candidates=uri.get(t['Track URI']) or tags.get((norm(artist),norm(t['Track Name']))) or names.get(norm(artist+' '+t['Track Name'])) or []
    return candidates[0] if len(candidates)==1 else None


def export_4k(cfg, entries):
    ready=[e for e in entries if e['status']=='ready']
    for e in ready:
        if not re.fullmatch(r'https://www.youtube.com/watch\?v=[A-Za-z0-9_-]{11}',e.get('url','')):
            raise ValueError('Ready entry needs a valid YouTube watch URL')
    batch={'json_schema_version':'1.0.0','items':[]}
    for e in ready:
        batch['items'].append({'urlDesc':{'handlerName':'','serviceName':'youtube','type':'','url':e['url']},
            'playlistTitle':cfg['crate_hierarchy'][-1],
            'downloadPreferences':{'audioTracks':[],'subtitles':[],'outputDir':cfg['downloads'],
                'format':{'container':'MP3','audio':{'codec':'MP3','bitrate':320000}}}})
    save(artifact(cfg,'4K_IMPORT.json'),batch)
    artifact(cfg,'4K_DOWNLOAD.txt').write_text(''.join(e['url']+'\n' for e in ready))
    save(artifact(cfg,'review.json'),[e for e in entries if e['status']=='review'])


def part1(cfg):
    from .downloaders import search_youtube
    csv_fingerprint=hashlib.sha256(Path(cfg['csv']).read_bytes()).hexdigest()
    save(artifact(cfg,'part1.json'),{'complete':False,'csv_sha256':csv_fingerprint})
    index=library_index(cfg['library'])
    previous={e['track']['Track URI']:e for e in read(artifact(cfg,'youtube.json'),[])}
    matched=[]; entries=[]
    Path(cfg['downloads']).mkdir(exist_ok=True)
    for t in tracks(cfg['csv']):
        owned=find_existing(t,index)
        if owned: matched.append({'track':t,'path':owned}); continue
        old=previous.get(t['Track URI'])
        if old and old.get('status') in ('ready','review'):
            entries.append(old); continue
        artist=t['Artist Name(s)'].split(';')[0].strip(); title=t['Track Name']
        candidates=search_youtube(artist+' '+title,8)
        # A score based on duration alone must never authorize a different song.
        base=re.split(r'\s+-\s+|\s+\(feat\.', title, flags=re.I)[0]
        expected=float(t.get('Duration (ms)') or 0)/1000
        valid=[]
        for r in candidates:
            text=r.get('title',''); channel=r.get('channel','') or r.get('uploader','')
            duration=r.get('duration') or 0
            bad=any(w in text.casefold() and w not in title.casefold() for w in ('slowed','reverb','sped up','karaoke','instrumental','remix','live','radio edit','clean','cover','full album'))
            version_ok=all(w in text.casefold() for w in re.findall(r'\b(?:extended|remaster|vocal|knee deep|spotify studios)\b',title.casefold()))
            if norm(base) in norm(text) and norm(artist) in norm(text+' '+channel) and expected and abs(duration-expected)<=5 and not bad and version_ok:
                valid.append(r)
        best=valid[0] if valid else None
        entry={'track':t,'status':'ready' if best else 'review','candidates':candidates,
               'url':'https://www.youtube.com/watch?v='+best['id'] if best else '',
               'yt_title':best['title'] if best else '', 'duration':best.get('duration') if best else None}
        entries.append(entry)
        previous[t['Track URI']]=entry
        save(artifact(cfg,'youtube.json'),list(previous.values()))
        print(f'{entry["status"]}: {artist} - {title}',flush=True)
    save(artifact(cfg,'matched.json'),matched); save(artifact(cfg,'youtube.json'),entries)
    export_4k(cfg,entries)
    if hashlib.sha256(Path(cfg['csv']).read_bytes()).hexdigest()!=csv_fingerprint:
        raise RuntimeError('CSV changed during Part 1; rerun before processing downloads')
    save(artifact(cfg,'part1.json'),{'complete':True,'csv_sha256':csv_fingerprint})
    return {'existing':len(matched),'ready':sum(e['status']=='ready' for e in entries),'review':sum(e['status']=='review' for e in entries),'downloads':cfg['downloads']}


def audio_hash(path):
    """Hash MP3 payload excluding ID3 headers and ID3v1 trailer."""
    data=Path(path).read_bytes()
    if data[:3]==b'ID3':
        size=0
        for b in data[6:10]: size=(size<<7)|(b&127)
        data=data[10+size:]
    if data[-128:-125]==b'TAG': data=data[:-128]
    return hashlib.sha256(data).hexdigest()


def part2(cfg, apply=False):
    if not apply:
        return _part2(cfg,False)
    from .serato4 import preflight
    preflight(cfg['serato_folder'])
    lock=artifact(cfg,'processing.lock')
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        return _part2(cfg,True)
    finally:
        os.close(fd)
        lock.unlink()


def _part2(cfg, apply=False):
    from .serato4 import preflight,write_crate
    library=Path(cfg['library']).resolve(strict=True)
    dl=Path(cfg['downloads'])
    journal_path=artifact(cfg,'moves.json')
    journal=read(journal_path,{})
    entries=read(artifact(cfg,'youtube.json'))
    matched=read(artifact(cfg,'matched.json'))
    if entries is None or matched is None: raise RuntimeError('Run Part 1 first')
    state=read(artifact(cfg,'part1.json'),{})
    if not state.get('complete') or state.get('csv_sha256')!=hashlib.sha256(Path(cfg['csv']).read_bytes()).hexdigest():
        raise RuntimeError('Part 1 is incomplete or CSV changed; rerun Part 1')
    expected={t['Track URI'] for t in tracks(cfg['csv'])}
    actual=[e['track']['Track URI'] for e in entries+matched]
    if set(actual)!=expected or len(actual)!=len(expected):
        raise ValueError('Handoff tracks do not match CSV exactly; rerun Part 1')
    index=library_index(library)
    all_paths=[]; plans=[]; pending=[]; used=set()
    for entry in matched:
        p=Path(entry['path']).resolve(strict=True)
        if not p.is_relative_to(library): raise ValueError(f'Existing match outside library: {p}')
        all_paths.append(str(p))
    files=list(dl.glob('*.mp3')) if dl.exists() else []
    for e in entries:
        if e['status']!='ready': continue
        t=e['track']; key=t['Track URI']
        done=journal.get(key)
        if done:
            dest=Path(done['destination']).resolve()
            # A planned journal can survive interruption before publication.
            if done.get('state')=='planned' and not dest.exists():
                done=None
        if done:
            if not dest.is_relative_to(library) or not dest.is_file() or audio_hash(dest)!=done['audio_sha256']:
                raise RuntimeError(f'Previously transferred file changed or missing: {dest}')
            if str(ID3(dest).get('TCOM'))!=t['Track URI'] or str(ID3(dest).get('TIT2'))!=t['Track Name'].strip():
                raise RuntimeError('Previously transferred tags changed; source retained')
            source=Path(done['source'])
            if source.exists():
                if source.parent.resolve()!=dl.resolve() or audio_hash(source)!=done['audio_sha256']:
                    raise RuntimeError('Source changed since interrupted transfer')
                if apply: source.unlink()
            all_paths.append(str(dest)); continue
        choices=[p for p in files if norm(p.stem)==norm(e['yt_title']) and p not in used]
        if sum(x.get('status')=='ready' and norm(x.get('yt_title',''))==norm(e['yt_title']) for x in entries)>1:
            raise ValueError('Multiple tracks share one download title; resolve the mapping first')
        if len(choices)!=1:
            owned=find_existing(t,index)
            if owned: all_paths.append(owned); continue
            pending.append(t['Track Name']); continue
        source=choices[0];used.add(source)
        if source.is_symlink(): raise ValueError('Download symlinks are not accepted')
        audio=File(source)
        if audio is None or abs(audio.info.length-float(t['Duration (ms)'])/1000)>10:
            raise ValueError(f'Download duration mismatch: {source.name}')
        artist=get_primary_artist(t['Artist Name(s)'])
        dest=library/sanitize(artist)/(sanitize(t['Album Name']) or '_Singles')/(sanitize(artist+' - '+t['Track Name'])+'.mp3')
        if not dest.resolve().is_relative_to(library): raise ValueError('Destination escapes library')
        if dest in [p[1] for p in plans]: raise ValueError('Two tracks map to the same destination')
        if dest.exists():
            raise FileExistsError(f'Destination already exists; review it before transfer: {dest}')
        plans.append((source,dest,t))
    if apply:
        preflight(cfg['serato_folder'])
        try:
            for source,dest,t in plans:
                dest.parent.mkdir(parents=True,exist_ok=True)
                fingerprint=audio_hash(source)
                stage=dest.with_name('.'+dest.name+'.pipeline-stage')
                if stage.exists():
                    raise FileExistsError(f'Interrupted staging file needs inspection: {stage}')
                with stage.open('xb') as out, source.open('rb') as inp:
                    shutil.copyfileobj(inp,out)
                if not write_spotify_tags(str(stage),t) or audio_hash(stage)!=fingerprint:
                    raise RuntimeError(f'Tag/audio verification failed; source retained: {source}')
                if str(ID3(stage).get('TIT2'))!=t['Track Name']:
                    raise RuntimeError('Tag verification failed')
                journal[t['Track URI']]={'source':str(source),'destination':str(dest),'audio_sha256':fingerprint,'state':'planned'}
                save(journal_path,journal)  # durable recovery record before removing source
                os.link(stage,dest)  # atomic no-clobber publication, even on a rerun
                stage.unlink()
                with dest.open('rb') as published: os.fsync(published.fileno())
                if audio_hash(dest)!=fingerprint or audio_hash(source)!=fingerprint:
                    raise RuntimeError('File changed during transfer; source retained')
                source.unlink(); all_paths.append(str(dest))
                journal[t['Track URI']]['state']='moved'
                save(journal_path,journal)
            crate=write_crate(all_paths,cfg['crate_hierarchy'],cfg['serato_folder'])
            if dl.exists() and not any(dl.iterdir()): dl.rmdir()
            result={'library_paths':all_paths,'crate':crate,'pending_downloads':pending,
                    'review':sum(e['status']=='review' for e in entries),'downloads_remaining':[p.name for p in dl.iterdir()] if dl.exists() else []}
            save(artifact(cfg,'part2.json'),result)
            return result
        finally:
            pass
    return {'dry_run':True,'moves':[{'source':str(s),'destination':str(d)} for s,d,t in plans],
            'crate_hierarchy':cfg['crate_hierarchy'],'existing_paths':all_paths,'pending_downloads':pending}
