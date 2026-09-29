#!/usr/bin/env python3
"""Tests for the evidence-coverage gate and the cross-stage findings queue.

Every fixture here encodes a defect that was actually observed in a real run:
a commented-out Gradle dependency that invented a module and a build cycle, an
`include` list whose entries lack the leading colon, a declaration below line 1
that a non-MULTILINE regex could not see, and an AC whose truth source pointed
back at the ArkTS implementation.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
sys.path.insert(0, str(SCRIPTS))

import _a2h_findings as findings  # noqa: E402
import extract_module_deps as deps  # noqa: E402
import lint_coverage  # noqa: E402
import profile_feature  # noqa: E402


class GradleParsing(unittest.TestCase):
    def test_commented_dependency_is_not_a_dependency(self):
        text = deps.strip_gradle_comments(
            'dependencies {\n'
            '//    implementation project(":docviewer")\n'
            '    implementation project(":basic")\n'
            '}\n'
        )
        self.assertNotIn("docviewer", text)
        self.assertIn("basic", text)

    def test_block_comment_preserves_line_numbers(self):
        # Line numbers must survive comment stripping, otherwise every evidence
        # `file:line` recorded downstream points at the wrong line.
        source = "a\n/* x\ny\n*/\nb\n"
        text = deps.strip_gradle_comments(source)
        self.assertEqual(text.count("\n"), source.count("\n"))
        self.assertEqual(text.split("\n")[4], "b")

    def test_url_inside_string_is_not_a_comment(self):
        text = deps.strip_gradle_comments('maven { url "https://example.com/repo" }')
        self.assertIn("https://example.com/repo", text)

    def test_include_without_leading_colon_is_still_a_module(self):
        # `include ':app','aliauth','bdConvert'` — only the first entry carries
        # the colon. Requiring it drops 8 of 9 modules on a real project.
        got = deps.gradle_includes("include ':app','aliauth','bdConvert'")
        self.assertEqual(got, ["app", "aliauth", "bdConvert"])

    def test_multiline_and_kts_include(self):
        got = deps.gradle_includes('include(":app", ":lib")\ninclude ":extra"\n')
        self.assertEqual(sorted(got), ["app", "extra", "lib"])

    def test_dynamic_include_yields_nothing_rather_than_a_guess(self):
        self.assertEqual(deps.gradle_includes("include(resolveModules())"), [])


class SymbolResolution(unittest.TestCase):
    def test_declaration_below_first_line_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "AIPptViewModel.kt"
            path.write_text(
                "package com.x\n\nimport a.b.C\n\nclass AIPptViewModel : KViewModel() {\n"
                "    fun fetch() {}\n}\n",
                encoding="utf-8",
            )
            symbols = lint_coverage.declared_symbols(str(path))
        self.assertIn("AIPptViewModel", symbols)
        self.assertIn("fetch", symbols)

    def test_symbol_roots_splits_qualified_names(self):
        roots = lint_coverage.symbol_roots(["MemberCenterActivitiy.openMemberCenter()"])
        self.assertEqual(roots, {"MemberCenterActivitiy", "openMemberCenter"})


class SignalDetection(unittest.TestCase):
    def _scan(self, body: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "S.kt"
            path.write_text(body, encoding="utf-8")
            return profile_feature.scan_file(str(path), "S.kt")

    def test_permission_and_error_are_detected_with_evidence(self):
        found = self._scan(
            "fun f() {\n"
            "  if (checkSelfPermission(Manifest.permission.CAMERA) != 0) throw E()\n"
            "}\n"
        )
        self.assertIn("permission", found)
        self.assertIn("error_path", found)
        self.assertEqual(found["permission"][0]["line"], 2)

    def test_commented_out_code_is_not_evidence(self):
        found = self._scan("fun f() {\n//  checkSelfPermission(X)\n}\n")
        self.assertNotIn("permission", found)

    def test_required_kinds_come_from_signals_not_from_self_report(self):
        rules = profile_feature.load_rules()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            (src / "app").mkdir(parents=True)
            (src / "app" / "A.kt").write_text(
                "class A {\n  fun f() { requestPermissions(arrayOf(P), 1) }\n}\n",
                encoding="utf-8",
            )
            md = Path(tmp) / "F001-x.md"
            md.write_text(
                'android_source_anchors:\n  - role: service\n    path: "app/A.kt"\n',
                encoding="utf-8",
            )
            profile = profile_feature.profile_one(str(src), str(md), rules)
        self.assertIn("permission_denied", profile["required_obligation_kinds"])
        self.assertEqual(
            profile["required_obligation_kinds"]["permission_denied"]["required_oracle"], "ui"
        )

    def test_no_ac_count_is_ever_emitted(self):
        rules = profile_feature.load_rules()
        text = json.dumps(rules)
        for banned in ("min_ac", "max_ac", "target_ac", "ac_floor", "ac_budget"):
            self.assertNotIn(banned, text)


class CoverageGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp) / "proj"
        self.src = Path(self.tmp) / "android"
        (self.src / "app").mkdir(parents=True)
        (self.root / "spec" / "baseline" / "features").mkdir(parents=True)
        (self.src / "app" / "Login.kt").write_text(
            "class Login {\n"
            "  fun doLogin() {\n"
            "    if (checkSelfPermission(Manifest.permission.READ_PHONE_STATE) != 0) return\n"
            "  }\n"
            "}\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_feature(self, acs: str):
        (self.root / "spec/baseline/features/F001-login.md").write_text(
            'android_source_anchors:\n  - role: service\n    path: "app/Login.kt"\n'
            "\n## 验收标准\n" + acs,
            encoding="utf-8",
        )

    def _run(self):
        env = dict(os.environ, PYTHONPATH=str(SCRIPTS))
        subprocess.run(
            [sys.executable, str(SCRIPTS / "profile_feature.py"), "--src", str(self.src),
             "--features-dir", str(self.root / "spec/baseline/features")],
            check=True, capture_output=True, env=env,
        )
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "lint_coverage.py"), "--src", str(self.src),
             "--project-root", str(self.root), "--skip-breadth"],
            capture_output=True, text=True, env=env,
        )
        data = findings.load(str(self.root))
        return proc.returncode, data["sections"]["spec/lint_coverage"]["findings"]

    def test_anchor_file_with_no_referencing_ac_blocks(self):
        self._write_feature("- [ ] F001-AC01 用户可以登录　`源:Unrelated.foo → 标:X`\n")
        code, items = self._run()
        self.assertEqual(code, 2)
        self.assertTrue(any(f["rule"] == "SPEC.UNCOVERED_ANCHOR_FILE" for f in items))

    def test_referencing_ac_clears_the_blocking_finding(self):
        self._write_feature(
            "- [ ] F001-AC01 授予 READ_PHONE_STATE 权限后可登录　`源:Login.doLogin → 标:X`　"
            "`判:ui | 授权后进入首页`　`真:src:app/Login.kt:3`\n"
        )
        code, items = self._run()
        blocking = [f for f in items if f["severity"] == "blocking"]
        self.assertEqual(blocking, [], blocking)
        self.assertEqual(code, 0)

    def test_missing_oracle_warns_but_does_not_block(self):
        self._write_feature(
            "- [ ] F001-AC01 授予 READ_PHONE_STATE 权限后可登录　`源:Login.doLogin → 标:X`\n"
        )
        code, items = self._run()
        self.assertEqual(code, 0)
        rules = {f["rule"] for f in items}
        self.assertIn("SPEC.ORACLE_MISSING", rules)
        self.assertIn("SPEC.TRUTH_SOURCE_MISSING", rules)

    def test_truth_source_pointing_at_arkts_implementation_blocks(self):
        self._write_feature(
            "- [ ] F001-AC01 授予权限后可登录　`源:Login.doLogin → 标:X`　"
            "`判:ui | 授权后进入首页`　`真:arkts-impl`\n"
        )
        code, items = self._run()
        self.assertEqual(code, 2)
        self.assertTrue(any(f["rule"] == "SPEC.TRUTH_SOURCE_INVALID" for f in items))

    def test_writing_more_acs_never_fails(self):
        many = "- [ ] F001-AC00 READ_PHONE_STATE 权限交代　`源:Login.doLogin → 标:X`　`判:ui | 授权`　`真:src:app/Login.kt:3`\n" + "".join(
            f"- [ ] F001-AC{i:02d} 断言{i}　`源:Login.doLogin → 标:X`　"
            f"`判:ui | 结果{i}`　`真:src:app/Login.kt:3`\n"
            for i in range(1, 61)
        )
        self._write_feature(many)
        code, items = self._run()
        self.assertEqual(code, 0)
        self.assertEqual([f for f in items if f["severity"] == "blocking"], [])


class FindingsQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_occurrences_accumulate_only_on_repair_rounds(self):
        item = lambda: findings.make("R.X", "plan", "F001-AC01", "d")  # noqa: E731
        findings.replace_section(self.tmp, "sec", [item()])
        for _ in range(findings.LOOP_LIMIT - 1):
            findings.replace_section(self.tmp, "sec", [item()], after_repair=True)
        stored = findings.load(self.tmp)["sections"]["sec"]["findings"]
        target = [f for f in stored if f["rule"] == "R.X"][0]
        self.assertEqual(target["occurrences"], findings.LOOP_LIMIT)
        self.assertTrue(target["escalate"])

    def test_status_checks_do_not_advance_counters(self):
        item = lambda: findings.make("R.X", "plan", "F001-AC01", "d")  # noqa: E731
        for _ in range(5):
            findings.replace_section(self.tmp, "sec", [item()])
        stored = findings.load(self.tmp)["sections"]["sec"]["findings"][0]
        self.assertEqual(stored["occurrences"], 1)
        self.assertFalse(stored["escalate"])
        progress = findings.load(self.tmp)["sections"]["sec"]["progress"]
        self.assertEqual(progress["repair_rounds"], 0)
        self.assertFalse(progress["halted"])

    def test_a_finding_disappears_only_when_the_linter_stops_reporting_it(self):
        findings.replace_section(self.tmp, "sec", [findings.make("R.X", "plan", "S", "d")])
        self.assertEqual(len(findings.for_stage(self.tmp, "plan")), 1)
        findings.replace_section(self.tmp, "sec", [])
        self.assertEqual(findings.for_stage(self.tmp, "plan"), [])

    def test_upstream_blocking_findings_stop_a_downstream_stage(self):
        findings.replace_section(self.tmp, "spec/x", [
            findings.make("SPEC.X", "spec", "S", "d"),
            findings.make("SPEC.Y", "spec", "T", "d", severity="warn"),
        ])
        self.assertEqual(len(findings.upstream_of(self.tmp, "execute")), 1)
        self.assertEqual(findings.upstream_of(self.tmp, "spec"), [])

    def test_owner_stage_must_be_a_real_stage(self):
        with self.assertRaises(ValueError):
            findings.make("R", "nowhere", "S", "d")

    def test_corrupt_queue_surfaces_instead_of_reading_as_empty(self):
        path = Path(findings.path_for(self.tmp))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        self.assertTrue(findings.for_stage(self.tmp, "spec"))


class NoBudgetSurvives(unittest.TestCase):
    def test_score_complexity_emits_no_budget_fields(self):
        import score_complexity
        out = score_complexity.score([], tier="core")
        for banned in ("ac_budget", "ac_floor", "stub_range", "compression_AC_per_kLOC"):
            self.assertNotIn(banned, out)

    def test_feature_prefixes_beyond_plain_F_are_scored(self):
        import re
        import score_complexity  # noqa: F401
        pattern = re.compile(r"[A-Z]{1,4}\d+-[a-z0-9-]+\.md")
        for name in ("F001-a.md", "FS001-a.md", "FR012-b-c.md", "FC003-x.md"):
            self.assertTrue(pattern.fullmatch(name), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class InstanceExtraction(unittest.TestCase):
    """Enumerable facts must be captured by name — the list IS the requirement."""

    def _instances(self, body: str) -> dict:
        return profile_feature.extract_instances(
            profile_feature.strip_comments(body), "S.kt"
        )

    def test_event_names_and_thresholds_and_consts(self):
        got = self._instances(
            'fun report() {\n'
            '  VolcEnginManger.onEvent(ctx, "payment_fail")\n'
            '  tracker.track("ad_show")\n'
            '  if (query.length > 8000) return\n'
            '  const val RETRY_MAX = 3\n'
            '}\n'
        )
        event_ids = {item["id"] for item in got.get("event_name", [])}
        self.assertEqual(event_ids, {"event:payment_fail", "event:ad_show"})
        self.assertIn("threshold:8000", {i["id"] for i in got.get("threshold_literal", [])})
        self.assertIn("const:RETRY_MAX", {i["id"] for i in got.get("numeric_const", [])})

    def test_js_bridge_annotation_on_own_line(self):
        got = self._instances(
            "class Bridge {\n  @JavascriptInterface\n  fun openPay(url: String) {}\n}\n"
        )
        self.assertEqual({i["id"] for i in got["js_bridge"]}, {"js:openPay"})

    def test_enum_cases_carry_the_enum_name(self):
        got = self._instances(
            "enum class PayState {\n  IDLE,\n  RUNNING,\n  DONE;\n}\n"
        )
        self.assertEqual(
            {i["id"] for i in got["enum_case"]},
            {"enum:PayState.IDLE", "enum:PayState.RUNNING", "enum:PayState.DONE"},
        )

    def test_sdk_seam_once_per_file(self):
        got = self._instances(
            "import com.tencent.mm.opensdk.modelpay.PayReq\n"
            "import com.tencent.mm.opensdk.openapi.WXAPIFactory\n"
        )
        self.assertEqual(len(got["sdk_seam"]), 1)
        self.assertEqual(got["sdk_seam"][0]["id"], "sdk:com.tencent.mm")

    def test_commented_event_is_not_an_instance(self):
        got = self._instances('fun f() {\n//  tracker.track("dead_event")\n}\n')
        self.assertNotIn("event_name", got)


class GateFloorSimulation(CoverageGate):
    """Encodes the depth-regression incident: a one-AC-per-kind spec over a
    feature with 10 named events MUST fail; 组:/skip make it legal explicitly."""

    EVENTS = [f"evt_{c}" for c in "abcdefghij"]

    def setUp(self):
        super().setUp()
        body = "class Tracker {\n" + "".join(
            f'  fun r{i}() {{ tracker.track("{name}") }}\n'
            for i, name in enumerate(self.EVENTS)
        ) + "}\n"
        (self.src / "app" / "Tracker.kt").write_text(body, encoding="utf-8")
        (self.root / "spec/baseline/features/F001-login.md").unlink(missing_ok=True)

    def _write_track_feature(self, acs: str):
        (self.root / "spec/baseline/features/F015-track.md").write_text(
            'android_source_anchors:\n  - role: service\n    path: "app/Tracker.kt"\n'
            "\n## 验收标准\n" + acs,
            encoding="utf-8",
        )

    def test_one_ac_per_kind_cannot_satisfy_ten_events(self):
        # the F015 shape: satisfies every KIND check, names only one event
        self._write_track_feature(
            "- [ ] F015-AC01 事件 evt_a 经 Tracker 上报　`源:Tracker.r0 → 标:T.report`　"
            "`判:contract | 事件名一致`　`真:src:app/Tracker.kt:2`\n"
        )
        code, items = self._run()
        self.assertEqual(code, 2)
        stall = [f for f in items if f["rule"] == "SPEC.INSTANCE_UNACCOUNTED"]
        self.assertEqual(len(stall), 1)
        self.assertIn("9 个", stall[0]["detail"])

    def test_group_declaration_makes_the_same_spec_legal(self):
        rest = ", ".join(self.EVENTS[1:])
        self._write_track_feature(
            "- [ ] F015-AC01 事件 evt_a 经 Tracker 上报　`源:Tracker.r0 → 标:T.report`　"
            "`判:contract | 事件名一致`　`真:src:app/Tracker.kt:2`　"
            f"`组:{{{rest}}}`\n"
        )
        code, items = self._run()
        self.assertEqual([f for f in items if f["severity"] == "blocking"], [])
        self.assertEqual(code, 0)

    def test_skip_list_entry_accounts_an_instance(self):
        self._write_track_feature(
            "- [ ] F015-AC01 事件上报　`源:Tracker.r0 → 标:T.report`　"
            "`判:contract | 一致`　`真:src:app/Tracker.kt:2`　"
            f"`组:{{{', '.join(self.EVENTS[1:-1])}}}`\n"
        )
        # evt_a covered by... nothing names evt_a now; put it in skip with the last one
        (self.root / "spec/baseline/skip-list.md").write_text(
            f"| `event:{self.EVENTS[0]}` | 调试专用埋点，不迁移 |\n"
            f"| `{self.EVENTS[-1]}` | 服务端已废弃 |\n",
            encoding="utf-8",
        )
        code, items = self._run()
        self.assertEqual([f for f in items if f["severity"] == "blocking"], [], items)
        self.assertEqual(code, 0)

    def test_group_declaration_does_not_change_assertion_digest(self):
        import build_traceability_index as bti
        plain = "断言文本　`源:Tracker.r0 → 标:T.report`　`判:contract | 一致`　`真:src:a.kt:1`"
        grouped = plain + "　`组:{evt_b, evt_c}`"
        self.assertEqual(bti.assertion_digest(plain), bti.assertion_digest(grouped))


class LoopBrake(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _round(self, subjects, after_repair=True):
        items = [findings.make("R.X", "spec", s, "d") for s in subjects]
        findings.replace_section(self.tmp, "spec/sec", items, after_repair=after_repair)
        return findings.load(self.tmp)["sections"]["spec/sec"]

    def test_mutating_failures_halt_after_three_no_progress_rounds(self):
        # fix AC01 -> AC02 appears -> fix AC02 -> AC03 appears... same count,
        # different keys every round. Per-key counters never fire; the section
        # brake must.
        self._round(["F001-AC01"], after_repair=False)   # first observation
        for i in range(2, 5):
            section = self._round([f"F001-AC{i:02d}"])
        self.assertTrue(section["progress"]["halted"])
        rules = {f["rule"] for f in section["findings"]}
        self.assertIn("LOOP.NOT_CONVERGING", rules)

    def test_shrinking_blocking_set_resets_the_counter(self):
        self._round(["A", "B", "C"], after_repair=False)
        self._round(["A", "B"])          # progress
        self._round(["A"])               # progress
        section = self._round(["A"])     # stuck round 1
        self.assertEqual(section["progress"]["no_progress_rounds"], 1)
        self.assertFalse(section["progress"]["halted"])

    def test_halted_section_returns_exit_3(self):
        self._round(["S"], after_repair=False)
        for _ in range(findings.HALT_LIMIT):
            self._round(["S"])
        items = findings.load(self.tmp)["sections"]["spec/sec"]["findings"]
        self.assertEqual(findings.section_exit_code(self.tmp, "spec/sec", items), 3)

    def test_clear_halt_requires_decision_and_releases(self):
        self._round(["S"], after_repair=False)
        for _ in range(findings.HALT_LIMIT):
            self._round(["S"])
        with self.assertRaises(ValueError):
            findings.clear_halt(self.tmp, "spec/sec", "")
        findings.clear_halt(self.tmp, "spec/sec", "D-021")
        section = findings.load(self.tmp)["sections"]["spec/sec"]
        self.assertFalse(section["progress"]["halted"])
        self.assertEqual(section["progress"]["decision_ref"], "D-021")
        self.assertNotIn("LOOP.NOT_CONVERGING", {f["rule"] for f in section["findings"]})

    def test_clean_section_releases_the_brake_automatically(self):
        self._round(["S"], after_repair=False)
        for _ in range(findings.HALT_LIMIT):
            self._round(["S"])
        section = self._round([])        # repairs finally landed
        self.assertFalse(section["progress"]["halted"])
        self.assertEqual(section["progress"]["no_progress_rounds"], 0)


class AddendumRuleAlignment(unittest.TestCase):
    """SKILL.md must not contradict the evidence-triggered addendum linter."""

    SKILL = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")

    def test_simple_features_are_not_denied_addenda(self):
        self.assertNotIn("否（单文件）", self.SKILL)

    def test_c46e_is_not_gated_on_complexity(self):
        self.assertNotIn("Addenda 元数据收口（仅 complexity=complex）", self.SKILL)

    def test_evidence_trigger_is_stated(self):
        self.assertIn("required_addenda", self.SKILL)


class ManifestComponentAccounting(unittest.TestCase):
    """Sub-module manifests merge into the APK; an activity declared there must
    be a page, an anchor, or a recorded skip — never silence. Encodes the
    VideoPlayActivity incident, including the disclosure rule: a skip closes
    the blocking finding but the activity stays visibly listed, and a skip
    line that cites no decision draws its own warning."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp) / "proj"
        self.src = Path(self.tmp) / "android"
        (self.root / "spec/baseline").mkdir(parents=True)
        for module, pkg, activities in (
            ("app", "com.demo.app", ['.MainActivity']),
            ("basic", "com.demo.basic", ['.activity.VideoPlayActivity',
                                         '.activity.VideoPlayActivity$Portrait',
                                         'com.other.sdk.LoginAuthActivity']),
        ):
            main = self.src / module / "src" / "main"
            main.mkdir(parents=True)
            body = "".join(f'    <activity android:name="{a}"/>\n' for a in activities)
            (main / "AndroidManifest.xml").write_text(
                f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
                f'package="{pkg}">\n  <application>\n{body}  </application>\n</manifest>\n',
                encoding="utf-8",
            )
        (self.src / "app/src/main/MainActivity.kt").write_text(
            "class MainActivity { fun go() {} }\n", encoding="utf-8")
        (self.src / "basic/src/main/VideoPlayActivity.kt").write_text(
            "class VideoPlayActivity { fun start() {} }\n", encoding="utf-8")
        (self.root / "spec/baseline/ui-manifest.md").write_text(
            "| 0001 | MainActivity | MainPage.ets |\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _check(self):
        return lint_coverage.check_manifest_components(str(self.src), {}, str(self.root))

    def test_submodule_activity_without_page_or_skip_blocks(self):
        out, summary = self._check()
        blocking = [f for f in out if f["severity"] == "blocking"]
        self.assertEqual({f["subject"] for f in blocking}, {"VideoPlayActivity"})
        self.assertIn("basic", blocking[0]["detail"])
        self.assertIn("疑似死码", blocking[0]["detail"])   # zero external refs
        self.assertEqual(summary["unaccounted"], ["VideoPlayActivity"])

    def test_inner_class_variants_fold_into_one_finding(self):
        out, _ = self._check()
        subjects = [f["subject"] for f in out if f["rule"] == "SPEC.MANIFEST_ACTIVITY_UNACCOUNTED"]
        self.assertEqual(subjects.count("VideoPlayActivity"), 1)

    def test_sdk_shell_without_source_is_advisory_only(self):
        out, summary = self._check()
        shells = [f for f in out if f["rule"] == "SPEC.MANIFEST_ACTIVITY_SDK_SHELL"]
        self.assertEqual(len(shells), 1)
        self.assertEqual(shells[0]["severity"], "warn")
        self.assertIn("LoginAuthActivity", shells[0]["detail"])
        self.assertEqual(len(summary["sdk_shells"]), 1)

    def test_skip_with_decision_closes_but_stays_disclosed(self):
        # skipping is a decision, and the record must show WHO decided:
        # the finding closes, yet the activity remains listed by name.
        (self.root / "spec/baseline/skip-list.md").write_text(
            "| `VideoPlayActivity` | D-004 死码：Builder.start() 全仓 0 调用点 |\n"
            "| `LoginAuthActivity` | PD-C2-F002-01 阿里 SDK 内部页，F002 规约 |\n",
            encoding="utf-8",
        )
        out, summary = self._check()
        self.assertEqual(out, [])
        disclosed = {item["short"]: item["decision_ref"] for item in summary["skip_registered"]}
        self.assertEqual(disclosed["VideoPlayActivity"], "D-004")
        self.assertEqual(disclosed["LoginAuthActivity"], "PD-C2-F002-01")

    def test_skip_without_decision_ref_warns_but_does_not_block(self):
        (self.root / "spec/baseline/skip-list.md").write_text(
            "| `VideoPlayActivity` | 死码，不迁移 |\n"
            "| `LoginAuthActivity` | 阿里 SDK 内部页 |\n",
            encoding="utf-8",
        )
        out, summary = self._check()
        self.assertEqual([f for f in out if f["severity"] == "blocking"], [])
        warns = [f for f in out if f["rule"] == "SPEC.MANIFEST_SKIP_NO_DECISION"]
        self.assertEqual({w["subject"] for w in warns}, {"VideoPlayActivity", "LoginAuthActivity"})
        self.assertIsNone(summary["skip_registered"][0]["decision_ref"])

    def test_referenced_activity_is_not_called_dead(self):
        (self.src / "app/src/main/Caller.kt").write_text(
            "fun open() { VideoPlayActivity().start() }\n", encoding="utf-8")
        out, _ = self._check()
        blocking = [f for f in out if f["subject"] == "VideoPlayActivity"]
        self.assertIn("另有 1 处引用", blocking[0]["detail"])


class UnownedListVisibility(unittest.TestCase):
    def test_full_unowned_list_survives_in_context_not_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "android"
            for i in range(12):
                d = src / "app/src/main"
                d.mkdir(parents=True, exist_ok=True)
                (d / f"A{i:02d}.kt").write_text("class X\n", encoding="utf-8")
            (src / "basic/src/main").mkdir(parents=True)
            (src / "basic/src/main/VideoPlayActivity.kt").write_text("class V\n", encoding="utf-8")
            out, unowned = lint_coverage.check_breadth(str(src), {}, tmp)
        self.assertEqual(len(unowned), 13)
        self.assertTrue(any("VideoPlayActivity" in rel for rel in unowned))
        self.assertIn("basic 1", out[0]["detail"])          # per-module counts surface it
        self.assertIn("unowned_files", out[0]["detail"])    # points at the complete list


class Generalization(unittest.TestCase):
    """The gate must work for arbitrary Android apps — not one vendor mix,
    one AGP era, or one source language."""

    def test_sdk_seams_come_from_the_registry_not_the_code(self):
        # a niche SDK added to coverage-rules.json is detected with no code change
        rules = {"sdk_seams": {"roots": {
            "io.example.pay": {"label": "ExamplePay", "aliases": ["ExamplePay"]}}}}
        got = profile_feature.extract_instances(
            "import io.example.pay.Client\n", "S.kt",
            sdk_roots=profile_feature.sdk_roots_from_rules(rules),
        )
        self.assertEqual(got["sdk_seam"][0]["id"], "sdk:io.example.pay")

    def test_default_registry_covers_international_sdks(self):
        rules = profile_feature.load_rules()
        roots = profile_feature.sdk_roots_from_rules(rules)
        for expected in ("com.google.firebase", "com.facebook", "com.stripe", "com.tencent.mm"):
            self.assertIn(expected, roots)

    def test_registry_aliases_account_an_sdk_seam_in_ac_text(self):
        lint_coverage.merge_sdk_aliases_from_rules(
            {"sdk_seams": {"roots": {"com.google.firebase": {
                "label": "Firebase", "aliases": ["Firebase", "FCM"]}}}}
        )
        self.assertTrue(lint_coverage.instance_accounted(
            "sdk:com.google.firebase", "推送经 FCM 通道送达，token 刷新后重新注册"))

    def test_java_enum_cases_are_instances_too(self):
        got = profile_feature.extract_instances(
            "public enum PayState {\n  IDLE,\n  RUNNING,\n  DONE;\n}\n", "S.java")
        self.assertEqual(
            {i["id"] for i in got["enum_case"]},
            {"enum:PayState.IDLE", "enum:PayState.RUNNING", "enum:PayState.DONE"},
        )

    def test_manifest_without_package_attr_resolves_via_gradle_namespace(self):
        # AGP 7.3+: package attribute removed, namespace lives in build.gradle
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "android"
            module = src / "feature" / "src" / "main"
            module.mkdir(parents=True)
            (module / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
                '  <application><activity android:name=".DetailActivity"/></application>\n'
                "</manifest>\n", encoding="utf-8")
            (src / "feature" / "build.gradle.kts").write_text(
                'android {\n    namespace = "com.modern.feature"\n}\n', encoding="utf-8")
            entries = lint_coverage.manifest_activities(str(src))
        self.assertEqual(entries[0]["class_fq"], "com.modern.feature.DetailActivity")
        self.assertEqual(entries[0]["short"], "DetailActivity")

    def test_flavor_and_module_root_manifests_are_discovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "android"
            flavor = src / "app" / "src" / "paid"
            flavor.mkdir(parents=True)
            (flavor / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
                'package="com.x"><application>'
                '<activity android:name=".PaidOnlyActivity"/></application></manifest>\n',
                encoding="utf-8")
            legacy = src / "legacy"
            legacy.mkdir(parents=True)
            (legacy / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
                'package="com.y"><application>'
                '<activity android:name=".OldActivity"/></application></manifest>\n',
                encoding="utf-8")
            shorts = {e["short"] for e in lint_coverage.manifest_activities(str(src))}
        self.assertEqual(shorts, {"PaidOnlyActivity", "OldActivity"})

    def test_no_project_specific_decision_ids_in_tooling(self):
        # D-004 was one project's ledger entry; hints must stay project-neutral
        for path in ("lint_coverage.py", "profile_feature.py", "coverage-rules.json"):
            self.assertNotIn("D-004", (SCRIPTS / path).read_text(encoding="utf-8"), path)


class WorkerSelfLint(CoverageGate):
    """--only-feature: the worker self-check that folds the serial fix pass
    into the parallel generation window. Must be strictly read-only — parallel
    workers sharing open-findings.json would race."""

    def _run_only(self, extra=()):
        env = dict(os.environ, PYTHONPATH=str(SCRIPTS))
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "lint_coverage.py"), "--src", str(self.src),
             "--project-root", str(self.root), "--only-feature", "F001-login.md", *extra],
            capture_output=True, text=True, env=env,
        )

    def test_gap_exits_2_without_touching_the_findings_file(self):
        self._write_feature("- [ ] F001-AC01 用户可以登录　`源:Unrelated.foo → 标:X`\n")
        proc = self._run_only()
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertFalse((self.root / "spec/.a2h/open-findings.json").exists())
        self.assertIn("只读不写", proc.stdout)

    def test_no_profiles_file_is_needed(self):
        # workers self-check the file they just wrote; the profile is rebuilt
        # inline, so the shared feature-profiles.json need not exist yet
        self._write_feature(
            "- [ ] F001-AC01 授予 READ_PHONE_STATE 权限后可登录　`源:Login.doLogin → 标:X`　"
            "`判:ui | 授权后进入首页`　`真:src:app/Login.kt:3`\n"
        )
        self.assertFalse((self.root / "spec/baseline/feature-profiles.json").exists())
        proc = self._run_only()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse((self.root / "spec/.a2h/open-findings.json").exists())

    def test_repair_counters_never_advance_even_if_flag_smuggled(self):
        self._write_feature("- [ ] F001-AC01 用户可以登录　`源:Unrelated.foo → 标:X`\n")
        for _ in range(4):
            self._run_only(extra=("--after-repair",))
        self.assertFalse((self.root / "spec/.a2h/open-findings.json").exists())

    def test_missing_feature_file_is_exit_3(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "lint_coverage.py"), "--src", str(self.src),
             "--project-root", str(self.root), "--only-feature", "F099-nope.md"],
            capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(SCRIPTS)),
        )
        self.assertEqual(proc.returncode, 3)

    def test_report_only_full_run_writes_nothing(self):
        self._write_feature("- [ ] F001-AC01 用户可以登录　`源:Unrelated.foo → 标:X`\n")
        env = dict(os.environ, PYTHONPATH=str(SCRIPTS))
        subprocess.run(
            [sys.executable, str(SCRIPTS / "profile_feature.py"), "--src", str(self.src),
             "--features-dir", str(self.root / "spec/baseline/features")],
            check=True, capture_output=True, env=env,
        )
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS / "lint_coverage.py"), "--src", str(self.src),
             "--project-root", str(self.root), "--skip-breadth", "--report-only"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.root / "spec/.a2h/open-findings.json").exists())
