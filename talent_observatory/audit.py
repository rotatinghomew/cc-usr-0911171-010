from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

@dataclass(frozen=True)
class AuditProblem:
    code: str
    aggregate_id: str
    detail: str

class AuditVerifier:
    def event_chain(self, events: Sequence[Mapping[str,Any]]) -> list[AuditProblem]:
        problems=[]; expected=1; seen=set()
        for event in sorted(events,key=lambda item:int(item.get('sequence',0))):
            event_id=str(event.get('event_id',''))
            if event_id in seen: problems.append(AuditProblem('duplicate_event',event_id,'event id repeated'))
            seen.add(event_id)
            sequence=int(event.get('sequence',0))
            if sequence!=expected: problems.append(AuditProblem('sequence_gap',str(event.get('aggregate_id','')),f'expected {expected}, found {sequence}'))
            expected=sequence+1
        return problems

    def manifest(self, records: Iterable[Mapping[str,Any]]) -> dict[str,Any]:
        rows=[]
        for record in records:
            payload=json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
            rows.append({'key':str(record.get('id') or record.get('record_id') or record.get('application_id') or ''),'sha256':hashlib.sha256(payload.encode()).hexdigest()})
        rows.sort(key=lambda item:(item['key'],item['sha256']))
        digest=hashlib.sha256('\n'.join(item['sha256'] for item in rows).encode()).hexdigest()
        return {'count':len(rows),'items':rows,'sha256':digest}

    def verify_manifest(self, records: Iterable[Mapping[str,Any]], expected: Mapping[str,Any]) -> list[AuditProblem]:
        actual=self.manifest(records); problems=[]
        if actual['count']!=expected.get('count'): problems.append(AuditProblem('count_mismatch','manifest',f"{actual['count']} != {expected.get('count')}"))
        if actual['sha256']!=expected.get('sha256'): problems.append(AuditProblem('hash_mismatch','manifest','manifest digest differs'))
        return problems
