#!/usr/bin/env python3
"""兄弟脚本「可不可调」判据的打包态回归 + 打包契约静态闸（2026-09-15，DiceRoller 插件实跑 D6 验收顺带发现）。

病根：调用方用 `os.path.isfile(<兄弟>.py)` 做前置守卫，打包态 `__file__` 在 `_entry.dist/` 里、那里没有 .py，
判据恒 False → 正确的 `sibling_cmd` 被挡在门外，兄弟**静默不被调用**（feat 单 §2 永远 UNRESOLVED、截鸿蒙前的
baseline 安全闸消失、事务复验一律 degraded）。修法：判据收进 `sibling_exec.sibling_available`，与 `sibling_cmd`
同一套冻结态判据；8 处守卫换用它（静态闸首跑又揪出 verify_outcome 的跨 skill 一处）。本文件锁三件事：
  ① `sibling_available` 三种态的判据（源码态 = isfile；冻结态同 skill 看本 _entry + stem 编进去没有；跨 skill 看对方产物）
  ② 8 处守卫守的兄弟在冻结态一律可调，且都满足调度壳的 main() 契约
  ③ 打包契约静态闸：不许 isfile/exists 守 .py、不许 [sys.executable, …] spawn、不许模块级脚本（implicit/broken）
夹具零 app 常量，换项目通用。"""
import ast, json, os, subprocess, sys, textwrap
from pathlib import Path
import pytest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)
import sibling_exec as se                                     # noqa: E402
from test_entry_main_wrappers_0915 import DISPATCH, _run, _w  # noqa: E402  复用 D6 的调度壳同构分派 + 夹具工具

# 调用方 → 它用 sibling_available 守的同 skill 兄弟 stem（2026-09-15 census：vv 共 8 处，含 verify_outcome 的跨 skill 1 处）
GUARDED = {   # verify_outcome 的跨 skill 目标不在同目录，单独由 test_frozen_cross_skill 覆盖
    "render_finding_skeleton": ["inject_spec_oracle"],
    "capture_or_reuse": ["check_android_screenshot"],
    "dispatch_phase2_batches": ["check_blackbox_evidence", "materialize_blackbox_to_factree", "check_android_screenshot"],
    "reverify_transaction": ["verify_outcome"],
    "materialize_blackbox_to_factree": ["resize_screenshot"],
}


def _frozen(monkeypatch, here):
    """模拟冻结态：sys.frozen=True（sibling_exec 的判据之一）+ 把本 skill 的 _HERE 指到 here。"""
    monkeypatch.setattr(se.sys, "frozen", True, raising=False)
    monkeypatch.setattr(se, "_HERE", Path(here).resolve())


# ───────── ① 判据 ─────────
def test_source_mode_equals_isfile(tmp_path):
    assert not getattr(sys, "frozen", False)
    assert se.sibling_available(os.path.join(SCRIPTS, "inject_spec_oracle.py")) is True
    assert se.sibling_available(os.path.join(SCRIPTS, "no_such_sibling_zz.py")) is False
    p = tmp_path / "x.py"; assert se.sibling_available(p) is False
    p.write_text("pass\n"); assert se.sibling_available(p) is True


def test_frozen_same_skill_needs_entry_and_bundled_stem(monkeypatch, tmp_path):
    _frozen(monkeypatch, tmp_path)
    real = tmp_path / "check_android_screenshot.py"          # 冻结态磁盘上没有这个 .py
    assert not real.exists()
    assert se.sibling_available(real) is False               # 本 _entry 不在 → 不可调
    (tmp_path / se._ENTRY_NAME).write_bytes(b"")
    assert se.sibling_available(real) is True                # _entry 在 + stem 能 find_spec → 可调（isfile 会说 False）
    assert se.sibling_available(tmp_path / "no_such_stem_zz.py") is False   # 没编进去的 stem 不算可调


def test_frozen_cross_skill(monkeypatch, tmp_path):
    _frozen(monkeypatch, tmp_path / "me")
    other = tmp_path / "other" / "scripts"; other.mkdir(parents=True)
    tgt = other / "scenario_run.py"
    assert se.sibling_available(tgt) is False                # 对方既无产物也无源码
    tgt.write_text("pass\n")
    assert se.sibling_available(tgt) is True                 # 对方源码在（sibling_cmd 会回落系统解释器）
    tgt.unlink()
    ent = other / "bin" / se._platform_tag() / "_entry.dist" / se._ENTRY_NAME
    ent.parent.mkdir(parents=True); ent.write_bytes(b""); ent.chmod(0o755)
    assert se.sibling_available(tgt) is True                 # 对方编译产物在


# ───────── ② 守卫守的兄弟（8 处）：冻结态可调 + 满足调度壳 main() 契约 ─────────
@pytest.mark.parametrize("caller,stems", sorted(GUARDED.items()))
def test_guarded_siblings_dispatchable_when_frozen(monkeypatch, tmp_path, caller, stems):
    src = open(os.path.join(SCRIPTS, caller + ".py"), encoding="utf-8").read()
    assert "sibling_available" in src, f"{caller}.py 没用 sibling_available 守兄弟"
    _frozen(monkeypatch, tmp_path); (tmp_path / se._ENTRY_NAME).write_bytes(b"")
    for stem in stems:
        assert se.sibling_available(tmp_path / f"{stem}.py") is True, (caller, stem)
        tree = ast.parse(open(os.path.join(SCRIPTS, stem + ".py"), encoding="utf-8").read())
        main = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
        assert main, f"{stem}.py 无 main()：调度壳 `_entry.bin {stem}` 会 AttributeError"
        req = main[0].args.args[:len(main[0].args.args) - len(main[0].args.defaults)]
        assert len(req) <= 1, f"{stem}.main 必填位置参数 {len(req)} 个，调度壳最多传 1 个"


# ───────── ②' 端到端：render_finding_skeleton 的 feat 单 §2 真的拿到验收行（源码态 & 调度壳态一致） ─────────
def test_feat_ticket_gets_spec_lines_in_both_modes(tmp_path):
    outs = {}
    for mode in ("src", "bin"):
        root = str(tmp_path / mode); base = os.path.join(root, "spec", "baseline")
        _w(os.path.join(base, "features", "F001-x.md"),
           "---\nfeature_id: F001\nfeature_name: 占位功能\n---\n# F001: 占位功能\n\n## 验收标准\n- [ ] 判据一\n- [ ] 判据二\n")
        _w(os.path.join(base, "feature-index.md"),
           "## 功能清单\n\n| ID | 功能 | 状态 | 涉及页面 |\n|---|---|---|---|\n| F001 | 占位功能 | 完成 | PageAActivity |\n")
        rc, out, err = _run(mode, "build_spec_oracle", ["spec/baseline", "spec/visual-verify/spec_oracle.json"], {}, root)
        assert rc == 0, (mode, err)
        rc, out, err = _run(mode, "render_finding_skeleton",
                            ["--project-root", ".", "--round", "1", "--layer", "feat", "--id", "X_feat", "--title", "t",
                             "--kind", "IMPL_MISSING", "--severity", "P1", "--category-pattern", "x", "--page", "PageA",
                             "--trip", "trip_1_logged_out", "--feature-path", "更多>占位功能"], {}, root)
        assert rc == 0, (mode, rc, out, err)
        md = open(os.path.join(root, "spec", "fix", "round-1", "feat", "X_feat.md"), encoding="utf-8").read()
        assert "> 验收标准 (F001" in md and "判据一" in md, (mode, md[md.find("## 2"):][:400])
        assert "UNRESOLVED" not in md, (mode, md[md.find("## 2"):][:400])
        outs[mode] = md.replace(root, "<ROOT>")
    assert outs["src"] == outs["bin"]


# ───────── ③ 打包契约静态闸（换项目通用；扫本 skill 全部脚本） ─────────
def _py_path_expr(node, pynames):
    """表达式是不是「某个 .py 的路径」：字面量 / os.path.join(…, "x.py") / <dir> / "x.py" / f"…x.py" /
    Path(x)·.resolve()·.expanduser() 包一层 / 在**当前作用域**被赋成上述的名字。"""
    if isinstance(node, ast.Constant): return isinstance(node.value, str) and node.value.endswith(".py")
    if isinstance(node, ast.Call):
        f = ast.unparse(node.func)
        if f.endswith("join") and node.args: return _py_path_expr(node.args[-1], pynames)
        if f.endswith("Path") and node.args: return _py_path_expr(node.args[0], pynames)          # Path(x) 透明
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("resolve", "absolute", "expanduser"):
            return _py_path_expr(node.func.value, pynames)                                          # Path(x).resolve() 透明
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div): return _py_path_expr(node.right, pynames)
    if isinstance(node, ast.JoinedStr): return any(isinstance(v, ast.Constant) and str(v.value).endswith(".py") for v in node.values)
    if isinstance(node, ast.Name): return node.id in pynames
    return False


def _contract_violations(src: str):
    """返回违规行列表。作用域按「模块级 ∪ 所在顶层函数」解析名字（跨函数同名不串台）；
    唯一豁免：except 兜底分支里的 isfile，且所在函数确实先试过 sibling_available（materialize._resize_available 形态）。"""
    tree = ast.parse(src); src_lines = src.splitlines()
    parents = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n): parents[c] = n
    def _top_func(n):
        top = None
        while n in parents:
            n = parents[n]
            if isinstance(n, ast.FunctionDef): top = n
        return top
    def _in_except(n):
        while n in parents:
            n = parents[n]
            if isinstance(n, ast.ExceptHandler): return True
            if isinstance(n, ast.FunctionDef): return False
        return False
    def _names(scope_nodes, pred):
        out = set()
        for sn in scope_nodes:
            for n in ast.walk(sn):
                if isinstance(n, ast.Assign) and pred(n.value):
                    out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        return out
    mod_stmts = [n for n in tree.body if not isinstance(n, ast.FunctionDef)]
    mod_py = _names(mod_stmts, lambda v: _py_path_expr(v, set()))
    mod_exe = _names(mod_stmts, lambda v: ast.unparse(v) == "sys.executable")
    cache = {}
    def _scope(n):
        f = _top_func(n)
        if f not in cache:
            py = (mod_py | _names([f], lambda v: _py_path_expr(v, mod_py))) if f else mod_py
            exe = (mod_exe | _names([f], lambda v: ast.unparse(v) == "sys.executable")) if f else mod_exe
            cache[f] = (py, exe, f is not None and "sibling_available" in ast.unparse(f))
        return cache[f]
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call): continue
        f = ast.unparse(n.func); py, exe, tried_helper = _scope(n)
        guard = ((f.endswith(".isfile") or f.endswith(".exists")) and n.args and _py_path_expr(n.args[0], py)) or \
                (isinstance(n.func, ast.Attribute) and n.func.attr in ("is_file", "exists") and _py_path_expr(n.func.value, py))
        if guard and not (tried_helper and _in_except(n)):
            out.append(f"{n.lineno}: {ast.unparse(n)[:70]}  ← 用 sibling_exec.sibling_available 判兄弟在不在（打包态无 .py）")
        if f.startswith("subprocess.") and n.args and isinstance(n.args[0], ast.List) and n.args[0].elts \
                and "packaging-contract-ok" not in src_lines[n.lineno - 1]:   # 逐行豁免：打包器 EXCLUDE_STEMS 按源码发运、永不冻结的编排壳
            e0 = n.args[0].elts[0]
            if ast.unparse(e0) == "sys.executable" or (isinstance(e0, ast.Name) and e0.id in exe):
                out.append(f"{n.lineno}: {ast.unparse(n)[:70]}  ← 用 sibling_exec.sibling_cmd（打包态 sys.executable 是 libpython）")
    return out


def test_contract_lint_selfcheck():
    """lint 自身的变异自检：该抓的抓、豁免只在 except 兜底、跨函数同名不误报、Path()/别名绕不过。"""
    hit = lambda src: len(_contract_violations(textwrap.dedent(src)))
    assert hit('def f():\n    p = os.path.join(D, "x.py")\n    if os.path.isfile(p): pass\n') == 1
    assert hit('if os.path.exists(os.path.join(D, "x.py")): pass\n') == 1
    assert hit('p = D / "x.py"\nif p.exists(): pass\n') == 1
    assert hit('def f():\n    p = os.path.join(D, "x.py")\n    if Path(p).resolve().is_file(): pass\n') == 1      # Path() 包装绕不过
    assert hit('def a():\n    q = os.path.join(D, "x.py")\ndef b(q):\n    return os.path.isfile(q)\n') == 0        # 跨函数同名不串台
    fallback = ('def g():\n    p = os.path.join(D, "x.py")\n    try:\n        from sibling_exec import sibling_available\n'
                '        return sibling_available(p)\n    except Exception:\n        return os.path.isfile(p)\n')
    assert hit(fallback) == 0                                                                                    # except 兜底豁免
    assert hit(fallback.replace("        return sibling_available(p)\n",
                                "        if os.path.isfile(p): pass\n        return sibling_available(p)\n")) == 1  # 同函数 try 体里的真违规不得被放过
    assert hit('subprocess.run([sys.executable, "x.py"])\n') == 1
    assert hit('subprocess.run([sys.executable, "x.py"])   # packaging-contract-ok: keep-source shim\n') == 0   # 逐行豁免
    assert hit('PY = sys.executable\ndef f():\n    subprocess.run([PY, "x.py"])\n') == 1                          # 别名绕不过
    assert hit('def f():\n    subprocess.run(sibling_cmd(p, []))\n') == 0
    assert hit('if os.path.isfile(os.path.join(D, "data.json")): pass\n') == 0                                  # 数据档不管


def test_packaging_contract_lint():
    bad = {}
    for fn in sorted(os.listdir(SCRIPTS)):
        if not fn.endswith(".py") or fn == "sibling_exec.py": continue     # sibling_exec 自己就是判据实现
        v = _contract_violations(open(os.path.join(SCRIPTS, fn), encoding="utf-8").read())
        if v: bad[fn] = v
    assert not bad, "打包契约违规：\n" + "\n".join(f"  {k}:{x}" for k, vs in bad.items() for x in vs)
    # 模块级脚本闸：借打包器自己的分类（唯一实现，不抄第二份）；仓库外（发行包）找不到就跳过
    cfg = None
    for up in Path(SCRIPTS).resolve().parents:
        cand = up / "build" / "script-compression" / "scripts" / "config.py"
        if cand.is_file(): cfg = cand; break
    if cfg is None:
        pytest.skip("找不到 build/script-compression/scripts/config.py（发行包布局），跳过 implicit/broken 分类闸")
    sys.path.insert(0, str(cfg.parent))
    import importlib; config = importlib.import_module("config")
    cls = config.classify_scripts_dir(SCRIPTS)
    offenders = {k: v for k, v in cls.items() if v in ("implicit", "broken")}
    assert not offenders, f"模块级脚本（打包态 .main 不存在 / 守卫不执行）: {offenders}"
