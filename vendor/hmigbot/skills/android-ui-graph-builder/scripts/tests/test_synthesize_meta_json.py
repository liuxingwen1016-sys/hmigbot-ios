#!/usr/bin/env python3
"""Layout-source resolution fixtures.

Encodes the Phase-A incident: a DataBinding + custom-res project produced empty
layout_sources for 52/53 pages, costing three debug re-runs (~15-20 min) on a
real generation. Each test is one resolution path that run needed.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import parse_layouts  # noqa: E402
import synthesize_meta_json as smj  # noqa: E402


class LayoutResolution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        root = Path(self.tmp)
        std = root / "app/src/main/res/layout"
        custom = root / "app/src/main/platform-res/layout"
        std.mkdir(parents=True)
        custom.mkdir(parents=True)
        (std / "activity_plain.xml").write_text("<LinearLayout/>", encoding="utf-8")
        (custom / "activity_renew_manage.xml").write_text("<LinearLayout/>", encoding="utf-8")
        (custom / "activity_webview.xml").write_text("<LinearLayout/>", encoding="utf-8")
        (custom / "activity_member_center.xml").write_text("<LinearLayout/>", encoding="utf-8")
        self.layouts = parse_layouts.find_layout_files(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _extract(self, source: str) -> list[str]:
        return smj.extract_layout_sources(source, self.layouts, self.tmp)

    def test_custom_res_sourceset_layouts_are_discovered(self):
        # requiring the parent dir to be literally `res` dropped all of these
        self.assertIn("activity_renew_manage", self.layouts)
        self.assertIn("activity_plain", self.layouts)

    def test_unrelated_dirs_do_not_false_positive(self):
        stray = Path(self.tmp) / "app/src/main/features/layout"
        stray.mkdir(parents=True)
        (stray / "not_a_layout.xml").write_text("<x/>", encoding="utf-8")
        layouts = parse_layouts.find_layout_files(self.tmp)
        self.assertNotIn("not_a_layout", layouts)

    def test_plain_setcontentview_still_resolves(self):
        got = self._extract("class A { fun onCreate() { setContentView(R.layout.activity_plain) } }")
        self.assertTrue(any("activity_plain.xml" in p for p in got))

    def test_layout_id_fun_expression_form(self):
        got = self._extract(
            "class ManageRenewActivity : Base() {\n"
            "    override fun getLayoutResId() = R.layout.activity_renew_manage\n}"
        )
        self.assertTrue(any("activity_renew_manage.xml" in p for p in got), got)

    def test_layout_id_fun_block_form(self):
        got = self._extract(
            "class MemberCenterActivitiy : Base() {\n"
            "    override fun getLayoutResId(): Int {\n"
            "        return R.layout.activity_member_center\n    }\n}"
        )
        self.assertTrue(any("activity_member_center.xml" in p for p in got), got)

    def test_layout_id_fun_java_form(self):
        got = self._extract(
            "public class X extends Base {\n"
            "    protected int getLayoutResId() { return R.layout.activity_plain; }\n}"
        )
        self.assertTrue(any("activity_plain.xml" in p for p in got), got)

    def test_generic_binding_parameter_resolves(self):
        got = self._extract(
            "class WebViewActivity : BaseBusinessActivity<ActivityWebviewBinding>() {\n}"
        )
        self.assertTrue(any("activity_webview.xml" in p for p in got), got)

    def test_databinding_two_arg_setcontentview(self):
        got = self._extract(
            "val b = DataBindingUtil.setContentView(this, R.layout.activity_plain)"
        )
        self.assertTrue(any("activity_plain.xml" in p for p in got), got)

    def test_unknown_generic_binding_is_harmless(self):
        got = self._extract("class Adapter<T : ViewDataBinding>() {}")
        self.assertEqual(got, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
