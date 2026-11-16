from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence

class ClockError(ValueError):pass

@dataclass(frozen=True)
class WorkPeriod:
    weekday:int
    start:dt.time
    end:dt.time
    def __post_init__(self):
        if self.weekday<0 or self.weekday>6:raise ClockError('weekday outside range')
        if self.end<=self.start:raise ClockError('work period end must follow start')

@dataclass(frozen=True)
class Pause:
    start:dt.datetime
    end:dt.datetime
    reason:str
    def __post_init__(self):
        if self.end<=self.start:raise ClockError('pause end must follow start')

@dataclass(frozen=True)
class Deadline:
    case_id:str
    started_at:dt.datetime
    due_at:dt.datetime
    target_seconds:int
    pauses:tuple[Pause,...]
    calendar_name:str

@dataclass(frozen=True)
class DeadlineStatus:
    case_id:str
    due_at:dt.datetime
    remaining_seconds:int
    overdue_seconds:int
    level:str
    paused:bool

class BusinessCalendar:
    def __init__(self,name:str,periods:Sequence[WorkPeriod],holidays:Iterable[dt.date]=(),timezone:dt.tzinfo=dt.timezone.utc):
        if not name or not periods:raise ClockError('calendar name and periods required')
        self.name=name;self.periods=tuple(sorted(periods,key=lambda item:(item.weekday,item.start)));self.holidays=frozenset(holidays);self.timezone=timezone
        self._by_weekday={weekday:tuple(period for period in self.periods if period.weekday==weekday) for weekday in range(7)}
    def local(self,moment:dt.datetime) -> dt.datetime:
        if moment.tzinfo is None:raise ClockError('timezone-aware datetime required')
        return moment.astimezone(self.timezone)
    def intervals(self,day:dt.date) -> tuple[tuple[dt.datetime,dt.datetime],...]:
        if day in self.holidays:return ()
        return tuple((dt.datetime.combine(day,period.start,self.timezone),dt.datetime.combine(day,period.end,self.timezone)) for period in self._by_weekday[day.weekday()])
    def working(self,moment:dt.datetime) -> bool:
        local=self.local(moment)
        return any(start<=local<end for start,end in self.intervals(local.date()))
    def next_open(self,moment:dt.datetime) -> dt.datetime:
        local=self.local(moment)
        if self.working(local):return local
        for offset in range(0,370):
            day=local.date()+dt.timedelta(days=offset)
            for start,end in self.intervals(day):
                if start>=local:return start
        raise ClockError('calendar has no opening within search horizon')
    def previous_close(self,moment:dt.datetime) -> dt.datetime:
        local=self.local(moment)
        for offset in range(0,370):
            day=local.date()-dt.timedelta(days=offset)
            closes=[end for start,end in self.intervals(day) if end<=local]
            if closes:return max(closes)
        raise ClockError('calendar has no close within search horizon')
    def add_working_seconds(self,start:dt.datetime,seconds:int) -> dt.datetime:
        if seconds<0:raise ClockError('seconds cannot be negative')
        cursor=self.next_open(start);remaining=seconds
        while remaining:
            intervals=self.intervals(cursor.date());current=None
            for left,right in intervals:
                if left<=cursor<right:current=(left,right);break
                if cursor<left:cursor=left;current=(left,right);break
            if current is None:cursor=self.next_open(dt.datetime.combine(cursor.date()+dt.timedelta(days=1),dt.time.min,self.timezone));continue
            available=int((current[1]-cursor).total_seconds())
            if remaining<=available:return cursor+dt.timedelta(seconds=remaining)
            remaining-=available;cursor=self.next_open(current[1]+dt.timedelta(microseconds=1))
        return cursor
    def working_seconds(self,start:dt.datetime,end:dt.datetime) -> int:
        left=self.local(start);right=self.local(end)
        if right<left:raise ClockError('end precedes start')
        seconds=0;day=left.date()
        while day<=right.date():
            for opening,closing in self.intervals(day):
                a=max(left,opening);b=min(right,closing)
                if b>a:seconds+=int((b-a).total_seconds())
            day+=dt.timedelta(days=1)
        return seconds
    def subtract_pauses(self,start:dt.datetime,end:dt.datetime,pauses:Sequence[Pause]) -> int:
        base=self.working_seconds(start,end);removed=0
        merged=[]
        for pause in sorted(pauses,key=lambda item:item.start):
            clipped=(max(start,pause.start),min(end,pause.end))
            if clipped[1]<=clipped[0]:continue
            if merged and clipped[0]<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],clipped[1]))
            else:merged.append(clipped)
        for left,right in merged:removed+=self.working_seconds(left,right)
        return max(0,base-removed)

class ServiceClock:
    def __init__(self,calendar:BusinessCalendar):self.calendar=calendar
    def deadline(self,case_id:str,started_at:dt.datetime,target_seconds:int,pauses:Sequence[Pause]=()) -> Deadline:
        if target_seconds<=0:raise ClockError('target seconds must be positive')
        due=self.calendar.add_working_seconds(started_at,target_seconds)
        for pause in pauses:
            extension=self.calendar.working_seconds(pause.start,pause.end)
            if extension:due=self.calendar.add_working_seconds(due,extension)
        return Deadline(case_id,started_at,due,target_seconds,tuple(pauses),self.calendar.name)
    def status(self,deadline:Deadline,now:dt.datetime,warning_seconds:int=7200,critical_seconds:int=0) -> DeadlineStatus:
        active_pause=any(pause.start<=now<pause.end for pause in deadline.pauses)
        if now<=deadline.due_at:
            remaining=self.calendar.working_seconds(now,deadline.due_at);overdue=0
            level='paused' if active_pause else ('warning' if remaining<=warning_seconds else 'on_track')
        else:
            remaining=0;overdue=self.calendar.working_seconds(deadline.due_at,now);level='critical' if overdue>critical_seconds else 'overdue'
        return DeadlineStatus(deadline.case_id,deadline.due_at,remaining,overdue,level,active_pause)
    def queue(self,deadlines:Sequence[Deadline],now:dt.datetime) -> tuple[DeadlineStatus,...]:
        statuses=[self.status(deadline,now) for deadline in deadlines]
        priority={'critical':0,'overdue':1,'warning':2,'paused':3,'on_track':4}
        return tuple(sorted(statuses,key=lambda item:(priority[item.level],item.due_at,item.case_id)))
    def compliance(self,completed:Sequence[tuple[Deadline,dt.datetime]]) -> dict[str,Any]:
        if not completed:return {'cases':0,'within_target':0,'rate':None,'average_overdue_seconds':0}
        within=0;overdue=[]
        for deadline,finished_at in completed:
            if finished_at<=deadline.due_at:within+=1
            else:overdue.append(self.calendar.working_seconds(deadline.due_at,finished_at))
        return {'cases':len(completed),'within_target':within,'rate':within/len(completed),'average_overdue_seconds':sum(overdue)/len(overdue) if overdue else 0}
