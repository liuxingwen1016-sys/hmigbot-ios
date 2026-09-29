#!/usr/bin/env python3
"""判定并行与采集解耦（2026-09-13 用户拍板 B：采集一趟一次跑，判定按**负载**切包并派；不许 hard code 页数）。

  · 页与 escalation 不重不漏；escalation 按 owner（to→from→第一包）唯一归属；
  · 预算按上下文推导；单页超预算独占一包；页数上限只是防呆；
  · 页级产物必读、证据产物抽看（同样 30 张证据图不等于 30 张页级图）；
  · 小 app 一包、大 app 多包，包数随负载变，不随页数硬切。
夹具占位串；子进程跑真脚本。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import slice_judge_input as SJ  # noqa: E402


def _run(*args, cwd):
    return subprocess.run([sys.executable, str(SCRIPTS / "slice_judge_input.py"), *map(str, args)],
                          cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def _page(pid, root, n_evidence=0, big_json=0):
    """一页：三张页级图 + 一份到达 dump（都真实落盘），可选 n_evidence 份证据图/dump，可选填充 JSON。"""
    sd = root / "spec" / "visual-verify" / "screenshots"
    files = {"sbs": sd / "sbs" / f"{pid}.jpeg", "hmos_screenshot": sd / "harmony" / f"{pid}.jpeg",
             "android_baseline": sd / "android" / f"{pid}.png", "hmos_dump": sd / "harmony" / f"{pid}.hmos.json"}
    for k, p in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * (40 * 1024 if k == "hmos_dump" else 100))
    obs = []
    for i in range(n_evidence):
        shot = sd / "evidence" / f"{pid}__el{i}.jpeg"; dump = sd / "evidence" / f"{pid}__el{i}.hmos.json"
        shot.parent.mkdir(parents=True, exist_ok=True); shot.write_bytes(b"x" * 100); dump.write_bytes(b"x" * (40 * 1024))
        obs.append({"element": f"占位{i}", "evidence": {"shot": str(shot.relative_to(root)), "dump": str(dump.relative_to(root))}})
    return {"page_id": pid, **{k: str(p.relative_to(root)) for k, p in files.items()},
            "functional_checks": [], "behavior_observations": obs, "pad": "占" * big_json}


def _ji(root, pages, escalations=()):
    ji = {"trip": "trip_1_logged_out", "round": 0, "pages": pages, "escalations": list(escalations),
          "llm_interventions": [{"note": "占位"}], "functional_coverage": {"x": 1}}
    d = root / "spec" / "visual-verify" / "replay" / "round-0-trip_1_logged_out"; d.mkdir(parents=True, exist_ok=True)
    p = d / "judge_input_round0.json"; p.write_text(json.dumps(ji, ensure_ascii=False), encoding="utf-8")
    return p


def _read_packets(root, p):
    idx = json.load(open(p.parent / "judge_packets" / "judge_packets.json", encoding="utf-8"))
    pk = [json.load(open(root / x["file"], encoding="utf-8")) for x in idx["packets"]]
    return idx, pk


def test_conservation_owner_rule_and_passthrough(tmp_path):
    pages = [_page(f"Page{c}", tmp_path) for c in "ABCDE"]
    esc = [{"step": 1, "from": "PageA", "to": "PageB"},      # owner=PageB
           {"step": 2, "from": "PageC", "to": "PageZ"},      # to 不在页集 → owner=PageC
           {"step": 3, "from": "PageY", "to": "PageZ"}]      # 都不在 → 孤儿 → 第一包
    p = _ji(tmp_path, pages, esc)
    r = _run("--judge-input", p, "--project-root", tmp_path, "--budget-kb", "80", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    idx, pk = _read_packets(tmp_path, p)
    allp = [x for k in pk for x in k["packet"]["pages"]]
    assert sorted(allp) == ["PageA", "PageB", "PageC", "PageD", "PageE"] and len(allp) == len(set(allp))
    alle = [e["step"] for k in pk for e in k["escalations"]]
    assert sorted(alle) == [1, 2, 3]
    own = {e["step"]: k["packet"]["pages"] for k in pk for e in k["escalations"]}
    assert "PageB" in own[1] and "PageC" in own[2] and own[3] == pk[0]["packet"]["pages"]
    for k in pk:                                            # 趟级段：无页标识的只进第一包；标量每包保留
        assert k["llm_interventions"] == ([{"note": "占位"}] if k["packet"]["part"] == 1 else [])
        assert k["functional_coverage"] == {"x": 1}
        assert k["packet"]["of"] == len(pk) and k["trip"] == "trip_1_logged_out"
        assert len(k["pages"]) == len(k["packet"]["pages"])
    assert idx["total_pages"] == 5 and all(x["load_kb"] <= 80 or len(x["pages"]) == 1 for x in idx["packets"])


def test_budget_drives_packet_count_not_page_count(tmp_path):
    pages = [_page(f"Page{c}", tmp_path) for c in "ABCDEFGH"]
    p = _ji(tmp_path, pages)
    r1 = _run("--judge-input", p, "--project-root", tmp_path, "--budget-kb", "10000", "--dry-run", cwd=tmp_path)
    assert json.loads(r1.stdout.strip().splitlines()[-1])["packets"] == 1          # 小 app：一包
    r2 = _run("--judge-input", p, "--project-root", tmp_path, "--budget-kb", "30", "--dry-run", cwd=tmp_path)
    assert json.loads(r2.stdout.strip().splitlines()[-1])["packets"] >= 4         # 预算小：多包
    r3 = _run("--judge-input", p, "--project-root", tmp_path, "--budget-kb", "10000", "--max-pages", "3", "--dry-run", cwd=tmp_path)
    assert json.loads(r3.stdout.strip().splitlines()[-1])["packets"] == 3         # 防呆上限兜底


def test_heavy_page_stands_alone_and_default_budget_is_derived(tmp_path):
    pages = [_page("PageA", tmp_path, big_json=300 * 1024), _page("PageB", tmp_path), _page("PageC", tmp_path)]
    p = _ji(tmp_path, pages)
    r = _run("--judge-input", p, "--project-root", tmp_path, "--context-tokens", "100000", "--bytes-per-token", "3",
             "--input-share", "0.5", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    idx, pk = _read_packets(tmp_path, p)
    assert idx["budget_kb"] == round(100000 * 3 * 0.5 / 1024, 1)                # 146.5：按上下文推导
    heavy = [x for x in idx["packets"] if "PageA" in x["pages"]][0]
    assert heavy["pages"] == ["PageA"] and heavy["load_kb"] > idx["budget_kb"]   # 超预算的页独占一包，不再切细


def test_evidence_artifacts_weigh_less_than_page_level(tmp_path):
    root = tmp_path
    loads, _ = SJ.page_loads({"pages": [_page("PageA", root, n_evidence=30), _page("PageB", root)]}, str(root), 5.0, 0.25, 0.2)
    la, lb = {l["page_id"]: l for l in loads}["PageA"], {l["page_id"]: l for l in loads}["PageB"]
    assert la["evidence_images"] == 30 and la["evidence_dumps"] == 30 and la["images"] == 3 and la["dumps"] == 1
    # 30 份证据（图+dump）只按 0.2 抽看：增量 = 0.2×(30×5 + 30×40×0.25) = 90 KB，而不是 450 KB
    assert 80 < la["load_kb"] - lb["load_kb"] < 100


def test_missing_files_do_not_count(tmp_path):
    pg = _page("PageA", tmp_path)
    pg["sbs"] = "spec/visual-verify/screenshots/sbs/不存在.jpeg"
    loads, _ = SJ.page_loads({"pages": [pg]}, str(tmp_path), 5.0, 0.25, 0.2)
    assert loads[0]["images"] == 2


# ── v2：不劣化判定的三条 + 并行上限 ─────────────────────────────────────────
def _loads(pids, kb=100.0):
    return [{"page_id": p, "load_kb": kb, "json_kb": kb, "images": 0, "dumps": 0, "evidence_images": 0,
             "evidence_dumps": 0, "escalations": 0} for p in pids]


def test_chain_is_cut_contiguously_along_edges():
    """链 A→B→C→D→E，预算装两页：切成 [A,B],[C,D],[E]，只断 2 条边；按负载 FFD 会把链打散。"""
    loads = _loads(list("ABCDE")); soft = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")]
    pk = SJ.pack(loads, soft, [], budget_kb=210, max_pages=10)
    assert pk == [["A", "B"], ["C", "D"], ["E"]]
    assert len(SJ.cut_edges(pk, soft)) == 2


def test_dfs_order_keeps_neighbours_adjacent_even_if_input_order_is_shuffled():
    loads = _loads(["A", "C", "E", "B", "D"]); soft = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")]
    pk = SJ.pack(loads, soft, [], budget_kb=210, max_pages=10)
    assert len(SJ.cut_edges(pk, soft)) == 2 and sorted(sum(pk, [])) == list("ABCDE")


def test_alias_atom_is_never_split_even_over_budget():
    loads = _loads(["A", "B", "C"], kb=150.0); hard = [("A", "B")]
    pk = SJ.pack(loads, [], hard, budget_kb=200, max_pages=10)
    assert ["A", "B"] in pk and not SJ.cut_edges(pk, hard)


def test_unlinked_pages_are_merged_across_components():
    loads = _loads(list("ABCDEF"), kb=50.0)
    pk = SJ.pack(loads, [("A", "B")], [], budget_kb=200, max_pages=10)
    assert len(pk) == 2 and sorted(sum(pk, [])) == list("ABCDEF")


def test_cross_ref_stub_and_trip_level_ownership(tmp_path):
    pages = [_page(f"Page{c}", tmp_path, big_json=60 * 1024) for c in "AB"]      # 两页各 ~60KB，预算 80 → 必拆两包
    esc = [{"step": 7, "from": "PageA", "to": "PageB", "verdict": "ABANDON_no_match", "blame": "占位"}]
    ji = {"trip": "trip_1_logged_out", "round": 0, "pages": pages, "escalations": esc,
          "unverified_destructive": [{"node": "PageA", "trigger": "占位甲"}, {"node": "PageB", "trigger": "占位乙"}, {"node": "PageZ", "trigger": "占位丙"}],
          "llm_interventions": [{"kind": "handoff", "note": "占位"}, {"kind": "handoff", "note": "占位2"}],
          "functional_coverage": {"ratio": 0.5, "gap_items": [{"node": "PageB", "name": "占位点"}]},
          "coverage_reconciliation": {"targets": 2, "missing": ["PageB"], "note": "占位"},
          "evidence_path_rule": "占位规则"}
    d = tmp_path / "spec" / "visual-verify" / "replay" / "round-0-trip_1_logged_out"; d.mkdir(parents=True, exist_ok=True)
    p = d / "judge_input_round0.json"; p.write_text(json.dumps(ji, ensure_ascii=False), encoding="utf-8")
    r = _run("--judge-input", p, "--project-root", tmp_path, "--budget-kb", "80", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    idx, pk = _read_packets(tmp_path, p)
    assert len(pk) == 2 and idx["cross_packet_edges"] == [["PageA", "PageB"]]
    a = next(k for k in pk if k["packet"]["pages"] == ["PageA"]); b = next(k for k in pk if k["packet"]["pages"] == ["PageB"])
    assert b["escalations"] == esc and a["escalations"] == []                          # 归 to 所在包
    assert a["escalations_cross_ref"][0]["owned_by_part"] == b["packet"]["part"]          # 对侧只读存根
    assert [x["trigger"] for x in a["unverified_destructive"]] == ["占位甲", "占位丙"]     # PageZ 不在页集 → 第一包
    assert [x["trigger"] for x in b["unverified_destructive"]] == ["占位乙"]
    assert len(a["llm_interventions"]) == 2 and b["llm_interventions"] == []             # 无页标识 → 只进第一包
    assert b["functional_coverage"]["gap_items"] == [{"node": "PageB", "name": "占位点"}] and a["functional_coverage"]["gap_items"] == []
    assert a["functional_coverage"]["ratio"] == b["functional_coverage"]["ratio"] == 0.5   # 趟级标量每包保留
    assert b["coverage_reconciliation"]["missing"] == ["PageB"] and a["coverage_reconciliation"]["missing"] == []
    assert a["evidence_path_rule"] == b["evidence_path_rule"] == "占位规则"


def test_waves_and_hard_packet_cap(tmp_path):
    pages = [_page(f"Page{i:02d}", tmp_path, big_json=30 * 1024) for i in range(12)]
    p = _ji(tmp_path, pages)
    r = _run("--judge-input", p, "--project-root", tmp_path, "--budget-kb", "40", "--max-parallel", "5", "--dry-run", cwd=tmp_path)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["packets"] == 12 and [len(w) for w in out["waves"]] == [5, 5, 2]
    r2 = _run("--judge-input", p, "--project-root", tmp_path, "--budget-kb", "40", "--max-packets", "3", cwd=tmp_path)
    assert r2.returncode == 0, r2.stderr
    idx, pk = _read_packets(tmp_path, p)
    assert len(pk) <= 3 and idx["cap_applied"] and idx["budget_effective_kb"] > idx["budget_kb"]
    assert sorted(x for k in pk for x in k["packet"]["pages"]) == sorted(pg["page_id"] for pg in pages)
