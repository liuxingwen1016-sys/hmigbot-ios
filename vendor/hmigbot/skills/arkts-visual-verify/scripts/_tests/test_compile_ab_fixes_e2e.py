#!/usr/bin/env python3
"""编译器整段跑（子进程）：2026-09-11 A/B 档修复的编译侧落点。

  ③ 救回的探测步：导航类型按**目标节点类型**推（弹窗→dialog，其余→push），不再沿用上游 skip 的理由词
  ① tap 步 match 标 text_identity_source；rid-only 但安卓屏上有 text/content-desc → android_dump_text
  ⑤ rid-only 身份的屏上文案命中破坏词表 → 不救回（资金安全 > 覆盖）

复用 test_compile_android_edges_and_gate 的最小工程夹具（全占位串）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_compile_android_edges_and_gate import _fixture_project, _compile, edge, ib, led_disp  # noqa: E402


def _extend(tmp_path):
    """在夹具工程上加：弹窗目标的 skip 边、rid-only 边（屏上有 content-desc）、rid-only 破坏性边。"""
    tree = json.load(open(tmp_path / "tree.json", encoding="utf-8"))
    fc = lambda n: [{"name": f"功能{n}", "anchor": "pkg:id/ctlZ", "expected_android": "占位预期",  # noqa: E731
                     "android_trusted": True}]
    tree["dialogs"] = [{"id": "DlgQ", "functional_checks": fc("DlgQ"),
                        "inbound_triggers": [ib("PageA", label="入口Q", rid="ctlQ")]}]
    tree["pages"] += [{"id": "PageF", "functional_checks": fc("PageF"), "inbound_triggers": [ib("PageA", rid="ctlF")]},
                      {"id": "PageG", "functional_checks": fc("PageG"), "inbound_triggers": [ib("PageA", rid="ctlG")]}]
    (tmp_path / "tree.json").write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    walk = json.load(open(tmp_path / "walk.json", encoding="utf-8"))
    walk["walks"][0]["steps"] += [
        {"step": 7, "action": "skip", "from": "PageA", "to": "DlgQ", "kind": "scope_exit", "note": "占位理由"},
        {"step": 8, "action": "tap", "from": "PageA", "to": "PageF", "trigger": None, "kind": "push"},
        {"step": 9, "action": "skip", "from": "PageA", "to": "PageG", "kind": "scope_exit", "note": "占位理由"},
    ]
    (tmp_path / "walk.json").write_text(json.dumps(walk, ensure_ascii=False), encoding="utf-8")
    edges = json.load(open(tmp_path / "edges.json", encoding="utf-8"))
    edges += [edge("PageA", "DlgQ", rid="ctlQ", text="入口Q"),
              edge("PageA", "PageF", rid="ctlF"),            # rid-only：安卓 trigger 文案为空（图标控件）
              edge("PageA", "PageG", rid="ctlG")]            # rid-only，屏上文案是破坏性动作
    (tmp_path / "edges.json").write_text(json.dumps(edges, ensure_ascii=False), encoding="utf-8")
    for d in ("shots", "shots1"):
        p = tmp_path / d / "PageA.android.xml"
        x = p.read_text(encoding="utf-8").replace(
            "</hierarchy>",
            '<node resource-id="pkg:id/ctlF" text="" content-desc="占位入口己" clickable="true"/>'
            '<node resource-id="pkg:id/ctlG" text="" content-desc="一键退款占位" clickable="true"/></hierarchy>')
        p.write_text(x, encoding="utf-8")
    for n in ("DlgQ", "PageF", "PageG"):
        for d in ("shots", "shots1"):
            (tmp_path / d / f"{n}.android.xml").write_text(
                f'<hierarchy><node text="判别物{n}" clickable="false"/></hierarchy>', encoding="utf-8")
        (tmp_path / "shots" / f"{n}.png").write_bytes(b"\x89PNG")


def test_probe_nav_kind_follows_target_type_and_match_identity_source(tmp_path):
    _fixture_project(tmp_path)
    _extend(tmp_path)
    plan, err = _compile(tmp_path)
    steps = {str(s["step"]): s for s in plan["steps"] if not str(s["step"]).endswith("R")}
    # ③ 页目标的救回探测步 → push（不是 scope_exit）；配对 back 同 kind
    assert steps["2"]["action"] == "tap" and steps["2"]["probe_only"] is True
    assert steps["2"]["kind"] == "push" and steps["2"]["expect"]["kind"] == "push" and steps["2B"]["kind"] == "push"
    # ③ 弹窗目标的救回探测步 → dialog
    assert steps["7"]["action"] == "tap" and steps["7"]["kind"] == "dialog" and steps["7"]["expect"]["kind"] == "dialog"
    assert steps["7B"]["action"] == "back" and steps["7B"]["kind"] == "dialog"
    # ① 身份来源：有 trigger 文案 → trigger；rid-only 但安卓屏上有 content-desc → android_dump_text
    assert steps["1"]["match"]["text_identity_source"] == "trigger"
    m8 = steps["8"]["match"]
    assert m8["primary"] == "" and m8["rid"] == "ctlF" and m8["source"] == "android_runtime"
    assert m8["android_dump_text"] == "占位入口己" and m8["text_identity_source"] == "android_dump_rid"
    # ⑤ rid-only、屏上文案是破坏性动作 → 不救回（没有任何 tap 步指向它）
    assert not any(s.get("action") == "tap" and s.get("to") == "PageG" for s in plan["steps"])
    assert "scope_exit" not in {s.get("kind") for s in plan["steps"] if s.get("action") == "tap"}


def test_rid_only_without_any_screen_text_has_no_identity_source(tmp_path):
    _fixture_project(tmp_path)
    _extend(tmp_path)
    for d in ("shots", "shots1"):                       # 抹掉 ctlF 的 content-desc → 纯图标
        p = tmp_path / d / "PageA.android.xml"
        p.write_text(p.read_text(encoding="utf-8").replace('content-desc="占位入口己"', 'content-desc=""'), encoding="utf-8")
    plan, err = _compile(tmp_path)
    m8 = next(s for s in plan["steps"] if str(s["step"]) == "8")["match"]
    assert m8["rid"] == "ctlF" and "android_dump_text" not in m8 and m8["text_identity_source"] is None


# ── F2（2026-09-12）：计划文案安卓自己都没见过（树/LLM 描述名）────────────────────
def _extend_f2(tmp_path):
    """三种形态：死标签但 (from,to) 已由别的步覆盖 → skip；死标签且无人覆盖但安卓有实测控件 → 换控件；
    死标签且安卓根本没这对页的记录 → 照发但标 static_unverified。外加护栏：基线上见过的文案不受影响。"""
    tree = json.load(open(tmp_path / "tree.json", encoding="utf-8"))
    fc = lambda n: [{"name": f"功能{n}", "anchor": "pkg:id/ctlZ", "expected_android": "占位预期",  # noqa: E731
                     "android_trusted": True}]
    tree["pages"] += [{"id": "PageF", "functional_checks": fc("PageF"), "inbound_triggers": [ib("PageA", rid="ctlF")]},
                      {"id": "PageG", "functional_checks": fc("PageG"), "inbound_triggers": [ib("PageA", label="描述名丙")]}]
    (tmp_path / "tree.json").write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    walk = json.load(open(tmp_path / "walk.json", encoding="utf-8"))
    walk["walks"][0]["steps"] += [
        {"step": 10, "action": "tap", "from": "PageA", "to": "PageD", "trigger": "描述名甲", "kind": "push"},   # 步 3 已覆盖 (A,D)
        {"step": 11, "action": "tap", "from": "PageA", "to": "PageF", "trigger": "描述名乙", "kind": "push"},   # 无人覆盖，安卓有 ctlF
        {"step": 12, "action": "tap", "from": "PageA", "to": "PageG", "trigger": "描述名丙", "kind": "push"},   # 安卓无记录
        {"step": 13, "action": "tap", "from": "PageA", "to": "PageC", "trigger": "锚A", "kind": "push"},        # 基线上有这句 → 护栏
    ]
    (tmp_path / "walk.json").write_text(json.dumps(walk, ensure_ascii=False), encoding="utf-8")
    edges = json.load(open(tmp_path / "edges.json", encoding="utf-8"))
    edges += [edge("PageA", "PageF", rid="ctlF")]
    (tmp_path / "edges.json").write_text(json.dumps(edges, ensure_ascii=False), encoding="utf-8")
    for n in ("PageF", "PageG"):
        for d in ("shots", "shots1"):
            (tmp_path / d / f"{n}.android.xml").write_text(
                f'<hierarchy><node text="判别物{n}" clickable="false"/></hierarchy>', encoding="utf-8")
        (tmp_path / "shots" / f"{n}.png").write_bytes(b"\x89PNG")


def test_f2_dead_label_skip_replace_unverified_and_guard(tmp_path):
    _fixture_project(tmp_path)
    _extend_f2(tmp_path)
    plan, err = _compile(tmp_path)
    steps = {str(s["step"]): s for s in plan["steps"] if not str(s["step"]).endswith("R")}
    # 死标签、(A,D) 已由步 3 覆盖 → skip，账上写明谁覆盖、安卓实测控件是什么
    assert steps["10"]["action"] == "skip" and steps["10"]["skip_reason"] == "label_never_observed_on_android"
    assert 3 in steps["10"]["covered_by_steps"] and steps["10"]["android_control"]["rid"] == "ctlD"
    # 死标签、无人覆盖、安卓有实测控件 → 换成实测控件发步，记下原文案
    m11 = steps["11"]["match"]
    assert steps["11"]["action"] == "tap" and m11["rid"] == "ctlF" and m11["primary"] == "" and m11["source"] == "android_runtime"
    assert steps["11"]["label_replaced"]["plan_label"] == "描述名乙"
    # 死标签、安卓无这对页记录 → 照发但 static_unverified（执行器找不到不判缺失）
    assert steps["12"]["action"] == "tap" and steps["12"]["match"]["text_identity_source"] == "static_unverified"
    # 护栏：安卓基线上见过的文案照旧
    assert steps["13"]["action"] == "tap" and steps["13"]["match"]["text_identity_source"] == "trigger"
    led = json.load(open(tmp_path / "translation_ledger_trip_1_logged_out.json", encoding="utf-8"))
    assert led_disp(led, "PageD", "描述名甲") == "skipped"
    assert any(e.get("label_unverified_on_android") for e in led["edges"] if e["to"] == "PageG")
