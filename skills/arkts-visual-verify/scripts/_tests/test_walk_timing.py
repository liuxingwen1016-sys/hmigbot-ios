import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import walk_timing as wt
import walk_exec as we


def test_summarize_splits_mechanical_llm_idle():
    t0 = 1000.0
    state = {"step_times": [
        {"step": 1, "action": "coldstart", "from": None, "to": "R", "t_s": 10.0, "ended_at": t0 + 10},
        {"step": 2, "action": "tap", "from": "R", "to": "A", "t_s": 5.0, "ended_at": t0 + 15},
        {"step": 3, "action": "tap", "from": "A", "to": "B", "t_s": 3.0, "ended_at": t0 + 138}],   # 中间熔断了 120s
        "llm_gaps": [{"step": 3, "reason": "control_not_found", "llm_s": 120.0}]}
    ledger = {"coldstarts": [{"at": 0.0, "ts": t0}]}
    edges = [{"from": "R", "to": "A", "status": "confirmed", "t_s": 5.0}, {"from": "A", "to": "B", "status": "confirmed"}]
    o = wt.summarize(state, ledger, edges)
    assert o["mechanical_s"] == 18.0 and o["llm_s"] == 120.0 and o["escalations"] == 1
    assert o["wall_clock_s"] == 138.0 and o["idle_s"] == 0.0 and o["share"]["llm"] == 0.87
    assert o["by_action_s"] == {"coldstart": 10.0, "tap": 8.0} and o["by_escalation_reason"]["control_not_found"]["n"] == 1
    assert o["edges"] == {"confirmed": 2} and o["edges_with_t_s"] == 1
    assert "墙钟 138.0s" in wt.render(o)


def test_stamp_timing_adds_t_s_and_ts_without_overwrite():
    rec = {"from": "A", "to": "B", "status": "confirmed"}
    we.stamp_timing(rec, time.time() - 2.0)
    assert 1.5 <= rec["t_s"] <= 3.0 and rec["ts"] > 0
    rec2 = {"t_s": 9.9}
    we.stamp_timing(rec2, time.time())
    assert rec2["t_s"] == 9.9 and "ts" in rec2
    rec3 = {}
    we.stamp_timing(rec3, None)
    assert "t_s" not in rec3 and "ts" in rec3


def test_choose_gate_control_whitelist_only(tmp_path):
    xml = ('<node resource-id="x:id/tv_privacy_title" text="服务协议及隐私协议" clickable="false" bounds="[0,0][100,10]"/>'
           '<node resource-id="x:id/btn_disagree" text="不同意" clickable="true" bounds="[0,0][100,50]"/>'
           '<node resource-id="x:id/btn_agree_privacy" text="同意并继续" clickable="true" bounds="[0,100][200,150]"/>'
           '<node resource-id="x:id/tv_sure_1" text="确定" clickable="true" bounds="[0,200][200,250]"/>')
    pt, rid, txt = we.choose_gate_control(xml)
    assert rid == "btn_agree_privacy" and txt == "同意并继续" and pt == (100, 125)
    # 退出登录确认窗：正文含账号动作词 → 绝不放行（chunk2 审出的隐患）
    logout = ('<node text="确定退出登录吗？" clickable="false" bounds="[0,0][10,10]"/>'
              '<node resource-id="x:id/tv_sure" text="确定" clickable="true" bounds="[0,0][10,10]"/>')
    assert we.choose_gate_control(logout) is None
    # 没有门正文的普通页，即使有「确定」也不动
    assert we.choose_gate_control('<node text="保存成功" clickable="false" bounds="[0,0][1,1]"/><node resource-id="x:id/tv_sure" text="确定" clickable="true" bounds="[0,0][10,10]"/>') is None
    assert we.choose_gate_control('<node resource-id="x:id/tv_refund_sure" text="确定退款" clickable="true" bounds="[0,0][10,10]"/>') is None
    assert we.choose_gate_control('<node resource-id="x:id/tv_sure" text="确定" clickable="false" bounds="[0,0][10,10]"/>') is None
    led = tmp_path / "ledger.json"; led.write_text('{"t0": 1.0, "coldstarts": [], "settled": {}}', encoding="utf-8")
    assert we.settle_dialog_direct(str(led), "CustomerServiceDialog", "Mine--[联系我们]-->", "s.png", "s.xml", "x.HomeActivity")
    import json; d = json.load(open(led)); assert d["settled"]["CustomerServiceDialog"]["capture"] == "dialog_direct"
    assert we.settle_dialog_direct(str(led), "CustomerServiceDialog", "again", "t.png", "t.xml", "x") and d["settled"]["CustomerServiceDialog"]["capture_meta"]["screenshot"] == "s.png"


def test_choose_cancel_control_whitelist():
    xml = ('<node resource-id="x:id/tv_sure" text="确定" clickable="true" bounds="[0,0][100,50]"/>'
           '<node resource-id="x:id/tv_cancel" text="取消" clickable="true" bounds="[0,100][200,150]"/>')
    pt, rid, txt = we.choose_cancel_control(xml)
    assert rid == "tv_cancel" and txt == "取消"
    assert we.choose_cancel_control('<node resource-id="x:id/tv_sure" text="确定" clickable="true" bounds="[0,0][10,10]"/>') is None
    pt, rid, txt = we.choose_cancel_control('<node resource-id="x:id/iv_close_dialog" text="" clickable="true" bounds="[0,0][10,10]"/>', extra_ids=["pkg:id/iv_close_dialog"])
    assert rid == "iv_close_dialog"
