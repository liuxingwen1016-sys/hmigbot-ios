#!/usr/bin/env python3
"""打包入口契约回归（2026-09-15 DiceRoller 实跑 D6）：
build/script-compression 的调度壳只会 `importlib.import_module(stem).main()`——脚本若把逻辑写在模块级、
没有 main()，源码态 `python x.py` 能跑，打包态一进 _entry.bin 就 AttributeError: module has no attribute 'main'
（build_judge_input 实锤，同病 6 个）。本测试锁两件事：
  ① 6 个脚本的 main(argv=None) 契约：顶层只剩 import/docstring/def main/__main__ 守卫；main 无必填位置参数；
  ② 源码态 与 调度壳态（sys.argv=[stem.py,*args] → import → main()）在真实小夹具上 退出码/stdout/产物 一致。
夹具零 app 常量（占位页名），换项目通用。"""
import ast, inspect, json, os, re, subprocess, sys, textwrap
import pytest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIX = ["build_judge_input", "build_spec_oracle", "inject_spec_oracle",
       "merge_capture_dirs", "slice_batches", "trip_end_slice"]

# 与 build_binaries.ENTRY_TEMPLATE 同构的最小调度壳（只保留分派逻辑，不带 UTF-8 猴补丁）
DISPATCH = textwrap.dedent("""
    import importlib, inspect, sys
    scripts, stem, args = sys.argv[1], sys.argv[2], sys.argv[3:]
    sys.path.insert(0, scripts)
    sys.argv = [stem + ".py", *args]
    fn = importlib.import_module(stem).main
    required = [p for p in inspect.signature(fn).parameters.values()
                if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    rc = fn(sys.argv[1]) if required else fn()
    sys.exit(rc if isinstance(rc, int) else 0)
""")


@pytest.mark.parametrize("stem", SIX)
def test_entry_contract(stem):
    src = open(os.path.join(SCRIPTS, stem + ".py"), encoding="utf-8").read()
    tree = ast.parse(src)
    kinds = []
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            kinds.append("import")
        elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant):
            kinds.append("doc")
        elif isinstance(n, ast.FunctionDef) and n.name == "main":
            kinds.append("main")
        elif isinstance(n, ast.If) and "__main__" in ast.unparse(n.test):
            kinds.append("guard")
        elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and ast.unparse(n.value).startswith("sys.path.insert"):
            kinds.append("syspath")
        else:
            pytest.fail(f"{stem}.py 顶层仍有模块级逻辑（打包态不会执行）: {ast.unparse(n)[:80]}")
    assert "main" in kinds and "guard" in kinds, f"{stem}.py 缺 def main / __main__ 守卫: {kinds}"
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    required = [a.arg for a in main.args.args[:len(main.args.args) - len(main.args.defaults)]]
    assert required == [], f"{stem}.main 有必填位置参数 {required}：调度壳会按 main(sys.argv[1]) 传单个路径"
    # 正文里直接绑定（import/赋值/def）的名字不得在绑定之前就被读——否则整个函数域内它是局部名 → UnboundLocalError
    bound, loads = {}, {}
    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, n): bound.setdefault(n.name, n.lineno)
        def visit_Lambda(self, n): pass
        def visit_ListComp(self, n): pass
        visit_SetComp = visit_DictComp = visit_GeneratorExp = visit_ListComp
        def visit_Import(self, n):
            for a in n.names: bound.setdefault((a.asname or a.name).split(".")[0], n.lineno)
        def visit_ImportFrom(self, n):
            for a in n.names: bound.setdefault(a.asname or a.name, n.lineno)
        def visit_Name(self, n):
            (bound if isinstance(n.ctx, ast.Store) else loads).setdefault(n.id, n.lineno)
    v = V()
    for st in main.body: v.visit(st)
    risky = {k: (loads[k], bound[k]) for k in bound if k in loads and loads[k] < bound[k]}
    assert not risky, f"{stem}.main 内先读后绑定（UnboundLocalError）: {risky}"


# ───────── 夹具（零 app 常量） ─────────
def _w(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        if isinstance(obj, str): f.write(obj)
        else: json.dump(obj, f, ensure_ascii=False, indent=1)
    return p


def _png(p, w=12, h=24):
    Image = pytest.importorskip("PIL.Image")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    Image.new("RGB", (w, h), (10, 20, 30)).save(p)
    return p


def _plan():
    return {"roots": [{"node": "PageRoot"}], "steps": [
        {"step": "s0", "action": "coldstart", "to": "PageRoot"},
        {"step": "s1", "action": "tap", "from": "PageRoot", "to": "PageA", "kind": "tab_switch",
         "match": {"primary": "TabA"}},
        {"step": "s2", "action": "reconcile", "node": "PageA",
         "elements": [{"trigger_text": "DangerAction", "rid": "btn_x", "defer_to_trip_end": True}]},
        {"step": "s3", "action": "back", "to": "PageRoot"},
        {"step": "s4", "action": "tap", "from": "PageRoot", "to": "PageB", "kind": "tab_switch",
         "match": {"primary": "TabB"}},
        {"step": "s5", "action": "reconcile", "node": "PageB", "elements": []},
    ]}


def _manifest(status, obs):
    return {"role": "capture", "started_at": "2026-09-15T00:00:00",
            "pages_status": {"PageA": status}, "per_page": {"PageA": {"behavior_observations": obs}},
            "escalations": [], "need_scenarios": [], "llm_intervention": []}


def _cases(tmp):
    """返回 {stem: (args, env, artifact_globs)}；夹具在 tmp 下按 stem 分目录，两种运行态各建一份。"""
    c = {}
    base = os.path.join(tmp, "spec", "baseline")
    _w(os.path.join(base, "features", "F001-x.md"),
       "---\nfeature_id: F001\nfeature_name: 占位功能\n---\n# F001: 占位功能\n\n## 验收标准\n- [ ] 判据一\n- [ ] 判据二\n\n## 其它\n略\n")
    _w(os.path.join(base, "feature-index.md"),
       "## 功能清单\n\n| ID | 功能 | 状态 | 涉及页面 |\n|---|---|---|---|\n| F001 | 占位功能 | 完成 | PageAActivity, PageB(+2 子页) |\n")
    oracle = os.path.join(tmp, "spec", "visual-verify", "spec_oracle.json")
    c["build_spec_oracle"] = ([base, oracle], {}, [oracle])
    c["inject_spec_oracle"] = (["PageA", "更多>占位功能"], {"SPEC_ORACLE": oracle}, [])

    plan = _w(os.path.join(tmp, "plan.json"), _plan())
    c["slice_batches"] = (["--plan", plan, "--out-dir", os.path.join(tmp, "batches"), "--strip-login"], {},
                          [os.path.join(tmp, "batches", "*.json")])
    enc = _w(os.path.join(tmp, "encountered.json"),
             {"items": [{"node": "PageA", "name": "DangerAction", "located": True}]})
    c["trip_end_slice"] = (["--plan", plan, "--encountered", enc, "--out", os.path.join(tmp, "trip_end.json")], {},
                           [os.path.join(tmp, "trip_end.json")])

    d1, d2 = os.path.join(tmp, "cap1"), os.path.join(tmp, "cap2")
    _w(os.path.join(d1, "capture_manifest.json"), _manifest("blocked", []))
    _w(os.path.join(d2, "capture_manifest.json"),
       _manifest({"status": "captured"}, [{"trigger_text": "DangerAction", "rid": "btn_x", "outcome": "encountered_destructive"}]))
    _w(os.path.join(d1, "run.jsonl"), '{"step":"s1","action":"tap","from":"PageRoot","to":"PageA","verdict":"ok"}\n')
    _png(os.path.join(d2, "shots", "PageA.jpeg"))
    c["merge_capture_dirs"] = (["--out", os.path.join(tmp, "merged"), d1, d2], {},
                               [os.path.join(tmp, "merged", "capture_manifest.json"), os.path.join(tmp, "merged", "run.jsonl")])

    root = os.path.join(tmp, "proj")
    cap = os.path.join(root, "replay", "run1")
    _w(os.path.join(cap, "capture_manifest.json"),
       _manifest({"status": "captured"}, [{"trigger_text": "DangerAction", "rid": "btn_x", "outcome": "encountered_destructive"}]))
    _w(os.path.join(cap, "run.jsonl"), '{"step":"s1","action":"tap","from":"PageRoot","to":"PageA","verdict":"ok","batch":1}\n')
    _png(os.path.join(cap, "shots", "PageA.jpeg"))
    _w(os.path.join(cap, "dumps", "PageA.hmos.json"), {"attributes": {"bounds": "[0,0][100,200]", "text": ""},
                                                       "children": [{"attributes": {"text": "DangerAction", "bounds": "[0,50][100,80]"}}]})
    android = os.path.join(root, "spec", "visual-verify", "screenshots", "android")
    _png(os.path.join(android, "PageA.png")); _png(os.path.join(android, "PageMissing.png"))
    _w(os.path.join(android, "PageA.android.xml"),
       '<hierarchy><node text="DangerAction" resource-id="app:id/btn_x" bounds="[0,50][100,80]"/></hierarchy>')
    tree = _w(os.path.join(root, "tree.json"), {"pages": [{"id": "PageA", "functional_checks": [
        {"name": "DangerAction", "android_trusted": True, "expected_android": "弹确认窗"}]}]})
    c["build_judge_input"] = (["--root", root, "--capture-dir", cap, "--android-baseline-dir", android,
                               "--tree", tree, "--round", "1", "--trip", "trip_1_logged_out", "--plan", plan], {},
                              [os.path.join(cap, "judge_input_round1.json"),
                               os.path.join(root, "spec", "visual-verify", "screenshots", "sbs", "round-1", "trip_1_logged_out", "*.jpeg")])
    return c


def _run(mode, stem, args, env, cwd):
    if mode == "src":
        cmd = [sys.executable, os.path.join(SCRIPTS, stem + ".py"), *args]
    else:
        cmd = [sys.executable, "-c", DISPATCH, SCRIPTS, stem, *args]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **env}, timeout=120)
    return r.returncode, r.stdout, r.stderr


def _snapshot(globs, tmp):
    import glob
    out = {}
    for g in globs:
        for p in sorted(glob.glob(g)):
            rel = os.path.relpath(p, tmp)
            if p.endswith(".json"):
                out[rel] = json.dumps(json.load(open(p, encoding="utf-8")), ensure_ascii=False, sort_keys=True).replace(tmp, "<TMP>")
            else:
                out[rel] = os.path.getsize(p)
    return out


@pytest.mark.parametrize("stem", SIX)
def test_src_and_dispatcher_equivalent(stem, tmp_path):
    """同一夹具下 源码态 与 调度壳态 退出码/stdout/产物 一致，且都成功（rc=0）。"""
    snaps = {}
    for mode in ("src", "bin"):
        tmp = str(tmp_path / mode)
        cases = _cases(tmp)
        args, env, globs = cases[stem]
        if stem == "inject_spec_oracle":   # 先建旁路再注入（同一运行态下串行）
            rc0, *_ = _run(mode, "build_spec_oracle", cases["build_spec_oracle"][0], {}, tmp)
            assert rc0 == 0
        rc, out, err = _run(mode, stem, args, env, tmp)
        assert rc == 0, f"[{mode}] {stem} rc={rc}\nstdout:\n{out}\nstderr:\n{err}"
        assert "Traceback" not in err, f"[{mode}] {stem} stderr:\n{err}"
        snaps[mode] = (rc, out.replace(tmp, "<TMP>"), _snapshot(globs, tmp))
        if globs:
            assert snaps[mode][2], f"[{mode}] {stem} 没产出预期产物 {globs}"
        else:   # 只写 stdout 的脚本（inject_spec_oracle）：锁 stdout 里的解析结果
            assert '"resolved": true' in out, f"[{mode}] {stem} stdout:\n{out}"
    assert snaps["src"] == snaps["bin"], f"{stem}: 源码态与调度壳态不一致\nsrc={snaps['src']}\nbin={snaps['bin']}"


def test_inject_usage_rc1(tmp_path):
    """无参 → usage 到 stderr、退出码 1（原 sys.exit(1) 语义在调度壳态经 return 1 保留）。"""
    for mode in ("src", "bin"):
        rc, out, err = _run(mode, "inject_spec_oracle", [], {}, str(tmp_path))
        assert rc == 1 and "usage:" in err and out.strip() == "", (mode, rc, out, err)


def test_trip_end_empty_pass_rc0(tmp_path):
    """无可验元素 → 空收尾趟、rc=0（原 raise SystemExit(0) 语义经 return 0 保留）。"""
    plan = _plan(); plan["steps"][2]["elements"] = []
    p = _w(str(tmp_path / "plan.json"), plan)
    for mode in ("src", "bin"):
        rc, out, err = _run(mode, "trip_end_slice", ["--plan", p, "--out", str(tmp_path / f"o_{mode}.json")], {}, str(tmp_path))
        assert rc == 0 and '"target_nodes": 0' in out, (mode, rc, out, err)


def test_stitch_failure_recorded_in_both_modes(tmp_path):
    """验收 minor 1：`STITCH_FAILED` 是本次唯一从模块级迁进 main 的可变状态，由嵌套函数 stitch() 以闭包 .append。
    损坏 PNG 强制拼接失败 → rc 仍 0、`sbs_stitch_failed` 记 1 条、该页 sbs=null；源码态与调度壳态一致。"""
    snaps = {}
    for mode in ("src", "bin"):
        tmp = str(tmp_path / mode)
        cases = _cases(tmp)
        args, env, _ = cases["build_judge_input"]
        bad = os.path.join(tmp, "proj", "spec", "visual-verify", "screenshots", "android", "PageA.png")
        with open(bad, "wb") as f: f.write(b"not-a-png")
        rc, out, err = _run(mode, "build_judge_input", args, env, tmp)
        assert rc == 0 and "sbs 拼接失败" in err, (mode, rc, err[-600:])
        ji = json.load(open(os.path.join(tmp, "proj", "replay", "run1", "judge_input_round1.json"), encoding="utf-8"))
        fails = ji.get("sbs_stitch_failed") or []
        assert len(fails) == 1 and fails[0]["page_id"] == "PageA", (mode, fails)
        page = next(p for p in ji["pages"] if p["page_id"] == "PageA")
        assert page.get("sbs") is None, (mode, page.get("sbs"))
        snaps[mode] = (rc, [f["page_id"] for f in fails], fails[0]["error"].replace(tmp, "<TMP>"), out.replace(tmp, "<TMP>"))
    assert snaps["src"] == snaps["bin"], snaps


def test_slice_batches_non_coldstart_rc1(tmp_path):
    """验收 minor 2：slice_batches 保留的 `raise SystemExit("计划首步必须是 coldstart")` 是 6 个脚本里唯一的字符串 SystemExit 出口；
    调度壳态它穿透 `rc = fn()` → 进程 rc=1 + 提示进 stderr，与源码态一致。"""
    plan = _plan(); plan["steps"] = plan["steps"][1:]          # 首步变成 tap
    p = _w(str(tmp_path / "plan.json"), plan)
    for mode in ("src", "bin"):
        rc, out, err = _run(mode, "slice_batches", ["--plan", p, "--out-dir", str(tmp_path / f"b_{mode}")], {}, str(tmp_path))
        assert rc == 1 and "计划首步必须是 coldstart" in err and out.strip() == "", (mode, rc, out, err)
        assert not os.path.isdir(str(tmp_path / f"b_{mode}")), mode
