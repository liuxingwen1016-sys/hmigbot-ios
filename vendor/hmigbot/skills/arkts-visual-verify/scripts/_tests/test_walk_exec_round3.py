"""walk_exec 第三轮通用改进单测（2026-09-10 A~H）

铁律同 test_walk_exec_rules：合成计划 + 合成 dump + FakeDev，**绝不触碰 adb / 模拟器**；
node_sweep 子进程一律 monkeypatch（另一代理正在实现 --chain-mode/--only-rids/--exclude-*，
本文件只按契约断言「命令怎么发、产物怎么消费」）。断言里不出现任何真实 app 的页名/控件名。
"""
import json, os, sys, types
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import walk_exec as we  # noqa: E402
from test_walk_exec_rules import (FakeDev, ew, mk_exec, wrap, write_plan,      # noqa: F401,F811,E402
                                  write_ledger, esc_of, last_edge,
                                  _reset_ui_words, _no_sleep)


# ── 公共夹具 ────────────────────────────────────────────────────────────────
def fake_proc(rc=0, out=""):
    return types.SimpleNamespace(returncode=rc, stdout=out, stderr="")


def sweep_stub(monkeypatch, calls, manifest=None, man_path=None, rc=0, stdout=""):
    """替掉 node_sweep 子进程：记下 argv，并（可选）把 manifest 落到契约路径。"""
    def _run(cmd, **kw):
        calls.append(list(cmd))
        if manifest is not None and man_path:
            os.makedirs(os.path.dirname(man_path), exist_ok=True)
            json.dump(manifest, open(man_path, "w"), ensure_ascii=False)
        return fake_proc(rc, stdout)
    monkeypatch.setattr(we.subprocess, "run", _run)
    return calls


def argv_val(argv, flag):
    return argv[argv.index(flag) + 1] if flag in argv else None


# ── A 首启链页当场普查 ───────────────────────────────────────────────────────
CHAIN_SENTINELS = {"C1": {"kind": "resource_id_unique", "value": ["tv_c1"], "hosts": []},
                   "C2": {"kind": "resource_id_unique", "value": ["tv_c2"], "hosts": []},
                   "C3": {"kind": "resource_id_unique", "value": ["tv_c3"], "hosts": []},
                   "C4": {"kind": "resource_id_unique", "value": ["tv_c4"], "hosts": []}}


def chain_plan(d, chain_protected=True):
    """一次性首启链：C1→C2→C3→C4→X，每步各结一个账。普查在 C2 上跑。"""
    steps = [{"step": 1, "action": "coldstart", "to": "C1"},
             {"step": 2, "action": "tap", "from": "C1", "to": "C2", "trigger": "下一步",
              "static_rid": "btn_next1", "settles_capture": "C2"},
             {"step": 3, "action": "tap", "from": "C2", "to": "C3", "trigger": "下一步",
              "static_rid": "btn_next2", "settles_capture": "C3"},
             {"step": 4, "action": "tap", "from": "C3", "to": "C4", "trigger": "开始",
              "static_rid": "btn_go", "settles_capture": "C4"},
             {"step": 5, "action": "tap", "from": "C4", "to": "X", "trigger": "入口",
              "static_rid": "btn_x"}]
    write_plan(d, [{"walk_id": "w1", "chain_protected": chain_protected, "steps": steps}],
               sentinels=CHAIN_SENTINELS)
    write_ledger(d)
    return steps


def chain_exec(d, at="C2", **kw):
    """普查跑完后设备仍在 at（普查自己会回位）——dump 给对应哨兵 id，免得收尾的判位误熔断。"""
    kw.setdefault("no_blackbox", False)
    kw.setdefault("blackbox_out", str(d / "bb"))
    return mk_exec(d, dev=FakeDev([wrap(f'<node resource-id="com.x:id/tv_{at.lower()}" bounds="[0,0][100,50]"/>')]), **kw)


def test_a_chain_sweep_sends_chain_mode_and_exclusions(ew, monkeypatch):
    """链页不再整趟跳过普查：带 --chain-mode + 排除集（树的 wizard_exit_controls ∪ 本节点出边 static_rid）。"""
    steps = chain_plan(ew)
    calls = sweep_stub(monkeypatch, [], manifest={"discoveries": []},
                       man_path=str(ew / "bb" / "C2" / "C2__manifest.json"))
    ex = chain_exec(ew)
    ex.tree = {"pages": [{"id": "C2", "wizard_exit_controls": [{"view_id": "com.x:id/btn_skip"},
                                                              {"view_id": "btn_next2"}]}],
               "fragments": [], "dialogs": []}
    ex._maybe_sweep("C2", steps[1])
    argv = calls[0]
    assert "--chain-mode" in argv and "--allow-chain-sweep" not in argv
    assert sorted(argv_val(argv, "--exclude-rids").split(",")) == ["btn_next2", "btn_skip"]
    _texts = argv_val(argv, "--exclude-texts").split(",")
    assert "下一步" in _texts and "Skip" in _texts and "同意并继续" in _texts
    assert ex.state["chain_swept"][0]["node"] == "C2"
    assert ex.state.get("sweep_skipped_chain") is None       # 旧的「整趟欠账交收尾链趟」已取消
    assert ex.state["sweep_ran"][-1]["chain_mode"] is True


def test_a_exclude_texts_follow_ui_words_override(ew, monkeypatch):
    steps = chain_plan(ew)
    (ew / "ui_words.json").write_text(json.dumps({"wizard_advance_texts": ["Proceed"]}), encoding="utf-8")
    calls = sweep_stub(monkeypatch, [], manifest={"discoveries": []},
                       man_path=str(ew / "bb" / "C2" / "C2__manifest.json"))
    chain_exec(ew)._maybe_sweep("C2", steps[1])
    assert argv_val(calls[0], "--exclude-texts") == "Proceed"   # 词表跨项目可整表覆盖，逻辑零业务常量


def test_a_chain_advanced_syncs_position_and_books_debts(ew, monkeypatch):
    """普查把链推进到 C4：中间步记 skipped(chain_advanced_by_sweep)、未结账目标进 capture_debt、
    unswept 进 sweep_debt，position/_jump_to 同步到落点，不熔断。"""
    steps = chain_plan(ew)
    man = {"chain_advanced": True,
           "advanced_to": {"activity": "com.x.ChainActivity", "landing_node": "C4"},
           "unswept": [{"rid": "btn_more", "text": "更多", "center": [10, 20]}],
           "discoveries": []}
    sweep_stub(monkeypatch, [], manifest=man, man_path=str(ew / "bb" / "C2" / "C2__manifest.json"))
    ex = chain_exec(ew)
    assert ex._maybe_sweep("C2", steps[1]) == "chain_advanced"
    assert ex._jump_to == 4 and ex.state["position"] == "C4"       # 计划里第一个 from==C4 的步
    assert ex.state["skipped"] == [3, 4]
    # capture_debt 的形态必须是**页 id 列表**：plan_chain_sweep.chain_debt 直接 set() 它排收尾趟
    assert ex.state["capture_debt"] == ["C3", "C4"] and set(ex.state["capture_debt"])
    assert ex.state["chain_advances"][0]["reason"] == "chain_advanced_by_sweep"
    assert ex.state["sweep_debt"]["C2"][0]["rid"] == "btn_more"
    adv = ex.state["chain_advances"][0]
    assert adv["landing_node"] == "C4" and adv["skipped_steps"] == [3, 4] and adv["resume_at_step"] == 5


def test_a_chain_advanced_settled_target_not_double_booked(ew, monkeypatch):
    steps = chain_plan(ew)
    write_ledger(ew, {"C3": {"via": "早前"}})
    man = {"chain_advanced": True, "advanced_to": {"landing_node": "C4"}, "discoveries": []}
    sweep_stub(monkeypatch, [], manifest=man, man_path=str(ew / "bb" / "C2" / "C2__manifest.json"))
    ex = chain_exec(ew)
    ex._maybe_sweep("C2", steps[1])
    assert ex.state["capture_debt"] == ["C4"]                           # 已结账的不欠


def test_a_chain_advanced_unresolved_falls_back_to_meltdown(ew, monkeypatch):
    """落点解析不出（manifest 没给、树也判不出）→ 走原熔断，且熔断包带 options 菜单。"""
    steps = chain_plan(ew)
    man = {"chain_advanced": True, "advanced_to": {}, "discoveries": []}
    sweep_stub(monkeypatch, [], manifest=man, man_path=str(ew / "bb" / "C2" / "C2__manifest.json"))
    with pytest.raises(SystemExit) as e:
        chain_exec(ew)._maybe_sweep("C2", steps[1])
    assert e.value.code == 30
    esc = esc_of(ew)
    assert esc["reason"] == "chain_advanced_unresolved" and esc["options"]


def test_a_non_chain_walk_keeps_plain_sweep(ew, monkeypatch):
    steps = chain_plan(ew, chain_protected=False)
    calls = sweep_stub(monkeypatch, [], manifest={"discoveries": []},
                       man_path=str(ew / "bb" / "C2" / "C2__manifest.json"))
    chain_exec(ew)._maybe_sweep("C2", steps[1])
    assert "--chain-mode" not in calls[0] and "--exclude-rids" not in calls[0]


# ── B 普查发现当场入账 ───────────────────────────────────────────────────────
def disc_plan(d, settled=None):
    steps = [{"step": 1, "action": "coldstart", "to": "P"},
             {"step": 2, "action": "tap", "from": "P", "to": "Z", "trigger": "入口", "static_rid": "btn_z"}]
    write_plan(d, [{"walk_id": "w1", "steps": steps}],
               sentinels={"P": {"kind": "resource_id_unique", "value": ["tv_p"], "hosts": []},
                          "Q": {"kind": "resource_id_unique", "value": ["tv_q"], "hosts": []},
                          "Host$Dlg": {"kind": "resource_id_unique", "value": ["tv_dlg"], "hosts": []}})
    write_ledger(d, settled)
    return steps


P_XML = wrap('<node resource-id="com.x:id/tv_p" bounds="[0,0][100,50]"/>')
Q_XML = wrap('<node resource-id="com.x:id/tv_q" bounds="[0,0][100,50]"/>')
DISC_TREE = {"pages": [{"id": "P"}, {"id": "Q"}], "fragments": [], "dialogs": [{"id": "Host$Dlg"}]}


def test_b_dialog_discovery_settles_from_sweep_evidence(ew):
    """dialog 类发现：零设备动作，用普查自己的截图/dump 直接结账 + 补一条 discovered 边。"""
    steps = disc_plan(ew)
    man = {"discoveries": [{"idx": 1, "landing_node": "Host$Dlg", "trigger_text": "更多",
                            "trigger_resource_id": "com.x:id/btn_more", "trigger_center": [30, 40],
                            "landing_ability": "com.x.HomeActivity",
                            "screenshot": "bb/P/shot.png", "dump": "bb/P/shot.android.xml"}]}
    ex = mk_exec(ew, dev=FakeDev([P_XML]), no_blackbox=False, blackbox_out=str(ew / "bb"))
    ex.tree = DISC_TREE
    ex._ingest_discoveries("P", steps[1], man)
    rec = json.load(open(ew / "ledger.json"))["settled"]["Host$Dlg"]
    assert rec["capture"] == "dialog_direct" and rec["capture_meta"]["screenshot"] == "bb/P/shot.png"
    edge = last_edge(ew)
    assert edge["from"] == "P" and edge["to"] == "Host$Dlg"
    assert edge["status"] == "confirmed" and edge["discovered"] is True
    assert edge["control"]["matched_by"] == "sweep_discovery" and edge["control"]["center"] == [30, 40]
    assert ex.dev.taps == []                                   # dialog 类不碰设备


def test_b_page_discovery_reenters_settles_and_returns(ew, monkeypatch):
    """activity/fragment 类发现：按 trigger_center 重点进入 → settle → 回起点。"""
    steps = disc_plan(ew)
    man = {"discoveries": [{"idx": 1, "landing_node": "Q", "trigger_text": "入口",
                            "trigger_resource_id": "com.x:id/btn_q2", "trigger_center": [55, 66]}]}
    seen = []
    monkeypatch.setattr(we.Exec, "_ledger", lambda self, *a: seen.append(list(a)))
    ex = mk_exec(ew, dev=FakeDev([Q_XML, P_XML]), no_blackbox=False, blackbox_out=str(ew / "bb"))
    ex.tree = DISC_TREE
    ex._ingest_discoveries("P", steps[1], man)
    assert ex.dev.taps == [(55, 66)]
    assert seen and seen[0][:4] == ["settle", "--node", "Q", "--via"]
    edge = last_edge(ew)
    assert (edge["to"], edge["discovered"], edge["status"]) == ("Q", True, "confirmed")
    assert ex.state["discoveries_settled"] == ["Q"]


def test_b_skips_settled_offtree_and_respects_no_blackbox(ew, monkeypatch):
    steps = disc_plan(ew, settled={"Q": {"via": "行走"}})
    man = {"discoveries": [{"idx": 1, "landing_node": "Q", "trigger_center": [55, 66]},
                           {"idx": 2, "landing_node": "NotInTree", "trigger_center": [1, 2]},
                           {"idx": 3, "landing_node": "P", "trigger_center": [3, 4]}]}
    monkeypatch.setattr(we.Exec, "_ledger", lambda self, *a: pytest.fail("已结账/树外/自身 不该再结账"))
    ex = mk_exec(ew, dev=FakeDev([P_XML]), no_blackbox=False, blackbox_out=str(ew / "bb"))
    ex.tree = DISC_TREE
    ex._ingest_discoveries("P", steps[1], man)
    assert ex.dev.taps == [] and not os.path.exists(ew / "edge_results.json")
    ex2 = mk_exec(ew, dev=FakeDev([P_XML]), no_blackbox=True)        # --no-blackbox 一律不做
    ex2.tree = DISC_TREE
    ex2._ingest_discoveries("P", steps[1], {"discoveries": [{"landing_node": "Host$Dlg",
                                                             "screenshot": "x.png"}]})
    assert "Host$Dlg" not in json.load(open(ew / "ledger.json"))["settled"]


def test_b_reentry_capped(ew, monkeypatch):
    steps = disc_plan(ew)
    man = {"discoveries": [{"idx": i, "landing_node": "Q", "trigger_center": [i, i]} for i in range(1, 7)]}
    monkeypatch.setattr(we.Exec, "_ledger", lambda self, *a: None)
    ex = mk_exec(ew, dev=FakeDev([P_XML]), no_blackbox=False, blackbox_out=str(ew / "bb"))
    ex.tree = DISC_TREE                                      # 到达判不到 → 每次都只花一次 tap
    ex._ingest_discoveries("P", steps[1], man)
    assert len(ex.dev.taps) == we.DISCOVERY_REENTRY_MAX       # 入账不许退化成第二次遍历


# ── C 边失败当场补点 ─────────────────────────────────────────────────────────
def repair_plan(d):
    steps = [{"step": 1, "action": "coldstart", "to": "P"},
             {"step": 2, "action": "tap", "from": "P", "to": "Q", "trigger": "入口",
              "static_rid": "btn_q", "suspect": ["stale_edge"]},
             {"step": 3, "action": "back", "from": "Q", "to": "P"},
             {"step": 4, "action": "note", "from": "P", "to": "P"}]
    write_plan(d, [{"walk_id": "w1", "steps": steps}],
               sentinels={"P": {"kind": "resource_id_unique", "value": ["tv_p"], "hosts": []},
                          "Q": {"kind": "resource_id_unique", "value": ["tv_q"], "hosts": []}})
    write_ledger(d)
    return steps


def write_run_meta(d, node, checks):
    g = d / "grounding" / node
    g.mkdir(parents=True, exist_ok=True)
    (g / "run_meta.json").write_text(json.dumps({"node": node, "checks": checks}, ensure_ascii=False),
                                     encoding="utf-8")


def test_c_same_destination_check_repaired_on_edge_failure(ew, monkeypatch):
    """suspect 快路记 not_reproduced 后，起点那条 deferred_same_destination 的 check 失去继承源 → 当场 --only-rids 补点。"""
    steps = repair_plan(ew)
    write_run_meta(ew, "P", [{"idx": 3, "name": "chk", "status": "deferred_same_destination",
                              "anchor_rid": "com.x:id/btn_q"},
                             {"idx": 4, "name": "other", "status": "ok", "rid": "btn_zzz"}])
    calls = sweep_stub(monkeypatch, [])
    other = wrap('<node resource-id="com.x:id/tv_p" bounds="[0,0][20,10]"/>'
                 '<node resource-id="com.x:id/btn_other" text="别的" clickable="true" bounds="[0,0][20,10]"/>')
    ex = mk_exec(ew, dev=FakeDev([other]), no_grounding=False)
    ex.do_tap(steps[1])                                       # 控件不在 → suspect 快路
    assert last_edge(ew)["status"] == "not_reproduced"
    argv = calls[0]
    assert argv_val(argv, "--only-rids") == "btn_q" and "--chain-mode" not in argv
    assert argv_val(argv, "--node") == "P"
    rep = ex.state["same_dest_repairs"][0]
    assert rep["node"] == "P" and rep["check_idx"] == [3] and rep["why"].startswith("suspect_fastpath:")
    assert any("失去继承源" in n for n in ex.state["notes"])


def test_c_repair_uses_rid_field_and_skips_when_anchor_differs(ew, monkeypatch):
    steps = repair_plan(ew)
    write_run_meta(ew, "P", [{"idx": 3, "status": "deferred_same_destination", "rid": "btn_q"}])
    calls = sweep_stub(monkeypatch, [])
    assert mk_exec(ew, dev=FakeDev([P_XML]), no_grounding=False)._repair_same_dest_check(steps[1], "t") is True
    assert argv_val(calls[0], "--only-rids") == "btn_q"        # run_meta 只有 rid 字段时同样认

    write_run_meta(ew, "P", [{"idx": 9, "status": "deferred_same_destination", "rid": "btn_elsewhere"}])
    calls2 = sweep_stub(monkeypatch, [])
    assert mk_exec(ew, dev=FakeDev([P_XML]), no_grounding=False)._repair_same_dest_check(steps[1], "t") is False
    assert calls2 == []


def test_c_no_repair_without_deferred_check_or_grounding(ew, monkeypatch):
    steps = repair_plan(ew)
    write_run_meta(ew, "P", [{"idx": 3, "status": "ok", "rid": "btn_q"}])
    calls = sweep_stub(monkeypatch, [])
    assert mk_exec(ew, dev=FakeDev([P_XML]), no_grounding=False)._repair_same_dest_check(steps[1], "t") is False
    write_run_meta(ew, "P", [{"idx": 3, "status": "deferred_same_destination", "rid": "btn_q"}])
    assert mk_exec(ew, dev=FakeDev([P_XML]), no_grounding=True)._repair_same_dest_check(steps[1], "t") is False
    assert calls == []


def test_c_landing_recover_paths_also_repair(ew, monkeypatch):
    """no_effect / landed_elsewhere 两条机械收边路径同样触发补点。"""
    steps = repair_plan(ew)
    write_run_meta(ew, "P", [{"idx": 3, "status": "deferred_same_destination", "rid": "btn_q"}])
    calls = sweep_stub(monkeypatch, [])
    ex = mk_exec(ew, dev=FakeDev([P_XML]), no_grounding=False)
    ex.tree = {"pages": [{"id": "P", "fq_class": "com.x.HomeActivity",
                          "layout_facts": {"discriminators": {"view_ids": ["tv_p"]}}}],
               "fragments": [], "dialogs": []}
    assert ex._arrival_landing_recover(steps[1], P_XML, "com.x.HomeActivity", "rid:btn_q", "?",
                                       (1, 2), "btn_q", "btn_q", "入口") is True
    assert last_edge(ew)["note"].startswith("no_effect")
    assert argv_val(calls[0], "--only-rids") == "btn_q"


# ── D 熔断菜单 ──────────────────────────────────────────────────────────────
SMALL_STEPS = [{"step": 1, "action": "coldstart", "to": "P"},
               {"step": 2, "action": "tap", "from": "P", "to": "Q", "trigger": "入口", "static_rid": "btn_q"},
               {"step": 3, "action": "back", "from": "Q", "to": "P"},
               {"step": 4, "action": "note", "from": "P", "to": "P"}]
BIG_STEPS = [{"step": 1, "action": "coldstart", "to": "P"},
             {"step": 2, "action": "tap", "from": "P", "to": "Q", "trigger": "入口", "static_rid": "btn_q"},
             {"step": 3, "action": "tap", "from": "Q", "to": "R", "trigger": "r"},
             {"step": 4, "action": "tap", "from": "R", "to": "S", "trigger": "s"},
             {"step": 5, "action": "back", "from": "S", "to": "R"},
             {"step": 6, "action": "back", "from": "R", "to": "Q"},
             {"step": 7, "action": "tap", "from": "Q", "to": "T", "trigger": "t"},
             {"step": 8, "action": "back", "from": "T", "to": "Q"},
             {"step": 9, "action": "back", "from": "Q", "to": "P"},
             {"step": 10, "action": "note", "from": "P", "to": "P"}]


def mk_diag(land="Z", strong=True):
    return {"activity": "com.x.HomeActivity", "screen": [1080, 1920],
            "landing_node": land, "landing_why": "fragment 判别物命中 2 条",
            "landing_sentinel": {"node": land, "ok": bool(strong), "weak": not strong},
            "expected_sentinel": {"node": "Q", "ok": False, "weak": False},
            "open_dialogs": [], "control": {"rid": "btn_q", "in_dump": False, "in_clickables": False},
            "cancel_control": None, "clickables_top": [],
            "target_settled": False, "sole_settle_step": False}


def opts_for(d, steps, reason, diag, idx=1):
    write_plan(d, [{"walk_id": "w1", "steps": steps}])
    write_ledger(d)
    ex = mk_exec(d, dev=FakeDev())
    return ex._options(steps[idx], reason, diag, {})


def test_d1_skip_options_state_subtree_cost(ew):
    opts = opts_for(ew, SMALL_STEPS, "arrival_unverified", mk_diag())
    skips = [o for o in opts if o["key"].startswith("skip")]
    assert skips and all("共 2 步" in o["effect"] for o in skips)     # tap + 配对的 back
    assert all("共" not in o["effect"] for o in opts if not o["key"].startswith("skip"))
    assert opts[0]["key"].startswith("skip")                          # 小子树时推荐位不变（旧行为）


def test_d2_big_subtree_demotes_skip_and_recommends_mark_done(ew):
    opts = opts_for(ew, BIG_STEPS, "arrival_unverified", mk_diag(land="Z", strong=True))
    assert opts[0]["key"] == "mark_done_assume"
    assert "--mark-step-done" in opts[0]["cmd"] and "--assume-at" in opts[0]["cmd"] and "Z" in opts[0]["cmd"]
    assert "未直接观测" in opts[0]["effect"] and "transient/landed_elsewhere" in opts[0]["effect"]
    assert "共 8 步" in [o for o in opts if o["key"].startswith("skip")][0]["effect"]
    assert all(o["key"].startswith("skip") for o in opts[-2:])        # skip 类整体退到末尾


def test_d2_big_subtree_without_strong_landing_recommends_resume(ew):
    opts = opts_for(ew, BIG_STEPS, "arrival_unverified", mk_diag(land="Z", strong=False))
    assert opts[0]["key"] == "resume_assume" and "--resume" in opts[0]["cmd"]
    assert "--assume-at" in opts[0]["cmd"] and "Z" in opts[0]["cmd"]
    assert "--mark-step-done" not in opts[0]["cmd"]
    assert not opts[0]["coverage_loss"]


def test_d3_manual_mark_done_assumes_measured_landing(ew):
    opts = opts_for(ew, SMALL_STEPS, "input_target_not_found", mk_diag(land="Z", strong=True))
    o = next(o for o in opts if o["key"] == "manual_then_mark_done")
    assert "--assume-at Z" in o["cmd"] and "--assume-at Q" not in o["cmd"]
    # 落点不强命中时退回计划 to（老行为）
    o2 = next(o for o in opts_for(ew, SMALL_STEPS, "input_failed", mk_diag(land=None, strong=False))
              if o["key"] == "manual_then_mark_done")
    assert "--assume-at Q" in o2["cmd"]


# ── E 熔断预算按代理算 ───────────────────────────────────────────────────────
def test_e_escalation_budget_counts_current_agent_only(ew):
    write_plan(ew, [{"walk_id": "w1", "steps": SMALL_STEPS}])
    write_ledger(ew)
    (ew / ".driver_in_flight.json").write_text(json.dumps({"ts": 1000.0}), encoding="utf-8")
    ex = mk_exec(ew, dev=FakeDev([P_XML]), max_escalations=2)
    ex.state["escalations"] = 7                                  # 上一个代理留下的整趟累计
    ex.state["llm_gaps"] = [{"escalated_at": 10.0}, {"escalated_at": 900.0},   # 锁之前 = 别人的
                            {"escalated_at": 1500.0}]                          # 本代理的 1 次
    assert ex._escalations_scope() == 1
    with pytest.raises(SystemExit):
        ex.escalate(SMALL_STEPS[1], "control_not_found")
    esc = esc_of(ew)
    assert esc["escalations_so_far"] == 2 and esc["escalations_scope"] == "agent"
    assert esc["handoff_due"] is True and esc["escalations_walk_total"] == 8


def test_e_without_inflight_lock_keeps_walk_cumulative(ew):
    write_plan(ew, [{"walk_id": "w1", "steps": SMALL_STEPS}])
    write_ledger(ew)
    ex = mk_exec(ew, dev=FakeDev([P_XML]), max_escalations=5)
    ex.state["escalations"] = 4
    assert ex._escalations_scope() == 4
    with pytest.raises(SystemExit):
        ex.escalate(SMALL_STEPS[1], "control_not_found")
    esc = esc_of(ew)
    assert esc["escalations_scope"] == "walk" and esc["escalations_so_far"] == 5 and esc["handoff_due"] is True


# ── F 裸重跑保护 / --restart ─────────────────────────────────────────────────
def stale_state(d, walk="w1", **kw):
    st = {"walk_id": walk, "next_step": 2, "position": "P", "escalations": 1,
          "done_steps": [1, 2], "skipped": [7, 8]}
    st.update(kw)
    (d / "walk_exec_state.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


def test_f_refuses_bare_rerun_with_existing_state(ew, capsys):
    write_plan(ew, [{"walk_id": "w1", "steps": SMALL_STEPS}])
    write_ledger(ew)
    stale_state(ew)
    with pytest.raises(SystemExit) as e:
        mk_exec(ew, dev=FakeDev([P_XML])).run()
    assert e.value.code == 5
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["status"] == "refused" and out["reason"] == "state_exists_without_resume"
    assert "--resume" in out["hint"] and "--restart" in out["hint"]
    assert json.load(open(ew / "walk_exec_state.json"))["done_steps"] == [1, 2]   # 状态原封不动


def test_f_resume_and_fresh_and_other_walk_pass(ew):
    write_plan(ew, [{"walk_id": "w1", "steps": SMALL_STEPS},
                    {"walk_id": "w2", "steps": [{"step": 1, "action": "note", "to": "P"}]}])
    write_ledger(ew)
    stale_state(ew)
    mk_exec(ew, dev=FakeDev([P_XML]), resume=True)._refuse_bare_rerun()      # 续走放行
    stale_state(ew)
    mk_exec(ew, dev=FakeDev([P_XML]), walk="w2")._refuse_bare_rerun()        # 另一个 walk 不受约束
    stale_state(ew, done_steps=[], escalations=0)
    mk_exec(ew, dev=FakeDev([P_XML]))._refuse_bare_rerun()                   # 空状态=没跑过，放行


def test_f_restart_archives_and_zeroes_skipped(ew):
    write_plan(ew, [{"walk_id": "w1", "steps": [{"step": 1, "action": "note", "to": "P"}]}])
    write_ledger(ew)
    stale_state(ew)
    ex = mk_exec(ew, dev=FakeDev([P_XML]), restart=True)
    assert ex.state["skipped"] == [] and ex.state["done_steps"] == [] and ex.state["escalations"] == 0
    assert any(f.name.startswith("walk_exec_state.w1.restart.") for f in ew.iterdir())
    assert any("--restart" in n for n in ex.state["notes"])
    ex.run()
    st = json.load(open(ew / "walk_exec_state.json"))
    assert st["status"] == "walk_done" and st["skipped"] == [] and st["done_steps"] == [1]


# ── G 逃逸自愈不再 IndexError ────────────────────────────────────────────────
def test_g_escaped_app_selfheal_does_not_raise(ew, monkeypatch):
    """0910 实爆：记录追加在 sweep_ran 却按 blackbox_ran 下标索引 → 自愈第一行就 IndexError。"""
    steps = chain_plan(ew, chain_protected=False)
    sweep_stub(monkeypatch, [])
    dev = FakeDev([wrap('<node resource-id="com.x:id/tv_c1" bounds="[0,0][100,50]"/>')],
                  activity="com.x.HomeActivity", pkg="com.other.picker")
    ex = mk_exec(ew, dev=dev, no_grounding=False, no_blackbox=True)
    ex._maybe_sweep("C1", steps[0])                       # C1 是 root → 重拉起即回位，不熔断
    assert ex.state["sweep_ran"][-1]["escaped_app"] is True
    assert "blackbox_ran" not in ex.state                 # 不再有第二本对不上的账


def test_g_escaped_deep_node_still_melts_down(ew, monkeypatch):
    steps = chain_plan(ew, chain_protected=False)
    sweep_stub(monkeypatch, [])
    dev = FakeDev([wrap("<node/>")], activity="com.x.HomeActivity", pkg="com.other.picker")
    ex = mk_exec(ew, dev=dev, no_grounding=False, no_blackbox=True)
    with pytest.raises(SystemExit) as e:
        ex._maybe_sweep("C2", steps[1])                   # 深层节点重放失败 → 仍交还 LLM
    assert e.value.code == 30 and esc_of(ew)["reason"] == "blackbox_escaped_app"


# ── H type 步的子状态前置 ────────────────────────────────────────────────────
SUBTAB = ('<node resource-id="com.x:id/tab_group" bounds="[0,0][400,80]">'
          '<node resource-id="com.x:id/tab_a" text="A" selected="true" clickable="true" bounds="[0,0][200,80]"/>'
          '<node resource-id="com.x:id/tab_b" text="B" selected="false" clickable="true" bounds="[200,0][400,80]"/>'
          '</node>')


def test_h_find_subtab_candidates_needs_selected_sibling():
    assert we.find_subtab_candidates(wrap(SUBTAB)) == [((300, 40), "tab_b")]
    lone = wrap('<node resource-id="com.x:id/x" selected="false" clickable="true" bounds="[0,0][10,10]"/>')
    assert we.find_subtab_candidates(lone) == []              # 没有 selected=true 兄弟 → 不是 tab 组
    assert we.find_subtab_candidates("{ not xml") == []


def test_h_do_type_switches_subtab_then_types(ew):
    step = {"step": 1, "action": "type", "from": "P", "to": "P",
            "view_id": "com.x:id/et_field", "text": "hello world"}
    write_plan(ew, [{"walk_id": "w1", "steps": [step]}])
    field = '<node resource-id="com.x:id/et_field" text="%s" clickable="false" bounds="[0,100][400,200]"/>'
    dev = FakeDev([wrap(SUBTAB), wrap(SUBTAB + field % ""), wrap(field % "hello world")])
    ex = mk_exec(ew, dev=dev)
    ex.do_type(step)
    assert dev.taps == [(300, 40), (200, 150)]                # 先切子 tab，再点输入框
    assert "input text hello%sworld" in dev.shell_log
    assert any("input_target_found_after_subtab_switch" in n for n in ex.state["notes"])


def test_h_still_escalates_when_no_subtab_helps(ew):
    step = {"step": 1, "action": "type", "from": "P", "to": "P", "view_id": "et_field"}
    write_plan(ew, [{"walk_id": "w1", "steps": [step]}])
    dev = FakeDev([wrap(SUBTAB)])                             # 切了也找不到 → 仍熔断交人
    with pytest.raises(SystemExit) as e:
        mk_exec(ew, dev=dev).do_type(step)
    assert e.value.code == 30 and esc_of(ew)["reason"] == "input_target_not_found"
    assert dev.taps == [(300, 40)] and "切子 tab" in esc_of(ew)["detail"]
