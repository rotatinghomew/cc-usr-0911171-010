from __future__ import annotations
import decimal
import statistics
from collections import Counter,defaultdict
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence

class MetricError(ValueError):pass

@dataclass(frozen=True)
class MetricDefinition:
    name:str
    operation:str
    field:str|None=None
    numerator:str|None=None
    denominator:str|None=None
    dimensions:tuple[str,...]=()
    filters:tuple[tuple[str,str,Any],...]=()
    missing:str='exclude'
    precision:int=4

class MetricCatalog:
    OPERATIONS={'count','distinct','sum','mean','median','min','max','ratio'}
    def __init__(self):self._definitions:dict[str,MetricDefinition]={}
    def register(self,definition:MetricDefinition) -> None:
        if definition.name in self._definitions:raise MetricError('metric already exists')
        if definition.operation not in self.OPERATIONS:raise MetricError('unsupported operation')
        if definition.operation=='ratio' and (not definition.numerator or not definition.denominator):raise MetricError('ratio requires numerator and denominator')
        if definition.missing not in {'exclude','zero','error'}:raise MetricError('unsupported missing policy')
        self._definitions[definition.name]=definition
    def definition(self,name:str) -> MetricDefinition:
        try:return self._definitions[name]
        except KeyError as exc:raise MetricError('unknown metric') from exc
    def value(self,row:Mapping[str,Any],path:str|None) -> Any:
        if path is None:return None
        current:Any=row
        for part in path.split('.'):
            if not isinstance(current,Mapping) or part not in current:return None
            current=current[part]
        return current
    def compare(self,actual:Any,operator:str,expected:Any) -> bool:
        if operator=='eq':return actual==expected
        if operator=='ne':return actual!=expected
        if operator=='in':return actual in expected
        if actual is None:return False
        if operator=='gte':return actual>=expected
        if operator=='gt':return actual>expected
        if operator=='lte':return actual<=expected
        if operator=='lt':return actual<expected
        raise MetricError('unsupported filter operator')
    def select(self,definition:MetricDefinition,rows:Iterable[Mapping[str,Any]]) -> list[Mapping[str,Any]]:return [row for row in rows if all(self.compare(self.value(row,field),op,expected) for field,op,expected in definition.filters)]
    def numeric(self,definition:MetricDefinition,rows:Sequence[Mapping[str,Any]]) -> list[decimal.Decimal]:
        values=[]
        for row in rows:
            value=self.value(row,definition.field)
            if value is None:
                if definition.missing=='error':raise MetricError('missing value')
                if definition.missing=='zero':values.append(decimal.Decimal('0'))
                continue
            values.append(decimal.Decimal(str(value)))
        return values
    def scalar(self,definition:MetricDefinition,rows:Sequence[Mapping[str,Any]],cache:Mapping[str,Any]|None=None) -> Any:
        selected=self.select(definition,rows);operation=definition.operation
        if operation=='count':return len(selected)
        if operation=='distinct':return len({self.value(row,definition.field) for row in selected})
        if operation=='ratio':
            values=cache or {};numerator=decimal.Decimal(str(values.get(definition.numerator,0)));denominator=decimal.Decimal(str(values.get(definition.denominator,0)))
            return None if denominator==0 else (numerator/denominator).quantize(decimal.Decimal(1).scaleb(-definition.precision))
        values=self.numeric(definition,selected)
        if not values:return None
        if operation=='sum':result=sum(values,decimal.Decimal('0'))
        elif operation=='mean':result=sum(values,decimal.Decimal('0'))/len(values)
        elif operation=='median':result=statistics.median(values)
        elif operation=='min':result=min(values)
        elif operation=='max':result=max(values)
        else:raise MetricError('unsupported operation')
        return result.quantize(decimal.Decimal(1).scaleb(-definition.precision))
    def compute(self,names:Sequence[str],rows:Sequence[Mapping[str,Any]]) -> dict[str,Any]:
        result={}
        non_ratios=[self.definition(name) for name in names if self.definition(name).operation!='ratio'];ratios=[self.definition(name) for name in names if self.definition(name).operation=='ratio']
        for definition in non_ratios:result[definition.name]=self.scalar(definition,rows,result)
        for definition in ratios:result[definition.name]=self.scalar(definition,rows,result)
        return result
    def grouped(self,name:str,rows:Sequence[Mapping[str,Any]]) -> list[dict[str,Any]]:
        definition=self.definition(name);groups=defaultdict(list)
        for row in rows:groups[tuple(self.value(row,dimension) for dimension in definition.dimensions)].append(row)
        result=[]
        for key,items in sorted(groups.items(),key=lambda item:str(item[0])):result.append({**{dimension:value for dimension,value in zip(definition.dimensions,key)},definition.name:self.scalar(definition,items)})
        return result
    def funnel(self,rows:Sequence[Mapping[str,Any]],entity_field:str,stage_field:str,ordered_stages:Sequence[str]) -> list[dict[str,Any]]:
        reached=defaultdict(set)
        for row in rows:
            entity=self.value(row,entity_field);stage=self.value(row,stage_field)
            if stage in ordered_stages:reached[stage].add(entity)
        previous=None;result=[]
        for stage in ordered_stages:
            count=len(reached[stage]);conversion=None if previous in {None,0} else decimal.Decimal(count)/decimal.Decimal(previous);result.append({'stage':stage,'entities':count,'conversion_from_previous':conversion});previous=count
        return result
    def cohort(self,rows:Sequence[Mapping[str,Any]],cohort_field:str,period_field:str,entity_field:str) -> list[dict[str,Any]]:
        groups=defaultdict(set)
        for row in rows:groups[(self.value(row,cohort_field),self.value(row,period_field))].add(self.value(row,entity_field))
        return [{'cohort':key[0],'period':key[1],'entities':len(values)} for key,values in sorted(groups.items(),key=lambda item:str(item[0]))]
    def definitions(self) -> tuple[MetricDefinition,...]:return tuple(self._definitions[name] for name in sorted(self._definitions))
