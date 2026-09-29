#!/usr/bin/env python3
"""2026-09-11 完整跑法（replay-t1f）实爆的 A/B 档修复——纯函数层单测。

  ② 数值形文案不当哨兵（value_shaped）；单词命中规则参数化（离线 A/B 否决了硬规则，默认旧行为）
  ① rid_texts 收 content-desc（图标控件的屏上身份）
  ⑤ identity_is_destructive 连屏上文案一起过破坏词表
  ④ stack_prefix_from_plan：续跑按计划重建 DFS 栈
  gate 判据：仍在源页 ⇒ GATE_NOT_EXERCISED（不论屏有无局部变化）
  a) lib_dumpsys.overlay_dialogs + capture 内核弹窗叠层硬闸（on_page / classify_arrival）

夹具纪律：app 侧标识一律占位串，断言里不出现任何真实应用常量。零设备。
"""
import os
import sys

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import compile_replay_plan as C  # noqa: E402
import replay_exec as R  # noqa: E402
import lib_dumpsys as D  # noqa: E402
import capture_page_e2e as K  # noqa: E402
from test_lib_dumpsys import SECTION, KNOWN  # noqa: E402

DLG = ("        TipsDialogX{ab12cd3} (11111111-2222-3333-4444-555555555555 tag=d1)\n"
       "          mFragmentId=#0 mContainerId=#0 mTag=d1\n"
       "          mState=7 mWho=11111111 mBackStackNesting=0\n"
       "          mHidden=false mDetached=false mMenuVisible=true mHasMenu=false\n"
       "          mUserVisibleHint=true\n")
SECTION_DLG = SECTION.replace("        NextFragment{809006a}", DLG + "        NextFragment{809006a}")


# ── ② 数值形文案 ─────────────────────────────────────────────────────────────
def test_value_shaped_texts_are_not_sentinels():
    for t in ("10020001226", "ID:90000001", "4.10 kB", "37%", "2026-09-11", "12:30", "¥28", "V1.0.6"):
        assert C.value_shaped(t), t
    for t in ("会员中心", "立即开通", "第1页", "一键退款", "关于我们", ""):
        assert not C.value_shaped(t), t


def test_build_sentinels_skips_value_shaped_candidates(tmp_path):
    """两轮基线同账号 → 手机号/ID 两轮相同不算 dynamic，却是数值形 → 不进哨兵；文案词照常入选。"""
    for d in ("s1", "s2"):
        p = tmp_path / d; p.mkdir()
        (p / "PageA.android.xml").write_text(
            '<hierarchy><node text="10020001226" bounds="[0,0][10,10]"/><node text="ID:90000001" bounds="[0,0][10,10]"/>'
            '<node text="页甲独有词" bounds="[0,0][10,10]"/><node text="共享词" bounds="[0,0][10,10]"/></hierarchy>', encoding="utf-8")
        (p / "PageB.android.xml").write_text(
            '<hierarchy><node text="页乙独有词" bounds="[0,0][10,10]"/><node text="共享词" bounds="[0,0][10,10]"/></hierarchy>', encoding="utf-8")
    sent, _ig, _dyn = C.build_sentinels(str(tmp_path / "s1"), str(tmp_path / "s2"))
    assert "页甲独有词" in sent["PageA"]
    assert not any(C.value_shaped(t) for t in sent["PageA"])


# ── ① content-desc 身份 ──────────────────────────────────────────────────────
def test_rid_texts_uses_content_desc_for_icon_controls(tmp_path):
    d = tmp_path / "shots"; d.mkdir()
    (d / "PageA.android.xml").write_text(
        '<hierarchy><node text="" content-desc="占位入口" resource-id="com.x:id/iv_icon" bounds="[0,0][10,10]"/>'
        '<node text="标题甲" content-desc="不该盖过 text" resource-id="com.x:id/tv_title" bounds="[0,0][10,10]"/>'
        '<node text="" content-desc="" resource-id="com.x:id/iv_blank" bounds="[0,0][10,10]"/></hierarchy>', encoding="utf-8")
    rmap, texts = C.rid_texts(str(d))["PageA"]
    k = lambda rid: next(iter(C._rid_variants(rid)))    # noqa: E731  rmap 键是归一化后的 rid 变体
    assert rmap.get(k("iv_icon")) == "占位入口" and rmap.get(k("tv_title")) == "标题甲"
    assert k("iv_blank") not in rmap and "占位入口" in texts


# ── ⑤ 破坏性判据看屏上文案 ───────────────────────────────────────────────────
def test_identity_is_destructive_checks_on_screen_text():
    assert C.identity_is_destructive("", "iv_icon", [], screen_text="一键退款")
    assert C.identity_is_destructive("", "iv_icon", ["危险占位"], screen_text="危险占位")
    assert not C.identity_is_destructive("", "iv_icon", [], screen_text="会员入口")
    assert not C.identity_is_destructive("", "iv_icon", [])
    assert C.identity_is_destructive("一键退款", None, [])          # 原有语义不变


# ── gate 判据 ────────────────────────────────────────────────────────────────
def test_gate_verdict_source_page_with_toast_is_not_exercised():
    v, why = R.gate_landing_verdict("PageA", "PageB", "PageA", True, "GateX", ("GateX",))
    assert v == "GATE_NOT_EXERCISED" and "局部变化" in why
    assert R.gate_landing_verdict("PageA", "PageB", "PageA", False, "GateX", ("GateX",))[0] == "GATE_NOT_EXERCISED"
    assert R.gate_landing_verdict(None, "PageB", "PageA", True, "GateX", ("GateX",))[0] == "GATE_UNKNOWN"
    assert R.gate_landing_verdict("PageB", "PageB", "PageA", True, "GateX", ("GateX",))[0] == "GATE_MISSING"
    assert R.gate_landing_verdict("GateX", "PageB", "PageA", True, "GateX", ("GateX",))[0] == "GATE_HELD"


# ── ④ 续跑栈重建 ─────────────────────────────────────────────────────────────
def _isp(s):
    return ((s.get("expect") or {}).get("kind") in ("push", "dialog", "webview")) \
        or (bool(s.get("probe_only")) and not s.get("expect_blocked"))


STEPS = [{"step": 1, "action": "coldstart", "to": "PageA"},
         {"step": 2, "action": "tap", "from": "PageA", "to": "PageB", "expect": {"kind": "push"}},
         {"step": "2R", "action": "reconcile", "node": "PageB"},
         {"step": 3, "action": "tap", "from": "PageB", "to": "PageC", "expect": {"kind": "tab_switch"}},
         {"step": 4, "action": "tap", "from": "PageC", "to": "PageD", "expect": {"kind": "scope_exit"}, "probe_only": True},
         {"step": "4B", "action": "back", "to": "PageC", "probe_return": True, "probe_from": "PageD"},
         {"step": 5, "action": "tap", "from": "PageC", "to": "PageE", "expect": {"kind": "push"},
          "expect_blocked": True, "probe_only": True},
         {"step": 6, "action": "tap", "from": "PageC", "to": "PageF", "expect": {"kind": "dialog"}},
         {"step": 7, "action": "back", "to": "PageC"},
         {"step": 8, "action": "back", "to": "PageA"},
         {"step": 9, "action": "coldstart", "to": "PageA"},
         {"step": 10, "action": "tap", "from": "PageA", "to": "PageB", "expect": {"kind": "push"}}]


def test_stack_prefix_from_plan_simulates_push_back_coldstart_and_probes():
    f = lambda n: R.stack_prefix_from_plan(STEPS, n, _isp)[0]   # noqa: E731
    assert f(3) == ["PageB"]
    assert f(5) == ["PageB"]                 # 探测 tap+back 成对抵消
    assert f(6) == ["PageB"]                 # 反向门禁探测自带回位，不入栈
    assert f(7) == ["PageB", "PageF"]
    assert f(9) == []
    assert f(11) == ["PageB"]                # coldstart 清栈后重新押
    d, v = R.stack_prefix_from_plan(STEPS, 11, _isp)
    assert v.count("PageB") == 2 and "PageD" in v
    assert R.stack_prefix_from_plan(STEPS, 0, _isp) == ([], [])


# ── ② 单词命中规则：参数化，默认旧行为（离线 A/B 否决硬规则）─────────────────
def test_identify_single_hit_rule_is_parameterized_and_defaults_to_old_behavior():
    ns = {"PageA": ["判别物A", "甲词"], "PageB": ["判别物B", "乙词"], "PageC": ["判别物C"]}
    wt = lambda w: 1.0  # noqa: E731
    assert R.IDENTIFY_SINGLE_HIT_OK is True
    assert R.identify_scored({"判别物A"}, ns, wt) == "PageA"
    assert R.identify_scored({"判别物A"}, ns, wt, single_hit_ok=False) is None
    assert R.identify_scored({"判别物A", "甲词"}, ns, wt, single_hit_ok=False) == "PageA"
    assert R.identify_scored({"判别物C"}, ns, wt, single_hit_ok=False) == "PageC"     # 唯一哨兵的页仍按 1 个
    assert R.identify_scored({"判别物A", "判别物B"}, ns, wt) is None                 # 并列且哨兵集不同 → 歧义
    assert R.identify_scored(set(), ns, wt) is None


# ── a) dumpsys 弹窗叠层 ──────────────────────────────────────────────────────
def test_overlay_dialogs_from_dumpsys():
    known = KNOWN | {"TipsDialogX"}
    assert D.overlay_dialogs(SECTION_DLG, known, {"TipsDialogX"}) == ["TipsDialogX"]
    assert D.overlay_dialogs(SECTION, KNOWN, {"TipsDialogX"}) == []
    assert D.overlay_dialogs(SECTION_DLG, known, set()) == []
    assert D.overlay_dialogs("", known, {"TipsDialogX"}) == []


def test_classify_arrival_dumpsys_overlay_is_dialog_over_page():
    rec = {"id": "HostX", "type": "Activity"}
    out, detail = K.classify_arrival("HostX", rec, "<hierarchy/>", {"HostX": rec}, {}, set(), overlay_ids=["TipsDialogX"])
    assert out == "dialog_over_page" and detail["dialog_ids"] == ["TipsDialogX"] and detail["source"] == "dumpsys"
    # 期望节点本身是弹窗：叠层判据不适用
    drec = {"id": "TipsDialogX", "type": "Dialog"}
    assert K.classify_arrival("HostX", drec, "<hierarchy/>", {"TipsDialogX": drec}, {}, set(),
                              overlay_ids=["TipsDialogX"])[0] != "dialog_over_page"


class _Drv:
    def __init__(self, raw, activity):
        self.raw, self.a = raw, activity

    def current_activity(self):
        return self.a

    def adb(self, args, timeout=30):
        class R_:  # noqa: N801
            pass
        r = R_(); r.stdout = self.raw if "dumpsys" in args else ""; r.returncode = 0
        return r


def _raw(sec):
    return "  ACTIVITY com.other.launcher/.MainActivity 1 pid=9\n    View Hierarchy:\n" + sec


def test_on_page_refuses_host_binding_when_known_dialog_overlays():
    """宿主 activity 相符、甚至 fragment 也 RESUMED，但已知弹窗叠在上面 → 这份 dump 是弹窗的，不绑给宿主。"""
    act, _ = D.section_for_pkg(_raw(SECTION), "com.example.app")
    K._BY_ID.clear()
    K._BY_ID.update({"HostActivity": {"id": "HostActivity", "type": "Activity"},
                     "LoadingFragment": {"id": "LoadingFragment", "type": "Fragment", "parent_in_nav": "HostActivity"},
                     "TipsDialogX": {"id": "TipsDialogX", "type": "Dialog"}})
    K._PKG = "com.example.app"
    try:
        full = "com.example.app/" + act
        clean, over = _Drv(_raw(SECTION), full), _Drv(_raw(SECTION_DLG), full)
        assert K._dumpsys_overlay_ids(over, K._BY_ID["HostActivity"]) == ["TipsDialogX"]
        assert K._dumpsys_overlay_ids(clean, K._BY_ID["HostActivity"]) == []
        assert K._dumpsys_overlay_ids(over, K._BY_ID["TipsDialogX"]) == []          # 弹窗本尊不适用
        assert K.on_page(clean, K._BY_ID["HostActivity"], "<hierarchy/>") == "activity"
        assert K.on_page(over, K._BY_ID["HostActivity"], "<hierarchy/>") is None
        assert K.on_page(over, K._BY_ID["LoadingFragment"], "<hierarchy/>") is None
    finally:
        K._BY_ID.clear(); K._PKG = ""
