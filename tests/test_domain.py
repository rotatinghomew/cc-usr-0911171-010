import decimal
import unittest
from talent_observatory.warehouse.engine import WarehouseEngine

class DomainTests(unittest.TestCase):
    def setUp(self): self.engine=WarehouseEngine()

    def row(self,**changes):
        value={'id':'fact-1','natural_key':'job-1','dimension_code':'ai','effective_from':'2026-11-16','values':[10,5]};value.update(changes);return value
    def context(self,**changes):
        value={'dimensions':{'ai':'industry-ai'}};value.update(changes);return value
    def test_mapped_dimension(self):self.assertEqual(self.engine.evaluate(self.row(),self.context()).facts['mapped_dimension'],'industry-ai')
    def test_measure_sum(self):self.assertEqual(self.engine.evaluate(self.row(),self.context()).value,decimal.Decimal('15'))
    def test_unmapped(self):self.assertIn('unmapped_dimension',self.engine.evaluate(self.row(dimension_code='unknown'),self.context()).reasons)
    def test_invalid_period(self):self.assertIn('invalid_dimension_period',self.engine.evaluate(self.row(valid_to='2026-01-01'),self.context()).reasons)
    def test_rank_large_fact(self):self.assertEqual(self.engine.rank([self.row(id='small',values=[1]),self.row(id='large',values=[9])],self.context())[0].key,'large')
    def test_compare_measure(self):self.assertEqual(self.engine.compare(self.engine.rank([self.row(values=[1])],self.context()),self.engine.rank([self.row(values=[2])],self.context()))['change_count'],1)

