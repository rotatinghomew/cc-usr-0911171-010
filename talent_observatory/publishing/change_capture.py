from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence

class ChangeError(RuntimeError):pass

@dataclass(frozen=True)
class Change:
    key:str
    operation:str
    before:Mapping[str,Any]|None
    after:Mapping[str,Any]|None
    changed_fields:tuple[str,...]
    before_hash:str|None
    after_hash:str|None

class ChangeCapture:
    def __init__(self,key_fields:Sequence[str]):
        if not key_fields:raise ChangeError('key fields required')
        self.key_fields=tuple(key_fields)
    def key(self,row:Mapping[str,Any]) -> str:
        values=[str(row.get(field,'')).strip() for field in self.key_fields]
        if any(not value for value in values):raise ChangeError('row missing key')
        return '|'.join(values)
    def digest(self,row:Mapping[str,Any]) -> str:return hashlib.sha256(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
    def index(self,rows:Iterable[Mapping[str,Any]]) -> dict[str,Mapping[str,Any]]:
        result={}
        for row in rows:
            key=self.key(row)
            if key in result:raise ChangeError(f'duplicate key {key}')
            result[key]=dict(row)
        return result
    def compare(self,before:Iterable[Mapping[str,Any]],after:Iterable[Mapping[str,Any]],ignore_fields:Iterable[str]=()) -> tuple[Change,...]:
        left=self.index(before);right=self.index(after);ignore=set(ignore_fields);changes=[]
        for key in sorted(set(left)|set(right)):
            old=left.get(key);new=right.get(key)
            if old is None:changes.append(Change(key,'insert',None,new,tuple(sorted(new)),None,self.digest(new)));continue
            if new is None:changes.append(Change(key,'delete',old,None,tuple(sorted(old)),self.digest(old),None));continue
            fields=tuple(sorted(field for field in set(old)|set(new) if field not in ignore and old.get(field)!=new.get(field)))
            if fields:changes.append(Change(key,'update',old,new,fields,self.digest(old),self.digest(new)))
        return tuple(changes)
    def apply(self,base:Iterable[Mapping[str,Any]],changes:Sequence[Change],strict:bool=True) -> tuple[Mapping[str,Any],...]:
        result=self.index(base)
        for change in changes:
            current=result.get(change.key)
            if change.operation=='insert':
                if strict and current is not None:raise ChangeError('insert target exists')
                result[change.key]=dict(change.after or {})
            elif change.operation=='delete':
                if strict and current is None:raise ChangeError('delete target missing')
                if strict and current is not None and self.digest(current)!=change.before_hash:raise ChangeError('delete precondition failed')
                result.pop(change.key,None)
            elif change.operation=='update':
                if current is None:raise ChangeError('update target missing')
                if strict and self.digest(current)!=change.before_hash:raise ChangeError('update precondition failed')
                result[change.key]=dict(change.after or {})
            else:raise ChangeError('unknown operation')
        return tuple(result[key] for key in sorted(result))
    def invert(self,changes:Sequence[Change]) -> tuple[Change,...]:
        result=[]
        for change in reversed(changes):
            if change.operation=='insert':result.append(Change(change.key,'delete',change.after,None,change.changed_fields,change.after_hash,None))
            elif change.operation=='delete':result.append(Change(change.key,'insert',None,change.before,change.changed_fields,None,change.before_hash))
            else:result.append(Change(change.key,'update',change.after,change.before,change.changed_fields,change.after_hash,change.before_hash))
        return tuple(result)
    def summary(self,changes:Sequence[Change]) -> dict[str,Any]:
        operations={'insert':0,'update':0,'delete':0};fields={}
        for change in changes:
            operations[change.operation]+=1
            for field in change.changed_fields:fields[field]=fields.get(field,0)+1
        return {'total':len(changes),'operations':operations,'fields':dict(sorted(fields.items()))}
