import datetime as dt
import unittest
from talent_observatory.warehouse.access_audit import AccessAuditor,AccessError

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,16,10,tzinfo=UTC)

class AccessAuditTests(unittest.TestCase):
    def auditor(self):
        auditor=AccessAuditor();auditor.grant('person-1','reviewer-1',{'eligibility_review'},{'diploma','invitation'},NOW-dt.timedelta(days=1),NOW+dt.timedelta(days=1));return auditor
    def test_authorized(self):self.assertTrue(self.auditor().authorize('person-1','reviewer-1','eligibility_review',{'diploma'},NOW).allowed)
    def test_wrong_purpose(self):self.assertIn('purpose_not_granted',self.auditor().authorize('person-1','reviewer-1','marketing',{'diploma'},NOW).reasons)
    def test_extra_field(self):self.assertTrue(any(reason.startswith('fields_not_granted') for reason in self.auditor().authorize('person-1','reviewer-1','eligibility_review',{'phone'},NOW).reasons))
    def test_revoke(self):
        auditor=self.auditor();grant=auditor.grants[0];auditor.revoke(grant,NOW-dt.timedelta(minutes=1));self.assertFalse(auditor.authorize('person-1','reviewer-1','eligibility_review',{'diploma'},NOW).allowed)
    def test_require_raises(self):
        with self.assertRaises(AccessError):self.auditor().require('person-2','reviewer-1','eligibility_review',{'diploma'},NOW)
    def test_report(self):
        auditor=self.auditor();auditor.authorize('person-1','reviewer-1','eligibility_review',{'diploma'},NOW);auditor.authorize('person-2','reviewer-1','eligibility_review',{'diploma'},NOW);self.assertEqual(auditor.report()['denied'],1)
    def test_excessive_access(self):
        auditor=AccessAuditor()
        for i in range(3):auditor.grant(f'p{i}','reviewer',{'review'},{'field'},NOW-dt.timedelta(days=1),NOW+dt.timedelta(days=1));auditor.authorize(f'p{i}','reviewer','review',{'field'},NOW)
        self.assertTrue(auditor.excessive_access('reviewer',NOW-dt.timedelta(hours=1),2))
