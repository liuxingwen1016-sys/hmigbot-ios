"""walk_exec 第四轮 A 批单测（2026-09-10 A1~A6）

铁律同 test_walk_exec_rules：合成计划 + 合成 dump + FakeDev，**绝不触碰 adb / 模拟器**；
node_sweep / walk_ledger 子进程一律 monkeypatch；断言里不出现任何真实 app 的页名/控件名
（一律 RootPage / HubPage / LeafPage / ConfirmDlg 这类占位名）。

覆盖：
  A1 门已消费 → 熔断菜单 skip 占推荐位
  A2 chain_advanced_unresolved 首项换成带 --assume-at 的续走（+ 同节点不重复普查）
  A3 action==verify 的步首项换成「先把设备弄回宿主再 --resume」
  A4 门放行步落点与计划不符时先信运行时
  A5 多重边消歧（同 from/to 两个控件）+ tap 后 rid 与计划不符如实记
  A6 结账判据从计划步属性改成运行时事实（含「带 settles_capture 的步一字不变」回归）
"""
import json, os, sys, types
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import walk_exec as we  # noqa: E402
from test_walk_exec_rules import (FakeDev, ew, mk_exec, wrap, write_plan,      # noqa: F401,E402
                                  write_ledger, esc_of, last_edge,
                                  _reset_ui_words, _no_sleep)                  # noqa: F401


# ── 公共夹具 ────────────────────────────────────────────────────────────────
ROOT_ACT = "com.x.RootActivity"


def proc(rc=0, out=""):
    return types.SimpleNamespace(returncode=rc, stdout=out, stderr="")


def run_stub(monkeypatch, calls, rc=0, out=""):
    """替掉所有子进程（node_sweep / walk_ledger）：只记 argv。"""
    def _run(cmd, **kw):
        calls.append(list(cmd))
        return proc(rc, out)
    monkeypatch.setattr(we.subprocess, "run", _run)
    return calls


def argv_val(argv, flag):
    return argv[argv.index(flag) + 1] if flag in argv else None


def is_sweep(argv):
    return any(str(x).endswith("node_sweep.py") for x in argv)


def is_settle(argv):
    return any(str(x).endswith("walk_ledger.py") for x in argv) and "settle" in argv


def rec(nid, texts=(), vids=(), **kw):
    """树 record：判别物真值给 lib_landing 投票（落点**不** monkeypatch，走它自己的规则）。"""
    return {"id": nid, "layout_facts": {"discriminators": {"texts": list(texts), "view_ids": list(vids)}},
            "inbound_triggers": [], "navigation": {"inbound": [], "outbound": []}, **kw}


def opts_of(d, steps, step_idx, reason, diag, ctx=None, sentinels=None, **kw):
    write_plan(d, [{"walk_id": "w1", "steps": steps}], sentinels=sentinels or {})
    write_ledger(d)
    ex = mk_exec(d, dev=FakeDev(), **kw)
    return ex._options(steps[step_idx], reason, diag, ctx or {})


# ══ A1 门已消费 → skip 占推荐位 ═══════════════════════════════════════════════
GATE_STEPS = [{"step": 1, "action": "coldstart", "to": "RootPage"},
              {"step": 2, "action": "tap", "from": "RootPage", "to": "RootPage$GateDlg", "gate": True,
               "auto_transition": True, "static_rid": "btn_agree", "settles_capture": "RootPage$GateDlg"},
              {"step": 3, "action": "gate_pass", "from": "RootPage$GateDlg", "to": "RootPage", "gate": True},
              {"step": 4, "action": "tap", "from": "RootPage", "to": "HubPage", "trigger": "入口",
               "static_rid": "btn_hub"},
              {"step": 5, "action": "tap", "from": "HubPage", "to": "LeafPage", "trigger": "叶子",
               "static_rid": "btn_leaf"},
              {"step": 6, "action": "back", "from": "LeafPage", "to": "HubPage"}]


def gdiag(land="HubPage", strong=True, in_dump=False, in_clk=False):
    return {"activity": ROOT_ACT, "screen": [1080, 1920], "landing_node": land,
            "landing_why": "fragment 判别物命中 3 条",
            "landing_sentinel": {"node": land, "ok": bool(strong), "weak": not strong},
            "expected_sentinel": {"node": "RootPage$GateDlg", "ok": False, "weak": False},
            "open_dialogs": [], "cancel_control": None, "clickables_top": [],
            "control": {"rid": None, "static_rid": "btn_agree", "label": None,
                        "in_dump": in_dump, "in_clickables": in_clk},
            "target_settled": False, "sole_settle_step": False}


def test_a1_consumed_gate_puts_skip_first_with_reason(ew):
    """门步 + 控件既不在 dump 也不在可点集 + 强落点是计划里更靠后的节点 → options[0] 换成 skip。"""
    opts = opts_of(ew, GATE_STEPS, 1, "position_mismatch", gdiag(),
                   ctx={"verify_node": "RootPage$GateDlg"})
    o = opts[0]
    assert o["key"] == "skip_gate_consumed" and o["coverage_loss"] is False
    assert "--skip-step 2" in o["cmd"] and "gate_consumed:landed_HubPage" in o["cmd"]
    assert "一次性门已被前序步消费" in o["effect"] and "共 2 步" in o["effect"]      # D① 的子树代价仍在
    assert "宿主已越过该门" in o["when"]
    assert any(x["key"] == "resume_assume" for x in opts[1:])                        # 老首项退居其次，不删


def test_a1_not_fired_when_control_on_screen_or_landing_not_past(ew):
    """三条反例：控件还在屏上 / 落点是计划里更靠前的节点 / 本步不是门步 → 菜单一字不变。"""
    # ① 控件仍在 dump（或可点集）里 → 门还在，照旧推 resume_assume
    for kw in ({"in_dump": True}, {"in_clk": True}):
        opts = opts_of(ew, GATE_STEPS, 1, "position_mismatch", gdiag(**kw),
                       ctx={"verify_node": "RootPage$GateDlg"})
        assert opts[0]["key"] == "resume_assume" and not any(
            o["key"] == "skip_gate_consumed" for o in opts)
    # ② 落点是计划里**本步之前**就出现过的节点（还没越过门）
    opts = opts_of(ew, GATE_STEPS, 1, "position_mismatch", gdiag(land="RootPage"),
                   ctx={"verify_node": "RootPage$GateDlg"})
    assert opts[0]["key"] == "resume_assume"
    # ③ 落点弱判 → 不成立
    opts = opts_of(ew, GATE_STEPS, 1, "position_mismatch", gdiag(strong=False),
                   ctx={"verify_node": "RootPage$GateDlg"})
    assert not any(o["key"] == "skip_gate_consumed" for o in opts)
    # ④ 本步没被计划标 gate（普通边）→ 与门无关，绝不套用
    d = gdiag(land="LeafPage")
    d["control"] = {"rid": None, "static_rid": "btn_hub", "in_dump": False, "in_clickables": False}
    opts = opts_of(ew, GATE_STEPS, 3, "position_mismatch", d, ctx={"verify_node": "HubPage"})
    assert not any(o["key"] == "skip_gate_consumed" for o in opts)


# ══ A2 chain_advanced_unresolved 首项 ════════════════════════════════════════
CHAIN_STEPS = [{"step": 1, "action": "coldstart", "to": "RootPage"},
               {"step": 2, "action": "tap", "from": "RootPage", "to": "HubPage", "trigger": "入口",
                "static_rid": "btn_hub", "settles_capture": "HubPage"},
               {"step": 3, "action": "tap", "from": "HubPage", "to": "LeafPage", "trigger": "叶子",
                "static_rid": "btn_leaf"},
               {"step": 4, "action": "back", "from": "LeafPage", "to": "HubPage"},
               {"step": 5, "action": "back", "from": "HubPage", "to": "RootPage"}]
BIG_CHAIN_STEPS = CHAIN_STEPS[:3] + [
    {"step": 4, "action": "tap", "from": "LeafPage", "to": "DeepPage", "trigger": "深", "static_rid": "btn_deep"},
    {"step": 5, "action": "tap", "from": "DeepPage", "to": "DeeperPage", "trigger": "更深", "static_rid": "btn_deeper"},
    {"step": 6, "action": "back", "from": "DeeperPage", "to": "DeepPage"},
    {"step": 7, "action": "back", "from": "DeepPage", "to": "LeafPage"},
    {"step": 8, "action": "back", "from": "LeafPage", "to": "HubPage"},
    {"step": 9, "action": "back", "from": "HubPage", "to": "RootPage"}]


def cdiag(land="SideBranchPage", strong=True):
    return {"activity": ROOT_ACT, "screen": [1080, 1920], "landing_node": land,
            "landing_why": "fragment 判别物命中 4 条",
            "landing_sentinel": {"node": land, "ok": bool(strong), "weak": not strong},
            "expected_sentinel": {"node": "HubPage", "ok": False, "weak": True},
            "open_dialogs": [], "cancel_control": None, "clickables_top": [],
            "control": {"rid": "btn_hub", "static_rid": "btn_hub", "in_dump": False, "in_clickables": True},
            "target_settled": True, "sole_settle_step": False}


def test_a2_chain_advanced_first_option_is_assume_at_landing(ew):
    """普查推进了链：首项必须是带 --assume-at <实测落点> 的续走，**绝不是原步重试**。"""
    opts = opts_of(ew, CHAIN_STEPS, 1, "chain_advanced_unresolved", cdiag())
    o = opts[0]
    assert o["key"] == "mark_done_assume_landing"
    assert "--mark-step-done 2" in o["cmd"] and "--assume-at SideBranchPage" in o["cmd"]
    assert "--resume" not in o["cmd"]                                  # 原步重试 = 普查再推一次链
    assert "结账与普查在熔断前已完成" in o["effect"] and "不会重跑" in o["effect"]
    assert all(x["key"] != "resume" for x in opts[:1])


def test_a2_big_subtree_does_not_resurrect_resume_first(ew):
    """子树够大时 D② 会把 resume_assume 提到首位——本 reason 必须免疫，否则死循环复活。"""
    opts = opts_of(ew, BIG_CHAIN_STEPS, 1, "chain_advanced_unresolved", cdiag())
    assert opts[0]["key"] == "mark_done_assume_landing"
    assert not any(o["key"] == "resume_assume" for o in opts)


def test_a2_unresolved_landing_falls_back_to_skip_not_resume(ew):
    """落点判不出（投票不强）→ 首项换成 skip，仍然不是 resume。"""
    opts = opts_of(ew, CHAIN_STEPS, 1, "chain_advanced_unresolved", cdiag(strong=False))
    assert opts[0]["key"].startswith("skip")
    assert "chain_advanced_landing_unresolved" in opts[0]["cmd"] and "--resume" not in opts[0]["cmd"]
    assert opts[0]["effect"].startswith("该边记 not_reproduced")


SWEEP_SENT = {"HubPage": {"kind": "activity_suffix", "value": "HomeActivity"}}


def sweep_exec(d, monkeypatch, calls):
    write_plan(d, [{"walk_id": "w1", "steps": CHAIN_STEPS}], sentinels=SWEEP_SENT)
    write_ledger(d)
    run_stub(monkeypatch, calls)
    return mk_exec(d, dev=FakeDev([wrap("<node/>")], activity="com.x.HomeActivity"),
                   no_grounding=False, no_blackbox=True)


def test_a2_sweep_skipped_for_node_already_swept_in_this_walk(ew, monkeypatch):
    """--mark-step-done 续走会对同一节点再触发一次普查；链页重扫 = 再推一次链，必须挡住。"""
    calls = []
    ex = sweep_exec(ew, monkeypatch, calls)
    ex.state["sweep_ran"] = [{"node": "HubPage", "rc": 0}]
    assert ex._maybe_sweep("HubPage", CHAIN_STEPS[1]) is None
    assert calls == [] and any("已普查过" in n for n in ex.state["notes"])


def test_a2_sweep_still_runs_for_fresh_node(ew, monkeypatch):
    """反例：本 walk 没普查过的节点照跑（去重只挡重复，不挡首达）。"""
    calls = []
    ex = sweep_exec(ew, monkeypatch, calls)
    ex._maybe_sweep("HubPage", CHAIN_STEPS[1])
    assert len(calls) == 1 and is_sweep(calls[0]) and argv_val(calls[0], "--node") == "HubPage"
    assert ex.state["sweep_ran"][-1]["node"] == "HubPage"


# ══ A3 verify 步的推荐位 ════════════════════════════════════════════════════
V_STEPS = [{"step": 1, "action": "coldstart", "to": "RootPage"},
           {"step": 2, "action": "tap", "from": "RootPage", "to": "HubPage", "trigger": "入口",
            "static_rid": "btn_hub"},
           {"step": 3, "action": "tap", "from": "HubPage", "to": "LeafPage", "trigger": "叶子",
            "static_rid": "btn_leaf"},
           {"step": 4, "action": "verify", "from": None, "to": "HubPage", "kind": "host"}]
V_SENT = {"RootPage": {"kind": "activity_suffix", "value": "com.x.RootActivity"},
          "HubPage": {"kind": "resource_id_unique", "value": ["tv_hub"], "hosts": ["HubActivity"]}}


def vdiag(activity):
    return {"activity": activity, "screen": [1080, 1920], "landing_node": "SubPage",
            "landing_why": "activity_only", "open_dialogs": [], "cancel_control": None,
            "landing_sentinel": {"node": "SubPage", "ok": True, "weak": False},
            "expected_sentinel": {"node": "HubPage", "ok": False, "weak": False},
            "control": None, "clickables_top": [], "target_settled": False, "sole_settle_step": False}


def test_a3_verify_step_recommends_device_recovery_not_assume_at(ew):
    """子 activity 压在宿主上 → 单次 BACK 再 --resume；effect 必须写明根 activity 禁 BACK 的边界。"""
    opts = opts_of(ew, V_STEPS, 3, "position_mismatch", vdiag("com.x.SubPageActivity"),
                   ctx={"verify_node": "HubPage"}, sentinels=V_SENT)
    o = opts[0]
    assert o["key"] == "back_then_resume"
    assert "input keyevent 4" in o["cmd"] and "--resume" in o["cmd"]
    assert "--assume-at" not in o["cmd"]                       # 只改声明改不动设备
    assert "禁按 BACK" in o["effect"] and "--assume-at 改不了它" in o["effect"]
    assert o["cmd"].index("keyevent 4") < o["cmd"].index("&&")  # 先弄设备，再续走


def test_a3_on_root_activity_recommends_renav_instead_of_back(ew):
    """反例：当前就在根/宿主 activity（BACK 会退出 app）→ 换成按到达路径重新导航。"""
    opts = opts_of(ew, V_STEPS, 3, "position_mismatch", vdiag("com.x.HubActivity"),
                   ctx={"verify_node": "HubPage"}, sentinels=V_SENT)
    o = opts[0]
    assert o["key"] == "renav_then_resume" and "keyevent" not in o["cmd"]
    assert "RootPage→HubPage" in o["effect"] and "[2]" in o["effect"]   # 到达路径 + 推进步号
    assert "--resume" in o["cmd"]


def test_a3_non_verify_step_menu_unchanged(ew):
    """回归：非 verify 步的推荐位保持旧行为（落点强命中 → resume_assume）。"""
    opts = opts_of(ew, V_STEPS, 2, "position_mismatch", vdiag("com.x.SubPageActivity"),
                   ctx={"verify_node": "LeafPage"}, sentinels=V_SENT)
    assert opts[0]["key"] == "resume_assume" and "--assume-at SubPage" in opts[0]["cmd"]


# ══ A4 门放行落点先信运行时 ══════════════════════════════════════════════════
GP_STEPS = [{"step": 1, "action": "coldstart", "to": "RootPage"},
            {"step": 2, "action": "tap", "from": "RootPage", "to": "RootPage$GateDlg", "gate": True,
             "auto_transition": True, "settles_capture": "RootPage$GateDlg"},
            {"step": 3, "action": "gate_pass", "from": "RootPage$GateDlg", "to": "RootPage", "gate": True},
            {"step": 4, "action": "tap", "from": "WizardPage", "to": "LeafPage", "trigger": "叶子",
             "static_rid": "btn_leaf"}]
GP_SENT = {"RootPage": {"kind": "activity_suffix", "value": "com.x.RootActivity"},
           "RootPage$GateDlg": {"kind": "resource_id_unique", "value": ["tv_gate"], "hosts": ["RootActivity"]}}
GP_TREE = {"pages": [rec("RootPage", ["根页标题"], ["tv_root"], type="Activity", fq_class="com.x.RootActivity"),
                     rec("WizardPage", ["向导页标题"], ["tv_wizard"], type="Activity",
                         fq_class="com.x.WizardActivity")],
           "fragments": [], "dialogs": []}
WIZ_DUMP = wrap('<node resource-id="com.x:id/tv_wizard" text="向导页标题" bounds="[0,100][900,200]"/>')
ROOT_DUMP = wrap('<node resource-id="com.x:id/tv_root" text="根页标题" bounds="[0,100][900,200]"/>')


def gp_exec(d, dump, activity, monkeypatch, tree=None):
    write_plan(d, [{"walk_id": "w1", "steps": GP_STEPS}], sentinels=GP_SENT)
    write_ledger(d)
    monkeypatch.setattr(we, "choose_gate_control", lambda xml: ((10, 20), "btn_agree", "同意并继续"))
    ex = mk_exec(d, dev=FakeDev([dump], activity=activity))
    ex.tree = GP_TREE if tree is None else tree
    return ex


def test_a4_gate_landing_drift_is_accepted_and_booked(ew, monkeypatch):
    """计划写的落点是 X，实测直连 Y，而 Y 是计划里后续某步的 from → 接受、同步位置、记事实，不熔断。"""
    ex = gp_exec(ew, WIZ_DUMP, "com.x.WizardActivity", monkeypatch)
    ex.do_gate_pass(GP_STEPS[2])                                   # 不抛 = 没熔断
    drift = ex.state["gate_landing_drift"]
    assert drift == [{"step": 3, "gate": "RootPage$GateDlg", "planned": "RootPage",
                      "observed": "WizardPage", "why": drift[0]["why"], "walk_id": "w1",
                      "device_state": "trip_1"}]
    assert ex.state["position"] == "WizardPage"
    assert any(n.startswith("step3: gate_landing_drift: 计划 RootPage → 实测 WizardPage")
               for n in ex.state["notes"])
    assert ex.state["gates"][-1]["via"] == "gate_pass"              # 放行本身照记


def test_a4_landing_not_on_plan_still_escalates(ew, monkeypatch):
    """反例：实测落点不是计划里后续步的 from（树里根本没有它）→ 仍走原熔断，绝不盲收。"""
    ex = gp_exec(ew, wrap('<node resource-id="com.x:id/tv_other" bounds="[0,0][10,10]"/>'),
                 "com.x.OtherActivity", monkeypatch)
    with pytest.raises(SystemExit) as e:
        ex.do_gate_pass(GP_STEPS[2])
    assert e.value.code == 30 and esc_of(ew)["reason"] == "position_mismatch"
    assert "gate_landing_drift" not in ex.state


def test_a4_planned_landing_ok_keeps_old_path(ew, monkeypatch):
    """回归：落点与计划一致时行为不变——不记漂移、不熔断、不多按任何键。"""
    ex = gp_exec(ew, ROOT_DUMP, "com.x.RootActivity", monkeypatch)
    ex.do_gate_pass(GP_STEPS[2])
    assert "gate_landing_drift" not in ex.state and ex.dev.backs == 0
    assert ex.dev.taps == [(10, 20)]                                # 只点了放行控件


# ══ A5 多重边消歧 ═══════════════════════════════════════════════════════════
def dup_tree(second_rid="btn_delete"):
    """同一起点两个控件指向同一目标（共用确认弹窗）——树里是两条 inbound_trigger。"""
    def ib(vid, lab, rid):
        return {"from_page": "HubPage", "trigger_view_id": vid, "trigger_label": lab,
                "runtime": {"status": "confirmed", "control": {"rid": rid}}}
    return {"pages": [rec("HubPage")], "fragments": [],
            "dialogs": [dict(rec("ConfirmDlg"),
                             inbound_triggers=[ib("btn_logout", "退出", "btn_logout"),
                                               ib(second_rid, "注销", second_rid)])]}


DEL_STEP = {"step": 2, "action": "tap", "from": "HubPage", "to": "ConfirmDlg", "trigger": "注销",
            "static_rid": "btn_delete", "safety": "stop_at_dialog"}


def test_a5_runtime_rid_disambiguates_by_plan_fields(ew):
    ex = mk_exec(ew_plan(ew), dev=FakeDev())
    ex.tree = dup_tree()
    # ① 本步 static_rid 对得上第二条候选 → 拿第二条，绝不是兄弟边的第一条
    assert ex._runtime_rid("HubPage", "ConfirmDlg", DEL_STEP) == "btn_delete"
    # ② 只按文案也能对上（计划没给 static_rid 的边）
    assert ex._runtime_rid("HubPage", "ConfirmDlg", {"trigger": "退出"}) == "btn_logout"
    # ③ 候选唯一时老行为一字不变（不需要任何消歧字段）
    ex.tree["dialogs"][0]["inbound_triggers"] = ex.tree["dialogs"][0]["inbound_triggers"][:1]
    assert ex._runtime_rid("HubPage", "ConfirmDlg", None) == "btn_logout"


def test_a5_runtime_rid_returns_none_when_ambiguous(ew):
    """反例：对不上任何候选 / 没有本步信息 → None（退回计划 static_rid），绝不返回兄弟边的 rid。"""
    ex = mk_exec(ew_plan(ew), dev=FakeDev())
    ex.tree = dup_tree()
    assert ex._runtime_rid("HubPage", "ConfirmDlg", {"static_rid": "btn_other", "trigger": "别的"}) is None
    assert ex._runtime_rid("HubPage", "ConfirmDlg", None) is None
    assert ex._runtime_rid("HubPage", "ConfirmDlg", {}) is None


def ew_plan(d):
    write_plan(d, [{"walk_id": "w1", "steps": [{"step": 1, "action": "coldstart", "to": "HubPage"}, DEL_STEP]}],
               sentinels={"HubPage": {"kind": "resource_id_unique", "value": ["tv_hub"], "hosts": []},
                          "ConfirmDlg": {"kind": "resource_id_unique", "value": ["tv_confirm"], "hosts": []}})
    write_ledger(d)
    return d


HUB_DUMP = wrap('<node resource-id="com.x:id/tv_hub" text="枢纽页" bounds="[0,0][900,80]"/>'
                '<node resource-id="com.x:id/btn_logout" text="退出" clickable="true" bounds="[0,100][200,200]"/>'
                '<node resource-id="com.x:id/btn_delete" text="注销" clickable="true" bounds="[0,300][200,400]"/>')
CONFIRM_DUMP = wrap('<node resource-id="com.x:id/tv_confirm" text="确认?" bounds="[0,0][900,300]"/>')


def test_a5_do_tap_hits_own_control_not_sibling(ew):
    """端到端：多重边的第二条边点的必须是**自己的**控件（此前点回兄弟边的控件还记 confirmed）。"""
    ex = mk_exec(ew_plan(ew), dev=FakeDev([HUB_DUMP, CONFIRM_DUMP]))
    ex.tree = dup_tree()
    ex.do_tap(DEL_STEP)
    assert ex.dev.taps == [(100, 350)]                              # btn_delete 的中心，不是 btn_logout
    e = last_edge(ew)
    assert e["status"] == "confirmed" and e["control"]["rid"] == "btn_delete"
    assert "rid_mismatch_with_plan" not in e["control"] and "rid_mismatch" not in (e.get("note") or "")


def test_a5_rid_mismatch_with_plan_is_recorded_not_silent(ew):
    """反哺 rid 与计划 static_rid 指的不是同一个控件时：边真值如实记标志 + note，不静默记 confirmed。"""
    ex = mk_exec(ew_plan(ew), dev=FakeDev([HUB_DUMP, CONFIRM_DUMP]))
    ex.tree = dup_tree(second_rid="btn_logout")                     # 两条候选同 rid → 消歧后仍是它
    ex.do_tap(DEL_STEP)
    e = last_edge(ew)
    assert ex.dev.taps == [(100, 150)]                              # 实际点到的是兄弟控件
    assert e["control"]["rid"] == "btn_logout" and e["control"]["rid_mismatch_with_plan"] is True
    assert "rid_mismatch_with_plan" in e["note"] and "btn_delete" in e["note"]
    assert any("rid_mismatch_with_plan" in n for n in ex.state["notes"])


# ══ A6 结账判据 = 运行时事实 ═════════════════════════════════════════════════
A6_SENT = {"HubPage": {"kind": "resource_id_unique", "value": ["tv_hub"], "hosts": []},
           "ConfirmDlg": {"kind": "resource_id_unique", "value": ["tv_confirm"], "hosts": []},
           "LeafPage": {"kind": "resource_id_unique", "value": ["tv_leaf"], "hosts": []}}
LEAF_DUMP = wrap('<node resource-id="com.x:id/tv_leaf" text="叶子页" bounds="[0,0][900,300]"/>')
A6_TREE = {"pages": [rec("HubPage"), rec("LeafPage")], "fragments": [], "dialogs": [rec("ConfirmDlg")]}


def a6_exec(d, step, dumps, monkeypatch, calls, settled=None, **kw):
    write_plan(d, [{"walk_id": "w1", "steps": [{"step": 1, "action": "coldstart", "to": "HubPage"}, step]}],
               sentinels=A6_SENT)
    write_ledger(d, settled)
    run_stub(monkeypatch, calls)
    kw.setdefault("no_grounding", False)
    kw.setdefault("tree", str(d / "tree.json"))
    (d / "tree.json").write_text(json.dumps({"app": {"launcher_activity": "com.x.Main"}}), encoding="utf-8")
    ex = mk_exec(d, dev=FakeDev(dumps), **kw)
    ex.tree = A6_TREE
    return ex


def test_a6_late_settles_unsettled_dialog_without_sweep(ew, monkeypatch):
    """计划没排结账、但本步真到达且目标未入账 → 用手上的帧补结账；确认窗上**不普查**。"""
    calls = []
    step = {"step": 2, "action": "tap", "from": "HubPage", "to": "ConfirmDlg", "trigger": "注销",
            "static_rid": "btn_delete", "safety": "stop_at_dialog"}
    ex = a6_exec(ew, step, [HUB_DUMP, CONFIRM_DUMP], monkeypatch, calls)
    ex.do_tap(step)
    led = json.load(open(ew / "ledger.json"))["settled"]
    assert led["ConfirmDlg"]["capture"] == "dialog_direct"
    assert ex.state["late_settled"] == [{"node": "ConfirmDlg", "step": 2, "from": "HubPage",
                                         "trigger": "注销", "reason": "arrived_unsettled_target",
                                         "no_sweep": True}]
    assert not any(is_sweep(c) for c in calls)                      # 补结账绝不带普查
    assert last_edge(ew)["status"] == "confirmed"


def test_a6_late_settles_unsettled_page_via_ledger(ew, monkeypatch):
    """非 dialog 目标走正常 settle 内核（同 settles_capture 的那条路），同样不普查。"""
    calls = []
    step = {"step": 2, "action": "tap", "from": "HubPage", "to": "LeafPage", "trigger": "叶子",
            "static_rid": "btn_delete"}
    ex = a6_exec(ew, step, [HUB_DUMP, LEAF_DUMP], monkeypatch, calls)
    ex.do_tap(step)
    settle = [c for c in calls if is_settle(c)]
    assert len(settle) == 1 and argv_val(settle[0], "--node") == "LeafPage"
    assert argv_val(settle[0], "--mode") == "walk"
    assert not any(is_sweep(c) for c in calls)
    assert ex.state["late_settled"][0]["node"] == "LeafPage"


def test_a6_settles_capture_step_behaviour_is_byte_for_byte_unchanged(ew, monkeypatch):
    """回归：带 settles_capture 的步一字不变——照样 settle、照样普查、不记 late_settled。"""
    calls = []
    step = {"step": 2, "action": "tap", "from": "HubPage", "to": "LeafPage", "trigger": "叶子",
            "static_rid": "btn_delete", "settles_capture": "LeafPage"}
    ex = a6_exec(ew, step, [HUB_DUMP, LEAF_DUMP], monkeypatch, calls)
    ex.do_tap(step)
    assert [argv_val(c, "--node") for c in calls if is_settle(c)] == ["LeafPage"]
    assert [argv_val(c, "--node") for c in calls if is_sweep(c)] == ["LeafPage"]   # 普查照跑
    assert "late_settled" not in ex.state


def test_a6_already_settled_target_still_goes_to_variant_path(ew, monkeypatch):
    """反例：目标已入账 → 不补结账，变体逻辑照旧生效（一字不动）。"""
    calls = []
    step = {"step": 2, "action": "tap", "from": "HubPage", "to": "ConfirmDlg", "trigger": "注销",
            "static_rid": "btn_delete"}
    ex = a6_exec(ew, step, [HUB_DUMP, CONFIRM_DUMP], monkeypatch, calls,
                 settled={"ConfirmDlg": {"via": "OtherPage--[退出]-->", "capture": "dialog_direct"}})
    ex.do_tap(step)
    led = json.load(open(ew / "ledger.json"))["settled"]
    assert sorted(k for k in led if "#via=" in k) == ["ConfirmDlg#via=HubPage__btn_delete"]
    assert "late_settled" not in ex.state
    assert last_edge(ew)["variant_baseline"] == "ConfirmDlg#via=HubPage__btn_delete"


def test_a6_auto_edge_late_settles_too(ew, monkeypatch):
    """auto 边（wait 语义，无控件可点）同规则：到达未入账目标即补结账并记账。"""
    calls = []
    step = {"step": 2, "action": "tap", "from": "HubPage", "to": "ConfirmDlg", "trigger": None,
            "auto_transition": True}
    ex = a6_exec(ew, step, [CONFIRM_DUMP], monkeypatch, calls)
    ex.do_tap(step)
    led = json.load(open(ew / "ledger.json"))["settled"]
    assert led["ConfirmDlg"]["capture"] == "dialog_direct"
    assert ex.state["late_settled"][0]["reason"] == "arrived_unsettled_target_auto"
    assert not any(is_sweep(c) for c in calls)


def test_a6_no_settle_grant_falls_back_silently(ew, monkeypatch):
    """反例：settle 收权四参不齐（无 --tree）时非 dialog 目标**不**补结账——
    补结账是运行时新增的结账点，不该让 walk_ledger 的 exit 2 拖死整趟。"""
    calls = []
    step = {"step": 2, "action": "tap", "from": "HubPage", "to": "LeafPage", "trigger": "叶子",
            "static_rid": "btn_delete"}
    ex = a6_exec(ew, step, [HUB_DUMP, LEAF_DUMP], monkeypatch, calls, tree=None)
    ex.do_tap(step)                                                 # 不抛 SystemExit
    assert not any(is_settle(c) for c in calls) and "late_settled" not in ex.state
    assert last_edge(ew)["status"] == "confirmed"
