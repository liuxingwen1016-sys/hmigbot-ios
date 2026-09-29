"""walk_exec 熔断诊断包 / 决策菜单 / 机械收边 单测（2026-09-09）

对应两项通用改进：
  一、熔断包自带诊断与决策菜单（escalate → diag + options + escalations/step<N>.json）
  二、能机械收的不再熔断（do_tap 的落点解析 / 屏外定向滚动 / 弱哨兵投票接受、verify_at 的挡路弹窗）

铁律（与 test_walk_exec_rules.py 同）：合成计划 + 合成 dump + 假设备，**绝不触碰 adb / 模拟器**；
断言里不出现任何真实 app 的页名/控件名。落点投票**不 monkeypatch**——合成树里给真的
layout_facts.discriminators，让 lib_landing 按它自己的规则投票。
"""
import json, os, sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from test_walk_exec_rules import (FakeDev, ew, mk_exec, wrap, write_plan,  # noqa: F401,E402
                                  write_ledger, esc_of, last_edge,
                                  _reset_ui_words, _no_sleep)             # noqa: F401


ACT = "com.x.HostActivity"          # 合成树的宿主 activity（哨兵 hosts / 落点投票都按它）


def fdev(dumps):
    """定屏假设备：dump 固定，activity 恒为合成树的宿主。"""
    return FakeDev(dumps, activity=ACT)


# ── 设备替身：带页面状态机（tap / 定向 swipe / BACK 都会换页）────────────────────
class NavDev(FakeDev):
    """按「当前页」返回 dump。tap→after_tap 页，BACK→back_to 页，**定向** swipe→after_swipe 页。

    定向 swipe 的判据只用于测试替身：机械收边 (b) 发的那一条时长是 400ms，
    do_tap 原有的三次盲滚 + 两次滚回都是 300ms，用尾部时长把两者分开。
    after_tap 给列表时按次序消费（第一下点进弹窗、第二下点取消回起点）。
    """

    def __init__(self, pages, cur, after_tap=None, back_to=None, after_swipe=None,
                 activity=ACT, **kw):
        super().__init__([pages[cur]], activity=activity, **kw)
        self.pages, self.cur = pages, cur
        self.after_tap, self.back_to, self.after_swipe = after_tap, back_to, after_swipe

    def dump(self):
        return self.pages[self.cur]

    def tap(self, x, y):
        self.taps.append((x, y))
        nxt = (self.after_tap.pop(0) if self.after_tap else None) if isinstance(
            self.after_tap, list) else self.after_tap
        if nxt:
            self.cur = nxt

    def back(self):
        self.backs += 1
        if self.back_to:
            self.cur = self.back_to

    def shell(self, cmd, timeout=30):
        self.shell_log.append(cmd)
        if self.after_swipe and cmd.startswith("input swipe") and cmd.endswith(" 400"):
            self.cur = self.after_swipe
        return ""


# ── 合成树（判别物真值，供 lib_landing 投票）──────────────────────────────────
def _rec(nid, texts, vids, **kw):
    return {"id": nid, "layout_facts": {"discriminators": {"texts": texts, "view_ids": vids}},
            "inbound_triggers": [], "navigation": {"inbound": [], "outbound": []}, **kw}


TREE = {
    "pages": [_rec("HostActivity", ["宿主标题"], ["tv_host"], type="Activity", fq_class="com.x.HostActivity")],
    "fragments": [_rec("SrcFrag", ["源片段标题"], ["tv_src"], type="Fragment", parent_in_nav="HostActivity"),
                  _rec("OtherFrag", ["别处标题"], ["tv_other"], type="Fragment", parent_in_nav="HostActivity"),
                  _rec("W2", ["第二步内容"], ["tv_step2"], type="Fragment", parent_in_nav="HostActivity")],
    "dialogs": [_rec("HostActivity$BlockDlg", ["挡路弹窗"], ["tv_block"], type="Dialog",
                     parent_in_nav="HostActivity")],
}

SENTINELS = {
    "SrcFrag": {"kind": "resource_id_unique", "value": ["tv_src"], "hosts": ["HostActivity"]},
    "OtherFrag": {"kind": "resource_id_unique", "value": ["tv_other"], "hosts": ["HostActivity"]},
    "Dst": {"kind": "resource_id_unique", "value": ["tv_dst"], "hosts": ["HostActivity"]},
    "W2": {"kind": "resource_id_shared", "value": ["ll_step"], "hosts": ["HostActivity"]},
    "HostActivity$BlockDlg": {"kind": "resource_id_unique", "value": ["tv_block"], "hosts": ["HostActivity"]},
}


def page(*inner):
    return wrap("".join(inner))


SRC = page('<node resource-id="com.x:id/tv_src" text="源片段标题" bounds="[0,100][900,200]"/>',
           '<node resource-id="com.x:id/btn_go" text="入口" clickable="true" bounds="[0,300][400,400]"/>')
OTHER = page('<node resource-id="com.x:id/tv_other" text="别处标题" bounds="[0,100][900,200]"/>')
DSTP = page('<node resource-id="com.x:id/tv_dst" text="目标页标题" bounds="[0,100][900,200]"/>')
W2P = page('<node resource-id="com.x:id/ll_step" text="步骤容器" bounds="[0,100][900,200]"/>',
           '<node resource-id="com.x:id/tv_step2" text="第二步内容" bounds="[0,220][900,300]"/>')
BLOCK = page('<node resource-id="com.x:id/tv_block" text="挡路弹窗" bounds="[100,600][900,700]"/>',
             '<node resource-id="com.x:id/btn_cancel" text="取消" clickable="true" bounds="[100,800][400,900]"/>',
             '<node resource-id="com.x:id/btn_ok" text="确定" clickable="true" bounds="[500,800][800,900]"/>')


def steps_for(tap):
    """1 冷启→SrcFrag / 2 本步 / 3 back 回 SrcFrag / 4 note。子树 = 第 3 步。"""
    return [{"step": 1, "action": "coldstart", "to": "SrcFrag"}, tap,
            {"step": 3, "action": "back", "from": tap["to"], "to": "SrcFrag"},
            {"step": 4, "action": "note", "from": "SrcFrag", "to": "SrcFrag"}]


def setup(d, tap, settled=None, sentinels=None):
    sen = dict(SENTINELS)
    sen.update(sentinels or {})
    write_plan(d, [{"walk_id": "w1", "steps": steps_for(tap)}], sentinels=sen)
    write_ledger(d, settled)


def mk(d, dev, **kw):
    ex = mk_exec(d, dev=dev, **kw)
    ex.tree = TREE
    return ex


def pack(d, n=2):
    """熔断整包（落盘副本）——代理实际读的就是这个文件。"""
    return json.load(open(d / "escalations" / f"step{n}.json", encoding="utf-8"))


def tap_step(**kw):
    return {"step": 2, "action": "tap", "from": "SrcFrag", "to": "Dst", "trigger": "入口",
            "static_rid": "btn_go", **kw}


def edges(d):
    return json.load(open(d / "edge_results.json"))


# ══ 一、熔断包：诊断 + 决策菜单 ════════════════════════════════════════════════
def test_escalation_pack_is_written_to_disk_with_diag_and_card(ew):
    """整包除 stdout 外另存 escalations/step<N>.json（覆盖写），dump 落 step<N>.xml。"""
    step = tap_step()
    setup(ew, step)
    ex = mk(ew, fdev([SRC]))
    with pytest.raises(SystemExit) as e:
        ex.escalate(step, "control_not_found")
    assert e.value.code == 30
    info = pack(ew)
    assert info == esc_of(ew)                                  # 落盘副本 == state 里那份
    assert info["escalation_card"].startswith("包内已有判位/控件清单/弹窗判定")
    assert "不要再自行 dump" in info["escalation_card"] and "3 分钟" in info["escalation_card"]
    d = info["diag"]
    assert set(d) >= {"activity", "package", "ime_shown", "screen", "landing_node", "landing_sentinel",
                      "expected_sentinel", "open_dialogs", "control", "clickables_top",
                      "target_settled", "sole_settle_step", "evidence_dump"}
    assert d["activity"] == ACT and d["package"] == "com.x" and d["screen"] == [1080, 1920]
    assert d["ime_shown"] is False and d["open_dialogs"] == []
    assert d["clickables_top"] == [{"rid": "btn_go", "text": "入口", "center": [200, 350]}]
    assert open(d["evidence_dump"], encoding="utf-8").read() == SRC     # dump 也落了盘
    assert info["resume_hint"].startswith("处理后三选一")                # 旧字段保留
    # 覆盖写：同一步再熔断一次只留最新一份
    with pytest.raises(SystemExit):
        mk(ew, fdev([SRC])).escalate(step, "back_failed")
    assert pack(ew)["reason"] == "back_failed"


def test_diag_landing_and_open_dialogs_are_machine_resolved(ew):
    """判位（判别物投票）与「屏上有哪些弹窗」都由执行器采好，代理不必再自己 dump 一遍。"""
    step = tap_step()
    setup(ew, step)
    with pytest.raises(SystemExit):
        mk(ew, fdev([BLOCK])).escalate(step, "position_mismatch", verify_node="SrcFrag")
    d = pack(ew)["diag"]
    assert d["landing_node"] == "HostActivity$BlockDlg"          # 弹窗层优先于子页/宿主
    assert d["landing_sentinel"] == {"node": "HostActivity$BlockDlg", "ok": True, "weak": False,
                                     "why": "宿主符合 + 唯一 id 可见命中 1/1"}
    assert d["expected_sentinel"]["node"] == "SrcFrag" and d["expected_sentinel"]["ok"] is False
    assert d["open_dialogs"] == ["HostActivity$BlockDlg"]
    assert d["cancel_control"]["rid"] == "btn_cancel" and d["cancel_control"]["center"] == [250, 850]


def test_options_control_not_found_three_branches_and_fallback(ew):
    """control_not_found 的菜单分支：无覆盖损失的 skip / 屏外 resume / 不可点 manual_tap / 兜底 skip。"""
    # ① 本步不结账（或目标已入账）→ 推荐 skip，明确 coverage_loss=false
    step = tap_step()
    setup(ew, step)
    with pytest.raises(SystemExit):
        mk(ew, fdev([SRC])).escalate(step, "control_not_found")
    o = pack(ew)["options"][0]
    assert o["key"] == "skip" and o["coverage_loss"] is False
    assert "--skip-step 2" in o["cmd"] and "control_absent(btn_go)" in o["cmd"]
    assert "--walk w1" in o["cmd"] and "--package com.x" in o["cmd"] and "--no-blackbox" in o["cmd"]

    # ② 控件在 dump 里但在屏幕高之外 → 推荐 resume（下一趟执行器会定向滚动）
    step2 = tap_step(settles_capture="Dst")
    setup(ew, step2)
    off = page('<node resource-id="com.x:id/btn_go" text="入口" clickable="false" bounds="[0,3000][1000,3100]"/>')
    with pytest.raises(SystemExit):
        mk(ew, fdev([off])).escalate(step2, "control_not_found")
    info = pack(ew)
    assert info["diag"]["control"]["in_dump"] is True and info["diag"]["control"]["offscreen"] is True
    assert info["diag"]["control"]["in_clickables"] is False
    o = info["options"][0]
    assert o["key"] == "resume" and o["coverage_loss"] is False and "--assume-at SrcFrag" in o["cmd"]

    # ③ 在 dump 里、屏内、但不在可点集 → 手点 bounds 中心后 --mark-step-done
    setup(ew, step2)
    nocl = page('<node resource-id="com.x:id/btn_go" text="入口" clickable="false" bounds="[0,300][400,400]"/>')
    with pytest.raises(SystemExit):
        mk(ew, fdev([nocl])).escalate(step2, "control_not_found")
    o = pack(ew)["options"][0]
    assert o["key"] == "manual_tap" and o["cmd"].startswith("adb -s fake-serial shell input tap 200 350")
    assert "--mark-step-done 2" in o["cmd"] and "--assume-at Dst" in o["cmd"]

    # ④ 都不命中 → 兜底 skip，覆盖损失如实标注（本步是目标唯一未结账的结账步）
    setup(ew, step2)
    with pytest.raises(SystemExit):
        mk(ew, fdev([OTHER])).escalate(step2, "control_not_found")
    info = pack(ew)
    assert info["diag"]["sole_settle_step"] is True
    o = info["options"][0]
    assert o["key"] == "skip" and o["coverage_loss"] is True and len(info["options"]) == 1


def test_options_arrival_unverified_landed_and_no_effect(ew):
    """arrival_unverified：落点=起点→no_effect；落点=别的强命中节点→skip_landed 带 --assume-at。"""
    step = tap_step(settles_capture="Dst")
    setup(ew, step)
    with pytest.raises(SystemExit):
        mk(ew, fdev([SRC])).escalate(step, "arrival_unverified")
    o = pack(ew)["options"][0]
    assert o["key"] == "skip" and "--skip-reason no_effect" in o["cmd"]

    setup(ew, step)
    with pytest.raises(SystemExit):
        mk(ew, fdev([OTHER])).escalate(step, "arrival_unverified")
    opts = pack(ew)["options"]
    assert opts[0]["key"] == "skip_landed" and opts[0]["coverage_loss"] is True
    assert "--skip-reason landed:OtherFrag" in opts[0]["cmd"] and "--assume-at OtherFrag" in opts[0]["cmd"]
    assert [o["key"] for o in opts[1:]] == ["resume", "skip"]        # 兜底两条仍在

    # 屏上有弹窗 → 先关弹窗再续走（cmd 直接给出取消控件坐标）
    setup(ew, step)
    with pytest.raises(SystemExit):
        mk(ew, fdev([BLOCK])).escalate(step, "arrival_unverified")
    keys = [o["key"] for o in pack(ew)["options"]]
    assert "close_dialog_then_resume" in keys
    o = next(o for o in pack(ew)["options"] if o["key"] == "close_dialog_then_resume")
    assert o["cmd"].startswith("adb -s fake-serial shell input tap 250 850") and "--assume-at SrcFrag" in o["cmd"]


def test_options_position_mismatch_recommends_assume_at_landing(ew):
    step = tap_step()
    setup(ew, step)
    with pytest.raises(SystemExit):
        mk(ew, fdev([OTHER])).escalate(step, "position_mismatch", verify_node="SrcFrag")
    opts = pack(ew)["options"]
    assert opts[0]["key"] == "resume_assume" and "--assume-at OtherFrag" in opts[0]["cmd"]
    assert opts[-1]["key"] == "resume" and "--assume-at" not in opts[-1]["cmd"]


def test_options_back_failed_and_manual_reasons(ew):
    step = {"step": 2, "action": "back", "from": "Dst", "to": "SrcFrag"}
    write_plan(ew, [{"walk_id": "w1", "steps": [step]}], sentinels=SENTINELS)
    write_ledger(ew)
    with pytest.raises(SystemExit):
        mk(ew, fdev([BLOCK])).escalate(step, "back_failed")
    opts = pack(ew)["options"]
    assert opts[0]["key"] == "close_dialog_then_resume"          # BACK 被弹窗吃掉：先点取消
    assert opts[-1]["key"] == "walk_back_to_then_resume"
    assert "walk_back_to.py" in opts[-1]["cmd"] and "--expect-host HostActivity" in opts[-1]["cmd"]

    for reason in ("input_failed", "input_target_not_found", "gate_pass_unknown"):
        with pytest.raises(SystemExit):
            mk(ew, fdev([SRC])).escalate(step, reason)
        o = pack(ew)["options"][0]
        assert o["key"] == "manual_then_mark_done" and "--mark-step-done 2" in o["cmd"]


def test_options_unknown_reason_keeps_generic_three(ew):
    step = tap_step()
    setup(ew, step)
    with pytest.raises(SystemExit):
        mk(ew, fdev([SRC])).escalate(step, "llm_action")
    assert [o["key"] for o in pack(ew)["options"]] == ["resume", "mark_step_done", "skip"]


def test_diag_never_raises_even_when_device_is_broken(ew):
    """诊断绝不能自己抛错：设备侧全挂时每项置 null，熔断仍然正常交还。"""
    class DeadDev(FakeDev):
        def dump(self):
            raise RuntimeError("device gone")

        def current_activity(self):
            raise RuntimeError("device gone")

        def screenshot(self, path):
            raise RuntimeError("device gone")

    step = tap_step()
    setup(ew, step)
    with pytest.raises(SystemExit) as e:
        mk(ew, DeadDev(activity=ACT)).escalate(step, "control_not_found")
    assert e.value.code == 30
    info = pack(ew)
    assert info["observed_activity"] == "?" and info["diag"]["landing_node"] is None
    assert info["options"] and info["options"][0]["key"] == "skip"


# ══ 二、能机械收的不再熔断 ═════════════════════════════════════════════════════
# (a) 到达失败 → 落点解析
def test_a_no_effect_is_recorded_without_meltdown(ew):
    """落点解析仍是起点 = 这一下点击没效果：记 not_reproduced(no_effect) + 跳子树续走。"""
    step = tap_step()
    setup(ew, step)
    ex = mk(ew, NavDev({"src": SRC}, "src"))
    ex.do_tap(step)                                            # 不抛
    e = last_edge(ew)
    assert e["status"] == "not_reproduced" and e["note"].startswith("no_effect:")
    assert e["control"]["rid"] == "btn_go" and ex._jump_to == 3 and ex.state["skipped"] == [3]
    assert any("no_effect" in n for n in ex.state["notes"])
    assert not os.path.exists(ew / "escalations" / "step2.json")


def test_a_landed_elsewhere_records_discovered_edge_and_recovers(ew):
    """落到树内别的节点：本边记 landed，另补一条 discovered edge，再机械回位续走。"""
    step = tap_step()
    setup(ew, step)
    ex = mk(ew, NavDev({"src": SRC, "other": OTHER}, "src", after_tap="other", back_to="src"))
    ex.do_tap(step)
    planned, discovered = edges(ew)[-2], edges(ew)[-1]
    assert planned["status"] == "not_reproduced" and planned["landed"] == "OtherFrag"
    assert planned["to"] == "Dst" and "landed_elsewhere" in planned["note"]
    assert discovered == {**discovered, "from": "SrcFrag", "to": "OtherFrag",
                          "status": "confirmed", "discovered": True}
    assert discovered["control"]["rid"] == "btn_go"
    assert ex.dev.backs == 1 and ex._jump_to == 3               # 一次 BACK 就回到起点
    assert ex.dev.cur == "src"


def test_a_landed_on_unsettled_dialog_settles_it(ew):
    """落点是未结账的弹窗 → 顺手 dialog_direct 结账（弹窗是叶子，capture 内核拒跑）。"""
    step = tap_step()
    setup(ew, step)
    ex = mk(ew, NavDev({"src": SRC, "dlg": BLOCK}, "src", after_tap=["dlg", "src"]))
    ex.do_tap(step)
    assert edges(ew)[-1]["to"] == "HostActivity$BlockDlg"
    settled = json.load(open(ew / "ledger.json"))["settled"]
    assert settled["HostActivity$BlockDlg"]["capture"] == "dialog_direct"
    assert ex.dev.taps[-1] == (250, 850)                        # 回位时点「取消」而不是按 BACK
    assert ex.dev.backs == 0


def test_a_recovery_failure_escalates_position_mismatch_with_menu(ew):
    """回不到起点才熔断——且菜单直接给出 --assume-at <落点>。"""
    step = tap_step()
    setup(ew, step)
    ex = mk(ew, NavDev({"src": SRC, "other": OTHER}, "src", after_tap="other"))   # BACK 也回不去
    with pytest.raises(SystemExit) as e:
        ex.do_tap(step)
    assert e.value.code == 30
    info = pack(ew)
    assert info["reason"] == "position_mismatch" and "机械回位 2 次" in info["detail"]
    assert info["options"][0]["key"] == "resume_assume" and "--assume-at OtherFrag" in info["options"][0]["cmd"]
    assert edges(ew)[-1]["discovered"] is True                  # 熔断前边真值已经落账，不白跑


def test_a_sole_settle_step_still_melts_down(ew):
    """覆盖优先于速度：本步是目标唯一且未结账的结账步 → 机械收边一律让位给熔断。"""
    step = tap_step(settles_capture="Dst")
    setup(ew, step)
    ex = mk(ew, NavDev({"src": SRC}, "src"))
    with pytest.raises(SystemExit) as e:
        ex.do_tap(step)
    assert e.value.code == 30 and pack(ew)["reason"] == "arrival_unverified"
    assert not os.path.exists(ew / "edge_results.json")          # 没有就地记账
    # 同一条边，目标已由别处结账 → 例外解除，机械收下
    setup(ew, step, settled={"Dst": {"via": "别处"}})
    ex2 = mk(ew, NavDev({"src": SRC}, "src"))
    ex2.do_tap(step)
    assert last_edge(ew)["note"].startswith("no_effect:")


# (b) 屏外控件定向滚动
def test_b_offscreen_control_directed_scroll(ew):
    """控件在 dump 里但在屏幕高之外 → 按 bounds 与屏幕中心的差值定向滑一次再找，不熔断。"""
    step = tap_step(static_rid="btn_far", trigger="远处入口")
    setup(ew, step)
    far = page('<node resource-id="com.x:id/tv_src" text="源片段标题" bounds="[0,100][900,200]"/>',
               # 未绑定的列表行：有 resource-id、在层级里，但既不在屏内也还不可点
               '<node resource-id="com.x:id/btn_far" text="远处入口" clickable="false" bounds="[0,3000][1000,3100]"/>')
    scrolled = page('<node resource-id="com.x:id/tv_src" text="源片段标题" bounds="[0,100][900,200]"/>',
                    '<node resource-id="com.x:id/btn_far" text="远处入口" clickable="true" bounds="[0,900][1000,1000]"/>')
    dev = NavDev({"far": far, "scrolled": scrolled, "dst": DSTP}, "far",
                 after_tap="dst", after_swipe="scrolled")
    ex = mk(ew, dev)
    ex.do_tap(step)
    assert "input swipe 540 1344 540 1 400" in dev.shell_log     # 定向：向上滑 dy=+2090
    assert dev.taps == [(500, 950)]
    e = last_edge(ew)
    assert e["status"] == "confirmed" and e["note"].startswith("offscreen_scroll:")
    assert any("offscreen_scroll" in n for n in ex.state["notes"])


def test_b_onscreen_miss_does_not_scroll(ew):
    """控件就在屏内却没找到 = 别的原因（不可点/被遮），不该靠滚动救 → 走原熔断路径。"""
    step = tap_step(settles_capture="Dst")
    setup(ew, step)
    onscreen = page('<node resource-id="com.x:id/tv_src" text="源片段标题" bounds="[0,100][900,200]"/>',
                    '<node resource-id="com.x:id/btn_go" text="入口" clickable="false" bounds="[0,300][400,400]"/>')
    dev = NavDev({"p": onscreen}, "p")
    with pytest.raises(SystemExit):
        mk(ew, dev).do_tap(step)
    assert pack(ew)["reason"] == "control_not_found"
    assert not any(c.endswith(" 400") for c in dev.shell_log)    # 一次定向滚动都没发


# (c) 弱哨兵按落点投票接受
def test_c_weak_sentinel_accepted_by_landing_vote(ew):
    """弱哨兵 + 落点投票（另一套判据）同时指向 to → 机械接受，不再烧一次 LLM 看图。"""
    step = tap_step(to="W2")
    setup(ew, step)
    ex = mk(ew, NavDev({"src": SRC, "w2": W2P}, "src", after_tap="w2"))
    ex.do_tap(step)
    e = last_edge(ew)
    assert e["status"] == "confirmed" and "weak_accepted_by_landing_vote" in e["note"]
    assert any("weak_accepted_by_landing_vote" in n for n in ex.state["notes"])


def test_c_weak_sentinel_without_vote_still_melts_down(ew):
    """投票投不出（判别物不在屏上）→ 仍旧交 LLM 看图，不许自说自话收下。"""
    step = tap_step(to="W2")
    setup(ew, step)
    bare = page('<node resource-id="com.x:id/ll_step" text="步骤容器" bounds="[0,100][900,200]"/>')
    ex = mk(ew, NavDev({"src": SRC, "w2": bare}, "src", after_tap="w2"))
    with pytest.raises(SystemExit):
        ex.do_tap(step)
    info = pack(ew)
    assert info["reason"] == "weak_sentinel_confirm"
    assert info["options"][0]["key"] == "resume_assume" and "--assume-at W2" in info["options"][0]["cmd"]


# (d) 起点被弹窗挡住
def test_d_blocking_dialog_is_cancelled_before_meltdown(ew):
    """判位失败但屏上强命中了别的弹窗 → 点一次取消（绝不点确定）再判，判到就不熔断。"""
    step = tap_step()
    setup(ew, step)
    dev = NavDev({"blk": BLOCK, "src": SRC}, "blk", after_tap="src")
    ex = mk(ew, dev)
    assert ex.verify_at("SrcFrag", step, "起点") == SRC
    assert dev.taps == [(250, 850)]                              # 只点了「取消」，没碰「确定」
    assert any("被弹窗 HostActivity$BlockDlg 挡住" in n for n in ex.state["notes"])
    assert dev.backs == 0


def test_d_no_cancel_control_falls_back_to_back_key(ew):
    step = tap_step()
    setup(ew, step)
    nocancel = page('<node resource-id="com.x:id/tv_block" text="挡路弹窗" bounds="[100,600][900,700]"/>')
    dev = NavDev({"blk": nocancel, "src": SRC}, "blk", back_to="src")
    ex = mk(ew, dev)
    assert ex.verify_at("SrcFrag", step, "起点") == SRC
    assert dev.backs == 1 and dev.taps == []


def test_d_expected_dialog_itself_is_not_dismissed(ew):
    """期望落点就是那个弹窗时不算「挡路」——绝不把自己要采的证据点掉。"""
    step = tap_step(to="HostActivity$BlockDlg")
    setup(ew, step)
    dev = NavDev({"blk": BLOCK}, "blk")
    ex = mk(ew, dev)
    assert ex.verify_at("HostActivity$BlockDlg", step, "落点") == BLOCK
    assert dev.taps == [] and dev.backs == 0


def test_d_skipped_when_no_gate(ew):
    """no_gate（stop_at_dialog / 计划内门步）一律不碰弹窗：取消也是碰。"""
    step = tap_step(safety="stop_at_dialog")
    setup(ew, step)
    dev = NavDev({"blk": BLOCK, "src": SRC}, "blk", after_tap="src")
    with pytest.raises(SystemExit) as e:
        mk(ew, dev).verify_at("SrcFrag", step, "落点", no_gate=True)
    assert e.value.code == 30 and dev.taps == [] and dev.backs == 0
    assert pack(ew)["reason"] == "position_mismatch"


# ── 公共覆盖例外判定 ─────────────────────────────────────────────────────────
def test_sole_settle_step_predicate(ew):
    step = tap_step(settles_capture="Dst")
    setup(ew, step)
    ex = mk(ew, fdev([SRC]))
    assert ex._is_sole_settle_step(step) is True
    assert ex._is_sole_settle_step(tap_step()) is False              # 本步不结账
    write_ledger(ew, {"Dst": {"via": "别处"}})
    assert ex._is_sole_settle_step(step) is False                    # 目标已入账


def test_handoff_due_flag_follows_escalation_budget(ew, monkeypatch, tmp_path):
    """动态边界：第 N 次熔断包带 handoff_due=true（N=--max-escalations，默认 12）。"""
    import json as _j, walk_exec as we
    step = {"step": 5, "action": "tap", "from": "P", "to": "Q", "trigger": "x", "static_rid": "btn_q"}
    write_plan(ew, [{"walk_id": "w1", "steps": [step]}],
               sentinels={"P": {"kind": "activity_suffix", "value": "HomeActivity"},
                          "Q": {"kind": "activity_suffix", "value": "QActivity"}})
    write_ledger(ew)
    ex = mk_exec(ew, dev=FakeDev([wrap("<node/>")]))
    ex.a.max_escalations = 2
    ex.state["escalations"] = 0
    with pytest.raises(SystemExit):
        ex.escalate(step, "control_not_found", detail="d")
    pkt = _j.load(open(ew / "escalations" / "step5.json"))
    assert pkt["handoff_due"] is False and pkt["escalations_so_far"] == 1
    with pytest.raises(SystemExit):
        ex.escalate(step, "control_not_found", detail="d")
    pkt = _j.load(open(ew / "escalations" / "step5.json"))
    assert pkt["handoff_due"] is True and pkt["escalations_so_far"] == 2


def test_wall_budget_from_driver_lock_forces_handoff(ew, monkeypatch, tmp_path):
    """墙钟预算：在飞锁 ts 很早 + 预算 1 分钟 → run() 第一步前就出 wall_budget_exhausted 且 handoff_due=true。"""
    import json as _j, time as _t, walk_exec as we
    step = {"step": 1, "action": "tap", "from": "P", "to": "Q", "trigger": "x", "static_rid": "btn_q"}
    write_plan(ew, [{"walk_id": "w1", "steps": [step]}],
               sentinels={"P": {"kind": "activity_suffix", "value": "HomeActivity"},
                          "Q": {"kind": "activity_suffix", "value": "QActivity"}})
    write_ledger(ew)
    _j.dump({"walk_id": "w1", "ts": _t.time() - 3600}, open(ew / ".driver_in_flight.json", "w"))
    ex = mk_exec(ew, dev=FakeDev([wrap("<node/>")]))
    ex.a.budget_min = 1
    with pytest.raises(SystemExit):
        ex.run()
    pkt = _j.load(open(ew / "escalations" / "step1.json"))
    assert pkt["reason"] == "wall_budget_exhausted" and pkt["handoff_due"] is True


def test_order_exempt_walk_bypasses_trip_gate(ew, monkeypatch, tmp_path):
    import json as _j, walk_exec as we
    write_plan(ew, [{"walk_id": "w0", "trip_id": "t1", "steps": [{"step": 1, "action": "coldstart", "to": "R"}]},
                    {"walk_id": "w1", "trip_id": "t2", "steps": [{"step": 1, "action": "coldstart", "to": "R"}]},
                    {"walk_id": "w6", "trip_id": "t1", "dynamic": True, "order_exempt": True,
                     "steps": [{"step": 1, "action": "coldstart", "to": "R"}]}])
    write_ledger(ew, settled={"Z": {"capture_meta": {"trip_id": "t2"}}})
    ex = mk_exec(ew, dev=FakeDev([wrap("<node/>")]), walk="w6")
    ex._check_trip_order()                                   # 不抛 SystemExit 即通过
