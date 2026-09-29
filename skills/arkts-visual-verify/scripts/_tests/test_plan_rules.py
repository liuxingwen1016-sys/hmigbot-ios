"""计划器通用规则 A1~A8（2026-09-09，0909 安卓真走 12 次「归计划器」的熔断修复）。

夹具全部是**合成小树/合成边**：字段形状照契约写，页名一律 Root/Hub/Alpha/Gate 这类占位名——
本套规则必须换项目通用，测试里出现任何真实应用的页名/控件 id/文案都是规则被写死的信号。
"""
import json, os, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import plan_edge_walk as pw          # noqa: E402
import phase2_scope as ps            # noqa: E402

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


# ══ A1 哨兵消费 LLM 的 verify_signal ═══════════════════════════════════════════
def _rec(rid, typ="Dialog", kind=None, vs=None, inbound=()):
    return {"id": rid, "type": typ, "label": rid,
            "navigation_contract": {"relationship_kind": kind, "verify_signal": vs},
            "inbound_triggers": [{"from_page": f} for f in inbound]}


def _sent(rec, by_id=None, **kw):
    by_id = by_id or {rec["id"]: rec}
    return pw.derive_sentinel(rec, None, {}, {}, by_id, {}, {}, **kw)


def test_verify_signal_shape_filter():
    assert pw._verify_signal_of({"navigation_contract": {"verify_signal": {"text_contains": "abc"}}}) == {"text_contains": "abc"}
    assert pw._verify_signal_of({"navigation_contract": {"verify_signal": {"ordinal_in_wizard": 2}}}) == {"ordinal_in_wizard": 2}
    assert pw._verify_signal_of({"navigation_contract": {"verify_signal": None}}) is None
    assert pw._verify_signal_of({"navigation_contract": {"verify_signal": "some text"}}) is None      # 非 dict 脏值
    assert pw._verify_signal_of({"navigation_contract": {"verify_signal": {"unknown_key": 1}}}) is None
    assert pw._verify_signal_of({"navigation_contract": {"verify_signal": {"view_id": ""}}}) is None  # 空值不算证据


def test_a1_text_contains_makes_label_sentinel_strong():
    s = _sent(_rec("GateDialog", vs={"text_contains": "AGREE-TOKEN"}))
    assert s["kind"] == "label_text"
    assert s["verify_signal"] == {"text_contains": "AGREE-TOKEN"}
    assert s["weak"] is False and "verify_signal 判强" in s["note"]


def test_a1_view_id_makes_label_sentinel_strong():
    s = _sent(_rec("PanelDialog", vs={"view_id": "panel_root"}))
    assert s["verify_signal"] == {"view_id": "panel_root"}
    assert s["weak"] is False


def test_a1_ordinal_only_strong_for_wizard_step():
    wiz = _sent(_rec("StepTwoFragment", typ="Fragment", kind="wizard_step", vs={"ordinal_in_wizard": 2}))
    assert wiz["verify_signal"] == {"ordinal_in_wizard": 2}
    assert wiz["weak"] is False and "向导序号判强" in wiz["note"]
    # 同样的序号信号，非向导页 → 序号没有语义 → 仍弱
    other = _sent(_rec("PanelDialog", kind="dialog_trigger", vs={"ordinal_in_wizard": 2}))
    assert other["weak"] is True


def test_a1_no_signal_stays_weak_and_activity_still_copies_signal():
    assert _sent(_rec("PanelDialog"))["weak"] is True
    act = _sent(_rec("SomeActivity", typ="Activity", vs={"text_contains": "T"}))
    assert act["kind"] == "activity_suffix" and act["verify_signal"] == {"text_contains": "T"}
    assert "weak" not in act                       # Activity 哨兵本来就强，不因本规则新增 weak 键


def _shared_layout_fixture(tmp_path, host_a, host_b):
    """两个 fragment 共享同一组 id（谁都没有全局唯一 id → resource_id_shared），宿主由参数决定。"""
    ldir = tmp_path / "res" / "layout"
    ldir.mkdir(parents=True)
    for name in ("fragment_alpha.xml", "fragment_beta.xml"):
        (ldir / name).write_text('<L><V android:id="@+id/shared_one"/><V android:id="@+id/shared_two"/></L>')
    layout_idx = {p.name: str(p) for p in ldir.iterdir()}
    eff_ids = {n: {"shared_one", "shared_two"} for n in layout_idx}
    id_freq = {"shared_one": 2, "shared_two": 2}
    recs = [_rec("AlphaFragment", typ="Fragment", inbound=(host_a,)),
            _rec("BetaFragment", typ="Fragment", inbound=(host_b,)),
            _rec(host_a, typ="Activity"), _rec(host_b, typ="Activity")]
    by_id = {r["id"]: r for r in recs}
    holders = pw.build_holder_index(recs, by_id, str(tmp_path), layout_idx, {}, eff_ids)
    return recs, by_id, layout_idx, eff_ids, id_freq, holders


def test_a1_shared_id_strong_when_holders_have_disjoint_hosts(tmp_path):
    recs, by_id, layout_idx, eff_ids, id_freq, holders = _shared_layout_fixture(
        tmp_path, "HostOneActivity", "HostTwoActivity")
    assert sorted(holders["shared_one"]) == ["AlphaFragment", "BetaFragment"]
    s = pw.derive_sentinel(by_id["AlphaFragment"], str(tmp_path), layout_idx, {}, by_id,
                           eff_ids, id_freq, holders=holders)
    assert s["kind"] == "resource_id_shared"
    assert s["weak"] is False and "宿主可分判强" in s["note"]
    # 不给持有者索引 → 拿不到持有者 → 保持弱（本条判据不猜）
    s2 = pw.derive_sentinel(by_id["AlphaFragment"], str(tmp_path), layout_idx, {}, by_id,
                            eff_ids, id_freq)
    assert s2["weak"] is True


def test_a1_shared_id_stays_weak_when_holders_share_one_host(tmp_path):
    recs, by_id, layout_idx, eff_ids, id_freq, holders = _shared_layout_fixture(
        tmp_path, "HostOneActivity", "HostOneActivity")
    s = pw.derive_sentinel(by_id["AlphaFragment"], str(tmp_path), layout_idx, {}, by_id,
                           eff_ids, id_freq, holders=holders)
    assert s["kind"] == "resource_id_shared" and s["weak"] is True


# ══ A2 首启门边 ════════════════════════════════════════════════════════════════
def _gate_edge(**kw):
    e = {"trigger_kind": "auto", "edge_preconditions": [{"kind": "first_launch_onboarding"}]}
    e.update(kw); return e


def test_a2_gate_edge_predicate():
    assert pw.is_first_launch_gate(_gate_edge())
    assert pw.is_first_launch_gate(_gate_edge(edge_preconditions=[{"kind": "first_launch"}]))
    assert not pw.is_first_launch_gate(_gate_edge(trigger_kind="tap"))          # 有控件可点 = 不是门
    assert not pw.is_first_launch_gate(_gate_edge(edge_preconditions=[{"kind": "login_required"}]))
    assert not pw.is_first_launch_gate({"trigger_kind": "auto"})                # 光是自动跳转不算门
    assert not pw.is_first_launch_gate(None)


def test_a2_transient_target_predicate():
    by_id = {"ModalPage": {"navigation_contract": {"relationship_kind": "lifecycle_modal"}},
             "PlainPage": {"navigation_contract": {"relationship_kind": "activity_jump"}}}
    assert pw.is_transient_gate_target("SomeDialog", {"SomeDialog"}, by_id)
    assert pw.is_transient_gate_target("ModalPage", set(), by_id)
    assert not pw.is_transient_gate_target("PlainPage", set(), by_id)


def _edge(frm, to, kind="push", label="go", **kw):
    return {"from": frm, "to": to, "label": label, "kind": kind, "safety": "normal",
            "needs_discovery": False, "settles_grounding": [], "evidence_line": None, **kw}


def test_a2_walk0_emits_gate_then_gate_pass_before_siblings():
    edges = [_edge("RootPage", "GateDialog", kind="dialog", label=None,
                   gate=True, gate_transient=True, auto_transition=True, wait_hint="until_text:X"),
             _edge("RootPage", "NextPage")]
    w = pw.plan_walk("RootPage", edges, "w0", "r", consume_gates=True)
    acts = [(s["action"], s.get("to")) for s in w["steps"]]
    assert acts[:4] == [("coldstart", "RootPage"), ("tap", "GateDialog"),
                        ("gate_pass", "RootPage"), ("tap", "NextPage")]
    g = w["steps"][1]
    assert g["gate"] is True and g["auto_transition"] is True and g["trigger_kind"] == "auto"
    assert g["settles_capture"] == "GateDialog" and g["wait_hint"] == "until_text:X"
    assert "GateDialog" in w["settles"]


def test_a2_gate_target_settles_even_out_of_scope():
    """门是一次性资源，只有这趟见得到 → 不在本趟 scope 也要结账。"""
    edges = [_edge("RootPage", "GateDialog", kind="dialog", label=None, gate=True, gate_transient=True),
             _edge("RootPage", "NextPage")]
    w = pw.plan_walk("RootPage", edges, "w0", "r", scope={"RootPage", "NextPage"}, consume_gates=True)
    assert w["steps"][1]["to"] == "GateDialog" and w["steps"][1]["settles_capture"] == "GateDialog"
    assert "GateDialog" in w["settles"]


def test_a2_other_walks_skip_consumed_gate_but_keep_page_jumps():
    edges = [_edge("RootPage", "GateDialog", kind="dialog", label=None, gate=True, gate_transient=True),
             _edge("RootPage", "HubPage", gate=True)]      # 非瞬态门（真页面跳转）：每次冷启都发生
    w = pw.plan_walk("RootPage", edges, "w1", "r", consume_gates=False)
    by_to = {s["to"]: s for s in w["steps"] if s.get("to") != "RootPage"}
    assert by_to["GateDialog"]["action"] == "skip"
    assert by_to["GateDialog"]["skip_reason"] == "first_launch_gate_consumed"
    assert by_to["HubPage"]["action"] == "tap"            # 掐掉它整趟行走就没有入口了
    assert "GateDialog" not in w["settles"]


def test_a2_scope_dialog_capturable_without_label():
    """phase2_scope：无文案但机械可触发的 dialog 必须进采集集（否则计划器根本看不见门）。"""
    for kind in ("auto", "list_item", "span", "async_after_tap"):
        d = {"inbound_triggers": [{"from_page": "HostPage", "trigger_kind": kind}]}
        assert ps.dialog_trigger(d) == ("HostPage", f"<{kind}>")
    # 无 kind 但有控件 id → 可采
    assert ps.dialog_trigger({"inbound_triggers": [{"from_page": "HostPage",
                                                    "trigger_view_id": "pkg.R.id.btn_open"}]}) == ("HostPage", "<view_id>")
    # 文案可用 → 原行为不变
    assert ps.dialog_trigger({"inbound_triggers": [{"from_page": "HostPage",
                                                    "trigger_label": "开启"}]}) == ("HostPage", "开启")
    # 三条都不满足 → 仍不可采（脏 rid 不算控件）
    assert ps.dialog_trigger({"inbound_triggers": [{"from_page": "HostPage", "trigger_view_id": "null"}]}) is None
    assert ps.dialog_trigger({"inbound_triggers": [{"trigger_kind": "auto"}]}) is None      # 无 from_page
    assert ps.dialog_trigger({"inbound_triggers": []}) is None


# ══ A3 尾部回栈剪枝 ════════════════════════════════════════════════════════════
def _w(*steps):
    return {"walk_id": "w", "steps": [dict(step=i, **s) for i, s in enumerate(steps, 1)]}


def test_a3_prunes_trailing_returns_and_renumbers_subtree_end():
    w = _w({"action": "coldstart", "to": "RootPage"},
           {"action": "tap", "from": "RootPage", "to": "APage", "settles_capture": "APage",
            "subtree_end_step": 5},
           {"action": "tap", "from": "APage", "to": "BPage", "settles_capture": "BPage"},
           {"action": "back", "to": "APage"},
           {"action": "back", "to": "RootPage"})
    pw.prune_tail(w, launcher="RootPage")
    assert [s["action"] for s in w["steps"]] == ["coldstart", "tap", "tap"]
    assert [s["step"] for s in w["steps"]] == [1, 2, 3]
    assert w["steps"][1]["subtree_end_step"] == 3          # 原 5 → 存活步里 ≤5 的最大者
    assert len(w["pruned_tail_steps"]) == 2


def test_a3_prunes_back_to_finished_launcher_before_annotation_steps():
    w = _w({"action": "coldstart", "to": "RootPage"},
           {"action": "tap", "from": "RootPage", "to": "APage", "settles_capture": "APage"},
           {"action": "back", "to": "RootPage"},
           {"action": "skip", "from": "RootPage", "to": "CPage", "kind": "scope_exit"})
    pw.prune_tail(w, launcher="RootPage")
    assert [s["action"] for s in w["steps"]] == ["coldstart", "tap", "skip"]
    assert w["pruned_tail_steps"][0]["action"] == "back"   # skip 是注记不是依赖 → back 仍是空转


def test_a3_keeps_back_that_is_still_needed_and_never_prunes_settling_steps():
    w = _w({"action": "coldstart", "to": "RootPage"},
           {"action": "tap", "from": "RootPage", "to": "APage", "settles_capture": "APage"},
           {"action": "back", "to": "RootPage"},
           {"action": "tap", "from": "RootPage", "to": "BPage", "settles_capture": "BPage"},
           {"action": "verify", "from": "BPage", "to": "CPage", "kind": "embed",
            "settles_capture": "CPage"})
    before = json.dumps(w["steps"], sort_keys=True)
    pw.prune_tail(w, launcher="RootPage")
    assert json.dumps(w["steps"], sort_keys=True) == before and "pruned_tail_steps" not in w


# ══ A4 输入守卫 ════════════════════════════════════════════════════════════════
def test_a4_input_guard_from_contract():
    e = {"edge_preconditions": [{"kind": "state_required",
                                 "input": {"view_id": "input_box", "text_hint": "hello world"}}]}
    assert pw.derive_input_guard(e, {}) == {"view_id": "input_box", "text": "hello world",
                                            "source": "contract"}
    e2 = {"edge_preconditions": [{"kind": "state_required",
                                  "input": {"view_id": "input_box", "text_hint": "非 ASCII 提示"}}]}
    assert pw.derive_input_guard(e2, {})["text"] is None          # 非 ASCII → 交执行器用中性默认串
    e3 = {"edge_preconditions": [{"kind": "state_required", "input": {"view_id": "input_box"}}]}
    assert pw.derive_input_guard(e3, {})["text"] is None


def test_a4_mechanical_fallback_needs_verbatim_id_in_evidence():
    frm = {"layout_facts": {"edit_ids": ["input_box", "other_box"]}}
    e = {"edge_preconditions": [{"kind": "state_required",
                                 "evidence": "src/Foo.kt:10 — 空则直接返回，须先在 input_box 填内容"}]}
    assert pw.derive_input_guard(e, frm) == {"view_id": "input_box", "text": None,
                                             "source": "evidence_id_match"}
    # 证据里没有逐字出现任何 edit id → 不猜、不出步
    e2 = {"edge_preconditions": [{"kind": "state_required", "data_hint": "需要先填点什么"}]}
    assert pw.derive_input_guard(e2, frm) is None
    assert pw.derive_input_guard(e, {}) is None                   # 树无 layout_facts.edit_ids → 保持现状
    assert pw.derive_input_guard({"edge_preconditions": [{"kind": "login_required"}]}, frm) is None


def test_a4_type_step_precedes_tap():
    edges = [_edge("RootPage", "APage", label="go",
                   input_guard={"view_id": "input_box", "text": "abc", "source": "contract"}),
             _edge("RootPage", "BPage", label="go2",
                   input_guard={"view_id": "search_box", "text": None, "source": "evidence_id_match"})]
    w = pw.plan_walk("RootPage", edges, "w", "r")
    seq = [(s["action"], s.get("to"), s.get("view_id")) for s in w["steps"]]
    assert ("type", "RootPage", "input_box") in seq
    i_type = next(i for i, s in enumerate(w["steps"]) if s.get("view_id") == "input_box")
    assert w["steps"][i_type + 1]["action"] == "tap" and w["steps"][i_type + 1]["to"] == "APage"
    t = w["steps"][i_type]
    assert t["text"] == "abc" and t["precondition_kind"] == "state_required"
    assert "input_source" not in t                                # 契约来源不标注
    t2 = next(s for s in w["steps"] if s.get("view_id") == "search_box")
    assert t2["text"] is None and t2["input_source"] == "evidence_id_match"


# ══ A5 生成目标遍历全部调用方 ══════════════════════════════════════════════════
def test_a5_path_walk_honours_final_edge():
    edges = [_edge("RootPage", "HubPage"), _edge("HubPage", "OutPage", kind="generation"),
             _edge("RootPage", "SidePage"), _edge("SidePage", "OutPage", kind="generation")]
    via_side = pw.plan_path_walk("RootPage", edges, "OutPage", "w_side", "r", already=set(),
                                 final_edge=edges[3])
    hops = [(s.get("from"), s.get("to")) for s in via_side["steps"] if s["action"] == "tap"]
    assert hops == [("RootPage", "SidePage"), ("SidePage", "OutPage")]
    via_hub = pw.plan_path_walk("RootPage", edges, "OutPage", "w_hub", "r", already=set(),
                                final_edge=edges[1])
    assert [(s.get("from"), s.get("to")) for s in via_hub["steps"] if s["action"] == "tap"] \
        == [("RootPage", "HubPage"), ("HubPage", "OutPage")]
    # 起点即调用方 → 只有那一跳
    only = pw.plan_path_walk("HubPage", edges, "OutPage", "w", "r", already=set(), final_edge=edges[1])
    assert [(s.get("from"), s.get("to")) for s in only["steps"] if s["action"] == "tap"] \
        == [("HubPage", "OutPage")]


# ══ A6 guard_flags → suspect ══════════════════════════════════════════════════
def test_a6_suspect_copied_into_step_and_sorted_last():
    edges = [_edge("RootPage", "SuspectPage", suspect=["shape_mismatch"]),
             _edge("RootPage", "CleanPage")]
    w = pw.plan_walk("RootPage", edges, "w", "r")
    taps = [s for s in w["steps"] if s["action"] == "tap"]
    assert [t["to"] for t in taps] == ["CleanPage", "SuspectPage"]      # 可疑边排兄弟之后
    assert taps[1]["suspect"] == ["shape_mismatch"]
    assert "suspect" not in taps[0]


def test_a6_sort_key_order():
    gate = {"kind": "push", "to": "Z", "gate": True}
    clean = {"kind": "push", "to": "A"}
    suspect = {"kind": "push", "to": "A", "suspect": ["x"]}
    assert pw._edge_sort_key(gate) < pw._edge_sort_key(clean)
    assert pw._edge_sort_key(clean) < pw._edge_sort_key(suspect)


# ══ A7 / A8 端到端（合成树 + 合成分派表）════════════════════════════════════════
def _synthetic_project(tmp_path, extra_assignment_pages=()):
    spec = tmp_path / "spec"
    (spec / "visual-verify").mkdir(parents=True)
    def page(pid, kind, inbound=(), vs=None):
        return {"id": pid, "type": "Activity", "label": pid,
                "navigation_contract": {"relationship_kind": kind, "verify_signal": vs},
                "inbound_triggers": list(inbound)}
    tree = {"app": {"launcher_activity": "com.example.app.RootActivity"}, "source": {},
            "pages": [
                page("RootActivity", "launcher_entry", vs={"text_contains": "ROOT"}),
                page("HubActivity", "activity_root",
                     [{"from_page": "RootActivity", "trigger_label": "enter", "trigger_kind": "tap",
                       "trigger_view_id": "btn_enter"}], vs={"view_id": "hub_root"}),
                page("AlphaActivity", "activity_jump",
                     [{"from_page": "HubActivity", "trigger_label": "alpha", "trigger_kind": "tap",
                       "trigger_view_id": "btn_alpha"}], vs={"text_contains": "ALPHA"}),
                page("OutputActivity", "activity_jump",
                     [{"from_page": "HubActivity", "trigger_label": "make", "trigger_kind": "tap",
                       "trigger_view_id": "btn_make"},
                      {"from_page": "AlphaActivity", "trigger_label": "make too", "trigger_kind": "tap",
                       "trigger_view_id": "btn_make2"}], vs={"text_contains": "OUT"})],
            "fragments": [],
            "dialogs": [{"id": "GateDialog", "type": "Dialog", "label": "GateDialog",
                         "navigation_contract": {"relationship_kind": "lifecycle_modal",
                                                 "verify_signal": {"text_contains": "AGREE"}},
                         "inbound_triggers": [{"from_page": "RootActivity", "trigger_kind": "auto",
                                               "wait_hint": "until_text:AGREE",
                                               "edge_preconditions": [{"kind": "first_launch_onboarding",
                                                                       "evidence": "src/Root.kt:1"}]}]}]}
    tp = spec / "toolkit-fact-tree.json"
    tp.write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    pages = {p: {"trips": ["trip_1_logged_out", "trip_2_logged_in_vip"], "reason": "test"}
             for p in ("RootActivity", "HubActivity", "AlphaActivity", "OutputActivity", "GateDialog")}
    for p in extra_assignment_pages:
        pages[p] = {"trips": ["trip_1_logged_out"], "reason": "test"}
    (spec / "visual-verify" / "_trip_assignment.json").write_text(
        json.dumps({"pages": pages, "totals": {}}, ensure_ascii=False), encoding="utf-8")
    return tp


def _run_plan(tree_path, out, *extra):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, "plan_edge_walk.py"),
                           "--tree", str(tree_path), "--out", str(out),
                           "--generation-targets", "OutputActivity", *extra],
                          capture_output=True, text=True)


def test_a5_a2_end_to_end_walk_ids_and_gate_steps(tmp_path):
    tp = _synthetic_project(tmp_path)
    r = _run_plan(tp, tmp_path / "out")
    assert r.returncode == 0, r.stderr
    plan = json.loads((tmp_path / "out" / "walk_plan.json").read_text())
    ids = [w["walk_id"] for w in plan["walks"]]
    # A5：两个调用方 → 两条生成走，各带 stop_if_settled
    assert "walk_2_generation_OutputActivity_via_HubActivity" in ids
    assert "walk_2_generation_OutputActivity_via_AlphaActivity" in ids
    for w in plan["walks"]:
        if w["walk_id"].startswith("walk_2_"):
            assert w["stop_if_settled"] == "OutputActivity"
    # A2：门边进 walk_0，且 walk_1 里被判已消费
    w0 = next(w for w in plan["walks"] if w["walk_id"] == "walk_0_first_launch")
    assert [s["action"] for s in w0["steps"][:3]] == ["coldstart", "tap", "gate_pass"]
    assert w0["steps"][1]["to"] == "GateDialog" and w0["steps"][1]["gate"] is True
    w1 = next(w for w in plan["walks"] if w["walk_id"] == "walk_1_main")
    assert all(s.get("skip_reason") == "first_launch_gate_consumed"
               for s in w1["steps"] if s.get("to") == "GateDialog")
    # A1：合成树里每页都给了 verify_signal → 哨兵表原样带上
    assert plan["sentinels"]["GateDialog"]["verify_signal"] == {"text_contains": "AGREE"}


def test_a7_stale_assignment_gate(tmp_path):
    tp = _synthetic_project(tmp_path, extra_assignment_pages=("PageFromAnotherTree",))
    r = _run_plan(tp, tmp_path / "out")
    assert r.returncode == 3 and "PageFromAnotherTree" in r.stderr
    r2 = _run_plan(tp, tmp_path / "out2", "--allow-stale-assignment")
    assert r2.returncode == 0 and "仅告警" in r2.stderr
    # #via= 黑盒变体豁免：它是运行时发现的虚拟节点，树上可以没有
    tp2 = _synthetic_project(tmp_path / "p2", extra_assignment_pages=("HubActivity#via=item_1",))
    assert _run_plan(tp2, tmp_path / "out3").returncode == 0


def test_a8_trip_assign_meta(tmp_path):
    tp = _synthetic_project(tmp_path)
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "trip_assign.py"), str(tp),
                        "--project-root", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    asg = json.loads((tmp_path / "spec" / "visual-verify" / "_trip_assignment.json").read_text())
    meta = asg["meta"]
    assert meta["source_tree"] == os.path.abspath(str(tp))
    assert meta["tree_records"] == 5                      # 4 pages + 0 fragments + 1 dialog
    assert isinstance(meta["prefix_whitelist_hits"], list)
    assert "靠名字兜底" in r.stdout
    assert asg["pages"] and asg["totals"]                 # 原有结构不变


# ══ B1 BACK 落点消费 → renav（2026-09-10）══════════════════════════════════════
def _bl(**kw):
    b = {"node": "HostPage", "n": 2, "matched_n": 0, "matches_parent": False,
         "confirm_dialog": None, "expects": "HubPage", "walk_id": "w0"}
    b.update(kw); return b


def test_b1_renav_reason_predicate():
    assert pw.renav_reason(_bl()) == "back_landing_mismatch"
    assert pw.renav_reason(_bl(confirm_dialog="ExitConfirmDialog")) == "back_needs_confirm"
    # 确认窗优先报：它是机制层面的原因，落点不符只是表象
    assert pw.renav_reason(_bl(matches_parent=True, confirm_dialog="ExitConfirmDialog")) == "back_needs_confirm"
    assert pw.renav_reason(_bl(matches_parent=True)) is None
    assert pw.renav_reason({"n": 1}) is None                 # 只有观测次数、没有结论 → 不改行为
    assert pw.renav_reason(None) is None and pw.renav_reason("dirty") is None


def test_b1_back_landing_of_reads_record_runtime():
    by = {"LeafPage": {"runtime": {"back_landing": _bl(), "waited_s": 3}},
          "CleanPage": {"runtime": {"waited_s": 3}}, "NoRuntime": {}}
    assert pw.back_landing_of(by, "LeafPage")["node"] == "HostPage"
    assert pw.back_landing_of(by, "CleanPage") is None
    assert pw.back_landing_of(by, "NoRuntime") is None and pw.back_landing_of(by, "Ghost") is None


def test_b1_no_runtime_fact_keeps_back_step():
    edges = [_edge("RootPage", "LeafPage")]
    w = pw.plan_walk("RootPage", edges, "w", "r")                       # 不传 back_landing
    assert [s["action"] for s in w["steps"]] == ["coldstart", "tap", "back"]
    w2 = pw.plan_walk("RootPage", edges, "w", "r", back_landing={"LeafPage": _bl(matches_parent=True)})
    assert [s["action"] for s in w2["steps"]] == ["coldstart", "tap", "back"]


def test_b1_mismatch_and_confirm_dialog_emit_renav():
    edges = [_edge("RootPage", "LeafPage"), _edge("RootPage", "OutlinePage")]
    w = pw.plan_walk("RootPage", edges, "w", "r",
                     back_landing={"LeafPage": _bl(),
                                   "OutlinePage": _bl(node=None, confirm_dialog="ExitConfirmDialog")})
    ret_steps = [s for s in w["steps"] if s["action"] in ("back", "renav")]
    assert [s["action"] for s in ret_steps] == ["renav", "renav"]
    a, b = ret_steps
    assert (a["from"], a["to"], a["reason"]) == ("LeafPage", "RootPage", "back_landing_mismatch")
    assert a["observed_landing"] == "HostPage" and a["kind"] == "push"
    assert (b["from"], b["reason"], b["confirm_dialog"]) == ("OutlinePage", "back_needs_confirm",
                                                            "ExitConfirmDialog")


def test_b1_renav_never_replaces_tab_switch_or_wizard_return():
    """tab 切换本来就不发 BACK；向导单行道有自己的回位阶梯 —— 两者都不该被 renav 改写。"""
    tab = pw.plan_walk("HostPage", [_edge("HostPage", "TabPage", kind="tab_switch")], "w", "r",
                       back_landing={"TabPage": _bl()})
    assert [s["action"] for s in tab["steps"]] == ["coldstart", "tap", "verify"]
    wiz = pw.plan_walk("HostPage", [_edge("HostPage", "StepPage", kind="wizard_step")], "w", "r",
                       back_landing={"StepPage": _bl()})
    assert [s["action"] for s in wiz["steps"]] == ["coldstart", "tap", "skip"]
    assert wiz["steps"][2]["skip_reason"] == "one_way_no_return"


def test_b1_renav_position_and_subtree_interval_unchanged():
    """renav 只换回位手段：DFS 位置语义与子树区间标注一字不变（下一步仍从父页出发）。"""
    edges = [_edge("RootPage", "LeafPage"), _edge("LeafPage", "DeepPage"),
             _edge("RootPage", "OtherPage")]
    w = pw.plan_walk("RootPage", edges, "w", "r", back_landing={"DeepPage": _bl(node="RootPage")})
    acts = [(s["action"], s.get("from"), s["to"]) for s in w["steps"]]
    assert acts == [("coldstart", None, "RootPage"), ("tap", "RootPage", "LeafPage"),
                    ("tap", "LeafPage", "DeepPage"), ("renav", "DeepPage", "LeafPage"),
                    ("back", None, "RootPage"), ("tap", "RootPage", "OtherPage"),
                    ("back", None, "RootPage")]
    tap_leaf = w["steps"][1]
    assert tap_leaf["subtree_end_step"] == 5              # 区间仍覆盖到回位步


def test_b1_prune_tail_treats_renav_like_back():
    w = _w({"action": "coldstart", "to": "RootPage"},
           {"action": "tap", "from": "RootPage", "to": "APage", "settles_capture": "APage",
            "subtree_end_step": 4},
           {"action": "tap", "from": "APage", "to": "BPage", "settles_capture": "BPage"},
           {"action": "renav", "from": "BPage", "to": "APage", "reason": "back_landing_mismatch"},
           {"action": "renav", "from": "APage", "to": "RootPage", "reason": "back_needs_confirm"})
    pw.prune_tail(w, launcher="RootPage")
    assert [s["action"] for s in w["steps"]] == ["coldstart", "tap", "tap"]
    assert len(w["pruned_tail_steps"]) == 2
    # 规则②：renav 回已 finish 的启动页、其后再无一步从它出发 → 同 back 一样剪
    w2 = _w({"action": "coldstart", "to": "RootPage"},
            {"action": "tap", "from": "RootPage", "to": "APage", "settles_capture": "APage"},
            {"action": "renav", "from": "APage", "to": "RootPage", "reason": "back_landing_mismatch"},
            {"action": "skip", "from": "RootPage", "to": "CPage", "kind": "scope_exit"})
    pw.prune_tail(w2, launcher="RootPage")
    assert [s["action"] for s in w2["steps"]] == ["coldstart", "tap", "skip"]


def test_b1_end_to_end_plan_consumes_tree_back_landing(tmp_path):
    tp = _synthetic_project(tmp_path)
    tree = json.loads(tp.read_text())
    for p in tree["pages"]:
        if p["id"] == "AlphaActivity":
            p["runtime"] = {"back_landing": {"node": "RootActivity", "n": 3, "matched_n": 0,
                                             "matches_parent": False, "confirm_dialog": None,
                                             "expects": "HubActivity", "walk_id": "walk_1_main"}}
    # 加一个兄弟页，让 Alpha 的回位步不落在末尾（尾部空转步会被 A3 剪掉，那是另一条规则）
    tree["pages"].append({"id": "BetaActivity", "type": "Activity", "label": "BetaActivity",
                          "navigation_contract": {"relationship_kind": "activity_jump"},
                          "inbound_triggers": [{"from_page": "HubActivity", "trigger_label": "beta",
                                                "trigger_kind": "tap", "trigger_view_id": "btn_beta"}]})
    tp.write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    _asg_p = tmp_path / "spec" / "visual-verify" / "_trip_assignment.json"
    _asg = json.loads(_asg_p.read_text())
    _asg["pages"]["BetaActivity"] = {"trips": ["trip_1_logged_out", "trip_2_logged_in_vip"], "reason": "test"}
    _asg_p.write_text(json.dumps(_asg, ensure_ascii=False), encoding="utf-8")
    r = _run_plan(tp, tmp_path / "out")
    assert r.returncode == 0, r.stderr
    plan = json.loads((tmp_path / "out" / "walk_plan.json").read_text())
    w1 = next(w for w in plan["walks"] if w["walk_id"] == "walk_1_main")
    rn = [s for s in w1["steps"] if s["action"] == "renav"]
    assert rn and all(s["from"] == "AlphaActivity" and s["reason"] == "back_landing_mismatch" for s in rn)
    assert "AlphaActivity" in r.stderr and "renav" in r.stderr
    assert "重新导航" in (tmp_path / "out" / "walk_plan.txt").read_text()
