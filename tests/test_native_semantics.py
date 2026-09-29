"""Source-native contracts must reject dropped framework semantics and false evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hmigbot_ios.native_semantics import required_facts, validate_native_facts


class NativeSemanticTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.project = self.root / 'target'
        self.path = self.project / 'spec/baseline/ios-semantics.json'
        self.path.parent.mkdir(parents=True)
        (self.source / 'Screen.swift').write_text('import SwiftUI\nstruct Screen: View {\n @State var count = 0\n var body: some View { Text("Count") }\n}\n')
        self.doc = {'id': 'page_0001', 'kind': 'page', 'languages': ['swift'], 'frameworks': ['swiftui'], 'facts': {}}
        # Test fixture states explicit non-applicability; this does not claim a semantic audit.
        self.doc['facts'] = {k: {'status': 'not_applicable', 'reason': 'Fixture contract case'} for k in required_facts('page', {'swift'}, {'swiftui'})}
        self.doc['facts']['state_ownership'] = {'status': 'known', 'value': {'owner': 'Screen', 'storage': 'State', 'initial': 0}, 'evidence': [{'path': 'Screen.swift', 'line': 3}]}

    def findings(self):
        self.path.write_text(json.dumps({'schema_version': 1, 'source_platform': 'ios', 'documents': [self.doc]}))
        issues = []
        validate_native_facts(self.source, self.project, {'page_0001': ('page', ['Screen.swift'])}, {'Screen.swift'}, lambda *issue: issues.append(issue))
        return [i[0] for i in issues]

    def test_swiftui_cannot_omit_binding_modifier_or_cancellation(self):
        self.assertEqual(self.findings(), [])
        for field in ('binding_flow', 'modifier_order', 'task_lifetime'):
            value = self.doc['facts'].pop(field)
            self.assertIn('IOS.NATIVE_DIMENSION_MISSING', self.findings())
            self.doc['facts'][field] = value

    def test_unknown_is_not_equivalent_to_not_applicable(self):
        self.doc['facts']['binding_flow'] = {'status': 'unknown', 'reason': 'Custom wrapper not resolved'}
        self.assertIn('IOS.NATIVE_FACT_UNKNOWN', self.findings())
        self.doc['facts']['binding_flow'] = {'status': 'not_applicable', 'reason': ''}
        self.assertIn('IOS.NATIVE_FACT_REASON', self.findings())

    def test_false_evidence_and_language_relabeling_are_rejected(self):
        fact = self.doc['facts']['state_ownership']
        fact['evidence'][0]['line'] = 999
        self.assertIn('IOS.NATIVE_FACT_EVIDENCE', self.findings())
        fact['evidence'][0] = {'path': '../outside.swift', 'line': 1}
        self.assertIn('IOS.NATIVE_FACT_EVIDENCE', self.findings())
        self.doc['languages'] = ['objc']
        self.doc['frameworks'] = ['other']
        self.assertIn('IOS.NATIVE_FACTS_LANGUAGE', self.findings())
        self.assertIn('IOS.NATIVE_FACTS_FRAMEWORK', self.findings())

    def test_mixed_ui_requires_both_protocols_and_objc_keeps_ownership(self):
        fields = required_facts('page', {'swift', 'objc'}, {'swiftui', 'uikit'})
        self.assertTrue({'binding_flow', 'controller_lifecycle', 'delegates', 'nullability', 'ownership', 'dynamic_dispatch'} <= fields)
        self.doc['frameworks'] = ['swiftui', 'uikit']
        self.assertIn('IOS.NATIVE_DIMENSION_MISSING', self.findings())

    def test_page_cannot_be_labeled_nonvisual_to_skip_semantics(self):
        self.doc['frameworks'] = ['nonvisual']
        self.assertIn('IOS.NATIVE_FACTS_FRAMEWORK', self.findings())

    def test_known_zero_is_a_valid_value_but_no_provenance_is_not(self):
        self.doc['facts']['state_ownership']['value'] = 0
        self.assertEqual(self.findings(), [])
        self.doc['facts']['state_ownership']['evidence'] = []
        self.assertIn('IOS.NATIVE_FACT_EVIDENCE', self.findings())


if __name__ == '__main__':
    unittest.main()
