from __future__ import annotations
import datetime as dt
from collections import defaultdict
from decimal import Decimal
class TalentMart:
 def resolve_dimension(self,code,day,versions):
  date=dt.date.fromisoformat(str(day));matches=[]
  for row in versions:
   if str(row['code'])!=str(code):continue
   start=dt.date.fromisoformat(str(row['valid_from']));end=dt.date.fromisoformat(str(row['valid_to'])) if row.get('valid_to') else None
   if start<=date and (end is None or date<=end):matches.append(row)
  if len(matches)!=1:raise ValueError('dimension_resolution_'+('missing' if not matches else 'ambiguous'))
  return str(matches[0]['surrogate_key'])
 def ingest(self,facts,dimensions):
  chosen={};rejected=[]
  for row in facts:
   key=(str(row['source']),str(row['source_key']))
   if key in chosen and str(row.get('received_at',''))>=str(chosen[key].get('received_at','')):continue
   try:
    enriched=dict(row);enriched['industry_key']=self.resolve_dimension(row['industry_code'],row['event_date'],dimensions['industry']);enriched['region_key']=self.resolve_dimension(row['region_code'],row['event_date'],dimensions['region']);chosen[key]=enriched
   except ValueError as exc:rejected.append({'source_key':row['source_key'],'reason':str(exc)})
  return {'accepted':sorted(chosen.values(),key=lambda row:(row['event_date'],row['source_key'])),'rejected':rejected}
 def aggregate(self,facts,grain):
  groups=defaultdict(lambda:{'openings':0,'seekers':0,'intents':0,'salary_sum':Decimal('0'),'salary_count':0})
  for row in facts:
   key=tuple(str(row[field]) for field in grain);group=groups[key];group['openings']+=int(row.get('openings',0));group['seekers']+=int(row.get('seekers',0));group['intents']+=int(row.get('intents',0))
   if row.get('salary') is not None:group['salary_sum']+=Decimal(str(row['salary']));group['salary_count']+=1
  result=[]
  for key,value in sorted(groups.items()):result.append({'key':key,'openings':value['openings'],'seekers':value['seekers'],'intents':value['intents'],'gap':value['openings']-value['seekers'],'average_salary':str(value['salary_sum']/value['salary_count']) if value['salary_count'] else None})
  return result
 def flow_matrix(self,facts):
  matrix=defaultdict(int)
  for row in facts:
   if row.get('origin_region') and row.get('target_region'):matrix[(str(row['origin_region']),str(row['target_region']))]+=int(row.get('people',1))
  return [{'origin':key[0],'target':key[1],'people':value} for key,value in sorted(matrix.items())]
 def recompute_delta(self,old,new):
  def index(rows):return {tuple(row['key']):row for row in rows}
  left,right=index(old),index(new);changes=[]
  for key in sorted(set(left)|set(right)):
   if left.get(key)!=right.get(key):changes.append({'key':key,'before':left.get(key),'after':right.get(key)})
  return changes
