#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_py_golden_0914.py —— `.py` ↔ golden 等价闸（2026-09-14 源侧全 py 化·阶段 B）。

阶段 A 用 `_dev/sh_py_parity.py` 证明了 23 对 `.sh ↔ .py` 行为等价（116 例）。阶段 B 把
23 个 `.sh` 退役后那个验证器跑不起来了（它要两侧同时在场），所以**删之前**把每个用例的
`.sh` 侧观测固化进 `fixtures/golden_sh_0914/`，本文件只跑 `.py` 与 golden 比 ——
退役之后行为仍被机械锁住，而不是靠"当时验过一次"。

归一化规则与阶段 A **同一份代码**（`_dev/sh_py_parity.normalize`，经 `_dev/golden.py` 复用）。
用例矩阵仍是 `_dev/parity_cases.py`（golden 按 `case_index` 回指），改用例要同步重跑
`python3 scripts/_dev/freeze_golden.py`——而那需要先从 git 历史取回 `.sh`：
`git show 915_vvSpeed:arkts-skills/skills/arkts-visual-verify/scripts/<name>.sh`。

本文件同时接管了阶段 A 挂在 `test_sh_py_parity_0914.py` 上的三条静态闸
（同名 .py 齐备 / 零 shell 依赖 / open 带 encoding）与 compose 的几何闸。
无 bash 的机器（纯 Windows）**照跑**——这正是全 py 化的目的。
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SCRIPTS, "_dev"))

import golden as G  # noqa: E402
import parity_cases  # noqa: E402
import sh_py_parity as P  # noqa: E402
from freeze_golden import fixture_digest  # noqa: E402

GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "golden_sh_0914")
_CASES = parity_cases.build_cases()


def _in_converted_product() -> bool:
    """本副本是不是 codex-adapter 的**产物**（`codex/skills/arkts-visual-verify/`）？

    产物里的脚本过了 adapter 的平台分歧改写（`.codex/agents/*.md` → `.codex/agents/*.toml`、
    `$x` → `$x`、`Agent(...)` → `spawn_agent(...)` 等），行为**本就该与源侧不同**；
    而 golden 锁的是**源侧**行为。不加这道判别，产物里跑套件会红 4 例
    （check_dimension_prereqs 去找 `.codex/agents/*.toml`，夹具造的是 `.codex/agents/*.md`；
    run_scenario_with_verify 同源），把"平台分歧"误报成"回归"。

    判据取 adapter 一定会改、源侧一定没有的字符串，不靠目录名（产物可能被装到任意位置）。
    """
    p = os.path.join(SCRIPTS, "check_dimension_prereqs.py")
    try:
        return ".codex/agents" in open(p, encoding="utf-8").read()
    except OSError:
        return False


_IS_PRODUCT = _in_converted_product()


def _load_goldens():
    if not os.path.isdir(GOLDEN_DIR):
        return []
    out = []
    for fn in sorted(os.listdir(GOLDEN_DIR)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        with open(os.path.join(GOLDEN_DIR, fn), encoding="utf-8") as f:
            out.append((fn, json.load(f)))
    return out


_GOLDENS = _load_goldens()


def _load_overrides():
    """有意的行为超集声明（见 `fixtures/golden_sh_0914/_overrides.json` 与 golden.apply_override）。"""
    p = os.path.join(GOLDEN_DIR, "_overrides.json")
    if not os.path.isfile(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


_OVERRIDES = _load_overrides()


def test_overrides_all_point_at_live_goldens():
    """`_overrides.json` 里的条目必须逐条对得上现存 golden，且都写了 why ——
    否则就是把告警关掉后忘了清理，超集声明会悄悄豁免掉本不该豁免的用例。"""
    names = {fn for fn, _ in _GOLDENS}
    stale = sorted(set(_OVERRIDES) - names)
    assert not stale, "这些超集声明指向不存在的 golden：%s" % stale
    nowhy = sorted(k for k, v in _OVERRIDES.items() if not (v.get("why") or "").strip())
    assert not nowhy, "这些超集声明没写 why：%s" % nowhy


_ABS_PATH_RE = re.compile(r"(?:(?<=[\s\"'`(\[:=,])|^)(?:/(?:Users|home|root|opt|srv|var|private|tmp|mnt|media)/"
                          r"|[A-Za-z]:[\\/])", re.M)


def test_goldens_have_no_absolute_paths():
    """golden 落盘里不许出现**任何**绝对路径（2026-09-15 阶段 C）。

    阶段 B 的 golden 冻进了 worktree 的绝对路径（`run_scenario_with_verify` 的"请先跑
    …/arkts-scenario-runner/scripts/scenario_run.py"提示行）与真实工程根
    （`requires_fixture`）——把 skill 整目录拷到别处跑，这两例必红，与"无 bash 的机器照跑"
    的初衷直接冲突。归一化占位符见 `_dev/sh_py_parity.normalize`：
    `<ROOT>` / `<SCRIPTS>` / `<SKILLS>` / `<TMP>` / `<REAL_PROJECT>`。

    新增 golden 撞红这条时**不要**把路径加进白名单——去 normalize 里补一条占位符规则，
    再 `python3 scripts/_dev/freeze_golden.py --only <script>` 重固化。
    """
    bad = []
    for fn in sorted(os.listdir(GOLDEN_DIR)) if os.path.isdir(GOLDEN_DIR) else []:
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(GOLDEN_DIR, fn), encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if _ABS_PATH_RE.search(line):
                    bad.append("%s:%d: %s" % (fn, i, line.strip()[:160]))
    assert not bad, ("这些 golden 里有绝对路径（换目录就红）：\n" + "\n".join(bad))


def test_golden_set_is_complete():
    """golden 份数必须与用例矩阵对齐——少一份 = 有分支悄悄没被锁住。"""
    assert _GOLDENS, "golden 目录为空：跑 python3 scripts/_dev/freeze_golden.py（需先取回 .sh）"
    assert len(_GOLDENS) == len(_CASES), (
        "golden %d 份 ≠ 用例 %d 例：改了 _dev/parity_cases.py 就要重跑 freeze_golden.py"
        % (len(_GOLDENS), len(_CASES)))


@pytest.mark.skipif(_IS_PRODUCT,
                    reason="codex 产物：脚本已过 adapter 平台分歧改写，golden 锁的是源侧行为，此处不适用"
                           "（静态闸与 dismiss_popups 离线闸照跑）")
@pytest.mark.parametrize("fn,rec", _GOLDENS, ids=[x[0][:-5] for x in _GOLDENS])
def test_py_matches_golden(fn, rec):
    idx = rec["case_index"]
    assert idx < len(_CASES), "golden %s 指向的用例 #%d 已不存在（重跑 freeze_golden.py）" % (fn, idx)
    case = _CASES[idx]
    assert case["script"] == rec["script"] and case.get("name", "") == rec["name"], (
        "golden %s 与用例矩阵错位：golden=%s/%s 现矩阵=%s/%s（重跑 freeze_golden.py）"
        % (fn, rec["script"], rec["name"], case["script"], case.get("name", "")))

    need = rec.get("requires_fixture") or case.get("requires_fixture")
    if need == parity_cases.REAL_PROJECT_PLACEHOLDER:
        # golden 里只存占位符（绝对路径进 golden = 换 checkout/换机器必红）；这里按 env 解析回真路径
        need = parity_cases.real_spec_root()
        if not need:
            pytest.skip("未设 $%s（8 个【真实工程】用例整体跳过，不是通过）"
                        % parity_cases.REAL_PROJECT_ENV)
    if need and not os.path.exists(need):
        pytest.skip("缺真实工程夹具: %s" % need)

    tmp = None
    try:
        fx = case.get("fixture_factory")
        if fx:
            tmp = tempfile.mkdtemp(prefix="fx_")
            fx(tmp)
        if rec.get("fixture_digest"):
            now = fixture_digest(tmp or case.get("fixture"))
            if now != rec["fixture_digest"]:
                pytest.skip("真实工程夹具已漂移（golden %s ≠ 现 %s）：golden 锁的是当时那份工程，"
                            "要么恢复工程要么重跑 freeze_golden.py"
                            % (rec["fixture_digest"], now))
        actual = G.observe_py(case, case.get("args", []), tmp)
        expected, actual = G.apply_override(rec["observation"], actual, _OVERRIDES.get(fn))
        diffs = P._filter_ignored(G.diff_observations(expected, actual),
                                  rec.get("ignore") or case.get("ignore"))
        if diffs:
            msg = ["%s %s 与 golden 不等价:" % (case["script"], case.get("name"))]
            msg += ["  ✗ " + d for d in diffs]
            if "stdout 不一致" in diffs:
                msg += ["  stdout:"] + ["    " + x for x in
                                        P._linediff(expected["stdout"], actual["stdout"])]
            if "stderr 不一致" in diffs:
                msg += ["  stderr:"] + ["    " + x for x in
                                        P._linediff(expected["stderr"], actual["stderr"])]
            for d in diffs:
                m = re.match(r"产物 (.+?) 内容不一致$", d)
                if m and m.group(1) in expected["artifacts"]:
                    msg += ["  产物 %s:" % m.group(1)]
                    msg += ["    " + x for x in G.artifact_linediff(expected, actual, m.group(1))]
            pytest.fail("\n".join(msg))
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


# ── 静态闸（阶段 A 自 test_sh_py_parity_0914.py 迁入；名单改由 golden.RETIRED_SH_0914 承载）──

def test_every_retired_sh_has_a_py():
    """23 个退役 .sh 必须都有同名 .py（退役后没有 .sh 可 listdir，名单是常量）。"""
    missing = [n for n in G.RETIRED_SH_0914
               if not os.path.isfile(os.path.join(SCRIPTS, n + ".py"))]
    assert not missing, "这些退役 .sh 没有同名 .py：%s" % missing


def test_no_sh_left_in_scripts():
    """scripts/ 下不许再有 .sh（全 py 化的收口判据；Windows 原生要求）。"""
    left = sorted(f for f in os.listdir(SCRIPTS) if f.endswith(".sh"))
    assert not left, "scripts/ 仍有 .sh：%s" % left


def test_ported_py_have_no_shell_dependency():
    """移植件不许依赖 bash/awk/grep/sed/find/xargs/yq/jq/sips，也不许 os.system / shell=True。"""
    bad = []
    pat = re.compile(r"os\.system\(|shell\s*=\s*True|[\"'](?:/bin/)?(?:bash|sh|awk|grep|sed|find|"
                     r"xargs|yq|jq|sips|md5)[\"']")
    for n in G.RETIRED_SH_0914 + ["lib_tools", "lib_image", "lib_resolve_round"]:
        p = os.path.join(SCRIPTS, n + ".py")
        if not os.path.isfile(p):
            continue
        for i, line in enumerate(open(p, encoding="utf-8"), 1):
            if pat.search(line) and not line.lstrip().startswith("#"):
                bad.append("%s:%d: %s" % (n + ".py", i, line.strip()[:110]))
    assert not bad, "这些行带 shell 依赖：\n" + "\n".join(bad)


def test_ported_py_open_utf8():
    """移植件里的 open() 必须带 encoding（Windows 默认 cp936 会把中文读崩）。"""
    bad = []
    pat = re.compile(r"\bopen\(")
    ok_pat = re.compile(r"encoding\s*=|[\"']rb[\"']|[\"']wb[\"']|[\"']ab[\"']|Image\.open")
    for n in G.RETIRED_SH_0914 + ["lib_tools", "lib_image", "lib_resolve_round"]:
        p = os.path.join(SCRIPTS, n + ".py")
        if not os.path.isfile(p):
            continue
        for i, line in enumerate(open(p, encoding="utf-8"), 1):
            if pat.search(line) and not ok_pat.search(line) and "subprocess" not in line:
                bad.append("%s:%d: %s" % (n + ".py", i, line.strip()[:110]))
    assert not bad, "这些 open() 没写 encoding：\n" + "\n".join(bad)


def test_compose_matches_golden_geometry():
    """compose_side_by_side：`.py` 的拼图与冻结的 `.sh` 拼图**只允许标签带不同**
    ——画布尺寸与两张图的粘贴区必须逐像素相同（golden 存 (W,H) + 标签带以下的 sha256）。"""
    pytest.importorskip("PIL")
    from PIL import Image
    gp = os.path.join(GOLDEN_DIR, "_compose_geometry.json")
    if not os.path.isfile(gp):
        pytest.skip("缺 _compose_geometry.json（跑 freeze_golden.py 固化）")
    with open(gp, encoding="utf-8") as f:
        g = json.load(f)
    d = tempfile.mkdtemp(prefix="fx_compose_")
    try:
        parity_cases._fx_two_imgs(d)
        a, b = os.path.join(d, "a.png"), os.path.join(d, "b.png")
        out = os.path.join(d, "o_py.jpeg")
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "compose_side_by_side.py"), a, b, out],
                       capture_output=True, check=True)
        im = Image.open(out).convert("RGB")
        w, h = im.size
        assert [w, h] == g["size"], "画布尺寸与 golden 不同：%s vs %s" % ([w, h], g["size"])
        body = hashlib.sha256(im.crop((0, g["label_band_h"], w, h)).tobytes()).hexdigest()
        assert body == g["body_sha256"], \
            "标签带以下的像素与 golden 不同 —— 差异越出标签带，不只是字体回落"
    finally:
        shutil.rmtree(d, ignore_errors=True)
