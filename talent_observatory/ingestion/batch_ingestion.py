from __future__ import annotations
import csv
import hashlib
import io
import json
from dataclasses import dataclass,field
from typing import Any,Iterable,Iterator,Mapping,Sequence

class IngestionError(RuntimeError): pass

@dataclass(frozen=True)
class IngestedRow:
    row_number:int
    key:str
    payload:Mapping[str,Any]
    checksum:str
    source_offset:int

@dataclass(frozen=True)
class IngestionResult:
    accepted:tuple[IngestedRow,...]
    duplicates:tuple[IngestedRow,...]
    rejected:tuple[tuple[int,str],...]
    input_checksum:str
    statistics:Mapping[str,int]

class BatchReader:
    def json_lines(self,text:str) -> Iterator[tuple[int,dict[str,Any]]]:
        for number,line in enumerate(text.splitlines(),1):
            if not line.strip(): continue
            try: value=json.loads(line)
            except json.JSONDecodeError as exc: raise IngestionError(f'line {number}: {exc.msg}') from exc
            if not isinstance(value,dict): raise IngestionError(f'line {number}: object required')
            yield number,value

    def csv_rows(self,text:str) -> Iterator[tuple[int,dict[str,Any]]]:
        reader=csv.DictReader(io.StringIO(text))
        if not reader.fieldnames: raise IngestionError('CSV header required')
        for number,row in enumerate(reader,2): yield number,dict(row)

    def json_array(self,text:str) -> Iterator[tuple[int,dict[str,Any]]]:
        try: values=json.loads(text)
        except json.JSONDecodeError as exc: raise IngestionError(exc.msg) from exc
        if not isinstance(values,list): raise IngestionError('JSON array required')
        for number,value in enumerate(values,1):
            if not isinstance(value,dict): raise IngestionError(f'item {number}: object required')
            yield number,value

class BatchIngestor:
    def __init__(self,key_fields:Sequence[str],duplicate_policy:str='keep-first'):
        if not key_fields: raise IngestionError('key fields required')
        if duplicate_policy not in {'keep-first','keep-last','reject'}: raise IngestionError('unsupported duplicate policy')
        self.key_fields=tuple(key_fields); self.duplicate_policy=duplicate_policy

    def key(self,row:Mapping[str,Any]) -> str:
        values=[]
        for field in self.key_fields:
            value=str(row.get(field,'')).strip()
            if not value: raise IngestionError(f'missing key field {field}')
            values.append(value)
        return '|'.join(values)

    def checksum(self,row:Mapping[str,Any]) -> str:
        return hashlib.sha256(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

    def ingest(self,rows:Iterable[tuple[int,Mapping[str,Any]]]) -> IngestionResult:
        accepted:dict[str,IngestedRow]={}; duplicates=[]; rejected=[]; input_hash=hashlib.sha256(); total=0
        for offset,(row_number,payload) in enumerate(rows):
            total+=1; normalized=dict(payload); input_hash.update(self.checksum(normalized).encode())
            try: key=self.key(normalized)
            except IngestionError as exc: rejected.append((row_number,str(exc))); continue
            item=IngestedRow(row_number,key,normalized,self.checksum(normalized),offset)
            existing=accepted.get(key)
            if existing is None: accepted[key]=item; continue
            if existing.checksum==item.checksum: duplicates.append(item); continue
            if self.duplicate_policy=='reject': rejected.append((row_number,'conflicting duplicate')); continue
            if self.duplicate_policy=='keep-last': duplicates.append(existing); accepted[key]=item
            else: duplicates.append(item)
        values=tuple(sorted(accepted.values(),key=lambda item:item.source_offset))
        return IngestionResult(values,tuple(duplicates),tuple(rejected),input_hash.hexdigest(),{'input':total,'accepted':len(values),'duplicates':len(duplicates),'rejected':len(rejected)})

    def chunks(self,result:IngestionResult,size:int) -> Iterator[tuple[IngestedRow,...]]:
        if size<1: raise IngestionError('chunk size must be positive')
        for offset in range(0,len(result.accepted),size): yield result.accepted[offset:offset+size]

    def resume(self,result:IngestionResult,after_offset:int) -> tuple[IngestedRow,...]:
        return tuple(item for item in result.accepted if item.source_offset>after_offset)

    def reconcile(self,previous:IngestionResult,current:IngestionResult) -> dict[str,tuple[str,...]]:
        before={item.key:item for item in previous.accepted}; after={item.key:item for item in current.accepted}
        added=tuple(sorted(set(after)-set(before))); removed=tuple(sorted(set(before)-set(after)))
        changed=tuple(sorted(key for key in set(before)&set(after) if before[key].checksum!=after[key].checksum))
        unchanged=tuple(sorted(key for key in set(before)&set(after) if before[key].checksum==after[key].checksum))
        return {'added':added,'removed':removed,'changed':changed,'unchanged':unchanged}
