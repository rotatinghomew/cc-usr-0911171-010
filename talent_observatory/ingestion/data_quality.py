from __future__ import annotations
import datetime as dt
import decimal
from collections import Counter,defaultdict
from dataclasses import dataclass
from typing import Any,Callable,Iterable,Mapping,Sequence

@dataclass(frozen=True)
class QualityIssue:
    rule:str
    row_key:str
    field:str|None
    severity:str
    detail:str

@dataclass(frozen=True)
class QualityReport:
    checked:int
    passed:int
    issues:tuple[QualityIssue,...]
    by_rule:Mapping[str,int]
    by_severity:Mapping[str,int]
    score:decimal.Decimal

class Rule:
    name='rule';severity='error'
    def evaluate(self,row:Mapping[str,Any],row_key:str,context:Mapping[str,Any]) -> Iterable[QualityIssue]:return ()

class RequiredFields(Rule):
    name='required_fields'
    def __init__(self,*fields:str,severity:str='error'):self.fields=fields;self.severity=severity
    def evaluate(self,row,row_key,context):
        for field in self.fields:
            if field not in row or row[field] in {None,'',()}:yield QualityIssue(self.name,row_key,field,self.severity,'required value missing')

class ValueRange(Rule):
    name='value_range'
    def __init__(self,field:str,minimum:Any=None,maximum:Any=None,severity:str='error'):self.field=field;self.minimum=minimum;self.maximum=maximum;self.severity=severity
    def evaluate(self,row,row_key,context):
        value=row.get(self.field)
        if value is None:return
        if self.minimum is not None and value<self.minimum:yield QualityIssue(self.name,row_key,self.field,self.severity,f'{value} below {self.minimum}')
        if self.maximum is not None and value>self.maximum:yield QualityIssue(self.name,row_key,self.field,self.severity,f'{value} above {self.maximum}')

class AllowedValues(Rule):
    name='allowed_values'
    def __init__(self,field:str,values:Iterable[Any],severity:str='error'):self.field=field;self.values=frozenset(values);self.severity=severity
    def evaluate(self,row,row_key,context):
        if row.get(self.field) not in self.values:yield QualityIssue(self.name,row_key,self.field,self.severity,'value is not allowed')

class UniqueKey(Rule):
    name='unique_key'
    def __init__(self,*fields:str,severity:str='error'):self.fields=fields;self.severity=severity
    def evaluate(self,row,row_key,context):
        key=tuple(row.get(field) for field in self.fields);counts=context.get('unique_counts',{}).get(self.fields,{})
        if counts.get(key,0)>1:yield QualityIssue(self.name,row_key,','.join(self.fields),self.severity,'key is duplicated')

class ForeignKey(Rule):
    name='foreign_key'
    def __init__(self,field:str,reference:str,severity:str='error'):self.field=field;self.reference=reference;self.severity=severity
    def evaluate(self,row,row_key,context):
        if row.get(self.field) not in context.get('references',{}).get(self.reference,set()):yield QualityIssue(self.name,row_key,self.field,self.severity,f'missing reference {self.reference}')

class Freshness(Rule):
    name='freshness'
    def __init__(self,field:str,maximum_age:dt.timedelta,severity:str='warning'):self.field=field;self.maximum_age=maximum_age;self.severity=severity
    def evaluate(self,row,row_key,context):
        value=row.get(self.field);now=context.get('now')
        if value is None or now is None:return
        moment=value if isinstance(value,dt.datetime) else dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if now-moment>self.maximum_age:yield QualityIssue(self.name,row_key,self.field,self.severity,'value is stale')

class Consistency(Rule):
    name='consistency'
    def __init__(self,name:str,predicate:Callable[[Mapping[str,Any]],bool],detail:str,severity:str='error'):self.name=name;self.predicate=predicate;self.detail=detail;self.severity=severity
    def evaluate(self,row,row_key,context):
        if not self.predicate(row):yield QualityIssue(self.name,row_key,None,self.severity,self.detail)

class QualitySuite:
    def __init__(self,rules:Sequence[Rule],key_field:str='id'):self.rules=tuple(rules);self.key_field=key_field
    def context(self,rows:Sequence[Mapping[str,Any]],references:Mapping[str,Iterable[Any]]|None=None,now:dt.datetime|None=None) -> dict[str,Any]:
        unique_specs={rule.fields for rule in self.rules if isinstance(rule,UniqueKey)};unique_counts={}
        for fields in unique_specs:unique_counts[fields]=Counter(tuple(row.get(field) for field in fields) for row in rows)
        return {'unique_counts':unique_counts,'references':{key:set(values) for key,values in (references or {}).items()},'now':now or dt.datetime.now(dt.timezone.utc)}
    def run(self,rows:Sequence[Mapping[str,Any]],references:Mapping[str,Iterable[Any]]|None=None,now:dt.datetime|None=None) -> QualityReport:
        context=self.context(rows,references,now);issues=[];failed_positions=set()
        for position,row in enumerate(rows,1):
            row_key=str(row.get(self.key_field) or position)
            for rule in self.rules:
                found=list(rule.evaluate(row,row_key,context));issues.extend(found)
                if any(issue.severity=='error' for issue in found):failed_positions.add(position)
        checked=len(rows);passed=checked-len(failed_positions);score=decimal.Decimal(passed)/decimal.Decimal(checked) if checked else decimal.Decimal('1')
        return QualityReport(checked,passed,tuple(issues),dict(Counter(issue.rule for issue in issues)),dict(Counter(issue.severity for issue in issues)),score.quantize(decimal.Decimal('0.0001')))
    def partition(self,rows:Sequence[Mapping[str,Any]],**kwargs):
        report=self.run(rows,**kwargs);context=self.context(rows,kwargs.get('references'),kwargs.get('now'));valid=[];invalid=[]
        for position,row in enumerate(rows,1):
            row_key=str(row.get(self.key_field) or position);has_error=False
            for rule in self.rules:
                if any(issue.severity=='error' for issue in rule.evaluate(row,row_key,context)):has_error=True;break
            (invalid if has_error else valid).append(row)
        return valid,invalid,report
