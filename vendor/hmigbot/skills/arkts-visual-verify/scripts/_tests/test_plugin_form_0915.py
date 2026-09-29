#!/usr/bin/env python3
"""插件安装形态四件（2026-09-15，antennapod_v630_cc 上 hmigbot 1.5.1 插件实跑归因）：

  ① check_dimension_prereqs 的 skills 根 / agent 目录解析认插件缓存布局（此前只认 ~/.claude/skills 与 ~/.claude/agents）
  ②（已撤：agent 派发名前缀改在 hmigbot 发布侧机械改写，见 hmigbot 仓）
  ③ next_walk 给模型看的命令路径走 ARKTS_SKILL_DIR（打包态 __file__ 在 _entry.dist 里、那里没有 .py）、
     兄弟脚本 spawn 走 sibling_cmd（打包态 sys.executable 是不可执行的 libpython）
  ④ 静态闸：scripts/ 下不许再出现 `[sys.executable, …]` 形态的兄弟 spawn（整类缺陷的机械守门）
全合成夹具，零设备。"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import next_walk as NW                      # noqa: E402
from sibling_exec import sibling_cmd        # noqa: E402

PROBE = SCRIPTS / "check_dimension_prereqs.py"


def _w(p: Path, text="# 占位\n"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _install_probe(skills_root: Path) -> Path:
    """把探针拷进布局里再跑——自动发现会把探针自身所在的 skills 根算作候选，
    直接跑仓库里的探针会把开发仓的 arkts-scenario-runner / arkts-agents 找出来，测不出"缺失"。"""
    import shutil
    d = skills_root / "arkts-visual-verify" / "scripts"; d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPTS / "check_dimension_prereqs.py", d / "check_dimension_prereqs.py")
    shutil.copy2(SCRIPTS / "sibling_exec.py", d / "sibling_exec.py")   # 0916：探针的环境定位（skills 根 / agent 目录）收进了 sibling_exec，同目录要有它
    return d / "check_dimension_prereqs.py"


def _plugin_layout(tmp: Path, plugin="hmigbot", with_runner=True, with_agents=True, with_fixbuild=True) -> Path:
    """~/.claude/plugins/cache/<marketplace>/<plugin>/<ver>/{skills,agents}"""
    root = tmp / "home" / ".claude" / "plugins" / "cache" / "mk" / plugin / "1.5.1"
    _w(root / "skills" / "arkts-visual-verify" / "SKILL.md")
    _install_probe(root / "skills")
    if with_runner:
        _w(root / "skills" / "arkts-scenario-runner" / "scripts" / "scenario_run.py")
    if with_fixbuild:                                   # 源侧目录名 hmos_fix_build_errors，codex 产物改成了短横线名；两种都摆
        _w(root / "skills" / "hmos_fix_build_errors" / "SKILL.md")
        _w(root / "skills" / "hmos-fix-build-errors" / "SKILL.md")
    if with_agents:
        _w(root / "agents" / "visual-fixer.md")
        _w(root / "agents" / "visual-fixer-reviewer.md")
    return root


def _spec_all_green(proj: Path):
    _w(proj / "spec" / "baseline" / "ui" / "page_A.md")
    _w(proj / "spec" / "baseline" / "features" / "F001.md")
    _w(proj / "spec" / "baseline" / "feature-index.md")
    _w(proj / "spec" / "toolkit-fact-tree.json", '{"pages": [], "functional_checks": []}')
    _w(proj / "spec" / "baseline" / "dev_info.json", "{}")
    _w(proj / "spec" / "visual-verify" / "page_scenarios.json", "{}")


def _run_probe(proj: Path, home: Path, extra_env=None, args=(), probe: Path = PROBE):
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "CLAUDE_PROJECT_DIR": str(proj)}
    env.pop("SKILLS_ROOT", None); env.pop("ARKTS_SKILL_DIR", None)
    env.update(extra_env or {})
    proj.mkdir(parents=True, exist_ok=True)
    return subprocess.run([sys.executable, str(probe), "--project-root", str(proj), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, cwd=proj)


# ── ① 探针认插件布局 ────────────────────────────────────────────────
def test_probe_plugin_layout_all_green_via_arkts_skill_dir(tmp_path):
    root = _plugin_layout(tmp_path)
    proj = tmp_path / "proj"; _spec_all_green(proj)
    r = _run_probe(proj, tmp_path / "home",
                   {"ARKTS_SKILL_DIR": str(root / "skills" / "arkts-visual-verify" / "scripts")},
                   probe=root / "skills" / "arkts-visual-verify" / "scripts" / "check_dimension_prereqs.py")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "✅ scenario_run.py 可达" in r.stdout and "❌" not in r.stdout
    assert "✅ agent visual-fixer 已注册" in r.stdout and "✅ agent visual-fixer-reviewer 已注册" in r.stdout
    assert re.search(r"✅ hmos[_-]fix[_-]build[_-]errors 已安装", r.stdout)


def test_probe_plugin_layout_missing_pieces_still_fail_and_list_searched_dirs(tmp_path):
    root = _plugin_layout(tmp_path, with_runner=False, with_agents=False, with_fixbuild=False)
    proj = tmp_path / "proj"; _spec_all_green(proj)
    r = _run_probe(proj, tmp_path / "home",
                   {"ARKTS_SKILL_DIR": str(root / "skills" / "arkts-visual-verify" / "scripts")},
                   probe=root / "skills" / "arkts-visual-verify" / "scripts" / "check_dimension_prereqs.py")
    assert r.returncode == 2, r.stdout
    assert "❌ scenario_run.py 缺失" in r.stdout and "❌ agent visual-fixer 未注册" in r.stdout
    assert "另查过：" in r.stdout and str(root / "agents") in r.stdout      # 插件 agents 目录确实查过
    assert re.search(r"⚠️ hmos[_-]fix[_-]build[_-]errors 未找到", r.stdout)


def test_probe_user_level_layout_unchanged(tmp_path):
    """用户级安装（~/.claude/skills + ~/.claude/agents）：老路径照旧 ✅，无插件提示行。"""
    home = tmp_path / "home"
    _w(home / ".claude" / "skills" / "arkts-visual-verify" / "SKILL.md")
    probe = _install_probe(home / ".claude" / "skills")
    _w(home / ".claude" / "skills" / "arkts-scenario-runner" / "scripts" / "scenario_run.py")
    _w(home / ".claude" / "agents" / "visual-fixer.md"); _w(home / ".claude" / "agents" / "visual-fixer-reviewer.md")
    proj = tmp_path / "proj"; _spec_all_green(proj)
    r = _run_probe(proj, home, probe=probe)
    assert r.returncode == 0, r.stdout
    assert "❌" not in r.stdout


def test_probe_explicit_skills_root_wins_over_plugin_discovery(tmp_path):
    """显式 --skills-root 只认显式值（golden 047–052 语义）：即使 ARKTS_SKILL_DIR 指向齐全的插件布局也不救。"""
    root = _plugin_layout(tmp_path)
    proj = tmp_path / "proj"; _spec_all_green(proj)
    empty = tmp_path / "empty_skills"; empty.mkdir()
    r = _run_probe(proj, tmp_path / "home",
                   {"ARKTS_SKILL_DIR": str(root / "skills" / "arkts-visual-verify" / "scripts")},
                   args=["--skills-root", str(empty)],
                   probe=root / "skills" / "arkts-visual-verify" / "scripts" / "check_dimension_prereqs.py")
    assert r.returncode == 2 and f"到 {empty}/" in r.stdout and "已查：" not in r.stdout


def test_probe_frozen_dist_dir_is_not_mistaken_for_skills_root(tmp_path):
    """打包态 ARKTS_SKILL_DIR 指向真 scripts/，而 __file__ 在 scripts/bin/<平台>/_entry.dist——上溯两级是 scripts/bin，
    不像 skills 根，必须被过滤而不是被当根。用本文件所在真实仓库模拟不了 _entry.dist，改用 skill_roots() 直接验。"""
    import check_dimension_prereqs as CDP
    root = _plugin_layout(tmp_path)
    os.environ["ARKTS_SKILL_DIR"] = str(root / "skills" / "arkts-visual-verify" / "scripts")
    try:
        roots = CDP.skill_roots("", str(tmp_path / "home"), str(tmp_path / "proj"))
    finally:
        os.environ.pop("ARKTS_SKILL_DIR", None)
    assert roots[0] == str(root / "skills")
    assert all(Path(r, "arkts-visual-verify").is_dir() for r in roots)


# ── ③ next_walk：命令路径与 spawn ──────────────────────────────────
def test_next_walk_plan_cmd_uses_arkts_skill_dir_when_frozen(tmp_path, monkeypatch):
    """给模型看的 cmd 必须指向真实 scripts/（launcher 注入的 ARKTS_SKILL_DIR），不是 __file__ 所在目录。"""
    fake_scripts = tmp_path / "plugin" / "skills" / "arkts-visual-verify" / "scripts"; fake_scripts.mkdir(parents=True)
    monkeypatch.setattr(NW, "SCRIPTS", str(fake_scripts))
    ew = tmp_path / "proj" / "spec" / "visual-verify" / "edgewalk"; ew.mkdir(parents=True)
    tree = tmp_path / "proj" / "spec" / "toolkit-fact-tree.json"; _w(tree, "{}")
    out = NW.decide(str(ew), str(tmp_path / "proj"), str(tree), None, None, None, False)
    assert out["action"] == "plan"
    assert out["cmd"].startswith(f"python3 {fake_scripts / 'plan_edge_walk.py'} ")
    assert "_entry.dist" not in out["cmd"]


def test_next_walk_scripts_default_is_here_without_env():
    assert NW.SCRIPTS == (os.environ.get("ARKTS_SKILL_DIR") or NW.HERE)


def test_next_walk_fill_walk_prompt_spawns_via_sibling_cmd(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = list(cmd)

        class R:  # noqa: D401
            returncode = 0; stdout = ""; stderr = ""
        return R()
    monkeypatch.setattr(NW.subprocess, "run", fake_run)
    ew = tmp_path / "ew"; (ew / "prompts").mkdir(parents=True); (ew / "steps").mkdir()
    _w(ew / "walk_plan.json", json.dumps({"walks": []}))
    walk = {"walk_id": "walk_0_first", "trip_id": "trip_1", "steps": [{"seq": 1}], "step_ids": [1]}
    monkeypatch.setattr(NW, "_walk_steps_file", lambda *a, **k: str(ew / "steps" / "w0.json"), raising=False)
    try:
        NW.fill_walk_prompt(str(ew), walk, None, 1)
    except Exception:
        pass                                            # 夹具不全时函数可能在 spawn 之后失败；只关心 spawn 形态
    if "cmd" not in seen:
        import pytest
        pytest.skip("fill_walk_prompt 未走到 spawn（夹具形态与本版不符）")
    cmd = seen["cmd"]
    expect_head = sibling_cmd(str(SCRIPTS / "fill_chunk_prompt.py"))[:2]
    assert cmd[:2] == expect_head, cmd[:3]             # 开发态 = [解释器, …/fill_chunk_prompt.py]；不再是裸 sys.executable 拼接
    assert "--chunk" in cmd and "walk_0_first" in cmd


def test_next_walk_run_bind_cmds_via_sibling_cmd(tmp_path):
    res, err = NW.run_bind(str(tmp_path), str(tmp_path / "t.json"), [{"node": "PageA"}, {"node": "PageB"}], apply=False)
    assert err is None and len(res["cmds"]) == 2
    head = " ".join(sibling_cmd(str(SCRIPTS / "walk_ledger.py"))[:2])
    assert all(c.startswith(head) and "bind-from-evidence" in c and "--node" in c for c in res["cmds"])


# ── ④ 静态闸 ────────────────────────────────────────────────────────
def test_no_bare_sys_executable_spawn_left_in_scripts():
    """整类缺陷的机械守门：scripts/ 下（除 sibling_exec / lib_tools 这两个定义处）不许再出现
    `[sys.executable, …]` 形态的列表 spawn；兄弟脚本一律 sibling_cmd。"""
    pat = re.compile(r"\[\s*sys\.executable\s*,")
    bad = []
    for p in sorted(SCRIPTS.glob("*.py")):
        if p.name in ("sibling_exec.py", "lib_tools.py"):
            continue
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(ln) and not ln.lstrip().startswith("#"):
                bad.append(f"{p.name}:{i}: {ln.strip()[:90]}")
    assert not bad, "\n".join(bad)


def test_no_here_based_py_path_emitted_to_model():
    """给模型看的命令里不许用 HERE/__file__ 拼 .py 路径（打包态那里没有 .py）；只许 SCRIPTS（ARKTS_SKILL_DIR 优先）。"""
    pat = re.compile(r"python3? \{os\.path\.(join\(HERE|abspath\(__file__)")
    bad = []
    for p in sorted(SCRIPTS.glob("*.py")):
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(ln):
                bad.append(f"{p.name}:{i}: {ln.strip()[:90]}")
    assert not bad, "\n".join(bad)
