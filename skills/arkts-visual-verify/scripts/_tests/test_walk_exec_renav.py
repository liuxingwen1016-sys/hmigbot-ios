"""B1（2026-09-10）执行器侧：renav 回位步 + BACK 观测记录（新契约）。
夹具全是占位名（R/A/B/C），零 app 常量。"""
import json, os, sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import walk_exec as we  # noqa: E402
import writeback_walk as wb  # noqa: E402
from test_walk_exec_rules import (FakeDev, ew, mk_exec, wrap, write_plan, write_ledger,  # noqa: F401,E402
                                  _reset_ui_words, _no_sleep)


def _xml(rid, extra=""):
    return wrap(f'<node resource-id="com.x:id/{rid}" text="{rid}" clickable="true" bounds="[0,0][200,100]"/>{extra}')


R_XML, A_XML, B_XML, C_XML = _xml("tv_r", _xml("btn_a")[60:-20]), _xml("tv_a", ""), _xml("tv_b"), _xml("tv_c")
# A 页上要有推进控件 btn_b；R 页上要有 btn_a
R_XML = wrap('<node resource-id="com.x:id/tv_r" bounds="[0,0][200,100]"/>'
             '<node resource-id="com.x:id/btn_a" text="去A" clickable="true" bounds="[0,100][200,200]"/>')
A_XML = wrap('<node resource-id="com.x:id/tv_a" bounds="[0,0][200,100]"/>'
             '<node resource-id="com.x:id/btn_b" text="去B" clickable="true" bounds="[0,100][200,200]"/>')
X_XML = wrap('<node resource-id="com.x:id/tv_x" bounds="[0,0][200,100]"/>')

SENT = {n: {"kind": "resource_id_unique", "value": [f"tv_{n.lower()}"], "hosts": []} for n in ("R", "A", "B", "C")}
STEPS = [
    {"step": 1, "action": "coldstart", "to": "R"},
    {"step": 2, "action": "tap", "from": "R", "to": "A", "trigger": "去A", "static_rid": "btn_a"},
    {"step": 3, "action": "type", "from": "A", "to": "A", "view_id": "com.x:id/et_topic", "text": "hello world"},
    {"step": 4, "action": "tap", "from": "A", "to": "B", "trigger": "去B", "static_rid": "btn_b"},
    {"step": 5, "action": "tap", "from": "B", "to": "C", "trigger": "去C", "static_rid": "btn_c"},
    {"step": 6, "action": "renav", "from": "C", "to": "B", "kind": "activity", "reason": "back_landing_mismatch"},
    {"step": 7, "action": "tap", "from": "B", "to": "C", "trigger": "再去C", "static_rid": "btn_c2"},
    {"step": 8, "action": "renav", "from": "C", "to": "A", "reason": "back_needs_confirm"},
    {"step": 9, "action": "tap", "from": "A", "to": "B", "trigger": "去B2", "static_rid": "btn_b2"},
]
WALK = {"walk_id": "w1", "steps": STEPS}


# ── 位置模拟：renav 与 back 同等 ─────────────────────────────────────────────
def test_positions_and_stack_treat_renav_as_return():
    pos = we.precompute_positions(WALK)
    assert pos[5] == "C" and pos[6] == "B"          # renav(6) 执行前在 C，执行后位置=B
    assert pos[8] == "A"                              # renav(8) 回到 A
    assert we.simulate_stack(WALK, 6) == ["R", "A", "B"]
    assert we.simulate_stack(WALK, 8) == ["R", "A"]


def test_subtree_end_closes_on_renav():
    pos = we.precompute_positions(WALK)
    # 跳过 step7（B→C 的 tap）：子树到 step8 renav 回 A 为止？不——renav 的 to 是 A≠B，所以要找回到 B 的位置
    # 跳过 step5（B→C）：下一次回到位置 B 的步是 step6 renav(to=B) → 区间含它
    assert we.subtree_end(WALK, pos, 4) == 6           # steps[4]=step5；step6（下标5）是 renav 回 B → j+1=6


# ── 到达路径 / type 前置 ─────────────────────────────────────────────────────
def test_plan_path_to_and_type_replay():
    path = we.plan_path_to(WALK, 5, "B")
    assert [p[0] for p in path] == ["R", "A", "B"] and [p[1] for p in path] == [0, 1, 3]
    assert we.plan_path_to(WALK, 5, "Z") is None
    pos = we.precompute_positions(WALK)
    assert we.replay_type_steps(WALK, 1, 3, "A", pos) == [2]   # A 上的 type 步要复现
    assert we.replay_type_steps(WALK, 0, 1, "R", pos) == []


# ── do_renav ────────────────────────────────────────────────────────────────
def _setup(ew, dumps):
    write_plan(ew, [WALK], sentinels=SENT)
    write_ledger(ew)
    ex = mk_exec(ew, dev=FakeDev(dumps))
    ex._ledger = lambda *a, **k: ex.state.setdefault("_ledger_calls", []).append(list(a))
    ex.do_type = lambda st: ex.state.setdefault("_typed", []).append(st.get("step"))
    return ex


def test_renav_already_there_is_noop(ew):
    ex = _setup(ew, [B_XML])
    ex.do_renav(STEPS[5])
    assert ex.dev.taps == [] and ex.dev.backs == 0
    assert any("已在位" in n for n in ex.state["notes"])


def test_renav_replays_from_located_level_with_type_prereq(ew):
    # 当前在 A（不在 B）：探 B 不中 → 沿路径 B 不中、A 命中 → 只重放 A 上的 type + A→B 的 tap
    ex = _setup(ew, [A_XML, A_XML, A_XML, A_XML, B_XML])
    ex.do_renav(STEPS[5])
    assert ex.state["_typed"] == [3]
    assert len(ex.dev.taps) == 1 and ex.dev.backs == 0
    assert "_ledger_calls" not in ex.state                       # 没冷启就不记冷启
    assert ex.state["renavs"][-1]["replayed"] == [3, 4] and ex.state["renavs"][-1]["cold"] is False


def test_renav_relaunches_when_off_path_and_counts_coldstart(ew):
    # 在未知页 X：路径三层都探不到 → 重新拉起（不 pm clear）→ 落在 R → 重放 R→A、type、A→B
    ex = _setup(ew, [X_XML, X_XML, X_XML, X_XML, R_XML, R_XML, R_XML, R_XML, A_XML, A_XML, B_XML])
    ex.do_renav(STEPS[5])
    assert ex.state["_ledger_calls"] and ex.state["_ledger_calls"][0][0] == "coldstart"
    assert not any("pm clear" in c for c in ex.dev.shell_log)
    assert ex.state["renavs"][-1]["cold"] is True and ex.state["renavs"][-1]["replayed"] == [2, 3, 4]
    assert len(ex.dev.taps) == 2


def test_renav_escalates_position_mismatch_when_unreachable(ew):
    ex = _setup(ew, [X_XML])
    with pytest.raises(SystemExit) as e:
        ex.do_renav(STEPS[5])
    assert e.value.code == 30
    st = json.load(open(ew / "walk_exec_state.json"))
    assert st["escalation"]["reason"] == "position_mismatch" and st["escalation"]["action"] == "renav"


def test_run_dispatches_renav(ew, monkeypatch):
    write_plan(ew, [{"walk_id": "w1", "steps": [{"step": 1, "action": "renav", "from": "C", "to": "B", "reason": "x"}]}],
               sentinels=SENT)
    write_ledger(ew)
    ex = mk_exec(ew, dev=FakeDev([B_XML]))
    ex._check_trip_order = lambda: None
    ex.run()
    assert any("已在位" in n for n in ex.state["notes"])
    assert json.load(open(ew / "walk_exec_state.json"))["status"] == "walk_done"


# ── BACK 观测记录（新契约） ──────────────────────────────────────────────────
BACK_STEP = {"step": 5, "action": "back", "from": "C", "to": "B", "kind": "activity"}


def test_do_back_records_confirmed_observation(ew):
    write_plan(ew, [WALK], sentinels=SENT); write_ledger(ew)
    ex = mk_exec(ew, dev=FakeDev([B_XML]))
    ex.do_back(BACK_STEP)
    rec = json.load(open(ew / "edge_results.json"))[-1]
    assert rec["action"] == "back" and rec["from"] == "C" and rec["to"] == "B"
    assert rec["landed"] == "B" and rec["status"] == "confirmed" and rec["back_dialog"] is None
    ob = wb.back_observation(rec)
    assert ob["node"] == "C" and ob["expect"] == "B" and ob["landed"] == "B"


def test_do_back_failure_records_unknown_landing_and_escalates(ew, monkeypatch):
    write_plan(ew, [WALK], sentinels=SENT); write_ledger(ew)
    monkeypatch.setattr(we, "choose_cancel_control", lambda xml, extra=(): None)
    ex = mk_exec(ew, dev=FakeDev([X_XML]))
    with pytest.raises(SystemExit):
        ex.do_back(BACK_STEP)
    recs = json.load(open(ew / "edge_results.json"))
    rec = [r for r in recs if r.get("action") == "back"][-1]
    assert rec["status"] == "not_reproduced" and rec["landed"] is None
    ob = wb.back_observation(rec)
    assert ob["node"] == "C" and ob["landed"] is None
    assert ex.dev.backs == 3


def test_fill_back_never_touches_back_records(ew):
    write_plan(ew, [WALK], sentinels=SENT); write_ledger(ew)
    ex = mk_exec(ew, dev=FakeDev([B_XML]))
    ex._append(ex.edge_path, {"from": "B", "to": "C", "status": "confirmed", "walk_exec": True})
    ex._append(ex.edge_path, {"action": "back", "from": "X", "to": "C", "status": "confirmed", "walk_exec": True})
    ex._pending_back_edge = "C"
    ex._fill_back(True)
    recs = json.load(open(ew / "edge_results.json"))
    assert recs[0]["back_returns_to_parent"] is True and "back_returns_to_parent" not in recs[1]
