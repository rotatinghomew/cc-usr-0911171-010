from __future__ import annotations

import dataclasses
import datetime as dt
import decimal
import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

class ContractError(ValueError):
    pass

class State(str, Enum):
    DRAFT = 'draft'
    RECEIVED = 'received'
    VALIDATED = 'validated'
    ACTIVE = 'active'
    SUSPENDED = 'suspended'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

def require_text(value: Any, name: str, minimum: int = 1, maximum: int = 160) -> str:
    if not isinstance(value, str):
        raise ContractError(f'{name} must be text')
    normalized = ' '.join(value.split())
    if len(normalized) < minimum or len(normalized) > maximum:
        raise ContractError(f'{name} length out of range')
    return normalized

def require_identifier(value: Any, name: str) -> str:
    normalized = require_text(value, name, 2, 96)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', normalized):
        raise ContractError(f'{name} has invalid characters')
    return normalized

def require_integer(value: Any, name: str, minimum: int = 0, maximum: int = 10**9) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f'{name} must be integer')
    if not minimum <= value <= maximum:
        raise ContractError(f'{name} out of range')
    return value

def require_decimal(value: Any, name: str, minimum: str = '0', maximum: str = '1000000000') -> decimal.Decimal:
    try:
        result = decimal.Decimal(str(value))
    except decimal.InvalidOperation as exc:
        raise ContractError(f'{name} must be decimal') from exc
    if not decimal.Decimal(minimum) <= result <= decimal.Decimal(maximum):
        raise ContractError(f'{name} out of range')
    return result.quantize(decimal.Decimal('0.01'))

def require_date(value: Any, name: str) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError as exc:
            raise ContractError(f'{name} must be ISO date') from exc
    raise ContractError(f'{name} must be date')

def require_datetime(value: Any, name: str) -> dt.datetime:
    if isinstance(value, dt.datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError as exc:
            raise ContractError(f'{name} must be ISO datetime') from exc
    else:
        raise ContractError(f'{name} must be datetime')
    if result.tzinfo is None:
        result = result.replace(tzinfo=dt.timezone.utc)
    return result.astimezone(dt.timezone.utc)

def canonical_json(value: Any) -> str:
    def default(item: Any) -> Any:
        if isinstance(item, (dt.date, dt.datetime)):
            return item.isoformat()
        if isinstance(item, decimal.Decimal):
            return format(item, 'f')
        if isinstance(item, Enum):
            return item.value
        if dataclasses.is_dataclass(item):
            return dataclasses.asdict(item)
        raise TypeError(type(item).__name__)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=default)

def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()

@dataclass(frozen=True)
class Event:
    event_id: str
    aggregate_type: str
    aggregate_id: str
    kind: str
    occurred_at: dt.datetime
    payload: Mapping[str, Any]
    sequence: int

    def __post_init__(self) -> None:
        object.__setattr__(self, 'event_id', require_identifier(self.event_id, 'event_id'))
        object.__setattr__(self, 'aggregate_type', require_identifier(self.aggregate_type, 'aggregate_type'))
        object.__setattr__(self, 'aggregate_id', require_identifier(self.aggregate_id, 'aggregate_id'))
        object.__setattr__(self, 'kind', require_identifier(self.kind, 'kind'))
        object.__setattr__(self, 'occurred_at', require_datetime(self.occurred_at, 'occurred_at'))
        object.__setattr__(self, 'sequence', require_integer(self.sequence, 'sequence', 1))
        if not isinstance(self.payload, Mapping):
            raise ContractError('payload must be mapping')

@dataclass(frozen=True)
class CommandResult:
    aggregate_id: str
    version: int
    state: str
    changed: bool
    messages: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

@dataclass(frozen=True)
class IndustryRecord:
    industry_id: str
    owner_id: str
    category: str
    status: str = 'draft'
    effective_from: dt.date = field(default_factory=dt.date.today)
    effective_to: dt.date | None = None
    quantity: int = 0
    amount: decimal.Decimal = decimal.Decimal('0.00')
    attributes: Mapping[str, Any] = field(default_factory=dict)
    version: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, 'industry_id', require_identifier(self.industry_id, 'industry_id'))
        object.__setattr__(self, 'owner_id', require_identifier(self.owner_id, 'owner_id'))
        object.__setattr__(self, 'category', require_text(self.category, 'category', 2, 80))
        if self.status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        object.__setattr__(self, 'effective_from', require_date(self.effective_from, 'effective_from'))
        if self.effective_to is not None:
            object.__setattr__(self, 'effective_to', require_date(self.effective_to, 'effective_to'))
            if self.effective_to < self.effective_from:
                raise ContractError('effective_to precedes effective_from')
        object.__setattr__(self, 'quantity', require_integer(self.quantity, 'quantity'))
        object.__setattr__(self, 'amount', require_decimal(self.amount, 'amount'))
        object.__setattr__(self, 'version', require_integer(self.version, 'version'))
        if not isinstance(self.attributes, Mapping):
            raise ContractError('attributes must be mapping')

    @property
    def active_days(self) -> int | None:
        if self.effective_to is None:
            return None
        return (self.effective_to - self.effective_from).days + 1

    def with_status(self, status: str) -> 'IndustryRecord':
        if status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        return dataclasses.replace(self, status=status, version=self.version + 1)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

@dataclass(frozen=True)
class RegionRecord:
    region_id: str
    owner_id: str
    category: str
    status: str = 'draft'
    effective_from: dt.date = field(default_factory=dt.date.today)
    effective_to: dt.date | None = None
    quantity: int = 0
    amount: decimal.Decimal = decimal.Decimal('0.00')
    attributes: Mapping[str, Any] = field(default_factory=dict)
    version: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, 'region_id', require_identifier(self.region_id, 'region_id'))
        object.__setattr__(self, 'owner_id', require_identifier(self.owner_id, 'owner_id'))
        object.__setattr__(self, 'category', require_text(self.category, 'category', 2, 80))
        if self.status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        object.__setattr__(self, 'effective_from', require_date(self.effective_from, 'effective_from'))
        if self.effective_to is not None:
            object.__setattr__(self, 'effective_to', require_date(self.effective_to, 'effective_to'))
            if self.effective_to < self.effective_from:
                raise ContractError('effective_to precedes effective_from')
        object.__setattr__(self, 'quantity', require_integer(self.quantity, 'quantity'))
        object.__setattr__(self, 'amount', require_decimal(self.amount, 'amount'))
        object.__setattr__(self, 'version', require_integer(self.version, 'version'))
        if not isinstance(self.attributes, Mapping):
            raise ContractError('attributes must be mapping')

    @property
    def active_days(self) -> int | None:
        if self.effective_to is None:
            return None
        return (self.effective_to - self.effective_from).days + 1

    def with_status(self, status: str) -> 'RegionRecord':
        if status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        return dataclasses.replace(self, status=status, version=self.version + 1)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    owner_id: str
    category: str
    status: str = 'draft'
    effective_from: dt.date = field(default_factory=dt.date.today)
    effective_to: dt.date | None = None
    quantity: int = 0
    amount: decimal.Decimal = decimal.Decimal('0.00')
    attributes: Mapping[str, Any] = field(default_factory=dict)
    version: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, 'skill_id', require_identifier(self.skill_id, 'skill_id'))
        object.__setattr__(self, 'owner_id', require_identifier(self.owner_id, 'owner_id'))
        object.__setattr__(self, 'category', require_text(self.category, 'category', 2, 80))
        if self.status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        object.__setattr__(self, 'effective_from', require_date(self.effective_from, 'effective_from'))
        if self.effective_to is not None:
            object.__setattr__(self, 'effective_to', require_date(self.effective_to, 'effective_to'))
            if self.effective_to < self.effective_from:
                raise ContractError('effective_to precedes effective_from')
        object.__setattr__(self, 'quantity', require_integer(self.quantity, 'quantity'))
        object.__setattr__(self, 'amount', require_decimal(self.amount, 'amount'))
        object.__setattr__(self, 'version', require_integer(self.version, 'version'))
        if not isinstance(self.attributes, Mapping):
            raise ContractError('attributes must be mapping')

    @property
    def active_days(self) -> int | None:
        if self.effective_to is None:
            return None
        return (self.effective_to - self.effective_from).days + 1

    def with_status(self, status: str) -> 'SkillRecord':
        if status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        return dataclasses.replace(self, status=status, version=self.version + 1)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

@dataclass(frozen=True)
class JobRecord:
    job_id: str
    owner_id: str
    category: str
    status: str = 'draft'
    effective_from: dt.date = field(default_factory=dt.date.today)
    effective_to: dt.date | None = None
    quantity: int = 0
    amount: decimal.Decimal = decimal.Decimal('0.00')
    attributes: Mapping[str, Any] = field(default_factory=dict)
    version: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, 'job_id', require_identifier(self.job_id, 'job_id'))
        object.__setattr__(self, 'owner_id', require_identifier(self.owner_id, 'owner_id'))
        object.__setattr__(self, 'category', require_text(self.category, 'category', 2, 80))
        if self.status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        object.__setattr__(self, 'effective_from', require_date(self.effective_from, 'effective_from'))
        if self.effective_to is not None:
            object.__setattr__(self, 'effective_to', require_date(self.effective_to, 'effective_to'))
            if self.effective_to < self.effective_from:
                raise ContractError('effective_to precedes effective_from')
        object.__setattr__(self, 'quantity', require_integer(self.quantity, 'quantity'))
        object.__setattr__(self, 'amount', require_decimal(self.amount, 'amount'))
        object.__setattr__(self, 'version', require_integer(self.version, 'version'))
        if not isinstance(self.attributes, Mapping):
            raise ContractError('attributes must be mapping')

    @property
    def active_days(self) -> int | None:
        if self.effective_to is None:
            return None
        return (self.effective_to - self.effective_from).days + 1

    def with_status(self, status: str) -> 'JobRecord':
        if status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        return dataclasses.replace(self, status=status, version=self.version + 1)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

@dataclass(frozen=True)
class SeekerRecord:
    seeker_id: str
    owner_id: str
    category: str
    status: str = 'draft'
    effective_from: dt.date = field(default_factory=dt.date.today)
    effective_to: dt.date | None = None
    quantity: int = 0
    amount: decimal.Decimal = decimal.Decimal('0.00')
    attributes: Mapping[str, Any] = field(default_factory=dict)
    version: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, 'seeker_id', require_identifier(self.seeker_id, 'seeker_id'))
        object.__setattr__(self, 'owner_id', require_identifier(self.owner_id, 'owner_id'))
        object.__setattr__(self, 'category', require_text(self.category, 'category', 2, 80))
        if self.status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        object.__setattr__(self, 'effective_from', require_date(self.effective_from, 'effective_from'))
        if self.effective_to is not None:
            object.__setattr__(self, 'effective_to', require_date(self.effective_to, 'effective_to'))
            if self.effective_to < self.effective_from:
                raise ContractError('effective_to precedes effective_from')
        object.__setattr__(self, 'quantity', require_integer(self.quantity, 'quantity'))
        object.__setattr__(self, 'amount', require_decimal(self.amount, 'amount'))
        object.__setattr__(self, 'version', require_integer(self.version, 'version'))
        if not isinstance(self.attributes, Mapping):
            raise ContractError('attributes must be mapping')

    @property
    def active_days(self) -> int | None:
        if self.effective_to is None:
            return None
        return (self.effective_to - self.effective_from).days + 1

    def with_status(self, status: str) -> 'SeekerRecord':
        if status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        return dataclasses.replace(self, status=status, version=self.version + 1)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

@dataclass(frozen=True)
class TrainingRecord:
    training_id: str
    owner_id: str
    category: str
    status: str = 'draft'
    effective_from: dt.date = field(default_factory=dt.date.today)
    effective_to: dt.date | None = None
    quantity: int = 0
    amount: decimal.Decimal = decimal.Decimal('0.00')
    attributes: Mapping[str, Any] = field(default_factory=dict)
    version: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, 'training_id', require_identifier(self.training_id, 'training_id'))
        object.__setattr__(self, 'owner_id', require_identifier(self.owner_id, 'owner_id'))
        object.__setattr__(self, 'category', require_text(self.category, 'category', 2, 80))
        if self.status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        object.__setattr__(self, 'effective_from', require_date(self.effective_from, 'effective_from'))
        if self.effective_to is not None:
            object.__setattr__(self, 'effective_to', require_date(self.effective_to, 'effective_to'))
            if self.effective_to < self.effective_from:
                raise ContractError('effective_to precedes effective_from')
        object.__setattr__(self, 'quantity', require_integer(self.quantity, 'quantity'))
        object.__setattr__(self, 'amount', require_decimal(self.amount, 'amount'))
        object.__setattr__(self, 'version', require_integer(self.version, 'version'))
        if not isinstance(self.attributes, Mapping):
            raise ContractError('attributes must be mapping')

    @property
    def active_days(self) -> int | None:
        if self.effective_to is None:
            return None
        return (self.effective_to - self.effective_from).days + 1

    def with_status(self, status: str) -> 'TrainingRecord':
        if status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        return dataclasses.replace(self, status=status, version=self.version + 1)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

@dataclass(frozen=True)
class IntentRecord:
    intent_id: str
    owner_id: str
    category: str
    status: str = 'draft'
    effective_from: dt.date = field(default_factory=dt.date.today)
    effective_to: dt.date | None = None
    quantity: int = 0
    amount: decimal.Decimal = decimal.Decimal('0.00')
    attributes: Mapping[str, Any] = field(default_factory=dict)
    version: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, 'intent_id', require_identifier(self.intent_id, 'intent_id'))
        object.__setattr__(self, 'owner_id', require_identifier(self.owner_id, 'owner_id'))
        object.__setattr__(self, 'category', require_text(self.category, 'category', 2, 80))
        if self.status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        object.__setattr__(self, 'effective_from', require_date(self.effective_from, 'effective_from'))
        if self.effective_to is not None:
            object.__setattr__(self, 'effective_to', require_date(self.effective_to, 'effective_to'))
            if self.effective_to < self.effective_from:
                raise ContractError('effective_to precedes effective_from')
        object.__setattr__(self, 'quantity', require_integer(self.quantity, 'quantity'))
        object.__setattr__(self, 'amount', require_decimal(self.amount, 'amount'))
        object.__setattr__(self, 'version', require_integer(self.version, 'version'))
        if not isinstance(self.attributes, Mapping):
            raise ContractError('attributes must be mapping')

    @property
    def active_days(self) -> int | None:
        if self.effective_to is None:
            return None
        return (self.effective_to - self.effective_from).days + 1

    def with_status(self, status: str) -> 'IntentRecord':
        if status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        return dataclasses.replace(self, status=status, version=self.version + 1)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

@dataclass(frozen=True)
class SnapshotRecord:
    snapshot_id: str
    owner_id: str
    category: str
    status: str = 'draft'
    effective_from: dt.date = field(default_factory=dt.date.today)
    effective_to: dt.date | None = None
    quantity: int = 0
    amount: decimal.Decimal = decimal.Decimal('0.00')
    attributes: Mapping[str, Any] = field(default_factory=dict)
    version: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, 'snapshot_id', require_identifier(self.snapshot_id, 'snapshot_id'))
        object.__setattr__(self, 'owner_id', require_identifier(self.owner_id, 'owner_id'))
        object.__setattr__(self, 'category', require_text(self.category, 'category', 2, 80))
        if self.status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        object.__setattr__(self, 'effective_from', require_date(self.effective_from, 'effective_from'))
        if self.effective_to is not None:
            object.__setattr__(self, 'effective_to', require_date(self.effective_to, 'effective_to'))
            if self.effective_to < self.effective_from:
                raise ContractError('effective_to precedes effective_from')
        object.__setattr__(self, 'quantity', require_integer(self.quantity, 'quantity'))
        object.__setattr__(self, 'amount', require_decimal(self.amount, 'amount'))
        object.__setattr__(self, 'version', require_integer(self.version, 'version'))
        if not isinstance(self.attributes, Mapping):
            raise ContractError('attributes must be mapping')

    @property
    def active_days(self) -> int | None:
        if self.effective_to is None:
            return None
        return (self.effective_to - self.effective_from).days + 1

    def with_status(self, status: str) -> 'SnapshotRecord':
        if status not in {item.value for item in State}:
            raise ContractError('unsupported status')
        return dataclasses.replace(self, status=status, version=self.version + 1)

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

RECORD_TYPES = {
    'industry': IndustryRecord,
    'region': RegionRecord,
    'skill': SkillRecord,
    'job': JobRecord,
    'seeker': SeekerRecord,
    'training': TrainingRecord,
    'intent': IntentRecord,
    'snapshot': SnapshotRecord,
}

def build_record(kind: str, values: Mapping[str, Any]) -> Any:
    try:
        record_type = RECORD_TYPES[kind]
    except KeyError as exc:
        raise ContractError(f'unknown record kind: {kind}') from exc
    return record_type(**dict(values))

def stable_ids(records: Iterable[Any]) -> tuple[str, ...]:
    result = []
    for record in records:
        first = next(iter(dataclasses.asdict(record).values()))
        result.append(str(first))
    return tuple(sorted(result))
