#!/usr/bin/env python3
"""test_codex_merged_logic_0915.py —— 阶段 D1 三方合并把 **codex 原产物独有的两组逻辑**
并回本产物后的最小回归闸（合成夹具，零设备、零真实工程）。

被测两组（源侧至今没有，只在 codex 产物里活着；REPORT_B ⑧-1 点名）：
  A. `round_budget.py`  —— `DEBT_DISPOSITIONS` / `count_debt()` / `read_round_state()`
     治「把没测到写成终态单 → 它从待办里消失 → 缺页越多账面越干净」。
  B. `compile_replay_plan.py` —— `EDGE_STATUS_UNTAPPABLE` / `_ABSENT_MARKERS` /
     `_STACK_LOST_MARKERS` / `edge_untappable()` / `build_status_index()` / `overlay_edge_notes()`
     治「安卓白纸黑字写着控件不存在，编译出来照样 tap」与它的反面「拿我没走到当它不存在」。

跑: python3 _tests/test_codex_merged_logic_0915.py      （也可被 pytest 收）
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
sys.path.insert(0, str(SCRIPTS))

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f"\n       {detail}" if detail and not cond else ""))


# ───────────────────────── A. round_budget 债单 ─────────────────────────
def case_a_debt():
    rb = importlib.import_module("round_budget")
    with tempfile.TemporaryDirectory() as td:
        cwd = os.getcwd()
        os.chdir(td)
        try:
            d = pathlib.Path("spec/fix/round-3/ui"); d.mkdir(parents=True)
            # 一条真 fixed（终态、非债）+ 两条债单（终态、但代表"没测到"）
            (d / "a.md").write_text("---\ndisposition: fixed\n---\n正文\n", encoding="utf-8")
            (d / "b.md").write_text("---\ndisposition: pending_upstream_fix\n---\n正文\n", encoding="utf-8")
            (d / "c.md").write_text("---\ndisposition: pending_data_seed\n---\n正文\n", encoding="utf-8")
            open_n, tally = rb.count_open(3)
            check("A1 债单不算 open（open=0）", open_n == 0, f"open={open_n} tally={tally}")
            check("A2 count_debt 数出两条债", rb.count_debt(3) == 2, f"debt={rb.count_debt(3)}")

            # verdict_of：open=0 但 debt>0 → 不得 CLEAN_AT_EXIT
            v_clean = rb.verdict_of(1, 3, 0, 0, "ALIGNMENT_CLEAN")
            v_debt = rb.verdict_of(1, 3, 0, 2, "ALIGNMENT_CLEAN")
            v_nogate = rb.verdict_of(1, 3, 0, 0, "NO_ROUND_STATE")
            v_legacy = rb.verdict_of(1, 3, 0)          # 不传整轮结论 = 并入前的两参语义
            check("A3 open=0 debt=0 闸绿 → CLEAN_AT_EXIT", v_clean == "CLEAN_AT_EXIT", v_clean)
            check("A4 open=0 但 debt=2 → 不得 CLEAN_AT_EXIT", v_debt == "OPEN_REMAIN", v_debt)
            check("A5 open=0 但没跑整轮闸 → 不得 CLEAN_AT_EXIT", v_nogate == "OPEN_REMAIN", v_nogate)
            check("A6 两参老签名行为不变（向后兼容）", v_legacy == "CLEAN_AT_EXIT", v_legacy)
            check("A7 预算耗尽仍压过一切", rb.verdict_of(3, 3, 5, 0, "ALIGNMENT_CLEAN") == "BUDGET_EXHAUSTED")

            # read_round_state：没有整轮账本 → None（拒绝给结论的前提）
            check("A8 无整轮账本 → read_round_state 返回 None", rb.read_round_state(3) is None)
            check("A9 ROUND_STATE：无账本 = ROUND_UNVERIFIED",
                  rb.round_state_of(None, 0, 0) == "ROUND_UNVERIFIED")
            check("A10 ROUND_STATE：闸绿但有债 = ACCOUNTED_WITH_DEBT",
                  rb.round_state_of({"verdict": "ALIGNMENT_CLEAN"}, 0, 2) == "ACCOUNTED_WITH_DEBT")
            check("A11 ROUND_STATE：闸自己没绿照原样透出",
                  rb.round_state_of({"verdict": "ROUND_INCOMPLETE"}, 0, 0) == "ROUND_INCOMPLETE")
        finally:
            os.chdir(cwd)


# ─────────────────── B. compile_replay_plan 编译期降级闸 ───────────────────
def case_b_edge_gate():
    crp = importlib.import_module("compile_replay_plan")
    eu = crp.edge_untappable
    # ① 控件实测不存在 → 跳
    drop, why = eu("not_reproduced", "the live Splash dialog has no 进入首页 control")
    check("B1 note 写明控件不存在 → 跳", drop and why == "not_reproduced_control_absent", f"{drop} {why}")
    drop, why = eu("not_reproduced", "control_not_found: tv_filter")
    check("B2 control_not_found → 跳", drop and why == "not_reproduced_control_absent", f"{drop} {why}")
    # ② 安卓自己走丢了栈 → 必须保留 tap（拿"我没走到"当"它不存在"是循环论证）
    drop, why = eu("not_reproduced", "parent_stack_lost before the tap")
    check("B3 parent_stack_lost → 保留 tap", (not drop) and why == "not_reproduced_stack_lost", f"{drop} {why}")
    drop, why = eu("not_reproduced", "CreateOutLinePage was absent from the inherited stack")
    check("B4 inherited stack → 保留 tap", (not drop) and why == "not_reproduced_stack_lost", f"{drop} {why}")
    # ③ 说不清 → 保留 tap（不确定一律保留）
    drop, why = eu("not_reproduced", "timeout while waiting")
    check("B5 note 说不清 → 保留 tap", (not drop) and why == "not_reproduced_unclassified", f"{drop} {why}")
    drop, why = eu("not_reproduced", "")
    check("B6 note 为空 → 保留 tap", (not drop) and why == "not_reproduced_unclassified", f"{drop} {why}")
    # ④ 结构性外部触发 → 跳
    drop, why = eu("deferred_structural_external_trigger", "")
    check("B7 push/桌面快捷方式拉起的边 → 跳",
          drop and why == "deferred_structural_external_trigger", f"{drop} {why}")
    # ⑤ confirmed / 其它状态 → 不跳
    check("B8 confirmed 边不受影响", eu("confirmed", "anything") == (False, ""))
    check("B9 状态缺失不受影响", eu(None, "has no X control") == (False, ""))

    # build_status_index：全收（不只 confirmed），note 一并带出
    tree = {"pages": [{"id": "P2", "inbound_triggers": [
        {"from_page": "P1", "trigger_label": "进入首页",
         "runtime": {"status": "not_reproduced", "note": "has no 进入首页 control"}},
    ]}], "dialogs": [], "fragments": []}
    sidx = crp.build_status_index(tree)
    check("B10 status 索引收下非 confirmed 边",
          sidx.get(("P1", "P2")) == ("not_reproduced", "has no 进入首页 control"), str(sidx))
    check("B11 status 索引建了边级精确键",
          sidx.get(("P1", "P2", "lbl:进入首页"))[0] == "not_reproduced", str(sidx))

    # overlay_edge_notes：树里 note 为空时，从 edge_results.json 叠回来
    tree2 = {"pages": [{"id": "P2", "inbound_triggers": [
        {"from_page": "P1", "trigger_label": "进入首页",
         "runtime": {"status": "not_reproduced", "note": ""}},
    ]}], "dialogs": [], "fragments": []}
    sidx2 = crp.build_status_index(tree2)
    check("B12 树里 note 为空（真实产物 138 条全空）", sidx2[("P1", "P2")][1] == "")
    with tempfile.TemporaryDirectory() as td:
        er = pathlib.Path(td) / "edge_results.json"
        er.write_text(json.dumps([{"from": "P1", "to": "P2", "status": "not_reproduced",
                                   "note": "the live Splash dialog has no 进入首页 control",
                                   "control": {"text": "进入首页"}}], ensure_ascii=False),
                      encoding="utf-8")
        sidx2, n = crp.overlay_edge_notes(sidx2, str(er))
        check("B13 overlay 叠回 note（计数 > 0）", n > 0, f"n={n}")
        check("B14 叠加后判别器才拦得住",
              crp.edge_untappable(*sidx2[("P1", "P2")]) == (True, "not_reproduced_control_absent"),
              str(sidx2[("P1", "P2")]))
        # 文件不存在 / 坏 JSON → 零回归（保持保守放行）
        sidx3 = crp.build_status_index(tree2)
        check("B15 edge_results 缺失 → 不改索引、计数 0",
              crp.overlay_edge_notes(sidx3, str(pathlib.Path(td) / "nope.json")) == (sidx3, 0))
        bad = pathlib.Path(td) / "bad.json"; bad.write_text("{not json", encoding="utf-8")
        check("B16 edge_results 坏 JSON → 不抛、计数 0",
              crp.overlay_edge_notes(sidx3, str(bad))[1] == 0)


def test_codex_merged_logic():          # pytest 壳
    main()
    assert not FAIL, FAIL


def main() -> int:
    print("A. round_budget 债单计数 / 整轮账本交接面")
    case_a_debt()
    print("B. compile_replay_plan 编译期降级闸")
    case_b_edge_gate()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
