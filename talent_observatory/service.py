from __future__ import annotations
import datetime as dt
import uuid
from typing import Any, Mapping, Sequence
from .contracts import Event, fingerprint
from .storage import Database
from .warehouse.engine import WarehouseEngine

class ApplicationService:
    def __init__(self,database:Database):
        self.database=database; self.engine=WarehouseEngine()

    def process(self,payload:Mapping[str,Any],context:Mapping[str,Any],request_key:str) -> dict[str,Any]:
        digest=fingerprint({'payload':payload,'context':context})
        recalled=self.database.recalled('process',request_key,digest)
        if recalled is not None:return recalled
        result=self.engine.evaluate(payload,context)
        identifier=result.key
        response={'id':identifier,'accepted':result.accepted,'value':str(result.value),'reasons':list(result.reasons),'facts':dict(result.facts)}
        with self.database.transaction() as connection:
            record={'industry_id':identifier,'owner_id':str(payload.get('owner_id','owner-default')),'category':'warehouse','status':'active' if result.accepted else 'cancelled','effective_from':str(payload.get('effective_from',dt.date.today())),'effective_to':payload.get('effective_to'),'quantity':int(payload.get('demand',0)),'amount':str(payload.get('amount','0')),'attributes':response}
            version=self.database.put_record(connection,'industry',record)
            event=Event(str(uuid.uuid4()),'industry',identifier,'processed',dt.datetime.now(dt.timezone.utc),response,version)
            self.database.append_event(connection,event)
            self.database.enqueue(connection,'result:'+identifier,'warehouse'+'.result',identifier,response)
            self.database.remember(connection,'process',request_key,digest,response)
        return response

    def batch(self,subjects:Sequence[Mapping[str,Any]],context:Mapping[str,Any]) -> dict[str,Any]:
        results=self.engine.rank(subjects,context)
        return {'summary':self.engine.summarize(results),'results':[{'id':r.key,'accepted':r.accepted,'value':str(r.value),'reasons':list(r.reasons)} for r in results]}
