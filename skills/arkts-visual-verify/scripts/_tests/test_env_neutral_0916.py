#!/usr/bin/env python3
"""环境中立回归（2026-09-16 DiceRoller codex 实跑 C1 + claude 实跑 D8）。

C1：前置探针按 ~/.claude/agents/<a>.md 找 agent，codex 线 agent 在 .codex/agents/<a>.toml → 恒「未注册」→ UNIT 级 ABORT，整条 codex 线挡死。
D8：next_walk 用 __file__ 上溯找 references/ 模板，打包态 __file__ 在 _entry.dist 里 → FileNotFoundError。
修法：环境定位收进 sibling_exec 一处（scripts_dir / skill_dir / skills_root / skills_root_candidates / find_in_skills /
agent_search_dirs / agent_registered），两种平台布局都认、不判环境；业务脚本只调它。本文件锁：
  ① 定位函数在 源码态 / 冻结态布局 / ARKTS_SKILL_DIR（本 skill 与他人 skill）下的判据
  ② agent_registered：.claude/agents/*.md、.codex/agents/*.toml、插件缓存兄弟 agents/ 三种布局
  ③ 探针端到端：codex 形状工程与 claude 形状工程都 ✅ agent；显式 --skills-root 输出与既往一字不差（golden 047–052 另锁）
  ④ 静态闸：业务脚本不得再自己拼 ".claude"/".codex"/".agents" 路径或 <agent>.md（唯一实现在 sibling_exec；逐行豁免须写 env-literal-ok）
夹具零 app 常量。"""
import ast, os, subprocess, sys
from pathlib import Path
import pytest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)
import sibling_exec as se   # noqa: E402

PROBE = os.path.join(SCRIPTS, "check_dimension_prereqs.py")


# ───────── ① 定位函数 ─────────
def test_source_mode_locations(monkeypatch):
    monkeypatch.delenv("ARKTS_SKILL_DIR", raising=False)
    assert se.scripts_dir() == Path(SCRIPTS).resolve()
    assert se.skill_dir() == Path(SCRIPTS).resolve().parent
    assert se.skills_root() == Path(SCRIPTS).resolve().parent.parent
    assert (se.skill_dir() / "references").is_dir()          # D8 的资产目录真在这里


def test_frozen_layout_walks_up_to_scripts(monkeypatch, tmp_path):
    """冻结态 _HERE = <scripts>/bin/<平台>/_entry.dist → scripts_dir 必须回到 <scripts>，而不是 bin/。"""
    monkeypatch.delenv("ARKTS_SKILL_DIR", raising=False)
    scripts = tmp_path / "skills" / "arkts-visual-verify" / "scripts"
    here = scripts / "bin" / "macos-arm64" / "_entry.dist"; here.mkdir(parents=True)
    monkeypatch.setattr(se, "_HERE", here.resolve())
    assert se.scripts_dir() == scripts.resolve()
    assert se.skill_dir() == (tmp_path / "skills" / "arkts-visual-verify").resolve()
    assert se.skills_root() == (tmp_path / "skills").resolve()
    pre = scripts / "_entry.dist"; pre.mkdir()                                            # 装配前布局（打包器 verify 跑的就是它）
    monkeypatch.setattr(se, "_HERE", pre.resolve())
    assert se.scripts_dir() == scripts.resolve()
    other = tmp_path / "skills" / "arkts-visual-verify" / "scripts_alt"; other.mkdir()
    monkeypatch.setenv("ARKTS_SKILL_DIR", str(other))                                      # 装配前布局下 env 指向本 skill 的另一份 → 认
    assert se.scripts_dir() == other.resolve()
    monkeypatch.delenv("ARKTS_SKILL_DIR")
    monkeypatch.setattr(se, "_HERE", (tmp_path / "elsewhere" / "_entry.dist").resolve())   # 祖先里没有 scripts → 原样
    assert se.scripts_dir() == (tmp_path / "elsewhere" / "_entry.dist").resolve()


def test_env_only_trusted_when_it_points_to_this_skill(monkeypatch, tmp_path):
    """ARKTS_SKILL_DIR 会被子进程继承：指向本 skill 的另一份安装 → 认；指向别的 skill → 不认（#103 归因）。"""
    mine_other_install = tmp_path / "plugins" / "x" / "skills" / "arkts-visual-verify" / "scripts"; mine_other_install.mkdir(parents=True)
    foreign = tmp_path / "plugins" / "x" / "skills" / "arkts-scenario-runner" / "scripts"; foreign.mkdir(parents=True)
    monkeypatch.setenv("ARKTS_SKILL_DIR", str(mine_other_install))
    assert se.scripts_dir() == mine_other_install.resolve()
    monkeypatch.setenv("ARKTS_SKILL_DIR", str(foreign))
    assert se.scripts_dir() == Path(SCRIPTS).resolve()                     # 别人的目录 → 回落自己
    monkeypatch.setenv("ARKTS_SKILL_DIR", str(tmp_path / "no_such_dir" / "scripts"))
    assert se.scripts_dir() == Path(SCRIPTS).resolve()                     # 不存在 → 回落自己


def test_skills_root_candidates_and_find(monkeypatch, tmp_path):
    monkeypatch.delenv("ARKTS_SKILL_DIR", raising=False)
    here = tmp_path / "src" / "skills" / "arkts-visual-verify" / "scripts"; here.mkdir(parents=True)
    monkeypatch.setattr(se, "_HERE", here.resolve())          # 别让开发仓自己的 skills 根（含真 scenario_run.py）混进候选
    home, proj = tmp_path / "home", tmp_path / "proj"
    c = se.skills_root_candidates(home, proj)
    assert c[0] == str(se.skills_root())
    assert str(home / ".claude" / "skills") in c and str(home / ".agents" / "skills") in c
    assert str(proj / ".claude" / "skills") in c and str(proj / ".agents" / "skills") in c and str(proj / "skills") in c
    assert se.find_in_skills("arkts-scenario-runner/scripts/scenario_run.py", home, proj) is None
    tgt = proj / ".agents" / "skills" / "arkts-scenario-runner" / "scripts" / "scenario_run.py"
    tgt.parent.mkdir(parents=True); tgt.write_text("pass\n")
    assert se.find_in_skills("arkts-scenario-runner/scripts/scenario_run.py", home, proj) == str(tgt)   # codex 工程级布局找得到


# ───────── ② agent_registered 三种布局 ─────────
@pytest.mark.parametrize("layout", ["claude_home", "codex_home", "claude_proj", "codex_proj", "plugin_sibling", "none"])
def test_agent_registered_layouts(tmp_path, layout):
    home, proj = tmp_path / "home", tmp_path / "proj"
    root = tmp_path / "cache" / "skills"; (root / "arkts-visual-verify").mkdir(parents=True)
    files = {
        "claude_home": home / ".claude" / "agents" / "visual-fixer.md",
        "codex_home": home / ".codex" / "agents" / "visual-fixer.toml",
        "claude_proj": proj / ".claude" / "agents" / "visual-fixer.md",
        "codex_proj": proj / ".codex" / "agents" / "visual-fixer.toml",
        "plugin_sibling": tmp_path / "cache" / "agents" / "visual-fixer.md",
    }
    if layout != "none":
        files[layout].parent.mkdir(parents=True); files[layout].write_text("x")
    hit = se.agent_registered("visual-fixer", home, proj, [str(root)])
    assert (hit == str(files[layout])) if layout != "none" else (hit is None)
    assert se.agent_registered("visual-fixer-reviewer", home, proj, [str(root)]) is None
    dirs = se.agent_search_dirs(home, proj, [str(root)])
    assert dirs[:4] == [str(home / ".claude" / "agents"), str(home / ".codex" / "agents"),
                        str(proj / ".claude" / "agents"), str(proj / ".codex" / "agents")]   # 标准 4 个在前（探针"另查过"以此切分）


# ───────── ③ 探针端到端：两种工程形状 ─────────
def _skills_root(tmp, kind):
    """造一个像 skills 根的目录：含 arkts-visual-verify/ 与 arkts-scenario-runner/scripts/scenario_run.py。"""
    r = tmp / kind / "skills"
    (r / "arkts-visual-verify" / "scripts").mkdir(parents=True)   # 真实布局有 scripts/（scripts_dir 的自标记要它存在）
    (r / "arkts-scenario-runner" / "scripts").mkdir(parents=True)
    (r / "arkts-scenario-runner" / "scripts" / "scenario_run.py").write_text("pass\n")
    return r


def _probe_copy(tmp):
    """探针副本放进 tmp 的 skills 布局里跑：直接跑仓库里的探针会把开发仓的 arkts-scenario-runner / arkts-agents 找出来，测不出"缺失"。"""
    d = tmp / "probe_home" / "skills" / "arkts-visual-verify" / "scripts"; d.mkdir(parents=True, exist_ok=True)
    for fn in ("check_dimension_prereqs.py", "sibling_exec.py"):
        (d / fn).write_bytes((Path(SCRIPTS) / fn).read_bytes())
    return d / "check_dimension_prereqs.py"


def _run_probe(proj, home, skills_root=None, env=None):
    probe = _probe_copy(Path(home).parent)
    cmd = [sys.executable, str(probe), "--project-root", str(proj)] + (["--skills-root", str(skills_root)] if skills_root else [])
    e = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    for k in ("ARKTS_SKILL_DIR", "SKILLS_ROOT", "CLAUDE_PROJECT_DIR"): e.pop(k, None)   # 先清宿主环境，再放用例自己要的
    e.update(env or {})
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=e, timeout=60)
    return r.returncode, r.stdout + r.stderr


def test_probe_codex_shaped_project_registers_toml_agents(tmp_path):
    """codex 工程：<project>/.agents/skills/… + <project>/.codex/agents/*.toml → 两个 agent ✅（改前恒 ❌ → exit 2 ABORT）。"""
    proj, home = tmp_path / "proj", tmp_path / "home"
    root = proj / ".agents" / "skills"
    (root / "arkts-visual-verify").mkdir(parents=True)
    (root / "arkts-scenario-runner" / "scripts").mkdir(parents=True); (root / "arkts-scenario-runner" / "scripts" / "scenario_run.py").write_text("pass\n")
    for a in ("visual-fixer", "visual-fixer-reviewer"):
        (proj / ".codex" / "agents").mkdir(parents=True, exist_ok=True); (proj / ".codex" / "agents" / f"{a}.toml").write_text('name = "%s"\n' % a)
    (root / "hmos-fix-build-errors").mkdir()          # codex 线的连字符目录名
    rc, out = _run_probe(proj, home, skills_root=root)
    assert "✅ agent visual-fixer 已注册" in out and "✅ agent visual-fixer-reviewer 已注册" in out, out
    assert "❌ agent" not in out, out
    assert "hmos_fix_build_errors 已安装" in out or "hmos-fix-build-errors 已安装" in out, out   # 连字符目录名也认
    assert rc != 2 or "UNIT 级缺失" not in out, out


def test_probe_claude_shaped_project_still_registers_md_agents(tmp_path):
    proj, home = tmp_path / "proj", tmp_path / "home"
    root = _skills_root(tmp_path, "claude")
    for a in ("visual-fixer", "visual-fixer-reviewer"):
        (home / ".claude" / "agents").mkdir(parents=True, exist_ok=True); (home / ".claude" / "agents" / f"{a}.md").write_text("# a\n")
    rc, out = _run_probe(proj, home, skills_root=root)
    assert "✅ agent visual-fixer 已注册" in out and "✅ agent visual-fixer-reviewer 已注册" in out, out


def test_probe_lists_extra_dirs_only_when_auto_discovered(tmp_path):
    """显式 --skills-root 且都缺：不打「另查过」（与既往一字不差）；自动发现（ARKTS_SKILL_DIR）时列出多查的插件目录。"""
    proj, home = tmp_path / "proj", tmp_path / "home"; proj.mkdir(); home.mkdir()
    root = _skills_root(tmp_path, "x")
    rc, out = _run_probe(proj, home, skills_root=root)
    assert "❌ agent visual-fixer 未注册" in out and "另查过" not in out, out
    rc, out = _run_probe(proj, home, env={"ARKTS_SKILL_DIR": str(root / "arkts-visual-verify" / "scripts")})
    assert "另查过：" in out and str(root.parent / "agents") in out, out


# ───────── ④ 静态闸：业务脚本不得自己拼平台目录 / agent 后缀 ─────────
PLAT = {".claude", ".codex", ".agents"}


def _platform_violations(src):
    tree = ast.parse(src); lines = src.splitlines(); out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and ast.unparse(n.func).endswith(("join", "Path")):
            if any(isinstance(a, ast.Constant) and a.value in PLAT for a in n.args) and "env-literal-ok" not in lines[n.lineno - 1]:
                out.append(f"{n.lineno}: {ast.unparse(n)[:80]}")
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) and isinstance(n.right, ast.Constant) and n.right.value in PLAT \
                and "env-literal-ok" not in lines[n.lineno - 1]:
            out.append(f"{n.lineno}: {ast.unparse(n)[:80]}")
        if isinstance(n, ast.JoinedStr) and any(isinstance(v, ast.Constant) and str(v.value).endswith((".md", ".toml")) for v in n.values) \
                and any(isinstance(v, ast.FormattedValue) and "agent" in ast.unparse(v.value) for v in n.values):
            out.append(f"{n.lineno}: {ast.unparse(n)[:80]}  ← 用 sibling_exec.agent_registered")
    return out


def test_no_platform_path_literals_outside_env_module():
    bad = {}
    for fn in sorted(os.listdir(SCRIPTS)):
        if not fn.endswith(".py") or fn == "sibling_exec.py": continue
        v = _platform_violations(open(os.path.join(SCRIPTS, fn), encoding="utf-8").read())
        if v: bad[fn] = v
    assert not bad, "平台目录/agent 后缀写死在业务脚本里（应改调 sibling_exec 的定位函数，或逐行注 env-literal-ok）：\n" + \
        "\n".join(f"  {k}:{x}" for k, vs in bad.items() for x in vs)


def test_platform_lint_selfcheck():
    hit = lambda s: len(_platform_violations(s))
    assert hit('p = os.path.join(home, ".claude", "agents")\n') == 1
    assert hit('p = Path(home) / ".codex" / "agents"\n') == 1
    assert hit('p = os.path.join(home, ".claude", "agents")   # env-literal-ok\n') == 0
    assert hit('ok = os.path.isfile(os.path.join(d, f"{agent}.md"))\n') == 1
    assert hit('EXCLUDE = (".agents", ".codex", ".claude")\n') == 0       # 排除清单不是路径拼接
    assert hit('p = os.path.join(home, "skills", name)\n') == 0


# ───────── ⑤ vv 依赖 skill：sibling_exec 副本零漂移 + 同一套打包/平台契约 ─────────
DEP_SKILLS = ("android-fact-tree", "arkts-scenario-runner", "app-relationship-tree", "a2h-functional-merge",
              "compose-fact-tree", "toolkit-fact-indexer", "a2h-spec", "a2h-functional-registry")
SKILLS_ROOT_DIR = Path(SCRIPTS).resolve().parent.parent


def test_sibling_exec_copies_identical():
    """sibling_exec 按 skill 复制（打包按 skill 独立成二进制，没有共享库）——所有副本必须与 vv 这份逐字节相同，改一份忘同步就红。"""
    mine = (Path(SCRIPTS) / "sibling_exec.py").read_bytes()
    copies = sorted(p for p in SKILLS_ROOT_DIR.glob("*/scripts/sibling_exec.py") if p.parent.parent.name != "arkts-visual-verify")
    assert copies, "没找到任何 sibling_exec 副本（布局不对？）"
    drift = [str(p.relative_to(SKILLS_ROOT_DIR)) for p in copies if p.read_bytes() != mine]
    assert not drift, f"sibling_exec 副本漂移（以 arkts-visual-verify/scripts/sibling_exec.py 为准整份覆盖）: {drift}"


@pytest.mark.parametrize("skill", DEP_SKILLS)
def test_dependency_skill_contracts(skill):
    """vv 会调到的 skill 也得过同一套闸：不许 [sys.executable,…] spawn、不许 isfile 守 .py、不许拼平台目录/agent 后缀、无模块级脚本。"""
    from test_sibling_available_0915 import _contract_violations
    d = SKILLS_ROOT_DIR / skill / "scripts"
    if not d.is_dir():
        pytest.skip(f"{skill} 无 scripts/ 或布局不同")
    bad = {}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".py") or fn == "sibling_exec.py": continue
        src = (d / fn).read_text(encoding="utf-8")
        v = _contract_violations(src) + _platform_violations(src)
        if v: bad[fn] = v
    assert not bad, f"{skill} 违反打包/平台契约：\n" + "\n".join(f"  {k}:{x}" for k, vs in bad.items() for x in vs)
    cfg = next((up / "build" / "script-compression" / "scripts" / "config.py" for up in SKILLS_ROOT_DIR.parents
                if (up / "build" / "script-compression" / "scripts" / "config.py").is_file()), None)
    if cfg:
        sys.path.insert(0, str(cfg.parent)); import importlib; config = importlib.import_module("config")
        cls = config.classify_scripts_dir(str(d))
        assert not {k: v for k, v in cls.items() if v in ("implicit", "broken")}, cls
        # packaging-contract-ok 只许出现在打包器按源码发运（EXCLUDE_STEMS）的脚本里——豁免从自觉变机械
        marked = [fn[:-3] for fn in os.listdir(d) if fn.endswith(".py") and "packaging-contract-ok" in (d / fn).read_text(encoding="utf-8")]
        allowed = set(getattr(config, "EXCLUDE_STEMS", {}).get(skill, ()))
        assert set(marked) <= allowed, f"{skill}: 带 packaging-contract-ok 但不在 config.EXCLUDE_STEMS 里: {sorted(set(marked) - allowed)}"
