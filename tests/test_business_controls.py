import datetime as dt
import decimal
import unittest
from talent_observatory.dimensions.state_policy import StatePolicy,StatePolicyError,Transition
from talent_observatory.ingestion.reconciliation import Reconciler,ReconciliationError
from talent_observatory.warehouse.privacy_projection import FieldPolicy,PrivacyError,PrivacyProjector
from talent_observatory.metrics.notification_router import NotificationError,NotificationRouter,Subscription

UTC=dt.timezone.utc

class StatePolicyTests(unittest.TestCase):
    def policy(self):return StatePolicy('draft',[Transition('draft','received','submit',frozenset({'applicant'})),Transition('received','validated','validate',frozenset({'reviewer'}),'documents_ok'),Transition('validated','active','activate',frozenset({'operator'})),Transition('active','completed','complete',frozenset({'operator'}),terminal=True),Transition('received','cancelled','cancel',frozenset({'applicant','reviewer'}),terminal=True)],{'documents_ok':lambda facts,context:bool(facts.get('documents_ok'))})
    def test_authorized_transition(self):
        record,decision=self.policy().apply({'state':'draft','version':0},'submit','applicant',{'now':dt.datetime(2026,11,16,tzinfo=UTC)});self.assertEqual(record['state'],'received');self.assertTrue(decision.allowed)
    def test_role_denied(self):self.assertIn('role_not_authorized',self.policy().decide('received','validate','applicant',{'documents_ok':True}).reasons)
    def test_guard_denied(self):self.assertIn('guard_failed:documents_ok',self.policy().decide('received','validate','reviewer',{'documents_ok':False}).reasons)
    def test_actions(self):self.assertEqual(self.policy().actions('received','applicant'),('cancel',))
    def test_terminal_states(self):self.assertEqual(self.policy().terminal_states(),('cancelled','completed'))
    def test_shortest_path(self):self.assertEqual(self.policy().shortest_actions('draft','completed'),('submit','validate','activate','complete'))
    def test_validation(self):self.assertEqual(self.policy().validate(),())
    def test_illegal_apply(self):
        with self.assertRaises(StatePolicyError):self.policy().apply({'state':'draft'},'complete','operator')

class ReconciliationTests(unittest.TestCase):
    def test_balanced(self):
        result=Reconciler(['id']).reconcile([{'id':'a','q':2,'amount':'5'}],[{'id':'a','q':2,'amount':'5'}],['q','amount'],total_fields=['amount']);self.assertTrue(result.balanced)
    def test_tolerance(self):
        result=Reconciler(['id']).reconcile([{'id':'a','amount':'5.00'}],[{'id':'a','amount':'5.01'}],['amount'],{'amount':decimal.Decimal('0.02')});self.assertFalse(result.matches[0].tolerance_breaches)
    def test_breach(self):
        result=Reconciler(['id']).reconcile([{'id':'a','amount':'5.00'}],[{'id':'a','amount':'6.00'}],['amount'],{'amount':decimal.Decimal('0.02')});self.assertEqual(result.matches[0].tolerance_breaches,('amount',))
    def test_left_and_right_only(self):
        result=Reconciler(['id']).reconcile([{'id':'a'}],[{'id':'b'}],[]);self.assertEqual(result.left_only[0]['id'],'a');self.assertEqual(result.right_only[0]['id'],'b')
    def test_ambiguous(self):self.assertEqual(Reconciler(['id']).reconcile([{'id':'a'},{'id':'a'}],[],[]).ambiguous,('a',))
    def test_repair_plan(self):self.assertEqual(Reconciler(['id']).repair_plan(Reconciler(['id']).reconcile([{'id':'a'}],[],[]))[0]['action'],'insert_right')
    def test_conservation(self):self.assertEqual(Reconciler(['id']).conservation([{'d':'5','c':'3'},{'d':'0','c':'2'}],'d','c')['all'],decimal.Decimal('0'))
    def test_missing_key(self):
        with self.assertRaises(ReconciliationError):Reconciler(['id']).reconcile([{'x':1}],[],[])

class PrivacyTests(unittest.TestCase):
    def projector(self):return PrivacyProjector([FieldPolicy('name','mask',keep_start=1),FieldPolicy('email','tokenize'),FieldPolicy('phone','last4'),FieldPolicy('birthday','generalize_date'),FieldPolicy('ip','generalize_ip'),FieldPolicy('secret','drop'),FieldPolicy('internal','keep',frozenset({'auditor'}))],b'0123456789abcdef')
    def row(self):return {'name':'Nicole','email':'n@example.com','phone':'13800138000','birthday':'2000-05-06','ip':'192.168.1.9','secret':'x','internal':'case-1'}
    def test_projection(self):
        projected=self.projector().project(self.row());self.assertEqual(projected['name'][0],'N');self.assertTrue(projected['phone'].endswith('8000'));self.assertNotIn('secret',projected);self.assertEqual(projected['birthday'],'2000-05')
    def test_auditor_keep(self):self.assertEqual(self.projector().project(self.row(),'auditor')['internal'],'case-1')
    def test_stable_token(self):self.assertEqual(self.projector().project(self.row())['email'],self.projector().project(self.row())['email'])
    def test_join_key(self):self.assertEqual(len(self.projector().stable_join_key(self.row(),['email','phone'])),24)
    def test_audit(self):
        projected=self.projector().project(self.row());self.assertEqual(self.projector().audit(self.row(),projected),())
    def test_plaintext_detection(self):self.assertEqual(set(self.projector().detect_plaintext(self.row())),{'email:email','phone:phone'})
    def test_short_secret(self):
        with self.assertRaises(PrivacyError):PrivacyProjector([],b'short')

class NotificationTests(unittest.TestCase):
    def router(self):
        router=NotificationRouter();router.subscribe(Subscription('u1',('sms','app'),('result',),22,7));router.subscribe(Subscription('u2',('email',),('result','reminder')));return router
    def test_route_channels(self):self.assertEqual(len(self.router().route('result',{'id':'a'},dt.datetime(2026,11,16,10,tzinfo=UTC))),3)
    def test_topic_filter(self):self.assertEqual(len(self.router().route('reminder',{'id':'a'},dt.datetime(2026,11,16,10,tzinfo=UTC))),1)
    def test_quiet_hours(self):
        deliveries=self.router().route('result',{'id':'a'},dt.datetime(2026,11,16,23,tzinfo=UTC),['u1']);self.assertEqual(deliveries[0].scheduled_at.hour,7);self.assertEqual(deliveries[0].scheduled_at.day,17)
    def test_dedupe_after_sent(self):
        router=self.router();delivery=router.route('result',{'id':'a'},dt.datetime(2026,11,16,10,tzinfo=UTC),['u1'])[0];router.mark_sent(delivery);self.assertEqual(router.route('result',{'id':'a'},dt.datetime(2026,11,16,11,tzinfo=UTC),['u1']),())
    def test_failure_backoff(self):
        router=self.router();delivery=router.route('result',{'id':'a'},dt.datetime(2026,11,16,10,tzinfo=UTC),['u1'])[0];router.mark_failed(delivery);self.assertEqual(router.retry_at(delivery,dt.datetime(2026,11,16,10,tzinfo=UTC)).minute,2)
    def test_channel_batches(self):
        router=self.router();groups=router.batch_by_channel(router.route('result',{'id':'a'},dt.datetime(2026,11,16,10,tzinfo=UTC)));self.assertEqual(set(groups),{'sms','app','email'})
    def test_receipt(self):
        router=self.router();delivery=router.route('result',{'id':'a'},dt.datetime(2026,11,16,10,tzinfo=UTC))[0];self.assertEqual(router.receipt(delivery,'delivered',dt.datetime(2026,11,16,10,tzinfo=UTC))['status'],'delivered')
    def test_invalid_channel(self):
        with self.assertRaises(NotificationError):NotificationRouter().subscribe(Subscription('u',('fax',),('x',)))
