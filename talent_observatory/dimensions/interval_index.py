from __future__ import annotations
import bisect
import datetime as dt
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence

class IntervalError(ValueError): pass

@dataclass(frozen=True,order=True)
class Interval:
    start:dt.datetime
    end:dt.datetime
    key:str
    resource:str
    payload:Mapping[str,Any]
    def __post_init__(self):
        if self.start.tzinfo is None or self.end.tzinfo is None: raise IntervalError('timezone-aware datetimes required')
        if self.end<=self.start: raise IntervalError('end must follow start')
        if not self.key or not self.resource: raise IntervalError('key and resource required')
    @property
    def duration(self): return self.end-self.start
    def overlaps(self,other:'Interval') -> bool: return self.resource==other.resource and self.start<other.end and other.start<self.end
    def intersection(self,other:'Interval') -> 'Interval|None':
        if not self.overlaps(other): return None
        return Interval(max(self.start,other.start),min(self.end,other.end),f'{self.key}&{other.key}',self.resource,{'left':self.key,'right':other.key})
    def contains(self,moment:dt.datetime) -> bool: return self.start<=moment<self.end

class IntervalIndex:
    def __init__(self): self._by_resource:dict[str,list[Interval]]={}; self._keys:dict[str,Interval]={}
    def add(self,interval:Interval,allow_overlap:bool=False) -> None:
        if interval.key in self._keys: raise IntervalError('duplicate interval key')
        values=self._by_resource.setdefault(interval.resource,[]); position=bisect.bisect_left(values,interval)
        neighbors=values[max(0,position-1):min(len(values),position+1)]
        if not allow_overlap and any(interval.overlaps(item) for item in neighbors): raise IntervalError('interval overlaps existing allocation')
        values.insert(position,interval); self._keys[interval.key]=interval
    def remove(self,key:str) -> Interval:
        try: interval=self._keys.pop(key)
        except KeyError as exc: raise IntervalError('unknown interval') from exc
        self._by_resource[interval.resource].remove(interval)
        if not self._by_resource[interval.resource]: del self._by_resource[interval.resource]
        return interval
    def replace(self,key:str,replacement:Interval,allow_overlap:bool=False) -> None:
        original=self.remove(key)
        try: self.add(replacement,allow_overlap)
        except BaseException:
            self.add(original,True); raise
    def get(self,key:str) -> Interval:
        try:return self._keys[key]
        except KeyError as exc: raise IntervalError('unknown interval') from exc
    def resource(self,resource:str) -> tuple[Interval,...]: return tuple(self._by_resource.get(resource,()))
    def conflicts(self,candidate:Interval,exclude_key:str|None=None) -> tuple[Interval,...]: return tuple(item for item in self._by_resource.get(candidate.resource,()) if item.key!=exclude_key and item.overlaps(candidate))
    def active(self,resource:str,moment:dt.datetime) -> tuple[Interval,...]: return tuple(item for item in self._by_resource.get(resource,()) if item.contains(moment))
    def within(self,resource:str,start:dt.datetime,end:dt.datetime) -> tuple[Interval,...]:
        probe=Interval(start,end,'probe',resource,{})
        return tuple(item for item in self._by_resource.get(resource,()) if item.overlaps(probe))
    def gaps(self,resource:str,start:dt.datetime,end:dt.datetime,minimum:dt.timedelta=dt.timedelta(0)) -> tuple[tuple[dt.datetime,dt.datetime],...]:
        if end<=start: raise IntervalError('invalid window')
        cursor=start; gaps=[]
        for item in self.within(resource,start,end):
            if item.start>cursor and item.start-cursor>=minimum:gaps.append((cursor,min(item.start,end)))
            cursor=max(cursor,item.end)
            if cursor>=end:break
        if cursor<end and end-cursor>=minimum:gaps.append((cursor,end))
        return tuple(gaps)
    def utilization(self,resource:str,start:dt.datetime,end:dt.datetime) -> float:
        window=(end-start).total_seconds()
        if window<=0:raise IntervalError('invalid window')
        occupied=0.0
        for item in self.within(resource,start,end): occupied+=(min(item.end,end)-max(item.start,start)).total_seconds()
        return min(1.0,occupied/window)
    def validate(self) -> tuple[str,...]:
        problems=[]
        for resource,values in self._by_resource.items():
            for index,item in enumerate(values):
                if self._keys.get(item.key)!=item:problems.append(f'key_index_mismatch:{item.key}')
                if index and values[index-1].end>item.start:problems.append(f'overlap:{resource}:{values[index-1].key}:{item.key}')
        if sum(len(values) for values in self._by_resource.values())!=len(self._keys):problems.append('cardinality_mismatch')
        return tuple(problems)
    def snapshot(self) -> tuple[dict[str,Any],...]:
        return tuple({'key':item.key,'resource':item.resource,'start':item.start.isoformat(),'end':item.end.isoformat(),'payload':dict(item.payload)} for resource in sorted(self._by_resource) for item in self._by_resource[resource])
    @classmethod
    def restore(cls,rows:Iterable[Mapping[str,Any]]) -> 'IntervalIndex':
        result=cls()
        for row in rows:result.add(Interval(dt.datetime.fromisoformat(str(row['start'])),dt.datetime.fromisoformat(str(row['end'])),str(row['key']),str(row['resource']),dict(row.get('payload',{}))))
        return result
