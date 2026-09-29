import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hmigbot_ios.core import MigrationError, load_config, resolve_anchors, safe_child, snapshot, write_json, write_new_tree
from hmigbot_ios.environment import preflight


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def config(self, data):
        path = self.root / "config.json"
        write_json(path, data)
        return load_config(path)

    def test_legacy_android_roundtrip(self):
        value = self.config({"android": "android", "harmonyos": "harmony", "telemetry_consent": False})
        self.assertEqual(value["source"]["platform"], "android")
        self.assertFalse(value["telemetry_consent"])
        self.assertEqual(preflight(value, "scan")["status"], "delegate_android")

    def test_modern_ios_no_android_device_dependency(self):
        (self.root / "ios").mkdir()
        value = self.config({"source": {"platform": "ios", "root": "ios"},
                             "target": {"platform": "harmonyos", "root": "harmony"}})
        result = preflight(value, "scan")
        self.assertEqual(result["status"], "ready_to_attempt")
        self.assertEqual([c["name"] for c in result["checks"]], ["source_directory"])

    def test_conflicting_legacy_and_modern_config(self):
        with self.assertRaises(MigrationError):
            self.config({"android": "a", "source": {"platform": "ios", "root": "b"}, "harmonyos": "c"})

    def test_overlap_and_schema_rejected(self):
        for raw in [{"android": "a", "harmonyos": "a/out"},
                    {"schema_version": 999, "android": "a", "harmonyos": "b"}]:
            with self.subTest(raw=raw), self.assertRaises(MigrationError):
                self.config(raw)

    def test_duplicate_keys_are_not_silently_overwritten(self):
        path = self.root / "config.json"
        path.write_text('{"android":"a","android":"b","harmonyos":"c"}')
        with self.assertRaises(MigrationError):
            load_config(path)

    def test_anchors_conflict_and_ios_cannot_use_android_alias(self):
        self.assertEqual(resolve_anchors({"android_source_anchors_ref": [1]}), [1])
        for record in [{"source_anchors_ref": [1], "android_source_anchors_ref": [2]},
                       {"source_platform": "ios", "android_source_anchors_ref": [1]}]:
            with self.assertRaises(MigrationError):
                resolve_anchors(record)

    def test_fingerprint_changes_for_assets_and_renames(self):
        (self.root / "Main.swift").write_text("struct Model {}")
        (self.root / "asset.png").write_bytes(b"one")
        before = snapshot(self.root)["sha256"]
        (self.root / "asset.png").write_bytes(b"two")
        self.assertNotEqual(before, snapshot(self.root)["sha256"])
        before = snapshot(self.root)["sha256"]
        (self.root / "Main.swift").rename(self.root / "Other.swift")
        self.assertNotEqual(before, snapshot(self.root)["sha256"])

    def test_path_traversal_and_absolute_paths(self):
        for name in ["../escape", "a/../../escape", "C:/escape", "/absolute", "a\\..\\b", ""]:
            with self.subTest(name=name), self.assertRaises(MigrationError):
                safe_child(self.root, name)

    def test_existing_output_is_preserved(self):
        output = self.root / "out"
        write_new_tree(output, {"user.txt": b"keep"})
        with self.assertRaises(MigrationError):
            write_new_tree(output, {"user.txt": b"replace"})
        self.assertEqual((output / "user.txt").read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
