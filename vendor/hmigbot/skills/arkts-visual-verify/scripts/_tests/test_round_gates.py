#!/usr/bin/env python3
"""test_round_gates.py —— 整轮闸/出单闸/编译闸的回归测试

每个用例都对应 2026-08-16 round 4-6 事故里的一条**真实**失效路径。
不许删用例；新增失效形态时往后追加。

跑: python3 _tests/test_round_gates.py        （零依赖，自建 fixture，不碰真实工程）

★2026-09-14 自 codex 产物回流源侧时的**裁剪**（任务书：只保留被测对象已搬入的部分）：
  - 删 case_7 / case_8：它们测的是 **codex 侧 `round_budget.py` 独有**的两项能力
      ① `read_round_state()` —— 没有整轮账本就拒绝给结论
      ② `DEBT_DISPOSITIONS` / `count_debt()` —— open=0 但有"债单"时不得 CLEAN_AT_EXIT
    这两项从未回流源侧（源侧 round_budget.py 里没有），**留着就是测一个不存在的功能**。
    ⚠️ 它们治的病（"把没测到写成终态单，缺页越多账面越干净"）源侧**至今没有对应闸** —— 待拍板。
    ★2026-09-15 阶段 D1：这两项已**在本 codex 产物里**用三方合并恢复（源侧仍无），
      等价用例落在同目录 `test_codex_merged_logic_0915.py`（A 组），本文件不重复收。
  - 删 case_11：测 codex 侧 `compile_replay_plan.edge_untappable()`，源侧同名文件没有这个函数，同上。
    ★2026-09-15 阶段 D1 同样已恢复，等价用例见 `test_codex_merged_logic_0915.py`（B 组）。
  - case_9/10/12/13/14/16：`render_report.py` 回流时结论源改成 `round_budget.py end` 的判定
    （见该脚本头注），故这些用例改为先 `seed_verdict()` 造一条 `_state.yaml.last_verdict` 再渲染。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
PY = sys.executable

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f"\n       {detail}" if detail and not cond else ""))


def run(script: str, *args: str) -> tuple[int, str]:
    p = subprocess.run([PY, str(SCRIPTS / script), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


# ───────────────────────── fixture 构造 ─────────────────────────
def mkproj(tmp: pathlib.Path, trips: dict[str, int], delivered: dict[str, list[str]],
           tickets: list[dict] | None = None, rnd: int = 1,
           ets: list[str] | None = None,
           sbs: dict[str, list[str]] | None = None) -> pathlib.Path:
    """造一个最小鸿蒙工程骨架。
    trips: {trip: 安卓 GT 页数}；delivered: {trip: [本轮交付的 page_id]}
    """
    root = tmp / "proj"
    for trip, n in trips.items():
        d = root / "spec/visual-verify/screenshots/android" / trip
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (d / f"Page{i}Activity.png").write_bytes(b"x")
    for trip, pages in (delivered or {}).items():
        d = root / f"spec/visual-verify/screenshots/harmony/round-{rnd}" / trip
        d.mkdir(parents=True, exist_ok=True)
        for p in pages:
            (d / f"{p}.jpeg").write_bytes(b"x")
    for trip, pages in (sbs or {}).items():
        d = root / f"spec/visual-verify/screenshots/sbs/round-{rnd}" / trip
        d.mkdir(parents=True, exist_ok=True)
        for p in pages:
            (d / f"{p}.jpeg").write_bytes(b"x")
    src = root / "entry/src/main/ets/pages"
    src.mkdir(parents=True, exist_ok=True)
    (src / "Index.ets").write_text("\n".join(
        f"    }} else if (name === '{e}') {{" for e in (ets or [])), encoding="utf-8")
    for e in (ets or []):
        (src / f"{e}.ets").write_text("// stub", encoding="utf-8")
    for t in (tickets or []):
        d = root / f"spec/fix/round-{rnd}" / t.pop("_layer", "ui")
        d.mkdir(parents=True, exist_ok=True)
        fm = "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in t.items()
                       if k != "_name")
        (d / f"{t.get('_name', 'T')}.md").write_text(f"---\n{fm}\n---\n\n# t\n", encoding="utf-8")
    return root


def outdir(root: pathlib.Path, name: str = "out") -> pathlib.Path:
    d = root / "spec/visual-verify" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "capture_manifest.json").write_text("{}", encoding="utf-8")
    return d


def seed_verdict(root: pathlib.Path, rnd: int = 1, verdict: str = "OPEN_REMAIN",
                 open_n: int = 0) -> None:
    """造一条 `round_budget.py end` 的终态留痕 —— render_report.py 的结论行只认它。

    真实流程里这条由 `round_budget.py end` 写；用例不跑完整循环，直接落等价内容。
    """
    st = root / "spec/fix/_state.yaml"
    st.parent.mkdir(parents=True, exist_ok=True)
    prev = st.read_text(encoding="utf-8") if st.is_file() else ""
    st.write_text(prev + (
        f"\nlast_verdict:\n  verdict: {verdict}\n  round: {rnd}\n"
        f"  started_at_round: {rnd}\n  rounds_run: 1\n  budget: 3\n  open: {open_n}\n"),
        encoding="utf-8")


# ───────────────────────── 用例 ─────────────────────────
def case_1_missing_trip(tmp):
    """① 只跑了 trip2、trip1 整个缺失 → 必须 ROUND_INCOMPLETE(20)，绝不允许被当成完成。
       （事故原样：round 4/5/6 三轮 trip1 都是 0/18）"""
    root = mkproj(tmp, {"trip_1": 18, "trip_2": 20}, {"trip_2": [f"Page{i}Activity" for i in range(20)]})
    rc, log = run("assert_round_complete.py", root, 1,
                  "--trip-out", f"trip_2={outdir(root)}")
    check("① 缺整个 trip → ROUND_INCOMPLETE(20)", rc == 20, f"实际 rc={rc}")
    check("① 报告里点名未执行的 trip", "trip_1" in log and "未执行" in log)


def case_2_partial_coverage_not_clean(tmp):
    """② trip 都跑了但 trip2 只交付 6/20 → 绝不可能是 ALIGNMENT_CLEAN(0)。"""
    root = mkproj(tmp, {"trip_1": 18, "trip_2": 20},
                  {"trip_1": [f"Page{i}Activity" for i in range(18)],
                   "trip_2": [f"Page{i}Activity" for i in range(6)]})
    rc, _ = run("assert_round_complete.py", root, 1,
                "--trip-out", f"trip_1={outdir(root, 'o1')}",
                "--trip-out", f"trip_2={outdir(root, 'o2')}")
    check("② 覆盖 6/20 → 非 0（不得判 CLEAN）", rc != 0, f"实际 rc={rc}")


def case_3_gap_without_ticket(tmp):
    """③ 有缺页但一张认领单都没有 → gap 闸必须 21。"""
    root = mkproj(tmp, {"trip_1": 5}, {"trip_1": ["Page0Activity"]})
    rc, log = run("assert_gap_ticket_coverage.py", root, 1, "trip_1", outdir(root))
    check("③ 缺页无单 → 21", rc == 21, f"实际 rc={rc}")
    check("③ 明确指出 unclaimed", "unclaimed" in log)


def case_4_blocked_without_evidence(tmp):
    """④ 缺页有单，但 `is_migration_bug: false` 且三个证据位全空 → 21。
       这是 round-6 那 13 张假阴性单的**确切形态**。"""
    root = mkproj(tmp, {"trip_1": 2}, {"trip_1": ["Page0Activity"]},
                  tickets=[{"_name": "BLOCKED_P1", "kind": "BLOCKED", "severity": "P3",
                            "page_id": "Page1Activity", "is_migration_bug": False,
                            "suggested_files": ["unknown"],
                            "disposition": "pending_upstream_fix"}],
                  ets=["Page1Page"])
    rc, log = run("assert_gap_ticket_coverage.py", root, 1, "trip_1", outdir(root))
    check("④ 零证据的 is_migration_bug:false → 21", rc == 21, f"实际 rc={rc}")
    check("④ 违规类型是 no_evidence", "no_evidence" in log)


def case_5_absent_page_must_be_product_bug(tmp):
    """⑤ 页在鸿蒙源码里**根本不存在**，却判 is_migration_bug:false → 必须拦。
       这条是「缺页正确出单」的核心：源码没有 = 迁移缺陷本身。"""
    root = mkproj(tmp, {"trip_1": 2}, {"trip_1": ["Page0Activity"]},
                  tickets=[{"_name": "BLOCKED_P1", "kind": "BLOCKED", "severity": "P3",
                            "page_id": "Page1Activity", "is_migration_bug": False,
                            "hmos_impl": "entry/src/main/ets/pages/Nope.ets",
                            "disposition": "pending_upstream_fix"}],
                  ets=[])                      # 工程里没有任何 .ets → absent
    rc, log = run("assert_gap_ticket_coverage.py", root, 1, "trip_1", outdir(root))
    check("⑤ absent 页判非迁移缺陷 → 21", rc == 21, f"实际 rc={rc}")
    check("⑤ 要求改判 is_migration_bug: true", "absent_but_not_bug" in log)


def case_6_present_page_with_evidence_passes(tmp):
    """⑥ 页确实存在且单里指认了实现 → 判工具债**合法**，闸放行（避免闸只会说不）。"""
    root = mkproj(tmp, {"trip_1": 2}, {"trip_1": ["Page0Activity"]},
                  tickets=[{"_name": "BLOCKED_P1", "kind": "BLOCKED", "severity": "P3",
                            "page_id": "Page1Activity", "is_migration_bug": False,
                            "hmos_impl": "entry/src/main/ets/pages/Page1Page.ets",
                            "disposition": "pending_upstream_fix"}],
                  ets=["Page1Page"])
    rc, log = run("assert_gap_ticket_coverage.py", root, 1, "trip_1", outdir(root))
    check("⑥ present + 已举证 → 放行(0)", rc == 0, f"实际 rc={rc}\n{log[-400:]}")


# ⑦⑧ 已删（2026-09-14 回流裁剪）：测的是 codex 侧 round_budget.py 独有的
#   read_round_state()（无整轮账本则拒绝给结论）与 count_debt()（债单不得 CLEAN）。
#   源侧 round_budget.py 没有这两项，留着等于测不存在的功能；见文件头注与 CHANGELOG。


def case_9_report_cannot_say_pass(tmp):
    """⑨ 报告机械渲染：非 CLEAN 时**渲染不出**"完成/通过"。"""
    root = mkproj(tmp, {"trip_1": 20}, {"trip_1": ["Page0Activity"]})
    rs = root / "spec/visual-verify/round-1"
    rs.mkdir(parents=True, exist_ok=True)
    (rs / "run_state.json").write_text(json.dumps(
        {"round": 1, "expected_trips": ["trip_1"], "verdict": "ROUND_INCOMPLETE",
         "trips": {"trip_1": {"android_denominator": 20, "delivered": 1, "out_dir": None}},
         "open_findings": 0, "product_findings": 0}), encoding="utf-8")
    seed_verdict(root, 1, "OPEN_REMAIN")
    rc, _ = run("render_report.py", root, 1)
    txt = (root / "spec/visual-verify/report.md").read_text(encoding="utf-8")
    check("⑨ 渲染成功", rc == 0)
    check("⑨ 结论段不含「闭环已完成/通过」",
          "闭环已完成" not in txt and "## 结论：✅" not in txt, txt[:200])
    check("⑨ 覆盖率如实呈现", "1 |" in txt and "20" in txt)


def case_10_report_needs_a_verdict(tmp):
    """⑩ 没有结论来源就不许出报告（否则模型又能自由写结论）。

    2026-09-14 回流后判据换了源：原来是"缺整轮账本(run_state.json)"，现在是
    "没跑过 round_budget.py end（_state.yaml 无 last_verdict）"——渲染器不自判，没人给结论就不出报告。
    """
    root = mkproj(tmp, {"trip_1": 2}, {})
    rc, _ = run("render_report.py", root, 1)
    check("⑩ 无结论来源 → 拒绝出报告(2)", rc == 2, f"实际 rc={rc}")
    # 有整轮账本但仍没跑 end → 照样拒绝（账本是明细，不是结论）
    rs = root / "spec/fix/round-1"
    rs.mkdir(parents=True, exist_ok=True)
    (rs / "_run_state.json").write_text(json.dumps(
        {"round": 1, "verdict": "ALIGNMENT_CLEAN", "expected_trips": [], "trips": {}}),
        encoding="utf-8")
    rc2, _ = run("render_report.py", root, 1)
    check("⑩ 只有整轮账本、没跑 end → 仍拒绝", rc2 == 2, f"实际 rc={rc2}")


# ⑪ 已删（2026-09-14 回流裁剪）：测 codex 侧 compile_replay_plan.edge_untappable()，
#   源侧同名文件无此函数（"控件实测不存在"才降级 skip 的编译闸整体未回流）。


def case_12_run_state_lands_in_fix_round(tmp: pathlib.Path) -> None:
    """⑫ 整轮账本必须落 spec/fix/round-N/_run_state.json（2026-08-29 收口：路径唯一事实源）。"""
    root = mkproj(tmp, {"trip_a": 2}, {"trip_a": ["Page0Activity"]}, rnd=1)
    run("assert_round_complete.py", root, 1)
    canon = root / "spec/fix/round-1/_run_state.json"
    legacy = root / "spec/visual-verify/round-1/run_state.json"
    check("⑫ 账本落在 spec/fix/round-1/_run_state.json", canon.is_file(),
          f"实际未生成: {canon}")
    check("⑫ 不再往 spec/visual-verify/round-N/ 写", not legacy.exists(),
          "旧位置仍被写入 —— 会长出单文件目录")
    check("⑫ 内容可解析且带 verdict",
          canon.is_file() and "verdict" in json.loads(canon.read_text(encoding="utf-8")))
    # 报告渲染必须能读到新位置，且链接指向新位置
    seed_verdict(root, 1, "OPEN_REMAIN")
    rc, out = run("render_report.py", root, 1)
    rep = root / "spec/visual-verify/report.md"
    check("⑫ render_report 读得到新位置", rc == 0 and rep.is_file(), out[:200])
    if rep.is_file():
        check("⑫ 报告链接指向 ../fix/round-1/_run_state.json",
              "../fix/round-1/_run_state.json" in rep.read_text(encoding="utf-8"))


def case_13_legacy_run_state_still_readable(tmp: pathlib.Path) -> None:
    """⑬ 旧项目账本仍在 spec/visual-verify/round-N/ → 读取端必须回落，不得误报"没跑闸"。"""
    root = mkproj(tmp, {"trip_a": 2}, {"trip_a": ["Page0Activity"]}, rnd=1)
    rs = root / "spec/visual-verify/round-1"
    rs.mkdir(parents=True, exist_ok=True)
    (rs / "run_state.json").write_text(json.dumps(
        {"round": 1, "verdict": "ACCOUNTED_WITH_DEBT", "exit_code": 11,
         "expected_trips": ["trip_a"], "trips": {}}, ensure_ascii=False), encoding="utf-8")
    seed_verdict(root, 1, "OPEN_REMAIN")
    rc, out = run("render_report.py", root, 1)
    check("⑬ 旧位置账本仍能渲染报告", rc == 0, out[:200])
    canon = root / "spec/fix/round-1/_run_state.json"
    check("⑬ 回落是只读的，不偷偷迁移", not canon.exists())


def case_14_sbs_gap_reported_without_replay(tmp: pathlib.Path) -> None:
    """⑭ 两端截图都在、sbs 没合成 → 必须报（2026-08-29 下沉：判据不再依赖 replay/--trip-out）。

    实录：CreateOutLinePage 在 round-4/5 两端截图都采到了，sbs 一次没合成，
    于是那一页从来没做过视觉对比——却在账面上和"通过"同形。"""
    root = mkproj(tmp, {"t1": 3}, {"t1": ["Page0Activity", "Page1Activity"]},
                  sbs={"t1": ["Page0Activity"]}, rnd=1)     # Page1 有两端图但无 sbs
    run("assert_round_complete.py", root, 1)
    rs = json.loads((root / "spec/fix/round-1/_run_state.json").read_text(encoding="utf-8"))
    miss = (rs["trips"]["t1"] or {}).get("sbs_missing") or []
    check("⑭ 缺 sbs 被识别", miss == ["Page1Activity"], f"实际 {miss}")
    check("⑭ 未提供 --trip-out 也照样跑", True)
    seed_verdict(root, 1, "OPEN_REMAIN")
    rc, _ = run("render_report.py", root, 1)
    rep = (root / "spec/visual-verify/report.md").read_text(encoding="utf-8")
    check("⑭ 报告里点名该页", "Page1Activity" in rep and "缺 3 张 sbs" not in rep, rep[:300])
    check("⑭ 报告说明「从来没被看过」", "从未做过视觉对比" in rep)


def case_15_sbs_complete_no_false_alarm(tmp: pathlib.Path) -> None:
    """⑮ sbs 齐套 / 安卓无基线的页 → 一律不得误报。"""
    root = mkproj(tmp, {"t1": 3}, {"t1": ["Page0Activity", "ExtraOnlyOnHmos"]},
                  sbs={"t1": ["Page0Activity"]}, rnd=1)
    run("assert_round_complete.py", root, 1)
    rs = json.loads((root / "spec/fix/round-1/_run_state.json").read_text(encoding="utf-8"))
    miss = (rs["trips"]["t1"] or {}).get("sbs_missing") or []
    check("⑮ 鸿蒙独有页（安卓无基线）不算缺 sbs", miss == [], f"实际 {miss}")


def case_16_evidence_bypassed_blocks(tmp: pathlib.Path) -> None:
    """⑯ canonical 交付 0 但 adhoc 有本轮新文件 → EVIDENCE_BYPASSED(23)，不许当"跑过了"。

    实录：round-6 canonical 0/58、adhoc 当天 107 个文件，闸算对了(ROUND_INCOMPLETE)
    但红灯亮在 Phase 6.4——fixer 早派完了。本用例锁死"主路塌了要停"。"""
    root = mkproj(tmp, {"t1": 3}, {}, rnd=1)          # 鸿蒙本轮零交付
    ad = root / "spec/visual-verify/screenshots/adhoc"
    ad.mkdir(parents=True, exist_ok=True)
    (ad / "probe__x_120000.jpeg").write_bytes(b"x")
    rc, out = run("assert_evidence_channel.py", root, 1)
    check("⑯ 独立闸判 30", rc == 30, f"实际 {rc}: {out[:160]}")
    check("⑯ 说明不得派 fixer/定终态", "不得派 fixer" in out, out[:200])
    run("assert_round_complete.py", root, 1)
    rs = json.loads((root / "spec/fix/round-1/_run_state.json").read_text(encoding="utf-8"))
    check("⑯ 整轮 verdict = EVIDENCE_BYPASSED", rs.get("verdict") == "EVIDENCE_BYPASSED",
          str(rs.get("verdict")))
    seed_verdict(root, 1, "OPEN_REMAIN")
    rc2, _ = run("render_report.py", root, 1)
    rep = (root / "spec/visual-verify/report.md").read_text(encoding="utf-8")
    check("⑯ 报告渲染成「证据走了旁路」", "证据走了旁路" in rep, rep[:240])
    check("⑯ 报告不得出现完成/通过", not any(w in rep.split("## 覆盖账")[0]
                                            for w in ("闭环完成", "已通过", "收敛完成")))


def case_17_no_adhoc_stays_incomplete(tmp: pathlib.Path) -> None:
    """⑰ 零交付但 adhoc 也空（设备挂了没跑）→ 仍是 ROUND_INCOMPLETE，本闸不抢戏。"""
    root = mkproj(tmp, {"t1": 3}, {}, rnd=1)
    rc, _ = run("assert_evidence_channel.py", root, 1)
    check("⑰ 无旁路证据 → 放行(0)，交给 ROUND_INCOMPLETE", rc == 0, f"实际 {rc}")
    run("assert_round_complete.py", root, 1)
    rs = json.loads((root / "spec/fix/round-1/_run_state.json").read_text(encoding="utf-8"))
    check("⑰ verdict 仍是 ROUND_INCOMPLETE", rs.get("verdict") == "ROUND_INCOMPLETE",
          str(rs.get("verdict")))


def case_18_healthy_round_not_flagged(tmp: pathlib.Path) -> None:
    """⑱ 主路正常（canonical > adhoc）→ 一律不得误报。"""
    root = mkproj(tmp, {"t1": 3}, {"t1": ["Page0Activity", "Page1Activity", "Page2Activity"]},
                  rnd=1)
    ad = root / "spec/visual-verify/screenshots/adhoc"
    ad.mkdir(parents=True, exist_ok=True)
    (ad / "probe__x_120000.jpeg").write_bytes(b"x")
    rc, out = run("assert_evidence_channel.py", root, 1)
    check("⑱ 健康轮 → 0 且不报旁路", rc == 0 and "旁路量" not in out, f"{rc}: {out[:160]}")


def case_19_ticket_carries_usable_references(tmp: pathlib.Path) -> None:
    """⑲ 工单必须自带「必用参考」清单，且是可粘贴执行的命令而非路径提示。

    背景（2026-08-29 实测）：§1 光给路径，读取率 3.9%；且同批数据显示
    「读了安卓」与「修好」不相关（读过 21% vs 没读 25%，读最多的会话 6%）——
    所以不建强制闸，改为把本单可用的参考直接摆出来，命中链这类**脚本产出结论**的优先。"""
    root = tmp / "proj"
    (root / "spec/fix/round-1/feat").mkdir(parents=True, exist_ok=True)
    (root / "spec/fix/round-1/ui").mkdir(parents=True, exist_ok=True)
    rc, out = run("render_finding_skeleton.py", "--project-root", root, "--round", 1,
                  "--trip", "t1", "--page", "MineFragment", "--title", "[MineFragment] 取消点了不关闭",
                  "--kind", "IMPL_MISSING", "--severity", "P0", "--layer", "feat",
                  "--fixer-layer", "feat", "--id", "t_feat")
    md = (root / "spec/fix/round-1/feat/t_feat.md")
    check("⑲ feat 单渲染成功", rc == 0 and md.is_file(), out[:200])
    t = md.read_text(encoding="utf-8") if md.is_file() else ""
    check("⑲ 含「必用参考」段", "## 1.5 必用参考" in t)
    check("⑲ 行为类单挂上命中链探针命令", "hit_chain_probe.py" in t and "--page MineFragment" in t)
    check("⑲ 点明 dump/截图对命中断链是盲的", "结构性盲" in t)
    check("⑲ feat 单给常量真值源", "raw_apis.json" in t)
    check("⑲ 要求用不上要写明理由", "写明为什么用不上" in t)

    rc2, _ = run("render_finding_skeleton.py", "--project-root", root, "--round", 1,
                 "--trip", "t1", "--page", "GuideActivity", "--title", "[GuideActivity] 图标不一致",
                 "--kind", "ALIGNMENT_DIFF", "--category-pattern", "icon_mismatch",
                 "--severity", "P2", "--layer", "ui", "--fixer-layer", "ui", "--id", "t_ui")
    u = (root / "spec/fix/round-1/ui/t_ui.md")
    tu = u.read_text(encoding="utf-8") if u.is_file() else ""
    check("⑲ ui 单指向 sbs 且说明缺图=缺证", "screenshots/sbs/round-1/t1/GuideActivity.jpeg" in tu
          and "按缺证处理" in tu)
    check("⑲ 非行为类 ui 单不硬塞命中链", "hit_chain_probe.py" not in tu)
    check("⑲ §1.5 不破坏 1-7 段序校验", rc2 == 0)


def case_20_runtime_rid_backfill(tmp: pathlib.Path) -> None:
    """⑳ 边遍历实测到的 rid 要能回填空的 trigger_view_id，且来源可区分、不覆盖源码真值。

    病（2026-08-30 实测 AIPPT）：树 trigger_view_id 只有 26% 有值 → 遍历器按 id 点击 →
    54% 节点机械不可达 → 走不到那条边 → 更没机会实测 id（自锁）。
    回灌此前只写 runtime 子字典，从不写 trigger_view_id（原设计：源码真值的地盘）。"""
    root = tmp / "wb"; root.mkdir(parents=True, exist_ok=True)
    tree = {"pages": [{"id": "TargetPage", "inbound_triggers": [
        {"from_page": "HomePage", "trigger_view_id": None, "trigger_label": "去详情",
         "source": "llm_source_read"}]},
        {"id": "SecondPage", "inbound_triggers": [
        {"from_page": "HomePage", "trigger_view_id": "tv_wrong", "trigger_label": "第二页",
         "source": "llm_source_read"}]},
        {"id": "ThirdPage", "inbound_triggers": [
        {"from_page": "HomePage", "trigger_view_id": None, "trigger_label": "保存",
         "source": "reference_scan:ctor"}]}], "fragments": [], "dialogs": []}
    edges = [
        # ① 空洞 + 标签一致 → 应回填
        {"from": "HomePage", "to": "TargetPage", "status": "confirmed",
         "control": {"rid": "tv_detail", "text": "去详情", "center": [10, 20]},
         "landed": "TargetPage", "evidence": [], "note": "", "device_state": "d",
         "back_returns_to_parent": True},
        # ② 树已有值但与实测不同 → 不许覆盖，记冲突
        {"from": "HomePage", "to": "SecondPage", "status": "confirmed",
         "control": {"rid": "tv_right", "text": "第二页", "center": [10, 40]},
         "landed": "SecondPage", "evidence": [], "note": "", "device_state": "d",
         "back_returns_to_parent": True},
        # ③ 空洞但标签矛盾 → 不回填，但必须显性化（别沉进 discovered_edges）
        {"from": "HomePage", "to": "ThirdPage", "status": "confirmed",
         "control": {"rid": "tv_save", "text": "保存本地", "center": [10, 60]},
         "landed": "ThirdPage", "evidence": [], "note": "", "device_state": "d",
         "back_returns_to_parent": True},
    ]
    tp = root / "tree.json"; ep = root / "edges.json"
    tp.write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    ep.write_text(json.dumps(edges, ensure_ascii=False), encoding="utf-8")
    rc, out = run("writeback_walk.py", "--tree", tp, "--edges", ep, "--walk-id", "w1")
    after = json.loads(tp.read_text(encoding="utf-8"))
    byid = {r["id"]: r["inbound_triggers"][0] for r in after["pages"]}

    t1 = byid["TargetPage"]
    check("⑳ 空洞被实测 rid 回填", t1.get("trigger_view_id") == "tv_detail", str(t1))
    check("⑳ 回填来源可区分", t1.get("trigger_view_id_source") == "runtime_edge_walk", str(t1))
    check("⑳ 原 source 字段不被篡改", t1.get("source") == "llm_source_read", str(t1))
    check("⑳ 记了 walk_id 可追溯", t1.get("trigger_view_id_walk_id") == "w1", str(t1))

    t2 = byid["SecondPage"]
    check("⑳ 已有源码值不被静默覆盖", t2.get("trigger_view_id") == "tv_wrong", str(t2))
    check("⑳ 冲突被报出来", "冲突未覆盖 1 条" in out or "rid_conflict" in out, out[-300:])

    t3 = byid["ThirdPage"]
    check("⑳ 标签矛盾时拒填（静默错写>>漏写）", t3.get("trigger_view_id") is None, str(t3))
    check("⑳ 矛盾被显性化而非沉入死字段",
          "标签矛盾" in out and "tv_save" in out, out[-400:])


def main() -> int:
    cases = [v for k, v in sorted(globals().items()) if k.startswith("case_")]
    print(f"跑 {len(cases)} 组用例（每组对应 round 4-6 的一条真实失效路径）\n")
    for fn in cases:
        print(f"{fn.__name__}: {(fn.__doc__ or '').strip().splitlines()[0]}")
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="vvgate_"))
        try:
            fn(tmp)
        except Exception as e:                      # noqa: BLE001
            check(f"{fn.__name__} 抛异常", False, f"{type(e).__name__}: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print()
    print(f"结果: {len(PASS)} 通过 / {len(FAIL)} 失败")
    for f in FAIL:
        print(f"  ❌ {f}")
    return 1 if FAIL else 0


def test_round_gates_all_cases():
    """pytest 入口。本文件在 codex 侧是独立脚本（`python3 _tests/test_round_gates.py`），
    回流源侧后套件统一走 pytest —— 用例函数名是 `case_*` 不是 `test_*`，不加这层壳会被**整份漏收**
    （文件在、测试从不跑，正是本 skill 反复吃亏的"看着有闸其实没装"形态）。"""
    assert main() == 0, "整轮闸/出单闸/编译闸回归失败：\n" + "\n".join(FAIL)


if __name__ == "__main__":
    sys.exit(main())
