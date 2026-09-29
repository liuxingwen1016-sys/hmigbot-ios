#!/usr/bin/env python3
"""执行期：反向门禁探测（GATE_HELD / GATE_MISSING / 落点判不出）+ 无锚点到达（2026-09-11）。

病：安卓在登出趟被登录/会员门拦住的边，鸿蒙侧此前**根本没人去点** —— 门要是丢了（未登录
    就能进受限页）在账面上完全不可见；而安卓已 confirmed、鸿蒙侧目标页没哨兵的边，
    要么被编译期静默跳过，要么被当成「到达失败」去交接。

夹具纪律：app 侧标识一律占位串（PageA / GateX / ctlB / 判别物A…），断言里不出现任何真实应用常量。
设备全假：不碰 hdc/adb，屏幕是一张脚本化状态机。
"""
import json
import os
import sys

import pytest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)

import replay_exec as R  # noqa: E402


# ── 纯函数：落点四分 ─────────────────────────────────────────────────────────
GP = ("GateX",)


def test_gate_verdict_not_exercised_beats_everything():
    """点了屏没变、还在源页 → 门压根没被触发。**绝不能读成「门没拦住」**（方向正好相反）。"""
    v, why = R.gate_landing_verdict("PageA", "PageB", "PageA", False, "GateX", GP)
    assert v == "GATE_NOT_EXERCISED"
    v2, _ = R.gate_landing_verdict(None, "PageB", "PageA", False, "GateX", GP)
    assert v2 == "GATE_NOT_EXERCISED"


def test_gate_verdict_held_by_node_set_sentinel_and_regex():
    assert R.gate_landing_verdict("GateX", "PageB", "PageA", True, "GateX", GP)[0] == "GATE_HELD"
    # 门集给不出具体是哪道门时，门页哨兵在场也算拦住
    assert R.gate_landing_verdict(None, "PageB", "PageA", True, None, (), True)[0] == "GATE_HELD"
    # 兜底正则只作用在**落点节点名**上（不扫全屏文本，否则登出屏上的「登录」字样会假阳）
    assert R.gate_landing_verdict("SomeLoginPage", "PageB", "PageA", True, None, (), False,
                                  R._LOGIN_GATE_FALLBACK_RE if hasattr(R, "_LOGIN_GATE_FALLBACK_RE")
                                  else __import__("re").compile("Login"))[0] == "GATE_HELD"


def test_gate_verdict_missing_and_unknown():
    assert R.gate_landing_verdict("PageB", "PageB", "PageA", True, "GateX", GP)[0] == "GATE_MISSING"
    assert R.gate_landing_verdict("PageZ", "PageB", "PageA", True, "GateX", GP)[0] == "GATE_MISSING"
    assert R.gate_landing_verdict(None, "PageB", "PageA", True, "GateX", GP)[0] == "GATE_UNKNOWN"


def test_judge_input_maps_gate_missing_to_security_must_ticket():
    """下游 build_judge_input 必须认识这条归因：must_ticket 由 product_defect 驱动（同
    control_missing_in_hmos 一级），严重级另标 security。脚本是模块级执行体，这里按源码契约验。"""
    src = open(os.path.join(SCRIPTS, "build_judge_input.py"), encoding="utf-8").read()
    assert '"gate_missing_in_hmos": "SECURITY_GATE_MISSING' in src
    assert 'e.get("blame") == "gate_missing_in_hmos"' in src


# ── 假设备 ──────────────────────────────────────────────────────────────────
def _node(type_, bounds, text="", clickable=False, key="", children=()):
    a = {"type": type_, "bounds": "[%d,%d][%d,%d]" % bounds,
         "clickable": "true" if clickable else "false"}
    if text:
        a["text"] = text
    if key:
        a["key"] = key
    return {"attributes": a, "children": list(children)}


def screen(*children):
    return json.dumps({"attributes": {"bounds": "[0,0][1320,2856]"},
                       "children": list(children)}, ensure_ascii=False)


def page(tag, *extra_ctrls):
    """一屏 = 一条独有判别物 + 若干可点控件（可点容器无 text，文案在子 Text —— 鸿蒙真实形状）。"""
    return screen(_node("Text", (100, 200, 1200, 300), text=f"判别物{tag}"), *extra_ctrls)


def ctrl(label, key, y=1000):
    return _node("Stack", (100, y, 1200, y + 120), clickable=True, key=key,
                 children=[_node("Text", (200, y + 20, 1100, y + 100), text=label)])


SCREENS = {
    "PageA": page("A", ctrl("入口甲", "ctlB", 900), ctrl("入口丙", "ctlC", 1200)),
    "GateX": page("G", ctrl("占位登录键", "ctlLogin")),
    "PageB": page("B"),
    "PageC": page("C"),
    # 识别不出的屏：没有任何页的哨兵，但结构/文本与 PageA 不同 → 签名会变
    "Unknown": screen(_node("Text", (100, 200, 1200, 300), text="无人认领的一屏")),
}


class FakeDrv:
    """脚本化的一块屏：tap 按当前屏查转移表，back 按返回表。不碰任何真实设备。"""

    def __init__(self, start, on_tap, back_to=None):
        self.cur = start
        self.on_tap = dict(on_tap)
        self.back_to = dict(back_to or {})
        self.taps = []
        self.backs = 0

    def dump_layout(self, out_local=None):
        return SCREENS[self.cur]

    def tap(self, x, y):
        self.taps.append((self.cur, x, y))
        self.cur = self.on_tap.get(self.cur, self.cur)

    def back(self):
        self.backs += 1
        self.cur = self.back_to.get(self.cur, self.cur)

    def swipe(self, x1, y1, x2, y2, *a, **kw):
        self.swipes = getattr(self, "swipes", 0) + 1

    def screencap(self, path):
        with open(path, "wb") as f:
            f.write(b"\x89PNG")

    def shell(self, *a, **kw):
        return ""


BASE_PLAN = {
    "app": {"bundle": "b", "ability": "a"},
    "safety": {"blacklist": []},
    "roots": [{"node": "PageA", "sentinel": ["判别物A"]}],
    "coverage_targets": ["PageA", "PageB", "PageC", "GateX"],
    "node_sentinels": {"PageA": ["判别物A"], "PageB": ["判别物B"],
                       "PageC": ["判别物C"], "GateX": ["判别物G"]},
    "login_gate_pages": ["GateX"],
    "trip_id": "trip_1_logged_out",
    "ignore_nodes": [], "dynamic_texts": [],
}


def gate_step(probe_only=True):
    return {"step": 1, "action": "tap", "from": "PageA", "to": "PageB",
            "match": {"primary": "入口甲", "rid": "ctlB", "source": "runtime"},
            "wait_budget_s": 0.1, "safety": "normal",
            "expect": {"kind": "push", "sentinel": ["判别物B"],
                       "arrival_confidence": "gate_probe"},
            "expect_blocked": True, "expected_gate": "GateX",
            "gate_kinds": ["login_required"], "gate_evidence": "tree_edge_precondition",
            "probe_only": probe_only}


def run(tmp_path, steps, drv, plan_extra=None, argv_extra=()):
    plan = dict(BASE_PLAN, steps=steps, **(plan_extra or {}))
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    argv = ["replay_exec.py", "--plan", str(p), "--serial", "fake", "--bundle", "b",
            "--ability", "a", "--out-dir", str(out), *argv_extra]
    import time as _t
    old_argv, old_drv, old_sleep = sys.argv, R.DeviceAdapter, _t.sleep
    sys.argv = argv
    R.DeviceAdapter = lambda *a, **kw: drv
    _t.sleep = lambda *_a, **_k: None      # 假设备没有真实时延；预算判据走 time.time()，语义不变
    code = 0
    try:
        R.main()
    except SystemExit as e:
        code = e.code
    finally:
        sys.argv, R.DeviceAdapter, _t.sleep = old_argv, old_drv, old_sleep
    rows = [json.loads(x) for x in open(out / "run.jsonl", encoding="utf-8") if x.strip()]
    man = json.load(open(out / "capture_manifest.json", encoding="utf-8"))
    return rows, man, code


# ── 1. GATE_HELD：门还在 = 正常，不出单，立即单次回位 ─────────────────────────
def test_gate_held_no_ticket_and_single_back(tmp_path):
    drv = FakeDrv("PageA", {"PageA": "GateX"}, {"GateX": "PageA"})
    rows, man, code = run(tmp_path, [gate_step()], drv)
    r = rows[0]
    assert r["verdict"] == "GATE_HELD" and r["gate_verdict"] == "GATE_HELD"
    assert man["escalations"] == []                  # 门还在 = 正常行为，绝不出单
    assert drv.backs == 1 and drv.cur == "PageA"     # 只按一次，回到起点
    assert code in (0, None)


# ── 2. GATE_MISSING：门失守 = 安全缺陷，必出单 ───────────────────────────────
def test_gate_missing_raises_security_ticket(tmp_path):
    drv = FakeDrv("PageA", {"PageA": "PageB"}, {"PageB": "PageA"})
    rows, man, code = run(tmp_path, [gate_step()], drv)
    assert rows[0]["verdict"] == "GATE_MISSING"
    e = man["escalations"][0]
    assert e["blame"] == "gate_missing_in_hmos"
    assert e["product_defect"] is True and e["severity"] == "security"
    assert e["expected_gate"] == "GateX" and e["landed"] == "PageB"
    assert drv.backs == 1                            # 门失守也照样回位（纯探测步）


def test_gate_missing_on_walk_step_keeps_going_instead_of_returning(tmp_path):
    """走序里本来就要点的边（probe_only=False）：门失守要出单，但**不回位**——
    我们确实进去了，计划照常走完子树，覆盖不能丢。"""
    drv = FakeDrv("PageA", {"PageA": "PageB"}, {"PageB": "PageA"})
    rows, man, _ = run(tmp_path, [gate_step(probe_only=False)], drv)
    assert rows[0]["gate_verdict"] == "GATE_MISSING"
    assert rows[0]["verdict"] == "ARRIVED_strong"     # 落判走正常到达分支
    assert man["escalations"][0]["blame"] == "gate_missing_in_hmos"
    assert drv.backs == 0


def test_gate_held_on_walk_step_skips_subtree_via_phantom(tmp_path):
    """走序步被门拦住 → 用既有 phantom 机制安全跳过子树，而不是让后面每步都在错屏上找控件。"""
    child = {"step": 2, "action": "tap", "from": "PageB", "to": "PageC",
             "match": {"primary": "入口丙", "rid": "ctlC", "source": "runtime"},
             "wait_budget_s": 0.1, "expect": {"kind": "push", "sentinel": ["判别物C"]}}
    drv = FakeDrv("PageA", {"PageA": "GateX"}, {"GateX": "PageA"})
    rows, man, _ = run(tmp_path, [gate_step(probe_only=False), child], drv)
    assert rows[0]["verdict"] == "GATE_HELD"
    assert rows[1]["verdict"] == "SKIP_ESCALATED"
    assert drv.backs == 1


# ── 3. 落点判不出 → 不猜，走既有交接 ─────────────────────────────────────────
def test_gate_landing_unknown_hands_off(tmp_path):
    drv = FakeDrv("PageA", {"PageA": "Unknown"}, {})
    rows, man, code = run(tmp_path, [gate_step()], drv)
    assert rows[0]["verdict"] == "GATE_UNKNOWN"
    assert code == 32                                  # 位置真丢了 → 交接
    assert man["escalations"][0]["blame"] == "gate_landing_unknown"
    assert man["escalations"][0]["product_defect"] is None   # 不猜就不定罪
    assert drv.backs == 0                              # 判不出时连回位都不做


def test_gate_not_exercised_falls_back_to_no_nav_blame(tmp_path):
    """点了屏没变：门没被触发 → 按既有 NO_NAV 三分归因走，**不判门失守**。"""
    drv = FakeDrv("PageA", {}, {})                     # tap 不改变屏
    rows, man, _ = run(tmp_path, [gate_step()], drv)
    assert rows[0]["verdict"] == "GATE_NOT_EXERCISED"
    assert man["escalations"][0]["blame"] != "gate_missing_in_hmos"
    assert man["escalations"][0]["verdict"] == "NO_NAV"


# ── 4. 根页守卫：在根上绝不按 BACK ──────────────────────────────────────────
def test_gate_return_respects_root_guard(tmp_path):
    """门本身就是 tab 根（真实存在的形态）时，回位必须让位给根页守卫——
    鸿蒙栈根 BACK 实测致白屏卡前台。"""
    drv = FakeDrv("PageA", {"PageA": "GateX"}, {"GateX": "PageA"})
    rows, _, _ = run(tmp_path, [gate_step()], drv,
                     plan_extra={"roots": [{"node": "PageA", "sentinel": ["判别物A"]},
                                           {"node": "GateX", "sentinel": ["判别物G"]}]})
    assert rows[0]["verdict"] == "GATE_HELD"
    assert rows[0]["gate_return"]["backed"] is False
    assert rows[0]["gate_return"]["why"] == "root_guard"
    assert drv.backs == 0


# ── 5. 无锚点到达 ───────────────────────────────────────────────────────────
UNANCH = {"step": 1, "action": "tap", "from": "PageA", "to": "PageC",
          "match": {"primary": "入口丙", "rid": "ctlC", "source": "android_runtime"},
          "wait_budget_s": 0.1, "safety": "normal", "probe_only": True,
          "expect": {"kind": "push", "sentinel": [], "arrival_confidence": "unanchored"}}


def test_unanchored_arrival_is_weak_not_failure(tmp_path):
    """目标页没哨兵 → 只要屏变了/落到别的页就按弱到达入账；**绝不因此交接**。"""
    drv = FakeDrv("PageA", {"PageA": "Unknown"}, {"Unknown": "PageA"})
    rows, man, code = run(tmp_path, [dict(UNANCH)], drv,
                          plan_extra={"node_sentinels": dict(BASE_PLAN["node_sentinels"],
                                                             PageC=[])})
    assert rows[0]["verdict"] == "ARRIVED_unanchored"
    assert rows[0]["position_confidence"] == "low"
    assert code in (0, None) and man["escalations"] == []
    ps = man["pages_status"]["PageC"]
    assert ps["status"] == "captured_weak" and ps["position_confidence"] == "low"


def test_unanchored_landing_elsewhere_is_not_wrong_landing(tmp_path):
    """落到别的**已知**页也算弱到达：目标页长什么样我们根本不知道，判「去错页」没有依据。"""
    drv = FakeDrv("PageA", {"PageA": "PageB"}, {"PageB": "PageA"})
    rows, man, _ = run(tmp_path, [dict(UNANCH)], drv,
                       plan_extra={"node_sentinels": dict(BASE_PLAN["node_sentinels"],
                                                          PageC=[])})
    assert rows[0]["verdict"] == "ARRIVED_unanchored"
    assert not any(e["verdict"] == "WRONG_LANDING" for e in man["escalations"])


def test_unanchored_no_screen_change_still_goes_no_nav(tmp_path):
    """屏没变仍走既有 NO_NAV（排除项照旧）——只是**不交接**，因为探测步没动过位置。"""
    drv = FakeDrv("PageA", {}, {})
    rows, man, code = run(tmp_path, [dict(UNANCH)], drv,
                          plan_extra={"node_sentinels": dict(BASE_PLAN["node_sentinels"],
                                                             PageC=[])})
    assert rows[0]["verdict"] == "NO_NAV"
    assert code in (0, None)
    assert rows[0]["handoff_suppressed"].startswith("probe_only")
    assert man["escalations"][0]["verdict"] == "NO_NAV"


def test_probe_control_missing_records_blame_but_does_not_abort(tmp_path):
    """探测步找不到控件：归因照记（缺陷候选一条不漏），但绝不为一条计划外探测中止整趟。"""
    step = dict(UNANCH, match={"primary": "不存在的控件", "rid": "ctlZZ", "source": "android_runtime"})
    drv = FakeDrv("PageA", {}, {})
    rows, man, code = run(tmp_path, [step], drv,
                          plan_extra={"node_sentinels": dict(BASE_PLAN["node_sentinels"],
                                                             PageC=[])})
    assert rows[0]["verdict"] == "ABANDON_no_match"
    assert code in (0, None) and man["escalations"]
    assert rows[0]["handoff_suppressed"].startswith("probe_only")


# ── 6. 探测回位步：只在真进去了才按 BACK ────────────────────────────────────
def test_probe_return_back_skipped_when_probe_never_arrived(tmp_path):
    """☠️ 探测没进去还按 BACK，会把**真正的 DFS 位置**带跑（首跑那场级联事故的形状）。"""
    back = {"step": "1B", "action": "back", "from": "PageC", "to": "PageA",
            "kind": "push", "probe_return": True, "probe_from": "PageC"}
    drv = FakeDrv("PageA", {}, {})
    rows, _, _ = run(tmp_path, [dict(UNANCH), back], drv,
                     plan_extra={"node_sentinels": dict(BASE_PLAN["node_sentinels"], PageC=[])})
    assert rows[1]["verdict"] == "SKIP_probe_no_arrival"
    assert drv.backs == 0


def test_probe_return_back_runs_when_probe_arrived(tmp_path):
    back = {"step": "1B", "action": "back", "from": "PageC", "to": "PageA",
            "kind": "push", "probe_return": True, "probe_from": "PageC"}
    drv = FakeDrv("PageA", {"PageA": "PageC"}, {"PageC": "PageA"})
    rows, _, _ = run(tmp_path, [dict(UNANCH), back], drv,
                     plan_extra={"node_sentinels": dict(BASE_PLAN["node_sentinels"], PageC=[])})
    assert rows[0]["verdict"].startswith("ARRIVED")
    assert rows[1]["verdict"].startswith("BACK_") and drv.backs == 1
    assert drv.cur == "PageA"


# ── 7. 老计划零回归：没有新字段的步，走法一字不变 ───────────────────────────
def test_plain_tap_without_new_fields_unchanged(tmp_path):
    plain = {"step": 1, "action": "tap", "from": "PageA", "to": "PageB",
             "match": {"primary": "入口甲", "rid": "ctlB", "source": "runtime"},
             "wait_budget_s": 0.1, "expect": {"kind": "push", "sentinel": ["判别物B"]}}
    drv = FakeDrv("PageA", {"PageA": "PageB"}, {"PageB": "PageA"})
    rows, man, code = run(tmp_path, [plain], drv)
    assert rows[0]["verdict"] == "ARRIVED_strong"
    assert "gate_verdict" not in rows[0] and man["escalations"] == []
    assert drv.backs == 0
