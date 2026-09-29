#!/usr/bin/env python3
"""鸿蒙回放执行器的「放行门」（gate_pass）—— 2026-09-10 补齐。

病：安卓 2026-09-09 新增的 gate_pass 只落在 walk_exec.py，replay_exec.py 零处接这个 action
    → 指令掉进 tap 兜底（无 match → tried:[] → ABANDON_no_match），首启协议门一直挡着，
      真机实测 102 步只走了 8 步。
治：本文件锁死三件事——① 词表单一真源（lib_ui_words，两端同一张表）；
    ② 三道判据同时成立才点、选不出走交接；③ **鸿蒙特有陷阱**：放行键 Text 节点 clickable=false、
    拒绝键 Text 节点 clickable=true（真机 dump 实证），照搬安卓的 clickable 扫描会只匹配到拒绝键。

夹具纪律：所有 app 侧文案一律占位串（PageA / GateDlg / 占位正文…），
    只有**词表本身的跨项目词**（同意并继续 / 不同意 / 服务协议 …）按真值出现——它们不是 app 常量。
"""
import json
import os
import sys

import pytest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)

import lib_ui_words as W      # noqa: E402
import replay_exec as R       # noqa: E402

W_OK = W.UI_WORDS_DEFAULT["GATE_TEXT_OK"]          # 放行白名单（词表真源，不复制）
BODY_FILLER = "占位正文：服务协议与隐私政策条款说明，占位占位。"   # 门语义靠 GATE_BODY_RE 的通用词


# ── dump 夹具（照 now.json 真实结构：root.attributes.bounds 定屏高，容器 clickable/文案在子 Text）──
def node(type_, bounds, text="", clickable=False, key="", children=()):
    a = {"type": type_, "bounds": "[%d,%d][%d,%d]" % bounds,
         "clickable": "true" if clickable else "false"}
    if text:
        a["text"] = text
    if key:
        a["key"] = key
    return {"attributes": a, "children": list(children)}


def screen(*children):
    return json.dumps({"attributes": {"bounds": "[0,0][1320,2856]"}, "children": list(children)},
                      ensure_ascii=False)


def body(text=BODY_FILLER):
    """门正文：真机实测这个 Text 自己也是 clickable=true，照实建。"""
    return node("Text", (140, 1123, 1180, 1557), text=text, clickable=True)


def allow_btn(label="同意并继续", bounds=(247, 1675, 1072, 1830)):
    """★鸿蒙陷阱原样复刻：可点的是外层 Stack（自身无 text），文案在 clickable=false 的子 Text 上。"""
    inner = (bounds[0] + 294, bounds[1] + 49, bounds[2] - 293, bounds[3] - 49)
    return node("Stack", bounds, clickable=True,
                children=[node("Text", inner, text=label, clickable=False)])


def deny_btn(label="不同意"):
    """★拒绝键反过来：Text 节点自己 clickable=true —— 照搬安卓扫 clickable 只会捞到它。"""
    return node("Text", (581, 1896, 739, 1958), text=label, clickable=True)


GATE = screen(body(), allow_btn(), deny_btn())


@pytest.fixture(autouse=True)
def _reset_words():
    yield
    W.load_ui_words("/nonexistent-dir-for-reset")


# ── 1. 词表单一真源 ────────────────────────────────────────────────────────
def test_word_table_is_one_object_shared_by_both_executors():
    import walk_exec as we
    assert we.UI_WORDS is W.UI_WORDS is R.UI_WORDS          # 同一个对象，不是各抄一份
    assert we.UI_WORDS_DEFAULT is W.UI_WORDS_DEFAULT
    assert we.load_ui_words is W.load_ui_words is R.load_ui_words


def test_project_override_reaches_hmos_side(tmp_path):
    """安卓侧的 $EW/ui_words.json 整表覆盖契约，对鸿蒙执行器同样生效（原地改写而非重绑定）。"""
    (tmp_path / "ui_words.json").write_text(
        json.dumps({"GATE_TEXT_OK": ["Accept all"]}), encoding="utf-8")
    en = screen(body("Terms of Service and privacy notice"),
                allow_btn("Accept all"), deny_btn("Cancel"))
    assert R.choose_gate_control_hmos(en)[0] is None         # 默认词表认不出
    assert W.load_ui_words(str(tmp_path)) == ["GATE_TEXT_OK"]
    assert R.choose_gate_control_hmos(en)[0]["label"] == "Accept all"


# ── 2. 正常放行 ────────────────────────────────────────────────────────────
def test_normal_gate_pass_picks_the_allow_control():
    choice, diag = R.choose_gate_control_hmos(GATE)
    assert diag["why"] == "ok"
    assert choice["label"] == "同意并继续" and choice["label"] in W_OK
    assert choice["center"] == (659, 1752)                   # 点的是**容器**中心（子 Text 不可点）


def test_allow_control_is_found_despite_unclickable_text_node():
    """★鸿蒙特有陷阱的正面断言：放行键的 Text 节点 clickable=false，仍必须被选出来。"""
    inner = json.loads(GATE)["children"][1]["children"][0]["attributes"]
    assert inner["text"] == "同意并继续" and inner["clickable"] == "false"
    assert R.choose_gate_control_hmos(GATE)[0]["label"] == "同意并继续"


# ── 3. 否定键在场时绝不误点（本次最承重的一条）─────────────────────────────
def test_negative_control_is_never_chosen_even_though_it_is_the_clickable_one():
    deny = json.loads(GATE)["children"][2]["attributes"]
    assert deny["text"] == "不同意" and deny["clickable"] == "true"   # 它才是 clickable 的那个
    choice, diag = R.choose_gate_control_hmos(GATE)
    assert choice["label"] != "不同意"
    assert "不同意" in diag["deny"] and "不同意" not in diag["allow"]


@pytest.mark.parametrize("neg", ["不同意", "拒绝", "取消", "退出", "Disagree", "Cancel", "稍后"])
def test_negative_only_screen_never_taps_anything(neg):
    """屏上只剩否定键 → 必须**选不出**，绝不退而求其次点它（点了=拒绝协议+消费一次性门）。"""
    choice, diag = R.choose_gate_control_hmos(screen(body(), deny_btn(neg)))
    assert choice is None and diag["why"] == "no_allow_control"
    assert neg in diag["deny"]


def test_negative_filter_runs_before_whitelist():
    """词表交集词（如「取消」既在 CANCEL_TEXT_OK 又被 GATE_TEXT_NO 命中）必须判 deny：
    否定过滤排在白名单匹配之前，顺序反了就会点错键。"""
    _c, diag = R.choose_gate_control_hmos(screen(body(), allow_btn("取消"), deny_btn()))
    assert [c for c in diag["candidates"] if c["text"] == "取消"][0]["verdict"] == "deny"


def test_destructive_word_on_control_is_denied():
    """控件级破坏词闸（用只在 DESTRUCTIVE_RE、不在 GATE_BODY_NO 里的词，才测得到这一层）。"""
    _c, diag = R.choose_gate_control_hmos(screen(body(), allow_btn("解绑")))
    assert diag["why"] == "no_allow_control" and "解绑" in diag["deny"]


def test_destructive_word_on_control_id_is_denied():
    """id 命中 GATE_ID_RE 也救不了带破坏词的控件——安卓 `DESTRUCTIVE_RE.search(short)` 平移。"""
    btn = node("Button", (247, 1675, 1072, 1830), text="解绑", clickable=True, key="btn_confirm")
    _c, diag = R.choose_gate_control_hmos(screen(body(), btn))
    assert diag["why"] == "no_allow_control" and "解绑" in diag["deny"]


# ── 4. 正文不像门就不点 ────────────────────────────────────────────────────
def test_body_without_gate_semantics_is_not_a_gate():
    plain = screen(node("Text", (0, 300, 900, 400), text="占位正文：随便一段说明"),
                   allow_btn("确定"))
    choice, diag = R.choose_gate_control_hmos(plain)
    assert choice is None and diag["why"] == "body_not_gate"


def test_destructive_body_blocks_the_confirm_button():
    """安卓 chunk2 的老账平移：退出登录确认窗的「确定」绝不能被当门放行。"""
    dlg = screen(node("Text", (0, 300, 900, 400), text="确认退出登录？隐私数据将清除"),
                 allow_btn("确定"))
    choice, diag = R.choose_gate_control_hmos(dlg)
    assert choice is None and diag["why"] == "body_has_destructive"


def test_empty_dump_is_not_a_gate():
    assert R.choose_gate_control_hmos("")[1]["why"] == "empty_dump"
    assert R.choose_gate_control_hmos("{ not json")[1]["why"] == "empty_dump"


# ── 5. 候选多于一个 → 交接；容器/子控件同文案 → 去重后仍算一个 ───────────────
def test_two_different_allow_controls_escalate():
    two = screen(body(), allow_btn("同意并继续"),
                 allow_btn("我知道了", bounds=(247, 1900, 1072, 2055)))
    choice, diag = R.choose_gate_control_hmos(two)
    assert choice is None and diag["why"] == "multiple_allow_controls"
    assert sorted(diag["allow"]) == ["同意并继续", "我知道了"]


def test_container_and_child_with_same_label_count_as_one_and_inner_wins():
    """整弹窗容器也 clickable 时，下钻会让容器与按钮拿到同一文案。
    同文案 + 几何包含 = 同一个逻辑控件，合并并取更内层的那个，不算歧义。"""
    outer = node("Column", (100, 1600, 1200, 1900), clickable=True,
                 children=[allow_btn()])
    dup = screen(body(), outer)
    choice, diag = R.choose_gate_control_hmos(dup)
    assert diag["why"] == "ok" and choice["center"] == (659, 1752)   # 内层按钮，不是外层容器


# ── 6. 交接包带候选清单 ────────────────────────────────────────────────────
def test_handoff_extra_carries_every_on_screen_candidate():
    _c, diag = R.choose_gate_control_hmos(screen(body(), deny_btn()))
    extra = R.gate_handoff_extra(diag)
    assert extra["gate_reason"] == "no_allow_control"
    assert any("不同意" in x for x in extra["gate_candidates"])
    assert extra["gate_denied_candidates"] == ["不同意"]
    assert "不猜" in extra["diagnosis_gate"] and "绝不点否定键" in extra["diagnosis_gate"]


# ── 7. 整条分发链（端到端跑 main()，零设备）─────────────────────────────────
class FakeDev:
    """屏幕按 tap 前进一格；不给下一屏就代表『点了没变化』。"""

    def __init__(self, screens):
        self.screens = list(screens)
        self.i = 0
        self.taps = []
        self.backs = 0
        self.shells = []
        self.shots = []

    def dump_layout(self, path=None):
        return self.screens[min(self.i, len(self.screens) - 1)]

    def tap(self, x, y):
        self.taps.append((x, y))
        self.i = min(self.i + 1, len(self.screens) - 1)

    def back(self):
        self.backs += 1

    def shell(self, *a, **k):
        self.shells.append(a)
        return ""

    def screencap(self, p):
        open(p, "wb").write(b"\xff\xd8fake")
        self.shots.append(p)
        return p


GATE_STEP = {"step": 3, "from": "GateDlg", "to": "PageA", "action": "gate_pass", "kind": "dialog",
             "note": "放行门：执行器按放行词表点唯一放行控件后验回起点"}


def _plan(steps=(GATE_STEP,), sentinels=None):
    return {"app": {"bundle": "com.x"}, "safety": {"blacklist": []},
            "roots": [{"node": "PageA", "sentinel": ["占位首页标题"]}],
            "coverage_targets": ["PageA"],
            "node_sentinels": sentinels if sentinels is not None else {"PageA": ["占位首页标题"]},
            "steps": list(steps)}


def run_main(tmp_path, monkeypatch, plan, screens, argv=()):
    planp = tmp_path / "replay_plan_hmos.json"
    planp.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "trip_1"
    dev = FakeDev(screens)
    monkeypatch.setattr(R, "DeviceAdapter", lambda *a, **k: dev)
    monkeypatch.setattr(R.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["replay_exec.py", "--plan", str(planp), "--serial", "fake",
                                      "--bundle", "com.x", "--ability", "Entry",
                                      "--out-dir", str(out), *argv])
    code = None
    try:
        R.main()
    except SystemExit as e:
        code = e.code
    rows = [json.loads(x) for x in open(out / "run.jsonl", encoding="utf-8") if x.strip()]
    man = json.load(open(out / "capture_manifest.json", encoding="utf-8"))
    cp = (json.load(open(out / "checkpoint.json", encoding="utf-8"))
          if os.path.exists(out / "checkpoint.json") else None)
    return dev, rows, man, cp, code


LANDED = screen(node("Text", (0, 400, 900, 500), text="占位首页标题"))


def test_dispatch_taps_the_allow_control_and_lands(tmp_path, monkeypatch):
    dev, rows, man, cp, code = run_main(tmp_path, monkeypatch, _plan(), [GATE, LANDED])
    assert code is None and len(dev.taps) == 1
    assert dev.taps[0] == (659, 1752)                       # 放行键容器中心，不是「不同意」的 (660,1927)
    assert rows[0]["verdict"] == "GATE_PASSED" and rows[0]["landed"] == "PageA"
    assert man["gates"][0]["label"] == "同意并继续"
    assert man["pages_status"]["PageA"]["status"] == "captured"


def test_dispatch_never_taps_the_negative_control(tmp_path, monkeypatch):
    """屏上只有否定键 → 一次 tap 都不许发，直接交接。"""
    dev, rows, man, cp, code = run_main(
        tmp_path, monkeypatch, _plan(), [screen(body(), deny_btn()), LANDED])
    assert dev.taps == [] and code == 32
    assert rows[0]["verdict"] == "GATE_PASS_UNKNOWN"
    assert man["escalations"][0]["reason"] == "gate_pass_unknown"
    assert man["escalations"][0]["blame"] == "gate_pass_needs_human"
    assert cp["gate_reason"] == "no_allow_control"
    assert any("不同意" in x for x in cp["gate_candidates"])   # ★交接包带候选清单


def test_dispatch_escalates_when_two_allow_controls(tmp_path, monkeypatch):
    two = screen(body(), allow_btn("同意并继续"), allow_btn("我知道了", bounds=(247, 1900, 1072, 2055)))
    dev, rows, _man, cp, code = run_main(tmp_path, monkeypatch, _plan(), [two, LANDED])
    assert dev.taps == [] and code == 32
    assert cp["gate_reason"] == "multiple_allow_controls"
    assert sorted(cp["gate_allow_candidates"]) == ["同意并继续", "我知道了"]


def test_dispatch_escalates_when_gate_still_on_screen_after_tap(tmp_path, monkeypatch):
    """点了、门还在 → 落点验不到，走交接；绝不静默继续（那正是 0910 连锁失败的形态）。"""
    dev, rows, man, cp, code = run_main(tmp_path, monkeypatch, _plan(), [GATE])
    assert dev.taps == [(659, 1752)] and code == 32
    assert rows[0]["verdict"] == "GATE_PASS_UNVERIFIED" and rows[0]["gate_gone"] is False
    assert cp["gate_still_on_screen"] is True and cp["tapped_control"] == "同意并继续"


def test_dispatch_weak_pass_when_gate_gone_but_identity_unconfirmed(tmp_path, monkeypatch):
    """门消失 + 屏已变，但哨兵/identify 认不出落点（鸿蒙侧哨兵命中率实测极低）：
    按弱到达如实入账并继续，不冤枉地熔断。"""
    unknown = screen(node("Text", (0, 400, 900, 500), text="占位：认不出的页"))
    dev, rows, man, cp, code = run_main(
        tmp_path, monkeypatch, _plan(sentinels={"PageA": ["占位首页标题"]}), [GATE, unknown])
    assert code is None and dev.taps == [(659, 1752)]
    assert rows[0]["verdict"] == "GATE_PASSED_weak" and rows[0]["gate_gone"] is True
    assert man["pages_status"]["PageA"]["status"] == "captured_weak"


def test_dispatch_no_longer_falls_through_to_tap_abandon(tmp_path, monkeypatch):
    """回归闸：0910 真机的原始症状是 gate_pass 掉进 tap 兜底、`tried: []`。"""
    _dev, rows, _man, _cp, _code = run_main(tmp_path, monkeypatch, _plan(), [GATE, LANDED])
    assert rows[0]["verdict"] != "ABANDON_no_match" and "tried" not in rows[0]
