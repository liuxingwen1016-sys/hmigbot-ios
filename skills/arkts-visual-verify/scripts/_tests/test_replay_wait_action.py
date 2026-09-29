#!/usr/bin/env python3
"""鸿蒙回放执行器的 `wait` 动作（F6，2026-09-11）——安卓 auto 转场边的对应件。

病：auto 边（首启门自动弹出 / Splash 倒计时 / 宿主装默认子页）此前编译成 skip，鸿蒙既不等也不判到达，
下一步在还没转场的屏上找控件必死（失败 dump 0 条 app 文本，零介入两趟都死在第 8 步）。
铁律不变：只产观察不判对错——到了才采、才押栈；没到记 AUTO_NOT_OBSERVED / AUTO_LANDED_ELSEWHERE 进归因
（needs_verification，不直接判缺陷），**不交接**（没发过点击，位置没丢）。夹具全占位串。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import replay_exec as R  # noqa: E402


def node(type_, bounds, text="", clickable=False):
    a = {"type": type_, "bounds": "[%d,%d][%d,%d]" % bounds, "clickable": "true" if clickable else "false"}
    if text:
        a["text"] = text
    return {"attributes": a, "children": []}


def screen(*children):
    return json.dumps({"attributes": {"bounds": "[0,0][1320,2856]"}, "children": list(children)}, ensure_ascii=False)


PAGE_A = screen(node("Text", (0, 400, 900, 500), text="占位首页标题"))
PAGE_B = screen(node("Text", (0, 400, 900, 500), text="占位乙页标题"), node("Text", (0, 600, 900, 700), text="占位乙正文"))
PAGE_C = screen(node("Text", (0, 400, 900, 500), text="占位丙页标题"))
PAGE_H = screen(node("Text", (0, 400, 900, 500), text="占位提示文案"))          # 无哨兵页，只有 wait_hint 文案


class ClockDev:
    """屏幕按 dump 次数推进（模拟"转场在第 k 次轮询后才发生"）；tap 记账但不推进。"""

    def __init__(self, screens, switch_after=0):
        self.screens = list(screens); self.n = 0; self.switch_after = switch_after
        self.taps = []; self.backs = 0; self.shells = []; self.shots = []

    def dump_layout(self, path=None):
        self.n += 1
        i = 0 if self.n <= self.switch_after else min(1, len(self.screens) - 1)
        return self.screens[i]

    def tap(self, x, y):
        self.taps.append((x, y))

    def back(self):
        self.backs += 1

    def shell(self, *a, **k):
        self.shells.append(a); return ""

    def screencap(self, p):
        open(p, "wb").write(b"\xff\xd8fake"); self.shots.append(p); return p


def _wait_step(**kw):
    s = {"step": 2, "from": "PageA", "to": "PageB", "action": "wait", "wait_budget_s": 1.0,
         "expect": {"kind": "push", "sentinel": ["占位乙页标题"], "arrival_confidence": "sentinel"},
         "android_waited_s": 2.5, "wait_hint": "until_text:占位乙页标题"}
    s.update(kw); return s


def _plan(steps, sentinels=None, cover=("PageA", "PageB", "PageC")):
    return {"app": {"bundle": "com.x"}, "safety": {"blacklist": []},
            "roots": [{"node": "PageA", "sentinel": ["占位首页标题"]}],
            "coverage_targets": list(cover),
            "node_sentinels": sentinels if sentinels is not None else
            {"PageA": ["占位首页标题"], "PageB": ["占位乙页标题"], "PageC": ["占位丙页标题"]},
            "steps": list(steps)}


def run_main(tmp_path, monkeypatch, plan, dev):
    planp = tmp_path / "replay_plan_hmos.json"
    planp.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "trip_1"
    monkeypatch.setattr(R, "DeviceAdapter", lambda *a, **k: dev)
    monkeypatch.setattr(R.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["replay_exec.py", "--plan", str(planp), "--serial", "fake",
                                      "--bundle", "com.x", "--ability", "Entry", "--out-dir", str(out)])
    code = None
    try:
        R.main()
    except SystemExit as e:
        code = e.code
    rows = [json.loads(x) for x in open(out / "run.jsonl", encoding="utf-8") if x.strip()]
    man = json.load(open(out / "capture_manifest.json", encoding="utf-8"))
    return rows, man, code


def test_wait_arrives_after_transition_and_captures_without_tapping(tmp_path, monkeypatch):
    # 切屏落在第 1 次 dump 之后（步边界）：夹具按 dump 计数切屏，若切在 capture() 内部的稳定复采中间，
    # 会把新屏登记给旧节点——那是夹具时钟假象，不是被测逻辑
    dev = ClockDev([PAGE_A, PAGE_B], switch_after=1)
    rows, man, code = run_main(tmp_path, monkeypatch, _plan([_wait_step()]), dev)
    r = rows[0]
    assert code is None and dev.taps == []                        # 等待步一下都不点
    assert r["verdict"] == "AUTO_ARRIVED" and r["matched_by"] == "sentinel" and r["landed"] == "PageB"
    assert r["stack"] == 1                                         # push 语义：到了才押栈
    assert man["pages_status"]["PageB"]["status"] == "captured"
    assert not man.get("escalations")


def test_wait_branch_captures_target_itself_when_transient_catch_cannot(tmp_path, monkeypatch):
    """目标页不在靶单 → 轮询里的顺路捞（_catch_transient 只认 _COVER）不会替它采；必须由 wait 分支自己采。"""
    dev = ClockDev([PAGE_A, PAGE_B], switch_after=1)
    rows, man, _ = run_main(tmp_path, monkeypatch, _plan([_wait_step()], cover=("PageA",)), dev)
    assert rows[0]["verdict"] == "AUTO_ARRIVED"
    assert man["pages_status"]["PageB"]["status"] == "captured" and man["pages_status"]["PageB"]["provenance"] == "arrival"
    assert "PageB" not in (man.get("transient_caught") or [])


def test_wait_already_there_on_first_dump(tmp_path, monkeypatch):
    dev = ClockDev([PAGE_B, PAGE_B])
    rows, man, _ = run_main(tmp_path, monkeypatch, _plan([_wait_step()]), dev)
    assert rows[0]["verdict"] == "AUTO_ARRIVED" and rows[0]["t_wait"] < 0.5


def test_wait_hint_text_counts_when_page_has_no_sentinel(tmp_path, monkeypatch):
    dev = ClockDev([PAGE_A, PAGE_H], switch_after=1)
    st = _wait_step(expect={"kind": "push", "sentinel": [], "arrival_confidence": "unanchored"},
                    wait_hint="until_text:占位提示文案")
    rows, man, _ = run_main(tmp_path, monkeypatch, _plan([st], sentinels={"PageA": ["占位首页标题"]}), dev)
    assert rows[0]["verdict"] == "AUTO_ARRIVED" and rows[0]["matched_by"] == "wait_hint_text"
    assert man["pages_status"]["PageB"]["status"] == "captured"


def test_wait_not_observed_records_verification_blame_and_does_not_handoff(tmp_path, monkeypatch):
    dev = ClockDev([PAGE_A, PAGE_A])                              # 屏永远不变
    rows, man, code = run_main(tmp_path, monkeypatch, _plan([_wait_step(wait_budget_s=0.3)]), dev)
    r = rows[0]
    assert code is None and dev.taps == []                        # 不交接（没发过点击，位置没丢）
    assert r["verdict"] == "AUTO_NOT_OBSERVED" and r["sig_changed"] is False and r["escalated"] is True
    assert "handoff_suppressed" in r
    e = man["escalations"][0]
    assert e["blame"] == "auto_transition_missing_in_hmos" and e["product_defect"] is None and e["needs_verification"] is True
    assert "2.5" in e["evidence"] and "屏也没变" in e["evidence"]
    assert man["pages_status"]["PageB"]["status"] == "escalated"


def test_wait_landed_elsewhere(tmp_path, monkeypatch):
    dev = ClockDev([PAGE_A, PAGE_C], switch_after=1)
    rows, man, code = run_main(tmp_path, monkeypatch, _plan([_wait_step(wait_budget_s=0.3)]), dev)
    r = rows[0]
    assert code is None and r["verdict"] == "AUTO_LANDED_ELSEWHERE" and r["landed"] == "PageC"
    e = man["escalations"][0]
    assert e["blame"] == "auto_transition_diverged" and e["needs_verification"] is True and e["landed"] == "PageC"


def test_wait_does_not_fall_through_to_tap_abandon(tmp_path, monkeypatch):
    """回归闸：新 action 绝不能掉进 tap 兜底（0910 gate_pass 的老病）。"""
    dev = ClockDev([PAGE_A, PAGE_A])
    rows, _man, _ = run_main(tmp_path, monkeypatch, _plan([_wait_step(wait_budget_s=0.2)]), dev)
    assert rows[0]["verdict"] != "ABANDON_no_match" and "tried" not in rows[0]


def test_judge_input_passes_needs_verification_through():
    # build_judge_input 在模块级 parse_args，不能 import；读源码文本核对接线
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build_judge_input.py"),
               encoding="utf-8").read()
    assert '"needs_verification": bool(e.get("needs_verification"))' in src
    assert "auto_transition_missing_in_hmos" in src and "auto_transition_diverged" in src


def test_wait_detects_divergence_before_wait_starts(tmp_path, monkeypatch):
    """T-1：wait 一开始就站在已知别页（发散被前一步盖住）→ 立即 AUTO_LANDED_ELSEWHERE(diverged_before_wait)，
    不空等预算，也不再误判成"没实装"（AUTO_NOT_OBSERVED）。"""
    dev = ClockDev([PAGE_C, PAGE_C])                              # 从第一次 dump 起就在 PageC
    rows, man, code = run_main(tmp_path, monkeypatch, _plan([_wait_step(wait_budget_s=5.0)]), dev)
    r = rows[0]
    assert code is None and r["verdict"] == "AUTO_LANDED_ELSEWHERE" and r["landed"] == "PageC"
    assert r["diverged_before_wait"] is True and r["t_wait"] < 1.0        # 没有把 5s 预算等满
    e = man["escalations"][0]
    assert e["blame"] == "auto_transition_diverged" and e["diverged_before_wait"] is True
    assert "等待开始时就已不在起点页" in e["evidence"]


def test_wait_unknown_position_still_waits(tmp_path, monkeypatch):
    """识别不出当前页（无哨兵）→ 不下"发散"判断，照常等；等满仍无 → AUTO_NOT_OBSERVED。"""
    unknown = screen(node("Text", (0, 400, 900, 500), text="占位：认不出的页"))
    dev = ClockDev([unknown, unknown])
    rows, man, _ = run_main(tmp_path, monkeypatch, _plan([_wait_step(wait_budget_s=0.3)]), dev)
    assert rows[0]["verdict"] == "AUTO_NOT_OBSERVED" and rows[0].get("diverged_before_wait") is None


def test_wait_landed_elsewhere_captures_landing_page_and_arms_its_reconcile(tmp_path, monkeypatch):
    """N-1（replay-t1e 回退实证）：提前返回后不能靠轮询碰巧顺路采；落点是靶单内已知页 → 顺路补采 + 插队它欠的 reconcile。"""
    dev = ClockDev([PAGE_C, PAGE_C])
    rec = {"step": "5R", "action": "reconcile", "node": "PageC", "from": "PageC", "to": "PageC", "anchored": True,
           "elements": [{"trigger_text": "占位丙页标题", "rid": "tv_c", "observe_only": True, "oracle_source": "functional_checks",
                         "match_labels": ["占位丙页标题"], "text_identity_source": "android_dump_name"}]}
    rows, man, _ = run_main(tmp_path, monkeypatch, _plan([_wait_step(wait_budget_s=5.0), rec]), dev)
    assert rows[0]["verdict"] == "AUTO_LANDED_ELSEWHERE" and rows[0].get("opportunistic_capture") == ["PageC"]
    assert man["pages_status"]["PageC"]["status"] == "captured" and man["pages_status"]["PageC"]["provenance"] == "opportunistic"
    inj = [r for r in rows if str(r.get("step")).endswith("@arrival")]
    assert inj and inj[0]["verdict"] == "RECONCILE"                                   # 落点页的 reconcile 被插队执行了
    obs = man["per_page"]["PageC"]["behavior_observations"]
    assert obs and obs[0]["outcome"] == "rendered"


def test_coverage_treats_unverifiable_as_unverified_not_observed():
    """N-4：unverifiable_no_screen_identity 是无证据，不进分子。"""
    import lib_coverage as L
    assert "unverifiable_no_screen_identity" in L.UNVERIFIED_OUTCOMES
    plan = {"functional_denominator": [{"node": "PageA", "name": "描述甲", "rid": "tv_a"},
                                       {"node": "PageA", "name": "描述乙", "rid": "iv_b"}]}
    man = {"per_page": {"PageA": {"behavior_observations": [
        {"trigger_text": "描述甲", "rid": "tv_a", "outcome": "rendered"},
        {"trigger_text": "描述乙", "rid": "iv_b", "outcome": "unverifiable_no_screen_identity"}]}}}
    fc = L.functional_coverage(plan, man)
    assert fc["observed"] == 1 and fc["gaps"] == 1 and fc["ratio"] == 0.5

