from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from typing import Any, Iterable, Mapping

_UTC = dt.timezone.utc
_EPOCH = dt.datetime.min.replace(tzinfo=_UTC)

# Fields the mart adds itself.  They must not take part in revision
# fingerprints, otherwise a fact re-read from a published snapshot would look
# like a different fact from the raw row it came from.
_DERIVED = frozenset({'industry_key', 'region_key', 'is_current', 'revision_status', 'late',
                      'revision_count', 'superseded_count', 'supersedes', 'from_snapshot'})
# Arrival / revision bookkeeping.  It may change on a redelivery of the same
# business fact, so it must not decide whether two rows are duplicates.
_ARRIVAL = frozenset({'received_at', 'received', 'ingested_at', 'delivered_at', 'recorded_at',
                      'arrival_time', 'revision', 'revision_number', 'version'})
_ARRIVAL_FIELDS = ('received_at', 'received', 'ingested_at', 'delivered_at', 'recorded_at', 'arrival_time')
_HISTORICAL_STATUSES = frozenset({'historical', 'historical_snapshot', 'snapshot', 'published_history'})
# Statuses carried by revision-trace rows (see ``ingest``).  Such rows are
# evidence of what happened, never inputs to an aggregate.
_TRACE_STATUSES = frozenset({'superseded', 'historical_snapshot', 'duplicate', 'rejected_invalid_dimension'})
_INVALID_MARKERS = frozenset({'invalid', 'rejected', 'failed', 'quarantined'})


def _digest(row: Mapping[str, Any], excluded: frozenset[str]) -> str:
    payload = json.dumps({key: value for key, value in row.items() if key not in excluded},
                         ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _fingerprint(row: Mapping[str, Any]) -> str:
    """Exact record digest used to make a revision trace auditable."""
    return _digest(row, _DERIVED)


def _content_fingerprint(row: Mapping[str, Any]) -> str:
    """Business-content digest used to recognise repeated input."""
    return _digest(row, _DERIVED | _ARRIVAL)


class TalentMart:
    """Fact mart for the industry/job observatory.

    A recruitment source may send more than one record for the same source
    identity (``source`` + ``source_key``).  Only the effective revision is a
    current fact; every older revision is retained in the trace but never
    added to an aggregate.  Correcting a quantity therefore changes the
    industry / region / business-date aggregates instead of leaving the first
    delivered quantity in the gap metric.
    """

    CURRENT = 'current'
    LATE_REVISION = 'late_revision'
    CARRIED_FORWARD = 'carried_forward'
    SUPERSEDED = 'superseded'
    HISTORICAL_SNAPSHOT = 'historical_snapshot'
    DUPLICATE = 'duplicate'
    REJECTED = 'rejected_invalid_dimension'

    # ------------------------------------------------------------------
    # dimensions
    # ------------------------------------------------------------------
    def resolve_dimension(self, code, day, versions):
        try:
            date = dt.date.fromisoformat(str(day))
        except (TypeError, ValueError) as exc:
            raise ValueError('dimension_resolution_invalid_date') from exc
        matches = []
        for row in versions:
            if str(row['code']) != str(code):
                continue
            start = dt.date.fromisoformat(str(row['valid_from']))
            end = dt.date.fromisoformat(str(row['valid_to'])) if row.get('valid_to') else None
            if start <= date and (end is None or date <= end):
                matches.append(row)
        if len(matches) != 1:
            raise ValueError('dimension_resolution_' + ('missing' if not matches else 'ambiguous'))
        return str(matches[0]['surrogate_key'])

    # ------------------------------------------------------------------
    # revision identity / ordering helpers
    # ------------------------------------------------------------------
    def identity(self, row: Mapping[str, Any]) -> tuple[str, str] | None:
        """Return the source identity whose revisions supersede one another."""
        source = row.get('source')
        key = row.get('source_key')
        if key in (None, ''):
            key = row.get('natural_key')
        if key in (None, ''):
            return None
        return (str(source if source is not None else ''), str(key))

    def _arrival(self, row: Mapping[str, Any]) -> Any:
        for field in _ARRIVAL_FIELDS:
            value = row.get(field)
            if value not in (None, ''):
                return value
        return None

    def _moment(self, value: Any) -> dt.datetime:
        if value in (None, ''):
            return _EPOCH
        if isinstance(value, dt.datetime):
            moment = value
        elif isinstance(value, dt.date):
            moment = dt.datetime.combine(value, dt.time.min)
        else:
            text = str(value).strip()
            try:
                moment = dt.datetime.fromisoformat(text.replace('Z', '+00:00'))
            except ValueError:
                # An unparsable arrival stamp must not look newer than a real one.
                return _EPOCH
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=_UTC)
        return moment.astimezone(_UTC)

    def _revision_number(self, row: Mapping[str, Any]) -> int | None:
        for field in ('revision', 'revision_number', 'version'):
            value = row.get(field)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return None

    def _event_date(self, row: Mapping[str, Any]) -> dt.date | None:
        value = row.get('event_date')
        if isinstance(value, dt.datetime):
            return value.date()
        if isinstance(value, dt.date):
            return value
        if value in (None, ''):
            return None
        try:
            return dt.date.fromisoformat(str(value))
        except ValueError:
            return None

    def _order_key(self, row: Mapping[str, Any], position: int, origin: int = 1) -> tuple:
        """Arrival ordering, *not* business-date ordering.

        A correction can legitimately describe an earlier business date than
        the fact it replaces, so revisions are ordered by explicit source
        revision number, then arrival time, then delivery order.  Business
        dates only decide which aggregate buckets are rewritten afterwards.
        """
        revision = self._revision_number(row)
        revision_rank = -1 if revision is None else revision
        # ``origin`` (an already published fact vs a newly delivered one)
        # outranks a missing or coarse arrival stamp: a fresh delivery is the
        # later observation by construction. Within one delivery batch,
        # ``received_at`` then row position decide.
        return (revision_rank, origin, self._moment(self._arrival(row)), position)

    def revision_order(self, row: Mapping[str, Any], position: int = 0, origin: int = 1) -> tuple:
        """Public arrival-order key for callers merging their own revisions.

        ``origin`` is 0 for a fact that was already published and 1 for a
        newly delivered one, so a fresh delivery always outranks the stored
        fact it might replace.
        """
        return self._order_key(dict(row), position, origin)

    def content_fingerprint(self, row: Mapping[str, Any]) -> str:
        """Digest of the business content, used to recognise repeated input."""
        return _content_fingerprint(row)

    def is_historical(self, row: Mapping[str, Any]) -> bool:
        """True when a row is explicitly a fact from an earlier publication.

        ``from_snapshot`` alone is *not* historical: it marks a fact that is
        still current but was carried over from the previously published
        snapshot.
        """
        if row.get('is_current') is False:
            return True
        return str(row.get('revision_status') or row.get('record_status') or '').lower() in _HISTORICAL_STATUSES

    # ------------------------------------------------------------------
    # ingestion
    # ------------------------------------------------------------------
    def _enrich(self, row: Mapping[str, Any], dimensions: Mapping[str, Any]) -> dict[str, Any]:
        enriched = dict(row)
        # Pre-enriched facts may carry only the surrogate key.  Re-resolve
        # whenever the source code is present so a corrected dimension wins.
        if row.get('industry_code') not in (None, ''):
            enriched['industry_key'] = self.resolve_dimension(
                str(row['industry_code']), row.get('event_date'), dimensions.get('industry', ()))
        elif not row.get('industry_key'):
            raise ValueError('dimension_resolution_missing')
        if row.get('region_code') not in (None, ''):
            enriched['region_key'] = self.resolve_dimension(
                str(row['region_code']), row.get('event_date'), dimensions.get('region', ()))
        elif not row.get('region_key'):
            raise ValueError('dimension_resolution_missing')
        return enriched

    def _summary(self, row: Mapping[str, Any], status: str, reason: str | None = None, **extra: Any) -> dict[str, Any]:
        summary = {
            'source': str(row.get('source', '')),
            'source_key': str(row.get('source_key', row.get('natural_key', ''))),
            'event_date': row.get('event_date'),
            'received_at': self._arrival(row),
            'revision': self._revision_number(row),
            'fingerprint': _fingerprint(row),
            'content_fingerprint': _content_fingerprint(row),
            'status': status,
        }
        if reason is not None:
            summary['reason'] = reason
        summary.update(extra)
        return summary

    def ingest(self, facts, dimensions, prior=None):
        """Resolve source revisions into traceable current facts.

        ``accepted`` keeps its historical shape: the enriched current facts in
        business-date order.  The other keys make the revision decision
        explainable:

        * ``superseded``          - older valid revisions replaced by a newer one;
        * ``historical_snapshot`` - facts from a previously published snapshot
                                    replaced by this delivery;
        * ``duplicates``          - repeated input that adds no new fact;
        * ``rejected``            - records whose dimension cannot be resolved
                                    (they never override a valid current fact);
        * ``late_revisions``      - current facts whose business date precedes
                                    the revision they replace (back-dated fix);
        * ``trace``               - per source identity history. The ``prior``
                                    argument carries already published facts so
                                    an incremental delivery can be merged
                                    without recounting them.
        """
        entries: list[dict[str, Any]] = []

        def add(row: Mapping[str, Any], origin: int, position: int) -> None:
            entry = {
                'position': position,
                'origin': origin,
                'row': dict(row),
                'identity': self.identity(row),
                'fingerprint': _fingerprint(row),
                'content': _content_fingerprint(row),
                'valid': False,
                'enriched': None,
                'reason': None,
            }
            if origin == 1 and self.is_historical(row):
                # A newly delivered row explicitly marked as history is trace
                # only.  ``prior`` rows are, by definition, the published facts
                # we are merging into, so they stay current.
                entry['historical'] = True
                entry['reason'] = 'historical snapshot row'
            elif str(row.get('revision_status') or '').lower() in _TRACE_STATUSES:
                entry['historical'] = True
                entry['reason'] = 'revision trace row'
            elif origin == 1 and (str(row.get('quality', '')).lower() in _INVALID_MARKERS or row.get('valid') is False):
                entry['reason'] = 'row_marked_invalid'
            else:
                try:
                    entry['enriched'] = self._enrich(row, dimensions)
                    entry['valid'] = True
                except ValueError as exc:
                    entry['reason'] = str(exc)
            entries.append(entry)

        for position, row in enumerate(prior or ()):
            add(row, 0, position)
        offset = len(entries)
        for position, row in enumerate(facts):
            add(row, 1, offset + position)

        groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        loose: list[dict[str, Any]] = []
        for entry in entries:
            if entry['identity'] is None:
                loose.append(entry)
            else:
                groups[entry['identity']].append(entry)

        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        superseded: list[dict[str, Any]] = []
        historical: list[dict[str, Any]] = []
        duplicates: list[dict[str, Any]] = []
        late_revisions: list[dict[str, Any]] = []
        trace: dict[str, dict[str, Any]] = {}

        # Unkeyed rows still represent distinct facts, but exact repeated
        # input is a duplicate rather than a second fact.
        seen_loose: set[str] = set()
        for entry in loose:
            if entry['content'] in seen_loose:
                duplicates.append(self._summary(entry['row'], self.DUPLICATE, 'duplicate input'))
                continue
            seen_loose.add(entry['content'])
            if entry.get('historical'):
                historical.append(self._summary(entry['row'], self.HISTORICAL_SNAPSHOT, entry['reason']))
            elif entry['valid']:
                accepted.append(self._current_row(entry, self.CURRENT, False, 1, 0, ()))
            else:
                rejected.append(self._summary(entry['row'], self.REJECTED, entry['reason'], would_supersede=False))

        for identity, group in groups.items():
            valid = [entry for entry in group if entry['valid'] and not entry.get('historical')]
            history = [entry for entry in group if entry.get('historical')]
            invalid = [entry for entry in group if not entry['valid'] and not entry.get('historical')]

            # Walk the arrivals in order and collapse a re-delivery only when
            # it repeats the content that is already in effect.  A later row
            # that *reverts* to older content is a real revision, so content
            # equality on its own must never discard it.
            timeline: list[dict[str, Any]] = []
            repeated: list[dict[str, Any]] = []
            for entry in sorted(valid, key=lambda item: self._order_key(item['row'], item['position'], item['origin'])):
                if timeline and entry['content'] == timeline[-1]['content']:
                    if entry['origin'] == 1:
                        repeated.append(entry)
                    continue
                timeline.append(entry)
            candidates = timeline
            effective = candidates[-1] if candidates else None
            replaced = candidates[:-1]

            replaced_dates = [date for date in (self._event_date(entry['row']) for entry in replaced + history) if date]
            effective_date = self._event_date(effective['row']) if effective else None
            is_late = bool(effective is not None and effective_date is not None
                           and replaced_dates and effective_date < max(replaced_dates))
            from_prior = bool(effective is not None and effective['origin'] == 0)

            identity_text = f'{identity[0]}|{identity[1]}'
            trace_entry: dict[str, Any] = {
                'source': identity[0],
                'source_key': identity[1],
                'status': None,
                'revision_count': len(candidates),
                'current': None,
                'superseded': [],
                'historical_snapshot': [],
                'rejected': [],
                'duplicates': [],
            }

            if effective is not None:
                status = self.CARRIED_FORWARD if from_prior else (self.LATE_REVISION if is_late else self.CURRENT)
                accepted.append(self._current_row(effective, status, is_late, len(candidates), len(replaced), tuple(
                    self._summary(entry['row'], self.SUPERSEDED) for entry in replaced)))
                trace_entry['status'] = status
                trace_entry['current'] = {
                    'event_date': effective['row'].get('event_date'),
                    'received_at': self._arrival(effective['row']),
                    'revision': self._revision_number(effective['row']),
                    'fingerprint': effective['fingerprint'],
                    'status': status,
                    'from_snapshot': from_prior,
                }
                if is_late and not from_prior:
                    late_revisions.append(trace_entry['current'] | {'source': identity[0], 'source_key': identity[1]})
            elif invalid:
                trace_entry['status'] = self.REJECTED
            elif history:
                # Every current delivery for this identity was history only.
                trace_entry['status'] = self.HISTORICAL_SNAPSHOT

            for entry in replaced:
                # A fact that came from an already published snapshot is a
                # historical fact, distinct from a late revision that is only
                # now arriving from the source.
                if entry['origin'] == 0:
                    summary = self._summary(entry['row'], self.HISTORICAL_SNAPSHOT,
                                            'replaced by a newer published revision')
                    historical.append(summary)
                    trace_entry['historical_snapshot'].append(summary)
                else:
                    summary = self._summary(entry['row'], self.SUPERSEDED, 'superseded by a later revision')
                    superseded.append(summary)
                    trace_entry['superseded'].append(summary)

            for entry in history:
                summary = self._summary(entry['row'], self.HISTORICAL_SNAPSHOT, 'replaced by a newer published revision')
                historical.append(summary)
                trace_entry['historical_snapshot'].append(summary)

            for entry in repeated:
                summary = self._summary(entry['row'], self.DUPLICATE, 'duplicate input')
                duplicates.append(summary)
                trace_entry['duplicates'].append(summary)

            for entry in invalid:
                would_supersede = bool(
                    effective is not None
                    and self._order_key(entry['row'], entry['position'], entry['origin'])
                    > self._order_key(effective['row'], effective['position'], effective['origin']))
                summary = self._summary(entry['row'], self.REJECTED, entry['reason'], would_supersede=would_supersede)
                rejected.append(summary)
                trace_entry['rejected'].append(summary)

            if trace_entry['current'] is None and not trace_entry['rejected'] and not trace_entry['historical_snapshot']:
                # Every delivery for this identity was a repeat of an already
                # published fact; there is nothing new to aggregate.
                trace_entry['status'] = self.DUPLICATE
            trace[identity_text] = trace_entry

        accepted.sort(key=lambda row: (str(row.get('event_date')), str(row.get('source_key'))))
        return {
            'accepted': accepted,
            'rejected': rejected,
            'superseded': superseded,
            'historical_snapshot': historical,
            'duplicates': duplicates,
            'late_revisions': late_revisions,
            'trace': trace,
            'statistics': {
                'input': len(entries),
                'accepted': len(accepted),
                'superseded': len(superseded),
                'historical_snapshot': len(historical),
                'duplicates': len(duplicates),
                'rejected': len(rejected),
                'late_revisions': len(late_revisions),
            },
        }

    def _current_row(self, entry: Mapping[str, Any], status: str, late: bool,
                     revision_count: int, superseded_count: int, supersedes: tuple) -> dict[str, Any]:
        chosen = dict(entry['enriched'])
        chosen['is_current'] = True
        chosen['revision_status'] = status
        chosen['late'] = late
        chosen['revision_count'] = revision_count
        chosen['superseded_count'] = superseded_count
        chosen['supersedes'] = supersedes
        chosen['from_snapshot'] = entry['origin'] == 0
        return chosen

    def current_facts(self, facts, dimensions, prior=None) -> list[Mapping[str, Any]]:
        """Return only the effective current facts (no superseded history)."""
        return list(self.ingest(facts, dimensions, prior)['accepted'])

    def select_current(self, facts, prior=None) -> list[Mapping[str, Any]]:
        """Pick the effective revision per source identity without dimensions.

        Useful for callers that already hold validated/enriched facts but
        still need to drop superseded and repeated deliveries before summing.
        """
        return list(self._current_rows(facts, None, prior))

    # ------------------------------------------------------------------
    # aggregation
    # ------------------------------------------------------------------
    def gap_metric(self, facts, grain, dimensions=None, prior=None):
        """Aggregate current facts into the regional supply/demand gap.

        ``openings`` (demand) minus ``seekers`` (supply) is computed from
        effective revisions only.  ``grain`` is the industry / region / time
        dimension combination to report on.
        """
        return self.aggregate(facts, grain, dimensions, prior)

    def _current_rows(self, facts: Iterable[Mapping[str, Any]],
                      dimensions: Mapping[str, Any] | None = None,
                      prior: Iterable[Mapping[str, Any]] | None = None) -> list[Mapping[str, Any]]:
        if dimensions is not None:
            return list(self.ingest(facts, dimensions, prior)['accepted'])

        def usable(row: Mapping[str, Any]) -> bool:
            return (not self.is_historical(row)
                    and str(row.get('revision_status') or '').lower() not in _TRACE_STATUSES
                    and str(row.get('quality', '')).lower() not in _INVALID_MARKERS
                    and row.get('valid') is not False)

        entries: list[tuple[int, int, Mapping[str, Any]]] = []
        for position, row in enumerate(prior or ()):
            if usable(row):
                entries.append((0, position, row))
        offset = len(entries)
        for position, row in enumerate(facts):
            if usable(row):
                entries.append((1, offset + position, row))

        groups: dict[tuple[str, str], list[tuple[int, int, Mapping[str, Any]]]] = defaultdict(list)
        loose: list[tuple[int, int, Mapping[str, Any]]] = []
        for origin, position, row in entries:
            identity = self.identity(row)
            if identity is None:
                loose.append((origin, position, row))
            else:
                groups[identity].append((origin, position, row))

        selected: list[tuple[int, Mapping[str, Any]]] = []
        for values in groups.values():
            ordered = sorted(values, key=lambda item: self._order_key(item[2], item[1], item[0]))
            effective = ordered[-1]
            selected.append((effective[1], effective[2]))
        seen: set[str] = set()
        for origin, position, row in loose:
            digest = _content_fingerprint(row)
            if digest in seen:
                continue
            seen.add(digest)
            selected.append((position, row))
        selected.sort(key=lambda item: item[0])
        return [row for _, row in selected]

    def aggregate(self, facts, grain, dimensions=None, prior=None):
        """Aggregate current facts only.

        Revision selection happens here as well as in :meth:`ingest`, so a
        caller that re-sends the same input (or supplies both an old and a
        corrected row) still counts a source exactly once.  Invalid-dimension
        rows are excluded unless ``dimensions`` is supplied, in which case the
        regular rejection rules apply.
        """
        groups = defaultdict(lambda: {'openings': 0, 'seekers': 0, 'intents': 0,
                                      'salary_sum': Decimal('0'), 'salary_count': 0})
        for row in self._current_rows(facts, dimensions, prior):
            key = tuple(str(row[field]) for field in grain)
            group = groups[key]
            group['openings'] += int(row.get('openings', 0))
            group['seekers'] += int(row.get('seekers', 0))
            group['intents'] += int(row.get('intents', 0))
            if row.get('salary') is not None:
                group['salary_sum'] += Decimal(str(row['salary']))
                group['salary_count'] += 1
        result = []
        for key, value in sorted(groups.items()):
            result.append({
                'key': key,
                'openings': value['openings'],
                'seekers': value['seekers'],
                'intents': value['intents'],
                'gap': value['openings'] - value['seekers'],
                'average_salary': str(value['salary_sum'] / value['salary_count']) if value['salary_count'] else None,
            })
        return result

    def flow_matrix(self, facts):
        matrix = defaultdict(int)
        for row in self._current_rows(facts):
            if row.get('origin_region') and row.get('target_region'):
                matrix[(str(row['origin_region']), str(row['target_region']))] += int(row.get('people', 1))
        return [{'origin': key[0], 'target': key[1], 'people': value} for key, value in sorted(matrix.items())]

    def recompute_delta(self, old, new):
        """Return only affected aggregate groups (existing contract).

        Untouched regions are deliberately absent from the change list and
        keep their prior result; they are never recomputed into a different
        value just because another region received a revision.  Use
        :meth:`change_list` when the operation and changed measures are needed.
        """
        return [{'key': change['key'], 'before': change['before'], 'after': change['after']}
                for change in self.change_list(old, new)]

    def change_list(self, old, new):
        """Explainable change list: operation, before/after and changed fields."""
        def index(rows):
            return {tuple(row['key']): row for row in rows}

        left, right = index(old), index(new)
        changes = []
        for key in sorted(set(left) | set(right), key=str):
            before = left.get(key)
            after = right.get(key)
            if before == after:
                continue
            change = {'key': key, 'before': before, 'after': after}
            if before is None:
                change['change'] = 'added'
                change['changed_fields'] = tuple(sorted(after))
            elif after is None:
                change['change'] = 'removed'
                change['changed_fields'] = tuple(sorted(before))
            else:
                change['change'] = 'updated'
                change['changed_fields'] = tuple(sorted(field for field in set(before) | set(after)
                                                        if field != 'key' and before.get(field) != after.get(field)))
            changes.append(change)
        return changes

    def change_manifest(self, before_facts, after_facts, grain, dimensions=None):
        """End-to-end trace: raw facts -> gap metric -> affected change list."""
        before = self.aggregate(before_facts, grain, dimensions)
        after = self.aggregate(after_facts, grain, dimensions)
        changes = self.change_list(before, after)
        manifest = {
            'grain': tuple(grain),
            'before': before,
            'after': after,
            'changes': changes,
            'changed_keys': tuple(change['key'] for change in changes),
            'unchanged_keys': tuple(key for key in (row['key'] for row in before)
                                    if key in {row['key'] for row in after}
                                    and key not in {change['key'] for change in changes}),
        }
        if dimensions is not None:
            resolved = self.ingest(after_facts, dimensions)
            manifest['revisions'] = {
                'statistics': resolved['statistics'],
                'current': [(row.get('source'), row.get('source_key'), row.get('event_date'),
                             row.get('revision_status')) for row in resolved['accepted']],
                'late_revisions': resolved['late_revisions'],
                'superseded': resolved['superseded'],
                'historical_snapshot': resolved['historical_snapshot'],
                'duplicates': resolved['duplicates'],
                'rejected': resolved['rejected'],
            }
        return manifest
