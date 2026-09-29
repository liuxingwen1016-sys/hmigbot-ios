#!/usr/bin/env python3
"""B 批（2026-09-12，replay-t2b 归因后用户拍板）：哨兵选词补"必要条件" + 计划外门放行收窄触发面。

  哨兵（compile_replay_plan.build_sentinels）：
    ② 树里是该页**静态文案**的候选优先（动态正文"生成的大纲标题"鸿蒙永不复现 → 0 命中）；
    ③ 回退哨兵集整体落在**另一页**文本里 → 宁空（identify None）+ notes 记账——**默认关闭**（用户拍板只有一页受影响，先不启用）；
    护栏：同屏页（文本集相同）静态文案取并集；通用按钮词（同意/取消/下一步…）不配当哨兵。
    离线：三趟 327 份真实 dump 回放，旧判对零变错，只有 3 份"大纲页被认成 PPT 页"改判正确。
  门（replay_exec）：wait/coldstart 目标没到 **且** 认不出任何计划页 **且** 不站在登录门页（PAGE_REF 参考）
    → 交 choose_gate_control_hmos 三道判据；放行后**同一步**重做到达判定（期望不变）。
    离线：327 份 dump 只在 8 份首启协议门上触发。

夹具纪律：app 侧标识一律占位串；设备全假（复用 test_replay_gate_probe_and_unanchored 的屏/假设备/run）。
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import compile_replay_plan as C  # noqa: E402
from test_replay_gate_probe_and_unanchored import SCREENS, FakeDrv, run, screen, _node, ctrl  # noqa: E402
from test_compile_android_edges_and_gate import _fixture_project, _compile  # noqa: E402

# 计划外门（首启协议形态）：正文带门语义、一个否决键、一个唯一白名单键；没有任何计划页的哨兵
SCREENS["GateU"] = screen(_node("Text", (100, 600, 1200, 700), text="服务协议占位正文"),
                          ctrl("不同意", "kNo", 1500), ctrl("同意并继续", "kYes", 1700))
# 登录门页 GateX 的"变体"：没有哨兵词「判别物G」，但「占位登录键」同位 → 参考判"站在 GateX"；同时带门形态（可被白名单放行）
SCREENS["GateXv"] = screen(ctrl("占位登录键", "ctlLogin", 1000),
                           _node("Text", (100, 600, 1200, 700), text="服务协议占位正文"),
                           ctrl("同意并继续", "kYes", 1700))


def _wait(step, frm, to, budget=0.3):
    return {"step": step, "action": "wait", "from": frm, "to": to, "wait_budget_s": budget,
            "expect": {"kind": "push", "sentinel": [f"判别物{to[-1]}"], "arrival_confidence": "sentinel"}}


def _tap(step, frm, to, prim, rid):
    return {"step": step, "action": "tap", "from": frm, "to": to,
            "match": {"primary": prim, "rid": rid, "source": "runtime"},
            "wait_budget_s": 0.1, "safety": "normal",
            "expect": {"kind": "push", "sentinel": [f"判别物{to[-1]}"]}}


def _row(rows, step):
    return next(x for x in rows if str(x.get("step")) == str(step))


# ── 哨兵选词（纯函数，临时基线目录）────────────────────────────────────────────
def _baseline(tmp_path, pages):
    d = tmp_path / "bl"; d.mkdir()
    for node, texts in pages.items():
        (d / f"{node}.android.xml").write_text(
            "<hierarchy>" + "".join(f'<node text="{t}"/>' for t in texts) + "</hierarchy>", encoding="utf-8")
    return str(d)


PAGES = {
    "PageP": ["静态标题", "动态很长的一句正文甲乙丙丁", "取消", "子集词甲", "子集词乙"],
    "PageR": ["子集词甲", "子集词乙"],                     # 文本集 ⊂ PageP：安卓自己就分不开
    "HostH": ["静态标题二", "动态长句子壹贰叁肆伍", "别的词"],  # 同屏别名对（宿主 / Fragment 文本集相同）
    "FragH": ["静态标题二", "动态长句子壹贰叁肆伍", "别的词"],
    "PageQ": ["孤词"],
}
STATIC = {"PageP": {"静态标题"}, "HostH": set(), "FragH": {"静态标题二"}}


def test_static_text_key_outranks_dynamic_long_text(tmp_path):
    b = _baseline(tmp_path, PAGES)
    old, _, _ = C.build_sentinels(b, None, None, void_contained_fallback=False)
    new, _, _ = C.build_sentinels(b, None, STATIC, void_contained_fallback=False)
    assert old["PageP"][0] == "动态很长的一句正文甲乙丙丁"      # 旧序：稀有度同 → 长者优先（动态正文居首）
    assert new["PageP"][0] == "静态标题"                        # 新序：静态文案居首，候选集不变
    assert set(new["PageP"]) <= set(PAGES["PageP"])


def test_generic_button_words_never_become_sentinels(tmp_path):
    b = _baseline(tmp_path, PAGES)
    old, _, _ = C.build_sentinels(b, None, STATIC, void_contained_fallback=False)
    new, _, _ = C.build_sentinels(b, None, STATIC, void_contained_fallback=False, generic_words={"取消"})
    assert "取消" in old["PageP"] and "取消" not in new["PageP"]
    assert new["PageP"] == ["静态标题", "动态很长的一句正文甲乙丙丁"]   # 其余候选与顺序不受影响


def test_same_screen_pair_shares_union_of_static_texts(tmp_path):
    """树把静态文案只挂在 Fragment 上、宿主为空 → 两页哨兵必须一样，否则 identify 平局判 None（t1i 引导页回退）。"""
    b = _baseline(tmp_path, PAGES)
    new, _, _ = C.build_sentinels(b, None, STATIC)
    assert new["HostH"] == new["FragH"] and new["HostH"][0] == "静态标题二"


def test_contained_fallback_is_kept_by_default_and_voided_only_when_opted_in(tmp_path):
    """必要条件三默认关（用户拍板）：默认调用回退照旧、notes 为空；显式开启才置空并记账。"""
    b = _baseline(tmp_path, PAGES)
    dn = {}
    dflt, _, _ = C.build_sentinels(b, None, STATIC, notes=dn)
    assert set(dflt["PageR"]) == {"子集词甲", "子集词乙"} and dn == {}   # 默认：回退词照旧（站到 PageP 会被认成 PageR，已知）
    notes = {}
    new, _, _ = C.build_sentinels(b, None, STATIC, notes=notes, void_contained_fallback=True)
    assert new["PageR"] == []                                    # 开启：宁空
    assert notes["PageR"]["contained_in"] == ["PageP"] and set(notes["PageR"]["fallback_voided"]) == {"子集词甲", "子集词乙"}
    assert new["HostH"] and new["FragH"]                         # 文本集相同的对不算"另一页"，照旧有哨兵
    assert "HostH" not in notes and "FragH" not in notes
    assert new["PageQ"] == ["孤词"]                              # 独有词页不受影响


def test_default_call_without_static_map_is_old_behaviour(tmp_path):
    b = _baseline(tmp_path, PAGES)
    old, ig, dy = C.build_sentinels(b, None, None, void_contained_fallback=False)
    ref, ig2, dy2 = C.build_sentinels(b, None)
    assert ref == old
    assert ig == ig2 and dy == dy2


def test_compiled_plan_carries_sentinel_notes(tmp_path):
    _fixture_project(tmp_path)
    plan, err = _compile(tmp_path)
    assert isinstance(plan.get("sentinel_notes"), dict)


# ── 计划外门：收窄触发面（假设备整段跑）──────────────────────────────────────
def test_unknown_gate_screen_is_passed_once_and_same_step_arrival_rechecked(tmp_path):
    drv = FakeDrv("GateU", {"GateU": "PageB"})
    rows, man, code = run(tmp_path, [_wait(1, "PageA", "PageB")], drv)
    r = _row(rows, 1)
    assert r["verdict"] == "AUTO_ARRIVED" and r["unplanned_gate_passed"] == "unknown_screen"
    assert len(drv.taps) == 1
    g = man["gates"][0]
    assert g["via"] == "unplanned_gate_pass" and g["label"] == "同意并继续" and g["step"] == 1
    assert man["observed_hmos_only"][0]["kind"] == "unexpected_gate"
    assert glob.glob(str(tmp_path / "out" / "**" / "*unplanned_gate*"), recursive=True)   # 点前留痕
    assert man["pages_status"]["PageB"]["status"] == "captured"


def test_unknown_non_gate_screen_is_not_tapped(tmp_path):
    drv = FakeDrv("Unknown", {"Unknown": "PageB"})
    rows, man, code = run(tmp_path, [_wait(1, "PageA", "PageB")], drv)
    assert _row(rows, 1)["verdict"] == "AUTO_NOT_OBSERVED"
    assert drv.taps == [] and "gates" not in man


def test_known_page_that_is_not_target_does_not_trigger_new_branch(tmp_path):
    """认得出是计划页（PageC）→ 不属于"认不出任何计划页"，新触发面不开（旧判据：非门节点、非模态 → 也不开）。"""
    drv = FakeDrv("PageC", {"PageC": "PageB"})
    rows, man, code = run(tmp_path, [_wait(1, "PageA", "PageB")], drv)
    assert _row(rows, 1)["verdict"] == "AUTO_LANDED_ELSEWHERE" and drv.taps == []


def test_login_gate_page_recognised_by_reference_is_not_passed(tmp_path):
    """站在登录门页（哨兵词没了、但同位参考判得出）→ 不放行；同一屏在没有参考的新进程里会被放行 → 排除条件真在起作用。"""
    steps = [_tap(1, "PageA", "GateX", "入口甲", "ctlB"), _wait(2, "GateX", "PageB")]
    rows1, man1, _ = run(tmp_path, steps[:1], FakeDrv("PageA", {"PageA": "GateX"}))
    assert man1["pages_status"]["GateX"]["status"] == "captured"
    drv2 = FakeDrv("GateXv", {"GateXv": "PageB"})
    rows2, man2, _ = run(tmp_path, steps, drv2, argv_extra=("--resume-from", "2"))
    assert "GateX" in next(x for x in rows2 if x.get("verdict") == "PAGE_REF_RESTORED")["nodes"]
    assert _row(rows2, 2)["verdict"] == "AUTO_NOT_OBSERVED" and drv2.taps == [] and "gates" not in man2
    # 对照：无参考的新进程，同一屏按白名单放行
    drv3 = FakeDrv("GateXv", {"GateXv": "PageB"})
    (tmp_path / "fresh").mkdir()
    rows3, man3, _ = run(tmp_path / "fresh", [_wait(2, "GateX", "PageB")], drv3)
    assert _row(rows3, 2)["verdict"] == "AUTO_ARRIVED" and len(drv3.taps) == 1


def test_coldstart_passes_unknown_gate_inside_polling_loop(tmp_path):
    drv = FakeDrv("GateU", {"GateU": "PageA"})
    rows, man, code = run(tmp_path, [{"step": 1, "action": "coldstart", "to": "PageA"}], drv)
    r = _row(rows, 1)
    assert r["verdict"] == "COLDSTART_OBSERVED" and r["unplanned_gate_passed"] == "unknown_screen"
    assert len(drv.taps) == 1 and man["gates"][0]["via"] == "unplanned_gate_pass"
    assert man["pages_status"]["PageA"]["status"] == "captured"      # 放行后同一循环里判到根页并入账


class _SeqDrv(FakeDrv):
    """先放几帧别的屏（启动图/转场），再回到 cur —— 门是在轮询中途才弹出来的。"""

    def __init__(self, pre, start, on_tap):
        super().__init__(start, on_tap)
        self.pre = list(pre)

    def dump_layout(self, out_local=None):
        return SCREENS[self.pre.pop(0)] if self.pre else SCREENS[self.cur]


def test_coldstart_gate_appearing_after_splash_is_still_passed(tmp_path):
    """t2c 实爆：第一轮屏还是启动图（认不出、也不是门）就把"唯一一次"用掉，门弹出后没人再问。
    现在"最多放行一次"，判据每轮都问：前两帧 Unknown 不放行、第三帧门 → 放行 → 同一循环判到根页。"""
    drv = _SeqDrv(["Unknown", "Unknown"], "GateU", {"GateU": "PageA"})
    rows, man, code = run(tmp_path, [{"step": 1, "action": "coldstart", "to": "PageA"}], drv)
    r = _row(rows, 1)
    assert r["verdict"] == "COLDSTART_OBSERVED" and r["unplanned_gate_passed"] == "unknown_screen"
    assert len(drv.taps) == 1 and drv.taps[0][0] == "GateU"        # 只在门上点了一次，启动图那两帧没点
    assert man["pages_status"]["PageA"]["status"] == "captured"
