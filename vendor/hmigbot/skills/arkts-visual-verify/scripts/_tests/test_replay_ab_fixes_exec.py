#!/usr/bin/env python3
"""2026-09-11 完整跑法（replay-t1f）实爆的 A/B 档修复——执行器整段跑（假设备，零 hdc）。

  ① rid-only 无屏上身份的控件找不到 → no_screen_identity（不出 control_missing 假 P0）；
     rid-only 带安卓屏上文案 → 用文案兜底定位
  ⑥ 点了屏有局部变化但没导航（toast/内联校验）→ feedback_without_nav，不按 handler 空实现出单；
     反向门禁探测同形 → GATE_NOT_EXERCISED 而非 GATE_MISSING 假安全单
  ③ 探测步（旧计划 kind=scope_exit）到达照押栈，配对 back 真按；身份仍是源页的弱到达不押
  ④ --resume-from 按计划重建 DFS 栈，后续 back 不再 SKIP_no_descend

夹具/屏/假设备全部复用 test_replay_gate_probe_and_unanchored（占位串纪律同）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_replay_gate_probe_and_unanchored import (SCREENS, FakeDrv, run, screen, _node, ctrl,  # noqa: E402
                                                    gate_step)

# 源页 + 一条 toast 文案：identify 仍是 PageA，但签名变了
SCREENS["PageA_toast"] = screen(_node("Text", (100, 200, 1200, 300), text="判别物A"),
                                ctrl("入口甲", "ctlB", 900), ctrl("入口丙", "ctlC", 1200),
                                _node("Text", (100, 2500, 1200, 2600), text="提示占位文案"))


def _tap(step, frm, to, prim, rid, kind="push", sentinel=None, **extra):
    st = {"step": step, "action": "tap", "from": frm, "to": to,
          "match": {"primary": prim, "rid": rid, "source": "runtime"},
          "wait_budget_s": 0.1, "safety": "normal",
          "expect": {"kind": kind, "sentinel": sentinel if sentinel is not None else [f"判别物{to[-1]}"]}}
    st.update(extra)
    return st


def _row(rows, step):
    return next(x for x in rows if str(x.get("step")) == str(step))


# ── ① rid-only 无屏上身份 ────────────────────────────────────────────────────
def test_rid_only_control_not_found_blames_no_screen_identity(tmp_path):
    st = _tap(1, "PageA", "PageB", "", "ctlZ")
    st["match"]["source"] = "android_runtime"; st["match"]["text_identity_source"] = None
    rows, man, code = run(tmp_path, [st], FakeDrv("PageA", {}))
    assert _row(rows, 1)["verdict"] == "ABANDON_no_match"
    e = man["escalations"][0]
    assert e["blame"] == "no_screen_identity" and e["product_defect"] is None and e["needs_verification"] is True
    assert e["hmos_dump_has_ids"] is True and e["confirmed_on_source_page"] is True


def test_text_identity_control_not_found_still_blames_control_missing(tmp_path):
    """有屏上文案的控件找不到 → 原判据不变（回归护栏）。"""
    rows, man, code = run(tmp_path, [_tap(1, "PageA", "PageB", "无此控件占位", "ctlZ")], FakeDrv("PageA", {}))
    assert man["escalations"][0]["blame"] == "control_missing_in_hmos"


def test_rid_only_step_locates_by_android_dump_text(tmp_path):
    st = _tap(1, "PageA", "PageC", "", "ctlNoSuch")
    st["match"].update(source="android_runtime", android_dump_text="入口丙", text_identity_source="android_dump_rid")
    rows, man, code = run(tmp_path, [st], FakeDrv("PageA", {"PageA": "PageC"}))
    r = _row(rows, 1)
    assert r["verdict"].startswith("ARRIVED") and str(r["matched_by"]).startswith("android_dump_text:")
    assert r["matched_by_android_dump_text"] == "入口丙"


# ── ⑥ 屏有反馈但没导航 ──────────────────────────────────────────────────────
def test_tap_with_toast_on_source_is_weak_arrival_marked_with_source_identity(tmp_path):
    """走序 tap 后屏变了但哨兵身份仍是源页：既有语义仍记弱到达（不改判），但 ①记 identified_as=源页
    ②不押栈 ③页槽注记"仍是源页"——judge 据此按未到达复核，而不是拿源页截图当目标页比。"""
    rows, man, code = run(tmp_path, [_tap(1, "PageA", "PageB", "入口甲", "ctlB")],
                          FakeDrv("PageA", {"PageA": "PageA_toast"}))
    r = _row(rows, 1)
    assert r["verdict"] == "ARRIVED_weak" and r["identified_as"] == "PageA" and r["stack"] == 0
    assert not man["escalations"]
    assert any("仍是源页" in n for n in man["per_page"]["PageB"]["observation_notes"])


def test_tap_with_no_change_at_all_keeps_handler_not_implemented(tmp_path):
    """屏纹丝不动 → 原判据不变（回归护栏）。"""
    rows, man, code = run(tmp_path, [_tap(1, "PageA", "PageB", "入口甲", "ctlB")], FakeDrv("PageA", {}))
    assert man["escalations"][0]["blame"] == "handler_not_implemented"


def test_gate_probe_toast_on_source_is_not_gate_missing(tmp_path):
    rows, man, code = run(tmp_path, [gate_step(True)], FakeDrv("PageA", {"PageA": "PageA_toast"}))
    r = _row(rows, 1)
    assert r["gate_verdict"] == "GATE_NOT_EXERCISED" and r["verdict"] == "GATE_NOT_EXERCISED"
    assert not any(e["blame"] == "gate_missing_in_hmos" for e in man["escalations"])
    assert man["escalations"][0]["blame"] == "feedback_without_nav"


# ── ③ 探测步押栈 ─────────────────────────────────────────────────────────────
def test_probe_step_with_legacy_scope_exit_kind_still_pushes_and_returns(tmp_path):
    steps = [_tap(1, "PageA", "PageC", "入口丙", "ctlC", kind="scope_exit", probe_only=True),
             {"step": "1B", "action": "back", "from": "PageC", "to": "PageA", "kind": "scope_exit",
              "probe_return": True, "probe_from": "PageC"}]
    drv = FakeDrv("PageA", {"PageA": "PageC"}, back_to={"PageC": "PageA"})
    rows, man, code = run(tmp_path, steps, drv)
    assert _row(rows, 1)["verdict"].startswith("ARRIVED") and _row(rows, 1)["stack"] == 1
    assert _row(rows, "1B")["verdict"] == "BACK_OK" and drv.backs == 1


def test_unanchored_arrival_on_source_page_does_not_push(tmp_path):
    """签名变了但身份仍是源页（弹层/toast）→ 不押栈；配对 back 不按（押了会在根上按 BACK）。"""
    steps = [_tap(1, "PageA", "PageZ", "入口丙", "ctlC", sentinel=[], probe_only=True,
                  expect={"kind": "push", "sentinel": [], "arrival_confidence": "unanchored"}),
             {"step": "1B", "action": "back", "from": "PageZ", "to": "PageA", "kind": "push",
              "probe_return": True, "probe_from": "PageZ"}]
    drv = FakeDrv("PageA", {"PageA": "PageA_toast"}, back_to={"PageA_toast": "PageA"})
    rows, man, code = run(tmp_path, steps, drv, plan_extra={"coverage_targets": ["PageA", "PageZ"]})
    assert _row(rows, 1)["verdict"] == "ARRIVED_unanchored" and _row(rows, 1)["stack"] == 0
    assert _row(rows, "1B")["verdict"] == "SKIP_probe_no_arrival" and drv.backs == 0


# ── ④ 续跑重建栈 ─────────────────────────────────────────────────────────────
def test_resume_from_reconstructs_dfs_stack_from_plan(tmp_path):
    steps = [{"step": 1, "action": "coldstart", "to": "PageA"},
             _tap(2, "PageA", "PageC", "入口丙", "ctlC"),
             {"step": 3, "action": "back", "from": "PageC", "to": "PageA", "kind": "push"}]
    drv = FakeDrv("PageC", {}, back_to={"PageC": "PageA"})
    rows, man, code = run(tmp_path, steps, drv, argv_extra=("--resume-from", "3"))
    assert rows[0]["verdict"] == "STACK_RECONSTRUCTED" and rows[0]["descend"] == ["PageC"]
    assert _row(rows, 3)["verdict"] == "BACK_OK" and drv.backs == 1
    assert man["resume_stack_reconstructed"][0] == {"resume_from": 3, "descend": ["PageC"]}


def test_fresh_run_has_no_reconstruction_record(tmp_path):
    steps = [{"step": 1, "action": "coldstart", "to": "PageA"},
             _tap(2, "PageA", "PageC", "入口丙", "ctlC"),
             {"step": 3, "action": "back", "from": "PageC", "to": "PageA", "kind": "push"}]
    drv = FakeDrv("PageA", {"PageA": "PageC"}, back_to={"PageC": "PageA"})
    rows, man, code = run(tmp_path, steps, drv)
    assert not any(x.get("verdict") == "STACK_RECONSTRUCTED" for x in rows)
    assert "resume_stack_reconstructed" not in man and _row(rows, 3)["verdict"] == "BACK_OK"


# ── F2 执行器侧：static_unverified 的文案找不到不判缺失 ─────────────────────────
def test_static_unverified_label_not_found_is_not_control_missing(tmp_path):
    st = _tap(1, "PageA", "PageB", "描述名占位", "ctlZ")
    st["match"]["source"] = "static"; st["match"]["text_identity_source"] = "static_unverified"
    rows, man, code = run(tmp_path, [st], FakeDrv("PageA", {}))
    assert _row(rows, 1)["verdict"] == "ABANDON_no_match"
    e = man["escalations"][0]
    assert e["blame"] == "trigger_label_unverified" and e["product_defect"] is None and e["needs_verification"] is True
