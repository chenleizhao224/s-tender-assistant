"""Regression checks for package moves; no model calls or credentials needed."""
import subprocess
import sys
import unittest
from pathlib import Path

from tender_assistant.paths import SERVICE_ROOT
from tender_assistant.pricing.summary import summarize
from tender_assistant.pricing.recommendations import validate_result


class ModuleLayoutTests(unittest.TestCase):
    def test_service_root_preserved(self):
        self.assertEqual(SERVICE_ROOT, Path(__file__).resolve().parents[1])
        self.assertTrue((SERVICE_ROOT / 'main.py').is_file())
        self.assertTrue((SERVICE_ROOT / 'pyproject.toml').is_file())

    def test_commands_import_and_show_help(self):
        for module in (
            'cli.match_rates', 'cli.batch_rates', 'text.extraction',
            'text.summary', 'reporting.demo', 'reporting.estimator_brief',
        ):
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, '-m', 'tender_assistant.' + module, '--help'],
                    cwd=SERVICE_ROOT, capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)

    def test_batch_summary_in_pricing(self):
        entries = [
            {'excel_row': 1, 'amount': '0.1', 'state': 'priced'},
            {'excel_row': 2, 'amount': '0.2', 'state': 'priced'},
        ]
        self.assertEqual(summarize(entries)['indicative_subtotal'], '0.3')
        with self.assertRaises(ValueError):
            summarize(entries + entries)

    def test_unknown_rate_rejected_by_pricing_validator(self):
        import json
        response = dict(status='proposed_match', rate_id='unknown',
                        match_basis='direct_description', reason='Example',
                        assumptions=[], differences=[])
        with self.assertRaises(ValueError):
            validate_result(json.dumps(response), {})
