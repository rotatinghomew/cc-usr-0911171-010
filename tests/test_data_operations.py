import datetime as dt
import decimal
import tempfile
import unittest
from pathlib import Path
from talent_observatory.dimensions.schema_registry import FieldSpec,SchemaError,SchemaRegistry
from talent_observatory.ingestion.batch_ingestion import BatchIngestor,BatchReader,IngestionError
from talent_observatory.warehouse.version_history import VersionError,VersionHistory
from talent_observatory.metrics.query_engine import QueryEngine,QueryError
from talent_observatory.publishing.recovery_control import RecoveryController,RecoveryError
from talent_observatory.dimensions.industry_repository import IndustryRepository
from talent_observatory.storage import ConflictError,Database

class DataOperationsTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.db=Database(Path(self.temp.name)/'db.sqlite3')
    def tearDown(self): self.temp.cleanup()
    def registry(self):
        registry=SchemaRegistry(); registry.register('items',1,[FieldSpec('id','text',True,pattern=r'[a-z0-9-]+',aliases=('item_id',)),FieldSpec('quantity','integer',True,decimal.Decimal('0'),decimal.Decimal('100')),FieldSpec('day','date',True),FieldSpec('active','boolean',default=True)]); return registry
    def test_schema_alias_and_coercion(self):
        row,problems=self.registry().validate_row('items',{'item_id':'a-1','quantity':'2','day':'2026-11-16'},1); self.assertEqual(problems,[]); self.assertEqual(row['quantity'],2); self.assertTrue(row['active'])
    def test_schema_unknown_field(self): self.assertEqual(self.registry().validate_row('items',{'id':'a','quantity':1,'day':'2026-11-16','extra':1},1)[1][0].code,'unknown_field')
    def test_schema_batch_rejects_invalid(self):
        batch=self.registry().validate_batch('items',[{'id':'a','quantity':1,'day':'2026-11-16'},{'id':'b','quantity':-1,'day':'2026-11-16'}]); self.assertEqual(len(batch.valid),1); self.assertEqual(batch.rejected_rows,(2,))
    def test_schema_compatibility(self):
        registry=self.registry(); registry.register('items',2,[FieldSpec('id','text',True),FieldSpec('quantity','integer',True),FieldSpec('day','date',True),FieldSpec('active','boolean')]); self.assertTrue(registry.compatible('items',1,2)[0])
    def test_json_lines(self): self.assertEqual(list(BatchReader().json_lines('{"id":"a"}\n{"id":"b"}'))[1][1]['id'],'b')
    def test_csv_rows(self): self.assertEqual(list(BatchReader().csv_rows('id,q\na,1\n'))[0][1]['q'],'1')
    def test_ingestion_duplicates(self):
        result=BatchIngestor(['id']).ingest([(1,{'id':'a','v':1}),(2,{'id':'a','v':1})]); self.assertEqual(result.statistics['duplicates'],1)
    def test_ingestion_conflicting_duplicate(self):
        result=BatchIngestor(['id'],'reject').ingest([(1,{'id':'a','v':1}),(2,{'id':'a','v':2})]); self.assertEqual(result.rejected[0][1],'conflicting duplicate')
    def test_ingestion_reconcile(self):
        ingestor=BatchIngestor(['id']); before=ingestor.ingest([(1,{'id':'a','v':1})]); after=ingestor.ingest([(1,{'id':'a','v':2}),(2,{'id':'b','v':1})]); diff=ingestor.reconcile(before,after); self.assertEqual(diff['added'],('b',)); self.assertEqual(diff['changed'],('a',))
    def test_version_diff(self):
        history=VersionHistory(); history.append('a',{'x':1,'nested':{'y':2}},'u','create'); history.append('a',{'x':2,'nested':{'y':2,'z':3}},'u','change'); self.assertEqual({c.kind for c in history.diff('a',1,2)},{'changed','added'})
    def test_version_conflict(self):
        history=VersionHistory(); history.append('a',{'x':1},'u','create')
        with self.assertRaises(VersionError): history.append('a',{'x':2},'u','change',expected_version=0)
    def test_version_chain(self):
        history=VersionHistory(); history.append('a',{'x':1},'u','create'); history.append('a',{'x':2},'u','change'); self.assertEqual(history.verify_chain('a'),())
    def test_query_filter_sort_page(self):
        engine=QueryEngine(); rows=[{'id':'a','q':2},{'id':'b','q':1},{'id':'c','q':3}]; selected=engine.filter(rows,[{'field':'q','op':'gte','value':2}]); page=engine.page(engine.sort(selected,[('q',True)]),0,1); self.assertEqual(page.items[0]['id'],'c'); self.assertEqual(page.next_offset,1)
    def test_query_aggregate(self):
        result=QueryEngine().aggregate([{'g':'a','q':1},{'g':'a','q':3}],['g'],[{'name':'total','op':'sum','field':'q'},{'name':'count','op':'count'}]); self.assertEqual(result[0]['total'],decimal.Decimal('4'))
    def test_query_histogram(self): self.assertEqual(sum(item['count'] for item in QueryEngine().histogram([{'q':1},{'q':5}],'q',[decimal.Decimal('3')])),2)
    def test_recovery_checkpoint_idempotent(self):
        recovery=RecoveryController(); a=recovery.checkpoint('op','loaded',{'x':1}); b=recovery.checkpoint('op','loaded',{'x':1}); self.assertEqual(a.sequence,b.sequence)
    def test_recovery_retry_backoff(self):
        recovery=RecoveryController(); start=dt.datetime(2026,1,1,tzinfo=dt.timezone.utc); recovery.record_attempt('op',start,start+dt.timedelta(seconds=1),False,'boom'); allowed,due=recovery.retry_allowed('op',3,start+dt.timedelta(seconds=3)); self.assertFalse(allowed); self.assertGreater(due,start)
    def test_recovery_compensation(self):
        recovery=RecoveryController(); sequence=recovery.add_compensation('op','release',{'id':'a'}); self.assertEqual(len(recovery.pending_compensations('op')),1); recovery.complete_compensation('op',sequence); self.assertEqual(recovery.pending_compensations('op'),())
    def test_repository_lifecycle_and_overlap(self):
        repo=IndustryRepository(self.db); version=repo.create({'industry'+'_id':'item-1','owner_id':'owner-1','category':'c','status':'draft','effective_from':'2026-11-16','effective_to':'2026-11-20','quantity':2,'amount':'3.00'}); self.assertEqual(version,1); self.assertEqual(repo.transition('item-1','received',1),2); self.assertEqual(len(repo.overlaps('owner-1',dt.date(2026,11,18),dt.date(2026,11,22))),1)
    def test_repository_version_conflict(self):
        repo=IndustryRepository(self.db); repo.create({'industry'+'_id':'item-1','owner_id':'owner-1','category':'c','status':'draft','effective_from':'2026-11-16'})
        with self.assertRaises(ConflictError): repo.update('item-1',{'quantity':4},0)
