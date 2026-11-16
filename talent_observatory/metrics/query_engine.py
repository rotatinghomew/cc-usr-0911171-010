from __future__ import annotations
import datetime as dt
import decimal
import math
import statistics
from collections import Counter,defaultdict
from dataclasses import dataclass
from typing import Any,Callable,Iterable,Mapping,Sequence

class QueryError(ValueError): pass

@dataclass(frozen=True)
class Page:
    items:tuple[Mapping[str,Any],...]
    total:int
    offset:int
    limit:int
    next_offset:int|None

class QueryEngine:
    OPS={'eq','ne','lt','lte','gt','gte','in','contains','prefix','exists','between'}
    def value(self,row:Mapping[str,Any],path:str) -> Any:
        current:Any=row
        for part in path.split('.'):
            if not isinstance(current,Mapping) or part not in current: return None
            current=current[part]
        return current
    def compare(self,actual:Any,operator:str,expected:Any) -> bool:
        if operator not in self.OPS: raise QueryError('unsupported operator')
        if operator=='exists': return (actual is not None)==bool(expected)
        if operator=='eq': return actual==expected
        if operator=='ne': return actual!=expected
        if operator=='in': return actual in expected
        if operator=='contains': return expected in actual if actual is not None else False
        if operator=='prefix': return str(actual).startswith(str(expected)) if actual is not None else False
        if actual is None: return False
        if operator=='lt': return actual<expected
        if operator=='lte': return actual<=expected
        if operator=='gt': return actual>expected
        if operator=='gte': return actual>=expected
        if operator=='between': return expected[0]<=actual<=expected[1]
        return False
    def filter(self,rows:Iterable[Mapping[str,Any]],predicates:Sequence[Mapping[str,Any]],mode:str='all') -> list[Mapping[str,Any]]:
        if mode not in {'all','any'}: raise QueryError('mode must be all or any')
        result=[]
        for row in rows:
            checks=[self.compare(self.value(row,p['field']),p.get('op','eq'),p.get('value')) for p in predicates]
            if (all(checks) if mode=='all' else any(checks)): result.append(row)
        return result
    def sort(self,rows:Iterable[Mapping[str,Any]],fields:Sequence[tuple[str,bool]]) -> list[Mapping[str,Any]]:
        result=list(rows)
        for field,descending in reversed(fields): result.sort(key=lambda row:(self.value(row,field) is None,self.value(row,field)),reverse=descending)
        return result
    def page(self,rows:Sequence[Mapping[str,Any]],offset:int=0,limit:int=50) -> Page:
        if offset<0 or limit<1 or limit>1000: raise QueryError('invalid page')
        items=tuple(rows[offset:offset+limit]); next_offset=offset+limit if offset+limit<len(rows) else None
        return Page(items,len(rows),offset,limit,next_offset)
    def group(self,rows:Iterable[Mapping[str,Any]],fields:Sequence[str]) -> dict[tuple[Any,...],list[Mapping[str,Any]]]:
        groups=defaultdict(list)
        for row in rows: groups[tuple(self.value(row,field) for field in fields)].append(row)
        return dict(groups)
    def aggregate(self,rows:Iterable[Mapping[str,Any]],group_fields:Sequence[str],measures:Sequence[Mapping[str,Any]]) -> list[dict[str,Any]]:
        output=[]
        for key,items in sorted(self.group(rows,group_fields).items(),key=lambda item:str(item[0])):
            result={field:value for field,value in zip(group_fields,key)}
            for measure in measures:
                name=measure['name']; operation=measure['op']; values=[self.value(item,measure.get('field','')) for item in items]; numeric=[decimal.Decimal(str(value)) for value in values if value is not None]
                if operation=='count': result[name]=len(items)
                elif operation=='distinct': result[name]=len(set(values))
                elif operation=='sum': result[name]=sum(numeric,decimal.Decimal('0'))
                elif operation=='mean': result[name]=sum(numeric,decimal.Decimal('0'))/len(numeric) if numeric else None
                elif operation=='min': result[name]=min(values) if values else None
                elif operation=='max': result[name]=max(values) if values else None
                elif operation=='median': result[name]=statistics.median(numeric) if numeric else None
                else: raise QueryError('unsupported aggregate')
            output.append(result)
        return output
    def histogram(self,rows:Iterable[Mapping[str,Any]],field:str,bounds:Sequence[decimal.Decimal]) -> list[dict[str,Any]]:
        ordered=sorted(bounds); counts=[0]*(len(ordered)+1)
        for row in rows:
            value=self.value(row,field)
            if value is None: continue
            numeric=decimal.Decimal(str(value)); index=0
            while index<len(ordered) and numeric>ordered[index]: index+=1
            counts[index]+=1
        result=[]
        for index,count in enumerate(counts): result.append({'lower':None if index==0 else ordered[index-1],'upper':None if index==len(ordered) else ordered[index],'count':count})
        return result
    def time_buckets(self,rows:Iterable[Mapping[str,Any]],field:str,unit:str='day') -> dict[str,int]:
        counts=Counter()
        for row in rows:
            value=self.value(row,field)
            if value is None: continue
            moment=value if isinstance(value,(dt.date,dt.datetime)) else dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
            if unit=='day': key=moment.strftime('%Y-%m-%d')
            elif unit=='week': key=f'{moment.isocalendar().year}-W{moment.isocalendar().week:02d}'
            elif unit=='month': key=moment.strftime('%Y-%m')
            else: raise QueryError('unsupported time unit')
            counts[key]+=1
        return dict(sorted(counts.items()))
