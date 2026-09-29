#!/usr/bin/env python3
"""walk_exec a)（2026-09-11 验收实爆）：宿主页补结账时已知弹窗叠在上面 → 推迟，弹窗走完再补。

病：HomeActivity 的 late_settle 发生在自动弹窗已 RESUMED 之后，uiautomator 只 dump 顶层窗口，
宿主基线 = 弹窗内容却因 activity 后缀相符判 verified（两份 xml md5 相同）。
判据只吃 dumpsys 的 FragmentManager 状态 + 树里的弹窗节点集，零 app 常量。
子进程（walk_ledger）一律 monkeypatch；断言里不出现任何真实 app 的页名/控件名。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from test_walk_exec_rules import FakeDev, ew, _reset_ui_words, _no_sleep  # noqa: F401,E402
from test_walk_exec_round4a import a6_exec, is_settle, argv_val, HUB_DUMP, LEAF_DUMP  # noqa: E402

DLG_FRAG = ("        ConfirmDlg{ab12cd3} (11111111-2222-3333-4444-555555555555 tag=d1)\n"
            "          mFragmentId=#0 mContainerId=#0 mTag=d1\n"
            "          mState=7 mWho=11111111 mBackStackNesting=0\n"
            "          mHidden=false mDetached=false mMenuVisible=true mHasMenu=false\n"
            "          mUserVisibleHint=true\n")


def raw(with_dialog, act="LeafPage"):
    return ("  ACTIVITY com.x/com.x.%s 1 pid=9\n    View Hierarchy:\n"
            "      com.android.internal.policy.DecorView{a1 V.E...... R.....ID 0,0-1440,3120}\n"
            "    Local FragmentActivity 4242ad2 State:\n      FragmentManager misc state:\n      Active Fragments:\n" % act
            ) + (DLG_FRAG if with_dialog else "")


class OverlayDev(FakeDev):
    """dumpsys 由脚本给：overlay=True 时弹窗节点 RESUMED 叠在宿主上。"""

    def __init__(self, dumps, overlay=True, **kw):
        super().__init__(dumps, **kw)
        self.overlay = overlay

    def shell(self, cmd, timeout=30):
        self.shell_log.append(cmd)
        if str(cmd).startswith("dumpsys activity top"):
            return raw(self.overlay)
        if str(cmd).startswith("wm size"):
            return "Physical size: 1440x3120"
        return ""


def _exec(ew, monkeypatch, calls, overlay):
    step = {"step": 2, "action": "tap", "from": "HubPage", "to": "LeafPage", "trigger": "叶子",
            "static_rid": "btn_delete"}
    ex = a6_exec(ew, step, [HUB_DUMP, LEAF_DUMP], monkeypatch, calls)
    ex.dev = OverlayDev([HUB_DUMP, LEAF_DUMP], overlay=overlay)
    ex._known_ids = {"HubPage", "LeafPage", "ConfirmDlg"}
    ex._dialog_ids = {"ConfirmDlg"}
    return ex, step


def test_late_settle_deferred_while_known_dialog_overlays_then_settled(ew, monkeypatch):
    calls = []
    ex, step = _exec(ew, monkeypatch, calls, overlay=True)
    ex.do_tap(step)
    assert not any(is_settle(c) for c in calls)                     # 弹窗盖着：不结
    d = ex.state["late_settle_deferred"]
    assert d[0]["node"] == "LeafPage" and d[0]["overlay"] == ["ConfirmDlg"] and d[0]["step"] == 2
    assert not ex.state.get("late_settled")
    assert any("推迟" in n for n in ex.state["notes"])
    ex._retry_deferred_settle()                                     # 弹窗还在：仍不结
    assert not any(is_settle(c) for c in calls)
    ex.dev.overlay = False                                          # 弹窗走完、dumpsys 判位仍在本页：补结账
    ex._retry_deferred_settle()
    st = [c for c in calls if is_settle(c)]
    assert len(st) == 1 and argv_val(st[0], "--node") == "LeafPage" and argv_val(st[0], "--mode") == "walk"
    assert ex.state["late_settle_deferred"] == []
    assert ex.state["late_settled"][0]["reason"] == "deferred_dialog_overlay_then_settled"
    assert ex.state["late_settled"][0]["no_sweep"] is True


def test_late_settle_without_overlay_settles_immediately(ew, monkeypatch):
    """没有弹窗叠层 → 与 A6 原行为一字不差（回归护栏）。"""
    calls = []
    ex, step = _exec(ew, monkeypatch, calls, overlay=False)
    ex.do_tap(step)
    st = [c for c in calls if is_settle(c)]
    assert len(st) == 1 and argv_val(st[0], "--node") == "LeafPage"
    assert "late_settle_deferred" not in ex.state
    assert ex.state["late_settled"][0]["reason"] == "arrived_unsettled_target"


def test_retry_deferred_settle_skips_when_not_on_that_page(ew, monkeypatch):
    """推迟后站到了别的页（dumpsys 判位不在该节点）→ 不结，账留着等回来。"""
    calls = []
    ex, step = _exec(ew, monkeypatch, calls, overlay=True)
    ex.do_tap(step)
    ex.dev.overlay = False
    ex.dev.shell = lambda cmd, timeout=30: raw(False, act="OtherPage") if str(cmd).startswith("dumpsys") else ""
    ex._retry_deferred_settle()
    assert not any(is_settle(c) for c in calls)
    assert ex.state["late_settle_deferred"][0]["node"] == "LeafPage"
