import csv
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from dj_pipeline import workspace as w
from dj_pipeline import serato4 as s


def database(folder):
    folder.mkdir()
    with closing(sqlite3.connect(folder/'root.sqlite')) as c, c:
        c.executescript('''
        CREATE TABLE serato(revision INTEGER); INSERT INTO serato VALUES(1);
        CREATE TABLE master(revision INTEGER); INSERT INTO master VALUES(1);
        CREATE TABLE space(id INTEGER PRIMARY KEY,name TEXT,revision INTEGER);
        INSERT INTO space VALUES(1,'Serato Library',1);
        CREATE TABLE container(id INTEGER PRIMARY KEY,revision INTEGER,parent_id INTEGER,name TEXT,type INTEGER,list_order INTEGER,space_id INTEGER);
        INSERT INTO container VALUES(1,1,0,'Library',0,0,1);
        CREATE TABLE asset(id INTEGER PRIMARY KEY,revision INTEGER,portable_id TEXT UNIQUE,file_name TEXT,file_size INTEGER,type TEXT,format TEXT,name TEXT);
        CREATE TABLE space_asset(id INTEGER PRIMARY KEY,asset_id INTEGER REFERENCES asset(id),space_id INTEGER REFERENCES space(id),UNIQUE(asset_id,space_id));
        CREATE TABLE container_asset(id INTEGER PRIMARY KEY,revision INTEGER,container_id INTEGER REFERENCES container(id),space_asset_id INTEGER REFERENCES space_asset(id),list_order INTEGER);
        ''')


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve(); self.exp=self.root/'Exportify'; self.folder=self.exp/'Genre'/'Playlist'
        self.folder.mkdir(parents=True); self.lib=self.root/'Library'; self.lib.mkdir()
        self.db=self.root/'Serato'; database(self.db)
        self.t={'Track URI':'spotify:track:example','Track Name':'Test Song','Artist Name(s)':'Test Artist','Album Name':'Album','Duration (ms)':'2000'}
        self.csv=self.folder/'Different title.csv'
        with self.csv.open('w') as f:
            out=csv.DictWriter(f,fieldnames=self.t);out.writeheader();out.writerow(self.t)
        self.cfg=w.prepare(self.csv,self.lib,self.exp,self.db)
        self.guard=patch.object(s.subprocess,'run',return_value=subprocess.CompletedProcess([],1)); self.guard.start();self.addCleanup(self.guard.stop)
        self.platform=patch.object(s.sys,'platform','darwin');self.platform.start();self.addCleanup(self.platform.stop)

    def seed(self):
        if not shutil.which('ffmpeg'): self.skipTest('ffmpeg required for real MP3 transfer tests')
        dl=Path(self.cfg['downloads']);dl.mkdir()
        self.source=dl/'Test Artist - Test Song.mp3'
        # Use Popen directly because only the Serato process probe is mocked.
        proc=subprocess.Popen(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=2','-codec:a','libmp3lame',str(self.source)])
        self.assertEqual(proc.wait(),0)
        w.save(w.artifact(self.cfg,'matched.json'),[])
        w.save(w.artifact(self.cfg,'part1.json'),{'complete':True,'csv_sha256':hashlib.sha256(self.csv.read_bytes()).hexdigest()})
        w.save(w.artifact(self.cfg,'youtube.json'),[{'track':self.t,'status':'ready','url':'https://www.youtube.com/watch?v=abcdefghijk','yt_title':self.source.stem}])

    def test_paths_and_copied_entrypoint_from_other_cwd(self):
        self.assertEqual(self.cfg['crate_hierarchy'],['LEROY CRATE LIBRARY','EXPORTIFY CRATES','Genre','Playlist'])
        proc=subprocess.Popen([sys.executable,str(self.folder/'playlist_part1_get_urls.py'),'--prepare-only'],cwd=self.root,stdout=subprocess.PIPE)
        data=json.loads(proc.communicate()[0]); self.assertEqual(proc.returncode,0)
        self.assertEqual(data['csv'],str(self.csv))
        self.assertEqual(w.artifact(data,'youtube.json').parent,self.folder)

    def test_relocated_workspace(self):
        new=self.root/'Relocated';shutil.move(self.folder,new)
        cfg=w.load_config(new/'Different title_pipeline_config.json')
        self.assertEqual(Path(cfg['csv']).parent,new)
        self.assertEqual(Path(cfg['downloads']),new/'Downloads')
        self.assertEqual(cfg['library'],str(self.lib))

    def test_existing_scripts_preserved_before_update(self):
        script=self.folder/'playlist_part2_process.py';script.write_text('# custom')
        with self.assertRaises(FileExistsError):w.prepare(self.csv,self.lib,self.exp,self.db)
        w.prepare(self.csv,self.lib,self.exp,self.db,backup_existing=True)
        self.assertEqual(next(self.folder.glob('pipeline-script-backup-*/playlist_part2_process.py')).read_text(),'# custom')

    def test_dry_run_and_move_and_idempotency(self):
        self.seed();before=w.audio_hash(self.source)
        preview=w.part2(self.cfg); self.assertTrue(self.source.exists());self.assertEqual(len(preview['moves']),1)
        result=w.part2(self.cfg,True);dest=Path(result['library_paths'][0])
        self.assertEqual(w.audio_hash(dest),before);self.assertFalse(Path(self.cfg['downloads']).exists())
        self.assertEqual(result['crate']['tracks_added'],1)
        self.assertFalse(result['crate']['ui_verified'])
        again=w.part2(self.cfg,True);self.assertEqual(again['crate']['tracks_added'],0)
        self.assertEqual(len(list(self.lib.rglob('*.mp3'))),1)

    def test_tag_failure_retains_source(self):
        self.seed()
        with patch.object(w,'write_spotify_tags',return_value=False),self.assertRaises(RuntimeError):w.part2(self.cfg,True)
        self.assertTrue(self.source.exists());self.assertEqual(list(self.lib.rglob('*.mp3')),[])

    def test_unmatched_file_retains_folder(self):
        self.seed();unknown=self.source.parent/'unmatched.txt';unknown.write_text('retain')
        result=w.part2(self.cfg,True)
        self.assertEqual(result['downloads_remaining'],['unmatched.txt']);self.assertTrue(unknown.exists())

    def test_collision_never_overwrites(self):
        self.seed();dest=self.lib/'Test Artist'/'Album'/'Test Artist - Test Song.mp3';dest.parent.mkdir(parents=True);dest.write_bytes(b'old')
        with self.assertRaises(FileExistsError):w.part2(self.cfg,True)
        self.assertEqual(dest.read_bytes(),b'old');self.assertTrue(self.source.exists())

    def test_running_serato_blocks_moves(self):
        self.seed()
        with patch.object(s.subprocess,'run',return_value=subprocess.CompletedProcess([],0)),self.assertRaises(RuntimeError):w.part2(self.cfg,True)
        self.assertTrue(self.source.exists())

    def test_recover_after_published_before_source_delete(self):
        self.seed();original=Path.unlink
        def fail_source(p,*a,**kw):
            if p==self.source:raise OSError('simulated interruption')
            return original(p,*a,**kw)
        with patch.object(Path,'unlink',fail_source),self.assertRaises(OSError):w.part2(self.cfg,True)
        self.assertTrue(self.source.exists())
        result=w.part2(self.cfg,True);self.assertEqual(len(result['library_paths']),1);self.assertFalse(self.source.exists())

    def test_ambiguous_download_title_stops(self):
        self.seed();entries=w.read(w.artifact(self.cfg,'youtube.json'));entries.append({**entries[0],'track':{**self.t,'Track URI':'spotify:other'}})
        w.save(w.artifact(self.cfg,'youtube.json'),entries)
        with self.assertRaises(ValueError):w.part2(self.cfg,True)
        self.assertTrue(self.source.exists())

    def test_database_preserves_other_crates_and_rolls_back_conflicts(self):
        f=self.lib/'a.mp3';f.write_bytes(b'a')
        a=s.write_crate([str(f)],['Existing'],self.db)
        s.write_crate([str(f)],['New','Nested'],self.db)
        with closing(sqlite3.connect(self.db/'root.sqlite')) as c, c:
            self.assertEqual(c.execute('select count(*) from container_asset where container_id=?',(a['container_id'],)).fetchone()[0],1)
            c.execute("insert into container values(99,1,1,'Conflict',2,9,1)")
        with self.assertRaises(RuntimeError):s.write_crate([str(f)],['Conflict'],self.db)
        self.assertTrue(list(self.db.glob('*.pipeline-backup.*')))

    def test_unsupported_schema_rejected(self):
        with closing(sqlite3.connect(self.db/'root.sqlite')) as c, c:c.execute('drop table master')
        with self.assertRaises(RuntimeError):s.preflight(self.db)

    def test_duration_alone_does_not_approve_wrong_song(self):
        wrong={'id':'abcdefghijk','title':'Other artist - Wrong song','duration':2,'channel':'Other artist'}
        with patch('dj_pipeline.downloaders.search_youtube',return_value=[wrong]):result=w.part1(self.cfg)
        self.assertEqual(result['ready'],0);self.assertEqual(result['review'],1)
        self.assertEqual(w.read(w.artifact(self.cfg,'4K_IMPORT.json'))['items'],[])

    def test_part1_exports_and_resumes_without_searching_again(self):
        good={'id':'abcdefghijk','title':'Test Artist - Test Song (Official Audio)','duration':2,'channel':'Test Artist'}
        with patch('dj_pipeline.downloaders.search_youtube',return_value=[good]) as search:
            result=w.part1(self.cfg);w.part1(self.cfg);self.assertEqual(search.call_count,1)
        self.assertEqual(result['ready'],1)
        self.assertEqual(w.read(w.artifact(self.cfg,'4K_IMPORT.json'))['items'][0]['downloadPreferences']['outputDir'],self.cfg['downloads'])

    def test_changed_csv_blocks_processing(self):
        self.seed();self.csv.write_text(self.csv.read_text()+'\n')
        with self.assertRaises(RuntimeError):w.part2(self.cfg,True)
        self.assertTrue(self.source.exists())


if __name__=='__main__': unittest.main()
