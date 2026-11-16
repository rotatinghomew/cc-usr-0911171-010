from __future__ import annotations
import hashlib
import hmac
import ipaddress
import re
from dataclasses import dataclass
from typing import Any,Iterable,Mapping,Sequence

class PrivacyError(ValueError):pass

@dataclass(frozen=True)
class FieldPolicy:
    field:str
    action:str
    roles:frozenset[str]=frozenset()
    keep_start:int=0
    keep_end:int=0

class PrivacyProjector:
    ACTIONS={'keep','drop','mask','hash','tokenize','generalize_date','generalize_ip','last4'}
    def __init__(self,policies:Sequence[FieldPolicy],secret:bytes):
        if len(secret)<16:raise PrivacyError('secret must be at least 16 bytes')
        self.policies={policy.field:policy for policy in policies};self.secret=secret
        if any(policy.action not in self.ACTIONS for policy in policies):raise PrivacyError('unsupported privacy action')
    def token(self,value:Any,namespace:str='default') -> str:return hmac.new(self.secret,(namespace+'|'+str(value)).encode(),hashlib.sha256).hexdigest()[:24]
    def mask(self,value:Any,keep_start:int=0,keep_end:int=0) -> str:
        text=str(value);middle=max(0,len(text)-keep_start-keep_end)
        return text[:keep_start]+'*'*middle+(text[len(text)-keep_end:] if keep_end else '')
    def apply_value(self,policy:FieldPolicy,value:Any,role:str) -> Any:
        if policy.roles and role in policy.roles:return value
        if policy.action=='keep':return value
        if policy.action=='drop':return None
        if policy.action=='mask':return self.mask(value,policy.keep_start,policy.keep_end)
        if policy.action=='hash':return hashlib.sha256(str(value).encode()).hexdigest()
        if policy.action=='tokenize':return self.token(value,policy.field)
        if policy.action=='last4':return self.mask(value,0,4)
        if policy.action=='generalize_date':return str(value)[:7] if value is not None else None
        if policy.action=='generalize_ip':
            address=ipaddress.ip_address(str(value));network=ipaddress.ip_network(f'{address}/24' if address.version==4 else f'{address}/64',strict=False);return str(network)
        raise PrivacyError('unsupported privacy action')
    def project(self,row:Mapping[str,Any],role:str='public') -> dict[str,Any]:
        result={}
        for field,value in row.items():
            policy=self.policies.get(field)
            if policy is None:result[field]=value;continue
            projected=self.apply_value(policy,value,role)
            if policy.action!='drop':result[field]=projected
        return result
    def project_many(self,rows:Iterable[Mapping[str,Any]],role:str='public') -> tuple[dict[str,Any],...]:return tuple(self.project(row,role) for row in rows)
    def audit(self,original:Mapping[str,Any],projected:Mapping[str,Any],role:str='public') -> tuple[str,...]:
        problems=[]
        for field,policy in self.policies.items():
            if policy.roles and role in policy.roles:continue
            if policy.action=='drop' and field in projected:problems.append(f'not_dropped:{field}')
            elif policy.action!='drop' and field in original and field not in projected:problems.append(f'missing_projection:{field}')
            elif policy.action in {'mask','hash','tokenize','last4','generalize_date','generalize_ip'} and field in original and projected.get(field)==original.get(field):problems.append(f'unchanged_sensitive:{field}')
        return tuple(problems)
    def stable_join_key(self,row:Mapping[str,Any],fields:Sequence[str],namespace:str='join') -> str:
        values=[]
        for field in fields:
            value=row.get(field)
            if value in {None,''}:raise PrivacyError(f'missing join field {field}')
            values.append(str(value).strip().casefold())
        return self.token('|'.join(values),namespace)
    def detect_plaintext(self,row:Mapping[str,Any]) -> tuple[str,...]:
        problems=[]
        email=re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');phone=re.compile(r'^\+?\d[\d -]{7,}$')
        for field,value in row.items():
            text=str(value)
            if email.fullmatch(text):problems.append(f'email:{field}')
            digits=''.join(character for character in text if character.isdigit())
            if phone.fullmatch(text) and len(digits)>=10 and any(token in field.casefold() for token in ('phone','mobile','tel')):problems.append(f'phone:{field}')
        return tuple(problems)
