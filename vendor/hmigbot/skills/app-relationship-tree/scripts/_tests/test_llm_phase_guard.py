import os, sys, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import llm_phase_guard as g

def _tree():
    return {"flow_graph": {"edges": [1]}, "features": [{"id": "f"}],
            "pages": [{"id": "A", "type": "Activity", "navigation": {"inbound": [], "outbound": []}, "fq_class": "x.A",
                       "inbound_triggers": [{"from_page": "B", "trigger_label": None, "trigger_view_id": "btn_b", "evidence_line": 10, "source": "mechanical_candidate", "provenance": {"status": "candidate", "rule": "click_context"}}],
                       # 2026-09-09 Phase 2.7 契约：账号态前置必须带 polarity（required / absent）
                       "preconditions": [{"kind": "login_required", "evidence": "x", "polarity": "required"}],
                       "navigation_contract": {"relationship_kind": "activity_jump"},
                       "components": [{"id": "c1", "source_anchor": {"file": "f", "line": 1}}]}],
            "fragments": [], "dialogs": []}

def test_pass_on_upgrade_in_place():
    b = _tree(); a = copy.deepcopy(b)
    e = a["pages"][0]["inbound_triggers"][0]; e.update({"trigger_label": "进入", "source": "llm_source_read", "verified_from_candidate": True}); e["provenance"]["status"] = "confirmed"
    a["pages"][0]["purpose"] = "打开 A"
    assert g.verify(b, a) == []

def test_fail_on_protected_change_dup_lost_candidate_bad_kind():
    b = _tree(); a = copy.deepcopy(b); p = a["pages"][0]
    p["navigation"]["inbound"].append({"from": "Z"})                       # protected
    p["inbound_triggers"] = [{"from_page": "C", "trigger_label": "x"}, {"from_page": "C", "trigger_label": "y"}]   # dup + lost candidate B
    p["preconditions"].append({"kind": "data_required", "evidence": ""})   # 表外 + evidence 空
    p["navigation_contract"]["relationship_kind"] = "menu"
    a["dialogs"].append({"id": "NewDlg"})
    fails = g.verify(b, a)
    joined = "\n".join(fails)
    for token in ("navigation 被改", "同起点同触发重复", "机械候选条目消失", "kind 表外", "evidence 为空", "relationship_kind 非法", "新增 record"):
        assert token in joined, token

def test_disproven_keeps_candidate_and_allow_delete():
    b = _tree(); a = copy.deepcopy(b)
    a["pages"][0]["inbound_triggers"][0].update({"disproven": True, "disproven_reason": "调用点已注释"})   # 2026-09-08 晚：证伪须带理由
    assert g.verify(b, a) == []
    a["pages"] = []
    assert any("删除 record" in f for f in g.verify(b, a)) and g.verify(b, a, allow_delete=True) == []


def test_same_from_page_two_real_triggers_allowed_and_legacy_candidate_flag():
    b = _tree(); a = copy.deepcopy(b); p = a["pages"][0]
    p["inbound_triggers"][0].update({"source": "llm_source_read", "trigger_label": "进入"}); p["inbound_triggers"][0]["provenance"]["status"] = "corrected"
    p["inbound_triggers"].append({"from_page": "B", "trigger_view_id": "menu_b", "evidence_line": 55, "trigger_label": "菜单进入", "source": "llm_source_read"})
    assert g.verify(b, a) == []                                          # 同起点两个真触发（不同控件）合法
    p["inbound_triggers"].append({"from_page": "B", "trigger_view_id": "menu_b", "evidence_line": 55, "trigger_label": "复制", "source": "llm_source_read"})
    assert any("同起点同触发重复" in f for f in g.verify(b, a))          # 同键复制非法
    # 旧式扁平 candidate=true 仍被识别为候选：删掉即 FAIL
    b2 = _tree(); b2["pages"][0]["inbound_triggers"] = [{"from_page": "B", "candidate": True, "source": "mechanical_candidate"}]
    a2 = copy.deepcopy(b2); a2["pages"][0]["inbound_triggers"] = []
    assert any("机械候选条目消失" in f for f in g.verify(b2, a2))


def test_span_key_and_semantic_enums_and_walkability():
    """2026-09-08 晚试点契约：同 TextView 多个 Span 各一条合法；trigger_kind / walkability 枚举；disproven 须有理由。"""
    b = _tree(); a = copy.deepcopy(b); p = a["pages"][0]
    e0 = p["inbound_triggers"][0]; e0.update({"source": "llm_source_read", "trigger_label": "进入", "trigger_kind": "tap", "trigger_kind_evidence": "f.kt:10 — onClick"}); e0["provenance"]["status"] = "confirmed"
    p["inbound_triggers"] += [
        {"from_page": "B", "trigger_view_id": "tv_agree", "evidence_line": 40, "trigger_kind": "span", "span_text": "服务条款", "source": "llm_source_read"},
        {"from_page": "B", "trigger_view_id": "tv_agree", "evidence_line": 44, "trigger_kind": "span", "span_text": "隐私协议", "source": "llm_source_read"},
    ]
    p["walkability"] = {"status": "walkable", "source": "mechanical", "evidence": "x"}
    assert g.verify(b, a) == []
    p["inbound_triggers"].append({"from_page": "B", "trigger_view_id": "tv_agree", "evidence_line": 44, "trigger_kind": "span", "span_text": "隐私协议", "source": "llm_source_read"})
    assert any("同起点同触发重复" in f for f in g.verify(b, a))
    p["inbound_triggers"].pop()
    p["inbound_triggers"][1]["trigger_kind"] = "swipe"
    p["walkability"]["status"] = "maybe"
    p["inbound_triggers"].append({"from_page": "Z", "evidence_line": 99, "disproven": True, "source": "mechanical_candidate"})
    fails = "\n".join(g.verify(b, a))
    assert "trigger_kind 非法" in fails and "walkability.status 非法" in fails and "无 disproven_reason" in fails


# ── 2026-09-09 Phase 2.7 契约：账号态极性 + 输入守卫配方 ─────────────────────────────
def test_account_precondition_needs_polarity_record_and_edge_level(monkeypatch):
    monkeypatch.delenv(g.ALLOW_MISSING_POLARITY_ENV, raising=False)
    b = _tree(); a = copy.deepcopy(b); p = a["pages"][0]
    p["preconditions"][0].pop("polarity")                                    # record 级缺极性
    p["inbound_triggers"][0]["edge_preconditions"] = [{"kind": "vip_required", "evidence": "f.kt:9"}]  # 边级缺极性
    fails = "\n".join(g.verify(b, a))
    assert "preconditions[login_required] 缺 polarity" in fails
    assert "preconditions[vip_required] 缺 polarity" in fails
    # 非账号态 kind 不要求极性
    a2 = copy.deepcopy(b); a2["pages"][0]["preconditions"] = [{"kind": "param_required", "evidence": "f.kt:1"}]
    assert g.verify(b, a2) == []
    # 取值非法：恒 FAIL（连环境变量也降不了 —— 那是拼写错，不是过渡）
    a3 = copy.deepcopy(b); a3["pages"][0]["preconditions"][0]["polarity"] = "optional"
    monkeypatch.setenv(g.ALLOW_MISSING_POLARITY_ENV, "1")
    assert any("polarity 取值非法: optional" in f for f in g.verify(b, a3))


def test_missing_polarity_downgraded_to_warn_by_env(monkeypatch):
    b = _tree(); a = copy.deepcopy(b); a["pages"][0]["preconditions"][0].pop("polarity")
    monkeypatch.setenv(g.ALLOW_MISSING_POLARITY_ENV, "1")
    warns = []
    assert g.verify(b, a, warns=warns) == [] and any("缺 polarity" in w for w in warns)
    monkeypatch.setenv(g.ALLOW_MISSING_POLARITY_ENV, "0")                    # 只有 "1" 才降级
    assert any("缺 polarity" in f for f in g.verify(b, a))


def test_input_view_id_must_be_in_edit_ids(monkeypatch):
    monkeypatch.delenv(g.ALLOW_MISSING_POLARITY_ENV, raising=False)
    b = _tree()
    b["pages"].append({"id": "B", "type": "Activity", "navigation": {"inbound": [], "outbound": []},
                       "layout_facts": {"file": "m/res/layout/lay_b.xml", "view_ids": ["et_q", "btn_go"],
                                        "edit_ids": ["et_q"], "clickable_ids": ["btn_go"]}})
    a = copy.deepcopy(b); p = a["pages"][0]
    ok = {"kind": "state_required", "evidence": "f.kt:3 — 输入非空才可点",
          "input": {"view_id": "et_q", "text_hint": "abc"}}
    p["inbound_triggers"][0]["edge_preconditions"] = [ok]                    # 边级：查 from_page(B) 的 edit_ids
    assert g.verify(b, a) == []
    p["inbound_triggers"][0]["edge_preconditions"] = [dict(ok, input={"view_id": "btn_go"})]
    assert any("input.view_id=btn_go 不在 layout_facts.edit_ids" in f for f in g.verify(b, a))
    p["inbound_triggers"][0]["edge_preconditions"] = [dict(ok, input={"text_hint": "abc"})]
    assert any("input 缺 view_id" in f for f in g.verify(b, a))
    # 起点没有 edit_ids 机械事实（老树）→ 无据可证伪，不判
    a2 = copy.deepcopy(b); a2["pages"][1]["layout_facts"].pop("edit_ids")
    a2["pages"][0]["inbound_triggers"][0]["edge_preconditions"] = [dict(ok, input={"view_id": "et_nowhere"})]
    b2 = copy.deepcopy(b); b2["pages"][1]["layout_facts"].pop("edit_ids")
    assert g.verify(b2, a2) == []
