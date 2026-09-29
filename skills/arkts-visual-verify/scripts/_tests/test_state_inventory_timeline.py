import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import walk_state_inventory as wsi
import walk_timeline as wtl


def _tree():
    return {
        "pages": [
            {"id": "P_root", "preconditions": [{"kind": "login_required", "evidence": "x"},
                                               {"kind": "vip_required", "evidence": "d", "disproven": True}],
             "layout_facts": {"edit_ids": ["et_q"]}},
            {"id": "P_member", "preconditions": [{"kind": "vip_required", "polarity": "absent", "evidence": "y"}],
             "inbound_triggers": [
                 {"from_page": "P_root", "trigger_view_id": "btn_a",
                  "edge_preconditions": [{"kind": "vip_required", "evidence": "z"},
                                         {"kind": "state_required", "evidence": "et_q 非空", "data_hint": "填一段文本"}]},
                 {"from_page": "P_root", "trigger_view_id": "btn_b",
                  "edge_preconditions": [{"kind": "state_required", "evidence": "", "input": {"view_id": "et_q", "text_hint": "abc"}}]}]},
        ],
        "fragments": [], "dialogs": [],
    }


def test_inventory_groups_missing_polarity_and_input():
    inv = wsi.inventory(_tree(), {"pages": {"P_root": {"trips": ["t1", "t2"]}, "P_member": {"trips": ["t2"]}}})
    assert inv["groups"]["login_required:-"]["nodes"] == 1
    assert inv["groups"]["vip_required:absent"]["nodes"] == 1
    assert inv["groups"]["vip_required:-"]["edges"] == 1
    # 极性缺失：节点级 login_required 一条 + 边级 vip_required 一条
    assert len(inv["missing_polarity"]) == 2          # disproven 的 vip_required 不计
    assert inv["groups"]["vip_required:disproven"]["nodes"] == 1
    # state_required 无 input：只有第一条边；且 evidence 提到 edit_id → 可机械回退
    im = inv["state_required_without_input"]
    assert len(im) == 1 and im[0]["edit_id_mentioned"] == ["et_q"]
    assert inv["per_trip"]["t2"]["vip_required:absent"] == 1
    txt = wsi.render(inv)
    assert "极性缺失" in txt and "2 条" in txt


def test_timeline_mark_and_load(tmp_path):
    ew = tmp_path / "spec" / "visual-verify" / "edgewalk"
    ew.mkdir(parents=True)
    r = wtl.mark(str(ew), "scenario:login_x", trip="trip_a", scenario="login_x")
    assert r["phase"] == "scenario:login_x" and r["trip"] == "trip_a" and r["epoch"] > 0
    rows = wtl.load(str(ew))
    assert len(rows) == 1 and rows[0]["scenario"] == "login_x"
    assert os.path.basename(wtl.timeline_path(str(ew))) == "android_walk_timeline.jsonl"
    assert os.path.abspath(os.path.dirname(wtl.timeline_path(str(ew)))) == str(ew.parent)
