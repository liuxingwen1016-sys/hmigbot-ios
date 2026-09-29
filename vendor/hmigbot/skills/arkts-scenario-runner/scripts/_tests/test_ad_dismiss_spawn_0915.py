#!/usr/bin/env python3
"""ad_dismiss 动作的跨 skill 调用（2026-09-15 插件形态归因）：
  · ad_dismiss.py 的路径走 SKILL_DIR.parent（ARKTS_SKILL_DIR 优先），不再按 __file__ 上溯——打包态 __file__ 在 _entry.dist 里
  · spawn 走 sibling_cmd，不再 [sys.executable, …]（打包态 sys.executable 是不可执行的 libpython）
  · 静态闸：本 skill scripts/ 下不许再出现 [sys.executable, …] 列表 spawn
全合成，零设备：用假 self 直接调 Runner.a_ad_dismiss。"""
import json
import os
import re
import sys
import types
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))


def _load_runner(monkeypatch, skill_dir_env: str | None):
    """按给定 ARKTS_SKILL_DIR 重新导入 scenario_run（SKILL_DIR 在 import 时定值）。"""
    if skill_dir_env is None:
        monkeypatch.delenv("ARKTS_SKILL_DIR", raising=False)
    else:
        monkeypatch.setenv("ARKTS_SKILL_DIR", skill_dir_env)
    sys.modules.pop("scenario_run", None)
    import scenario_run as SR
    return SR


def _layout(tmp: Path) -> Path:
    """<skills>/arkts-scenario-runner/scripts 与 <skills>/arkts-visual-verify/scripts/ad_dismiss.py"""
    skills = tmp / "plugins" / "cache" / "mk" / "hmigbot" / "1.0" / "skills"
    (skills / "arkts-scenario-runner" / "scripts").mkdir(parents=True)
    # 真实布局里 scripts/ 下有本脚本（源码或 launcher）；SKILL_DIR 只认"目录里有我自己"的 ARKTS_SKILL_DIR
    (skills / "arkts-scenario-runner" / "scripts" / "scenario_run.py").write_text("# launcher 占位\n", encoding="utf-8")
    (skills / "arkts-visual-verify" / "scripts").mkdir(parents=True)
    (skills / "arkts-visual-verify" / "scripts" / "ad_dismiss.py").write_text("# launcher 占位\n", encoding="utf-8")
    return skills


def _fake_self(log):
    d = types.SimpleNamespace(name="android", device_id="emulator-5556", tap=lambda *a: None, dump_ui=lambda: "<hierarchy/>")
    return types.SimpleNamespace(d=d, log=log.append, resolve=lambda p: p, _find_selector=lambda sel: None)


def test_ad_dismiss_path_and_spawn_follow_skill_dir(tmp_path, monkeypatch):
    skills = _layout(tmp_path)
    SR = _load_runner(monkeypatch, str(skills / "arkts-scenario-runner" / "scripts"))
    assert SR.SKILL_DIR == (skills / "arkts-scenario-runner").resolve()
    profile = tmp_path / "ad_profile.json"; profile.write_text(json.dumps({"home_signature": []}), encoding="utf-8")
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = list(cmd)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(SR.subprocess, "run", fake_run)
    log = []
    ok = SR.Runner.a_ad_dismiss(_fake_self(log), {"profile": str(profile)})
    assert ok is True, log
    cmd = seen["cmd"]
    expected_script = str(skills / "arkts-visual-verify" / "scripts" / "ad_dismiss.py")
    assert expected_script in cmd, cmd                       # 路径来自 SKILL_DIR.parent，不是 __file__ 上溯
    from sibling_exec import sibling_cmd
    assert cmd[:2] == sibling_cmd(expected_script)[:2], cmd  # 经 sibling_cmd 构造（开发态 = [解释器, 脚本]）
    assert cmd[-4:] == ["--serial", "emulator-5556", "--profile", str(profile)]


def test_ad_dismiss_reports_missing_dependency_instead_of_crashing(tmp_path, monkeypatch):
    skills = _layout(tmp_path)
    (skills / "arkts-visual-verify" / "scripts" / "ad_dismiss.py").unlink()
    SR = _load_runner(monkeypatch, str(skills / "arkts-scenario-runner" / "scripts"))
    profile = tmp_path / "ad_profile.json"; profile.write_text("{}", encoding="utf-8")
    log = []
    assert SR.Runner.a_ad_dismiss(_fake_self(log), {"profile": str(profile)}) is False
    assert any("ad_dismiss 依赖缺失" in ln for ln in log)


def test_no_bare_sys_executable_spawn_left():
    pat = re.compile(r"\[\s*sys\.executable\s*,")
    bad = []
    for p in sorted(SCRIPTS.glob("*.py")):
        if p.name == "sibling_exec.py":
            continue
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(ln) and not ln.lstrip().startswith("#"):
                bad.append(f"{p.name}:{i}: {ln.strip()[:90]}")
    assert not bad, "\n".join(bad)


# ── SKILL_DIR 自我定位：ARKTS_SKILL_DIR 是父进程可继承的，指向别的 skill 时不能认 ──────────
def _import_copy(dst_dir: Path):
    """把 scenario_run.py + sibling_exec.py 拷到指定目录后按路径导入（__file__ 落在那里）。"""
    import importlib.util, shutil
    dst_dir.mkdir(parents=True, exist_ok=True)
    for n in ("scenario_run.py", "sibling_exec.py"):
        shutil.copy2(SCRIPTS / n, dst_dir / n)
    spec = importlib.util.spec_from_file_location("scenario_run_copy", dst_dir / "scenario_run.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_skill_dir_rejects_foreign_env_and_accepts_own(tmp_path, monkeypatch):
    skills = tmp_path / "skills"
    own = skills / "arkts-scenario-runner" / "scripts"
    foreign = skills / "arkts-visual-verify" / "scripts"; foreign.mkdir(parents=True)
    (foreign / "next_walk.py").write_text("# vv\n", encoding="utf-8")
    monkeypatch.setenv("ARKTS_SKILL_DIR", str(foreign))            # 继承自 vv 的值
    m = _import_copy(own)
    assert m.SKILL_DIR == (skills / "arkts-scenario-runner").resolve()   # 没被带偏
    monkeypatch.setenv("ARKTS_SKILL_DIR", str(own))                # 自己的 launcher 设的值
    m = _import_copy(own)
    assert m.SKILL_DIR == (skills / "arkts-scenario-runner").resolve()


def test_skill_dir_frozen_layout_falls_back_to_entry_dist_ancestor(tmp_path, monkeypatch):
    """冻结态：__file__ 在 scripts/bin/<平台>/_entry.dist/，环境变量又被 vv 污染 → 按 _entry.dist 上溯到 scripts/。"""
    skills = tmp_path / "skills"
    scripts = skills / "arkts-scenario-runner" / "scripts"
    dist = scripts / "bin" / "macos-arm64" / "_entry.dist"
    foreign = skills / "arkts-visual-verify" / "scripts"; foreign.mkdir(parents=True)
    monkeypatch.setenv("ARKTS_SKILL_DIR", str(foreign))
    m = _import_copy(dist)
    assert m.SKILL_DIR == (skills / "arkts-scenario-runner").resolve()
    monkeypatch.delenv("ARKTS_SKILL_DIR")
    m = _import_copy(dist)
    assert m.SKILL_DIR == (skills / "arkts-scenario-runner").resolve()


def test_skill_dir_pre_assembly_artifacts_layout(tmp_path, monkeypatch):
    """打包校验跑在装配前的 _artifacts 布局：scripts/_entry.dist（没有 bin/<平台>/ 两级）——同样要上溯到 scripts/。"""
    skills = tmp_path / "skills"
    dist = skills / "arkts-scenario-runner" / "scripts" / "_entry.dist"
    monkeypatch.delenv("ARKTS_SKILL_DIR", raising=False)
    m = _import_copy(dist)
    assert m.SKILL_DIR == (skills / "arkts-scenario-runner").resolve()

