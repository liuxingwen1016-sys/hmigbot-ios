#!/usr/bin/env python3
"""遍历侧「只报不删」树反馈（tree_feedback.py，2026-09-11）——合成夹具，零 app 常量。

三个检测器：影子节点 / 同屏对（整份 dump md5）/ 同控件集。复合判据是为了不重演
「哈希分桶 10 组撞车只 1 组真重复」的假阳：两边都有布局事实的同屏对只记 host_overlay_or_container，不判重复。
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tree_feedback as T  # noqa: E402

XML_A = '<hierarchy><node resource-id="p/ctl_a" text="占位甲"/><node resource-id="p/ctl_b" text=""/></hierarchy>'
XML_A2 = '<hierarchy><node resource-id="p/ctl_a" text="占位甲" index="1"/><node resource-id="p/ctl_b" text=""/></hierarchy>'
XML_C = '<hierarchy><node resource-id="p/ctl_c" text="占位丙"/></hierarchy>'
XML_F = '<hierarchy><node resource-id="p/ctl_f" text="占位己"/></hierarchy>'


def _rec(rid, layout=True, status="walkable", **kw):
    r = {"id": rid, "walkability": {"status": status}}
    if layout:
        r["layout_file"] = f"res/layout/{rid}.xml"
    r.update(kw)
    return r


def _tree():
    return {"pages": [_rec("PageA"), _rec("PageA2"), _rec("PageC"), _rec("PageDead", layout=False, status="dead")],
            "fragments": [_rec("FragNoLayout", layout=False)],
            "dialogs": [_rec("DlgA", layout=True), _rec("PageA$showX", layout=False), _rec("Unknown#via=noise", layout=False)]}


def _baseline(tmp_path):
    b = tmp_path / "trip_x"; b.mkdir()
    for n, x in (("PageA", XML_A), ("DlgA", XML_A), ("PageA2", XML_A2), ("PageC", XML_C), ("FragNoLayout", XML_F)):
        (b / f"{n}.android.xml").write_text(x, encoding="utf-8"); (b / f"{n}.png").write_bytes(b"png")
    (b / "_evi_x.png").write_bytes(b"x")                       # 下划线开头的取证文件不算节点
    return b


def test_baseline_index_names_and_controls(tmp_path):
    base = T.baseline_index(str(_baseline(tmp_path)))
    assert set(base) == {"PageA", "DlgA", "PageA2", "PageC", "FragNoLayout"}
    assert base["PageA"]["md5"] == base["DlgA"]["md5"] and base["PageA"]["md5"] != base["PageA2"]["md5"]
    assert base["PageA"]["controls"] == base["PageA2"]["controls"] == frozenset({("ctl_a", "占位甲"), ("ctl_b", "")})


def test_detectors(tmp_path):
    base = T.baseline_index(str(_baseline(tmp_path)))
    ov = {"PageA$showX": {"reason": "structurally_unreachable", "note": "一次性门已消费"}}
    ents = T.detect(_tree(), base, ov, "trip_x")
    by_kind = {}
    for e in ents:
        by_kind.setdefault(e["kind"], []).append(e)
    # ① 影子：无基线 + ($ 或无布局)；dead 的不报；有基线的无布局节点（FragNoLayout）不报
    shadows = {e["node"]: e for e in by_kind["shadow_node"]}
    assert set(shadows) == {"PageA$showX", "Unknown#via=noise"}
    assert shadows["PageA$showX"]["why"] == ["id_has_dollar_call_site_or_inner_class", "no_layout_facts"]
    assert shadows["PageA$showX"]["android_reason"]["reason"] == "structurally_unreachable"
    # ② 同屏对：PageA/DlgA 整份 md5 相同，两边都有布局 → host_overlay_or_container（不是重复）
    pairs = by_kind["same_screen_pair"]
    assert len(pairs) == 1 and pairs[0]["group"] == ["DlgA", "PageA"] and pairs[0]["classification"] == "host_overlay_or_container"
    # ③ 同控件集：PageA2 与 PageA 控件集相同但 md5 不同 —— PageA 已进 md5 组，PageA2 单独成不了组 → 不报
    assert "same_control_set" not in by_kind
    # 有一边无布局的同屏对 → suspect_duplicate
    t = _tree(); [r for r in t["dialogs"] if r["id"] == "DlgA"][0].pop("layout_file")
    p2 = [e for e in T.detect(t, base, {}, "trip_x") if e["kind"] == "same_screen_pair"][0]
    assert p2["classification"] == "suspect_duplicate"


def test_same_control_set_when_no_md5_group(tmp_path):
    b = _baseline(tmp_path); (b / "DlgA.android.xml").unlink(); (b / "DlgA.png").unlink()
    base = T.baseline_index(str(b))
    ents = [e for e in T.detect(_tree(), base, {}, "trip_x") if e["kind"] == "same_control_set"]
    assert len(ents) == 1 and ents[0]["group"] == ["PageA", "PageA2"] and ents[0]["classification"] == "suspect_alias"


def test_cli_merges_trips_and_never_touches_tree(tmp_path):
    b = _baseline(tmp_path)
    tp = tmp_path / "tree.json"; tp.write_text(json.dumps(_tree()), encoding="utf-8"); before = tp.read_text(encoding="utf-8")
    out = tmp_path / "ew" / "tree_feedback.json"
    cmd = [sys.executable, T.__file__, "--tree", str(tp), "--baseline-dir", str(b), "--out", str(out)]
    assert subprocess.run(cmd + ["--trip", "trip_x"], capture_output=True, text=True).returncode == 0
    assert subprocess.run(cmd + ["--trip", "trip_y"], capture_output=True, text=True).returncode == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["trips"] == ["trip_x", "trip_y"] and all(e["trip"] in ("trip_x", "trip_y") for e in d["entries"])
    n_x = sum(1 for e in d["entries"] if e["trip"] == "trip_x")
    assert subprocess.run(cmd + ["--trip", "trip_x"], capture_output=True, text=True).returncode == 0   # 重跑同趟：覆盖不累加
    assert sum(1 for e in json.loads(out.read_text(encoding="utf-8"))["entries"] if e["trip"] == "trip_x") == n_x
    assert tp.read_text(encoding="utf-8") == before                                                    # 树一个字节没动
    assert subprocess.run(cmd + ["--trip", "t", "--baseline-dir", str(tmp_path / "nope")], capture_output=True).returncode == 2
