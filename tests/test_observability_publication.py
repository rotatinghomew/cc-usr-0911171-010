import datetime as dt
import decimal
import unittest
from talent_observatory.publishing.anomaly_monitor import AnomalyError,AnomalyMonitor
from talent_observatory.dimensions.snapshot_publisher import PublicationError,SnapshotPublisher

class AnomalyTests(unittest.TestCase):
    def rows(self):return [{'series':'applications','period':f'2026-11-{day:02d}','value':value,'dimensions':{'site':'a'}} for day,value in enumerate([10,11,9,10,10,35],1)]
    def test_detects_spike(self):
        anomalies=AnomalyMonitor(minimum_history=4).detect(self.rows(),window=5);self.assertEqual(anomalies[-1].period,'2026-11-06');self.assertIn('relative_change',anomalies[-1].reasons)
    def test_insufficient_history(self):self.assertEqual(AnomalyMonitor(minimum_history=5).detect(self.rows()[:4]),())
    def test_rolling_history(self):
        monitor=AnomalyMonitor();observations=monitor.normalize(self.rows());self.assertEqual(monitor.rolling(observations,3)[('applications','2026-11-04')]['history'],decimal.Decimal('3'))
    def test_dimension_comparison(self):self.assertEqual(AnomalyMonitor().compare_dimensions(self.rows(),'site')['a']['count'],decimal.Decimal('6'))
    def test_incident_summary(self):
        monitor=AnomalyMonitor(minimum_history=4);summary=monitor.incident_summary(monitor.detect(self.rows(),window=5));self.assertGreaterEqual(summary['anomalies'],1)
    def test_invalid_config(self):
        with self.assertRaises(AnomalyError):AnomalyMonitor(minimum_history=1)

class PublicationTests(unittest.TestCase):
    def setUp(self):self.publisher=SnapshotPublisher();self.datasets={'applications':[{'id':'a','q':1},{'id':'b','q':2}],'stations':[{'id':'s1'}]}
    def test_publish_verify(self):
        publication=self.publisher.publish('p1',self.datasets,dt.datetime(2026,11,16,tzinfo=dt.timezone.utc));self.assertEqual(self.publisher.verify(publication),());self.assertEqual(publication.manifest['datasets']['applications'],2)
    def test_inventory(self):self.assertEqual(self.publisher.inventory(self.publisher.publish('p1',self.datasets))['records'],3)
    def test_difference(self):
        left=self.publisher.publish('p1',self.datasets);right=self.publisher.publish('p2',{**self.datasets,'applications':[{'id':'a','q':3}]});self.assertEqual(right.manifest['datasets']['applications'],1);self.assertIn('applications.jsonl',self.publisher.difference(left,right)['changed'])
    def test_json_file(self):self.assertEqual(self.publisher.json_file('a.json',[{'id':'a'}]).media_type,'application/json')
    def test_csv_file(self):self.assertIn(b'id',self.publisher.csv_file('a.csv',[{'id':'a'}],['id']).content)
    def test_empty_id(self):
        with self.assertRaises(PublicationError):self.publisher.publish('',self.datasets)
