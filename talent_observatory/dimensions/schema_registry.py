from __future__ import annotations
import datetime as dt
import decimal
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

class SchemaError(ValueError):
    pass

@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: str
    required: bool = False
    minimum: decimal.Decimal | None = None
    maximum: decimal.Decimal | None = None
    choices: tuple[str,...] = ()
    pattern: str | None = None
    aliases: tuple[str,...] = ()
    default: Any = None

@dataclass(frozen=True)
class RowProblem:
    row: int
    field: str
    code: str
    detail: str

@dataclass(frozen=True)
class ValidationBatch:
    valid: tuple[Mapping[str,Any],...]
    problems: tuple[RowProblem,...]
    rejected_rows: tuple[int,...]

class SchemaRegistry:
    def __init__(self):
        self._schemas: dict[tuple[str,int],tuple[FieldSpec,...]]={}
        self._latest: dict[str,int]={}

    def register(self,name:str,version:int,fields:Sequence[FieldSpec]) -> None:
        if not name or version<1: raise SchemaError('invalid schema identity')
        key=(name,version)
        if key in self._schemas: raise SchemaError('schema version already exists')
        names=[field.name for field in fields]
        if len(names)!=len(set(names)): raise SchemaError('duplicate field name')
        aliases=[alias for field in fields for alias in field.aliases]
        if set(names)&set(aliases): raise SchemaError('alias collides with canonical name')
        if len(aliases)!=len(set(aliases)): raise SchemaError('duplicate alias')
        self._schemas[key]=tuple(fields); self._latest[name]=max(version,self._latest.get(name,0))

    def schema(self,name:str,version:int|None=None) -> tuple[FieldSpec,...]:
        selected=version or self._latest.get(name)
        if selected is None or (name,selected) not in self._schemas: raise SchemaError('unknown schema')
        return self._schemas[(name,selected)]

    def versions(self,name:str) -> tuple[int,...]:
        return tuple(sorted(version for candidate,version in self._schemas if candidate==name))

    def normalize(self,name:str,row:Mapping[str,Any],version:int|None=None) -> dict[str,Any]:
        result=dict(row)
        for field in self.schema(name,version):
            for alias in field.aliases:
                if field.name not in result and alias in result: result[field.name]=result.pop(alias)
            if field.name not in result and field.default is not None: result[field.name]=field.default() if callable(field.default) else field.default
        return result

    def coerce(self,field:FieldSpec,value:Any) -> Any:
        if value is None or value=='':
            if field.required: raise SchemaError('required value missing')
            return None
        if field.kind=='text': result=' '.join(str(value).split())
        elif field.kind=='integer':
            if isinstance(value,bool): raise SchemaError('boolean is not integer')
            result=int(value)
        elif field.kind=='decimal': result=decimal.Decimal(str(value))
        elif field.kind=='date': result=value if isinstance(value,dt.date) else dt.date.fromisoformat(str(value))
        elif field.kind=='datetime':
            result=value if isinstance(value,dt.datetime) else dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
            if result.tzinfo is None: result=result.replace(tzinfo=dt.timezone.utc)
            result=result.astimezone(dt.timezone.utc)
        elif field.kind=='boolean':
            if isinstance(value,bool): result=value
            elif str(value).casefold() in {'true','1','yes','y'}: result=True
            elif str(value).casefold() in {'false','0','no','n'}: result=False
            else: raise SchemaError('invalid boolean')
        elif field.kind=='list': result=list(value) if not isinstance(value,str) else [item.strip() for item in value.split(',') if item.strip()]
        else: raise SchemaError('unsupported field kind')
        if field.choices and str(result) not in field.choices: raise SchemaError('value outside choices')
        if field.pattern and not re.fullmatch(field.pattern,str(result)): raise SchemaError('value does not match pattern')
        if field.minimum is not None and decimal.Decimal(str(result))<field.minimum: raise SchemaError('value below minimum')
        if field.maximum is not None and decimal.Decimal(str(result))>field.maximum: raise SchemaError('value above maximum')
        return result

    def validate_row(self,name:str,row:Mapping[str,Any],row_number:int,version:int|None=None) -> tuple[dict[str,Any],list[RowProblem]]:
        normalized=self.normalize(name,row,version); result={}; problems=[]; allowed=set()
        for field in self.schema(name,version):
            allowed.add(field.name)
            try: result[field.name]=self.coerce(field,normalized.get(field.name))
            except (SchemaError,ValueError,decimal.InvalidOperation) as exc: problems.append(RowProblem(row_number,field.name,'invalid_field',str(exc)))
        for extra in sorted(set(normalized)-allowed): problems.append(RowProblem(row_number,extra,'unknown_field','field is not in schema'))
        return result,problems

    def validate_batch(self,name:str,rows:Iterable[Mapping[str,Any]],version:int|None=None,strict:bool=False) -> ValidationBatch:
        valid=[]; problems=[]; rejected=[]
        for index,row in enumerate(rows,1):
            item,item_problems=self.validate_row(name,row,index,version)
            if item_problems: problems.extend(item_problems); rejected.append(index)
            else: valid.append(item)
        if strict and problems: raise SchemaError(f'batch contains {len(problems)} field problems')
        return ValidationBatch(tuple(valid),tuple(problems),tuple(rejected))

    def compatible(self,name:str,older:int,newer:int) -> tuple[bool,tuple[str,...]]:
        old={field.name:field for field in self.schema(name,older)}; new={field.name:field for field in self.schema(name,newer)}; issues=[]
        for field_name,field in old.items():
            if field_name not in new: issues.append(f'removed:{field_name}')
            elif new[field_name].kind!=field.kind: issues.append(f'type_changed:{field_name}')
            elif not field.required and new[field_name].required and new[field_name].default is None: issues.append(f'became_required:{field_name}')
        return not issues,tuple(issues)
