"""Track-1 unit tests: registry_resolver header-aware parsing + audit guard.

Run:  python -m unittest tests.test_registry_resolver   (cwd = scripts/)
  or: python tests/test_registry_resolver.py

Fixtures cover the two real-world table orders:
  - canonical (a2h-plan template):  P-ID | location | trigger_condition | status | kind | resolve_by
  - drifted   (fitness_v730_login): P-ID | location | trigger_condition | kind | resolve_by | status
plus annotated status cells, strikethrough rows, non-registry P-ID tables,
headerless legacy tables, and the audit_skeletons registry-parse-degraded guard.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from skeleton_lib.registry_resolver import RegistryResolver  # noqa: E402

# Real drifted registry from the project where the incident occurred
FITNESS_REGISTRY = Path(
    r"D:\Coding\Arkts\Workspace\fitness_migration\fitness_v730_login\spec\placeholder-registry.md")

CANONICAL = """# Placeholder Registry

| P-ID | location | trigger_condition | status | kind | resolve_by |
|------|----------|-------------------|--------|------|------------|
| P-S2-001 | entry/src/main/ets/services/EventTrackService.ets#init | 火山引擎 SDK 入仓 | registered | thirdparty-sdk | |
| P-S3-001 | `entry/src/main/ets/pages/SearchPage.ets:128` | Slice 3 Step 3a 确认 | registered | forward-ref-uncertain | Slice 3 Step 3a |
| P-S4-001 | entry/src/main/ets/services/F012Service.ets#stub | Slice 4 Step 3c | resolved | forward-ref | Slice 4 Step 3c |
"""

DRIFTED = """# Placeholder Registry

| P-ID | location | trigger_condition | kind | resolve_by | status |
|---|---|---|---|---|---|
| P-S2-001 | `entry/src/main/ets/services/F016Service.ets#stub` | Slice 2 Step 3c | forward-ref | Slice 2 Step 3c | planned |
| P-S1-008 | `entry/src/main/ets/pages/CSAgreementPage.ets#applyRouteParam_type1` | Slice 2 Step 3c | forward-ref | Slice 2 Step 3c | emitted（🔴 2026-07-23 更正：Stage-1 converter 误标） |
| P-S4-022 | `entry/src/main/ets/network/AuthRequestUtil.ets#privateKey` | 集成期·密钥注入 | forward-ref | 集成期·密钥注入 | emitted 🔴 |
| ~~P-S1-011~~ | ~~`entry/src/main/ets/preferences/PrefsStore.ets#attach`~~ | — | forward-ref | — | **resolved**（2026-07-22 Base-5 收尾） |

## 延期记录（不是注册表——不得被解析进 registry）

| P-ID | defer_until | reason | approved_by |
|------|-------------|--------|-------------|
| P-S9-999 | 2026-08-01 | 等 SDK | D-001 |
"""

HEADERLESS_LEGACY = """| P-S5-001 | entry/src/main/ets/a.ets#x | Slice 5 Step 3c | registered | forward-ref | Slice 5 Step 3c |
"""


def _load(md: str) -> RegistryResolver:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "placeholder-registry.md"
        p.write_text(md, encoding="utf-8")
        return RegistryResolver(registry_path=p)


class TestCanonicalOrder(unittest.TestCase):
    def setUp(self):
        self.r = _load(CANONICAL)

    def test_rows_loaded(self):
        self.assertEqual(self.r.rows_loaded, 3)

    def test_fields(self):
        e = self.r.get_entry("P-S2-001")
        self.assertEqual(e["kind"], "thirdparty-sdk")
        self.assertEqual(e["status"], "registered")
        self.assertTrue(self.r.is_sdk_placeholder_registered("P-S2-001"))

    def test_location_backticks_stripped(self):
        e = self.r.get_entry("P-S3-001")
        self.assertEqual(e["location"], "entry/src/main/ets/pages/SearchPage.ets:128")

    def test_resolved_query(self):
        self.assertTrue(self.r.is_fwd_ref_resolved("P-S4-001"))
        self.assertNotIn("P-S4-001", self.r.all_unresolved_fwd_refs())


class TestDriftedOrder(unittest.TestCase):
    """The fitness_v730_login order (status last) must load identically."""

    def setUp(self):
        self.r = _load(DRIFTED)

    def test_rows_loaded_excludes_defer_table(self):
        self.assertEqual(self.r.rows_loaded, 4)
        self.assertIsNone(self.r.get_entry("P-S9-999"))

    def test_status_kind_not_swapped(self):
        e = self.r.get_entry("P-S2-001")
        self.assertEqual(e["kind"], "forward-ref")
        self.assertEqual(e["status"], "planned")
        self.assertTrue(self.r.is_fwd_ref_known("P-S2-001"))

    def test_annotated_status_normalized(self):
        self.assertEqual(self.r.get_entry("P-S1-008")["status"], "emitted")
        self.assertEqual(self.r.get_entry("P-S4-022")["status"], "emitted")

    def test_strikethrough_resolved_row(self):
        e = self.r.get_entry("P-S1-011")
        self.assertEqual(e["status"], "resolved")
        self.assertTrue(self.r.is_fwd_ref_resolved("P-S1-011"))
        self.assertNotIn("P-S1-011", self.r.all_unresolved_fwd_refs())

    def test_unresolved_set(self):
        self.assertEqual(set(self.r.all_unresolved_fwd_refs()),
                         {"P-S2-001", "P-S1-008", "P-S4-022"})


class TestHeaderlessLegacy(unittest.TestCase):
    def test_positional_fallback(self):
        r = _load(HEADERLESS_LEGACY)
        self.assertEqual(r.rows_loaded, 1)
        e = r.get_entry("P-S5-001")
        self.assertEqual(e["kind"], "forward-ref")
        self.assertEqual(e["status"], "registered")


class TestRealFitnessRegistry(unittest.TestCase):
    """Regression against the actual file that previously loaded 0 rows."""

    def setUp(self):
        if not FITNESS_REGISTRY.exists():
            self.skipTest("fitness_v730_login registry not present on this machine")
        self.r = RegistryResolver(registry_path=FITNESS_REGISTRY)

    def test_rows_loaded(self):
        self.assertGreaterEqual(self.r.rows_loaded, 40)

    def test_spot_checks(self):
        self.assertTrue(self.r.is_fwd_ref_known("P-S2-001"))
        self.assertEqual(self.r.get_entry("P-S2-001")["status"], "planned")
        self.assertEqual(self.r.get_entry("P-S1-008")["status"], "emitted")
        self.assertTrue(self.r.is_fwd_ref_resolved("P-S1-011"))


class TestAuditDegradedGuard(unittest.TestCase):
    """audit_skeletons CLI: unparseable registry with P-ID rows → exactly ONE
    registry-parse-degraded FAIL, zero dangling-fwd-ref findings."""

    def test_guard(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            # Table with P-ID data rows but a header the parser can't map to
            # the registry schema (no location/kind), and too few columns for
            # the legacy positional fallback → 0 rows loaded.
            (root / "spec" / "placeholder-registry.md").write_text(
                "| P-ID | foo | bar |\n|---|---|---|\n| P-X-001 | a | b |\n",
                encoding="utf-8")
            ets = root / "entry" / "src" / "main" / "ets" / "pages"
            ets.mkdir(parents=True)
            (ets / "APage.ets").write_text(
                "// FWD-REF: P-X-001 resolve_by=Slice 2 Step 3c\n"
                "export class APage {}\n", encoding="utf-8")
            out_json = root / "audit.json"
            res = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "audit_skeletons.py"),
                 "--project-root", str(root), "--scope", "all",
                 "--output-json", str(out_json)],
                capture_output=True, text=True)
            self.assertEqual(res.returncode, 1)  # FAIL present (the guard)
            data = json.loads(out_json.read_text(encoding="utf-8"))
            subtypes = [f["subtype"] for f in data["findings"]]
            self.assertEqual(subtypes.count("registry-parse-degraded"), 1)
            self.assertEqual(subtypes.count("dangling-fwd-ref"), 0)
            self.assertTrue(data["registry_parse_degraded"])
            self.assertEqual(data["registry_rows_loaded"], 0)

    def test_no_guard_on_healthy_registry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "spec").mkdir()
            (root / "spec" / "placeholder-registry.md").write_text(CANONICAL, encoding="utf-8")
            ets = root / "entry" / "src" / "main" / "ets" / "pages"
            ets.mkdir(parents=True)
            # Marker NOT in registry → genuine dangling finding must still fire
            (ets / "BPage.ets").write_text(
                "// FWD-REF: P-NOPE-001 resolve_by=Slice 2 Step 3c\n"
                "export class BPage {}\n", encoding="utf-8")
            out_json = root / "audit.json"
            res = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "audit_skeletons.py"),
                 "--project-root", str(root), "--scope", "all",
                 "--output-json", str(out_json)],
                capture_output=True, text=True)
            self.assertEqual(res.returncode, 1)
            data = json.loads(out_json.read_text(encoding="utf-8"))
            subtypes = [f["subtype"] for f in data["findings"]]
            self.assertEqual(subtypes.count("registry-parse-degraded"), 0)
            self.assertEqual(subtypes.count("dangling-fwd-ref"), 1)
            self.assertEqual(data["registry_rows_loaded"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
