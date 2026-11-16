import datetime as dt
import tempfile
import unittest
from pathlib import Path
from talent_observatory.contracts import Event
from talent_observatory.storage import ConflictError,Database,NotFoundError

class StorageTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.db=Database(Path(self.temp.name)/'db.sqlite3')
    def tearDown(self): self.temp.cleanup()
    def record(self,identifier='one',owner='owner-1'): return {'industry_id':identifier,'owner_id':owner,'category':'category','status':'active','effective_from':'2026-11-16','effective_to':'2026-11-20','quantity':2,'amount':'3.50','attributes':{'a':1}}
    def test_put_and_get(self):
        with self.db.transaction() as c: self.assertEqual(self.db.put_record(c,'industry',self.record()),1)
        self.assertEqual(self.db.get_record('industry','one')['owner_id'],'owner-1')
    def test_update_increments(self):
        with self.db.transaction() as c: self.db.put_record(c,'industry',self.record())
        with self.db.transaction() as c: self.assertEqual(self.db.put_record(c,'industry',self.record(),1),2)
    def test_conflict(self):
        with self.db.transaction() as c: self.db.put_record(c,'industry',self.record())
        with self.assertRaises(ConflictError):
            with self.db.transaction() as c: self.db.put_record(c,'industry',self.record(),0)
    def test_missing(self):
        with self.assertRaises(NotFoundError): self.db.get_record('industry','missing')
    def test_owner_filter(self):
        with self.db.transaction() as c:
            self.db.put_record(c,'industry',self.record('one','a')); self.db.put_record(c,'industry',self.record('two','b'))
        self.assertEqual(len(self.db.list_records('industry',owner_id='a')),1)
    def test_event_append(self):
        event=Event('event-1','aggregate','one','created',dt.datetime.now(dt.timezone.utc),{'a':1},1)
        with self.db.transaction() as c: self.db.append_event(c,event)
        self.assertEqual(self.db.events_for('aggregate','one')[0]['payload']['a'],1)
    def test_idempotency(self):
        with self.db.transaction() as c: self.db.remember(c,'scope','key','hash',{'ok':True})
        self.assertTrue(self.db.recalled('scope','key','hash')['ok'])
    def test_idempotency_mismatch(self):
        with self.db.transaction() as c: self.db.remember(c,'scope','key','hash',{'ok':True})
        with self.assertRaises(ConflictError): self.db.recalled('scope','key','other')
    def test_outbox(self):
        with self.db.transaction() as c: self.db.enqueue(c,'m1','topic','one',{'ok':1})
        self.assertEqual(len(self.db.pending_messages()),1); self.db.mark_delivered('m1'); self.assertEqual(self.db.pending_messages(),[])
    def test_snapshot_versions(self): self.assertEqual(self.db.save_snapshot('n','s',{'x':1},'h'),1); self.assertEqual(self.db.save_snapshot('n','s',{'x':2},'h2'),2)
    def test_snapshot_latest(self): self.db.save_snapshot('n','s',{'x':1},'h'); self.assertEqual(self.db.load_snapshot('n','s')['content']['x'],1)
    def test_lock(self):
        expiry=dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=1); self.assertTrue(self.db.acquire_lock('x','one','a',expiry)); self.assertFalse(self.db.acquire_lock('x','one','b',expiry)); self.assertTrue(self.db.release_lock('x','one','a'))
    def test_counts(self):
        with self.db.transaction() as c: self.db.put_record(c,'industry',self.record())
        self.assertEqual(self.db.counts()['industry'],1)
