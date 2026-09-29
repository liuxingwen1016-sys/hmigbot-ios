#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_fix_self_check.py 第 ⑩ 项（并入的 check_fix_schema 三条硬约束）正向测试。

背景（2026-09-15 阶段 C）：阶段 B 把 codex 侧独有的 `check_fix_schema.py` 并进
`run_fix_self_check.py` 第 10 项后，**没有任何用例守着**——验收实测把该段整段删掉，
全量套件照样 626 passed（golden 侧 `_overrides.json` 的 `added_stdout_pattern` 是
**两侧同时过滤**，"多打的三类 ❌"既被允许、缺席时也同样放行）。本文件补上正向闸：
三条约束各一个「违规必 FAIL」+ 一个「合规 PASS」，并锁住判定文案。

三条约束（源出 references/fix-file-schema.md §4.6，判定文案一字不改）：
  ① `reason_slug: nav_failed` → 必须 `android_verified: true` 且有 `blocks_subtree:` 行
  ② `kind: BLOCKED`           → `blocked_by:` 必须指向**存在的**文件
  ③ `kind: FACT_TREE_INVALID_EDGE` → 必须 `suggested_fix_owner: app-relationship-tree`

设计要点：
- 全合成夹具、零工程依赖、零设备；每个用例一个独立临时目录 + 独立 round 目录。
- 每张单都填齐第 1~9 项要求的字段，**保证 baseline 一定 PASS**——否则"FAIL"会
  被别的检查项冒领，测不出第 10 项。`assert_baseline_clean` 就是这道自证。
- 断言同时卡 **exit code** 与 **stdout 里的那一行判定文案**（文案漂移 = 下游按文案
  分诊的脚本静默失灵）。

突变自证（2026-09-15 实跑）：把 run_fix_self_check.py 第 10 项整段（L231-247，1039 字节）
注释掉 → 本文件 **9 例中 5 例红**（4 个「违规必 FAIL」+ 1 个多单聚合例），其余 4 例
（三类合规 PASS + 「只扫 ui/ 不扫 feat/」口径锁）仍绿——它们本就不该受影响。还原后 9/9 绿。

运行：python3 -m pytest scripts/_tests/test_fix_self_check_item10_0915.py -q
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SC = os.path.abspath(os.path.join(HERE, ".."))
PY = sys.executable
SCRIPT = os.path.join(SC, "run_fix_self_check.py")

SECTIONS = (
    "## 1. Spec 引用\n来源: spec/baseline/ui/page_0001.md\n\n"
    "## 2. 期望\n安卓上点「设置」进入设置页。\n\n"
    "## 3. 实际\n鸿蒙侧点击无响应。\n\n"
    "## 4. 源码缺口\nentry/src/main/ets/pages/Foo.ets:39\n\n"
    "## 5. 修复建议\n补上路由跳转。\n"
)


def ticket(root, rnd, name, *, layer="ui", extra_fm=(), kind="ALIGNMENT_DIFF",
           evidence="shots/a.png"):
    """写一张满足第 1~9 项的单；extra_fm 是本用例要测的第 10 项相关字段。"""
    d = os.path.join(root, "spec", "fix", f"round-{rnd}", layer)
    os.makedirs(d, exist_ok=True)
    fm = [
        f"id: {name}",
        f'title: "[PHome] {name}"',
        "source: visual-verify",
        "layer: ui",
        f"kind: {kind}",
        "severity: P1",
        "page_id: PHome",
        "multimodal_severity: medium",
        "is_migration_bug: true",
        "similarity: 0.80",
        "fixer_layer: ui",
        "suggested_files:",
        "  - entry/src/main/ets/pages/Foo.ets",
        "evidence:",
        f"  - {evidence}",
    ]
    fm.extend(extra_fm)
    # evidence/list 之后必须再跟一个标量键：第 9 项的 evidence 块解析按 `^[a-zA-Z_]+:` 收尾，
    # 列表挨着 frontmatter 结束线 `---` 时会把它当成一条 `-` 条目，报一个虚构的 `--` 不存在。
    fm.append("disposition: null")
    p = os.path.join(d, name + ".md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("---\n" + "\n".join(fm) + "\n---\n\n" + SECTIONS)
    # evidence 必须真实存在（第 9 项），相对 root 落一个占位文件
    ep = os.path.join(root, evidence.split(":")[0])
    os.makedirs(os.path.dirname(ep), exist_ok=True)
    if not os.path.exists(ep):
        open(ep, "wb").write(b"x")
    return p


def run_check(root, rnd=0):
    p = subprocess.run([PY, SCRIPT, str(rnd)], cwd=root, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def new_round(rnd=0):
    root = tempfile.mkdtemp(prefix="vv_item10_")
    os.makedirs(os.path.join(root, "spec", "fix", f"round-{rnd}", "ui"), exist_ok=True)
    return root


def assert_baseline_clean(root, rnd=0):
    """自证：夹具本身在第 1~9 项下是干净的，后续 FAIL 只可能来自第 10 项。"""
    rc, out, err = run_check(root, rnd)
    assert rc == 0, f"夹具本身就不干净（第 1~9 项报错），测不出第 10 项：\nrc={rc}\n{out}\n{err}"


# ── 合规 PASS ───────────────────────────────────────────────────────────────
def test_all_three_compliant_passes():
    """三类单各一张、全部合规 → exit 0，一条 ❌ 都不打。"""
    root = new_round()
    blocker = os.path.join(root, "spec", "fix", "round-0", "ui", "BLOCKED_PRoot.md")
    ticket(root, 0, "CRASH_PHome_nav_failed_settings", kind="CRASH",
           extra_fm=["reason_slug: nav_failed", "android_verified: true",
                     "blocks_subtree:", "  - PSettings"])
    ticket(root, 0, "BLOCKED_PRoot")                      # 先把 blocked_by 的目标单造出来
    ticket(root, 0, "BLOCKED_PChild", kind="BLOCKED",
           extra_fm=[f"blocked_by: {blocker}"])
    ticket(root, 0, "FACT_TREE_INVALID_EDGE_PHome_to_PGhost",
           kind="FACT_TREE_INVALID_EDGE",
           extra_fm=["suggested_fix_owner: app-relationship-tree"])
    rc, out, err = run_check(root)
    assert rc == 0, f"合规单不该 FAIL：\n{out}\n{err}"
    assert "❌" not in out, out


# ── 约束 ①：nav_failed ─────────────────────────────────────────────────────
def test_nav_failed_without_android_verified_fails():
    root = new_round()
    ticket(root, 0, "CRASH_PHome_nav_failed_settings", kind="CRASH",
           extra_fm=["reason_slug: nav_failed", "blocks_subtree:", "  - PSettings"])
    rc, out, _ = run_check(root)
    assert rc == 1, out
    assert "nav_failed 必须 android_verified=true (否则应归 FACT_TREE_INVALID_EDGE)" in out, out


def test_nav_failed_without_blocks_subtree_fails():
    root = new_round()
    ticket(root, 0, "CRASH_PHome_nav_failed_settings", kind="CRASH",
           extra_fm=["reason_slug: nav_failed", "android_verified: true"])
    rc, out, _ = run_check(root)
    assert rc == 1, out
    assert "nav_failed 必须列 blocks_subtree" in out, out


def test_nav_failed_fully_compliant_passes():
    root = new_round()
    ticket(root, 0, "CRASH_PHome_nav_failed_settings", kind="CRASH",
           extra_fm=["reason_slug: nav_failed", "android_verified: true",
                     "blocks_subtree:", "  - PSettings"])
    assert_baseline_clean(root)


# ── 约束 ②：BLOCKED.blocked_by ─────────────────────────────────────────────
def test_blocked_by_missing_target_fails():
    root = new_round()
    ticket(root, 0, "BLOCKED_PChild", kind="BLOCKED",
           extra_fm=["blocked_by: spec/fix/round-0/ui/BLOCKED_DoesNotExist.md"])
    rc, out, _ = run_check(root)
    assert rc == 1, out
    assert "blocked_by 指向不存在: spec/fix/round-0/ui/BLOCKED_DoesNotExist.md" in out, out


def test_blocked_by_existing_target_passes():
    root = new_round()
    blocker = ticket(root, 0, "BLOCKED_PRoot")
    ticket(root, 0, "BLOCKED_PChild", kind="BLOCKED", extra_fm=[f"blocked_by: {blocker}"])
    assert_baseline_clean(root)


# ── 约束 ③：FACT_TREE_INVALID_EDGE.suggested_fix_owner ─────────────────────
def test_invalid_edge_without_owner_fails():
    root = new_round()
    ticket(root, 0, "FACT_TREE_INVALID_EDGE_PHome_to_PGhost", kind="FACT_TREE_INVALID_EDGE",
           extra_fm=["suggested_fix_owner: visual-fixer"])     # owner 写错也算违规
    rc, out, _ = run_check(root)
    assert rc == 1, out
    assert "FACT_TREE_INVALID_EDGE 必须 suggested_fix_owner=app-relationship-tree" in out, out


# ── 口径：只扫 round_dir/ui/*.md ────────────────────────────────────────────
def test_item10_only_scans_ui_dir():
    """同样的违规单放 feat/ 下**不报**——第 10 项与原 check_fix_schema 同口径（ui 单专属）。

    这条既是口径锁，也是"别把第 10 项悄悄扩面到 feat/"的护栏。
    """
    root = new_round()
    ticket(root, 0, "BLOCKED_PChild", layer="feat", kind="BLOCKED",
           extra_fm=["blocked_by: spec/fix/round-0/ui/BLOCKED_DoesNotExist.md"])
    rc, out, err = run_check(root)
    assert rc == 0, f"feat/ 下的单不该被第 10 项卡住：\n{out}\n{err}"
    assert "blocked_by 指向不存在" not in out, out


def test_multiple_violations_all_reported():
    """三条约束同时违规 → 三行 ❌ 一条不少（脚本是「收集完再退出」不是「首错即停」）。"""
    root = new_round()
    ticket(root, 0, "CRASH_PHome_nav_failed_settings", kind="CRASH",
           extra_fm=["reason_slug: nav_failed"])                      # 缺两项
    ticket(root, 0, "BLOCKED_PChild", kind="BLOCKED",
           extra_fm=["blocked_by: nope.md"])
    ticket(root, 0, "FACT_TREE_INVALID_EDGE_PHome_to_PGhost", kind="FACT_TREE_INVALID_EDGE")
    rc, out, _ = run_check(root)
    assert rc == 1, out
    for frag in ("nav_failed 必须 android_verified=true",
                 "nav_failed 必须列 blocks_subtree",
                 "blocked_by 指向不存在: nope.md",
                 "FACT_TREE_INVALID_EDGE 必须 suggested_fix_owner=app-relationship-tree"):
        assert frag in out, f"缺判定行 [{frag}]：\n{out}"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([os.path.abspath(__file__), "-q"]))
