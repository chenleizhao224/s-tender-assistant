import unittest
from tender_assistant.text.summary import SECTIONS, BRIEF_SECTIONS, validate_summary

class SummaryTests(unittest.TestCase):
    def test_estimator_brief_profile(self):
        from tender_assistant.reporting.estimator_brief import render_brief
        result = {'sections': [{'title': t, 'items': [{'text': '<Draft>', 'source_ids': ['s']}]} for t in BRIEF_SECTIONS]}
        sources = {'s': {'source_file': 'spec.pdf', 'locator': 'page-1', 'text': '<Source>'}}
        validate_summary(result, sources)
        html = render_brief({'summary': result, 'sources': sources, 'coverage': []})
        self.assertIn('&lt;Draft&gt;', html)
        self.assertIn('&lt;Source&gt;', html)
        self.assertEqual(html.count('id="source-1"'), 1)
        self.assertNotIn('Indicative subtotal', html)

    def result(self):
        return {'sections': [{'title': title, 'items': [{'text': 'A finding', 'source_ids': ['source-1']}]} for title in SECTIONS]}

    def test_valid_citations(self):
        validate_summary(self.result(), {'source-1': {}})

    def test_unknown_citation_rejected(self):
        with self.assertRaises(ValueError):
            validate_summary(self.result(), {})

    def test_missing_section_rejected(self):
        result = self.result()
        result['sections'].pop()
        with self.assertRaises(ValueError):
            validate_summary(result, {'source-1': {}})

    def test_explicit_gap_can_have_no_citation(self):
        result = self.result()
        result['sections'][-1]['items'] = [{'text': 'Not established in supplied documents', 'source_ids': []}]
        validate_summary(result, {'source-1': {}})
