import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import lib_landing as ll
import plan_orphan_probe as pop
import materialize_blackbox_to_factree as mz


def _tree():
    return {"app": {"launcher_short": "Splash"},
            "pages": [{"id": "HomeActivity", "type": "Activity", "fq_class": "x.HomeActivity", "android_file": "a/HomeActivity.kt",
                       "layout_facts": {"discriminators": {"texts": ["我的"], "view_ids": ["ll_bottom_tab"]}}, "inbound_triggers": [], "navigation": {"inbound": [], "outbound": []}},
                      {"id": "OrphanActivity", "type": "Activity", "fq_class": "x.OrphanActivity", "android_file": "a/OrphanActivity.kt",
                       "walkability": {"status": "walkable", "facts": {"instantiation_examples": ["a/MineFragment.kt:88"]}},
                       "layout_facts": {"discriminators": {"texts": ["孤儿页标题"], "view_ids": ["tv_orphan"]}}, "inbound_triggers": [], "navigation": {"inbound": [], "outbound": []}},
                      {"id": "DeadActivity", "type": "Activity", "android_file": "a/Dead.kt", "walkability": {"status": "dead"}, "inbound_triggers": []}],
            "fragments": [{"id": "MineFragment", "type": "Fragment", "parent_in_nav": "HomeActivity", "android_file": "a/MineFragment.kt",
                           "layout_facts": {"discriminators": {"texts": ["账号管理"], "view_ids": ["tv_account_manage"]}}, "inbound_triggers": [], "navigation": {"inbound": [], "outbound": []}},
                          {"id": "WorksFragment", "type": "Fragment", "parent_in_nav": "HomeActivity", "android_file": "a/WorksFragment.kt",
                           "layout_facts": {"discriminators": {"texts": ["我的作品"], "view_ids": ["rv_works"]}}, "inbound_triggers": [], "navigation": {"inbound": [], "outbound": []}}],
            "dialogs": [{"id": "VipDialog", "type": "Dialog", "inbound_triggers": [{"from_page": "HomeActivity", "trigger_kind": "auto"}],
                         "layout_facts": {"discriminators": {"texts": ["账号绑定提醒"], "view_ids": ["tv_bind_now"]}}, "navigation": {"inbound": [], "outbound": []}}]}


def test_landing_vote_levels_and_tie():
    t = _tree()
    dump_mine = '<node resource-id="x:id/ll_bottom_tab"/><node resource-id="x:id/tv_account_manage" text="账号管理"/>'
    assert ll.resolve_landing_node(t, "x.HomeActivity", dump_mine)[0] == "MineFragment"          # 子页判别物命中 → 子页胜宿主
    dump_dlg = dump_mine + '<node resource-id="x:id/tv_bind_now" text="账号绑定提醒"/>'
    assert ll.resolve_landing_node(t, "x.HomeActivity", dump_dlg)[0] == "VipDialog"              # 弹窗层优先
    dump_tie = '<node resource-id="x:id/tv_account_manage"/><node resource-id="x:id/rv_works"/>'
    nid, info = ll.resolve_landing_node(t, "HomeActivity", dump_tie)
    assert nid is None and "平票" in info["why"]                                                   # 同层平票 → 歧义宁缺
    assert ll.resolve_landing_node(t, "x.HomeActivity", '<node resource-id="x:id/ll_bottom_tab"/>')[0] == "HomeActivity"  # 无子页命中 → Activity 本身
    assert ll.resolve_landing_node(t, "x.OrphanActivity", '<node text="孤儿页标题"/>')[0] == "OrphanActivity"
    assert ll.resolve_landing_node(t, "x.Unknown", "")[0] is None


def test_materialize_attaches_to_known_node_idempotent():
    t = _tree(); summ = {}
    d = {"trigger_resource_id": "x:id/rl_orphan_entry", "trigger_text": "孤儿入口", "landing_ability": "x.OrphanActivity", "landing_signature": "sig1"}
    assert mz.attach_to_known_node(t, "MineFragment", "OrphanActivity", d, summ)
    node = [r for r in t["pages"] if r["id"] == "OrphanActivity"][0]
    e = node["inbound_triggers"][0]
    assert e["from_page"] == "MineFragment" and e["trigger_view_id"] == "rl_orphan_entry" and e["trigger_kind"] == "tap" and e["runtime"]["status"] == "confirmed"
    assert mz.attach_to_known_node(t, "MineFragment", "OrphanActivity", d, summ) and len(node["inbound_triggers"]) == 1   # 幂等
    assert summ["attached_to_known_node"] == 1 and summ["attached_existing_edge_confirmed"] == 1
    assert not mz.attach_to_known_node(t, "MineFragment", "NoSuchNode", d, summ)


def test_orphan_recompute_and_candidates():
    t = _tree(); plan = {"targets": ["HomeActivity", "OrphanActivity", "DeadActivity", "MineFragment", "WorksFragment", "VipDialog"], "main_root": "HomeActivity", "walks": []}
    ledger = {"settled": {"HomeActivity": {}, "MineFragment": {}}}
    orph = pop.remaining_orphans(t, plan, ledger)
    assert orph == ["OrphanActivity", "WorksFragment"]            # dead 不算；settled 不算；VipDialog 有活入边不算
    w3 = pop.build_walk3(t, plan, orph)
    cands = {c["node"]: c for c in w3["steps"][1]["candidates"]}
    assert cands["OrphanActivity"]["candidates"] == [{"page": "MineFragment", "evidence": "a/MineFragment.kt:88"}]
    assert cands["WorksFragment"]["candidates"] == [] and cands["OrphanActivity"]["discriminators"]["texts"] == ["孤儿页标题"]
    assert w3["steps"][1]["action"] == "probe" and w3["dynamic"] is True
    # 普查挂回真节点后再算 → 孤儿消失
    mz.attach_to_known_node(t, "MineFragment", "OrphanActivity", {"trigger_resource_id": "x:id/r"}, {})
    assert "OrphanActivity" not in pop.remaining_orphans(t, plan, ledger)


# ══ B2 孤儿探测：黑盒噪音变体不排走（2026-09-10）════════════════════════════════
import subprocess                                                          # noqa: E402
import plan_chain_sweep as pcs                                             # noqa: E402

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _variant_tree():
    t = _tree()
    # 运行时黑盒变体：materialize 挂不回真节点时留下的壳——无入边、无源码引用、无判别物
    t["pages"].append({"id": "Unknown#via=列表项_1", "type": "Activity", "inbound_triggers": [],
                       "navigation": {"inbound": [], "outbound": []}})
    return t


def test_noise_orphan_predicate_needs_both_marks():
    t = _variant_tree()
    recs = t["pages"] + t["fragments"] + t["dialogs"]
    fidx = pop.build_file_index(recs)
    assert pop.is_noise_orphan(t, "Unknown#via=列表项_1", fidx)
    assert not pop.is_noise_orphan(t, "WorksFragment", fidx)          # 真节点零候选 → 照探（不是噪音）
    # 变体但**有**机械候选入口页 → 不是噪音，照排
    t["pages"].append({"id": "Hosted#via=卡片", "type": "Activity", "inbound_triggers": [],
                       "walkability": {"status": "walkable",
                                       "facts": {"instantiation_examples": ["a/MineFragment.kt:12"]}}})
    fidx2 = pop.build_file_index(t["pages"] + t["fragments"] + t["dialogs"])
    assert not pop.is_noise_orphan(t, "Hosted#via=卡片", fidx2)


def _run_orphan(tmp_path, tree, plan, settled=("HomeActivity", "MineFragment")):
    (tmp_path / "tree.json").write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "walk_plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "ledger.json").write_text(json.dumps({"settled": {n: {} for n in settled}}), encoding="utf-8")
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "plan_orphan_probe.py"),
                        "--tree", str(tmp_path / "tree.json"), "--dir", str(tmp_path)],
                       capture_output=True, text=True)
    return p, json.loads((tmp_path / "walk_plan.json").read_text())


def test_noise_orphan_not_planned_but_recorded(tmp_path):
    t = _variant_tree()
    plan = {"targets": ["HomeActivity", "OrphanActivity", "MineFragment", "Unknown#via=列表项_1"],
            "main_root": "HomeActivity", "walks": []}
    p, out = _run_orphan(tmp_path, t, plan)
    assert p.returncode == 0, p.stderr
    assert out["orphans"] == ["OrphanActivity"]                       # 噪音变体不再算进孤儿名单
    noise = out["orphan_probe"]["skipped_noise"]
    assert [x["node"] for x in noise] == ["Unknown#via=列表项_1"] and noise[0]["why"]
    w3 = next(w for w in out["walks"] if w["walk_id"] == "walk_3_orphan_probe")
    assert [c["node"] for c in w3["steps"][1]["candidates"]] == ["OrphanActivity"]


def test_all_orphans_noise_means_no_walk_at_all(tmp_path):
    """0910 实爆：为一个零候选的变体单排一趟 walk，白烧 6 分钟 + 一次冷启。"""
    plan = {"targets": ["HomeActivity", "MineFragment", "Unknown#via=列表项_1"],
            "main_root": "HomeActivity", "walks": []}
    p, out = _run_orphan(tmp_path, _variant_tree(), plan)
    assert out["orphans"] == [] and not [w for w in out["walks"] if w["walk_id"] == "walk_3_orphan_probe"]
    assert out["orphan_probe"]["n"] == 0 and len(out["orphan_probe"]["skipped_noise"]) == 1


# ══ B3 收尾链趟合并成一趟（2026-09-10）══════════════════════════════════════════
def _walk0():
    return {"walk_id": "walk_0_first_launch", "root": "RootPage", "trip_id": "trip_1_logged_out",
            "steps": [
                {"step": 1, "action": "coldstart", "to": "RootPage", "settles_capture": "RootPage"},
                {"step": 2, "action": "tap", "from": "RootPage", "to": "GateDialog", "gate": True,
                 "settles_capture": "GateDialog", "subtree_end_step": 3},
                {"step": 3, "action": "gate_pass", "from": "GateDialog", "to": "RootPage", "gate": True},
                {"step": 4, "action": "type", "from": "RootPage", "to": "RootPage", "view_id": "input_box"},
                {"step": 5, "action": "tap", "from": "RootPage", "to": "StepOnePage", "kind": "wizard_step",
                 "settles_capture": "StepOnePage", "static_rid": "btn_next"},
                {"step": 6, "action": "tap", "from": "StepOnePage", "to": "StepTwoPage",
                 "kind": "wizard_step", "settles_capture": "StepTwoPage"},
                {"step": 7, "action": "skip", "from": "StepTwoPage", "to": "SomePage", "kind": "scope_exit"},
                {"step": 8, "action": "tap", "from": "StepTwoPage", "to": "HubPage", "settles_capture": "HubPage"},
                {"step": 9, "action": "tap", "from": "HubPage", "to": "LeafPage", "settles_capture": "LeafPage",
                 "subtree_end_step": 10},
                {"step": 10, "action": "back", "to": "HubPage"},
                {"step": 11, "action": "tap", "from": "HubPage", "to": "TailPage", "settles_capture": "TailPage"}]}


def _sweep_dir(tmp_path, states, run_meta=(), walks=None):
    (tmp_path / "walk_plan.json").write_text(
        json.dumps({"walks": (walks if walks is not None else []) + [_walk0()]}, ensure_ascii=False),
        encoding="utf-8")
    for i, st in enumerate(states):
        (tmp_path / f"walk_exec_state.w{i}.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    for n in run_meta:
        d = tmp_path / "grounding" / n
        d.mkdir(parents=True, exist_ok=True)
        (d / "run_meta.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tree.json").write_text("{}", encoding="utf-8")
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "plan_chain_sweep.py"),
                        "--tree", str(tmp_path / "tree.json"), "--dir", str(tmp_path)],
                       capture_output=True, text=True)
    return p, json.loads((tmp_path / "walk_plan.json").read_text())


def test_chain_sweep_merges_into_one_trip_with_full_prefix(tmp_path):
    states = [{"sweep_skipped_chain": ["StepOnePage", "StepTwoPage"]},
              {"sweep_debt": {"LeafPage": ["btn_x", "btn_y"]}, "capture_debt": ["HubPage"]},
              {"sweep_skipped_chain": ["GhostPage"]}]                  # walk_0 里没有到达步 → 够不到
    p, plan = _sweep_dir(tmp_path, states, run_meta=("StepOnePage",))
    assert p.returncode == 0, p.stderr
    chain = [w for w in plan["walks"] if str(w["walk_id"]).startswith("walk_6_chain_sweep")]
    assert len(chain) == 1 and chain[0]["walk_id"] == "walk_6_chain_sweep"   # 一趟，不是一页一趟
    w = chain[0]
    assert (w["reset_before"], w["chain_protected"], w["dynamic"], w["order_exempt"]) == ("pm_clear", True, True, True)
    assert w["root"] == "RootPage" and w["trip_id"] == "trip_1_logged_out"
    seq = [(s["step"], s["action"], s.get("to")) for s in w["steps"]]
    assert seq == [(1, "coldstart", "RootPage"), (2, "tap", "GateDialog"),
                   (3, "gate_pass", "RootPage"),          # ★0910 实爆：旧实现漏抄 → 每趟必熔断
                   (4, "type", "RootPage"),               # ★输入守卫步同样必须抄
                   (5, "tap", "StepOnePage"), (6, "tap", "StepTwoPage"), (7, "sweep", "StepTwoPage"),
                   (8, "tap", "HubPage"), (9, "sweep", "HubPage"),
                   (10, "tap", "LeafPage"), (11, "sweep", "LeafPage")]
    # 审计注记步（skip）不抄；最后一个欠账页之后的步（back/TailPage）不抄
    assert w["chain_nodes"] == ["StepTwoPage", "HubPage", "LeafPage"]        # 顺序按 walk_0 步序
    # 采集欠账页恢复 settles_capture，其余只途经
    assert w["capture_restored"] == ["HubPage"]
    assert [s.get("settles_capture") for s in w["steps"] if s["action"] == "tap"] == [None, None, None, "HubPage", None]
    assert all(s.get("settles_grounding") == [] for s in w["steps"] if s["action"] == "tap")
    assert w["steps"][4]["static_rid"] == "btn_next"      # 执行器普查排除集要用本页出边 rid → 必须原样带上
    assert all("subtree_end_step" not in s for s in w["steps"])
    cs = plan["chain_sweep"]
    assert cs["mode"] == "after_finalize_single_trip" and cs["unreached"] == ["GhostPage"]
    assert cs["swept_in_walk"] == ["StepTwoPage", "HubPage", "LeafPage"] and cs["walks"] == ["walk_6_chain_sweep"]
    assert "StepOnePage" not in cs["remaining"]           # 已有 run_meta（别的趟扫过）→ 不欠账
    assert cs["sources"]["sweep_debt"] == {"LeafPage": ["btn_x", "btn_y"]}


def test_chain_sweep_keeps_cancelled_walks_and_reruns_are_idempotent(tmp_path):
    cancelled = {"walk_id": "walk_6_chain_sweep_StepTwoPage", "cancelled": {"reason": "用户带债收工"},
                 "steps": []}
    states = [{"sweep_skipped_chain": ["StepTwoPage"], "capture_debt": ["HubPage"]}]
    p, plan = _sweep_dir(tmp_path, states, walks=[cancelled])
    assert p.returncode == 0, p.stderr
    ids = [w["walk_id"] for w in plan["walks"]]
    assert "walk_6_chain_sweep_StepTwoPage" in ids                      # 带 cancelled 的原样保留
    w = next(w for w in plan["walks"] if w["walk_id"] == "walk_6_chain_sweep")
    assert w["chain_nodes"] == ["HubPage"]                              # 其节点不再重排
    # 再跑一次（finalize 会反复调）→ 链趟不叠加
    (tmp_path / "tree.json").write_text("{}", encoding="utf-8")
    subprocess.run([sys.executable, os.path.join(SCRIPTS, "plan_chain_sweep.py"),
                    "--tree", str(tmp_path / "tree.json"), "--dir", str(tmp_path)],
                   capture_output=True, text=True)
    plan2 = json.loads((tmp_path / "walk_plan.json").read_text())
    assert [w["walk_id"] for w in plan2["walks"]].count("walk_6_chain_sweep") == 1
    assert len([w for w in plan2["walks"] if str(w["walk_id"]).startswith("walk_6_chain_sweep")]) == 2


def test_chain_sweep_no_debt_plans_nothing(tmp_path):
    p, plan = _sweep_dir(tmp_path, [{"sweep_skipped_chain": []}])
    assert not [w for w in plan["walks"] if str(w["walk_id"]).startswith("walk_6_chain_sweep")]
    assert plan["chain_sweep"]["remaining"] == [] and plan["chain_sweep"]["walks"] == []


def test_chain_prefix_actions_cover_every_position_changing_step():
    """前缀白名单必须盖住所有会改变/校验位置的步——漏一类就是 0910 的 gate_pass 事故重演。"""
    assert set(pcs.ARRIVAL_ACTIONS) <= set(pcs.PREFIX_ACTIONS)
    for a in ("coldstart", "tap", "gate_pass", "type", "back", "back_inpage", "renav", "verify"):
        assert a in pcs.PREFIX_ACTIONS
    for a in ("skip", "note", "sweep", "probe", "await"):
        assert a not in pcs.PREFIX_ACTIONS
