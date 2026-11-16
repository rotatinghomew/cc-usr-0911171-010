import unittest
from talent_observatory.dimensional_model.mart import TalentMart
class TalentMartTests(unittest.TestCase):
 def setUp(self):self.m=TalentMart();self.dim={'industry':[{'code':'ai','surrogate_key':'i1','valid_from':'2026-01-01'}],'region':[{'code':'sy','surrogate_key':'r1','valid_from':'2026-01-01'}]};self.fact={'source':'jobs','source_key':'1','event_date':'2026-11-16','industry_code':'ai','region_code':'sy','openings':10,'seekers':4,'salary':10000}
 def test_resolve_scd(self):self.assertEqual(self.m.resolve_dimension('ai','2026-11-16',self.dim['industry']),'i1')
 def test_ingest_enriches_keys(self):self.assertEqual(self.m.ingest([self.fact],self.dim)['accepted'][0]['region_key'],'r1')
 def test_unmapped_rejected(self):self.assertEqual(self.m.ingest([{**self.fact,'industry_code':'missing'}],self.dim)['rejected'][0]['reason'],'dimension_resolution_missing')
 def test_aggregate_gap(self):self.assertEqual(self.m.aggregate([{**self.fact,'industry_key':'i1'}],['industry_key'])[0]['gap'],6)
 def test_flow_matrix(self):self.assertEqual(self.m.flow_matrix([{'origin_region':'a','target_region':'b','people':3}])[0]['people'],3)
 def test_recompute_delta(self):self.assertEqual(len(self.m.recompute_delta([{'key':('i1',),'gap':1}],[{'key':('i1',),'gap':2}])),1)
