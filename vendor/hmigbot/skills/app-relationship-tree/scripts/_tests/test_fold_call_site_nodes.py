#!/usr/bin/env python3
"""Phase 1.7 方法现场节点归位（fold_call_site_nodes.py）——合成夹具，零 app 常量。

病：`Outer$showXxx` 这种**方法现场**被当成独立的屏入树，和真弹窗类节点重复；反哺契约不许删节点、
tree_dup 只查边，没有回路送回树侧。规则见脚本 docstring。夹具里页名/类名/文案全是占位串。
"""
import copy
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import fold_call_site_nodes as F  # noqa: E402

PAGE_SRC = '''
package x.y

class PageA : Activity() {
    inner class Inner { }

    fun other() {
        if (flag) foo()
        else showBeta()
    }

    private fun showAlpha() {
        val d = AlphaDialog()
        d.show(fm)
    }

    private fun showBeta() {
        val d = TipsDialog.newInstance(
            title = "标题甲",
            content = "正文乙",
            sure = R.string.ok_word
        )
        d.show(fm)
    }

    private fun showGamma() {
        // AlphaDialog()  注释里的构造不算
        requestPermissions(arrayOf("x"), 1)
    }

    private fun showDelta() {
        EpsDialog().show(fm)
    }

    private fun showDead() {
        AlphaDialog().show(fm)
    }

    private fun showBoth() {
        AlphaDialog().show(fm)
        TipsDialog.newInstance().show(fm)
    }

    private fun showSetter() {
        track("evt_setter_1")
        val d = TipsDialog()
        d.setTitle("标题丙")
        d.show(fm)
    }

    private fun showApply() {
        TipsDialog.create().apply {
            content = getString(R.string.tip_c)
        }.show(fm)
    }

    private fun showOpen() {
        TipsDialog.open(this, payload)
    }

    private fun showPage() {
        track("evt_page")
        PageJ.start(this)
    }

    private fun showEvt() {
        AlphaDialog.newInstance(bean).apply {
            setConfirm { track("evt_in_lambda") }
            EventUpload.popupShowEvent("evt_other_receiver", name)
            show(fm)
        }
    }

    private fun showHostLay() { AlphaDialog().show(fm) }
    private fun showThird() { AlphaDialog().show(fm) }
    private fun showCode() {
        val v = inflate(R.layout.code_dlg)
        AlertDialog.Builder(this).setView(v).show()
    }
}
'''
JAVA_SRC = '''
package x.y;
public class PageJ extends Activity {
    void run() { if (a) showJ(); else showJ(); }
    private void showJ() {
        new AlphaDialog().show();
    }
}
'''


def _rec(rid, typ="Dialog", **kw):
    r = {"id": rid, "type": typ, "fq_class": rid, "android_file": None, "layout_file": None, "label": rid,
         "contains": [], "shows_dialogs": [], "components": [], "navigation": {"inbound": [], "outbound": []},
         "reach_paths": [], "inbound_triggers": [], "walkability": {"status": "walkable"}}
    r.update(kw)
    return r


def _tree():
    lf = {"file": "res/layout/dlg_alpha.xml", "view_ids": ["btn_a"], "static_texts": ["占位A"], "includes": []}
    tips_lf = {"file": "res/layout/dlg_tips.xml", "view_ids": ["tv_title", "tv_content"], "static_texts": [], "includes": []}
    return {
        "pages": [_rec("PageA", "Activity", android_file="PageA.kt", layout_file="res/layout/act_a.xml",
                       navigation={"inbound": [], "outbound": [{"from": "PageA", "to": "PageA$showAlpha", "trigger": "click"}]},
                       shows_dialogs=["PageA$showAlpha", "AlphaDialog"]),
                  _rec("PageJ", "Activity", android_file="PageJ.java")],
        "fragments": [],
        "dialogs": [
            _rec("AlphaDialog", layout_file="res/layout/dlg_alpha.xml", layout_facts=lf,
                 inbound_triggers=[{"from_page": "PageA", "trigger_view_id": None, "trigger_label": None, "trigger_kind": "auto"}]),
            _rec("TipsDialog", layout_file="res/layout/dlg_tips.xml", layout_facts=tips_lf),
            _rec("PageA$showAlpha", android_file="PageA.kt",
                 inbound_triggers=[{"from_page": "PageA", "trigger_view_id": "btn_gate", "trigger_label": None,
                                    "trigger_kind": "auto", "wait_hint": "until_text:占位A"}],
                 reach_paths=[{"display": "PageA > showAlpha"}],
                 screenshots={"trip_x": {"path": "shots/PageA$showAlpha.png"}},
                 navigation={"inbound": [{"from": "PageA", "trigger": "click"}], "outbound": []}),
            _rec("PageA$showBeta", android_file="PageA.kt"),
            _rec("PageA$showGamma", android_file="PageA.kt"),
            _rec("PageA$showDelta", android_file="PageA.kt"),
            _rec("PageA$Inner", android_file="PageA.kt"),
            _rec("PageA$showNone", android_file="PageA.kt"),
            _rec("PageA$showDead", android_file="PageA.kt", walkability={"status": "dead"},
                 inbound_triggers=[{"from_page": "PageA", "trigger_view_id": "ctl_dead", "trigger_label": "死键"}]),
            _rec("PageA$showBoth", android_file="PageA.kt"),
            _rec("PageJ$showJ", android_file="PageJ.java"),
            _rec("PageA$showSetter", android_file="PageA.kt"),
            _rec("PageA$showApply", android_file="PageA.kt"),
            _rec("PageA$showOpen", android_file="PageA.kt"),
            _rec("PageA$showPage", android_file="PageA.kt"),
            _rec("PageA$showEvt", android_file="PageA.kt"),
            _rec("PageA$showHostLay", android_file="PageA.kt", layout_file="res/layout/act_a.xml"),      # 915 版：挂了宿主布局
            _rec("PageA$showThird", android_file="PageA.kt", layout_file="res/layout/other.xml"),
            _rec("PageA$showCode", android_file="PageA.kt", layout_file="res/layout/code_dlg.xml"),
        ],
        "features": [{"id": "f1", "screens": ["PageA", "PageA$showAlpha", "AlphaDialog"]}],
        "flow_graph": {"nodes": [{"id": "PageA"}, {"id": "PageA$showAlpha"}, {"id": "AlphaDialog"}, {"id": "PageA$showDead"}],
                       "edges": [{"from": "PageA", "to": "PageA$showAlpha", "trigger": "click"},
                                 {"from": "PageA", "to": "AlphaDialog", "trigger": "click"},
                                 {"from": "PageA", "to": "PageA$showDead", "trigger": "click"}]},
    }


@pytest.fixture
def root(tmp_path):
    (tmp_path / "PageA.kt").write_text(PAGE_SRC, encoding="utf-8")
    (tmp_path / "PageJ.java").write_text(JAVA_SRC, encoding="utf-8")
    (tmp_path / "AlphaDialog.kt").write_text("package x.y\nclass AlphaDialog : Dialog()\n", encoding="utf-8")
    (tmp_path / "TipsDialog.kt").write_text("package x.y\nclass TipsDialog : DialogFragment()\n", encoding="utf-8")
    return tmp_path


def _ids(t):
    return {r["id"] for r in t["pages"] + t["fragments"] + t["dialogs"]}


def _by(t):
    return {r["id"]: r for r in t["pages"] + t["fragments"] + t["dialogs"]}


# ── 声明定位（真树踩过：换行后的调用被当声明）────────────────────────────────
def test_method_body_finds_declaration_not_call():
    src = F.blank_comments(PAGE_SRC)
    body, line = F.method_body(src, "showBeta")
    assert body and "TipsDialog" in body
    assert "else showBeta()" not in body            # 拿到的是声明体，不是 other() 里的调用
    assert line == PAGE_SRC[:PAGE_SRC.index("private fun showBeta")].count("\n") + 1


def test_method_body_java_requires_brace_after_paren():
    src = F.blank_comments(JAVA_SRC)
    body, _ = F.method_body(src, "showJ")
    assert body and "new AlphaDialog" in body       # `else showJ();` 这条调用没被当成声明


def test_method_body_kotlin_expression_and_return_type(tmp_path):
    src = "class K {\n  fun a(): Int = X()\n  fun b(): Unit {\n    Y()\n  }\n}\n"
    assert "X()" in F.method_body(src, "a")[0]
    assert "Y()" in F.method_body(src, "b")[0]


# ── 分类 ────────────────────────────────────────────────────────────────────
def test_classify_kinds(root):
    t = _tree(); by = _by(t)
    c2f = F.build_class_to_file_index(root)
    k = lambda rid: F.classify(by[rid], by, root, c2f)
    assert k("PageA$showAlpha")["kind"] == "pure_duplicate" and k("PageA$showAlpha")["target"] == "AlphaDialog"
    b = k("PageA$showBeta")
    assert b["kind"] == "shared_dialog_state" and b["target"] == "TipsDialog"
    assert b["text_literals"] == ["标题甲", "正文乙"] and b["text_refs"] == ["R.string.ok_word"]
    assert k("PageA$showGamma")["kind"] == "system_ui"          # 注释里的 AlphaDialog() 不算
    assert k("PageA$showDelta")["kind"] == "class_not_in_tree" and k("PageA$showDelta")["resolved_class"] == "EpsDialog"
    assert k("PageA$Inner")["kind"] == "inner_class"
    assert k("PageA$showNone")["kind"] == "method_not_found"
    assert k("PageA$showBoth")["kind"] == "ambiguous_multi_target"
    assert k("PageJ$showJ")["kind"] == "pure_duplicate"


def test_classify_generality_rules(root):
    """通用性三条（用户追问后补）：文案经 setter/apply 流入实例也算状态；埋点字面量不算；
    工厂名不设清单（`X.open(`）；页面类的静态调用绝不成目标（否则影子会并进 Activity）。"""
    t = _tree(); by = _by(t)
    c2f = F.build_class_to_file_index(root)
    k = lambda rid: F.classify(by[rid], by, root, c2f)
    st = k("PageA$showSetter")
    assert st["kind"] == "shared_dialog_state" and st["text_literals"] == ["标题丙"]     # evt_setter_1 没被算进去
    ap = k("PageA$showApply")
    assert ap["kind"] == "shared_dialog_state" and ap["text_refs"] == ["R.string.tip_c", "getString("] or \
        (ap["kind"] == "shared_dialog_state" and "R.string.tip_c" in ap["text_refs"])
    assert k("PageA$showOpen")["kind"] == "pure_duplicate" and k("PageA$showOpen")["target"] == "TipsDialog"
    pg = k("PageA$showPage")
    assert pg["kind"] != "pure_duplicate" and pg.get("target") is None                    # PageJ 是页面，不是真身


def test_layout_three_way_rule(root):
    """布局不是"真面"判据（915 版 toolkit 给方法现场挂宿主布局）：等于宿主 → 影子；第三个且有真身 → 冲突 uncertain；
    有自己布局且无弹窗真身 → 代码构建的弹窗，原样留、不标 uncertain。"""
    t = _tree(); by = _by(t); c2f = F.build_class_to_file_index(root)
    k = lambda rid: F.classify(by[rid], by, root, c2f)
    assert k("PageA$showHostLay")["kind"] == "pure_duplicate"                     # 宿主布局 ≠ 自己的面
    assert k("PageA$showThird")["kind"] == "layout_conflict" and k("PageA$showThird")["target"] == "AlphaDialog"
    assert k("PageA$showCode")["kind"] == "code_built_dialog_own_layout"
    F.fold(t, root); by = _by(t)
    assert "PageA$showHostLay" not in by and "PageA$showThird" in by and by["PageA$showThird"]["uncertain"] is True
    assert "PageA$showCode" in by and by["PageA$showCode"].get("uncertain") is not True


def test_scope_block_ignores_other_receivers_and_lambdas(root):
    """apply 块里对别的接收者的调用 / 嵌套 lambda 里的字面量（埋点事件名）不算文案（真树实测 vippop_3 混入）。"""
    t = _tree(); by = _by(t)
    assert F.classify(by["PageA$showEvt"], by, root, F.build_class_to_file_index(root))["kind"] == "pure_duplicate"


# ── 归位 ────────────────────────────────────────────────────────────────────
def test_pure_duplicate_folded_into_class_node_and_refs_remapped(root):
    t = _tree(); st = F.fold(t, root)
    assert "PageA$showAlpha" not in _ids(t)
    X = _by(t)["AlphaDialog"]
    assert [c["node"] for c in X["call_sites"] if not c.get("dead")] == \
        ["PageA$showAlpha", "PageJ$showJ", "PageA$showEvt", "PageA$showHostLay"]
    # auto 触发同起点算一条：原有的一条被补上 wait_hint，不复制第二条
    autos = [e for e in X["inbound_triggers"] if e.get("trigger_kind") == "auto"]
    assert len(autos) == 1 and autos[0]["wait_hint"] == "until_text:占位A"
    assert autos[0].get("trigger_view_id") is None        # ★影子那条带的 btn_gate 绝不灌进 auto 触发（A/B 实跑抓出）
    assert X["screenshots"]["trip_x"]["path"].endswith("PageA$showAlpha.png")     # 事实搬过来
    assert X["reach_paths"] == [{"display": "PageA > showAlpha"}]
    # 全树引用改指真节点并去重
    A = _by(t)["PageA"]
    assert A["shows_dialogs"] == ["AlphaDialog"]
    assert [e["to"] for e in A["navigation"]["outbound"]] == ["AlphaDialog"]
    assert t["features"][0]["screens"] == ["PageA", "AlphaDialog"]
    assert [n["id"] for n in t["flow_graph"]["nodes"]] == ["PageA", "AlphaDialog"]
    assert [(e["from"], e["to"]) for e in t["flow_graph"]["edges"]] == [("PageA", "AlphaDialog")]
    assert st["folded"] == 5 and st["by_kind"]["pure_duplicate"] == 6      # showAlpha/showJ/showOpen/showEvt/showHostLay + showDead(dead)
    assert json.dumps(t, ensure_ascii=False).count('"PageA$showAlpha"') == 1          # 只剩 call_sites 留痕


def test_dead_call_site_deleted_without_merging_edges(root):
    t = _tree(); F.fold(t, root)
    assert "PageA$showDead" not in _ids(t)
    X = _by(t)["AlphaDialog"]
    assert not any(e.get("trigger_view_id") == "ctl_dead" for e in X["inbound_triggers"])   # 死边不复活
    assert any(c["node"] == "PageA$showDead" and c["dead"] for c in X["call_sites"])
    assert not any(e["to"] == "PageA$showDead" for e in t["flow_graph"]["edges"])
    assert all(n["id"] != "PageA$showDead" for n in t["flow_graph"]["nodes"])


def test_shared_dialog_state_kept_and_enriched(root):
    t = _tree(); F.fold(t, root)
    s = _by(t)["PageA$showBeta"]
    assert s["variant_of"] == "TipsDialog" and s["construction_mode"] == "shared_dialog_state"
    assert s["layout_file"] == "res/layout/dlg_tips.xml"                       # 继承真节点布局
    assert s["layout_facts"]["static_texts"] == ["标题甲", "正文乙"]            # 调用点字面量=自己的文案
    assert s["call_site_texts"] == ["标题甲", "正文乙"] and s["call_site_text_refs"] == ["R.string.ok_word"]   # 2.4 重算后靠它并回
    assert s["layout_facts"]["view_ids"] == ["tv_title", "tv_content"] and s["layout_facts"]["inherited_from"] == "TipsDialog"
    assert s["label"] == "标题甲" and s["uncertain"] is False
    assert not s.get("parent_in_nav") and s["call_site"]["from_page"] == "PageA"   # 宿主只记在 call_site，不填 parent_in_nav（2.4 会据它补裸边）
    assert any(c["node"] == "PageA$showBeta" and c.get("state_node") for c in _by(t)["TipsDialog"]["call_sites"])


def test_unresolved_kinds_flagged_uncertain_not_deleted(root):
    t = _tree(); F.fold(t, root); by = _by(t)
    for rid, kind in (("PageA$showGamma", "system_ui"), ("PageA$showDelta", "class_not_in_tree"),
                      ("PageA$showBoth", "ambiguous_multi_target")):
        assert by[rid]["uncertain"] is True and by[rid]["call_site_resolution"]["kind"] == kind
    assert by["PageA$showDelta"]["call_site_resolution"]["resolved_class"] == "EpsDialog"
    assert by["PageA$Inner"].get("uncertain") is not True and "call_site_resolution" not in by["PageA$Inner"]
    assert "PageA$showNone" in by                                             # 找不到方法：不动


def test_idempotent_and_stats(root):
    t = _tree(); F.fold(t, root); snap = copy.deepcopy(t)
    st2 = F.fold(t, root)
    strip = lambda x: {k: v for k, v in x.items() if k != "stats"}      # stats 记最后一次运行，其余必须逐字节相同
    assert strip(t) == strip(snap)
    assert st2["folded"] == 0 and st2["by_kind"].get("already_state_node") == 3
    assert t["stats"]["total_dialogs"] == len(t["dialogs"])
    assert "app_relationship_tree_fold_call_sites" in t["stats"]["enhancers"]


def test_tree_feedback_hint_attached_to_unresolved(root):
    t = _tree()
    fb = {"entries": [{"kind": "shadow_node", "node": "PageA$showDelta", "why": ["no_baseline"],
                       "android_reason": {"reason": "structurally_unreachable"}}]}
    F.fold(t, root, fb)
    assert _by(t)["PageA$showDelta"]["call_site_resolution"]["walk_feedback"]["why"] == ["no_baseline"]


def test_cli_dry_run_does_not_write(root, tmp_path):
    import subprocess
    tp = tmp_path / "tree.json"; tp.write_text(json.dumps(_tree()), encoding="utf-8")
    before = tp.read_text(encoding="utf-8")
    out = subprocess.run([sys.executable, str(Path(F.__file__)), str(tp), "--android-root", str(root), "--dry-run"],
                         capture_output=True, text=True)
    assert out.returncode == 0 and "folded=5" in out.stdout
    assert tp.read_text(encoding="utf-8") == before
    out = subprocess.run([sys.executable, str(Path(F.__file__)), str(tp), "--android-root", str(root)],
                         capture_output=True, text=True)
    assert out.returncode == 0 and "PageA$showAlpha" not in _ids(json.loads(tp.read_text(encoding="utf-8")))
