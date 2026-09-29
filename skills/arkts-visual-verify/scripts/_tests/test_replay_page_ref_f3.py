#!/usr/bin/env python3
"""F3 / F1 / F4（2026-09-12，replay-t1g 完整跑法归因后用户定稿）——执行器整段跑（假设备，零 hdc）。

  F3 路径先验 + 同平台参考：页一旦本趟采过，「站不站在这页」用鸿蒙自己那份 dump 比（文本集 Jaccard + 同位），
     哨兵词撞页（别页恰好带本页哨兵词）不再被认成本页：不判缺失、算离开源页而押栈、reconcile 不在错页上跑。
  F1 降级模糊匹配落错页 → wrong_landing_after_fuzzy_match（needs_verification），不判 routing_target_wrong。
  F4 back 步已站在目标页上 → 不按 BACK（治被跳过弹窗的配对 back 弹掉真栈）。

夹具/屏/假设备复用 test_replay_gate_probe_and_unanchored（占位串纪律同）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import replay_exec as R  # noqa: E402
from test_replay_gate_probe_and_unanchored import SCREENS, FakeDrv, run, screen, _node, ctrl  # noqa: E402

# 「撞词页」：带 PageA 的哨兵词「判别物A」（位置不同），其余文本全是别的 —— 客服 H5 常见问题带「一键退款」的形状
SCREENS["PageQ"] = screen(_node("Text", (100, 1900, 1200, 2000), text="判别物A"),
                          _node("Text", (100, 200, 1200, 300), text="无人认领的标题"),
                          _node("Text", (100, 400, 1200, 500), text="常见问题一"),
                          _node("Text", (100, 600, 1200, 700), text="常见问题二"),
                          _node("Text", (100, 800, 1200, 900), text="常见问题三"),
                          ctrl("返回占位", "kBack", 1200))


def _tap(step, frm, to, prim, rid, kind="push", sentinel=None, **extra):
    st = {"step": step, "action": "tap", "from": frm, "to": to,
          "match": {"primary": prim, "rid": rid, "source": "runtime"},
          "wait_budget_s": 0.1, "safety": "normal",
          "expect": {"kind": kind, "sentinel": sentinel if sentinel is not None else [f"判别物{to[-1]}"]}}
    st.update(extra)
    return st


def _row(rows, step):
    return next(x for x in rows if str(x.get("step")) == str(step))


COLD = {"step": 1, "action": "coldstart", "to": "PageA"}


# ── 纯函数 ───────────────────────────────────────────────────────────────────
def test_on_page_by_ref_separates_collision_from_same_page():
    ta, pa = R.texts_pos(SCREENS["PageA"]); ref = {"texts": ta, "pos": pa, "n": len(ta)}
    assert R.on_page_by_ref(ref, *R.texts_pos(SCREENS["PageA"])) is True
    assert R.on_page_by_ref(ref, *R.texts_pos(SCREENS["PageQ"])) is False        # 只共一个哨兵词、位置还不同
    assert R.on_page_by_ref(ref, *R.texts_pos(SCREENS["PageC"])) is False
    assert R.on_page_by_ref(None, ta, pa) is None                                  # 没参考 → 不下判
    # toast 形：本页全部文案都在、多一条提示 → 仍在本页
    assert R.on_page_by_ref(ref, *R.texts_pos(SCREENS.get("PageA_toast", SCREENS["PageA"]))) is True


# ── F3：撞词页不判缺失、押栈 ───────────────────────────────────────────────────
def test_collision_page_is_not_confirmed_source_page(tmp_path):
    """站在带 A 哨兵词的别页上找 A 的控件：哨兵说在 A，参考说不在 → source_page_unconfirmed，不出 P0。"""
    steps = [COLD,
             _tap(2, "PageA", "PageC", "入口丙", "ctlC"),                # 点了却落到撞词页 PageQ
             _tap(3, "PageA", "PageB", "入口甲", "ctlB")]                # 在 PageQ 上找 A 的入口甲 → 找不到
    drv = FakeDrv("PageA", {"PageA": "PageQ"}, back_to={"PageQ": "PageA"})
    rows, man, code = run(tmp_path, steps, drv)
    r2 = _row(rows, 2)
    assert r2["verdict"] == "ARRIVED_weak" and r2["identified_as"] == "PageA" and r2["stack"] == 1   # 参考说离开了源页 → 押栈
    e = [x for x in man["escalations"] if x["step"] == 3][0]
    assert e["blame"] == "source_page_unconfirmed" and e["product_defect"] is None and e["needs_verification"] is True
    assert e["sentinel_said"] == "PageA" and e["source_ref_jaccard"] < 0.15


def test_genuine_source_page_still_confirms_control_missing(tmp_path):
    """真站在 A 上找不到有文案的控件 → 仍是 control_missing（回归护栏），且标 source_confirmed_by=reference。"""
    rows, man, code = run(tmp_path, [COLD, _tap(2, "PageA", "PageB", "无此控件占位", "ctlZ")], FakeDrv("PageA", {}))
    e = man["escalations"][0]
    assert e["blame"] == "control_missing_in_hmos" and e["source_confirmed_by"] == "reference"


# （reconcile 站位的参考判据没有独立整段用例：假设备上 reconcile 一到页就被 _arm_reconcile 结清，
#   撞词页上"仍欠账"的状态构造不出来；该分支由 t1g 121 份 dump 离线回放 + 上面的纯函数用例覆盖。）


# ── F4：back 步已在目标页不按 ────────────────────────────────────────────────
def test_back_skipped_when_already_standing_on_target(tmp_path):
    steps = [COLD,
             _tap(2, "PageA", "PageC", "入口丙", "ctlC"),
             {"step": 3, "action": "skip", "from": "PageC", "to": "PageD", "skip_reason": "android_unreached"},
             {"step": 4, "action": "back", "from": "PageD", "to": "PageC", "kind": "push"},     # 弹窗/子页没进去，人还在 C
             {"step": 5, "action": "back", "from": "PageC", "to": "PageA", "kind": "push"}]
    drv = FakeDrv("PageA", {"PageA": "PageC"}, back_to={"PageC": "PageA"})
    rows, man, code = run(tmp_path, steps, drv)
    assert _row(rows, 4)["verdict"] == "SKIP_back_already_at_target" and _row(rows, 4)["stack"] == 1
    assert _row(rows, 5)["verdict"] == "BACK_OK" and drv.backs == 1
    assert drv.cur == "PageA"


def test_back_still_pressed_on_collision_page(tmp_path):
    """站在撞词页上、back 目标是 A：参考说不在 A → 照按 BACK（t1g 步 62 客服 H5 的形状）。"""
    steps = [COLD, _tap(2, "PageA", "PageC", "入口丙", "ctlC"),
             {"step": 3, "action": "back", "from": "PageC", "to": "PageA", "kind": "push"}]
    drv = FakeDrv("PageA", {"PageA": "PageQ"}, back_to={"PageQ": "PageA"})
    rows, man, code = run(tmp_path, steps, drv)
    assert _row(rows, 3)["verdict"] == "BACK_OK" and drv.backs == 1 and drv.cur == "PageA"


# ── F1：模糊匹配落错页不判路由错 ───────────────────────────────────────────────
def test_wrong_landing_after_fuzzy_match_is_not_routing_defect(tmp_path):
    st = _tap(1, "PageA", "PageB", "入口甲丁", "ctlNoSuch")           # 只能字重叠到「入口甲」
    rows, man, code = run(tmp_path, [st], FakeDrv("PageA", {"PageA": "PageC"}))
    r = _row(rows, 1)
    assert r["verdict"] == "WRONG_LANDING" and r["matched_by"] not in ("text_strict", "rid_token")
    e = man["escalations"][0]
    assert e["blame"] == "wrong_landing_after_fuzzy_match" and e["product_defect"] is None


def test_wrong_landing_after_strict_match_still_routing_defect(tmp_path):
    rows, man, code = run(tmp_path, [_tap(1, "PageA", "PageB", "入口甲", "ctlB")], FakeDrv("PageA", {"PageA": "PageC"}))
    e = man["escalations"][0]
    assert e["blame"] == "routing_target_wrong" and e["product_defect"] is True and "fuzzy_match" in e["exclusions_checked"]


# ── 续跑重建参考（t1h 验收实爆：PAGE_REF 只活在进程内存）────────────────────────
def test_resume_restores_page_refs_from_manifest_dumps(tmp_path):
    steps = [COLD, _tap(2, "PageA", "PageC", "入口丙", "ctlC"),
             {"step": 3, "action": "tap", "from": "PageC", "to": "PageB", "match": {"primary": "无此控件占位", "rid": "ctlZ", "source": "runtime"},
              "wait_budget_s": 0.1, "safety": "normal", "expect": {"kind": "push", "sentinel": ["判别物B"]}, "probe_only": True}]
    # 第一段：采到 PageA / PageC
    rows1, man1, code1 = run(tmp_path, steps[:2], FakeDrv("PageA", {"PageA": "PageC"}))
    assert man1["pages_status"]["PageC"]["status"] == "captured"
    # 第二段（新进程）：站在撞词页 PageQ 上找 PageC 的控件 → 参考从 dump 读回 → 不许判"确认站在 PageC"
    drv2 = FakeDrv("PageQ", {})
    rows2, man2, code2 = run(tmp_path, steps, drv2, argv_extra=("--resume-from", "3"))
    rr = next(x for x in rows2 if x.get("verdict") == "PAGE_REF_RESTORED")
    assert "PageA" in rr["nodes"] and "PageC" in rr["nodes"]
    e = [x for x in man2["escalations"] if x["step"] == 3][0]
    assert e["blame"] in ("source_page_unconfirmed", "wrong_position_not_source_page")
    assert e["blame"] != "control_missing_in_hmos"


def test_back_for_skipped_dialog_is_skipped_by_stack_top(tmp_path):
    """被跳过弹窗的配对 back（kind=dialog）：栈顶就是 back 目标 → 不按（t1g/t1h 步 20 真退出会员中心的病）。"""
    steps = [COLD, _tap(2, "PageA", "PageC", "入口丙", "ctlC"),
             {"step": 3, "action": "skip", "from": "PageC", "to": "DlgX", "skip_reason": "android_unreached"},
             {"step": 4, "action": "back", "from": None, "to": "PageC", "kind": "dialog"},
             {"step": 5, "action": "back", "from": "PageC", "to": "PageA", "kind": "push"}]
    drv = FakeDrv("PageA", {"PageA": "PageC"}, back_to={"PageC": "PageA"})
    rows, man, code = run(tmp_path, steps, drv)
    r4 = _row(rows, 4)
    assert r4["verdict"] == "SKIP_back_already_at_target" and r4["by"] == "stack" and r4["stack"] == 1
    assert _row(rows, 5)["verdict"] == "BACK_OK" and drv.backs == 1 and drv.cur == "PageA"


def test_back_for_open_dialog_still_pressed(tmp_path):
    """真进了弹窗（栈顶=弹窗节点）的配对 back：照按。"""
    SCREENS["PageE"] = screen(_node("Text", (100, 200, 1200, 300), text="判别物E"), ctrl("打开弹窗占位", "kOpen", 1000))
    SCREENS["DlgX"] = screen(_node("Text", (100, 200, 1200, 300), text="判别物E"), ctrl("打开弹窗占位", "kOpen", 1000),
                             _node("Text", (100, 1300, 1200, 1400), text="弹窗占位标题"), ctrl("关闭占位", "kClose", 1500))
    ns = {"PageA": ["判别物A"], "PageB": ["判别物B"], "PageC": ["判别物C"], "GateX": ["判别物G"],
          "PageE": ["判别物E"], "DlgX": ["弹窗占位标题"]}
    steps = [COLD, _tap(2, "PageA", "PageE", "入口丙", "ctlC"),
             _tap(3, "PageE", "DlgX", "打开弹窗占位", "kOpen", kind="dialog", sentinel=["弹窗占位标题"]),
             {"step": 4, "action": "back", "from": "DlgX", "to": "PageE", "kind": "dialog"}]
    drv = FakeDrv("PageA", {"PageA": "PageE", "PageE": "DlgX"}, back_to={"DlgX": "PageE"})
    rows, man, code = run(tmp_path, steps, drv, plan_extra={"coverage_targets": ["PageA", "PageE", "DlgX"], "node_sentinels": ns})
    assert _row(rows, 3)["verdict"].startswith("ARRIVED") and _row(rows, 3)["stack"] == 2
    assert _row(rows, 4)["verdict"] == "BACK_OK" and drv.cur == "PageE"
