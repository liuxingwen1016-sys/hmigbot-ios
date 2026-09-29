"""共用弹窗按调用方分变体基线（2026-09-09 晚，用户拍板）：同一 dialog 节点被不同调用方到达 → 各一张 #via= 变体。"""
import json, os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from test_walk_exec_rules import (FakeDev, ew, mk_exec, wrap, write_plan, write_ledger, last_edge)  # noqa: F401,E402
import walk_exec as we  # noqa: E402

DLG = wrap('<node resource-id="com.x:id/tv_body" text="确定要继续吗?" bounds="[100,800][980,1000]"/>'
           '<node resource-id="com.x:id/tv_cancel" text="取消" clickable="true" bounds="[100,1100][500,1200]"/>')
SENT = {"P1": {"kind": "activity_suffix", "value": "HomeActivity"},
        "P2": {"kind": "activity_suffix", "value": "HomeActivity"},
        "Dlg": {"kind": "resource_id_unique", "value": ["tv_body"], "hosts": []}}


def _src(rid, text):
    return wrap(f'<node resource-id="com.x:id/{rid}" text="{text}" clickable="true" bounds="[0,0][200,100]"/>')


def _exec(ew, dumps):
    ex = mk_exec(ew, dev=FakeDev(dumps))
    ex.tree = {"pages": [{"id": "P1"}, {"id": "P2"}], "fragments": [], "dialogs": [{"id": "Dlg"}]}
    ex.a.no_grounding = True; ex.a.no_blackbox = True
    return ex


def test_second_caller_gets_variant_baseline_first_caller_keeps_node(ew):
    s1 = {"step": 1, "action": "tap", "from": "P1", "to": "Dlg", "trigger": "退出", "static_rid": "btn_exit", "settles_capture": "Dlg"}
    s2 = {"step": 2, "action": "tap", "from": "P2", "to": "Dlg", "trigger": "退款", "static_rid": "btn_refund"}
    s3 = {"step": 3, "action": "tap", "from": "P1", "to": "Dlg", "trigger": "退出", "static_rid": "btn_exit"}
    write_plan(ew, [{"walk_id": "w1", "steps": [s1, s2, s3]}], sentinels=SENT)
    write_ledger(ew)
    ex = _exec(ew, [_src("btn_exit", "退出"), DLG])
    ex.do_tap(s1)                                                   # 首达：原节点结账
    led = json.load(open(ew / "ledger.json"))["settled"]
    assert "Dlg" in led and led["Dlg"]["capture"] == "dialog_direct"
    ex.dev.dumps = [_src("btn_refund", "退款"), DLG]
    ex.do_tap(s2)                                                   # 第二个调用方：变体
    led = json.load(open(ew / "ledger.json"))["settled"]
    vids = [k for k in led if k.startswith("Dlg#via=")]
    assert vids == ["Dlg#via=P2__btn_refund"]
    assert led[vids[0]]["capture"] == "dialog_direct" and led[vids[0]]["via"].startswith("P2--[")
    assert any(str(p).endswith("shots/Dlg#via=P2__btn_refund.png") for p in ex.dev.shots)   # 假设备只记路径不落盘
    e = last_edge(ew)
    assert e["status"] == "confirmed" and e["variant_baseline"] == "Dlg#via=P2__btn_refund"
    assert e["evidence"].endswith("Dlg#via=P2__btn_refund.png")
    ex.dev.dumps = [_src("btn_exit", "退出"), DLG]
    ex.do_tap(s3)                                                   # 首个调用方复访：不重拍
    led = json.load(open(ew / "ledger.json"))["settled"]
    assert [k for k in led if k.startswith("Dlg#via=")] == ["Dlg#via=P2__btn_refund"]
    assert "variant_baseline" not in last_edge(ew)
    # 变体不普查、不进 targets 分母
    assert ex.state.get("dialog_variants") == ["Dlg#via=P2__btn_refund"]


def test_variant_is_idempotent_and_activity_targets_untouched(ew):
    s2 = {"step": 2, "action": "tap", "from": "P2", "to": "Dlg", "trigger": "退款", "static_rid": "btn_refund"}
    write_plan(ew, [{"walk_id": "w1", "steps": [s2]}], sentinels=SENT)
    write_ledger(ew, settled={"Dlg": {"via": "P1--[退出]-->", "capture": "dialog_direct"}})
    ex = _exec(ew, [_src("btn_refund", "退款"), DLG])
    ex.do_tap(s2)
    ex.dev.dumps = [_src("btn_refund", "退款"), DLG]
    ex.do_tap(s2)                                                   # 同调用方再来：变体只落一次
    led = json.load(open(ew / "ledger.json"))["settled"]
    assert sorted(k for k in led if "#via=" in k) == ["Dlg#via=P2__btn_refund"]
    # 非 dialog 节点永远不产变体
    assert ex._maybe_settle_dialog_variant("P1", "P2", "x", "y", "P2--[y]-->", None) is None
