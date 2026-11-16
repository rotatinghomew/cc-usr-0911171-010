from __future__ import annotations
import csv
import io
import json
import statistics
from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping, Sequence
from .audit import AuditVerifier
from .storage import Database

class Reporter:
    def __init__(self,database:Database): self.database=database
    def overview(self) -> dict[str,Any]:
        counts=self.database.counts(); pending=self.database.pending_messages()
        return {'counts':counts,'total_records':sum(counts.values()),'pending_messages':len(pending),'topics':dict(Counter(item['topic'] for item in pending))}
    def owner_breakdown(self,kind:str) -> dict[str,Any]:
        groups=defaultdict(list)
        for record in self.database.list_records(kind): groups[record['owner_id']].append(record)
        result={}
        for owner,rows in sorted(groups.items()):
            result[owner]={'count':len(rows),'quantity':sum(int(row['quantity']) for row in rows),'amount':sum(float(row['amount']) for row in rows),'states':dict(Counter(row['status'] for row in rows))}
        return result
    def export_json(self) -> str:
        records=[]
        records.extend(self.database.list_records('industry'))
        records.extend(self.database.list_records('region'))
        records.extend(self.database.list_records('skill'))
        records.extend(self.database.list_records('job'))
        records.extend(self.database.list_records('seeker'))
        records.extend(self.database.list_records('training'))
        records.extend(self.database.list_records('intent'))
        records.extend(self.database.list_records('snapshot'))
        manifest=AuditVerifier().manifest(records)
        return json.dumps({'overview':self.overview(),'records':records,'manifest':manifest},ensure_ascii=False,sort_keys=True,indent=2,default=str)
    def export_csv(self,kind:str) -> str:
        rows=self.database.list_records(kind)
        output=io.StringIO(); fields=['kind',f'{kind}_id','owner_id','category','status','effective_from','effective_to','quantity','amount','version']
        writer=csv.DictWriter(output,fieldnames=fields,extrasaction='ignore'); writer.writeheader(); writer.writerows(rows); return output.getvalue()
    def quality(self,kind:str) -> dict[str,Any]:
        rows=self.database.list_records(kind); issues=[]
        for row in rows:
            if not row['owner_id']: issues.append({'id':row[f'{kind}_id'],'code':'missing_owner'})
            if row['effective_to'] and row['effective_to']<row['effective_from']: issues.append({'id':row[f'{kind}_id'],'code':'reversed_period'})
            if int(row['quantity'])<0: issues.append({'id':row[f'{kind}_id'],'code':'negative_quantity'})
        return {'kind':kind,'records':len(rows),'issues':issues,'valid':not issues}
