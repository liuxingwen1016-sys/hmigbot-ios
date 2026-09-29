import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("ac_inputs", Path(__file__).parents[1] / "ac_inputs.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AcInputsTest(unittest.TestCase):
    def extract(self, text):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "F001-sync.md"
            path.write_text(text, encoding="utf-8")
            return module.extract_acs(path, "F001")

    def test_checked_unchecked_and_sparse_ids_keep_identity(self):
        rows = self.extract("## 验收标准\n- [x] F001-AC09 已完成\n- [ ] F001-AC02 待实现\n- [X] F001-AC17 已实现\n")
        self.assertEqual([r["source_ac_id"] for r in rows], ["F001-AC09", "F001-AC02", "F001-AC17"])
        self.assertEqual([r["case_prefix"] for r in rows], ["F001_AC09", "F001_AC02", "F001_AC17"])
        self.assertEqual([r["checked"] for r in rows], [True, False, True])

    def test_fenced_examples_and_other_sections_are_not_acs(self):
        rows = self.extract("- [ ] F001-AC99 前置\n## 验收标准\n```md\n- [ ] F001-AC88 示例\n```\n### 状态\n- [x] F001-AC03 保存\n## 其它\n- [ ] F001-AC77 附录\n")
        self.assertEqual([r["source_ac_id"] for r in rows], ["F001-AC03"])

    def test_missing_duplicate_or_foreign_ids_fail_without_renumbering(self):
        for body in ("- [ ] 缺 ID", "- [ ] F002-AC01 错 Feature", "- [x] F001-AC01 A\n- [ ] F001-AC01 B"):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.extract("## 验收标准\n" + body)

    def test_reordering_does_not_change_case_prefix(self):
        before = self.extract("## 验收标准\n- [ ] F001-AC07 A\n- [ ] F001-AC03 B\n")
        after = self.extract("## 验收标准\n- [x] F001-AC03 B\n- [x] F001-AC07 A\n")
        self.assertEqual({r["text"]: r["case_prefix"] for r in before}, {r["text"]: r["case_prefix"] for r in after})
