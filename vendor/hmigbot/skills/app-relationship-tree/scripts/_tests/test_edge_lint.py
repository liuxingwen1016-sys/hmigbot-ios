"""edge_lint 五条规则 + 幂等的合成用例（零 app 常量：页名/控件 id 全是占位符）。"""
import os, sys, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import edge_lint as el


def _tree(pages):
    return {"pages": pages, "fragments": [], "dialogs": []}


def _lf(file, view_ids, **kw):
    d = {"file": file, "view_ids": list(view_ids), "static_texts": [], "includes": []}
    d.update(kw)
    return d


def _flags(tree):
    """→ {(from_page, view_id, to): flags}"""
    flags, edges = el.compute_flags(tree)
    return {(e.get("from_page"), e.get("trigger_view_id"), tid): flags[id(e)] for tid, e in edges}


def test_rule1_owner_mismatch():
    t = _tree([{"id": "A"},
               {"id": "B", "inbound_triggers": [
                   {"from_page": "A", "trigger_view_id": "ctl_1", "trigger_owner_page": "C"},
                   {"from_page": "A", "trigger_view_id": "ctl_2", "trigger_owner_page": "A"},   # 同页 → 不标
                   {"from_page": "A", "trigger_view_id": "ctl_3"}]},                            # 无 owner → 不标
               {"id": "C"}])
    f = _flags(t)
    assert f[("A", "ctl_1", "B")] == ["owner_mismatch"]
    assert f[("A", "ctl_2", "B")] == [] and f[("A", "ctl_3", "B")] == []


def test_rule2_site_two_targets_and_conditioned_branch_exempt():
    def mk(extra_b=None, extra_c=None):
        return _tree([{"id": "A"},
                      {"id": "B", "inbound_triggers": [dict({"from_page": "A", "trigger_view_id": "ctl_1"}, **(extra_b or {}))]},
                      {"id": "C", "inbound_triggers": [dict({"from_page": "A", "trigger_view_id": "ctl_1"}, **(extra_c or {}))]}])
    f = _flags(mk())
    assert f[("A", "ctl_1", "B")] == ["site_two_targets"] and f[("A", "ctl_1", "C")] == ["site_two_targets"]
    # 任一条带 branch_condition 或 edge_preconditions → 有条件分支：不标硬 flag，改软标 conditional（两条都标）
    for extra in ({"branch_condition": "已登录"}, {"edge_preconditions": [{"kind": "login_required", "polarity": "required", "evidence": "f:1"}]}):
        assert _flags(mk(extra_b=extra))[("A", "ctl_1", "C")] == ["site_two_targets_conditional"]
        assert _flags(mk(extra_c=extra))[("A", "ctl_1", "B")] == ["site_two_targets_conditional"]
    # 同一目标上的两条边（同站点键）不算"两个目标"
    one = _tree([{"id": "A"}, {"id": "B", "inbound_triggers": [
        {"from_page": "A", "trigger_view_id": "ctl_1"}, {"from_page": "A", "trigger_view_id": "ctl_1"}]}])
    assert all(v == [] for v in _flags(one).values())
    # 已 disproven 的边不参与成组
    dead = _tree([{"id": "A"},
                  {"id": "B", "inbound_triggers": [{"from_page": "A", "trigger_view_id": "ctl_1"}]},
                  {"id": "C", "inbound_triggers": [{"from_page": "A", "trigger_view_id": "ctl_1", "disproven": True}]}])
    assert all(v == [] for v in _flags(dead).values())


def test_rule3_rid_not_in_from_layout_with_include_host_and_item_root():
    base = {"id": "A", "layout_facts": _lf("m/res/layout/lay_a.xml", ["ctl_own"], includes=["lay_bar"])}
    bar = {"id": "BarRec", "layout_facts": _lf("m/res/layout/lay_bar.xml", ["ctl_bar"])}
    host = {"id": "H", "layout_facts": _lf("m/res/layout/lay_h.xml", ["ctl_host"]), "contains": ["A"]}
    t = _tree([base, bar, host, {"id": "T", "inbound_triggers": [
        {"from_page": "A", "trigger_view_id": "ctl_own"},        # 自身 layout
        {"from_page": "A", "trigger_view_id": "ctl_bar"},        # include 链解析得到
        {"from_page": "A", "trigger_view_id": "ctl_host"},       # 宿主（contains 反向）
        {"from_page": "A", "trigger_view_id": "ctl_ghost"},      # 谁都没有 → 标
        {"from_page": "NoRec", "trigger_view_id": "ctl_x"},      # 起点无 record → 不标
        {"from_page": "BarRec", "trigger_view_id": "ctl_bar"}]}])
    f = _flags(t)
    for vid in ("ctl_own", "ctl_bar", "ctl_host"):
        assert f[("A", vid, "T")] == [], vid
    assert f[("A", "ctl_ghost", "T")] == ["rid_not_in_from_layout"]
    assert f[("NoRec", "ctl_x", "T")] == []
    # 起点没有 layout_facts → 无据可证伪，不标
    t2 = _tree([{"id": "A"}, {"id": "T", "inbound_triggers": [{"from_page": "A", "trigger_view_id": "ctl_ghost"}]}])
    assert _flags(t2)[("A", "ctl_ghost", "T")] == []
    # 适配器 item 根 id 算在可见域里（否则每条 list_item 边都误报）
    t3 = _tree([{"id": "A", "layout_facts": _lf("m/res/layout/lay_a.xml", ["ctl_own"]),
                 "list_item_roots": [{"item_layout": "item_row", "root_id": "row_root", "layout_file": "m/res/layout/item_row.xml"}]},
                {"id": "T", "inbound_triggers": [{"from_page": "A", "trigger_view_id": "row_root", "trigger_kind": "list_item"}]}])
    assert _flags(t3)[("A", "row_root", "T")] == []


def test_rule4_rid_no_click_evidence_and_confirmed_exempt():
    def mk(status=None):
        e = {"from_page": "A", "trigger_view_id": "ctl_plain"}
        if status:
            e["provenance"] = {"status": status}
        return _tree([{"id": "A", "layout_facts": _lf("m/res/layout/lay_a.xml", ["ctl_plain", "btn_ok"],
                                                      clickable_ids=["btn_ok"])},
                      {"id": "T", "inbound_triggers": [e]}])
    assert _flags(mk())[("A", "ctl_plain", "T")] == ["rid_no_click_evidence"]
    assert _flags(mk("candidate"))[("A", "ctl_plain", "T")] == ["rid_no_click_evidence"]
    assert _flags(mk("confirmed"))[("A", "ctl_plain", "T")] == []          # 运行时已确认 → 不标
    # 在 clickable_ids 里 → 不标
    ok = _tree([{"id": "A", "layout_facts": _lf("m/res/layout/lay_a.xml", ["btn_ok"], clickable_ids=["btn_ok"])},
                {"id": "T", "inbound_triggers": [{"from_page": "A", "trigger_view_id": "btn_ok"}]}])
    assert _flags(ok)[("A", "btn_ok", "T")] == []
    # 没有 clickable_ids 字段（老树 / 没跑 D2）→ 不标
    old = _tree([{"id": "A", "layout_facts": _lf("m/res/layout/lay_a.xml", ["ctl_plain"])},
                 {"id": "T", "inbound_triggers": [{"from_page": "A", "trigger_view_id": "ctl_plain"}]}])
    assert _flags(old)[("A", "ctl_plain", "T")] == []


def test_rule5_compressed_path():
    t = _tree([{"id": "A"},
               {"id": "B", "inbound_triggers": [{"from_page": "A", "trigger_view_id": "ctl_1"}]},
               {"id": "C", "inbound_triggers": [{"from_page": "A", "trigger_view_id": "ctl_1"},
                                                {"from_page": "B", "trigger_view_id": "ctl_next"}]}])
    f = _flags(t)
    assert "compressed_path" in f[("A", "ctl_1", "C")]          # A→C 其实是 A→B→C 压成一跳
    assert "compressed_path" not in f[("A", "ctl_1", "B")]
    assert f[("B", "ctl_next", "C")] == []
    # B→C 那条被证伪时不再构成压缩证据
    t2 = copy.deepcopy(t)
    t2["pages"][2]["inbound_triggers"][1]["disproven"] = True
    assert "compressed_path" not in _flags(t2)[("A", "ctl_1", "C")]


def test_write_is_idempotent_and_prunes_stale_flags():
    t = _tree([{"id": "A", "layout_facts": _lf("m/res/layout/lay_a.xml", ["ctl_own"])},
               {"id": "B", "inbound_triggers": [{"from_page": "A", "trigger_view_id": "ctl_ghost",
                                                 "guard_flags": ["stale_flag"]},
                                                {"from_page": "A", "trigger_view_id": "ctl_own",
                                                 "guard_flags": ["stale_flag"]}]}])
    r1 = el.annotate(t, write=True)
    snap1 = copy.deepcopy(t)
    r2 = el.annotate(t, write=True)
    for d in (snap1, t):
        d["_phase_markers"]["edge_lint"].pop("ts")
    assert snap1 == t and r1["counts"] == r2["counts"]          # 幂等（ts 除外）
    its = t["pages"][1]["inbound_triggers"]
    assert its[0]["guard_flags"] == ["rid_not_in_from_layout"]  # 旧值被覆盖，不累积
    assert "guard_flags" not in its[1]                          # 不中的边把字段删掉
    assert t["_phase_markers"]["edge_lint"]["counts"]["rid_not_in_from_layout"] == 1
