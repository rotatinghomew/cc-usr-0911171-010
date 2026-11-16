from __future__ import annotations
import decimal
from collections import defaultdict
from dataclasses import dataclass
from typing import Any,Callable,Iterable,Mapping,Sequence

class ReconciliationError(RuntimeError):pass

@dataclass(frozen=True)
class Match:
    left_key:str
    right_key:str
    differences:Mapping[str,tuple[Any,Any]]
    tolerance_breaches:tuple[str,...]

@dataclass(frozen=True)
class ReconciliationResult:
    matches:tuple[Match,...]
    left_only:tuple[Mapping[str,Any],...]
    right_only:tuple[Mapping[str,Any],...]
    ambiguous:tuple[str,...]
    totals:Mapping[str,Any]
    balanced:bool

class Reconciler:
    def __init__(self,left_keys:Sequence[str],right_keys:Sequence[str]|None=None):
        self.left_keys=tuple(left_keys);self.right_keys=tuple(right_keys or left_keys)
        if not self.left_keys or len(self.left_keys)!=len(self.right_keys):raise ReconciliationError('matching keys required')
    def key(self,row:Mapping[str,Any],fields:Sequence[str]) -> str:
        values=[str(row.get(field,'')).strip() for field in fields]
        if any(not value for value in values):raise ReconciliationError('missing reconciliation key')
        return '|'.join(values)
    def index(self,rows:Iterable[Mapping[str,Any]],fields:Sequence[str]) -> tuple[dict[str,Mapping[str,Any]],tuple[str,...]]:
        result={};ambiguous=[]
        for row in rows:
            key=self.key(row,fields)
            if key in result:ambiguous.append(key)
            else:result[key]=dict(row)
        return result,tuple(sorted(set(ambiguous)))
    def compare_fields(self,left:Mapping[str,Any],right:Mapping[str,Any],fields:Sequence[str],tolerances:Mapping[str,decimal.Decimal]) -> tuple[dict[str,tuple[Any,Any]],tuple[str,...]]:
        differences={};breaches=[]
        for field in fields:
            a=left.get(field);b=right.get(field)
            if a==b:continue
            differences[field]=(a,b)
            if field in tolerances:
                try:delta=abs(decimal.Decimal(str(a or 0))-decimal.Decimal(str(b or 0)))
                except decimal.InvalidOperation:breaches.append(field)
                else:
                    if delta>tolerances[field]:breaches.append(field)
            else:breaches.append(field)
        return differences,tuple(breaches)
    def reconcile(self,left_rows:Iterable[Mapping[str,Any]],right_rows:Iterable[Mapping[str,Any]],compare_fields:Sequence[str],tolerances:Mapping[str,decimal.Decimal]|None=None,total_fields:Sequence[str]=()) -> ReconciliationResult:
        left,left_ambiguous=self.index(left_rows,self.left_keys);right,right_ambiguous=self.index(right_rows,self.right_keys);ambiguous=tuple(sorted(set(left_ambiguous)|set(right_ambiguous)))
        matches=[]
        for key in sorted(set(left)&set(right)):
            differences,breaches=self.compare_fields(left[key],right[key],compare_fields,tolerances or {});matches.append(Match(key,key,differences,breaches))
        left_only=tuple(left[key] for key in sorted(set(left)-set(right)));right_only=tuple(right[key] for key in sorted(set(right)-set(left)))
        totals={}
        for field in total_fields:
            left_total=sum((decimal.Decimal(str(row.get(field,0))) for row in left.values()),decimal.Decimal('0'));right_total=sum((decimal.Decimal(str(row.get(field,0))) for row in right.values()),decimal.Decimal('0'));totals[field]={'left':left_total,'right':right_total,'difference':left_total-right_total}
        balanced=not ambiguous and not left_only and not right_only and all(not match.tolerance_breaches for match in matches) and all(item['difference']==0 for item in totals.values())
        return ReconciliationResult(tuple(matches),left_only,right_only,ambiguous,totals,balanced)
    def repair_plan(self,result:ReconciliationResult,authority:str='left') -> tuple[Mapping[str,Any],...]:
        if authority not in {'left','right'}:raise ReconciliationError('authority must be left or right')
        actions=[]
        for row in result.left_only:actions.append({'action':'insert_right' if authority=='left' else 'review_left_only','row':dict(row)})
        for row in result.right_only:actions.append({'action':'insert_left' if authority=='right' else 'review_right_only','row':dict(row)})
        for match in result.matches:
            if match.tolerance_breaches:actions.append({'action':'update_right' if authority=='left' else 'update_left','key':match.left_key,'fields':match.tolerance_breaches})
        for key in result.ambiguous:actions.append({'action':'resolve_duplicate','key':key})
        return tuple(actions)
    def conservation(self,rows:Iterable[Mapping[str,Any]],debit_field:str,credit_field:str,group_fields:Sequence[str]=()) -> dict[str,decimal.Decimal]:
        balances=defaultdict(lambda:decimal.Decimal('0'))
        for row in rows:
            key='|'.join(str(row.get(field,'')) for field in group_fields) if group_fields else 'all';balances[key]+=decimal.Decimal(str(row.get(debit_field,0)))-decimal.Decimal(str(row.get(credit_field,0)))
        return dict(sorted(balances.items()))
