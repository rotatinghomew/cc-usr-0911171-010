from __future__ import annotations
import datetime as dt
import decimal
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence
from ..storage import ConflictError,Database,NotFoundError

@dataclass(frozen=True)
class JobSummary:
    count:int
    active:int
    quantity:int
    amount:decimal.Decimal
    owners:int
    earliest:str|None
    latest:str|None

class JobRepository:
    kind='job'
    def __init__(self,database:Database): self.database=database
    def create(self,values:Mapping[str,Any]) -> int:
        record=self._normalize(values)
        with self.database.transaction() as connection: return self.database.put_record(connection,self.kind,record,expected_version=None)
    def update(self,identifier:str,values:Mapping[str,Any],expected_version:int) -> int:
        current=self.get(identifier); merged=current|dict(values); merged[f'{self.kind}_id']=identifier; merged.pop('kind',None); merged.pop('version',None)
        record=self._normalize(merged)
        with self.database.transaction() as connection: return self.database.put_record(connection,self.kind,record,expected_version=expected_version)
    def get(self,identifier:str) -> dict[str,Any]: return self.database.get_record(self.kind,identifier)
    def all(self,owner_id:str|None=None,status:str|None=None) -> list[dict[str,Any]]: return self.database.list_records(self.kind,owner_id=owner_id,status=status)
    def active_on(self,day:dt.date) -> list[dict[str,Any]]:
        result=[]
        for row in self.all(status='active'):
            start=dt.date.fromisoformat(row['effective_from']); end=dt.date.fromisoformat(row['effective_to']) if row['effective_to'] else None
            if start<=day and (end is None or day<=end): result.append(row)
        return result
    def overlaps(self,owner_id:str,start:dt.date,end:dt.date,exclude_id:str|None=None) -> list[dict[str,Any]]:
        result=[]
        for row in self.all(owner_id=owner_id):
            identifier=row[f'{self.kind}_id']
            if identifier==exclude_id or row['status'] in {'cancelled','completed'}: continue
            left=dt.date.fromisoformat(row['effective_from']); right=dt.date.fromisoformat(row['effective_to']) if row['effective_to'] else dt.date.max
            if start<=right and left<=end: result.append(row)
        return result
    def summary(self,rows:Sequence[Mapping[str,Any]]|None=None) -> JobSummary:
        values=list(rows) if rows is not None else self.all(); dates=[row['effective_from'] for row in values]
        return JobSummary(len(values),sum(row['status']=='active' for row in values),sum(int(row['quantity']) for row in values),sum((decimal.Decimal(str(row['amount'])) for row in values),decimal.Decimal('0')),len({row['owner_id'] for row in values}),min(dates) if dates else None,max(dates) if dates else None)
    def by_category(self) -> dict[str,JobSummary]:
        groups={}
        for row in self.all(): groups.setdefault(row['category'],[]).append(row)
        return {category:self.summary(rows) for category,rows in sorted(groups.items())}
    def replace_attributes(self,identifier:str,attributes:Mapping[str,Any],expected_version:int) -> int: return self.update(identifier,{'attributes':dict(attributes)},expected_version)
    def transition(self,identifier:str,target:str,expected_version:int) -> int:
        allowed={'draft':{'received','cancelled'},'received':{'validated','suspended','cancelled'},'validated':{'active','cancelled'},'active':{'suspended','completed','cancelled'},'suspended':{'active','cancelled'},'completed':set(),'cancelled':set()}
        current=self.get(identifier); source=current['status']
        if target not in allowed.get(source,set()): raise ConflictError(f'illegal transition {source}->{target}')
        return self.update(identifier,{'status':target},expected_version)
    def _normalize(self,values:Mapping[str,Any]) -> dict[str,Any]:
        identifier=str(values.get(f'{self.kind}_id','')).strip(); owner=str(values.get('owner_id','')).strip(); category=' '.join(str(values.get('category','default')).split())
        if len(identifier)<2 or len(owner)<2: raise ValueError('identifier and owner are required')
        start=values.get('effective_from') or dt.date.today(); start=start if isinstance(start,dt.date) else dt.date.fromisoformat(str(start))
        end=values.get('effective_to'); end=None if end in {None,''} else (end if isinstance(end,dt.date) else dt.date.fromisoformat(str(end)))
        if end is not None and end<start: raise ValueError('effective period reversed')
        quantity=int(values.get('quantity',0)); amount=decimal.Decimal(str(values.get('amount','0'))).quantize(decimal.Decimal('0.01'))
        if quantity<0 or amount<0: raise ValueError('quantity and amount cannot be negative')
        return {f'{self.kind}_id':identifier,'owner_id':owner,'category':category,'status':str(values.get('status','draft')),'effective_from':start,'effective_to':end,'quantity':quantity,'amount':amount,'attributes':dict(values.get('attributes',{}))}
