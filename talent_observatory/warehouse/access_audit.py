from __future__ import annotations
import datetime as dt
import hashlib
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence

class AccessError(RuntimeError):pass

@dataclass(frozen=True)
class Grant:
    subject_id:str
    actor_id:str
    purposes:frozenset[str]
    fields:frozenset[str]
    valid_from:dt.datetime
    valid_until:dt.datetime
    revoked_at:dt.datetime|None=None

@dataclass(frozen=True)
class AccessEvent:
    event_id:str
    subject_id:str
    actor_id:str
    purpose:str
    fields:tuple[str,...]
    occurred_at:dt.datetime
    allowed:bool
    reasons:tuple[str,...]

class AccessAuditor:
    def __init__(self):self.grants:list[Grant]=[];self.events:list[AccessEvent]=[];self._event_hashes:list[str]=[]
    def grant(self,subject_id:str,actor_id:str,purposes:Iterable[str],fields:Iterable[str],valid_from:dt.datetime,valid_until:dt.datetime) -> Grant:
        if not subject_id or not actor_id:raise AccessError('subject and actor required')
        if valid_until<=valid_from:raise AccessError('grant end must follow start')
        grant=Grant(subject_id,actor_id,frozenset(purposes),frozenset(fields),valid_from,valid_until);self.grants.append(grant);return grant
    def revoke(self,grant:Grant,revoked_at:dt.datetime) -> Grant:
        if revoked_at<grant.valid_from:raise AccessError('revocation precedes grant')
        updated=Grant(grant.subject_id,grant.actor_id,grant.purposes,grant.fields,grant.valid_from,grant.valid_until,revoked_at);self.grants[self.grants.index(grant)]=updated;return updated
    def active_grants(self,subject_id:str,actor_id:str,moment:dt.datetime) -> tuple[Grant,...]:
        return tuple(grant for grant in self.grants if grant.subject_id==subject_id and grant.actor_id==actor_id and grant.valid_from<=moment<grant.valid_until and (grant.revoked_at is None or moment<grant.revoked_at))
    def authorize(self,subject_id:str,actor_id:str,purpose:str,fields:Iterable[str],moment:dt.datetime) -> AccessEvent:
        requested=tuple(sorted(set(fields)));grants=self.active_grants(subject_id,actor_id,moment);reasons=[]
        if not grants:reasons.append('no_active_grant')
        if grants and not any(purpose in grant.purposes for grant in grants):reasons.append('purpose_not_granted')
        allowed_fields=set().union(*(grant.fields for grant in grants if purpose in grant.purposes)) if grants else set();missing=sorted(set(requested)-allowed_fields)
        if missing:reasons.append('fields_not_granted:'+','.join(missing))
        allowed=not reasons;previous=self._event_hashes[-1] if self._event_hashes else 'GENESIS';raw='|'.join([previous,subject_id,actor_id,purpose,','.join(requested),moment.isoformat(),str(len(self.events)+1),str(allowed),','.join(reasons)]);digest=hashlib.sha256(raw.encode()).hexdigest();event=AccessEvent(digest[:24],subject_id,actor_id,purpose,requested,moment,allowed,tuple(reasons));self.events.append(event);self._event_hashes.append(digest);return event
    def require(self,*args,**kwargs) -> AccessEvent:
        event=self.authorize(*args,**kwargs)
        if not event.allowed:raise AccessError(';'.join(event.reasons))
        return event
    def history(self,subject_id:str|None=None,actor_id:str|None=None) -> tuple[AccessEvent,...]:return tuple(event for event in self.events if (subject_id is None or event.subject_id==subject_id) and (actor_id is None or event.actor_id==actor_id))
    def report(self) -> dict[str,Any]:
        return {'events':len(self.events),'allowed':sum(event.allowed for event in self.events),'denied':sum(not event.allowed for event in self.events),'subjects':len({event.subject_id for event in self.events}),'actors':len({event.actor_id for event in self.events}),'denial_reasons':sorted({reason for event in self.events for reason in event.reasons})}
    def excessive_access(self,actor_id:str,window_start:dt.datetime,maximum_subjects:int) -> bool:
        subjects={event.subject_id for event in self.events if event.actor_id==actor_id and event.allowed and event.occurred_at>=window_start};return len(subjects)>maximum_subjects
    def purpose_matrix(self) -> dict[str,dict[str,int]]:
        result={}
        for event in self.events:
            row=result.setdefault(event.purpose,{'allowed':0,'denied':0,'subjects':set(),'actors':set()});row['allowed' if event.allowed else 'denied']+=1;row['subjects'].add(event.subject_id);row['actors'].add(event.actor_id)
        return {purpose:{'allowed':row['allowed'],'denied':row['denied'],'subjects':len(row['subjects']),'actors':len(row['actors'])} for purpose,row in sorted(result.items())}
    def actor_matrix(self) -> dict[str,dict[str,Any]]:
        result={}
        for event in self.events:
            row=result.setdefault(event.actor_id,{'allowed':0,'denied':0,'purposes':set(),'subjects':set(),'fields':set()});row['allowed' if event.allowed else 'denied']+=1;row['purposes'].add(event.purpose);row['subjects'].add(event.subject_id);row['fields'].update(event.fields)
        return {actor:{'allowed':row['allowed'],'denied':row['denied'],'purposes':tuple(sorted(row['purposes'])),'subjects':len(row['subjects']),'fields':tuple(sorted(row['fields']))} for actor,row in sorted(result.items())}
    def subject_matrix(self) -> dict[str,dict[str,Any]]:
        result={}
        for event in self.events:
            row=result.setdefault(event.subject_id,{'allowed':0,'denied':0,'actors':set(),'purposes':set()});row['allowed' if event.allowed else 'denied']+=1;row['actors'].add(event.actor_id);row['purposes'].add(event.purpose)
        return {subject:{'allowed':row['allowed'],'denied':row['denied'],'actors':tuple(sorted(row['actors'])),'purposes':tuple(sorted(row['purposes']))} for subject,row in sorted(result.items())}
    def active_scope(self,subject_id:str,actor_id:str,moment:dt.datetime) -> dict[str,tuple[str,...]]:
        grants=self.active_grants(subject_id,actor_id,moment);purposes=set();fields=set()
        for grant in grants:purposes.update(grant.purposes);fields.update(grant.fields)
        return {'purposes':tuple(sorted(purposes)),'fields':tuple(sorted(fields))}
    def expire_grants(self,moment:dt.datetime) -> tuple[Grant,...]:return tuple(grant for grant in self.grants if grant.valid_until<=moment or (grant.revoked_at is not None and grant.revoked_at<=moment))
    def purge_events(self,before:dt.datetime,retain_denials:bool=True) -> int:
        kept=[];kept_hashes=[];removed=0
        for event,digest in zip(self.events,self._event_hashes):
            if event.occurred_at<before and not (retain_denials and not event.allowed):removed+=1
            else:kept.append(event);kept_hashes.append(digest)
        self.events=kept;self._event_hashes=kept_hashes;return removed
    def verify_chain(self) -> tuple[str,...]:
        problems=[];previous='GENESIS'
        for index,event in enumerate(self.events):
            raw='|'.join([previous,event.subject_id,event.actor_id,event.purpose,','.join(event.fields),event.occurred_at.isoformat(),str(index+1),str(event.allowed),','.join(event.reasons)]);digest=hashlib.sha256(raw.encode()).hexdigest()
            if event.event_id!=digest[:24]:problems.append(f'event_id:{index+1}')
            if index>=len(self._event_hashes) or self._event_hashes[index]!=digest:problems.append(f'event_hash:{index+1}')
            previous=digest
        if len(self._event_hashes)!=len(self.events):problems.append('cardinality')
        return tuple(problems)
    def replay(self,events:Sequence[AccessEvent]) -> None:
        self.events=[];self._event_hashes=[]
        for event in events:self.authorize(event.subject_id,event.actor_id,event.purpose,event.fields,event.occurred_at)
    def grant_inventory(self,moment:dt.datetime) -> dict[str,Any]:
        active=[];expired=[];revoked=[]
        for grant in self.grants:
            item={'subject_id':grant.subject_id,'actor_id':grant.actor_id,'purposes':tuple(sorted(grant.purposes)),'fields':tuple(sorted(grant.fields)),'valid_from':grant.valid_from.isoformat(),'valid_until':grant.valid_until.isoformat(),'revoked_at':grant.revoked_at.isoformat() if grant.revoked_at else None}
            if grant.revoked_at is not None and grant.revoked_at<=moment:revoked.append(item)
            elif grant.valid_until<=moment:expired.append(item)
            elif grant.valid_from<=moment<grant.valid_until:active.append(item)
        return {'active':tuple(active),'expired':tuple(expired),'revoked':tuple(revoked),'counts':{'active':len(active),'expired':len(expired),'revoked':len(revoked)}}
    def field_usage(self) -> dict[str,dict[str,int]]:
        result={}
        for event in self.events:
            for field in event.fields:
                row=result.setdefault(field,{'allowed':0,'denied':0,'subjects':set(),'actors':set()});row['allowed' if event.allowed else 'denied']+=1;row['subjects'].add(event.subject_id);row['actors'].add(event.actor_id)
        return {field:{'allowed':row['allowed'],'denied':row['denied'],'subjects':len(row['subjects']),'actors':len(row['actors'])} for field,row in sorted(result.items())}
    def uncovered_requests(self) -> tuple[dict[str,Any],...]:
        result=[]
        for event in self.events:
            if event.allowed:continue
            result.append({'event_id':event.event_id,'subject_id':event.subject_id,'actor_id':event.actor_id,'purpose':event.purpose,'fields':event.fields,'occurred_at':event.occurred_at.isoformat(),'reasons':event.reasons})
        return tuple(result)
    def export_manifest(self) -> dict[str,Any]:
        events=[]
        for event,digest in zip(self.events,self._event_hashes):events.append({'event_id':event.event_id,'subject_id':event.subject_id,'actor_id':event.actor_id,'purpose':event.purpose,'fields':event.fields,'occurred_at':event.occurred_at.isoformat(),'allowed':event.allowed,'reasons':event.reasons,'sha256':digest})
        grants=[]
        for grant in self.grants:grants.append({'subject_id':grant.subject_id,'actor_id':grant.actor_id,'purposes':tuple(sorted(grant.purposes)),'fields':tuple(sorted(grant.fields)),'valid_from':grant.valid_from.isoformat(),'valid_until':grant.valid_until.isoformat(),'revoked_at':grant.revoked_at.isoformat() if grant.revoked_at else None})
        content='\n'.join(item['sha256'] for item in events);return {'events':tuple(events),'grants':tuple(grants),'event_count':len(events),'grant_count':len(grants),'chain_sha256':hashlib.sha256(content.encode()).hexdigest(),'problems':self.verify_chain()}
    def coverage(self,moment:dt.datetime) -> dict[str,Any]:
        inventory=self.grant_inventory(moment);subjects={grant['subject_id'] for grant in inventory['active']};actors={grant['actor_id'] for grant in inventory['active']};purposes={purpose for grant in inventory['active'] for purpose in grant['purposes']};fields={field for grant in inventory['active'] for field in grant['fields']}
        return {'active_grants':inventory['counts']['active'],'subjects':len(subjects),'actors':len(actors),'purposes':tuple(sorted(purposes)),'fields':tuple(sorted(fields)),'denied_requests':len(self.uncovered_requests())}
    def gap_summary(self) -> dict[str,Any]:
        by_purpose={};by_field={};by_reason={};actors=set();subjects=set()
        for event in self.events:
            if event.allowed:continue
            actors.add(event.actor_id);subjects.add(event.subject_id)
            purpose=by_purpose.setdefault(event.purpose,{'requests':0,'actors':set(),'subjects':set()});purpose['requests']+=1;purpose['actors'].add(event.actor_id);purpose['subjects'].add(event.subject_id)
            for field in event.fields:
                item=by_field.setdefault(field,{'requests':0,'purposes':set()});item['requests']+=1;item['purposes'].add(event.purpose)
            for reason in event.reasons:by_reason[reason]=by_reason.get(reason,0)+1
        return {'denied_requests':sum(by_reason.values()) if by_reason else 0,'actors':len(actors),'subjects':len(subjects),'purposes':{key:{'requests':value['requests'],'actors':len(value['actors']),'subjects':len(value['subjects'])} for key,value in sorted(by_purpose.items())},'fields':{key:{'requests':value['requests'],'purposes':tuple(sorted(value['purposes']))} for key,value in sorted(by_field.items())},'reasons':dict(sorted(by_reason.items()))}
    def recent_denials(self,since:dt.datetime,limit:int=100) -> tuple[AccessEvent,...]:
        if limit<1:raise AccessError('limit must be positive')
        values=[event for event in self.events if not event.allowed and event.occurred_at>=since]
        values.sort(key=lambda event:(event.occurred_at,event.event_id),reverse=True)
        return tuple(values[:limit])
    def actor_risk(self,actor_id:str,since:dt.datetime) -> dict[str,Any]:
        events=[event for event in self.events if event.actor_id==actor_id and event.occurred_at>=since]
        denied=[event for event in events if not event.allowed]
        return {'actor_id':actor_id,'requests':len(events),'denied':len(denied),'denial_rate':len(denied)/len(events) if events else 0.0,'subjects':len({event.subject_id for event in events}),'purposes':tuple(sorted({event.purpose for event in events}))}
    def active_grant_count(self,moment:dt.datetime) -> int:return self.grant_inventory(moment)['counts']['active']
