from __future__ import annotations
import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence

class PublicationError(RuntimeError):pass

@dataclass(frozen=True)
class DataFile:
    name:str
    media_type:str
    content:bytes
    sha256:str
    records:int

@dataclass(frozen=True)
class Publication:
    publication_id:str
    created_at:dt.datetime
    files:tuple[DataFile,...]
    manifest:Mapping[str,Any]
    fingerprint:str

class SnapshotPublisher:
    def canonical(self,value:Any) -> bytes:return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()
    def json_file(self,name:str,rows:Sequence[Mapping[str,Any]]) -> DataFile:
        content=json.dumps(list(rows),ensure_ascii=False,sort_keys=True,indent=2,default=str).encode();return DataFile(name,'application/json',content,hashlib.sha256(content).hexdigest(),len(rows))
    def json_lines_file(self,name:str,rows:Sequence[Mapping[str,Any]]) -> DataFile:
        content=b'\n'.join(self.canonical(row) for row in rows)+(b'\n' if rows else b'');return DataFile(name,'application/x-ndjson',content,hashlib.sha256(content).hexdigest(),len(rows))
    def csv_file(self,name:str,rows:Sequence[Mapping[str,Any]],fields:Sequence[str]) -> DataFile:
        import csv,io
        buffer=io.StringIO();writer=csv.DictWriter(buffer,fieldnames=list(fields),extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(rows);content=buffer.getvalue().encode();return DataFile(name,'text/csv',content,hashlib.sha256(content).hexdigest(),len(rows))
    def publish(self,publication_id:str,datasets:Mapping[str,Sequence[Mapping[str,Any]]],created_at:dt.datetime|None=None) -> Publication:
        if not publication_id:raise PublicationError('publication id required')
        files=[]
        for name,rows in sorted(datasets.items()):files.append(self.json_lines_file(name+'.jsonl',rows))
        manifest={'publication_id':publication_id,'datasets':{name:len(rows) for name,rows in sorted(datasets.items())},'files':[{'name':file.name,'media_type':file.media_type,'sha256':file.sha256,'records':file.records} for file in files]}
        fingerprint=hashlib.sha256(self.canonical(manifest)).hexdigest();return Publication(publication_id,created_at or dt.datetime.now(dt.timezone.utc),tuple(files),manifest,fingerprint)
    def verify(self,publication:Publication) -> tuple[str,...]:
        problems=[]
        for file in publication.files:
            if hashlib.sha256(file.content).hexdigest()!=file.sha256:problems.append(f'file_hash:{file.name}')
        if hashlib.sha256(self.canonical(publication.manifest)).hexdigest()!=publication.fingerprint:problems.append('manifest_hash')
        declared={item['name']:item for item in publication.manifest.get('files',[])}
        for file in publication.files:
            if file.name not in declared:problems.append(f'undeclared_file:{file.name}')
            elif declared[file.name].get('sha256')!=file.sha256:problems.append(f'manifest_file_hash:{file.name}')
        return tuple(problems)
    def difference(self,left:Publication,right:Publication) -> dict[str,Any]:
        a={file.name:file for file in left.files};b={file.name:file for file in right.files}
        return {'added':tuple(sorted(set(b)-set(a))),'removed':tuple(sorted(set(a)-set(b))),'changed':tuple(sorted(name for name in set(a)&set(b) if a[name].sha256!=b[name].sha256)),'unchanged':tuple(sorted(name for name in set(a)&set(b) if a[name].sha256==b[name].sha256))}
    def inventory(self,publication:Publication) -> dict[str,Any]:return {'publication_id':publication.publication_id,'fingerprint':publication.fingerprint,'files':len(publication.files),'records':sum(file.records for file in publication.files),'bytes':sum(len(file.content) for file in publication.files),'media_types':sorted({file.media_type for file in publication.files})}
