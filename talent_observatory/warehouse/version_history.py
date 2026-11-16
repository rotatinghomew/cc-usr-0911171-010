from __future__ import annotations
import dataclasses
import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence

class VersionError(RuntimeError): pass

@dataclass(frozen=True)
class Revision:
    entity_id:str
    version:int
    recorded_at:dt.datetime
    actor:str
    reason:str
    content:Mapping[str,Any]
    fingerprint:str
    parent_fingerprint:str|None

@dataclass(frozen=True)
class FieldChange:
    path:str
    before:Any
    after:Any
    kind:str

class VersionHistory:
    def __init__(self): self._revisions:dict[str,list[Revision]]={}
    def fingerprint(self,content:Mapping[str,Any]) -> str: return hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
    def append(self,entity_id:str,content:Mapping[str,Any],actor:str,reason:str,recorded_at:dt.datetime|None=None,expected_version:int|None=None) -> Revision:
        history=self._revisions.setdefault(entity_id,[]); current=len(history)
        if expected_version is not None and expected_version!=current: raise VersionError(f'expected {expected_version}, found {current}')
        digest=self.fingerprint(content)
        if history and history[-1].fingerprint==digest: return history[-1]
        revision=Revision(entity_id,current+1,recorded_at or dt.datetime.now(dt.timezone.utc),actor,reason,dict(content),digest,history[-1].fingerprint if history else None)
        history.append(revision); return revision
    def get(self,entity_id:str,version:int|None=None) -> Revision:
        history=self._revisions.get(entity_id,[])
        if not history: raise VersionError('unknown entity')
        if version is None: return history[-1]
        if version<1 or version>len(history): raise VersionError('unknown version')
        return history[version-1]
    def history(self,entity_id:str) -> tuple[Revision,...]: return tuple(self._revisions.get(entity_id,()))
    def diff(self,entity_id:str,left:int,right:int) -> tuple[FieldChange,...]: return self.diff_content(self.get(entity_id,left).content,self.get(entity_id,right).content)
    def diff_content(self,left:Any,right:Any,path:str='$') -> tuple[FieldChange,...]:
        changes=[]
        if isinstance(left,Mapping) and isinstance(right,Mapping):
            for key in sorted(set(left)|set(right)):
                child=f'{path}.{key}'
                if key not in left: changes.append(FieldChange(child,None,right[key],'added'))
                elif key not in right: changes.append(FieldChange(child,left[key],None,'removed'))
                else: changes.extend(self.diff_content(left[key],right[key],child))
        elif isinstance(left,list) and isinstance(right,list):
            for index in range(max(len(left),len(right))):
                child=f'{path}[{index}]'
                if index>=len(left): changes.append(FieldChange(child,None,right[index],'added'))
                elif index>=len(right): changes.append(FieldChange(child,left[index],None,'removed'))
                else: changes.extend(self.diff_content(left[index],right[index],child))
        elif left!=right: changes.append(FieldChange(path,left,right,'changed'))
        return tuple(changes)
    def rollback_plan(self,entity_id:str,target_version:int) -> dict[str,Any]:
        current=self.get(entity_id); target=self.get(entity_id,target_version)
        if target.version>=current.version: raise VersionError('target must precede current')
        return {'entity_id':entity_id,'from_version':current.version,'to_version':target.version,'target_content':dict(target.content),'changes':[dataclasses.asdict(change) for change in self.diff_content(current.content,target.content)]}
    def verify_chain(self,entity_id:str) -> tuple[str,...]:
        problems=[]; previous=None
        for expected,revision in enumerate(self.history(entity_id),1):
            if revision.version!=expected: problems.append(f'version_gap:{expected}')
            if revision.parent_fingerprint!=previous: problems.append(f'parent_mismatch:{revision.version}')
            if revision.fingerprint!=self.fingerprint(revision.content): problems.append(f'content_mismatch:{revision.version}')
            previous=revision.fingerprint
        return tuple(problems)
    def affected(self,entity_ids:Iterable[str],field_prefix:str,left_version:int,right_version:int) -> tuple[str,...]:
        result=[]
        for entity_id in entity_ids:
            try: changes=self.diff(entity_id,left_version,right_version)
            except VersionError: continue
            if any(change.path.startswith(field_prefix) for change in changes): result.append(entity_id)
        return tuple(sorted(result))
