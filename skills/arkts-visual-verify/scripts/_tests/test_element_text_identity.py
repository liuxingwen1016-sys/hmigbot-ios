#!/usr/bin/env python3
"""T-4（2026-09-11 零介入复跑实证）：reconcile 元素的屏上文本身份从**安卓 dump** 取，树名只当兜底。

病：元素 `trigger_text` 是树/LLM 的描述名（「场景选择标题」），屏上不会有；它的 rid 在安卓 dump 里就带着真实
文案，鸿蒙屏上同一句话原样在。执行器拿描述名找不到就盖 `control_missing_in_hmos`：一页 7/7 假 P0。
两条铁律：① 身份从安卓真值取（与边同一原则）；② 计划里**没有任何**屏上文本身份的元素，找不到≠缺失
（无证据≠反证），改记 unverifiable_no_screen_identity。
夹具全占位串；rid 驼峰/下划线互认是 ViewBinding 通例，不是 app 常量。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compile_replay_plan as C  # noqa: E402
import replay_exec as R          # noqa: E402
import test_compile_android_edges_and_gate as G  # noqa: E402


# ── 编译侧 ──────────────────────────────────────────────────────────────────
def test_rid_variants_normalize_snake_and_camel():
    assert C._rid_variants("pkg:id/cb_one") == C._rid_variants("cbOne") == {"cbone"}
    assert C._rid_variants("com.x.R.id.tv_title") == {"tvtitle"}
    assert C._rid_variants(None) == set()


def test_rid_texts_reads_android_dump(tmp_path):
    (tmp_path / "PageA.android.xml").write_text(
        '<hierarchy><node resource-id="pkg:id/tv_title" text="占位标题甲" clickable="false"/>'
        '<node resource-id="pkg:id/cb_one" text="&#127979; 占位项一" clickable="true"/>'
        '<node resource-id="pkg:id/box" text="" clickable="false"/>'
        '<node text="无id文案" clickable="false"/></hierarchy>', encoding="utf-8")
    rt = C.rid_texts(str(tmp_path))
    rmap, texts = rt["PageA"]
    assert rmap == {"tvtitle": "占位标题甲", "cbone": "🏫 占位项一"}        # 实体已 unescape；无文案的容器不入
    assert texts == {"占位标题甲", "🏫 占位项一", "无id文案"}


def test_attach_element_identity_sources_and_label_order():
    rec = {"PageA": {"elements": [
        {"trigger_text": "描述甲", "rid": "tvTitle"},                       # 驼峰 rid ↔ 安卓 dump 下划线
        {"trigger_text": "无id文案", "rid": None},                          # 树名本身就是屏上文案
        {"trigger_text": "描述丙", "rid": "iv_icon"},                       # 纯图标：无身份
        {"trigger_text": "描述丁", "rid": "tv_dyn"},                        # 动态文案不当身份
        {"trigger_text": "描述戊", "rid": "x", "match_labels": ["屏名戊", "描述戊"]},   # hprof 已给屏名
    ]}}
    rt = {"PageA": ({"tvtitle": "占位标题甲", "tvdyn": "用户123"}, {"占位标题甲", "无id文案", "用户123"})}
    st = C.attach_element_identity(rec, rt, {}, dynamic={"用户123"})
    els = rec["PageA"]["elements"]
    assert els[0]["match_labels"] == ["占位标题甲", "描述甲"] and els[0]["text_identity_source"] == "android_dump_rid"
    assert els[0]["android_dump_text"] == "占位标题甲"
    assert els[1]["text_identity_source"] == "android_dump_name" and "match_labels" not in els[1]
    assert els[2]["text_identity_source"] is None
    assert els[3]["text_identity_source"] is None and "match_labels" not in els[3]        # 动态文案没被塞进标签
    assert els[4]["text_identity_source"] == "hmos_profile" and els[4]["match_labels"][0] == "屏名戊"
    assert st == {"android_dump_rid": 1, "android_dump_name": 1, "hmos_profile": 1, "none": 2}


def test_e2e_compile_attaches_android_dump_text_to_reconcile_elements(tmp_path):
    G._fixture_project(tmp_path)
    tree = json.load(open(tmp_path / "tree.json", encoding="utf-8"))
    for p in tree["pages"]:
        if p["id"] == "PageD":          # PageD 的 reconcile 有元素（PageA 的被无锚点规则整体延后）
            p["functional_checks"].append({"name": "描述性功能名", "expected_android": "占位预期", "android_trusted": True,
                                           "android_anchor": {"raw_identifier": "ctlD"}})    # 安卓 dump 里 ctlD 的文案是「锚D」
    (tmp_path / "tree.json").write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    plan, err = G._compile(tmp_path)
    rs = [s for s in plan["steps"] if s["action"] == "reconcile" and s.get("node") == "PageD"]
    assert rs, "PageD 应有 reconcile 步"
    els = {e.get("trigger_text"): e for e in rs[0]["elements"]}
    assert els["描述性功能名"]["match_labels"][0] == "锚D" and els["描述性功能名"]["text_identity_source"] == "android_dump_rid"
    assert els["功能PageD"]["text_identity_source"] is None                 # 无 rid、树名不在屏上 → 无身份
    assert "元素文本身份" in err


# ── 执行侧 ──────────────────────────────────────────────────────────────────
def node(type_, bounds, text="", clickable=False):
    a = {"type": type_, "bounds": "[%d,%d][%d,%d]" % bounds, "clickable": "true" if clickable else "false"}
    if text:
        a["text"] = text
    return {"attributes": a, "children": []}


def screen(*children):
    return json.dumps({"attributes": {"bounds": "[0,0][1320,2856]"}, "children": list(children)}, ensure_ascii=False)


PAGE_A = screen(node("Text", (0, 400, 900, 500), text="占位首页标题"),
                node("Text", (0, 600, 900, 700), text="占位真文案甲"))


class StaticDev:
    def __init__(self, scr):
        self.scr = scr; self.taps = []; self.backs = 0; self.shells = []; self.shots = []

    def dump_layout(self, path=None):
        return self.scr

    def tap(self, x, y):
        self.taps.append((x, y))

    def swipe(self, *a, **k):
        pass

    def back(self):
        self.backs += 1

    def shell(self, *a, **k):
        self.shells.append(a); return ""

    def screencap(self, p):
        open(p, "wb").write(b"\xff\xd8fake"); self.shots.append(p); return p


def _plan(elements):
    return {"app": {"bundle": "com.x"}, "safety": {"blacklist": []},
            "roots": [{"node": "PageA", "sentinel": ["占位首页标题"]}],
            "coverage_targets": ["PageA"], "node_sentinels": {"PageA": ["占位首页标题"]},
            "steps": [{"step": 1, "action": "verify", "to": "PageA"},
                      {"step": "1R", "action": "reconcile", "node": "PageA", "from": "PageA", "to": "PageA",
                       "anchored": True, "elements": elements}]}


def run_main(tmp_path, monkeypatch, plan, dev):
    planp = tmp_path / "replay_plan_hmos.json"
    planp.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "trip_1"
    monkeypatch.setattr(R, "DeviceAdapter", lambda *a, **k: dev)
    monkeypatch.setattr(R.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["replay_exec.py", "--plan", str(planp), "--serial", "fake",
                                      "--bundle", "com.x", "--ability", "Entry", "--out-dir", str(out)])
    try:
        R.main()
    except SystemExit:
        pass
    return json.load(open(out / "capture_manifest.json", encoding="utf-8"))


def test_observe_only_uses_android_dump_label_and_no_identity_is_undecidable(tmp_path, monkeypatch):
    els = [
        {"trigger_text": "描述甲", "rid": "tv_a", "observe_only": True, "oracle_source": "functional_checks",
         "match_labels": ["占位真文案甲", "描述甲"], "text_identity_source": "android_dump_rid"},        # 安卓文案在屏上 → rendered
        {"trigger_text": "描述乙", "rid": "iv_b", "observe_only": True, "oracle_source": "functional_checks",
         "text_identity_source": None},                                                                # 无身份 → 不可判，不是 P0
        {"trigger_text": "描述丙", "rid": "tv_c", "observe_only": True, "oracle_source": "functional_checks",
         "match_labels": ["占位真文案丙", "描述丙"], "text_identity_source": "android_dump_rid"},        # 有身份且屏上没有 → 真缺失
    ]
    man = run_main(tmp_path, monkeypatch, _plan(els), StaticDev(PAGE_A))
    obs = {o["trigger_text"]: o for o in man["per_page"]["PageA"]["behavior_observations"]}
    assert obs["描述甲"]["outcome"] == "rendered" and obs["描述甲"]["matched_label"] == "占位真文案甲"
    assert obs["描述乙"]["outcome"] == "unverifiable_no_screen_identity" and obs["描述乙"]["blame_hint"] == "no_screen_identity"
    assert obs["描述丙"]["outcome"] == "not_found" and obs["描述丙"]["blame_hint"] == "control_missing_in_hmos"
    assert obs["描述丙"]["text_identity_source"] == "android_dump_rid"


def test_judge_input_wiring_for_no_screen_identity():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build_judge_input.py"),
               encoding="utf-8").read()
    assert 'o.get("blame_hint") == "no_screen_identity"' in src            # 不进 P0 改判循环
    assert '_norm(n.get("resource-id")) == _norm(rid)' in src              # cb_one ↔ cbOne 互认
