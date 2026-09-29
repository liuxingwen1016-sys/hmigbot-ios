"""BACK 落点回写（2026-09-10，0910 真走：创作链走到结果页后整条链出栈 / 大纲页 BACK 弹退出确认）。

夹具全是**合成树 + 合成边真值**：页名一律 RootPage/HubPage/LeafPage 这类占位名——
本规则必须换项目通用，测试里出现任何真实应用的页名/控件 id/文案都是规则被写死的信号。
"""
import json, os, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import writeback_walk as wb          # noqa: E402

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


# ══ 单元：一条记录 → 一次 BACK 观测 ═══════════════════════════════════════════
def test_back_observation_new_contract():
    o = wb.back_observation({"action": "back", "from": "LeafPage", "to": "HubPage",
                             "status": "not_reproduced", "landed": "HostPage",
                             "back_dialog": None, "walk_exec": True})
    assert o == {"node": "LeafPage", "expect": "HubPage", "landed": "HostPage",
                 "dialog": None, "matched": False}
    ok = wb.back_observation({"action": "back", "from": "LeafPage", "to": "HubPage",
                              "status": "confirmed", "landed": "HubPage", "back_dialog": None})
    assert ok["matched"] is True and ok["landed"] == "HubPage"
    dlg = wb.back_observation({"action": "back", "from": "OutlinePage", "to": "HubPage",
                               "status": "not_reproduced", "landed": None,
                               "back_dialog": "ExitConfirmDialog"})
    assert dlg["dialog"] == "ExitConfirmDialog" and dlg["matched"] is False and dlg["landed"] is None


def test_back_observation_legacy_shape_and_non_back_records():
    """旧形态：BACK 结果回填在**被 tap 的那条边**上 → 按 BACK 的页是 e['to']，期望父页是 e['from']。"""
    legacy = wb.back_observation({"from": "HubPage", "to": "LeafPage", "status": "confirmed",
                                  "landed": "LeafPage", "back_returns_to_parent": True})
    assert legacy == {"node": "LeafPage", "expect": "HubPage", "landed": "HubPage",
                      "dialog": None, "matched": True}
    bad = wb.back_observation({"from": "HubPage", "to": "LeafPage", "status": "confirmed",
                               "landed": "LeafPage", "back_returns_to_parent": False})
    # ★tap 的落点（LeafPage）绝不能当 BACK 的落点：回不去时落点未知
    assert bad["landed"] is None and bad["matched"] is False
    assert wb.back_observation({"from": "HubPage", "to": "LeafPage", "status": "confirmed"}) is None
    assert wb.back_observation(None) is None


def test_aggregate_majority_and_tie_and_strict_majority():
    obs = [{"node": "L", "expect": "H", "landed": "HostPage", "dialog": None, "matched": False},
           {"node": "L", "expect": "H", "landed": "HostPage", "dialog": None, "matched": False},
           {"node": "L", "expect": "H", "landed": "H", "dialog": None, "matched": True}]
    agg = wb.aggregate_back_landing(obs, "walk_x")
    assert agg["node"] == "HostPage" and agg["n"] == 3 and agg["matched_n"] == 1
    assert agg["matches_parent"] is False and agg["confirm_dialog"] is None and agg["walk_id"] == "walk_x"
    # 半数对半数 → 不算「回得去」（回位不可靠就该 renav）；落点平票按名字定序，逐字节可复现
    tie = wb.aggregate_back_landing(
        [{"landed": "BPage", "dialog": None, "matched": False, "expect": "H"},
         {"landed": "APage", "dialog": None, "matched": True, "expect": "H"}], "w")
    assert tie["matches_parent"] is False and tie["node"] == "APage"
    good = wb.aggregate_back_landing([{"landed": "H", "dialog": None, "matched": True, "expect": "H"}], "w")
    assert good["matches_parent"] is True and good["node"] == "H"
    dlg = wb.aggregate_back_landing(
        [{"landed": None, "dialog": "ExitConfirmDialog", "matched": False, "expect": "H"},
         {"landed": "H", "dialog": None, "matched": True, "expect": "H"}], "w")
    assert dlg["confirm_dialog"] == "ExitConfirmDialog"      # 只要稳定弹过确认窗就要报出来


# ══ 端到端：落到树 record.runtime.back_landing ═════════════════════════════════
def _tree():
    return {"pages": [{"id": "HubPage", "type": "Activity", "inbound_triggers": []},
                      {"id": "LeafPage", "type": "Activity",
                       "runtime": {"some_other_fact": "keep-me"},
                       "inbound_triggers": [{"from_page": "HubPage", "trigger_label": "进去",
                                             "trigger_view_id": "R.id.btn_go",
                                             "runtime": {"status": "confirmed"}}]},
                      {"id": "OutlinePage", "type": "Activity",
                       "inbound_triggers": [{"from_page": "HubPage", "trigger_label": "大纲"}]}],
            "fragments": [], "dialogs": []}


def _run(tmp_path, edges, walk_id="walk_1"):
    t = tmp_path / "tree.json"; e = tmp_path / "edges.json"
    t.write_text(json.dumps(_tree(), ensure_ascii=False), encoding="utf-8")
    e.write_text(json.dumps(edges, ensure_ascii=False), encoding="utf-8")
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "writeback_walk.py"),
                        "--tree", str(t), "--edges", str(e), "--walk-id", walk_id],
                       capture_output=True, text=True)
    return p, json.loads(t.read_text(encoding="utf-8"))


def _stats(p):
    """stdout = 统计 JSON + 「已写回 …」一行 → 只取前面那个 JSON 对象。"""
    return json.JSONDecoder().raw_decode(p.stdout.lstrip())[0]


def test_writeback_writes_back_landing_and_keeps_everything_else(tmp_path):
    edges = [
        # 正常 tap 边真值（照旧写 runtime）——顺带带一条旧形态 BACK 结果
        {"from": "HubPage", "to": "LeafPage", "status": "confirmed", "device_state": "trip_2",
         "control": {"rid": "btn_go", "text": "进去", "center": [1, 2]}, "landed": "LeafPage",
         "back_returns_to_parent": False, "walk_exec": True},
        # 新契约 BACK 记录 ×2：都落到 HostPage（不是计划期望的 HubPage）
        {"action": "back", "from": "LeafPage", "to": "HubPage", "status": "not_reproduced",
         "landed": "HostPage", "back_dialog": None, "walk_exec": True},
        {"action": "back", "from": "LeafPage", "to": "HubPage", "status": "not_reproduced",
         "landed": "HostPage", "back_dialog": None, "walk_exec": True},
        # 另一页：BACK 弹确认窗
        {"action": "back", "from": "OutlinePage", "to": "HubPage", "status": "not_reproduced",
         "landed": None, "back_dialog": "ExitConfirmDialog", "walk_exec": True},
    ]
    p, tree = _run(tmp_path, edges)
    assert p.returncode == 0, p.stderr
    by = {r["id"]: r for r in tree["pages"]}
    bl = by["LeafPage"]["runtime"]["back_landing"]
    assert bl["node"] == "HostPage" and bl["n"] == 3 and bl["matches_parent"] is False
    assert bl["confirm_dialog"] is None and bl["walk_id"] == "walk_1" and bl["expects"] == "HubPage"
    assert by["LeafPage"]["runtime"]["some_other_fact"] == "keep-me"      # 与既有 runtime 并存
    ob = by["OutlinePage"]["runtime"]["back_landing"]
    assert ob["confirm_dialog"] == "ExitConfirmDialog" and ob["matches_parent"] is False
    # 负面证据不删边；tap 边真值照旧写进 inbound_triggers[].runtime
    assert len(by["LeafPage"]["inbound_triggers"]) == 1
    assert by["LeafPage"]["inbound_triggers"][0]["runtime"]["status"] == "confirmed"
    assert len(by["OutlinePage"]["inbound_triggers"]) == 1
    # BACK 记录不进 trigger 匹配 → 不产生 discovered_edges / 不触发消歧闸
    assert "discovered_edges" not in by["HubPage"]
    st = _stats(p)
    assert st["back_landing_written"] == 2 and st["back_observed"] == 4


def test_back_record_for_unknown_node_does_not_block(tmp_path):
    """BACK 观测的宿主页不在树内（黑盒变体/未知落点）→ 单独记账，绝不走 exit 20 的拒写闸。"""
    p, tree = _run(tmp_path, [{"action": "back", "from": "Ghost#via=x", "to": "HubPage",
                               "status": "not_reproduced", "landed": None, "back_dialog": None}])
    assert p.returncode == 0, p.stderr
    st = _stats(p)
    assert st["back_node_missing"] == 1 and st["_defects"]["back_node_missing"][0]["node"] == "Ghost#via=x"
    assert "node_missing" not in st.get("_defects", {})
