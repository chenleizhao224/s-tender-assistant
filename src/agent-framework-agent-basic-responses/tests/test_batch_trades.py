import tempfile
import unittest
from pathlib import Path
from tender_assistant.cli.batch_trades import merge_saved, pending_batches
from tender_assistant.schedules.trades import build_request, save_classification


class BatchTradeTests(unittest.TestCase):
    def setUp(self):
        self.items = [dict(excel_row=n, row_id=f'h:s:{n}', source_file='s.xlsx',
                           description='Excavate', code=str(n), unit='m3',
                           category='measured_item', ready_for_rate_matching=True) for n in range(1, 5)]
        self.request = build_request(self.items)

    def test_only_missing_rows(self):
        self.assertEqual(pending_batches(self.request, {'R2': {}}, 2), [[1, 3], [4]])

    def test_batch_limits(self):
        for size in (0, 31):
            with self.assertRaises(ValueError):
                pending_batches(self.request, {}, size)

    def test_reuse_duplicate_and_changed_source(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'part.json'
            request = build_request(self.items, [1])
            result = {'decisions': [dict(item_id='R1', status='proposed_trade', trade='Earthworks',
                                        reason='Excavation', assumptions=[], source_ids=['R1'])]}
            save_classification(path, request, result, 'test-model')
            decisions, models = merge_saved(self.request, [path])
            self.assertEqual(list(decisions), ['R1'])
            self.assertEqual(models, {'test-model'})
            with self.assertRaises(ValueError):
                merge_saved(self.request, [path, path])
            self.request['schedule_sources']['R1']['description'] = 'Changed'
            with self.assertRaises(ValueError):
                merge_saved(self.request, [path])


if __name__ == '__main__':
    unittest.main()
