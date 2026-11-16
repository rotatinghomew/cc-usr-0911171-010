import datetime as dt
import unittest
from talent_observatory.ingestion.service_clock import BusinessCalendar,ClockError,Pause,ServiceClock,WorkPeriod

UTC=dt.timezone.utc
def moment(day,hour=9):return dt.datetime(2026,11,day,hour,tzinfo=UTC)

class ServiceClockTests(unittest.TestCase):
    def calendar(self):return BusinessCalendar('daily',[WorkPeriod(day,dt.time(9),dt.time(17)) for day in range(7)],holidays={dt.date(2026,11,18)},timezone=UTC)
    def test_working(self):self.assertTrue(self.calendar().working(moment(16,10)));self.assertFalse(self.calendar().working(moment(16,18)))
    def test_holiday_closed(self):self.assertFalse(self.calendar().working(moment(18,10)))
    def test_next_open_after_close(self):self.assertEqual(self.calendar().next_open(moment(16,18)),moment(17,9))
    def test_next_open_skips_holiday(self):self.assertEqual(self.calendar().next_open(moment(17,18)),moment(19,9))
    def test_add_within_day(self):self.assertEqual(self.calendar().add_working_seconds(moment(16,9),3600),moment(16,10))
    def test_add_across_days(self):self.assertEqual(self.calendar().add_working_seconds(moment(17,16),7200),moment(19,10))
    def test_working_seconds(self):self.assertEqual(self.calendar().working_seconds(moment(16,9),moment(17,10)),9*3600)
    def test_pause_subtraction(self):self.assertEqual(self.calendar().subtract_pauses(moment(16,9),moment(16,17),[Pause(moment(16,12),moment(16,13),'waiting')]),7*3600)
    def test_deadline_extension(self):
        clock=ServiceClock(self.calendar());deadline=clock.deadline('case-1',moment(16,9),8*3600,[Pause(moment(16,12),moment(16,14),'external')]);self.assertEqual(deadline.due_at,moment(17,11))
    def test_warning_status(self):
        clock=ServiceClock(self.calendar());deadline=clock.deadline('case-1',moment(16,9),8*3600);self.assertEqual(clock.status(deadline,moment(16,16),warning_seconds=7200).level,'warning')
    def test_overdue_status(self):
        clock=ServiceClock(self.calendar());deadline=clock.deadline('case-1',moment(16,9),3600);self.assertEqual(clock.status(deadline,moment(16,12)).level,'critical')
    def test_queue_priority(self):
        clock=ServiceClock(self.calendar());a=clock.deadline('a',moment(16,9),3600);b=clock.deadline('b',moment(16,9),8*3600);self.assertEqual(clock.queue([b,a],moment(16,12))[0].case_id,'a')
    def test_compliance(self):
        clock=ServiceClock(self.calendar());deadline=clock.deadline('a',moment(16,9),3600);self.assertEqual(clock.compliance([(deadline,moment(16,10))])['rate'],1.0)
    def test_invalid_period(self):
        with self.assertRaises(ClockError):WorkPeriod(0,dt.time(17),dt.time(9))
    def test_naive_datetime(self):
        with self.assertRaises(ClockError):self.calendar().working(dt.datetime(2026,11,16,10))
