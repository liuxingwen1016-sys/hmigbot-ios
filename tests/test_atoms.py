import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hmigbot_ios.atoms import run_atom
from hmigbot_ios.core import MigrationError, digest, json_bytes, snapshot
from hmigbot_ios.generate import generate, verify
from hmigbot_ios.resources import locale_qualifier
from hmigbot_ios.xcode import OpenStep


def make_png(width=4, height=4):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\x20\x80\xc0\xff' * width) * height)) + chunk(b'IEND', b''))


def resource_fixture(root):
    root.mkdir(parents=True)
    (root / 'ResourceView.swift').write_text('''import SwiftUI
struct ResourceView: View {
    var body: some View {
        VStack(spacing: 12) {
            Image("Badge")
            Text("Welcome")
            Text(verbatim: "Welcome")
        }.padding(16)
    }
}
''', encoding='utf-8')
    asset = root / 'Assets.xcassets/Badge.imageset'
    asset.mkdir(parents=True)
    (asset / 'badge.png').write_bytes(make_png())
    (asset / 'Contents.json').write_bytes(json_bytes({'images': [{'filename': 'badge.png', 'idiom': 'universal', 'scale': '2x'}], 'info': {'version': 1, 'author': 'xcode'}}))
    (root / 'Localizable.xcstrings').write_bytes(json_bytes({'sourceLanguage': 'en', 'version': '1.0', 'strings': {'Welcome': {'localizations': {'zh-Hans': {'stringUnit': {'state': 'translated', 'value': '欢迎'}}}}}}))


class AtomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'ios'
        self.source.mkdir()

    def test_openstep_comments_escapes_and_empty_values(self):
        parsed = OpenStep(r'''// header
        { "空 格" = "a\n\U4f60\U597d"; flags = ("", A,); /* ignore */ k = "()"; }''').parse()
        self.assertEqual(parsed, {'空 格': 'a\n你好', 'flags': ['', 'A'], 'k': '()'})
        for raw in ('{a=1;a=2;}', '{a=1;}', '{x=(a b);}', '{x="\\q";}', '{}junk'):
            if raw == '{a=1;}':
                self.assertEqual(OpenStep(raw).parse(), {'a': '1'})
            else:
                with self.subTest(raw=raw), self.assertRaises(MigrationError):
                    OpenStep(raw).parse()

    def test_project_sources_and_unresolved_build_settings(self):
        (self.source / 'App.xcodeproj').mkdir()
        (self.source / 'Sources').mkdir()
        (self.source / 'Sources/View.swift').write_text('import SwiftUI')
        (self.source / 'App.xcodeproj/project.pbxproj').write_text('''{objects = {
        root = {isa = PBXGroup; children = (g,); sourceTree = "<group>";};
        g = {isa = PBXGroup; path = Sources; children = (f,); sourceTree = "<group>";};
        f = {isa = PBXFileReference; path = View.swift; sourceTree = "<group>";};
        b = {isa = PBXBuildFile; fileRef = f;};
        p = {isa = PBXSourcesBuildPhase; files = (b,);};
        c = {isa = XCBuildConfiguration; name = Debug; buildSettings = {SWIFT_VERSION = 5.0;};};
        cl = {isa = XCConfigurationList; buildConfigurations = (c,);};
        t = {isa = PBXNativeTarget; name = App; buildConfigurationList = cl; buildPhases = (p,); productType = "com.apple.product-type.application";};
        };}''')
        report = run_atom('project-inventory', self.source, self.root / 'project')
        target = report['data']['projects'][0]['targets'][0]
        self.assertEqual(target['phases'][0]['files'][0]['path'], 'Sources/View.swift')
        self.assertTrue(target['phases'][0]['files'][0]['exists'])
        self.assertEqual(target['effective_settings'], 'unresolved')

    def test_dependency_pins_are_not_a_resolved_graph(self):
        (self.source / 'Package.resolved').write_bytes(json_bytes({'version': 2, 'pins': [{'identity': 'swift-syntax', 'location': 'https://github.com/swiftlang/swift-syntax', 'state': {'version': '600.0.1', 'revision': 'x'}}]}))
        (self.source / 'Podfile.lock').write_text('PODS:\n  - UIKitHelper (1.2.3):\n    - Dependency\nDEPENDENCIES:\n  - UIKitHelper\n')
        report = run_atom('dependency-inventory', self.source, self.root / 'deps')
        self.assertEqual(len(report['data']['dependencies']), 2)
        self.assertEqual(report['data']['dependencies'][0]['manager'], 'SwiftPM')

    def test_ib_references_and_entities_are_not_silently_accepted(self):
        (self.source / 'Main.storyboard').write_text('<document><view id="v"><connections><outlet id="o" destination="missing"/></connections></view></document>')
        report = run_atom('interface-builder', self.source, self.root / 'ib')
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['issues'][0]['code'], 'unresolved_ib_reference')
        (self.source / 'Main.storyboard').write_text('<!DOCTYPE x [<!ENTITY a "b">]><document/>')
        self.assertEqual(run_atom('interface-builder', self.source, self.root / 'ib2')['issues'][0]['code'], 'ib_parse_failed')

    def test_resources_bind_localized_and_verbatim_text_separately(self):
        shutil.rmtree(self.source)
        resource_fixture(self.source)
        assets, locale = self.root / 'assets', self.root / 'locale'
        a = run_atom('asset-convert', self.source, assets)
        l = run_atom('localization-convert', self.source, locale, default_locale='en')
        self.assertFalse(a['issues'] + l['issues'])
        self.assertEqual(a['data']['mappings'][0]['logical_width'], 2)
        target = self.root / 'target'
        generate(self.source, target, sdk='26.0.0', min_sdk='6.0.2(22)', model_version='6.0.2', bundle_name='com.example.resources', resource_bundles=[assets, locale])
        page = (target / 'entry/src/main/ets/pages/ResourceView.ets').read_text()
        self.assertIn('Image($r("app.media.', page)
        self.assertIn('Text($r("app.string.', page)
        self.assertIn('Text("Welcome")', page)
        self.assertTrue(verify(self.source, target)['integrity_passed'])
        copied = target / a['data']['mappings'][0]['target']
        self.assertEqual(copied.read_bytes(), make_png())

    def test_unbound_images_and_tampered_resources_refuse_generation(self):
        shutil.rmtree(self.source)
        resource_fixture(self.source)
        with self.assertRaises(MigrationError):
            generate(self.source, self.root / 'missing', sdk='26.0.0', min_sdk='6.0.2(22)', model_version='6.0.2', bundle_name='com.example.missing')
        assets = self.root / 'assets'
        a = run_atom('asset-convert', self.source, assets)
        (assets / a['data']['mappings'][0]['target']).write_bytes(b'changed')
        with self.assertRaises(MigrationError):
            generate(self.source, self.root / 'bad', sdk='26.0.0', min_sdk='6.0.2(22)', model_version='6.0.2', bundle_name='com.example.bad', resource_bundles=[assets])

    def test_localization_formats_variations_and_locales(self):
        self.assertEqual(locale_qualifier('zh-Hans-CN'), 'zh_Hans_CN')
        self.assertEqual(locale_qualifier('en-GB'), 'en_GB')
        with self.assertRaises(MigrationError):
            locale_qualifier('en-u-ca-gregory')
        (self.source / 'en.lproj').mkdir()
        (self.source / 'en.lproj/Localizable.strings').write_text('"hello" = "Hello"; "count" = "%d items";')
        report = run_atom('localization-convert', self.source, self.root / 'locale', default_locale='en')
        self.assertEqual(len(report['data']['mappings']), 1)
        self.assertEqual(len(report['issues']), 1)

    def test_source_mutation_invalidates_resource_bundle(self):
        shutil.rmtree(self.source)
        resource_fixture(self.source)
        assets = self.root / 'assets'
        run_atom('asset-convert', self.source, assets)
        (self.source / 'new.swift').write_text('// changed')
        with self.assertRaises(MigrationError):
            generate(self.source, self.root / 'stale', sdk='26.0.0', min_sdk='6.0.2(22)', model_version='6.0.2', bundle_name='com.example.stale', resource_bundles=[assets])


if __name__ == '__main__':
    unittest.main()
