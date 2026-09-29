from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hmigbot_ios.analyze import analyze, migration_plan
from hmigbot_ios.core import MigrationError, read_json, write_json
from hmigbot_ios.evidence import pack, validate
from hmigbot_ios.generate import generate, verify
from hmigbot_ios.swiftui import parse_view, emit_view, tokenize

FIXTURES = Path(__file__).parent / "fixtures"


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_counter_matches_independently_written_golden(self):
        view = parse_view((FIXTURES / "swiftui_counter/CounterView.swift").read_text())
        expected = (Path(__file__).parent / "golden/CounterView.ets").read_text()
        self.assertEqual(emit_view(view, entry=True), expected)
        self.assertEqual(view["states"], {"count": 0})
        buttons = view["root"]["children"][1]["children"]
        self.assertEqual(buttons[0]["action"], {"state": "count", "operator": "+=", "value": 1})
        self.assertEqual(buttons[1]["action"], {"state": "count", "operator": "=", "value": 0})

    def test_unsupported_statements_never_disappear(self):
        samples = [
            'Text("Hello").onAppear { doSomething() }',
            'ForEach(items) { Text($0) }',
            'NavigationStack { Text("Hello") }',
            'Text(model.title)',
            'Text("Hello").padding()',
            'VStack { if ready { Text("Ready") } }',
            'Button("Run") { launchPayment() }',
            'Image(systemName: "star")',
            'Text("Hello").frame(maxWidth: .infinity)',
            'Text("Hello").padding(-1)',
        ]
        for body in samples:
            with self.subTest(body=body), self.assertRaises(MigrationError):
                parse_view('import SwiftUI\nstruct Screen: View { var body: some View { ' + body + ' } }')

    def test_extra_helpers_and_multiple_actions_are_rejected(self):
        text = (FIXTURES / "swiftui_counter/CounterView.swift").read_text()
        for value in [text + '\nfunc ignored() {}', text.replace('count += 1', 'count += 1; save()'),
                      text.replace('Int = 0', 'Int = 9007199254740992')]:
            with self.assertRaises(MigrationError):
                parse_view(value)

    def test_comments_do_not_create_declarations(self):
        tokens = tokenize('/* nested /* struct Wrong {} */ comment */ struct Real {} // func wrong()')
        self.assertEqual([t.value for t in tokens], ['struct', 'Real', '{', '}'])

    def test_objc_and_ib_inventory_is_not_claimed_converted(self):
        objc = analyze(FIXTURES / "uikit_objc")
        self.assertEqual(objc["inventory"]["languages"]["Objective-C"], 1)
        self.assertTrue(migration_plan(objc)["tasks"])
        ib = analyze(FIXTURES / "interface_builder")
        kinds = [f["value"]["tag"] for f in ib["facts"] if f["kind"] == "interface_builder"]
        self.assertIn("action", kinds)
        self.assertIn("constraint", kinds)
        self.assertEqual(ib["pages"][0]["status"], "unsupported")

    def test_async_and_dynamic_dispatch_are_exposed(self):
        report = analyze(FIXTURES / "unsupported")
        self.assertEqual(report["pages"][0]["status"], "unsupported")
        self.assertIn("dynamic_dispatch", [i["code"] for i in analyze(FIXTURES / "dynamic")["issues"]])

    def test_stable_facts_and_source_anchors(self):
        first = analyze(FIXTURES / "swiftui_counter")
        second = analyze(FIXTURES / "swiftui_counter")
        self.assertEqual(first, second)
        self.assertTrue(all(f["source_anchors_ref"][0]["sha256"] for f in first["facts"]))

    def generate(self, source, **extra):
        return generate(source, self.root / "harmony", sdk="6.0.2(22)", min_sdk="6.0.2(22)",
                        model_version="6.0.2", bundle_name="com.example.migration", **extra)

    def test_project_generation_and_modified_source_or_target(self):
        source = self.root / "ios"
        shutil.copytree(FIXTURES / "swiftui_counter", source)
        manifest = self.generate(source)
        self.assertEqual(manifest["app_migration"], "incomplete")
        self.assertTrue(verify(source, self.root / "harmony")["integrity_passed"])
        page = self.root / "harmony/entry/src/main/ets/pages/CounterView.ets"
        page.write_text(page.read_text() + "\n// edit")
        self.assertFalse(verify(source, self.root / "harmony")["integrity_passed"])
        source.joinpath("CounterView.swift").write_text("struct Changed {}")
        self.assertFalse(verify(source, self.root / "harmony")["checks"][0]["passed"])

    def test_all_unsupported_produces_no_empty_success_project(self):
        with self.assertRaises(MigrationError):
            self.generate(FIXTURES / "unsupported")
        self.assertFalse((self.root / "harmony").exists())

    def test_explicit_scaffold_supports_objc_without_claiming_converted_pages(self):
        manifest = self.generate(FIXTURES / 'uikit_objc', scaffold_only=True)
        self.assertEqual(manifest['status'], 'scaffold_created')
        self.assertEqual(manifest['generated_pages'], [])
        self.assertTrue(verify(FIXTURES / 'uikit_objc', self.root / 'harmony')['integrity_passed'])

    def test_multiple_pages_require_entry_selection(self):
        source = self.root / "ios"
        shutil.copytree(FIXTURES / "swiftui_counter", source)
        shutil.copy(FIXTURES / "swiftui_static/WelcomeView.swift", source)
        with self.assertRaises(MigrationError):
            self.generate(source)
        self.generate(source, entry_view="WelcomeView")
        pages = read_json(self.root / "harmony/entry/src/main/resources/base/profile/main_pages.json")
        self.assertEqual(pages["src"][0], "pages/WelcomeView")

    def test_evidence_integrity_not_test_pass(self):
        artifacts = self.root / "captured"
        artifacts.mkdir()
        (artifacts / "test.log").write_text("one source test ran")
        bundle = self.root / "bundle"
        pack(FIXTURES / "swiftui_counter", artifacts, bundle, "source_tests", "Xcode test fixture")
        result = validate(FIXTURES / "swiftui_counter", bundle)
        self.assertTrue(result["integrity_passed"])
        self.assertEqual(result["claim_validation"], "not_performed")
        with self.assertRaises(MigrationError):
            validate(FIXTURES / "swiftui_static", bundle)
        (bundle / "artifacts/test.log").write_text("forged")
        with self.assertRaises(MigrationError):
            validate(FIXTURES / "swiftui_counter", bundle)

    def test_evidence_traversal(self):
        from hmigbot_ios.core import snapshot
        bundle = self.root / "bundle"
        bundle.mkdir()
        write_json(bundle / "manifest.json", {"schema_version": "hmigbot-ios/1", "kind": "source_tests",
                   "provider": "fixture", "origin": "user_supplied_source_evidence", "claim_validation": "not_performed",
                   "source_sha256": snapshot(FIXTURES / "swiftui_counter")["sha256"],
                   "artifacts": {"artifacts/../../escape": "f" * 64}})
        with self.assertRaises(MigrationError):
            validate(FIXTURES / "swiftui_counter", bundle)


if __name__ == "__main__":
    unittest.main()
