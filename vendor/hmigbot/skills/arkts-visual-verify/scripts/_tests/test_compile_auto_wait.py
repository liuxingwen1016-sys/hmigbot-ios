#!/usr/bin/env python3
"""编译期：auto 转场边 → `wait` 步（F6，2026-09-11）。

病：安卓 auto_transition=True 的边（首启门自动弹出 / Splash 倒计时 / 宿主装默认子页）没有控件身份，此前一律编成
`untranslatable_no_control_identity` skip；鸿蒙侧既不等也不判到达，下一步在还没转场的屏上找控件必死。
真产物复编：trip_1 步 2/6/7/13 由 skip 变 wait，其余 97 步零差异。

夹具复用 test_compile_android_edges_and_gate 的合成工程（全占位串），再追加两页：PageF（auto 边目标，有独有文本）、
PageG（非 auto、无身份 → 仍是 skip 的反例）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compile_replay_plan as C  # noqa: E402
import test_compile_android_edges_and_gate as G  # noqa: E402


def test_auto_wait_budget_rules():
    assert C.auto_wait_budget(4.0) == 8.0                                   # 默认×2
    assert C.auto_wait_budget(4.0, 2.5) == 8.0                              # 安卓实走短于默认×2 → 取默认×2
    assert C.auto_wait_budget(4.0, 10.3) == 15.5                            # 安卓实走×1.5
    assert C.auto_wait_budget(4.0, None, "countdown_ms:3000") == 8.0        # 倒计时×1.5=4.5 < 8
    assert C.auto_wait_budget(4.0, None, "countdown_ms:10000") == 15.0
    assert C.auto_wait_budget(4.0, None, "until_text:占位") == 8.0           # 文案提示不带时长
    assert C.auto_wait_budget(4.0, 40) == 30.0                              # 上限默认 30s
    assert C.auto_wait_budget(4.0, 40, cap_s=90) == 60.0                    # 上限可调（--auto-wait-cap）


def _add_auto_pages(tmp_path):
    tree = json.load(open(tmp_path / "tree.json", encoding="utf-8"))
    tree["pages"] += [{"id": "PageF", "inbound_triggers": [{"from_page": "PageA", "trigger_kind": "auto",
                                                            "wait_hint": "until_text:判别物F"}]},
                      {"id": "PageG", "inbound_triggers": [{"from_page": "PageA"}]}]
    (tmp_path / "tree.json").write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    xml = ('<hierarchy><node text="判别物F" clickable="false"/><node text="通用条" clickable="false"/></hierarchy>')
    for d in ("shots", "shots1"):
        (tmp_path / d / "PageF.android.xml").write_text(xml, encoding="utf-8")
    (tmp_path / "shots" / "PageF.png").write_bytes(b"\x89PNG")
    walk = json.load(open(tmp_path / "walk.json", encoding="utf-8"))
    walk["walks"][0]["steps"] += [
        {"step": 7, "action": "tap", "from": "PageA", "to": "PageF", "trigger": None, "kind": "push",
         "auto_transition": True, "trigger_kind": "auto", "wait_hint": "until_text:判别物F", "gate": False,
         "note": "自动转场占位"},
        {"step": 8, "action": "back", "to": "PageA", "kind": "push"},
        {"step": 9, "action": "tap", "from": "PageA", "to": "PageG", "trigger": None, "kind": "push"},
        {"step": 10, "action": "back", "to": "PageA", "kind": "push"},
    ]
    (tmp_path / "walk.json").write_text(json.dumps(walk, ensure_ascii=False), encoding="utf-8")


def test_auto_edge_without_identity_becomes_wait_and_non_auto_stays_skip(tmp_path):
    G._fixture_project(tmp_path)
    _add_auto_pages(tmp_path)
    plan, err = G._compile(tmp_path)
    steps = {s["step"]: s for s in plan["steps"] if not str(s["step"]).endswith("R")}
    w = steps[7]
    assert w["action"] == "wait" and w["from"] == "PageA" and w["to"] == "PageF"
    assert w["wait_budget_s"] == 8.0 and w["wait_hint"] == "until_text:判别物F"
    assert w["expect"]["kind"] == "push" and w["expect"]["sentinel"] and w["expect"]["arrival_confidence"] == "sentinel"
    assert w["kind"] == "push" and w["gate"] is False and w["note"] == "自动转场占位"
    assert "match" not in w                                          # 等待步没有控件身份，也不该假装有
    assert steps[8]["action"] == "back"                              # 配对回位照常透传
    # 反例：非 auto 且无身份 → 仍是 skip（带非空 reason）
    assert steps[9]["action"] == "skip" and steps[9]["skip_reason"] == "untranslatable_no_control_identity"
    led = json.load(open(tmp_path / "translation_ledger_trip_1_logged_out.json", encoding="utf-8"))
    assert G.led_disp(led, "PageF") == "emitted_wait"
    assert G.led_disp(led, "PageG") == "skipped"
    assert sum(1 for x in plan["steps"] if x["action"] == "wait") == 1      # 只有那条 auto 边变 wait


def test_auto_edge_to_page_without_sentinel_is_unanchored_wait(tmp_path):
    """目标页无独有文本（PageE 那种）→ 仍编成 wait，只是标 unanchored；执行器靠 wait_hint 文案 / identify 兜底。"""
    G._fixture_project(tmp_path)
    walk = json.load(open(tmp_path / "walk.json", encoding="utf-8"))
    walk["walks"][0]["steps"] = [
        {"step": 1, "action": "tap", "from": "PageA", "to": "PageE", "trigger": None, "kind": "push",
         "auto_transition": True, "wait_hint": "until_text:占位提示"},
        {"step": 2, "action": "back", "to": "PageA", "kind": "push"}]
    (tmp_path / "walk.json").write_text(json.dumps(walk, ensure_ascii=False), encoding="utf-8")
    plan, _ = G._compile(tmp_path, with_edges=False)            # 不带安卓边：也不许再退化成 skip
    s = plan["steps"][0]
    assert s["action"] == "wait" and s["expect"]["sentinel"] == [] and s["expect"]["arrival_confidence"] == "unanchored"
    assert s["wait_hint"] == "until_text:占位提示"
