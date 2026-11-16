import datetime as dt
import decimal
import unittest
from talent_observatory.dimensions.interval_index import Interval,IntervalError,IntervalIndex
from talent_observatory.ingestion.data_quality import AllowedValues,Consistency,ForeignKey,Freshness,QualitySuite,RequiredFields,UniqueKey,ValueRange
from talent_observatory.warehouse.lineage_graph import LineageError,LineageGraph
from talent_observatory.metrics.metric_catalog import MetricCatalog,MetricDefinition,MetricError
from talent_observatory.publishing.change_capture import ChangeCapture,ChangeError

UTC=dt.timezone.utc
def moment(day,hour=0):return dt.datetime(2026,11,day,hour,tzinfo=UTC)

class IntervalIndexTests(unittest.TestCase):
    def test_add_and_active(self):
        index=IntervalIndex();index.add(Interval(moment(16),moment(17),'a','bed-1',{}));self.assertEqual(index.active('bed-1',moment(16,12))[0].key,'a')
    def test_overlap_rejected(self):
        index=IntervalIndex();index.add(Interval(moment(16),moment(18),'a','bed-1',{}))
        with self.assertRaises(IntervalError):index.add(Interval(moment(17),moment(19),'b','bed-1',{}))
    def test_other_resource_allowed(self):
        index=IntervalIndex();index.add(Interval(moment(16),moment(18),'a','bed-1',{}));index.add(Interval(moment(17),moment(19),'b','bed-2',{}));self.assertEqual(len(index.snapshot()),2)
    def test_remove_and_restore(self):
        index=IntervalIndex();index.add(Interval(moment(16),moment(18),'a','bed-1',{'x':1}));restored=IntervalIndex.restore(index.snapshot());self.assertEqual(restored.remove('a').payload['x'],1)
    def test_replace_rolls_back(self):
        index=IntervalIndex();index.add(Interval(moment(16),moment(18),'a','bed-1',{}));index.add(Interval(moment(18),moment(20),'b','bed-1',{}))
        with self.assertRaises(IntervalError):index.replace('a',Interval(moment(17),moment(19),'c','bed-1',{}))
        self.assertEqual(index.get('a').key,'a')
    def test_gaps(self):
        index=IntervalIndex();index.add(Interval(moment(17),moment(18),'a','bed-1',{}));self.assertEqual(index.gaps('bed-1',moment(16),moment(19)),((moment(16),moment(17)),(moment(18),moment(19))))
    def test_utilization(self):
        index=IntervalIndex();index.add(Interval(moment(16),moment(17),'a','bed-1',{}));self.assertEqual(index.utilization('bed-1',moment(16),moment(18)),0.5)
    def test_validation(self):self.assertEqual(IntervalIndex().validate(),())

class QualityTests(unittest.TestCase):
    def rows(self):return [{'id':'a','owner':'o1','q':2,'status':'active','updated':'2026-11-16T00:00:00+00:00'},{'id':'b','owner':'o1','q':-1,'status':'bad','updated':'2026-10-01T00:00:00+00:00'},{'id':'b','owner':'missing','q':3,'status':'active','updated':'2026-11-16T00:00:00+00:00'}]
    def suite(self):return QualitySuite([RequiredFields('id','owner'),ValueRange('q',0,10),AllowedValues('status',{'active','closed'}),UniqueKey('id'),ForeignKey('owner','owners'),Freshness('updated',dt.timedelta(days=10)),Consistency('even_quantity',lambda row:row['q']%2==0,'quantity must be even','warning')])
    def test_report_counts(self):
        report=self.suite().run(self.rows(),references={'owners':{'o1'}},now=moment(16));self.assertEqual(report.checked,3);self.assertEqual(report.passed,1);self.assertGreater(len(report.issues),3)
    def test_partition(self):
        valid,invalid,report=self.suite().partition(self.rows(),references={'owners':{'o1'}},now=moment(16));self.assertEqual([row['id'] for row in valid],['a']);self.assertEqual(len(invalid),2)
    def test_issue_categories(self):
        report=self.suite().run(self.rows(),references={'owners':{'o1'}},now=moment(16));self.assertIn('unique_key',report.by_rule);self.assertIn('foreign_key',report.by_rule);self.assertIn('warning',report.by_severity)
    def test_empty_score(self):self.assertEqual(QualitySuite([]).run([]).score,decimal.Decimal('1.0000'))

class LineageTests(unittest.TestCase):
    def graph(self):
        graph=LineageGraph();[graph.add_node(node,kind) for node,kind in [('raw','source'),('clean','dataset'),('metric','metric'),('report','report')]];graph.add_edge('raw','clean','transforms');graph.add_edge('clean','metric','aggregates');graph.add_edge('metric','report','publishes');return graph
    def test_ancestors(self):self.assertEqual(self.graph().ancestors('report'),('clean','metric','raw'))
    def test_descendants(self):self.assertEqual(self.graph().descendants('raw'),('clean','metric','report'))
    def test_path(self):self.assertEqual(self.graph().path('raw','report'),('raw','clean','metric','report'))
    def test_topological(self):self.assertEqual(self.graph().topological(),('raw','clean','metric','report'))
    def test_impacted_kind(self):self.assertEqual(self.graph().impacted(['raw'],['report']),('report',))
    def test_cycle_rejected(self):
        graph=self.graph()
        with self.assertRaises(LineageError):graph.add_edge('report','raw','loops')
    def test_export(self):self.assertEqual(len(self.graph().export()['edges']),3)
    def test_validate(self):self.assertEqual(self.graph().validate(),())

class MetricTests(unittest.TestCase):
    def catalog(self):
        catalog=MetricCatalog();catalog.register(MetricDefinition('records','count',filters=(('status','eq','active'),)));catalog.register(MetricDefinition('people','distinct','person'));catalog.register(MetricDefinition('amount','sum','amount',dimensions=('group',),missing='zero',precision=2));catalog.register(MetricDefinition('conversion','ratio',numerator='records',denominator='people',precision=3));return catalog
    def rows(self):return [{'person':'p1','status':'active','amount':'2.50','group':'a','stage':'view'},{'person':'p1','status':'active','amount':'3.50','group':'a','stage':'apply'},{'person':'p2','status':'closed','amount':None,'group':'b','stage':'view'}]
    def test_compute(self):
        result=self.catalog().compute(['records','people','conversion'],self.rows());self.assertEqual(result['records'],2);self.assertEqual(result['people'],2);self.assertEqual(result['conversion'],decimal.Decimal('1.000'))
    def test_grouped(self):self.assertEqual(self.catalog().grouped('amount',self.rows())[0]['amount'],decimal.Decimal('6.00'))
    def test_funnel(self):self.assertEqual(self.catalog().funnel(self.rows(),'person','stage',['view','apply'])[1]['entities'],1)
    def test_cohort(self):self.assertEqual(self.catalog().cohort([{'c':'2026-11','p':0,'id':'a'},{'c':'2026-11','p':0,'id':'b'}],'c','p','id')[0]['entities'],2)
    def test_duplicate_metric(self):
        catalog=self.catalog()
        with self.assertRaises(MetricError):catalog.register(MetricDefinition('records','count'))
    def test_definitions_sorted(self):self.assertEqual([definition.name for definition in self.catalog().definitions()],['amount','conversion','people','records'])

class ChangeCaptureTests(unittest.TestCase):
    def test_compare_operations(self):
        capture=ChangeCapture(['id']);changes=capture.compare([{'id':'a','v':1},{'id':'b','v':1}],[{'id':'a','v':2},{'id':'c','v':1}]);self.assertEqual([change.operation for change in changes],['update','delete','insert'])
    def test_apply_and_invert(self):
        capture=ChangeCapture(['id']);before=[{'id':'a','v':1}];after=[{'id':'a','v':2},{'id':'b','v':1}];changes=capture.compare(before,after);applied=capture.apply(before,changes);self.assertEqual(applied,tuple(after));self.assertEqual(capture.apply(applied,capture.invert(changes)),tuple(before))
    def test_strict_precondition(self):
        capture=ChangeCapture(['id']);changes=capture.compare([{'id':'a','v':1}],[{'id':'a','v':2}])
        with self.assertRaises(ChangeError):capture.apply([{'id':'a','v':9}],changes)
    def test_ignore_field(self):self.assertEqual(ChangeCapture(['id']).compare([{'id':'a','updated':1}],[{'id':'a','updated':2}],['updated']),())
    def test_summary(self):self.assertEqual(ChangeCapture(['id']).summary(ChangeCapture(['id']).compare([], [{'id':'a','v':1}]))['operations']['insert'],1)
