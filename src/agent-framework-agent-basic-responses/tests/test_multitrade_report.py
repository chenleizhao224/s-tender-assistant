import unittest
from tender_assistant.pricing.summary import summarize
from tender_assistant.reporting.demo import render_report


class MultiTradeReportTests(unittest.TestCase):
    def test_unpriced_trade_and_coverage_remain_visible(self):
        entry = dict(excel_row=16, amount=None, state='unpriced', snapshot_file='missing.json',
                     allocated_trade='P&G', description='Establishment', reason='Lump sum rule pending',
                     code='1.1', quantity=None, unit='LS')
        batch = summarize([entry]) | {'source_sha256': 'test', 'created_at': 'test',
            'classification_coverage': {'work_item_count': 1,
                'decisions': [{'trade': 'P&G', 'status': 'proposed_trade'}]}}
        html = render_report(batch, 'Test')
        self.assertIn('P&amp;G', html)
        self.assertIn('Not estimated', html)
        self.assertIn('All 1 work rows', html)
        self.assertNotIn('selected Earthworks items', html)
        self.assertIn('<summary>Not estimated</summary>', html)
        self.assertIn('<summary>Unpriced</summary>', html)
        self.assertIn('Not specified</td>', html)
        self.assertIn('Lump sum rule pending', html)
        self.assertIn('No items from this trade were selected', html)

    def test_reason_is_escaped(self):
        from tender_assistant.reporting.demo import unpriced_explanation
        html = unpriced_explanation({'reason': '<script>alert(1)</script>'})
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_tampered_total_rejected(self):
        batch = summarize([]) | {'source_sha256': 'test', 'created_at': 'test', 'indicative_subtotal': '10'}
        with self.assertRaises(ValueError):
            render_report(batch, 'Test')
