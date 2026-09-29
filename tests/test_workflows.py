import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hmigbot_ios.core import MigrationError, digest, json_bytes, snapshot
from hmigbot_ios.evidence import pack
from hmigbot_ios.workflow import initialize, pipeline_status, compare_behavior, check_coverage
from hmigbot_ios.tasks import create_task, check_task
from hmigbot_ios.cloud import prepare, validate_config

spec = importlib.util.spec_from_file_location('manage_install', ROOT / 'scripts/manage_install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hmigbot 测试 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        shutil.copytree(ROOT / 'tests/fixtures/swiftui_counter', self.source)

    def test_initialized_pipeline_is_pending_and_rejects_stale_source(self):
        run = self.root / 'run'
        initialize(self.source, run)
        status = pipeline_status(run)
        self.assertFalse(status['migration_complete'])
        self.assertEqual(status['status'], 'in_progress')
        self.assertEqual(status['stages']['execute'], 'pending')
        self.assertEqual(status['stages']['retrospect'], 'pending')
        (self.source / 'extra').write_text('changed')
        self.assertEqual(pipeline_status(run)['status'], 'stale_source')

    def test_agent_task_requires_real_anchors_and_outputs(self):
        folder = self.root / 'task'
        create_task('D01', self.source, folder)
        with self.assertRaises(MigrationError):
            check_task(self.source, folder / 'task.json')
        task = json.loads((folder / 'task.json').read_text())
        task['source_anchors_ref'] = [snapshot(self.source)['files'][0]]
        task['decisions'] = [{'source': 'Int', 'target': 'number', 'constraint': 'exact integer domain must be proven'}]
        (folder / 'mapping.json').write_bytes(json_bytes(task['decisions']))
        task['outputs'] = [{'path': 'mapping.json', 'sha256': digest((folder / 'mapping.json').read_bytes())}]
        (folder / 'task.json').write_bytes(json_bytes(task))
        self.assertTrue(check_task(self.source, folder / 'task.json')['record_valid'])
        (folder / 'mapping.json').write_text('tampered')
        with self.assertRaises(MigrationError):
            check_task(self.source, folder / 'task.json')

    def test_independent_observations_compare_and_reject_missing_or_stale_cases(self):
        target = self.root / 'target'
        target.mkdir()
        (target / 'main.ets').write_text('// fixture target')
        artifacts = self.root / 'capture'
        artifacts.mkdir()
        (artifacts / 'oracle.json').write_bytes(json_bytes({'cases': [{'id': 'counter-1', 'feature_id': 'counter', 'expected': 1}, {'id': 'counter-reset', 'expected': 0}]}))
        bundle = self.root / 'bundle'
        pack(self.source, artifacts, bundle, 'source_tests', 'test fixture (synthetic protocol test)')
        actual = {'target_sha256': snapshot(target)['sha256'], 'cases': [{'id': 'counter-1', 'actual': 1}, {'id': 'counter-reset', 'actual': 0}]}
        observations = self.root / 'observed.json'
        observations.write_bytes(json_bytes(actual))
        result = compare_behavior(self.source, target, bundle, observations, self.root / 'equal')
        self.assertEqual(result['status'], 'observations_equal')
        actual['cases'].pop()
        observations.write_bytes(json_bytes(actual))
        self.assertEqual(compare_behavior(self.source, target, bundle, observations, self.root / 'missing')['status'], 'observations_differ')
        (target / 'main.ets').write_text('// changed')
        with self.assertRaises(MigrationError):
            compare_behavior(self.source, target, bundle, observations, self.root / 'stale')

    def test_feature_coverage_requires_disposition_and_current_outputs(self):
        target = self.root / 'target'
        target.mkdir()
        (target / 'x.ets').write_text('x')
        file = snapshot(self.source)['files'][0]
        features = [{'id': 'f1', 'source_path': file['path'], 'source_sha256': file['sha256']}]
        self.assertFalse(check_coverage(self.source, target, features, {'items': []})['complete'])
        with self.assertRaises(MigrationError):
            check_coverage(self.source, target, features, {'items': [{'feature_id': 'f1', 'status': 'not_applicable'}]})
        coverage = {'items': [{'feature_id': 'f1', 'status': 'implemented', 'outputs': [{'path': 'x.ets', 'sha256': digest(b'x')}]}]}
        self.assertTrue(check_coverage(self.source, target, features, coverage)['complete'])
        (target / 'x.ets').write_text('y')
        with self.assertRaises(MigrationError):
            check_coverage(self.source, target, features, coverage)

    def test_pipeline_rejects_contradictory_or_stale_verification(self):
        run = self.root / 'run'
        initialize(self.source, run)
        source_hash = snapshot(self.source)['sha256']
        feature = json.loads((run / 'plan/features.json').read_text(encoding='utf-8'))['features'][0]
        target = run / 'target'
        target.mkdir()
        (target / 'main.ets').write_text('// synthetic protocol fixture')
        hap = target / 'entry/build/test.hap'
        hap.parent.mkdir(parents=True)
        hap.write_bytes(b'synthetic protocol product')
        target_hash = snapshot(target)['sha256']
        coverage = {'source_sha256': source_hash, 'items': [{'feature_id': feature['id'], 'status': 'implemented',
            'outputs': [{'path': 'main.ets', 'sha256': digest((target / 'main.ets').read_bytes())}]}]}
        (run / 'execute/coverage.json').write_bytes(json_bytes(coverage))
        build = run / 'verify/build'
        build.mkdir(parents=True)
        (build / 'build.json').write_bytes(json_bytes({'status': 'build_passed', 'exit_code': 0,
            'hvigor_success_marker': True, 'source_sha256': source_hash, 'target_after_sha256': target_hash,
            'artifacts': [{'path': 'entry/build/test.hap', 'sha256': digest(hap.read_bytes())}]}))
        compare = run / 'verify/behavior'
        compare.mkdir()
        report = {'status': 'observations_equal', 'source_sha256': source_hash, 'target_sha256': target_hash,
            'cases': [{'id': 'case', 'feature_id': feature['id'], 'passed': True}]}
        (compare / 'comparison.json').write_bytes(json_bytes(report))
        self.assertEqual(pipeline_status(run)['status'], 'in_progress')
        report_path = run / 'retrospect/report.md'
        report_path.parent.mkdir()
        report_path.write_text('  \n', encoding='utf-8')
        self.assertEqual(pipeline_status(run)['stages']['retrospect'], 'pending')
        report_path.write_text('# Synthetic protocol fixture report\n', encoding='utf-8')
        self.assertEqual(pipeline_status(run)['status'], 'ready_for_acceptance_review')
        findings = run / 'verify/findings.json'
        findings.write_bytes(json_bytes({'findings': [{'id': 'unwired-event', 'status': 'open'}]}))
        self.assertEqual(pipeline_status(run)['status'], 'in_progress')
        findings.write_bytes(json_bytes({'findings': [{'id': 'unwired-event', 'status': 'closed'}]}))
        self.assertEqual(pipeline_status(run)['status'], 'ready_for_acceptance_review')
        self.assertFalse(pipeline_status(run)['migration_complete'])
        report['cases'][0]['passed'] = False
        (compare / 'comparison.json').write_bytes(json_bytes(report))
        self.assertEqual(pipeline_status(run)['status'], 'in_progress')
        report['cases'][0]['passed'] = True
        (compare / 'comparison.json').write_bytes(json_bytes(report))
        (target / 'new.ets').write_text('// evidence is now stale')
        self.assertEqual(pipeline_status(run)['status'], 'in_progress')

    def test_cloud_export_relocates_source_and_never_uploads(self):
        source = ROOT / 'tests/fixtures/cloud_counter'
        output = self.root / 'cloud'
        result = prepare(source, ROOT / 'providers/xcode/cloud.example.json', output)
        self.assertFalse(result['upload_performed'])
        self.assertEqual(snapshot(output / 'source')['sha256'], snapshot(source)['sha256'])
        self.assertTrue((output / '.github/workflows/hmigbot-ios.yml').is_file())
        config = json.loads((output / 'cloud-config.json').read_text())
        self.assertEqual(config['source_sha256'], snapshot(source)['sha256'])

    def test_cloud_export_refuses_keys_and_unsafe_project(self):
        source = self.root / 'cloud-source'
        shutil.copytree(ROOT / 'tests/fixtures/cloud_counter', source)
        (source / 'identity.p12').write_bytes(b'not a real key')
        with self.assertRaises(MigrationError):
            prepare(source, ROOT / 'providers/xcode/cloud.example.json', self.root / 'cloud')
        with self.assertRaises(MigrationError):
            validate_config({'project': 'file.txt', 'scheme': 'x', 'configuration': 'Debug', 'runner': 'macos-26'})


class InstallationTests(unittest.TestCase):
    def setUp(self):
        from install_fixture import small_payload
        patcher = small_payload(installer)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.temp = tempfile.TemporaryDirectory(prefix='hmigbot 安装 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_install_upgrade_uninstall_preserves_existing_agents_exactly(self):
        original = b'\xef\xbb\xbf# Existing rules\r\n\r\nPreserve this.\r\n'
        (self.root / 'AGENTS.md').write_bytes(original)
        installed = installer.manage(self.root, 'install')
        self.assertEqual(installed['status'], 'installed')
        runtime = self.root / '.hmigbot-ios/plugin/scripts/ios2harmony.py'
        result = subprocess.run([sys.executable, str(runtime), '--version'], cwd=self.root, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installer.manage(self.root, 'install')['status'], 'upgraded')
        self.assertEqual(installer.manage(self.root, 'uninstall')['status'], 'uninstalled')
        self.assertEqual((self.root / 'AGENTS.md').read_bytes(), original)
        self.assertFalse(runtime.exists())

    def test_install_conflicts_refuse_and_uninstall_preserves_edits(self):
        conflict = self.root / '.agents/skills/ios-source-analysis/SKILL.md'
        conflict.parent.mkdir(parents=True)
        conflict.write_text('user owned')
        with self.assertRaises(ValueError):
            installer.manage(self.root, 'install')
        self.assertFalse((self.root / 'AGENTS.md').exists())
        self.assertEqual(conflict.read_text(), 'user owned')
        conflict.unlink()
        installer.manage(self.root, 'install')
        conflict.write_text('my changed skill')
        with self.assertRaises(ValueError):
            installer.manage(self.root, 'install')
        result = installer.manage(self.root, 'uninstall')
        self.assertEqual(result['status'], 'uninstalled_with_preserved_edits')
        self.assertIn('.agents/skills/ios-source-analysis/SKILL.md', result['preserved'])
        self.assertEqual(conflict.read_text(), 'my changed skill')


if __name__ == '__main__':
    unittest.main()
