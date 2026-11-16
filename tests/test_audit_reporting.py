import tempfile
import unittest
from pathlib import Path
from talent_observatory.audit import AuditVerifier
from talent_observatory.reporting import Reporter
from talent_observatory.storage import Database

class AuditReportingTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.db=Database(Path(self.temp.name)/'db.sqlite3')
    def tearDown(self): self.temp.cleanup()
    def test_empty_manifest(self): self.assertEqual(AuditVerifier().manifest([])['count'],0)
    def test_manifest_stable(self): self.assertEqual(AuditVerifier().manifest([{'id':'a','x':1}])['sha256'],AuditVerifier().manifest([{'x':1,'id':'a'}])['sha256'])
    def test_manifest_detects_change(self): self.assertNotEqual(AuditVerifier().manifest([{'id':'a','x':1}])['sha256'],AuditVerifier().manifest([{'id':'a','x':2}])['sha256'])
    def test_event_gap(self): self.assertEqual(AuditVerifier().event_chain([{'event_id':'a','aggregate_id':'x','sequence':2}])[0].code,'sequence_gap')
    def test_duplicate_event(self): self.assertTrue(any(p.code=='duplicate_event' for p in AuditVerifier().event_chain([{'event_id':'a','sequence':1},{'event_id':'a','sequence':2}])))
    def test_overview_empty(self): self.assertEqual(Reporter(self.db).overview()['total_records'],0)
    def test_export_json(self): self.assertIn('manifest',Reporter(self.db).export_json())
    def test_export_csv_header(self): self.assertIn('owner_id',Reporter(self.db).export_csv('industry'))
    def test_quality_empty(self): self.assertTrue(Reporter(self.db).quality('industry')['valid'])
