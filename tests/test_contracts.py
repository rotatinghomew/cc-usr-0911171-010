import datetime as dt
import decimal
import unittest
from talent_observatory.contracts import *

class ContractTests(unittest.TestCase):
    def test_text_normalization(self): self.assertEqual(require_text('  hello   world  ','x'),'hello world')
    def test_text_type(self):
        with self.assertRaises(ContractError): require_text(3,'x')
    def test_text_minimum(self):
        with self.assertRaises(ContractError): require_text('','x')
    def test_identifier(self): self.assertEqual(require_identifier('abc-1','x'),'abc-1')
    def test_identifier_rejects_space(self):
        with self.assertRaises(ContractError): require_identifier('a b','x')
    def test_integer(self): self.assertEqual(require_integer(4,'x'),4)
    def test_integer_rejects_bool(self):
        with self.assertRaises(ContractError): require_integer(True,'x')
    def test_decimal(self): self.assertEqual(require_decimal('4.236','x'),decimal.Decimal('4.24'))
    def test_date(self): self.assertEqual(require_date('2026-11-16','x'),dt.date(2026,11,16))
    def test_datetime_normalizes_timezone(self): self.assertEqual(require_datetime('2026-11-16T08:00:00+08:00','x').hour,0)
    def test_canonical_json_order(self): self.assertEqual(canonical_json({'b':1,'a':2}),'{"a":2,"b":1}')
    def test_fingerprint_stable(self): self.assertEqual(fingerprint({'a':1}),fingerprint({'a':1}))
    def test_event_sequence(self):
        event=Event('event-1','aggregate','item-1','created',dt.datetime.now(dt.timezone.utc),{},1); self.assertEqual(event.sequence,1)
    def test_event_rejects_zero_sequence(self):
        with self.assertRaises(ContractError): Event('event-1','aggregate','item-1','created',dt.datetime.now(dt.timezone.utc),{},0)
    def test_command_result_dict(self): self.assertTrue(CommandResult('x',1,'active',True).as_dict()['changed'])
