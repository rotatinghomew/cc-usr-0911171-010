from __future__ import annotations
import datetime as dt
import hashlib
import json
from dataclasses import dataclass,field
from typing import Any,Callable,Iterable,Mapping,Sequence

class RecoveryError(RuntimeError): pass

@dataclass(frozen=True)
class Checkpoint:
    operation_id:str
    stage:str
    sequence:int
    recorded_at:dt.datetime
    state:Mapping[str,Any]
    fingerprint:str

@dataclass(frozen=True)
class Attempt:
    operation_id:str
    attempt:int
    started_at:dt.datetime
    finished_at:dt.datetime
    succeeded:bool
    error:str|None

class RecoveryController:
    def __init__(self): self._checkpoints:dict[str,list[Checkpoint]]={}; self._attempts:dict[str,list[Attempt]]={}; self._compensations:dict[str,list[Mapping[str,Any]]]={}
    def fingerprint(self,state:Mapping[str,Any]) -> str: return hashlib.sha256(json.dumps(state,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
    def checkpoint(self,operation_id:str,stage:str,state:Mapping[str,Any],recorded_at:dt.datetime|None=None) -> Checkpoint:
        history=self._checkpoints.setdefault(operation_id,[]); digest=self.fingerprint(state)
        if history and history[-1].stage==stage and history[-1].fingerprint==digest: return history[-1]
        item=Checkpoint(operation_id,stage,len(history)+1,recorded_at or dt.datetime.now(dt.timezone.utc),dict(state),digest); history.append(item); return item
    def latest(self,operation_id:str) -> Checkpoint|None:
        history=self._checkpoints.get(operation_id,[]); return history[-1] if history else None
    def history(self,operation_id:str) -> tuple[Checkpoint,...]: return tuple(self._checkpoints.get(operation_id,()))
    def resume_state(self,operation_id:str,required_stage:str|None=None) -> Mapping[str,Any]:
        history=self._checkpoints.get(operation_id,[])
        if not history: raise RecoveryError('checkpoint not found')
        if required_stage is None: return dict(history[-1].state)
        for checkpoint in reversed(history):
            if checkpoint.stage==required_stage: return dict(checkpoint.state)
        raise RecoveryError('required stage not found')
    def record_attempt(self,operation_id:str,started_at:dt.datetime,finished_at:dt.datetime,succeeded:bool,error:str|None=None) -> Attempt:
        if finished_at<started_at: raise RecoveryError('attempt finishes before start')
        attempts=self._attempts.setdefault(operation_id,[]); item=Attempt(operation_id,len(attempts)+1,started_at,finished_at,succeeded,error); attempts.append(item); return item
    def attempts(self,operation_id:str) -> tuple[Attempt,...]: return tuple(self._attempts.get(operation_id,()))
    def retry_allowed(self,operation_id:str,max_attempts:int,now:dt.datetime,base_delay_seconds:int=5) -> tuple[bool,dt.datetime|None]:
        attempts=self._attempts.get(operation_id,[])
        if attempts and attempts[-1].succeeded: return False,None
        if len(attempts)>=max_attempts: return False,None
        if not attempts: return True,now
        delay=base_delay_seconds*(2**(len(attempts)-1)); due=attempts[-1].finished_at+dt.timedelta(seconds=delay)
        return now>=due,due
    def add_compensation(self,operation_id:str,action:str,payload:Mapping[str,Any]) -> int:
        actions=self._compensations.setdefault(operation_id,[]); item={'sequence':len(actions)+1,'action':action,'payload':dict(payload),'status':'pending'}; actions.append(item); return item['sequence']
    def pending_compensations(self,operation_id:str) -> tuple[Mapping[str,Any],...]: return tuple(dict(item) for item in self._compensations.get(operation_id,[]) if item['status']=='pending')
    def complete_compensation(self,operation_id:str,sequence:int) -> None:
        actions=self._compensations.get(operation_id,[])
        if sequence<1 or sequence>len(actions): raise RecoveryError('compensation not found')
        if actions[sequence-1]['status']=='completed': return
        actions[sequence-1]=dict(actions[sequence-1])|{'status':'completed'}
    def verify(self,operation_id:str) -> tuple[str,...]:
        problems=[]; previous=0
        for checkpoint in self._checkpoints.get(operation_id,[]):
            if checkpoint.sequence!=previous+1: problems.append('checkpoint_sequence_gap')
            if checkpoint.fingerprint!=self.fingerprint(checkpoint.state): problems.append(f'checkpoint_tampered:{checkpoint.sequence}')
            previous=checkpoint.sequence
        attempts=self._attempts.get(operation_id,[])
        if any(attempt.attempt!=index for index,attempt in enumerate(attempts,1)): problems.append('attempt_sequence_gap')
        if any(attempt.succeeded for attempt in attempts[:-1]): problems.append('attempt_after_success')
        return tuple(problems)
    def operation_summary(self,operation_id:str) -> dict[str,Any]:
        checkpoints=self._checkpoints.get(operation_id,[]); attempts=self._attempts.get(operation_id,[]); compensations=self._compensations.get(operation_id,[])
        return {'operation_id':operation_id,'checkpoint_count':len(checkpoints),'latest_stage':checkpoints[-1].stage if checkpoints else None,'attempts':len(attempts),'succeeded':bool(attempts and attempts[-1].succeeded),'pending_compensations':sum(item['status']=='pending' for item in compensations),'problems':list(self.verify(operation_id))}
