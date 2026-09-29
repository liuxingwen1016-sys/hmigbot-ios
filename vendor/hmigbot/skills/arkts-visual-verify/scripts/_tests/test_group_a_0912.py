#!/usr/bin/env python3
"""A 组（2026-09-12，t2a 首跑归因后用户拍板：安卓遍历已有的逻辑/字段照搬到鸿蒙侧）。
  A1 安卓真值按趟：别趟确认不救回、走序 tap 标 trip_state_unverified、归因 edge_confirmed_only_in_other_trip
  A2 type 步：view_id/text 透传 + 安卓 hint 身份；执行器 rid→hint→类型→子 tab 切换四级定位
  A3 renav 步：已在位免动作 / 重导航 / 失败交接
  A5 排除表子串互认（「切换到X」）；plan.subtab_labels
  A7 web_url_from_dump；A8 破坏性遭遇账跨进程聚合
夹具全占位串；零设备。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import replay_exec as R  # noqa: E402
from test_replay_gate_probe_and_unanchored import SCREENS, FakeDrv, run, screen, _node, ctrl  # noqa: E402
from test_compile_android_edges_and_gate import _fixture_project, _compile, edge, ib  # noqa: E402

COLD = {"step": 1, "action": "coldstart", "to": "PageA"}


def _tap(step, frm, to, prim, rid, kind="push", **extra):
    st = {"step": step, "action": "tap", "from": frm, "to": to, "match": {"primary": prim, "rid": rid, "source": "runtime"},
          "wait_budget_s": 0.1, "safety": "normal", "expect": {"kind": kind, "sentinel": [f"判别物{to[-1]}"]}}
    st.update(extra); return st


def _row(rows, step):
    return next(x for x in rows if str(x.get("step")) == str(step))


# ── 纯函数 ──────────────────────────────────────────────────────────────────
def _area(hint="占位提示", y=1400):
    return {"attributes": {"type": "TextArea", "bounds": "[35,%d][1286,%d]" % (y, y + 170), "hint": hint, "text": "", "clickable": "true"}, "children": []}


SCREENS["PageA_input"] = screen(_node("Text", (100, 200, 1200, 300), text="判别物A"), _node("Text", (100, 900, 400, 1000), text="甲页签"), _area())
SCREENS["PageA_tabdoc"] = screen(_node("Text", (100, 200, 1200, 300), text="判别物A"),
                                 {"attributes": {"type": "Row", "bounds": "[100,900][1200,1000]", "clickable": "true"}, "children": [
                                     _node("Text", (100, 900, 400, 1000), text="甲页签"), _node("Text", (700, 900, 1000, 1000), text="乙页签")]},
                                 _node("Text", (100, 1300, 1200, 1400), text="导入区占位"))


def test_find_input_target_prefers_rid_then_android_hint_then_type():
    t = SCREENS["PageA_input"]
    assert R.find_input_target(t, "et_x", "占位提示", "TextInput")[1] == "android_hint"    # hint 优先于错的类型
    assert R.find_input_target(t, None, None, None)[1] == "type_any:TextArea"
    assert R.find_input_target(SCREENS["PageA"], "et_x", "占位提示", None) == (None, None)


def test_subtab_candidates_declared_first_and_tab_bar_excluded():
    t = json.dumps({"attributes": {"bounds": "[0,0][1320,2856]"}, "children": [
        {"attributes": {"type": "Row", "bounds": "[0,2548][1320,2856]"}, "children": [
            {"attributes": {"type": "Column", "selected": "true", "clickable": "true", "bounds": "[0,2548][330,2856]"}, "children": [_node("Text", (0, 2700, 330, 2750), text="首页占位")]},
            {"attributes": {"type": "Column", "selected": "false", "clickable": "true", "bounds": "[330,2548][660,2856]"}, "children": [_node("Text", (330, 2700, 660, 2750), text="模版占位")]}]},
        _node("Text", (100, 900, 400, 1000), text="甲页签")]})
    assert [lab for _, lab in R.find_subtab_candidates_hmos(t)] == ["模版占位"]                     # 安卓判据：未选中的可点兄弟
    assert R.find_subtab_candidates_hmos(t, exclude_labels={"模版占位"}) == []                         # 页级 tab 栏排掉
    assert [lab for _, lab in R.find_subtab_candidates_hmos(t, exclude_labels={"模版占位"}, declared_labels=["甲页签"])] == ["甲页签"]


def test_web_url_from_dump():
    t = json.dumps({"attributes": {"bounds": "[0,0][10,10]"}, "children": [{"attributes": {"type": "Web", "text": "http://127.0.0.1:8899/page/x.html"}, "children": []}]})
    assert R.web_url_from_dump(t) == "http://127.0.0.1:8899/page/x.html"
    assert R.web_url_from_dump(SCREENS["PageA"]) is None


# ── A2 type 步 ───────────────────────────────────────────────────────────────
def _type(step, frm, vid="et_x", hint="占位提示", text="Sample text"):
    return {"step": step, "action": "type", "from": frm, "to": frm, "view_id": vid, "text": text,
            "match": {"primary": "", "rid": vid, "source": "walk_type", "android_dump_text": hint, "text_identity_source": "android_dump_rid"}}


def test_type_step_locates_field_by_android_hint(tmp_path):
    rows, man, code = run(tmp_path, [_type(1, "PageA")], FakeDrv("PageA_input", {}))
    r = _row(rows, 1)
    assert r["verdict"] in ("TYPED", "TYPE_UNVERIFIED") and r["how"] == "android_hint" and r["text"] == "Sample text"
    assert not man["escalations"]


def test_type_step_switches_declared_subtab_when_field_hidden(tmp_path):
    drv = FakeDrv("PageA_tabdoc", {"PageA_tabdoc": "PageA_input"})
    rows, man, code = run(tmp_path, [_type(1, "PageA")], drv, plan_extra={"subtab_labels": {"PageA": ["甲页签", "乙页签"]}})
    r = _row(rows, 1)
    assert r["verdict"] in ("TYPED", "TYPE_UNVERIFIED") and r["subtab_switched"] == "甲页签" and r["how"] == "android_hint"


def test_type_target_missing_is_recorded_not_handed_off(tmp_path):
    rows, man, code = run(tmp_path, [_type(1, "PageA"), _tap(2, "PageA", "PageC", "入口丙", "ctlC")], FakeDrv("PageA", {"PageA": "PageC"}))
    assert _row(rows, 1)["verdict"] == "TYPE_TARGET_MISSING"
    assert man["escalations"][0]["blame"] == "input_target_missing" and man["escalations"][0]["product_defect"] is None
    assert _row(rows, 2)["verdict"].startswith("ARRIVED")                       # 没交接，后面照走


# ── A3 renav 步 ──────────────────────────────────────────────────────────────
def test_renav_noop_when_already_there_and_ok_via_recovery(tmp_path):
    steps = [COLD, _tap(2, "PageA", "PageC", "入口丙", "ctlC"),
             {"step": 3, "action": "renav", "from": "PageC", "to": "PageC", "kind": "push"},
             {"step": 4, "action": "renav", "from": "PageC", "to": "PageA", "kind": "push"}]
    drv = FakeDrv("PageA", {"PageA": "PageC"}, back_to={"PageC": "PageA"})
    rows, man, code = run(tmp_path, steps, drv)
    assert _row(rows, 3)["verdict"] == "RENAV_NOOP"
    assert _row(rows, 4)["verdict"] == "RENAV_OK" and drv.cur == "PageA"


def test_renav_failed_hands_off(tmp_path):
    steps = [COLD, _tap(2, "PageA", "PageC", "入口丙", "ctlC"),
             {"step": 3, "action": "renav", "from": "PageC", "to": "PageB", "kind": "push"}]
    drv = FakeDrv("PageA", {"PageA": "PageC"}, back_to={"PageC": "PageC"})
    rows, man, code = run(tmp_path, steps, drv)
    assert _row(rows, 3)["verdict"] == "RENAV_FAILED" and code == 32
    assert man["escalations"][-1]["blame"] == "position_lost_on_renav"


# ── A1 归因：别趟确认 ─────────────────────────────────────────────────────────
def test_abandon_on_other_trip_edge_is_not_control_missing(tmp_path):
    st = _tap(1, "PageA", "PageB", "无此控件占位", "ctlZ", runtime={"device_state": "trip_9"})
    rows, man, code = run(tmp_path, [st], FakeDrv("PageA", {}))
    e = man["escalations"][0]
    assert e["blame"] == "edge_confirmed_only_in_other_trip" and e["product_defect"] is None and e["edge_device_state"] == "trip_9"


# ── A8 遭遇账跨进程聚合 ───────────────────────────────────────────────────────
def test_encountered_destructive_aggregated_from_manifest_on_resume(tmp_path):
    rows1, man1, _ = run(tmp_path, [COLD], FakeDrv("PageA", {}))
    mp = tmp_path / "out" / "capture_manifest.json"
    m = json.load(open(mp, encoding="utf-8"))
    m["per_page"].setdefault("PageA", {"behavior_observations": [], "observation_notes": []})
    m["per_page"]["PageA"].setdefault("behavior_observations", []).append(
        {"trigger_text": "危险占位", "rid": "ctlDanger", "outcome": "encountered_destructive", "capture_status": "deferred_trip_end"})
    mp.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    rows2, man2, _ = run(tmp_path, [COLD, {"step": 2, "action": "skip", "from": "PageA", "to": "PageB", "skip_reason": "占位"}],
                         FakeDrv("PageA", {}), argv_extra=("--resume-from", "2"))
    f = json.load(open(tmp_path / "out" / "encountered_destructive.json", encoding="utf-8"))
    assert f["total"] == 1 and f["items"][0]["rid"] == "ctlDanger" and f["items"][0]["from_manifest"] is True


# ── 编译器：按趟 / type 透传 / 排除表子串 ─────────────────────────────────────
def _extend_a(tmp_path):
    tree = json.load(open(tmp_path / "tree.json", encoding="utf-8"))
    for pg in tree["pages"]:
        if pg["id"] == "PageA":
            pg["functional_checks"] += [{"name": "切换到甲页签", "anchor": "pkg:id/ctlTab", "expected_android": "占位", "android_trusted": True},
                                        {"name": "甲页签选中态", "anchor": "pkg:id/ctlTabSel", "expected_android": "占位", "android_trusted": True}]
    (tmp_path / "tree.json").write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    walk = json.load(open(tmp_path / "walk.json", encoding="utf-8"))
    walk["walks"][0]["steps"] += [
        {"step": 20, "action": "tap", "from": "PageA", "to": "PageC", "trigger": "入口丙", "kind": "push"},          # 安卓只在别趟确认
        {"step": 21, "action": "type", "from": "PageA", "to": "PageA", "view_id": "et_a", "text": "Sample", "precondition_kind": "state_required"}]
    (tmp_path / "walk.json").write_text(json.dumps(walk, ensure_ascii=False), encoding="utf-8")
    edges = json.load(open(tmp_path / "edges.json", encoding="utf-8"))
    edges = [e for e in edges if not (e["from"] == "PageA" and e["to"] == "PageC")]
    edges.append(edge("PageA", "PageC", rid="ctlC", text="入口丙", device_state="trip_2_logged_in_vip"))   # 别趟确认
    (tmp_path / "edges.json").write_text(json.dumps(edges, ensure_ascii=False), encoding="utf-8")
    ann = json.load(open(tmp_path / "ann.json", encoding="utf-8")); ann["reconcile_exclude"] = {"PageA": ["甲页签"]}
    (tmp_path / "ann.json").write_text(json.dumps(ann, ensure_ascii=False), encoding="utf-8")
    for d in ("shots", "shots1"):
        p = tmp_path / d / "PageA.android.xml"
        p.write_text(p.read_text(encoding="utf-8").replace("</hierarchy>", '<node resource-id="pkg:id/et_a" text="占位提示" clickable="true"/></hierarchy>'), encoding="utf-8")


def test_compile_other_trip_confirmation_not_rescued_and_marked(tmp_path):
    _fixture_project(tmp_path)
    _extend_a(tmp_path)
    plan, err = _compile(tmp_path)
    steps = {str(s["step"]): s for s in plan["steps"]}
    assert steps["2"]["action"] == "skip"                                       # 上游 skip、安卓只在别趟确认 → 不救回
    assert "2B" not in steps
    assert steps["20"]["action"] == "tap" and steps["20"]["trip_state_unverified"] is True \
        and steps["20"]["runtime"]["device_state"] == "trip_2_logged_in_vip"      # 走序 tap 照发但标注
    t21 = steps["21"]
    assert t21["action"] == "type" and t21["view_id"] == "et_a" and t21["text"] == "Sample"
    assert t21["match"]["android_dump_text"] == "占位提示" and t21["match"]["source"] == "walk_type"
    rec = [s for s in plan["steps"] if s["action"] == "reconcile" and s.get("from") == "PageA"][0]
    names = {e["trigger_text"] for e in rec["elements"]}
    assert "切换到甲页签" not in names and "甲页签选中态" not in names               # 子串互认
    assert plan["subtab_labels"] == {"PageA": ["甲页签"]}
