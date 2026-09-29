import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "generation_inventory.py"
spec = importlib.util.spec_from_file_location("generation_inventory", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GenerationInventoryTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "project with spaces"
        self.root.mkdir()
        self.feature = {"feature_id": "F001"}
        for key in ("feature_file", "design_file", "generation_file", "test_file"):
            path = self.root / key
            path.write_text("fixture", encoding="utf-8")
            self.feature[key] = str(path)
        self.manifest = {"project_root": str(self.root), "features": [self.feature]}
        self.record = {**self.feature, "cases": [
            {"case_id": "F001_a", "source_ac_ids": ["F001-AC01"], "outcome": "generated", "testability": "ut"},
            {"case_id": "F001_b", "source_ac_ids": ["F001-AC02"], "outcome": "deferred", "testability": "no_entry"},
            {"case_id": "F001_c", "source_ac_ids": ["F001-AC03"], "outcome": "deferred", "testability": "needs_review"}]}
        self.save()

    def save(self):
        Path(self.feature["generation_file"]).write_text(json.dumps(self.record), encoding="utf-8")

    def test_reactivated_case_increases_generated_without_increasing_recorded_total(self):
        before = module.inventory(self.manifest)
        self.record["cases"][1].update(outcome="generated", testability="ut")
        self.save()
        after = module.inventory(self.manifest, ["F001_a", "F001_b"])
        self.assertEqual(before["registered_id_check"]["status"], "not_checked")
        self.assertEqual(after["totals"], {"recorded_logic_count": 3, "generated": 2,
                                          "no_entry": 0, "needs_review": 1})
        self.assertEqual(after["registered_id_check"]["status"], "matched")
        self.assertNotIn("pass", after["totals"])

    def test_new_case_increases_both_recorded_and_generated_totals(self):
        self.record["cases"].append({"case_id": "F001_d", "source_ac_ids": ["F001-AC03"], "outcome": "generated", "testability": "ut"})
        self.save()
        result = module.inventory(self.manifest)
        self.assertEqual(result["totals"]["recorded_logic_count"], 4)
        self.assertEqual(result["totals"]["generated"], 2)

    def test_detects_missing_extra_and_duplicate_actual_ids(self):
        result = module.inventory(self.manifest, ["F001_other", "F001_other"])
        self.assertEqual(result["registered_id_check"], {
            "status": "mismatch", "missing": ["F001_a"],
            "unexpected": ["F001_other"], "duplicates": ["F001_other"]})

    def test_rejects_duplicate_records_and_invalid_classifications(self):
        original = copy.deepcopy(self.record)
        for change in ("duplicate", "classification", "feature"):
            self.record = copy.deepcopy(original)
            if change == "duplicate": self.record["cases"].append(self.record["cases"][0])
            elif change == "classification": self.record["cases"][0]["testability"] = "no_entry"
            else: self.record["feature_id"] = "F002"
            self.save()
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.inventory(self.manifest)

    def test_null_test_file_only_valid_without_generated_cases(self):
        self.record["test_file"] = None
        self.save()
        with self.assertRaisesRegex(ValueError, "require test_file"):
            module.inventory(self.manifest)
        self.record["cases"] = self.record["cases"][1:]
        self.save()
        self.assertEqual(module.inventory(self.manifest, [])["totals"]["generated"], 0)

    def test_rejects_manifest_path_mismatch_and_escape(self):
        self.record["design_file"] = self.feature["feature_file"]
        self.save()
        with self.assertRaisesRegex(ValueError, "differs from dispatch"):
            module.inventory(self.manifest)
        with self.assertRaisesRegex(ValueError, "outside project"):
            module.project_file(self.root, "../outside")

    def test_cli_mismatch_has_nonzero_exit_and_json_diagnostics(self):
        inputs, ids = self.root / "inputs.json", self.root / "ids.json"
        inputs.write_text(json.dumps(self.manifest), encoding="utf-8")
        ids.write_text("[]", encoding="utf-8")
        run = subprocess.run([sys.executable, str(SCRIPT), "--feature-inputs", str(inputs),
                              "--registered-ids", str(ids)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertEqual(json.loads(run.stdout)["registered_id_check"]["missing"], ["F001_a"])

    def test_source_ac_identity_cannot_be_missing_duplicated_or_foreign(self):
        for value in (None, [], ["AC1"], ["F002-AC01"], ["F001-AC01", "F001-AC01"]):
            self.record["cases"][0]["source_ac_ids"] = value
            self.save()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "source_ac_ids"):
                module.inventory(self.manifest)

    def test_generation_cannot_invent_ac_not_in_source_inputs(self):
        self.feature["ac_inputs"] = [{"source_ac_id": "F001-AC01"}, {"source_ac_id": "F001-AC02"}]
        with self.assertRaisesRegex(ValueError, "absent from AC inputs"):
            module.inventory(self.manifest)


if __name__ == "__main__":
    unittest.main()
