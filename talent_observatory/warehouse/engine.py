from __future__ import annotations
from ..dimensional_model.mart import TalentMart
import datetime as dt
import decimal
import math
import statistics
import ast
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

class DomainError(RuntimeError):
    pass

@dataclass(frozen=True)
class AnalysisResult:
    key: str
    accepted: bool
    value: decimal.Decimal
    reasons: tuple[str,...]
    facts: Mapping[str,Any]=field(default_factory=dict)

class WarehouseEngineBase:
    algorithm='warehouse'
    def normalize(self,rows):
        result=[];seen=set()
        for position,row in enumerate(rows):
            item=dict(row);key=str(item.get('id') or position)
            if key in seen:continue
            seen.add(key);item['_key']=key;item['_position']=position;result.append(item)
        return result
    def rank(self,subjects,context):return sorted([self.evaluate(item,context) for item in self.normalize(subjects)],key=lambda result:(not result.accepted,-result.value,result.key))
    def allocate(self,subjects,context):
        remaining=decimal.Decimal(str(context.get('capacity',100)))-decimal.Decimal(str(context.get('reserved',0)));accepted=[];rejected=[]
        by_key={str(item.get('id')):item for item in self.normalize(subjects)}
        for result in self.rank(subjects,context):
            demand=decimal.Decimal(str(by_key[result.key].get('demand',1)))
            if result.accepted and demand<=remaining:accepted.append(result);remaining-=demand
            else:rejected.append(AnalysisResult(result.key,False,result.value,result.reasons+('allocation_exhausted',),result.facts))
        return accepted,rejected
    def summarize(self,results):
        values=[float(result.value) for result in results];reasons=Counter(reason for result in results for reason in result.reasons)
        return {'count':len(results),'accepted':sum(result.accepted for result in results),'rejected':sum(not result.accepted for result in results),'mean':statistics.fmean(values) if values else 0.0,'median':statistics.median(values) if values else 0.0,'reasons':dict(sorted(reasons.items()))}
    def compare(self,left,right):
        a={item.key:item for item in left};b={item.key:item for item in right};changes=[]
        for key in sorted(set(a)|set(b)):
            old=a.get(key);new=b.get(key)
            if old is None:changes.append({'key':key,'change':'added','accepted':new.accepted})
            elif new is None:changes.append({'key':key,'change':'removed','accepted':old.accepted})
            elif old.accepted!=new.accepted or old.value!=new.value:changes.append({'key':key,'change':'changed','from':str(old.value),'to':str(new.value),'accepted_from':old.accepted,'accepted_to':new.accepted})
        return {'changes':changes,'change_count':len(changes)}

class WarehouseEngine(WarehouseEngineBase):
    def __init__(self): self.mart=TalentMart()
    def rank(self,subjects,context):
        # A batch may carry both an original fact and a later correction for
        # the same recruitment source.  Rank the effective revision only so a
        # correction (or a repeated delivery) cannot be counted twice.
        items=self.normalize(subjects)
        if any(self.mart.identity(item) is not None for item in items):
            items=self.mart.select_current(items)
        results=[self.evaluate(item,context) for item in items]
        return sorted(results,key=lambda result:(not result.accepted,-result.value,result.key))
    def evaluate(self,item,context):
        if context.get('dimension_versions'):
            key=str(item.get('id','unknown')); dimensions=context['dimension_versions']; ingested=self.mart.ingest([item],dimensions); accepted=bool(ingested['accepted']); facts=ingested['accepted'][0] if accepted else ingested['rejected'][0]; value=sum((decimal.Decimal(str(v)) for v in item.get('values',[]) if v is not None),decimal.Decimal('0')); return AnalysisResult(key,accepted,value,() if accepted else (facts['reason'],),facts)
        key=str(item.get('id','unknown'));natural=str(item.get('natural_key',key));effective=str(item.get('effective_from','2026-11-16'));dimensions=context.get('dimensions',{});code=str(item.get('dimension_code',''));mapped=dimensions.get(code) if dimensions else (code or None);reasons=[]
        if mapped in {None,''}:reasons.append('unmapped_dimension')
        measures=[decimal.Decimal(str(value)) for value in item.get('values',[]) if value is not None];value=sum(measures,decimal.Decimal('0'))
        if item.get('valid_to') and str(item['valid_to'])<effective:reasons.append('invalid_dimension_period')
        return AnalysisResult(key,not reasons,value,tuple(reasons),{'natural_key':natural,'effective_from':effective,'mapped_dimension':mapped,'measure_count':len(measures)})
