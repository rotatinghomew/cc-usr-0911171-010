from __future__ import annotations
import decimal
import statistics
from collections import defaultdict,deque
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence

class AnomalyError(ValueError):pass

@dataclass(frozen=True)
class Observation:
    series:str
    period:str
    value:decimal.Decimal
    dimensions:Mapping[str,Any]

@dataclass(frozen=True)
class Anomaly:
    series:str
    period:str
    value:decimal.Decimal
    expected:decimal.Decimal
    deviation:decimal.Decimal
    severity:str
    reasons:tuple[str,...]

class AnomalyMonitor:
    def __init__(self,minimum_history:int=4,warning_z:decimal.Decimal=decimal.Decimal('2'),critical_z:decimal.Decimal=decimal.Decimal('3')):
        if minimum_history<2 or warning_z<=0 or critical_z<warning_z:raise AnomalyError('invalid monitor configuration')
        self.minimum_history=minimum_history;self.warning_z=warning_z;self.critical_z=critical_z
    def normalize(self,rows:Iterable[Mapping[str,Any]]) -> tuple[Observation,...]:
        result=[]
        for row in rows:
            series=str(row.get('series','')).strip();period=str(row.get('period','')).strip()
            if not series or not period:raise AnomalyError('series and period required')
            try:value=decimal.Decimal(str(row.get('value')))
            except decimal.InvalidOperation as exc:raise AnomalyError('numeric value required') from exc
            result.append(Observation(series,period,value,dict(row.get('dimensions',{}))))
        return tuple(sorted(result,key=lambda item:(item.series,item.period)))
    def rolling(self,observations:Sequence[Observation],window:int=7) -> dict[tuple[str,str],dict[str,decimal.Decimal|None]]:
        if window<2:raise AnomalyError('window must be at least two')
        histories=defaultdict(lambda:deque(maxlen=window));result={}
        for observation in sorted(observations,key=lambda item:(item.series,item.period)):
            history=histories[observation.series];values=list(history)
            mean=sum(values,decimal.Decimal('0'))/len(values) if values else None
            deviation=None
            if len(values)>=2:
                variance=sum((value-mean)**2 for value in values)/decimal.Decimal(len(values));deviation=variance.sqrt()
            result[(observation.series,observation.period)]={'mean':mean,'stddev':deviation,'history':decimal.Decimal(len(values))};history.append(observation.value)
        return result
    def detect(self,rows:Iterable[Mapping[str,Any]],window:int=7,relative_limit:decimal.Decimal=decimal.Decimal('0.5')) -> tuple[Anomaly,...]:
        observations=self.normalize(rows);rolling=self.rolling(observations,window);result=[]
        for observation in observations:
            baseline=rolling[(observation.series,observation.period)];history=int(baseline['history']);expected=baseline['mean'];stddev=baseline['stddev']
            if history<self.minimum_history or expected is None:continue
            reasons=[];z=decimal.Decimal('0')
            if stddev and stddev>0:z=abs(observation.value-expected)/stddev
            relative=abs(observation.value-expected)/abs(expected) if expected else decimal.Decimal('0')
            if z>=self.warning_z:reasons.append('statistical_deviation')
            if relative>=relative_limit:reasons.append('relative_change')
            if not reasons:continue
            severity='critical' if z>=self.critical_z or relative>=relative_limit*2 else 'warning'
            result.append(Anomaly(observation.series,observation.period,observation.value,expected,observation.value-expected,severity,tuple(reasons)))
        return tuple(result)
    def compare_dimensions(self,rows:Iterable[Mapping[str,Any]],dimension:str) -> dict[str,dict[str,decimal.Decimal]]:
        observations=self.normalize(rows);groups=defaultdict(list)
        for observation in observations:groups[str(observation.dimensions.get(dimension,'unknown'))].append(observation.value)
        result={}
        for key,values in sorted(groups.items()):result[key]={'count':decimal.Decimal(len(values)),'mean':sum(values,decimal.Decimal('0'))/len(values),'minimum':min(values),'maximum':max(values)}
        return result
    def incident_summary(self,anomalies:Sequence[Anomaly]) -> dict[str,Any]:
        by_series=defaultdict(list)
        for anomaly in anomalies:by_series[anomaly.series].append(anomaly)
        return {'anomalies':len(anomalies),'critical':sum(item.severity=='critical' for item in anomalies),'warning':sum(item.severity=='warning' for item in anomalies),'series':{key:{'count':len(values),'periods':[item.period for item in values],'maximum_deviation':str(max(abs(item.deviation) for item in values))} for key,values in sorted(by_series.items())}}
