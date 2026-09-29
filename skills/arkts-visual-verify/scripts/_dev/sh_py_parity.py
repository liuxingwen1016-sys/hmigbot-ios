#!/usr/bin/env python3
"""sh_py_parity.py — .sh ↔ .py 等价验证器（开发工具，**不进 pytest 默认集**）。

★★ 2026-09-14 阶段 B：23 个 `.sh` 已退役，本工具**默认跑不起来**（它要两侧同时在场）。
   重跑需先从 git 历史取回 `.sh`：
       git show 915_vvSpeed:arkts-skills/skills/arkts-visual-verify/scripts/<name>.sh \
           > arkts-skills/skills/arkts-visual-verify/scripts/<name>.sh
   日常回归改由 `_tests/test_py_golden_0914.py` 承担：它把退役前的 `.sh` 侧观测固化在
   `_tests/fixtures/golden_sh_0914/`，只跑 `.py` 与 golden 比（归一化规则复用本文件的 normalize）。
   本文件保留的理由：golden 是"结论"，它是"怎么得出结论的"；改了 .py 的行为要重新对齐 .sh 时，
   取回 .sh + 跑 `--all` 仍是唯一的原地重验手段（重新固化走 `_dev/freeze_golden.py`）。

用途：给定脚本名 + 一组参数，在两份**内容相同的**沙箱里分别跑
    bash <name>.sh <args>   与   python3 <name>.py <args>
归一化后比较：退出码 / stdout / stderr / 产物文件（含新增、修改、删除）。

归一化（两边同样处理，只抹掉"必然不同"的东西，不抹判定文案）：
  - 沙箱根目录绝对路径 → <ROOT>；scripts 目录绝对路径 → <SCRIPTS>；系统临时目录 → <TMP>
  - ISO 时间戳 / yyyymmdd_HHMMSS / mmdd / epoch 秒 → <TS> 等占位
  - 耗时数字（12ms / 1.3s / took 5）→ <DUR>
  - 行尾空白、CRLF
产物比较：
  - .json 按结构比（递归归一化字符串值里的时间戳/路径）
  - 其它文本按行比
  - 二进制按字节比

用法：
  python3 _dev/sh_py_parity.py --script check_scratch_pollution --fixture <夹具目录> -- a.png
  python3 _dev/sh_py_parity.py --script gate_experiment --case-file cases.json
  python3 _dev/sh_py_parity.py --all            # 跑内置用例矩阵（_dev/parity_cases.py）
退出码：0 全部一致；1 有差异；2 参数/环境问题。
"""
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def skills_roots():
    """本机上「skills 安装根」的全部候选（脚本跨 skill 找兄弟时会打印其中之一的绝对路径）。

    2026-09-15 阶段 C：golden 里冻进过 worktree 的绝对路径
    （`run_scenario_with_verify` 的「请先跑 …/arkts-scenario-runner/scripts/scenario_run.py」提示行），
    换 checkout / 换机器这两例必红——与"无 bash 的机器照跑"的初衷直接冲突。
    候选顺序照抄 `run_scenario_with_verify._resolve_dep`：本 skill 的安装根 > `~/.agents/skills` >
    `$CLAUDE_PROJECT_DIR/.agents/skills`，任何一个命中都归一成 `<SKILLS>`。
    """
    cands = [os.path.dirname(os.path.dirname(SCRIPTS_DIR)),          # <skills>/<本skill>/scripts → <skills>
             os.path.join(os.path.expanduser("~"), ".claude", "skills")]
    pd = os.environ.get("CLAUDE_PROJECT_DIR")
    if pd:
        cands.append(os.path.join(pd, ".claude", "skills"))
    out = []
    for c in cands:
        for v in (c, os.path.realpath(c)):
            if v and v not in out:
                out.append(v)
    return out


def real_project_roots():
    """真实工程夹具根（env `VV_PARITY_REAL_PROJECT`）的全部写法，归一成 `<REAL_PROJECT>`。

    延迟 import：`parity_cases` 也 import 本模块（normalize），顶层互相 import 会成环。
    """
    try:
        import parity_cases as _PC
    except Exception:
        return []
    root = _PC.real_project_root()
    if not root:
        return []
    out = []
    for v in (root, os.path.realpath(root)):
        if v and v not in out:
            out.append(v)          # `<root>/spec` 自然变成 `<REAL_PROJECT>/spec`
    return out

# ── 归一化规则 ────────────────────────────────────────────────────────
_TS_PATTERNS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"), "<TS>"),
    # ★ 不能用结尾 \b：`20260914T134248Z_占位…` 里 Z 和 _ 都是 word 字符，\b 不成立 → 漏归一（实测 flake）
    (re.compile(r"(?<!\d)\d{8}T\d{6}Z"), "<TSZ>"),
    (re.compile(r"(?<!\d)\d{8}_\d{6}(?!\d)"), "<TSCOMPACT>"),
    (re.compile(r"(?<!\d)\d{14}(?!\d)"), "<TS14>"),          # walk_finalize 备份名 %Y%m%d%H%M%S
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "<DATE>"),
    (re.compile(r"archived-\d{4}\b"), "archived-<MMDD>"),
    (re.compile(r"\b1[6-9]\d{8}\b"), "<EPOCH>"),
    (re.compile(r"\b\d+(?:\.\d+)?\s?ms\b"), "<DUR>ms"),
    (re.compile(r"\b\d+(?:\.\d+)?\s?s\b(?!\w)"), "<DUR>s"),
]


def normalize(text, root, extra=()):
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    text = text.replace("\r\n", "\n")
    # 先抹最长的路径，避免短路径先抹掉造成残渣
    subs = [(os.path.realpath(root), "<ROOT>"), (root, "<ROOT>"),
            (SCRIPTS_DIR, "<SCRIPTS>"),
            (os.path.realpath(tempfile.gettempdir()), "<TMP>"), (tempfile.gettempdir(), "<TMP>")]
    # skills 安装根 → <SKILLS>（跨 skill 路径；排在 <SCRIPTS> 之后，靠下面按长度倒序保证不抢先）
    subs.extend((r, "<SKILLS>") for r in skills_roots())
    # 真实工程根 → <REAL_PROJECT>（8 个真实工程用例的路径不进 golden，见 parity_cases 头注）
    subs.extend((r, "<REAL_PROJECT>") for r in real_project_roots())
    subs.extend(extra)
    for a, b in sorted(subs, key=lambda kv: -len(kv[0])):
        if a:
            text = text.replace(a, b)
    for pat, rep in _TS_PATTERNS:
        text = pat.sub(rep, text)
    # ★ 两条**有意**的归一（阶段 A 的已知等价豁免，写进报告）：
    #   1) 同名脚本自引用：X.sh ↔ X.py（阶段 B 会把文档/调用方一起改成 .py）
    #   2) 解释器前缀：bash / python3 / python → <RUN>
    text = re.sub(r"\b([A-Za-z0-9_]+)\.(?:sh|py)\b", r"\1.<EXT>", text)
    text = text.replace("bash ", "<RUN> ").replace("python3 ", "<RUN> ").replace("python ", "<RUN> ")
    text = text.replace("<SCRIPTS>/", "")   # $0 在 .sh 是全路径、在 .py 取 basename
    lines = [ln.rstrip() for ln in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _norm_obj(o, root):
    if isinstance(o, dict):
        return {k: _norm_obj(v, root) for k, v in o.items()}
    if isinstance(o, list):
        return [_norm_obj(v, root) for v in o]
    if isinstance(o, str):
        return normalize(o, root)
    if isinstance(o, float):
        return round(o, 6)
    return o


# ── 沙箱与运行 ────────────────────────────────────────────────────────
def _snapshot(root):
    """相对路径 → bytes（只记文件，忽略 .git / __pycache__）。"""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            try:
                with open(p, "rb") as fh:
                    out[rel] = fh.read()
            except OSError:
                out[rel] = b"<UNREADABLE>"
    return out


def _run(cmd, cwd, env):
    e = dict(os.environ)
    e.setdefault("PYTHONIOENCODING", "utf-8")
    e.setdefault("LC_ALL", "en_US.UTF-8")
    e.update(env or {})
    p = subprocess.run(cmd, cwd=cwd, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout, p.stderr


def _prep(fixture, dest):
    os.makedirs(dest, exist_ok=True)
    if fixture:
        for name in os.listdir(fixture):
            src = os.path.join(fixture, name)
            dst = os.path.join(dest, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)


def _norm_rel(rel):
    """产物相对路径也过一遍时间戳归一（.sh/.py 各跑一次，秒级文件名必然不同）。"""
    for pat, r in _TS_PATTERNS:
        rel = pat.sub(r, rel)
    return rel


_TB_FRAME = re.compile(r'^  File "[^"]*", line \d+(?:, in .*)?$')


def collapse_traceback(text):
    """把 Python traceback 的**帧明细**折成 <FRAME>，只留首行 `Traceback...` 与末行异常类型。
    .sh 里的 python 是 heredoc（帧显示 `File "<stdin>", line 4`、无源码回显），
    .py 里是真文件（帧带文件/函数名 + 源码行 + 插入符）——帧明细必然不同，异常本身才是判定内容。"""
    out, skip = [], False
    for ln in text.split("\n"):
        if _TB_FRAME.match(ln):
            if not skip:
                out.append("  <FRAME>")
            skip = True
            continue
        if skip and (ln.startswith("    ") or ln.strip() == ""):
            continue          # 帧下面的源码回显 / 插入符行
        skip = False
        out.append(ln)
    return "\n".join(out)


def compare_case(script, args, fixture=None, env=None, subdir=None, keep=False, sort_lines=False,
                 cmd_sh=None, cmd_py=None, norm_traceback=False):
    """跑一对并返回 (ok, report_dict)。"""
    sh = os.path.join(SCRIPTS_DIR, script + ".sh")
    py = os.path.join(SCRIPTS_DIR, script + ".py")
    if not os.path.isfile(sh):
        return False, {"error": "缺 .sh: " + sh}
    if not os.path.isfile(py):
        return False, {"error": "缺 .py: " + py}

    base = tempfile.mkdtemp(prefix="parity_")
    a_root = os.path.join(base, "sh")
    b_root = os.path.join(base, "py")
    _prep(fixture, a_root)
    _prep(fixture, b_root)
    a_cwd = os.path.join(a_root, subdir) if subdir else a_root
    b_cwd = os.path.join(b_root, subdir) if subdir else b_root

    before_a, before_b = _snapshot(a_root), _snapshot(b_root)
    # cmd_sh/cmd_py：给「不是 CLI 入口」的脚本用（如 lib_*.sh 只能 source）。
    # {SH}/{PY}/{ARGS} 占位符由这里填。
    def _mk(tpl, path, default):
        if not tpl:
            return default
        out = []
        for tok in tpl:
            if tok == "{ARGS}":
                out += list(args)
            else:
                out.append(tok.replace("{SH}", sh).replace("{PY}", py)
                              .replace("{ARGS1}", args[0] if args else ""))
        return out

    # env 值里的 {ROOT} 换成各自沙箱根（用来隔离 HOME 之类的全局查找路径）
    def _env(root):
        return {k: v.replace("{ROOT}", root) for k, v in (env or {}).items()}

    rc_a, out_a, err_a = _run(_mk(cmd_sh, sh, ["bash", sh] + list(args)), a_cwd, _env(a_root))
    rc_b, out_b, err_b = _run(_mk(cmd_py, py, [sys.executable, py] + list(args)), b_cwd, _env(b_root))
    after_a, after_b = _snapshot(a_root), _snapshot(b_root)

    def _n(t, root):
        v = normalize(t, root)
        if norm_traceback:
            v = collapse_traceback(v)
        # sort_lines：清单类输出（.sh 用 `find` 的目录物理序，.py 用 sorted()）只比**内容集合**不比顺序。
        return "\n".join(sorted(v.split("\n"))) if sort_lines else v

    rep = {"script": script, "args": list(args), "rc": [rc_a, rc_b],
           "diffs": [], "stdout_sh": _n(out_a, a_root), "stdout_py": _n(out_b, b_root),
           "stderr_sh": _n(err_a, a_root), "stderr_py": _n(err_b, b_root)}

    if rc_a != rc_b:
        rep["diffs"].append("退出码 sh=%s py=%s" % (rc_a, rc_b))
    if rep["stdout_sh"] != rep["stdout_py"]:
        rep["diffs"].append("stdout 不一致")
    if rep["stderr_sh"] != rep["stderr_py"]:
        rep["diffs"].append("stderr 不一致")

    # 产物（含删除）
    changed_a = {_norm_rel(k): v for k, v in after_a.items() if before_a.get(k) != v}
    changed_b = {_norm_rel(k): v for k, v in after_b.items() if before_b.get(k) != v}
    gone_a = sorted(_norm_rel(k) for k in set(before_a) - set(after_a))
    gone_b = sorted(_norm_rel(k) for k in set(before_b) - set(after_b))
    if gone_a != gone_b:
        rep["diffs"].append("删除的文件不一致 sh=%s py=%s" % (gone_a, gone_b))
    only_a = sorted(set(changed_a) - set(changed_b))
    only_b = sorted(set(changed_b) - set(changed_a))
    if only_a or only_b:
        rep["diffs"].append("产物集合不一致 只有sh=%s 只有py=%s" % (only_a, only_b))
    for rel in sorted(set(changed_a) & set(changed_b)):
        va, vb = changed_a[rel], changed_b[rel]
        if va == vb:
            continue
        if rel.endswith(".json"):
            try:
                if _norm_obj(json.loads(va.decode("utf-8")), a_root) == _norm_obj(json.loads(vb.decode("utf-8")), b_root):
                    continue
            except Exception:
                pass
        try:                                  # 二进制产物（图片等）只报字节数，不往报告里倒乱码
            va.decode("utf-8"); vb.decode("utf-8")
            is_text = True
        except UnicodeDecodeError:
            is_text = False
        if not is_text:
            rep["diffs"].append("产物 %s 内容不一致（二进制，sh=%d 字节 / py=%d 字节）" % (rel, len(va), len(vb)))
            continue
        na, nb = normalize(va, a_root), normalize(vb, b_root)
        if na != nb:
            rep["diffs"].append("产物 %s 内容不一致" % rel)
            rep.setdefault("file_diff", {})[rel] = _linediff(na, nb)

    rep["sandbox"] = base
    if not keep:
        shutil.rmtree(base, ignore_errors=True)
    return (not rep["diffs"]), rep


def _filter_ignored(diffs, ignore):
    """用例声明的**已知等价豁免**（每条都要在 REPORT 里写清理由），按前缀过滤。"""
    if not ignore:
        return diffs
    return [d for d in diffs if not any(d.startswith(p) for p in ignore)]


def _linediff(a, b, limit=40):
    import difflib
    return list(difflib.unified_diff(a.split("\n"), b.split("\n"), "sh", "py", lineterm=""))[:limit]


def print_report(rep):
    buf = io.StringIO()
    ok = not rep.get("diffs") and not rep.get("error")
    buf.write("%s %s %s\n" % ("PASS" if ok else "FAIL", rep.get("script"), " ".join(rep.get("args") or [])))
    if rep.get("error"):
        buf.write("  错误: %s\n" % rep["error"])
    for d in rep.get("diffs", []):
        buf.write("  ✗ %s\n" % d)
    if "stdout 不一致" in rep.get("diffs", []):
        for ln in _linediff(rep["stdout_sh"], rep["stdout_py"]):
            buf.write("    " + ln + "\n")
    if "stderr 不一致" in rep.get("diffs", []):
        for ln in _linediff(rep["stderr_sh"], rep["stderr_py"]):
            buf.write("    " + ln + "\n")
    for rel, dl in (rep.get("file_diff") or {}).items():
        buf.write("    --- %s ---\n" % rel)
        for ln in dl:
            buf.write("    " + ln + "\n")
    sys.stdout.write(buf.getvalue())
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script")
    ap.add_argument("--fixture")
    ap.add_argument("--subdir")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--all", action="store_true", help="跑 _dev/parity_cases.py 的内置矩阵")
    ap.add_argument("--only", help="--all 时只跑这个脚本名")
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args()

    env = dict(kv.split("=", 1) for kv in a.env) if a.env else {}

    if a.all:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import parity_cases
        bad = 0
        total = 0
        skipped = 0
        for case in parity_cases.build_cases():
            if a.only and case["script"] != a.only:
                continue
            # 真实工程夹具缺席 → 显式跳过并**说清楚少跑了什么**（此前是"矩阵里根本没这条"
            # 的静默 skip：换台机器少跑 8 例，报告照样写"全绿"。2026-09-15 阶段 C）
            need = case.get("requires_fixture")
            if need and (need == parity_cases.REAL_PROJECT_PLACEHOLDER or not os.path.exists(need)):
                print("SKIP  %s | %s —— 未设 $%s（或路径不存在）"
                      % (case["script"], case.get("name", ""), parity_cases.REAL_PROJECT_ENV))
                skipped += 1
                continue
            total += 1
            fx = case.get("fixture_factory")
            tmp = None
            if fx:
                tmp = tempfile.mkdtemp(prefix="fx_")
                fx(tmp)
            ok, rep = compare_case(case["script"], case.get("args", []), tmp or case.get("fixture"),
                                   case.get("env"), case.get("subdir"), keep=a.keep,
                                   sort_lines=case.get("sort_lines", False),
                                   cmd_sh=case.get("cmd_sh"), cmd_py=case.get("cmd_py"),
                                   norm_traceback=case.get("norm_traceback", False))
            rep["diffs"] = _filter_ignored(rep.get("diffs", []), case.get("ignore"))
            ok = not rep["diffs"]
            rep["script"] = case["script"]
            if case.get("name"):
                rep["args"] = ["[%s]" % case["name"]] + list(rep.get("args") or [])
            if not print_report(rep):
                bad += 1
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)
        print("\n合计 %d 例，失败 %d 例%s"
              % (total, bad,
                 ("，跳过 %d 例（真实工程夹具缺席：export %s=<鸿蒙工程根>）"
                  % (skipped, parity_cases.REAL_PROJECT_ENV)) if skipped else ""))
        return 1 if bad else 0

    if not a.script:
        ap.error("需要 --script 或 --all")
    args = a.rest[1:] if a.rest and a.rest[0] == "--" else a.rest
    ok, rep = compare_case(a.script, args, a.fixture, env, a.subdir, keep=a.keep)
    print_report(rep)
    if a.keep:
        print("沙箱保留于 %s" % rep.get("sandbox"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
