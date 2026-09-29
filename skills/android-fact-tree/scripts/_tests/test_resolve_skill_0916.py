#!/usr/bin/env python3
"""android-fact-tree dispatch.py 的环境中立回归（2026-09-16 codex 实跑 C1 同族）。
`_resolve_skill` 原只认 Claude 线目录（~/.claude/skills、CLAUDE_PROJECT_DIR/.claude/skills），codex 线（.agents/skills）永远找不到 vv；
本文件按打包器 EXCLUDE_STEMS 以源码发运、不能 import 会被删源的 lib，故内联两种布局。本测试锁：
  ① 6 种布局 × 命中；② 候选顺序与 vv sibling_exec.skills_root_candidates 一致；③ `env-literal-ok` 标记真承重；④ `_vv_cmd` 借不到 sibling_exec 时回落系统解释器。"""
import importlib.util, os, sys
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
SKILLS_ROOT = SCRIPTS.parent.parent


def _load_dispatch(monkeypatch, here: Path, home: Path, proj: Path):
    monkeypatch.setenv("HOME", str(home)); monkeypatch.setenv("USERPROFILE", str(home)); monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(proj))
    here.mkdir(parents=True, exist_ok=True)
    (here / "dispatch.py").write_bytes((SCRIPTS / "dispatch.py").read_bytes())
    spec = importlib.util.spec_from_file_location("dispatch_under_test", here / "dispatch.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


REL = "arkts-visual-verify/scripts/check_prereq_freshness.py"
LAYOUTS = {
    "sibling_root": lambda t: t / "inst" / "skills" / REL,
    "home_claude":  lambda t: t / "home" / ".claude" / "skills" / REL,
    "home_agents":  lambda t: t / "home" / ".agents" / "skills" / REL,
    "proj_claude":  lambda t: t / "proj" / ".claude" / "skills" / REL,
    "proj_agents":  lambda t: t / "proj" / ".agents" / "skills" / REL,
    "proj_skills":  lambda t: t / "proj" / "skills" / REL,
}


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_resolve_skill_finds_every_layout(monkeypatch, tmp_path, layout):
    here = tmp_path / "inst" / "skills" / "android-fact-tree" / "scripts"
    m = _load_dispatch(monkeypatch, here, tmp_path / "home", tmp_path / "proj")
    tgt = LAYOUTS[layout](tmp_path); tgt.parent.mkdir(parents=True); tgt.write_text("pass\n")
    assert Path(m._resolve_skill(REL)).resolve() == tgt.resolve()


def test_resolve_skill_candidate_order_matches_sibling_exec(monkeypatch, tmp_path):
    """内联候选顺序必须与 vv sibling_exec.skills_root_candidates(home, proj) 一致（两处各写一套会漂）。"""
    se_path = SKILLS_ROOT / "arkts-visual-verify" / "scripts" / "sibling_exec.py"
    if not se_path.is_file():
        pytest.skip("非源码仓布局，找不到 vv 的 sibling_exec")
    here = tmp_path / "inst" / "skills" / "android-fact-tree" / "scripts"
    m = _load_dispatch(monkeypatch, here, tmp_path / "home", tmp_path / "proj")
    got = Path(m._resolve_skill(REL))                     # 全缺 → 回落 cands[0]
    assert got == (tmp_path / "inst" / "skills" / REL)
    spec = importlib.util.spec_from_file_location("se_ref", se_path); se = importlib.util.module_from_spec(spec); spec.loader.exec_module(se)
    monkeypatch.setattr(se, "_HERE", here.resolve())
    expected = [os.path.join(r, REL) for r in se.skills_root_candidates(tmp_path / "home", tmp_path / "proj")]
    src = (SCRIPTS / "dispatch.py").read_text(encoding="utf-8")
    # 从源码里机械抽出 cands 的拼法顺序（不执行）：同级根 / ~/.claude / ~/.agents / proj/.claude / proj/.agents / proj/skills
    order = ["skills_root"] + [f"{b}:{l}" for b in ("home", "proj") for l in (".claude", ".agents")] + ["proj:skills"]
    assert expected == [os.path.join(tmp_path / "inst" / "skills", REL)] + [os.path.join(tmp_path / "home", ".claude", "skills", REL), os.path.join(tmp_path / "home", ".agents", "skills", REL),
                                                                          os.path.join(tmp_path / "proj", ".claude", "skills", REL), os.path.join(tmp_path / "proj", ".agents", "skills", REL), os.path.join(tmp_path / "proj", "skills", REL)]
    assert src.index('".claude", "skills", rel') < src.index('".agents", "skills", rel') < src.index('os.path.join(proj, "skills", rel)'), order


def test_env_literal_markers_are_load_bearing():
    """删掉 env-literal-ok 标记后，vv 的平台闸必须抓到这两处（标记不是装饰）。"""
    lint = SKILLS_ROOT / "arkts-visual-verify" / "scripts" / "_tests" / "test_env_neutral_0916.py"
    if not lint.is_file():
        pytest.skip("找不到 vv 的平台闸")
    spec = importlib.util.spec_from_file_location("vv_env_lint", lint); L = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(lint.parent)); sys.path.insert(0, str(lint.parent.parent)); spec.loader.exec_module(L)
    src = (SCRIPTS / "dispatch.py").read_text(encoding="utf-8")
    assert L._platform_violations(src) == []
    assert len(L._platform_violations(src.replace("# env-literal-ok", "#"))) == 2


def test_vv_cmd_falls_back_to_interpreter_when_no_sibling_exec(monkeypatch, tmp_path):
    """发行包里 vv 的 lib 源已被打包器删掉 → 借不到 sibling_exec → 回落系统解释器跑 launcher（不能是 libpython 式崩溃）。"""
    here = tmp_path / "inst" / "skills" / "android-fact-tree" / "scripts"
    vv = tmp_path / "inst" / "skills" / "arkts-visual-verify" / "scripts"; vv.mkdir(parents=True)
    (vv / "check_prereq_freshness.py").write_text("print('PASS')\n")
    m = _load_dispatch(monkeypatch, here, tmp_path / "home", tmp_path / "proj")
    cmd = m._vv_cmd(str(vv / "check_prereq_freshness.py"), ["x"])
    assert cmd[1:] == [str(vv / "check_prereq_freshness.py"), "x"] and os.path.basename(cmd[0]).startswith("python")
