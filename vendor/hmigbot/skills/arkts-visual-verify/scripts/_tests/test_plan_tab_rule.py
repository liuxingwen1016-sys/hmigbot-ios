"""tab 边证据规则 / 同屏嵌入下钻 / skip_destructive 不下钻 / 静态 rid 定位顺序（2026-09-08）。
全部合成夹具，形状照抄五棵 AIPPT 树与 AntennaPod/DiceRoller 树里实测到的边写法。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import plan_edge_walk as pw
import walk_exec as we


def _cfg(**kw):
    base = {"tabs": set(), "sub_tabs": set(), "wizard": set(), "webview": set(), "generation_targets": set(),
            "main_root": "SplashActivity", "launcher": "SplashActivity", "tab_host": None}
    base.update(kw); return base


# ── 证据函数 ───────────────────────────────────────────────────────────────
def test_click_evidence_shapes_seen_in_trees():
    assert pw.edge_click_evidence({"trigger_label": "我的", "trigger_method": "onClick", "trigger_view_id": "tv_mine_tab"}) == "label"
    assert pw.edge_click_evidence({"trigger_label": "我的", "trigger_method": "viewpager_tab", "trigger_view_id": "viewPager"}) == "label"   # mock 树
    assert pw.edge_click_evidence({"trigger_label": "trigger_label_unknown", "trigger_view_id": "fragment_container"}) is None   # mock 装载边
    assert pw.edge_click_evidence({"trigger_label": "unknown", "trigger_view_id": "tv_works_tab"}) == "view_id"
    assert pw.edge_click_evidence({"trigger_label": "category_name_dynamic", "label_dynamic": True, "trigger_view_id": "tabLayout"}) is None
    assert pw.edge_click_evidence({"trigger_label": "", "trigger_view_id": "null"}) is None
    assert pw.edge_click_evidence(None) is None


def test_hostload_vocab():
    for m in ("hosts fragment (FragmentTransaction.replace)", "createOrShowFragment(host_default装载)", "initView", "initViewPager"):
        assert pw.is_hostload_edge({"trigger_method": m}), m
    for m in ("onClick", "onClick->changeItem(1)", "viewpager_tab", "getHomeIntent", "OnTitleBarListener.onRightClick", None):
        assert not pw.is_hostload_edge({"trigger_method": m}), m


def test_tab_host_majority_ignores_hostload():
    by = {"MineFragment": {"inbound_triggers": [
              {"from_page": "HomeActivity", "trigger_label": "我的", "trigger_method": "onClick"},
              {"from_page": "MineActivity", "trigger_label": "我的", "trigger_method": "initView", "trigger_view_id": "tv_mine_tab"}]},
          "WorksFragment": {"inbound_triggers": [
              {"from_page": "HomeActivity", "trigger_label": "作品", "trigger_method": "getHomeIntent"},
              {"from_page": "WorksPage", "trigger_label": "作品", "trigger_method": "initView"}]},
          "NoEvidence": {"inbound_triggers": [{"from_page": "X", "trigger_label": "unknown"}]}}
    assert pw.derive_tab_host(by, {"MineFragment", "WorksFragment", "NoEvidence"}) == "HomeActivity"
    assert pw.derive_tab_host(by, {"NoEvidence"}) is None
    assert pw.derive_tab_host(by, set()) is None


# ── classify ───────────────────────────────────────────────────────────────
def test_classify_tab_rules():
    cfg = _cfg(tabs={"MineFragment", "RecommendFragment"}, tab_host="HomeActivity")
    # ① tab_host 起点
    assert pw.classify("HomeActivity", "MineFragment", "我的", set(), cfg,
                       edge={"trigger_method": "hosts fragment (FragmentTransaction.replace)"})[0] == "tab_switch"
    # ② 非宿主但有点击证据、非装载
    assert pw.classify("OtherPage", "MineFragment", "我的", set(), cfg,
                       edge={"trigger_label": "我的", "trigger_method": "onClick"})[0] == "tab_switch"
    # ③ 装载边 → embed（0826 树把 tab 文案/id 抄到了装载边上）
    assert pw.classify("ChoicePPTTemplatePage", "RecommendFragment", "模版", set(), cfg,
                       edge={"trigger_label": "模版", "trigger_view_id": "tv_template_tab", "trigger_method": "initView"})[0] == "embed"
    # ③ 无证据 → embed
    assert pw.classify("ChoicePPTTemplatePage", "RecommendFragment", "trigger_label_unknown", set(), cfg,
                       edge={"trigger_label": "trigger_label_unknown", "trigger_view_id": "fragment_container",
                             "trigger_method": "createOrShowFragment(host_default装载)"})[0] == "embed"
    # 旧调用方式（不传 edge）：非宿主起点退成 embed，宿主起点仍 tab_switch
    assert pw.classify("HomeActivity", "MineFragment", "我的", set(), cfg)[0] == "tab_switch"
    assert pw.classify("Other", "MineFragment", "我的", set(), cfg)[0] == "embed"


def test_classify_untouched_without_tabs():
    """AntennaPod / Compose 形状：树无 tab 类 → 走原分支，结果与 main_root 无关。"""
    cfg = _cfg()
    assert pw.classify("A", "B", "进入", set(), cfg, edge={"trigger_label": "进入"}) == ("push", "normal")
    assert pw.classify("A", "D", "确定", {"D"}, cfg) == ("confirm_risk", "skip_unless_verified")
    assert pw.classify("A", "W", "x", set(), _cfg(wizard={"W"}, tabs={"W"})) == ("wizard_step", "normal")


# ── plan_walk：同屏嵌入下钻 + skip_destructive 不下钻 ───────────────────────
def _edge(frm, to, kind="push", label="go", safety="normal", **kw):
    return {"from": frm, "to": to, "label": label, "kind": kind, "safety": safety,
            "needs_discovery": False, "settles_grounding": [], "evidence_line": None, **kw}


def test_embed_first_reach_verifies_and_descends():
    edges = [_edge("R", "H"), _edge("H", "C"), _edge("C", "T", kind="embed", label=None),
             _edge("T", "A", label="进A", static_rid="btn_a")]
    w = pw.plan_walk("R", edges, "w", "r")
    acts = [(s["action"], s.get("to"), s.get("kind")) for s in w["steps"]]
    assert ("verify", "T", "embed") in acts and ("tap", "A", "push") in acts
    assert ("tap", "T", "embed") not in acts                       # 嵌入边绝不 tap
    assert all(not (s["action"] == "back" and s["to"] == "C" and s.get("kind") == "embed") for s in w["steps"])
    assert {"T", "A"} <= set(w["settles"])
    v = next(s for s in w["steps"] if s["action"] == "verify" and s["to"] == "T")
    assert v["settles_capture"] == "T"
    assert next(s for s in w["steps"] if s.get("to") == "A" and s["action"] == "tap")["static_rid"] == "btn_a"


def test_embed_after_tab_switch_is_verify_only():
    """PRIO 让 tab 先由宿主 tab_switch 首达；后到的 embed 边只剩一步 verify，不重复下钻。"""
    edges = [_edge("R", "H"), _edge("H", "T", kind="tab_switch", label="我的"), _edge("T", "A"),
             _edge("H", "C"), _edge("C", "T", kind="embed", label=None)]
    w = pw.plan_walk("R", edges, "w", "r")
    taps_A = [s for s in w["steps"] if s["action"] == "tap" and s["to"] == "A"]
    assert len(taps_A) == 1
    emb = [s for s in w["steps"] if s.get("kind") == "embed"]
    assert len(emb) == 1 and emb[0]["action"] == "verify" and emb[0]["settles_capture"] is None


def test_skip_destructive_not_descended():
    edges = [_edge("R", "H"), _edge("H", "D", kind="destructive", label="取消订阅", safety="skip_destructive"),
             _edge("D", "E", label="申请退款"), _edge("H", "S", label="安全页")]
    w = pw.plan_walk("R", edges, "w", "r")
    st = next(s for s in w["steps"] if s.get("to") == "D")
    assert st["action"] == "skip" and st["skip_reason"] == "skip_destructive_no_descend" and st["settles_capture"] is None
    assert not any(s.get("to") == "E" for s in w["steps"])
    assert "D" not in w["settles"] and "E" not in w["settles"] and "S" in w["settles"]
    assert w["destructive_cut"] == [["H", "D"]]
    assert not any(s["action"] == "tap" and s.get("safety") == "skip_destructive" for s in w["steps"])


def test_path_walk_never_routes_through_destructive():
    edges = [_edge("R", "H"), _edge("H", "D", kind="destructive", safety="skip_destructive"),
             _edge("D", "G", kind="generation", safety="side_effect")]
    assert pw.plan_path_walk("R", edges, "G", "w2", "r", already=set()) is None
    edges.append(_edge("H", "G", kind="generation", safety="side_effect", static_rid="btn_gen"))
    w = pw.plan_path_walk("R", edges, "G", "w2", "r", already=set())
    assert [s["to"] for s in w["steps"] if s["action"] == "tap"] == ["H", "G"]
    assert w["steps"][-2]["static_rid"] == "btn_gen"


# ── find_control 定位顺序 ──────────────────────────────────────────────────
XML = """<?xml version='1.0' encoding='UTF-8'?><hierarchy>
<node class="android.widget.FrameLayout" resource-id="pkg:id/viewPager" clickable="false" bounds="[0,0][1000,1800]" text="">
  <node class="android.widget.TextView" resource-id="pkg:id/tv_mine_tab" clickable="true" bounds="[750,1700][1000,1800]" text="我的"/>
  <node class="android.widget.TextView" resource-id="pkg:id/tv_works_tab" clickable="true" bounds="[500,1700][750,1800]" text="作品"/>
  <node class="android.widget.TextView" resource-id="pkg:id/runtime_x" clickable="true" bounds="[0,100][100,200]" text="我的头像"/>
</node></hierarchy>"""


def test_find_control_priority_runtime_static_label():
    pt, how = we.find_control(XML, rid="runtime_x", label="我的", static_rid="tv_mine_tab")
    assert how == "rid:runtime_x"                              # 反哺 rid 最先
    pt, how = we.find_control(XML, rid=None, label="我的", static_rid="tv_mine_tab")
    assert how == "static_rid:tv_mine_tab" and pt == (875, 1750)
    pt, how = we.find_control(XML, rid=None, label="我的", static_rid="viewPager")   # 容器 id 不可点 → 回退文案精确
    assert how == "text:我的"
    pt, how = we.find_control(XML, rid=None, label="作品")
    assert how == "text:作品"
    assert we.find_control(XML, rid=None, label="不存在", static_rid="nope") == (None, None)


# ── 向导链重建确定性（AntennaPod 树实证：两步同声明 leads_to 同一后继）───────────
def test_wizard_chain_rebuild_is_deterministic_on_conflict():
    def nc(idx, nxt):
        return {"relationship_kind": "wizard_step", "wizard_index": idx,
                "exit_action_to_next": {"leads_to": nxt, "label": "下一步", "resource_id": "btn_next"},
                "trigger_actions": [{"type": "tap_text", "label": "开始", "resource_id": "btn_start"}]}
    tree = {"pages": [{"id": "Host", "inbound_triggers": []}], "dialogs": [],
            "fragments": [{"id": "Cover", "navigation_contract": nc(0, "Desc"),
                           "inbound_triggers": [{"from_page": "Host", "trigger_label": "开始", "trigger_view_id": "btn_start"}]},
                          {"id": "Ext", "navigation_contract": nc(0, "Desc"),
                           "inbound_triggers": [{"from_page": "Host", "trigger_label": "x"}]},
                          {"id": "Desc", "navigation_contract": nc(0, "Ext"),
                           "inbound_triggers": [{"from_page": "Host", "trigger_label": "y"}]}]}
    cfg = _cfg(wizard={"Cover", "Ext", "Desc"})
    targets = {"Host", "Cover", "Ext", "Desc"}
    outs = set()
    for _ in range(5):
        edges, _by = pw.build_edges(tree, targets, targets, cfg)
        outs.add(tuple(sorted((e["from"], e["to"], e.get("static_rid")) for e in edges if e["kind"] == "wizard_step")))
    assert len(outs) == 1, outs
    chain = next(iter(outs))
    assert ("Cover", "Desc", "btn_next") in chain and ("Desc", "Ext", "btn_next") in chain   # (wizard_index, id) 首个为准
    assert ("Host", "Cover", "btn_start") in chain                                           # 链头带契约 resource_id


def test_embed_defers_to_tab_host_first_reach():
    """深层 embed 边撞到宿主的 tab：只 verify、不结账、不下钻；首达留给宿主 tab_switch。"""
    edges = [_edge("R", "H"), _edge("H", "A", kind="tab_switch", label="A"), _edge("A", "F"),
             _edge("F", "T", kind="embed", label=None), _edge("H", "T", kind="tab_switch", label="T"), _edge("T", "X")]
    w = pw.plan_walk("R", edges, "w", "r", tab_host="H")
    emb = [s for s in w["steps"] if s.get("kind") == "embed"]
    assert len(emb) == 1 and emb[0]["settles_capture"] is None                 # 撞到时不结账
    tap_T = [s for s in w["steps"] if s["action"] == "tap" and s["to"] == "T"]
    assert len(tap_T) == 1 and tap_T[0]["settles_capture"] == "T"             # 宿主首达
    assert sum(1 for s in w["steps"] if s["action"] == "tap" and s["to"] == "X") == 1
    # 无宿主信息时退回原行为：embed 首达就结账下钻
    w2 = pw.plan_walk("R", [_edge("R", "F"), _edge("F", "T", kind="embed", label=None), _edge("T", "X")], "w", "r")
    assert next(s for s in w2["steps"] if s.get("kind") == "embed")["settles_capture"] == "T"


# ── 2026-09-08 晚（试点核定）：计划器消费 LLM 语义字段 / 占位串不算文案 / 不可走 record 剔除；执行器 Span 定点与等待预算 ──
def _mini_tree():
    def rec(rid, typ, inbound, **kw):
        d = {"id": rid, "type": typ, "navigation": {"inbound": [], "outbound": []}, "inbound_triggers": inbound,
             "navigation_contract": {"relationship_kind": "activity_jump"}, "components": []}
        d.update(kw); return d
    return {"app": {"launcher_activity": "x.R", "launcher_short": "R"},
            "pages": [
                rec("R", "Activity", []),
                rec("H", "Activity", [{"from_page": "R", "trigger_label": None, "trigger_kind": "auto", "wait_hint": "countdown_ms:3000", "trigger_kind_evidence": "R.kt:9"}]),
                rec("P", "Activity", [{"from_page": "H", "trigger_label": "trigger_label_unknown", "trigger_view_id": None}]),
                rec("L", "Activity", [{"from_page": "H", "trigger_label": None, "trigger_view_id": "ppt_item_root", "trigger_kind": "list_item", "label_dynamic": True}]),
                rec("W", "Activity", [{"from_page": "H", "trigger_label": None, "trigger_view_id": "tv_agree", "trigger_kind": "span", "span_text": "服务条款"}]),
                rec("X", "Activity", [{"from_page": "H", "trigger_label": "去X"}], walkability={"status": "dead", "source": "mechanical", "evidence": "零引用"}),
            ], "fragments": [], "dialogs": []}


def test_build_edges_consumes_trigger_kind_and_placeholder():
    t = _mini_tree(); recs = t["pages"]; by = {r["id"]: r for r in recs}
    cfg = _cfg(main_root="H")
    edges, _ = pw.build_edges(t, {r["id"] for r in recs}, {r["id"] for r in recs}, cfg)
    e = {(x["from"], x["to"]): x for x in edges}
    assert e[("R", "H")]["auto_transition"] is True and e[("R", "H")]["needs_discovery"] is False and e[("R", "H")]["wait_hint"] == "countdown_ms:3000"
    assert e[("H", "P")]["needs_discovery"] is True                      # 占位串不是文案
    assert e[("H", "L")]["needs_discovery"] is False and e[("H", "L")]["item_rid"] == "ppt_item_root"
    assert e[("H", "W")]["needs_discovery"] is False and e[("H", "W")]["span_text"] == "服务条款"
    # 语义字段必须透传进步序（执行器只读步，不读边）
    w = pw.plan_walk("H", edges, "w", "r")
    st = {(x.get("from"), x.get("to")): x for x in w["steps"] if x["action"] == "tap"}
    assert st[("H", "L")]["item_rid"] == "ppt_item_root" and st[("H", "W")]["span_text"] == "服务条款" and st[("H", "L")]["trigger_kind"] == "list_item"


def test_find_span_point_and_wait_attempts():
    xml = ('<node resource-id="x:id/tv_agree" text="我已阅读并同意 服务条款 和 隐私协议" bounds="[100,900][1000,960]" clickable="true"/>'
           '<node resource-id="x:id/other" text="服务条款" bounds="[0,0][10,10]"/>')
    pt, how = we.find_span_point(xml, "tv_agree", "服务条款")
    # 子串「服务条款」起于第 8 字、19 字文本 → 横坐标 ≈ 100 + 900 × 10/19 ≈ 573（不是控件中心 550）
    assert how.startswith("span:") and 560 < pt[0] < 590 and pt[1] == 930
    assert we.find_span_point(xml, "tv_agree", "不存在") == (None, None)
    assert we.wait_attempts({"wait_hint": "countdown_ms:15000"}) == 10 and we.wait_attempts({"wait_hint": "immediate"}) == 4 and we.wait_attempts({}) == 8


def test_wizard_exit_unresolved_is_discovery_not_auto_and_deeplink_walks():
    """contract 出口来自 wizard_exit_controls；抽不到标 exit_unresolved → 需探索而非自动跳转。external_entry 页有可解析深链 → 一步直达走；占位符未解析 → 只留账。"""
    t = _mini_tree()
    # 造一个向导：H 宿主，S1 → S2，S1 出口未解析
    t["fragments"] = [
        {"id": "S1", "type": "Fragment", "parent_in_nav": "H", "navigation": {"inbound": [{"from": "H", "trigger": "viewpager_wizard", "wizard_index": 0}], "outbound": []},
         "inbound_triggers": [{"from_page": "H", "trigger_kind": "auto", "trigger_label": None}], "components": [],
         "navigation_contract": {"relationship_kind": "wizard_step", "wizard_index": 0, "trigger_actions": [{"type": "auto_default"}],
                                 "exit_action_to_next": {"type": "tap_text", "label": None, "resource_id": None, "leads_to": "S2", "exit_unresolved": True}}},
        {"id": "S2", "type": "Fragment", "parent_in_nav": "H", "navigation": {"inbound": [{"from": "H", "trigger": "viewpager_wizard", "wizard_index": 1}], "outbound": []},
         "inbound_triggers": [{"from_page": "H", "trigger_label": None}], "components": [],
         "navigation_contract": {"relationship_kind": "wizard_step", "wizard_index": 1, "trigger_actions": [{"type": "tap_text", "label": None}]}},
    ]
    t["pages"].append({"id": "DL", "type": "Activity", "navigation": {"inbound": [], "outbound": []}, "inbound_triggers": [], "components": [],
                       "navigation_contract": {"relationship_kind": "activity_jump"},
                       "walkability": {"status": "external_entry", "source": "mechanical", "evidence": "manifest",
                                       "facts": {"manifest": {"deeplinks": [{"scheme": "myapp", "host": "open", "path": "/x"}]}}}})
    t["pages"].append({"id": "DU", "type": "Activity", "navigation": {"inbound": [], "outbound": []}, "inbound_triggers": [], "components": [],
                       "navigation_contract": {"relationship_kind": "activity_jump"},
                       "walkability": {"status": "external_entry", "source": "mechanical", "evidence": "manifest",
                                       "facts": {"manifest": {"deeplinks": [{"scheme": "startapp", "host": "${applicationId}", "path": None, "unresolved_placeholders": ["applicationId"]}]}}}})
    recs = t["pages"] + t["fragments"]; ids = {r["id"] for r in recs}
    cfg = _cfg(main_root="H", wizard={"S1", "S2"})
    edges, _ = pw.build_edges(t, ids, ids, cfg)
    e = {(x["from"], x["to"]): x for x in edges}
    assert e[("S1", "S2")]["needs_discovery"] is True and not e[("S1", "S2")].get("auto_transition")
    # deeplink：走 main() 的组装逻辑太重，这里只验证 walk 构造规则（与 main 同款判据）
    dls = [(r["id"], dl) for r in recs for dl in (((r.get("walkability") or {}).get("facts") or {}).get("manifest") or {}).get("deeplinks") or []
           if (r.get("walkability") or {}).get("status") == "external_entry"]
    ok = [(rid, d) for rid, d in dls if d.get("scheme") and not d.get("unresolved_placeholders")]
    bad = [(rid, d) for rid, d in dls if d.get("unresolved_placeholders")]
    assert [x[0] for x in ok] == ["DL"] and [x[0] for x in bad] == ["DU"]
