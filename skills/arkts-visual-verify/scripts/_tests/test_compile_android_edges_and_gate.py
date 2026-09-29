#!/usr/bin/env python3
"""编译期「安卓验过的边一条都不许静默放过」+ 反向门禁探测 + 翻译账（2026-09-11）。

病（AIPPT_CodeX_0829 真机首跑实证）：执行期早就是「翻译失败 ⇒ 疑鸿蒙缺陷 ⇒ 三分归因 ⇒ 出单」，
**翻译期（编译）不是**。登录趟 61 个动作步编译期静默跳 47，其中 26 步对应的边安卓已 `confirmed`，
0 条进过 `_blame` —— 账面上「鸿蒙没验」和「鸿蒙没问题」长得一模一样；另有 33 步 `skip_reason` 为空。

夹具纪律：所有 app 侧标识一律占位串（PageA / GateX / ctlA / 触发甲…）。
逻辑与断言里**不出现任何真实应用的页名、rid、文案** —— 出现的只有 schema 词汇
（login_required / polarity / confirmed）和流水线自己的趟命名习惯（trip_1_logged_out）。
"""
import json
import os
import subprocess
import sys

import pytest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)

import compile_replay_plan as C  # noqa: E402


# ── 夹具 ────────────────────────────────────────────────────────────────────
def edge(frm, to, status="confirmed", trigger=None, rid=None, text=None,
         landed=None, device_state="trip_1_logged_out"):
    r = {"from": frm, "to": to, "status": status, "trigger": trigger,
         "device_state": device_state}
    if rid or text:
        r["control"] = {k: v for k, v in (("rid", rid), ("text", text)) if v}
    if landed:
        r["landed"] = landed
    return r


def ib(frm, label=None, rid=None, preconds=()):
    return {"from_page": frm, "trigger_label": label, "trigger_view_id": rid,
            "edge_preconditions": list(preconds)}


def pre(kind, polarity=None):
    p = {"kind": kind}
    if polarity:
        p["polarity"] = polarity
    return p


# ── 1. 安卓边真值索引 ────────────────────────────────────────────────────────
def test_lookup_prefers_exact_trigger_key_over_sibling(tmp_path):
    """同起点同终点的兄弟边只有触发控件不同 —— 只按 (from,to) 查会取回兄弟的 rid
    （安卓侧实测过的 mechanical_sibling_rid_collision）。"""
    p = tmp_path / "e.json"
    p.write_text(json.dumps([
        edge("PageA", "PageB", trigger="触发甲", rid="ctlA"),
        edge("PageA", "PageB", trigger="触发乙", rid="ctlB"),
    ]), encoding="utf-8")
    idx = C.load_android_edges(str(p))
    assert C.android_control_identity(
        C.android_edge_lookup(idx, "PageA", "PageB", "触发甲"))[1] == "ctlA"
    assert C.android_control_identity(
        C.android_edge_lookup(idx, "PageA", "PageB", "触发乙"))[1] == "ctlB"


def test_lookup_prefers_confirmed_over_not_reproduced(tmp_path):
    p = tmp_path / "e.json"
    p.write_text(json.dumps([
        edge("PageA", "PageB", status="not_reproduced"),
        edge("PageA", "PageB", status="confirmed", rid="ctlA"),
    ]), encoding="utf-8")
    idx = C.load_android_edges(str(p))
    assert C.android_edge_lookup(idx, "PageA", "PageB")["status"] == "confirmed"


def test_loader_tolerates_missing_and_broken(tmp_path):
    for bad in (None, str(tmp_path / "nope.json")):
        assert C.load_android_edges(bad) == {"by_key": {}, "records": []}
    b = tmp_path / "b.json"; b.write_text("{ not json", encoding="utf-8")
    assert C.load_android_edges(str(b))["records"] == []
    o = tmp_path / "o.json"; o.write_text('{"a":1}', encoding="utf-8")   # 不是 list
    assert C.load_android_edges(str(o))["records"] == []


def test_control_identity_ignores_unknown_trigger_placeholder():
    assert C.android_control_identity(
        {"trigger": "trigger_label_unknown"}) == (None, None)
    assert C.android_control_identity({"trigger_view_id": "pkg:id/ctlA"})[1] == "ctlA"
    assert C.android_control_identity(None) == (None, None)


# ── 2. 破坏性重查（补身份这条新通路必须重新过闸）──────────────────────────────
@pytest.mark.parametrize("text,rid", [
    (None, "tv_fast_refund"),          # 英文 rid 命中资金 rid 表
    (None, "btn_renew"),               # 英文 rid 命中资金词表
    ("注销账号", None),                 # 中文文案命中通用破坏词
])
def test_android_identity_re_checked_for_destructive(text, rid):
    assert C.identity_is_destructive(text, rid) is True


def test_harmless_identity_passes():
    assert C.identity_is_destructive("关于我们", "ctl_about") is False


def test_annotations_blacklist_participates():
    assert C.identity_is_destructive("咨询甲方", None, blacklist=["咨询甲方"]) is True


# ── 3. 门节点 / 登出态判定（零 app 硬编码）──────────────────────────────────
TREE_GATED = {"pages": [
    # GateX 是门：登录**缺席**时这条边落到它
    {"id": "GateX", "inbound_triggers": [
        ib("PageA", label="入口甲", rid="ctlA", preconds=[pre("login_conditional", "absent")])]},
    # PageB 必须已登录才进得去（同一个触发点 ctlA）
    {"id": "PageB", "inbound_triggers": [
        ib("PageA", label="入口甲", rid="ctlA", preconds=[pre("login_required", "required")])]},
    # PageC 无任何门前置
    {"id": "PageC", "inbound_triggers": [ib("PageA", label="入口丙", rid="ctlC")]},
    {"id": "PageA", "inbound_triggers": []},
]}


def test_gate_nodes_come_from_absent_polarity_only():
    g = C.find_gate_nodes(TREE_GATED)
    assert set(g) == {"GateX"}                 # required 的那条不是门，是被门拦的目标
    assert g["GateX"] == ["login_conditional"]


def test_gate_nodes_empty_tree_is_zero_change():
    assert C.find_gate_nodes({"pages": [{"id": "PageA", "inbound_triggers": []}]}) == {}


def test_logged_out_by_state_signature_intersecting_invite_labels():
    """②：态签名 ∩ 门节点入边文案 —— 屏上写着「入口甲」= 还没登录。"""
    inv = C.gate_invite_labels(TREE_GATED, C.find_gate_nodes(TREE_GATED))
    assert inv == {"入口甲"}
    ann = {"state_signatures": {"tripQ": ["入口甲"], "tripR": ["会员标识"]}}
    assert C.trip_is_logged_out("tripQ", ann, inv) is True
    assert C.trip_is_logged_out("tripR", ann, inv) is False


def test_logged_out_explicit_annotation_wins():
    ann = {"logged_out_trips": ["tripR"], "state_signatures": {"tripQ": ["入口甲"]}}
    assert C.trip_is_logged_out("tripR", ann, {"入口甲"}) is True
    assert C.trip_is_logged_out("tripQ", ann, {"入口甲"}) is False   # 人说了算


def test_logged_out_name_fallback():
    assert C.trip_is_logged_out("trip_1_logged_out", {}, set()) is True
    assert C.trip_is_logged_out("trip_2_logged_in_vip", {}, set()) is False
    assert C.trip_is_logged_out("tripQ", {}, set()) is False          # 判不出=不发探测


# ── 4. 被门拦住的边 + 门的解析 ────────────────────────────────────────────────
def test_gated_edge_and_expected_gate_resolution():
    g = C.find_gate_nodes(TREE_GATED)
    idx = C.find_gated_edges(TREE_GATED, g)
    c = C.gated_edge_for(idx, "PageA", "PageB", "入口甲", "ctlA")
    assert c["kinds"] == ["login_required"] and c["gate"] == "GateX"
    assert C.gated_edge_for(idx, "PageA", "PageC", "入口丙", "ctlC") is None


def test_expected_gate_resolves_across_pages_by_control_identity():
    """真产物实测必要：absent 兄弟边挂在**别的页**上时，只按同页匹会解析不出门。"""
    tree = {"pages": [
        {"id": "GateX", "inbound_triggers": [
            ib("PageZ", label="入口甲", rid="ctlA",
               preconds=[pre("login_conditional", "absent")])]},
        {"id": "PageB", "inbound_triggers": [
            ib("PageA", label="入口甲", rid="ctlA",
               preconds=[pre("login_required", "required")])]},
    ]}
    idx = C.find_gated_edges(tree, C.find_gate_nodes(tree))
    assert C.gated_edge_for(idx, "PageA", "PageB", "入口甲", "ctlA")["gate"] == "GateX"


def test_android_landed_on_gate_is_second_criterion():
    g = {"GateX": ["login_conditional"]}
    assert C.android_gate_blocked(
        edge("PageA", "PageB", landed="GateX"), g) == "GateX"
    assert C.android_gate_blocked(
        edge("PageA", "PageB", landed="PageB"), g) is None      # 落到目标=没被拦
    assert C.android_gate_blocked(edge("PageA", "PageB"), g) is None


def test_android_landed_regex_fallback_only_on_node_name():
    assert C.android_gate_blocked(
        edge("PageA", "PageB", landed="SomethingLoginish"), {},
        C._LOGIN_GATE_FALLBACK_RE) == "SomethingLoginish"


# ── 5. 端到端：真跑一次编译器，逐 disposition 验正反例 ──────────────────────
def _fixture_project(tmp_path, *, gated=True, with_edges=True):
    """最小可编译工程：两个基线目录 + 树 + walk_plan + annotations（全占位串）。"""
    b1 = tmp_path / "shots"; b1.mkdir()
    b2 = tmp_path / "shots1"; b2.mkdir()
    XML = ('<hierarchy><node resource-id="pkg:id/ctl{0}" text="锚{0}" clickable="true"/>'
           '<node text="判别物{0}" clickable="false"/>'
           '<node text="通用条" clickable="false"/></hierarchy>')
    # PageE 刻意**没有独有文本**（两条判别物都是别页的）→ 编译期取不到哨兵 = 无判位依据
    NOSENT = ('<hierarchy><node resource-id="pkg:id/ctlE" clickable="true"/>'
              '<node text="通用条" clickable="false"/></hierarchy>')
    for n in ("PageA", "PageB", "PageC", "PageD", "PageE", "GateX"):
        tag = n[-1]
        x = NOSENT if n == "PageE" else XML.format(tag)
        (b1 / f"{n}.android.xml").write_text(x, encoding="utf-8")
        (b2 / f"{n}.android.xml").write_text(x, encoding="utf-8")
        (b1 / f"{n}.png").write_bytes(b"\x89PNG")
    fc = lambda n: [{"name": f"功能{n}", "anchor": f"pkg:id/ctl{n[-1]}",
                     "expected_android": "占位预期", "android_trusted": True}]
    tree = {"pages": [
        {"id": "PageA", "inbound_triggers": [], "functional_checks": fc("PageA"),
         "blackbox_behavior": {"t": [{"outcome": "skipped_destructive",
                                      "trigger_text": "危险占位"}]}},
        {"id": "PageB", "functional_checks": fc("PageB"), "inbound_triggers": [
            ib("PageA", label="入口甲", rid="ctlA",
               preconds=[pre("login_required", "required")] if gated else [])]},
        {"id": "PageC", "functional_checks": fc("PageC"), "inbound_triggers": [
            ib("PageA", label="入口丙", rid="ctlC")]},
        {"id": "PageD", "functional_checks": fc("PageD"), "inbound_triggers": [
            ib("PageA", label="入口丁", rid="ctlD")]},
        {"id": "PageE", "functional_checks": fc("PageE"), "inbound_triggers": [
            ib("PageA", label="入口戊", rid="ctlE")]},
        {"id": "GateX", "functional_checks": fc("GateX"), "inbound_triggers": [
            ib("PageA", label="入口甲", rid="ctlA",
               preconds=[pre("login_conditional", "absent")] if gated else [])]},
    ]}
    (tmp_path / "tree.json").write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    walk = {"walks": [{"walk_id": "w0", "trip_id": "trip_1_logged_out", "root": "PageA",
                       "steps": [
                           {"step": 1, "action": "tap", "from": "PageA", "to": "PageB",
                            "trigger": "入口甲", "kind": "push"},
                           # 上游压下去的 tap 边：没有配对 back，安卓却 confirmed 过
                           {"step": 2, "action": "skip", "from": "PageA", "to": "PageC",
                            "kind": "scope_exit", "note": "占位理由"},
                           # 无 trigger、树也没 runtime：只能靠安卓真值补身份
                           {"step": 3, "action": "tap", "from": "PageA", "to": "PageD",
                            "trigger": None, "kind": "push"},
                           # 目标页没有独有文本 → 无哨兵 → 救回来也只能降级成弱到达
                           {"step": 4, "action": "skip", "from": "PageA", "to": "PageE",
                            "kind": "scope_exit", "note": "占位理由"},
                           # dialog 浅下沉边：折进源页 reconcile 当场测
                           {"step": 5, "action": "tap", "from": "PageA", "to": "PageC",
                            "trigger": "入口丙", "kind": "dialog"},
                           {"step": 6, "action": "back", "to": "PageA", "kind": "dialog"},
                       ]}]}
    (tmp_path / "walk.json").write_text(json.dumps(walk, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "ann.json").write_text(json.dumps(
        {"extra_blacklist": ["危险占位"]}, ensure_ascii=False), encoding="utf-8")
    edges = [edge("PageA", "PageE", rid="ctlE", text="入口戊"),
             edge("PageA", "PageC", rid="ctlC", text="入口丙"),
             edge("PageA", "PageD", rid="ctlD", text="入口丁"),
             edge("PageA", "PageB", rid="ctlA", trigger="入口甲", landed="GateX")]
    (tmp_path / "edges.json").write_text(json.dumps(edges, ensure_ascii=False), encoding="utf-8")
    return b1, b2


def led_disp(led, to, trig=None):
    for e in led["edges"]:
        if e["to"] == to and (trig is None or e["trigger"] == trig):
            return e["hmos_disposition"]
    return None


def _compile(tmp_path, *, with_edges=True, out="plan.json"):
    cmd = [sys.executable, os.path.join(SCRIPTS, "compile_replay_plan.py"),
           "--walk-plan", str(tmp_path / "walk.json"), "--tree", str(tmp_path / "tree.json"),
           "--baseline-dir", str(tmp_path / "shots"), "--baseline-dir2", str(tmp_path / "shots1"),
           "--annotations", str(tmp_path / "ann.json"), "--out", str(tmp_path / out)]
    if with_edges:
        cmd += ["--android-edges", str(tmp_path / "edges.json")]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return json.load(open(tmp_path / out, encoding="utf-8")), p.stderr


def test_e2e_dispositions_have_positive_and_negative_cases(tmp_path):
    _fixture_project(tmp_path)
    plan, err = _compile(tmp_path)
    steps = {s["step"]: s for s in plan["steps"] if not str(s["step"]).endswith("R")}
    # ① 被门拦住的走序 tap → expect_blocked（正例），且**不改步型**、不加回位步
    assert steps[1]["action"] == "tap" and steps[1]["expect_blocked"] is True
    assert steps[1]["expected_gate"] == "GateX" and steps[1]["probe_only"] is False
    # ② 上游压下去、安卓 confirmed 的边 → 救回来发出 + 配一条探测回位（正例）
    assert steps[2]["action"] == "tap" and steps[2]["probe_only"] is True
    assert steps["2B"]["action"] == "back" and steps["2B"]["probe_return"] is True
    assert steps["2B"]["probe_from"] == "PageC"
    # ③ 无 trigger 的 tap → 从安卓真值补身份（正例）
    assert steps[3]["match"]["rid"] == "ctlD"
    assert steps[3]["match"]["source"] == "android_runtime"
    # 翻译账：每条边一条记录，skipped 必带非空 reason
    led = json.load(open(tmp_path / "translation_ledger_trip_1_logged_out.json", encoding="utf-8"))
    assert led["summary"]["empty_reason_bug"] == 0
    # ④ 目标页无哨兵 → 降级为弱到达（正例），仍然发出去，并照样配回位步
    assert steps[4]["expect"]["arrival_confidence"] == "unanchored"
    assert steps[4]["expect"]["sentinel"] == [] and steps["4B"]["probe_return"] is True
    # ⑤ dialog 边照旧折进 reconcile（反例：本批不碰它）
    assert steps[5]["skip_reason"] == "dialog_moved_to_reconcile"
    assert led_disp(led, "PageE") == "emitted_unanchored"
    assert led_disp(led, "PageC", trig="入口丙") == "folded_to_reconcile"
    assert led["summary"]["android_confirmed"] == 5
    assert set(led["summary"]["android_confirmed_by_disposition"]) == {
        "emitted", "emitted_unanchored", "emitted_expect_blocked", "folded_to_reconcile"}
    assert "安卓 confirmed 的边共 5" in err


def test_e2e_no_android_edges_flag_means_zero_change_on_that_axis(tmp_path):
    """不带 --android-edges：救边/补身份两条通路**一字不变**（老项目零回归）。
    门禁探测是另一条轴（树驱动），本例中它照常生效——两者互不牵连。"""
    _fixture_project(tmp_path)
    with_e, _ = _compile(tmp_path, out="a.json")
    without, _ = _compile(tmp_path, with_edges=False, out="b.json")
    sw = {s["step"]: s for s in without["steps"]}
    assert sw[2]["action"] == "skip" and sw[2]["skip_reason"] == "upstream_scope_exit"
    assert "2B" not in sw                              # 没有救边就没有回位步
    assert sw[3]["action"] == "skip" and sw[3]["skip_reason"] == "no_trigger_captured"
    # 门禁探测两边都在（它不吃 --android-edges）
    assert sw[1]["expect_blocked"] is True
    assert sw[4]["action"] == "skip" and sw[4]["skip_reason"] == "upstream_scope_exit"
    assert {s["step"] for s in with_e["steps"]} - {s["step"] for s in without["steps"]} == {"2B", "4B"}


def test_e2e_no_gate_in_tree_means_no_gate_probe(tmp_path):
    """反例：树里没有门前置条件 → 一条门禁探测都不发。"""
    _fixture_project(tmp_path, gated=False)
    plan, _ = _compile(tmp_path)
    assert plan["login_gate_pages"] == []
    assert not any(s.get("expect_blocked") for s in plan["steps"])


def test_e2e_every_skip_has_non_empty_reason(tmp_path):
    _fixture_project(tmp_path)
    for flag in (True, False):
        plan, _ = _compile(tmp_path, with_edges=flag, out=f"p{flag}.json")
        bad = [s for s in plan["steps"]
               if s.get("action") == "skip" and not s.get("skip_reason")]
        assert bad == [], f"空 skip_reason 是 bug：{bad}"


def test_e2e_destructive_identity_from_android_is_refused(tmp_path):
    """反例：安卓真值补来的身份命中资金词 → **不救**，如实记 destructive_pruned。"""
    _fixture_project(tmp_path)
    edges = json.load(open(tmp_path / "edges.json", encoding="utf-8"))
    for e in edges:
        if e["to"] == "PageC":
            e["control"] = {"rid": "ctl_fast_refund"}       # 占位 rid，命中通用资金 rid 表
    (tmp_path / "edges.json").write_text(json.dumps(edges, ensure_ascii=False), encoding="utf-8")
    plan, _ = _compile(tmp_path)
    s2 = next(s for s in plan["steps"] if s["step"] == 2)
    assert s2["action"] == "skip" and s2["skip_reason"] == "destructive_pruned"
    assert not any(s.get("probe_from") == "PageC" for s in plan["steps"])   # 连回位步都不该有


def test_e2e_android_unreached_yields_to_gate_probe(tmp_path):
    """★`--android-unreached` 的跳过对被门拦住的边**让位**：
    它们"安卓到不了"的原因**就是门**，而门本身正是要验的东西。不让位 = 永远看不见门失守。"""
    _fixture_project(tmp_path)
    (tmp_path / "unreached.json").write_text(json.dumps(
        {"PageB": {"reason": "nav_unreachable", "note": "占位：安卓本趟没够到"},
         "PageD": {"reason": "nav_unreachable", "note": "占位：安卓本趟没够到"}},
        ensure_ascii=False), encoding="utf-8")
    cmd = [sys.executable, os.path.join(SCRIPTS, "compile_replay_plan.py"),
           "--walk-plan", str(tmp_path / "walk.json"), "--tree", str(tmp_path / "tree.json"),
           "--baseline-dir", str(tmp_path / "shots"), "--baseline-dir2", str(tmp_path / "shots1"),
           "--annotations", str(tmp_path / "ann.json"),
           "--android-edges", str(tmp_path / "edges.json"),
           "--android-unreached", str(tmp_path / "unreached.json"),
           "--out", str(tmp_path / "u.json")]
    p = subprocess.run(cmd, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    steps = {s["step"]: s for s in json.load(open(tmp_path / "u.json", encoding="utf-8"))["steps"]}
    assert steps[1]["action"] == "tap" and steps[1]["expect_blocked"] is True   # 门禁边照发
    assert steps[3]["action"] == "skip"                                         # 非门禁边照拦
    assert steps[3]["skip_reason"] == "android_unreached_nav_unreachable"
