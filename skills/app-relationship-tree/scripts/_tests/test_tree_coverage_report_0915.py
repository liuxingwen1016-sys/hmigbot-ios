#!/usr/bin/env python3
"""tree_coverage_report 2026-09-15：① 非 walkable 节点剔出 E1/E3 分母 ② E3 默认 92% ③ 放宽阈值须用户批准（hints 文件），
否则 --gate REFUSED exit 3 ④ 阈值/放宽/批准人写进 --json。全合成树。"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import tree_coverage_report as TCR   # noqa: E402


def _page(pid, from_pages=(), kind="screen", walk=None, extra=None):
    r = {"id": pid, "navigation_contract": {"relationship_kind": kind},
         "inbound_triggers": [{"from_page": f, "trigger_label": "go", "trigger_view_id": f"btn_{f}"} for f in from_pages]}
    if walk:
        r["walkability"] = {"status": walk}
    r.update(extra or {})
    return r


def _tree():
    pages = [_page("Home"), _page("A", ["Home"]), _page("B", ["Home"]), _page("C", ["A"]), _page("Orphan"),
             _page("AbstractBase", walk="abstract"), _page("ExtOnly", walk="external_entry"), _page("Dead", walk="dead")]
    frags = [_page("Tab1", ["Home"], kind="tab", extra={"parent_in_nav": "Home"}),
             _page("Tab2", ["Home"], kind="tab", extra={"parent_in_nav": "Home"}),
             _page("TabNoHost", [], kind="tab", extra={"parent_in_nav": "Home"}),
             _page("DeadTab", [], kind="tab", walk="dead", extra={"parent_in_nav": "Home"})]
    return {"app": {"launcher_short": "Splash"}, "pages": pages + [_page("Splash")], "fragments": frags, "dialogs": []}


def test_nonwalkable_excluded_from_e1_e3_denominators():
    rp = TCR.report(_tree())
    # E1 分母：Home A B C Orphan Tab1 Tab2 TabNoHost = 8（Splash 是 launcher；Abstract/Ext/Dead/DeadTab 剔除）
    assert rp["E1"]["d"] == 8 and rp["E1"]["n"] == 5            # A B C Tab1 Tab2 有活入边（Home 无入边、Orphan 无、TabNoHost 无）
    assert set(rp["nonwalkable_excluded"]) == {"AbstractBase", "ExtOnly", "Dead", "DeadTab"}
    assert rp["E3"]["d"] == 3 and rp["E3"]["n"] == 2             # DeadTab 不进分母；TabNoHost 缺宿主边


def _run(tree_dir: Path, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / "tree_coverage_report.py"), str(tree_dir / "t.json"), *args],
                          capture_output=True, text=True, encoding="utf-8", cwd=tree_dir)


def test_default_e3_is_92_percent_and_json_records_thresholds(tmp_path):
    (tmp_path / "t.json").write_text(json.dumps(_tree()), encoding="utf-8")
    r = _run(tmp_path, "--json", "cov.json")
    assert r.returncode == 0
    cov = json.loads((tmp_path / "cov.json").read_text(encoding="utf-8"))
    assert cov["thresholds"]["min_e3"] == 0.92 and cov["defaults"]["min_e3"] == 0.92
    assert cov["relaxed"] == [] and cov["approved_by"] is None and cov["gate"] in ("PASS", "FAIL")


def test_relaxed_without_user_approval_is_refused(tmp_path):
    (tmp_path / "t.json").write_text(json.dumps(_tree()), encoding="utf-8")
    r = _run(tmp_path, "--gate", "--min-e1", "0.5", "--json", "cov.json")
    assert r.returncode == 3, r.stdout
    assert "GATE: REFUSED" in r.stdout and "无用户批准" in r.stdout
    cov = json.loads((tmp_path / "cov.json").read_text(encoding="utf-8"))
    assert cov["gate"] == "REFUSED" and cov["relaxed"] == ["min_e1"]


def test_relaxed_with_user_approval_passes_and_is_audited(tmp_path):
    (tmp_path / "t.json").write_text(json.dumps(_tree()), encoding="utf-8")
    (tmp_path / "tree_hints.json").write_text(json.dumps(
        {"coverage_gate_approved": {"by": "user", "min_e1": 0.5, "min_e3": 0.6, "reason": "菜单型工程"}}), encoding="utf-8")
    r = _run(tmp_path, "--gate", "--min-e1", "0.5", "--min-e3", "0.6", "--json", "cov.json")
    assert r.returncode == 0, r.stdout
    assert "用户批准 ✓" in r.stdout and "GATE: PASS（阈值经用户批准放宽）" in r.stdout
    cov = json.loads((tmp_path / "cov.json").read_text(encoding="utf-8"))
    assert cov["approved_by"] == "user" and sorted(cov["relaxed"]) == ["min_e1", "min_e3"]


def test_cli_looser_than_approved_or_wrong_approver_is_refused(tmp_path):
    (tmp_path / "t.json").write_text(json.dumps(_tree()), encoding="utf-8")
    (tmp_path / "tree_hints.json").write_text(json.dumps(
        {"coverage_gate_approved": {"by": "user", "min_e1": 0.8}}), encoding="utf-8")
    assert _run(tmp_path, "--gate", "--min-e1", "0.5").returncode == 3          # 比批准的更松
    (tmp_path / "tree_hints.json").write_text(json.dumps(
        {"coverage_gate_approved": {"by": "main session", "min_e1": 0.5}}), encoding="utf-8")
    assert _run(tmp_path, "--gate", "--min-e1", "0.5").returncode == 3          # 不是用户批的
    r = _run(tmp_path, "--min-e1", "0.5")                                        # 不带 --gate 只警告
    assert r.returncode == 0 and "无用户批准" in r.stdout


def test_hints_path_override(tmp_path):
    (tmp_path / "t.json").write_text(json.dumps(_tree()), encoding="utf-8")
    h = tmp_path / "elsewhere.json"
    h.write_text(json.dumps({"coverage_gate_approved": {"by": "user", "min_e1": 0.5, "min_e3": 0.6}}), encoding="utf-8")
    r = _run(tmp_path, "--gate", "--min-e1", "0.5", "--min-e3", "0.6", "--hints", str(h))
    assert r.returncode == 0, r.stdout
