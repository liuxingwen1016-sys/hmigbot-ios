import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("feature_inputs", Path(__file__).parents[1] / "feature_inputs.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FeatureInputsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project with spaces"
        self.features = self.root / "spec/baseline/features"
        self.features.mkdir(parents=True)

    def add(self, name):
        path = self.features / name
        path.write_text("# Feature\n", encoding="utf-8")
        return path.resolve()

    def test_resolves_both_naming_styles_and_keeps_real_name(self):
        first = self.add("F001-app-bootstrap.md")
        second = self.add("F009_document_import.md")
        result = module.resolve_features(self.root)["features"]
        self.assertEqual([row["feature_file"] for row in result], [str(first), str(second)])
        self.assertEqual(Path(result[0]["design_file"]).name, "F001_app_bootstrap.md")
        self.assertEqual(Path(result[1]["test_file"]).name, "F009_document_import.test.ets")
        self.assertTrue(all(Path(value).is_absolute() for row in result for key, value in row.items() if key.endswith("_file")))

    def test_duplicate_id_fails_instead_of_selecting_first(self):
        self.add("F001-one.md")
        self.add("F001_two.md")
        with self.assertRaisesRegex(ValueError, "Duplicate Feature F001"):
            module.resolve_features(self.root)

    def test_scope_is_exact_and_deduplicated(self):
        self.add("F001-one.md")
        self.add("F010-ten.md")
        rows = module.resolve_features(self.root, "F010,F010,F001")["features"]
        self.assertEqual([row["feature_id"] for row in rows], ["F010", "F001"])
        with self.assertRaisesRegex(ValueError, "Missing Feature specs"):
            module.resolve_features(self.root, "F01")

    def test_missing_specs_and_invalid_scope_fail(self):
        with self.assertRaisesRegex(ValueError, "No Feature specs"):
            module.resolve_features(self.root)
        self.add("F001-one.md")
        for scope in ("F001-one", "", " , "):
            with self.subTest(scope=scope), self.assertRaisesRegex(ValueError, "exact Feature IDs"):
                module.resolve_features(self.root, scope)

    def test_addenda_are_related_inputs_not_duplicate_features(self):
        main = self.add("F001-sync.md")
        addendum = self.add("F001-sync.state-machine.md")
        row = module.resolve_features(self.root)["features"][0]
        self.assertEqual(row["feature_file"], str(main))
        self.assertEqual(row["addendum_files"], [str(addendum)])
        self.assertEqual(Path(row["test_file"]).name, "F001_sync.test.ets")

    def test_scope_does_not_validate_other_feature_duplicates(self):
        self.add("F001-one.md")
        self.add("F002-two.md")
        self.add("F002_duplicate.md")
        rows = module.resolve_features(self.root, "F001")["features"]
        self.assertEqual(len(rows), 1)
        with self.assertRaisesRegex(ValueError, "Duplicate Feature F002"):
            module.resolve_features(self.root)

    def test_orphan_addendum_is_not_a_main_spec(self):
        self.add("F001-sync.state-machine.md")
        with self.assertRaisesRegex(ValueError, "No Feature specs"):
            module.resolve_features(self.root)

    def test_mismatched_addendum_stem_fails_in_selected_scope(self):
        self.add("F001-sync.md")
        self.add("F001-old.state-machine.md")
        with self.assertRaisesRegex(ValueError, "Addendum does not match"):
            module.resolve_features(self.root)


if __name__ == "__main__":
    unittest.main()
