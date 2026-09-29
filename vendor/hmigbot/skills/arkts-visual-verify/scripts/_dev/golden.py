#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""golden.py — 单侧「观测」的采集与比对（.sh 退役后 parity 的接班人，2026-09-14 阶段 B）。

背景：阶段 A 用 `sh_py_parity.py` 证明了 23 对 `.sh ↔ .py` 行为等价（116 例）。阶段 B 把
`.sh` 退役后，那个验证器**跑不起来了**（它要两侧同时在场）。于是在删 `.sh` 之前，把
每个用例的 **`.sh` 侧观测**固化成 golden（`_tests/fixtures/golden_sh_0914/`），之后套件
只跑 `.py` 与 golden 比 —— 等价结论继续被机械锁住，而不是靠"当时验过"。

归一化规则**沿用 `sh_py_parity.normalize`**（同一份代码，不另写一套），另加一条：
解释器所在目录（`sys.executable` 的 dirname）抹成空 —— 冻结的是 `.sh` 侧，回放的是 `.py` 侧，
后者的自调命令里会出现本机解释器路径。

观测内容 = 退出码 / stdout / stderr / 产物（新增或改动的文件）/ 被删除的文件。
产物按类型存：
  - `.json` → 结构化归一后的对象（顺序无关地比语义，不比缩进）
  - 其它文本 → 归一化后的正文
  - 二进制 → **只存字节数**（图片字节随 Pillow/字体版本漂移，存哈希会把套件焊死在本机）

Windows 原生：无 shell 依赖、`encoding="utf-8"`、`tempfile`。
"""
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import sh_py_parity as P  # noqa: E402

GOLDEN_DIR = os.path.join(os.path.dirname(_HERE), "_tests", "fixtures", "golden_sh_0914")

# 23 个退役脚本的**唯一名单**（`.sh` 删除后 `os.listdir` 认不出来了，改由本表承载）
RETIRED_SH_0914 = [
    "assert_replay_artifacts", "assert_run_success", "auto_install_artifacts", "capture_or_reuse",
    "check_android_screenshot", "check_blackbox_evidence", "check_dimension_prereqs",
    "check_functional_dimension", "check_prereq_freshness", "check_scratch_pollution",
    "compose_side_by_side", "dismiss_popups", "dispatch_phase2_batches", "gate_experiment",
    "inject_factree_refs", "inject_spec_oracle", "lib_resolve_round", "resize_screenshot",
    "reverify_transaction", "run_fix_self_check", "run_phase2_android_survey",
    "run_scenario_with_verify", "walk_finalize",
]


def _extra_subs():
    """解释器目录（含末尾分隔符）抹成空：`.py` 侧的自调命令会把它打进输出。"""
    d = os.path.dirname(os.path.abspath(sys.executable))
    return [(d + os.sep, ""), (d + "/", "")] if d else []


def case_id(case):
    return "%s::%s" % (case["script"], case.get("name") or " ".join(case.get("args") or []))


def golden_name(idx, case):
    slug = "".join(ch if (ch.isalnum() or ch in "-_") else "_"
                   for ch in (case.get("name") or "-".join(case.get("args") or []) or "default"))
    return "%03d_%s__%s.json" % (idx, case["script"], slug[:60])


def _observe(cmd_template, script_path, case, args, tmp_fixture, keep=False):
    """跑一侧，返回归一化观测 dict。cmd_template = case 里的 cmd_sh/cmd_py（可为 None）。"""
    root = tempfile.mkdtemp(prefix="golden_")
    P._prep(tmp_fixture or case.get("fixture"), root)
    cwd = os.path.join(root, case["subdir"]) if case.get("subdir") else root
    before = P._snapshot(root)

    default = [sys.executable if script_path.endswith(".py") else "bash", script_path] + list(args)
    if cmd_template:
        cmd = []
        for tok in cmd_template:
            if tok == "{ARGS}":
                cmd += list(args)
            else:
                cmd.append(tok.replace("{SH}", script_path).replace("{PY}", script_path)
                              .replace("{ARGS1}", args[0] if args else ""))
    else:
        cmd = default

    env = {k: v.replace("{ROOT}", root) for k, v in (case.get("env") or {}).items()}
    rc, out, err = P._run(cmd, cwd, env)
    after = P._snapshot(root)

    def _n(t):
        v = P.normalize(t, root, extra=_extra_subs())
        if case.get("norm_traceback"):
            v = P.collapse_traceback(v)
        return "\n".join(sorted(v.split("\n"))) if case.get("sort_lines") else v

    artifacts = {}
    for rel, val in after.items():
        if before.get(rel) == val:
            continue
        key = P._norm_rel(rel)
        try:
            text = val.decode("utf-8")
        except UnicodeDecodeError:
            artifacts[key] = {"kind": "bin", "size": len(val)}
            continue
        if key.endswith(".json"):
            try:
                artifacts[key] = {"kind": "json",
                                  "value": P._norm_obj(json.loads(text), root)}
                continue
            except Exception:
                pass
        artifacts[key] = {"kind": "text", "text": P.normalize(val, root, extra=_extra_subs())}

    obs = {"rc": rc, "stdout": _n(out), "stderr": _n(err), "artifacts": artifacts,
           "deleted": sorted(P._norm_rel(k) for k in set(before) - set(after))}
    if keep:
        obs["_sandbox"] = root
    else:
        shutil.rmtree(root, ignore_errors=True)
    return obs


def observe_sh(case, args, tmp_fixture, keep=False):
    sh = os.path.join(P.SCRIPTS_DIR, case["script"] + ".sh")
    return _observe(case.get("cmd_sh"), sh, case, args, tmp_fixture, keep)


def observe_py(case, args, tmp_fixture, keep=False):
    py = os.path.join(P.SCRIPTS_DIR, case["script"] + ".py")
    return _observe(case.get("cmd_py"), py, case, args, tmp_fixture, keep)


def apply_override(golden_obs, actual_obs, ov):
    """把**有意的行为超集**从差异里摘出来，摘不干净的照样报红。

    `_overrides.json` 里每条声明的形态（golden 文件名 → 规则），用于"退役后源侧又故意加了一道闸"
    这类场景 —— golden 是 `.sh` 那天的真值、不该被改写，但新增判定也不该被 `ignore` 整条吞掉。

      added_stdout_pattern  仅允许**新增**匹配该正则的 stdout 行；删行/改行照样红
      added_stderr_pattern  同上，作用于 stderr
      count_line_pattern    两侧该正则命中的行里的数字统一抹成 <N> 再比（如 "FAIL: 435" vs "438"）
      allow_rc              允许的实际退出码（golden 之外）

    返回 (golden_obs', actual_obs')，交给 diff_observations 正常比。
    """
    if not ov:
        return golden_obs, actual_obs
    g = dict(golden_obs)
    a = dict(actual_obs)
    import re as _re
    for key, pat_key in (("stdout", "added_stdout_pattern"), ("stderr", "added_stderr_pattern")):
        pat = ov.get(pat_key)
        if not pat:
            continue
        rx = _re.compile(pat)
        a[key] = "\n".join(ln for ln in a[key].split("\n") if not rx.search(ln))
        g[key] = "\n".join(ln for ln in g[key].split("\n") if not rx.search(ln))
    cl = ov.get("count_line_pattern")
    if cl:
        rx = _re.compile(cl)
        def _mask(t):
            return "\n".join(_re.sub(r"\d+", "<N>", ln) if rx.search(ln) else ln
                              for ln in t.split("\n"))
        for key in ("stdout", "stderr"):
            g[key], a[key] = _mask(g[key]), _mask(a[key])
    if "allow_rc" in ov and a["rc"] == ov["allow_rc"]:
        a["rc"] = g["rc"]
    return g, a


def diff_observations(golden, actual):
    """→ 差异描述列表（前缀与 sh_py_parity 的一致，`ignore` 豁免前缀可直接复用）。"""
    diffs = []
    if golden["rc"] != actual["rc"]:
        diffs.append("退出码 sh=%s py=%s" % (golden["rc"], actual["rc"]))
    if golden["stdout"] != actual["stdout"]:
        diffs.append("stdout 不一致")
    if golden["stderr"] != actual["stderr"]:
        diffs.append("stderr 不一致")
    if golden.get("deleted", []) != actual.get("deleted", []):
        diffs.append("删除的文件不一致 sh=%s py=%s"
                     % (golden.get("deleted"), actual.get("deleted")))
    ga, aa = golden.get("artifacts", {}), actual.get("artifacts", {})
    only_g, only_a = sorted(set(ga) - set(aa)), sorted(set(aa) - set(ga))
    if only_g or only_a:
        diffs.append("产物集合不一致 只有sh=%s 只有py=%s" % (only_g, only_a))
    for rel in sorted(set(ga) & set(aa)):
        g, a = ga[rel], aa[rel]
        if g.get("kind") != a.get("kind"):
            diffs.append("产物 %s 类型不一致（%s vs %s）" % (rel, g.get("kind"), a.get("kind")))
        elif g["kind"] == "bin":
            if g["size"] != a["size"]:
                diffs.append("产物 %s 内容不一致（二进制，sh=%d 字节 / py=%d 字节）"
                             % (rel, g["size"], a["size"]))
        elif g["kind"] == "json":
            if g["value"] != a["value"]:
                diffs.append("产物 %s 内容不一致" % rel)
        elif g["text"] != a["text"]:
            diffs.append("产物 %s 内容不一致" % rel)
    return diffs


def artifact_linediff(golden, actual, rel):
    g, a = golden["artifacts"][rel], actual["artifacts"][rel]
    if g.get("kind") == "json":
        return P._linediff(json.dumps(g["value"], ensure_ascii=False, indent=2, sort_keys=True),
                           json.dumps(a["value"], ensure_ascii=False, indent=2, sort_keys=True))
    if g.get("kind") == "text":
        return P._linediff(g["text"], a["text"])
    return []
