"""A complete resource bundle must install when Windows long-path policy is off."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('long_install', ROOT / 'scripts/manage_install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class LongPathTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Win32 extended-path regression')
    def test_install_upgrade_uninstall_resources_beyond_max_path(self):
        with tempfile.TemporaryDirectory(prefix='hmigbot 深路径 ') as temp:
            workspace = Path(temp)
            relative = '.hmigbot-ios/plugin/vendor/hmigbot/' + '/'.join(['resource-' + 'x' * 50] * 5) + '/说明.md'
            self.assertGreater(len(str(workspace / relative)), 260)
            payload = {relative: b'original resource'}
            with patch.object(installer, 'payload', return_value=payload):
                self.assertEqual(installer.manage(workspace, 'install')['status'], 'installed')
                path = installer.filesystem_path(workspace / relative)
                self.assertEqual(path.read_bytes(), b'original resource')
                payload[relative] = b'updated resource'
                self.assertEqual(installer.manage(workspace, 'install')['status'], 'upgraded')
                self.assertEqual(path.read_bytes(), b'updated resource')
                self.assertEqual(installer.manage(workspace, 'uninstall')['status'], 'uninstalled')
                self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
