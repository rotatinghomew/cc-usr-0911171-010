from __future__ import annotations

import contextlib
import datetime as dt
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .contracts import ContractError, Event, canonical_json, require_identifier

class ConflictError(RuntimeError):
    pass

class NotFoundError(LookupError):
    pass

class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._local = threading.local()
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA busy_timeout=30000')
        return connection

    @contextlib.contextmanager
    def transaction(self, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute('BEGIN IMMEDIATE' if immediate else 'BEGIN')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.transaction() as connection:
            connection.executescript('''
            CREATE TABLE IF NOT EXISTS records(
                kind TEXT NOT NULL, record_id TEXT NOT NULL, owner_id TEXT NOT NULL,
                category TEXT NOT NULL, status TEXT NOT NULL, effective_from TEXT NOT NULL,
                effective_to TEXT, quantity INTEGER NOT NULL, amount TEXT NOT NULL,
                attributes_json TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(kind, record_id)
            );
            CREATE INDEX IF NOT EXISTS records_owner ON records(kind, owner_id, status);
            CREATE TABLE IF NOT EXISTS events(
                event_id TEXT PRIMARY KEY, aggregate_type TEXT NOT NULL, aggregate_id TEXT NOT NULL,
                kind TEXT NOT NULL, occurred_at TEXT NOT NULL, payload_json TEXT NOT NULL,
                sequence INTEGER NOT NULL, UNIQUE(aggregate_type, aggregate_id, sequence)
            );
            CREATE TABLE IF NOT EXISTS idempotency(
                scope TEXT NOT NULL, request_key TEXT NOT NULL, request_hash TEXT NOT NULL,
                response_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(scope, request_key)
            );
            CREATE TABLE IF NOT EXISTS outbox(
                message_id TEXT PRIMARY KEY, topic TEXT NOT NULL, aggregate_id TEXT NOT NULL,
                payload_json TEXT NOT NULL, created_at TEXT NOT NULL, delivered_at TEXT, attempts INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS snapshots(
                namespace TEXT NOT NULL, snapshot_id TEXT NOT NULL, version INTEGER NOT NULL,
                content_json TEXT NOT NULL, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(namespace, snapshot_id, version)
            );
            CREATE TABLE IF NOT EXISTS locks(
                resource_type TEXT NOT NULL, resource_id TEXT NOT NULL, holder TEXT NOT NULL,
                expires_at TEXT NOT NULL, PRIMARY KEY(resource_type, resource_id)
            );
            ''')

    def put_record(self, connection: sqlite3.Connection, kind: str, record: Mapping[str, Any], expected_version: int | None = None) -> int:
        record_id = require_identifier(record[f'{kind}_id'], f'{kind}_id')
        row = connection.execute('SELECT version FROM records WHERE kind=? AND record_id=?', (kind, record_id)).fetchone()
        current = row['version'] if row else None
        if expected_version is not None and current != expected_version:
            raise ConflictError(f'expected version {expected_version}, found {current}')
        version = 1 if current is None else current + 1
        connection.execute('''INSERT INTO records(kind,record_id,owner_id,category,status,effective_from,effective_to,quantity,amount,attributes_json,version,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(kind,record_id) DO UPDATE SET owner_id=excluded.owner_id,category=excluded.category,
            status=excluded.status,effective_from=excluded.effective_from,effective_to=excluded.effective_to,quantity=excluded.quantity,
            amount=excluded.amount,attributes_json=excluded.attributes_json,version=excluded.version,updated_at=excluded.updated_at''',
            (kind, record_id, record['owner_id'], record['category'], record.get('status','draft'), str(record['effective_from']),
             str(record.get('effective_to')) if record.get('effective_to') else None, int(record.get('quantity',0)), str(record.get('amount','0.00')),
             canonical_json(record.get('attributes',{})), version, dt.datetime.now(dt.timezone.utc).isoformat()))
        return version

    def get_record(self, kind: str, record_id: str) -> dict[str, Any]:
        with contextlib.closing(self.connect()) as connection:
            row = connection.execute('SELECT * FROM records WHERE kind=? AND record_id=?', (kind, record_id)).fetchone()
        if row is None:
            raise NotFoundError(f'{kind}:{record_id}')
        return self._record(row)

    def list_records(self, kind: str, owner_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        clauses = ['kind=?']
        values: list[Any] = [kind]
        if owner_id is not None:
            clauses.append('owner_id=?')
            values.append(owner_id)
        if status is not None:
            clauses.append('status=?')
            values.append(status)
        sql = 'SELECT * FROM records WHERE ' + ' AND '.join(clauses) + ' ORDER BY record_id'
        with contextlib.closing(self.connect()) as connection:
            rows = connection.execute(sql, values).fetchall()
        return [self._record(row) for row in rows]

    def _record(self, row: sqlite3.Row) -> dict[str, Any]:
        return {'kind': row['kind'], f"{row['kind']}_id": row['record_id'], 'owner_id': row['owner_id'],
                'category': row['category'], 'status': row['status'], 'effective_from': row['effective_from'],
                'effective_to': row['effective_to'], 'quantity': row['quantity'], 'amount': row['amount'],
                'attributes': json.loads(row['attributes_json']), 'version': row['version']} 

    def append_event(self, connection: sqlite3.Connection, event: Event) -> None:
        connection.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?)', (event.event_id,event.aggregate_type,event.aggregate_id,event.kind,
                           event.occurred_at.isoformat(),canonical_json(event.payload),event.sequence))

    def events_for(self, aggregate_type: str, aggregate_id: str) -> list[dict[str, Any]]:
        with contextlib.closing(self.connect()) as connection:
            rows = connection.execute('SELECT * FROM events WHERE aggregate_type=? AND aggregate_id=? ORDER BY sequence',
                                      (aggregate_type, aggregate_id)).fetchall()
        return [dict(row) | {'payload': json.loads(row['payload_json'])} for row in rows]

    def remember(self, connection: sqlite3.Connection, scope: str, key: str, request_hash: str, response: Mapping[str, Any]) -> None:
        row = connection.execute('SELECT request_hash,response_json FROM idempotency WHERE scope=? AND request_key=?',(scope,key)).fetchone()
        if row is not None:
            if row['request_hash'] != request_hash:
                raise ConflictError('idempotency key reused with different request')
            return
        connection.execute('INSERT INTO idempotency VALUES(?,?,?,?,?)',(scope,key,request_hash,canonical_json(response),dt.datetime.now(dt.timezone.utc).isoformat()))

    def recalled(self, scope: str, key: str, request_hash: str) -> dict[str, Any] | None:
        with contextlib.closing(self.connect()) as connection:
            row = connection.execute('SELECT request_hash,response_json FROM idempotency WHERE scope=? AND request_key=?',(scope,key)).fetchone()
        if row is None:
            return None
        if row['request_hash'] != request_hash:
            raise ConflictError('idempotency key reused with different request')
        return json.loads(row['response_json'])

    def enqueue(self, connection: sqlite3.Connection, message_id: str, topic: str, aggregate_id: str, payload: Mapping[str, Any]) -> None:
        connection.execute('INSERT OR IGNORE INTO outbox(message_id,topic,aggregate_id,payload_json,created_at) VALUES(?,?,?,?,?)',
                           (message_id,topic,aggregate_id,canonical_json(payload),dt.datetime.now(dt.timezone.utc).isoformat()))

    def pending_messages(self, limit: int = 100) -> list[dict[str, Any]]:
        with contextlib.closing(self.connect()) as connection:
            rows = connection.execute('SELECT * FROM outbox WHERE delivered_at IS NULL ORDER BY created_at,message_id LIMIT ?', (limit,)).fetchall()
        return [dict(row) | {'payload': json.loads(row['payload_json'])} for row in rows]

    def mark_delivered(self, message_id: str, delivered_at: dt.datetime | None = None) -> None:
        moment = (delivered_at or dt.datetime.now(dt.timezone.utc)).isoformat()
        with self.transaction() as connection:
            changed = connection.execute('UPDATE outbox SET delivered_at=?,attempts=attempts+1 WHERE message_id=? AND delivered_at IS NULL',(moment,message_id)).rowcount
            if not changed:
                raise NotFoundError(message_id)

    def save_snapshot(self, namespace: str, snapshot_id: str, content: Mapping[str, Any], fingerprint: str) -> int:
        with self.transaction() as connection:
            row = connection.execute('SELECT COALESCE(MAX(version),0) AS version FROM snapshots WHERE namespace=? AND snapshot_id=?',(namespace,snapshot_id)).fetchone()
            version = int(row['version']) + 1
            connection.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?)',(namespace,snapshot_id,version,canonical_json(content),fingerprint,dt.datetime.now(dt.timezone.utc).isoformat()))
        return version

    def load_snapshot(self, namespace: str, snapshot_id: str, version: int | None = None) -> dict[str, Any]:
        with self.connect() as connection:
            if version is None:
                row = connection.execute('SELECT * FROM snapshots WHERE namespace=? AND snapshot_id=? ORDER BY version DESC LIMIT 1',(namespace,snapshot_id)).fetchone()
            else:
                row = connection.execute('SELECT * FROM snapshots WHERE namespace=? AND snapshot_id=? AND version=?',(namespace,snapshot_id,version)).fetchone()
        if row is None:
            raise NotFoundError(snapshot_id)
        return dict(row) | {'content': json.loads(row['content_json'])}

    def acquire_lock(self, resource_type: str, resource_id: str, holder: str, expires_at: dt.datetime) -> bool:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        with self.transaction() as connection:
            connection.execute('DELETE FROM locks WHERE expires_at<=?',(now,))
            try:
                connection.execute('INSERT INTO locks VALUES(?,?,?,?)',(resource_type,resource_id,holder,expires_at.isoformat()))
                return True
            except sqlite3.IntegrityError:
                return False

    def release_lock(self, resource_type: str, resource_id: str, holder: str) -> bool:
        with self.transaction() as connection:
            return bool(connection.execute('DELETE FROM locks WHERE resource_type=? AND resource_id=? AND holder=?',(resource_type,resource_id,holder)).rowcount)

    def counts(self) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute('SELECT kind,COUNT(*) AS count FROM records GROUP BY kind').fetchall()
        return {row['kind']: row['count'] for row in rows}

    def list_industrys(self, owner_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        return self.list_records('industry', owner_id=owner_id, status=status)

    def list_regions(self, owner_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        return self.list_records('region', owner_id=owner_id, status=status)

    def list_skills(self, owner_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        return self.list_records('skill', owner_id=owner_id, status=status)

    def list_jobs(self, owner_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        return self.list_records('job', owner_id=owner_id, status=status)

    def list_seekers(self, owner_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        return self.list_records('seeker', owner_id=owner_id, status=status)

    def list_trainings(self, owner_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        return self.list_records('training', owner_id=owner_id, status=status)

    def list_intents(self, owner_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        return self.list_records('intent', owner_id=owner_id, status=status)

    def list_snapshots(self, owner_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        return self.list_records('snapshot', owner_id=owner_id, status=status)

