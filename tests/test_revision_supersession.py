import unittest

from talent_observatory.dimensional_model.mart import TalentMart


DIMENSIONS = {
    'industry': [
        {'code': 'ai', 'surrogate_key': 'i1', 'valid_from': '2026-01-01'},
        {'code': 'mk', 'surrogate_key': 'i2', 'valid_from': '2026-01-01'},
    ],
    'region': [
        {'code': 'sy', 'surrogate_key': 'r1', 'valid_from': '2026-01-01'},
        {'code': 'dl', 'surrogate_key': 'r2', 'valid_from': '2026-01-01'},
    ],
}


def fact(source_key='1', **changes):
    row = {
        'source': 'jobs',
        'source_key': source_key,
        'industry_code': 'ai',
        'region_code': 'sy',
        'event_date': '2026-11-16',
        'openings': 10,
        'seekers': 4,
        'salary': 10000,
        'received_at': '2026-11-16T09:00:00+00:00',
    }
    row.update(changes)
    return row


class RevisionInjectionTests(unittest.TestCase):
    """Same source identity, different arrival order and business dates."""

    def setUp(self):
        self.mart = TalentMart()

    def test_first_delivered_quantity_is_not_retained(self):
        original = fact(openings=10)
        correction = fact(openings=6, event_date='2026-11-15',
                          received_at='2026-11-17T09:00:00+00:00')
        result = self.mart.ingest([original, correction], DIMENSIONS)
        self.assertEqual(len(result['accepted']), 1)
        self.assertEqual(result['accepted'][0]['openings'], 6)
        self.assertEqual(result['accepted'][0]['event_date'], '2026-11-15')

    def test_arrival_order_does_not_override_later_revision(self):
        original = fact(openings=10, received_at='2026-11-16T09:00:00+00:00')
        correction = fact(openings=6, received_at='2026-11-17T09:00:00+00:00')
        forward = self.mart.ingest([original, correction], DIMENSIONS)['accepted']
        reverse = self.mart.ingest([correction, original], DIMENSIONS)['accepted']
        self.assertEqual([row['openings'] for row in forward], [6])
        self.assertEqual([row['openings'] for row in reverse], [6])

    def test_explicit_revision_number_wins_over_arrival_time(self):
        original = fact(openings=10, revision=1, received_at='2026-11-17T09:00:00+00:00')
        correction = fact(openings=6, revision=2, received_at='2026-11-16T09:00:00+00:00')
        accepted = self.mart.ingest([original, correction], DIMENSIONS)['accepted']
        self.assertEqual([row['openings'] for row in accepted], [6])

    def test_missing_arrival_timestamp_uses_delivery_order(self):
        # The original defect: both rows had no ``received_at`` and the first
        # delivered quantity was preferred forever.
        original = fact(openings=10)
        correction = fact(openings=6)
        original.pop('received_at')
        correction.pop('received_at')
        accepted = self.mart.ingest([original, correction], DIMENSIONS)['accepted']
        self.assertEqual([row['openings'] for row in accepted], [6])

    def test_equal_arrival_timestamp_uses_delivery_order(self):
        original = fact(openings=10, received_at='2026-11-17T09:00:00+00:00')
        correction = fact(openings=6, received_at='2026-11-17T09:00:00+00:00')
        accepted = self.mart.ingest([original, correction], DIMENSIONS)['accepted']
        self.assertEqual([row['openings'] for row in accepted], [6])

    def test_business_date_does_not_select_the_revision(self):
        # A correction can describe an earlier business date; the later
        # arrival is still the current fact.
        original = fact(openings=10, event_date='2026-11-16')
        correction = fact(openings=6, event_date='2026-11-10',
                          received_at='2026-11-17T09:00:00+00:00')
        accepted = self.mart.ingest([original, correction], DIMENSIONS)['accepted']
        self.assertEqual([row['openings'] for row in accepted], [6])
        self.assertEqual([row['event_date'] for row in accepted], ['2026-11-10'])

    def test_superseded_revision_is_traceable(self):
        original = fact(openings=10)
        correction = fact(openings=6, event_date='2026-11-15',
                          received_at='2026-11-17T09:00:00+00:00')
        result = self.mart.ingest([original, correction], DIMENSIONS)
        self.assertEqual(len(result['superseded']), 1)
        superseded = result['superseded'][0]
        self.assertEqual(superseded['status'], 'superseded')
        self.assertEqual(superseded['event_date'], '2026-11-16')
        self.assertTrue(superseded['fingerprint'])
        current = result['accepted'][0]
        self.assertEqual(current['revision_status'], 'late_revision')
        self.assertIs(current['late'], True)
        self.assertEqual(current['supersedes'][0]['fingerprint'], superseded['fingerprint'])
        self.assertEqual(result['statistics']['superseded'], 1)

    def test_late_revision_is_distinguishable_from_normal_current(self):
        original = fact(openings=10)
        same_day = fact(openings=8, received_at='2026-11-17T09:00:00+00:00')
        self.assertEqual(self.mart.ingest([original, same_day], DIMENSIONS)['accepted'][0]['revision_status'], 'current')
        back_dated = fact(openings=6, event_date='2026-11-15',
                          received_at='2026-11-17T09:00:00+00:00')
        result = self.mart.ingest([original, back_dated], DIMENSIONS)
        self.assertEqual(result['accepted'][0]['revision_status'], 'late_revision')
        self.assertEqual(len(result['late_revisions']), 1)

    def test_invalid_dimension_revision_does_not_override_current_fact(self):
        original = fact(openings=10)
        broken = fact(openings=1, industry_code='unknown',
                      received_at='2026-11-18T09:00:00+00:00')
        result = self.mart.ingest([original, broken], DIMENSIONS)
        self.assertEqual([row['openings'] for row in result['accepted']], [10])
        self.assertEqual(len(result['rejected']), 1)
        rejection = result['rejected'][0]
        self.assertEqual(rejection['status'], 'rejected_invalid_dimension')
        self.assertEqual(rejection['reason'], 'dimension_resolution_missing')
        self.assertIs(rejection['would_supersede'], True)
        self.assertEqual(result['trace']['jobs|1']['status'], 'current')

    def test_invalid_dimension_is_not_an_extra_non_current_fact(self):
        broken = fact(industry_code='unknown')
        result = self.mart.ingest([broken], DIMENSIONS)
        self.assertEqual(result['accepted'], [])
        self.assertEqual(result['statistics']['rejected'], 1)
        self.assertEqual(self.mart.aggregate([broken], ['industry_key'], DIMENSIONS), [])

    def test_historical_snapshot_rows_do_not_become_current(self):
        published = fact(openings=10, is_current=False, revision_status='historical_snapshot')
        fresh = fact(openings=6, received_at='2026-11-17T09:00:00+00:00')
        result = self.mart.ingest([published, fresh], DIMENSIONS)
        self.assertEqual([row['openings'] for row in result['accepted']], [6])
        self.assertEqual(result['statistics']['historical_snapshot'], 1)
        self.assertEqual(result['historical_snapshot'][0]['status'], 'historical_snapshot')
        self.assertEqual(result['accepted'][0]['revision_status'], 'current')

    def test_prior_snapshot_is_carried_forward_when_nothing_new_arrives(self):
        published = self.mart.ingest([fact(openings=10)], DIMENSIONS)['accepted']
        result = self.mart.ingest([], DIMENSIONS, prior=published)
        self.assertEqual(len(result['accepted']), 1)
        self.assertEqual(result['accepted'][0]['revision_status'], 'carried_forward')
        self.assertEqual(result['statistics']['accepted'], 1)

    def test_new_revision_replaces_prior_snapshot_as_history(self):
        published = self.mart.ingest([fact(openings=10)], DIMENSIONS)['accepted']
        correction = fact(openings=6, event_date='2026-11-15',
                          received_at='2026-11-17T09:00:00+00:00')
        result = self.mart.ingest([correction], DIMENSIONS, prior=published)
        self.assertEqual([row['openings'] for row in result['accepted']], [6])
        self.assertEqual(result['statistics']['historical_snapshot'], 1)
        self.assertEqual(result['historical_snapshot'][0]['event_date'], '2026-11-16')
        self.assertEqual(result['accepted'][0]['revision_status'], 'late_revision')

    def test_redelivery_of_published_fact_is_a_duplicate(self):
        published = self.mart.ingest([fact(openings=10)], DIMENSIONS)['accepted']
        result = self.mart.ingest([fact(openings=10)], DIMENSIONS, prior=published)
        self.assertEqual(len(result['accepted']), 1)
        self.assertEqual(result['statistics']['duplicates'], 1)


class NoDoubleCountTests(unittest.TestCase):
    def setUp(self):
        self.mart = TalentMart()

    def test_repeated_input_counts_once_in_aggregate(self):
        row = fact()
        totals = self.mart.aggregate([row, row, row], ['region_key'], DIMENSIONS)
        self.assertEqual(totals, [{'key': ('r1',), 'openings': 10, 'seekers': 4, 'intents': 0,
                                   'gap': 6, 'average_salary': '10000'}])

    def test_rank_uses_current_revision_only(self):
        from talent_observatory.warehouse.engine import WarehouseEngine
        engine = WarehouseEngine()
        original = {'id': 'fact-1', 'natural_key': 'job-1', 'industry_code': 'ai', 'region_code': 'sy',
                    'event_date': '2026-11-16', 'values': [10], 'received_at': '2026-11-16T09:00:00+00:00'}
        correction = {'id': 'fact-1r', 'natural_key': 'job-1', 'industry_code': 'ai', 'region_code': 'sy',
                      'event_date': '2026-11-16', 'values': [6], 'received_at': '2026-11-17T09:00:00+00:00'}
        results = engine.rank([original, correction], {'dimension_versions': DIMENSIONS})
        self.assertEqual(len(results), 1)
        self.assertEqual([str(result.value) for result in results], ['6'])

    def test_superseded_and_current_count_once(self):
        totals = self.mart.aggregate([fact(openings=10), fact(openings=6, event_date='2026-11-15')],
                                     ['region_key'], DIMENSIONS)
        self.assertEqual(totals[0]['openings'], 6)
        self.assertEqual(totals[0]['gap'], 2)

    def test_duplicate_is_reported_not_summed(self):
        result = self.mart.ingest([fact(), fact()], DIMENSIONS)
        self.assertEqual(result['statistics']['duplicates'], 1)
        self.assertEqual(len(result['accepted']), 1)
        self.assertEqual(result['duplicates'][0]['reason'], 'duplicate input')

    def test_distinct_sources_still_add_up(self):
        totals = self.mart.aggregate([fact('1', openings=10), fact('2', openings=5)], ['region_key'], DIMENSIONS)
        self.assertEqual(totals[0]['openings'], 15)

    def test_flow_matrix_counts_current_people_once(self):
        rows = [
            {'source': 'flows', 'source_key': 'f1', 'origin_region': 'sy', 'target_region': 'dl', 'people': 3},
            {'source': 'flows', 'source_key': 'f1', 'origin_region': 'sy', 'target_region': 'dl', 'people': 3,
             'received_at': '2026-11-17T00:00:00+00:00'},
        ]
        self.assertEqual(self.mart.flow_matrix(rows), [{'origin': 'sy', 'target': 'dl', 'people': 3}])


class AggregateCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.mart = TalentMart()

    def test_corrected_industry_region_and_date_dimensions(self):
        original = fact(openings=10, seekers=4)
        correction = fact(industry_code='mk', region_code='dl', event_date='2026-11-15',
                          openings=6, seekers=1, received_at='2026-11-17T09:00:00+00:00')
        by_industry = self.mart.aggregate([original, correction], ['industry_key'], DIMENSIONS)
        self.assertEqual(by_industry, [{'key': ('i2',), 'openings': 6, 'seekers': 1, 'intents': 0,
                                        'gap': 5, 'average_salary': '10000'}])
        by_region = self.mart.aggregate([original, correction], ['region_key'], DIMENSIONS)
        self.assertEqual([row['key'] for row in by_region], [('r2',)])
        by_date = self.mart.aggregate([original, correction], ['event_date'], DIMENSIONS)
        self.assertEqual(by_date[0]['key'], ('2026-11-15',))

    def test_untouched_region_keeps_previous_result(self):
        sy_original = fact('1', region_code='sy', openings=10)
        dl = fact('2', region_code='dl', openings=5)
        sy_correction = fact('1', region_code='sy', openings=6,
                             received_at='2026-11-17T09:00:00+00:00')
        manifest = self.mart.change_manifest(
            [sy_original, dl], [sy_original, dl, sy_correction], ['region_key'], DIMENSIONS)
        self.assertEqual(manifest['changed_keys'], (('r1',),))
        self.assertEqual(manifest['unchanged_keys'], (('r2',),))
        dl_after = [row for row in manifest['after'] if row['key'] == ('r2',)][0]
        dl_before = [row for row in manifest['before'] if row['key'] == ('r2',)][0]
        self.assertEqual(dl_after, dl_before)
        self.assertEqual([change['key'] for change in manifest['changes']], [('r1',)])

    def test_change_manifest_reports_before_after_and_fields(self):
        original = fact(openings=10, seekers=4)
        correction = fact(openings=6, event_date='2026-11-15',
                          received_at='2026-11-17T09:00:00+00:00')
        manifest = self.mart.change_manifest([original], [original, correction], ['industry_key'], DIMENSIONS)
        self.assertEqual(manifest['grain'], ('industry_key',))
        self.assertEqual(manifest['before'][0]['gap'], 6)
        self.assertEqual(manifest['after'][0]['gap'], 2)
        # The business date moved, so the old date bucket disappears and a new
        # one appears; the delta names both.
        by_date = self.mart.change_manifest([original], [original, correction], ['event_date'], DIMENSIONS)
        self.assertEqual({change['change'] for change in by_date['changes']}, {'added', 'removed'})

    def test_change_manifest_carries_raw_to_metric_trace(self):
        original = fact(openings=10)
        correction = fact(openings=6, event_date='2026-11-15',
                          received_at='2026-11-17T09:00:00+00:00')
        manifest = self.mart.change_manifest([original], [original, correction], ['region_key'], DIMENSIONS)
        revisions = manifest['revisions']
        self.assertEqual(revisions['statistics']['superseded'], 1)
        self.assertEqual(revisions['statistics']['late_revisions'], 1)
        self.assertEqual(revisions['superseded'][0]['event_date'], '2026-11-16')
        self.assertEqual(revisions['current'][0][3], 'late_revision')
        self.assertEqual(manifest['changes'][0]['after']['gap'], 2)

    def test_recompute_delta_keeps_existing_contract(self):
        old = [{'key': ('i1',), 'openings': 10, 'seekers': 4, 'intents': 0, 'gap': 6, 'average_salary': None}]
        new = [{'key': ('i1',), 'openings': 10, 'seekers': 4, 'intents': 0, 'gap': 6, 'average_salary': None}]
        self.assertEqual(self.mart.recompute_delta(old, new), [])
        changed = [dict(new[0], gap=2)]
        delta = self.mart.recompute_delta(old, changed)
        self.assertEqual(delta, [{'key': ('i1',), 'before': old[0], 'after': changed[0]}])

    def test_change_list_names_operation_and_fields(self):
        old = [{'key': ('i1',), 'openings': 10, 'seekers': 4, 'intents': 0, 'gap': 6, 'average_salary': None}]
        new = [dict(old[0], gap=2)]
        change = self.mart.change_list(old, new)[0]
        self.assertEqual(change['change'], 'updated')
        self.assertEqual(change['changed_fields'], ('gap',))
