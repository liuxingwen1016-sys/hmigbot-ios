#!/usr/bin/env python3
"""回放模式下游接线（2026-09-13，全流程干跑归因）：

  ① mark_batch_done 真写页账 progress.pages[pid]（cond 1 的分子），同轮重跑不重复计 rounds；
  ② build_batches 边遍历分支：无 phase2_batches 时分批来源 = _trip_assignment.json + 安卓 png 全集，无 png 的页记 excluded；
  ③ Phase 5/6 脚本读 batches/round-N/<bid>/manifest.json（落位后即可见）。

夹具纪律：占位串；子进程跑真脚本；不碰任何真实工程。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))


def _run(script, *args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8")


def _manifest(tmp, rnd=0, fix_b=("x.md",)):
    m = {"batch_id": "replay-round-%d-trip_1_logged_out" % rnd, "trip_id": "trip_1_logged_out", "current_round": rnd,
         "started_at": "2026-09-13T00:00:00Z", "finished_at": "2026-09-13T00:01:00Z",
         "pages_status": {"PageA": {"status": "pass", "similarity": 0.93, "fix_files": []},
                          "PageB": {"status": "fail", "similarity": 0.4, "fix_files": list(fix_b)},
                          "PageC": {"status": "blocked"}}}
    p = tmp / f"manifest_r{rnd}.json"; p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return p


# ── ① 页账 ────────────────────────────────────────────────────────────────────
def test_mark_batch_done_folds_pages_into_progress(tmp_path):
    prog = tmp_path / "progress.json"
    r = _run("mark_batch_done.py", "--batch_id", "b1", "--manifest", _manifest(tmp_path), "--progress", prog)
    assert r.returncode == 0, r.stderr
    pg = json.loads(prog.read_text(encoding="utf-8"))
    assert set(pg["pages"]) == {"PageA", "PageB", "PageC"}
    assert pg["pages"]["PageA"] == {"rounds": 1, "fix_files": [], "status": "pass", "similarity": 0.93,
                                    "trip_id": "trip_1_logged_out", "batch_id": "b1", "last_round": 0}
    assert pg["pages"]["PageB"]["fix_files"] == ["x.md"] and pg["pages"]["PageC"]["status"] == "blocked"
    assert pg["batches"]["b1"]["pages_folded"] == 3
    # 同一轮重跑：rounds 不重复计；fix_files 并集
    r2 = _run("mark_batch_done.py", "--batch_id", "b1", "--manifest", _manifest(tmp_path, fix_b=("x.md", "y.md")), "--progress", prog)
    assert r2.returncode == 0
    pg = json.loads(prog.read_text(encoding="utf-8"))
    assert pg["pages"]["PageB"]["rounds"] == 1 and pg["pages"]["PageB"]["fix_files"] == ["x.md", "y.md"]
    # 下一轮：rounds +1
    _run("mark_batch_done.py", "--batch_id", "b1", "--manifest", _manifest(tmp_path, rnd=1), "--progress", prog)
    pg = json.loads(prog.read_text(encoding="utf-8"))
    assert pg["pages"]["PageA"]["rounds"] == 2 and pg["pages"]["PageA"]["last_round"] == 1


def test_mark_batch_done_capture_stage_does_not_touch_pages(tmp_path):
    prog = tmp_path / "progress.json"
    r = _run("mark_batch_done.py", "--batch_id", "b1", "--manifest", _manifest(tmp_path), "--progress", prog, "--stage", "capture")
    assert r.returncode == 0
    assert "pages" not in json.loads(prog.read_text(encoding="utf-8"))


# ── ② 边遍历分批 ────────────────────────────────────────────────────────────
def _spec(tmp_path, assignment, pngs):
    spec = tmp_path / "spec"; vv = spec / "visual-verify"; vv.mkdir(parents=True)
    (vv / "_trip_assignment.json").write_text(json.dumps({"pages": assignment}), encoding="utf-8")
    base = vv / "screenshots" / "android"
    for trip, names in pngs.items():
        (base / trip).mkdir(parents=True)
        for n in names:
            (base / trip / f"{n}.png").write_bytes(b"\x89PNG")
    return spec, base


def test_edgewalk_partition_uses_assignment_and_png_set(tmp_path):
    import build_batches as bb
    spec, base = _spec(tmp_path,
                       {"PageA": {"trips": ["trip_1_logged_out"]},
                        "PageB": {"trips": ["trip_1_logged_out", "trip_2_logged_in_vip"]},
                        "PageC": {"trips": ["trip_2_logged_in_vip"]}},          # 分派了但安卓没截到 → excluded
                       {"trip_1_logged_out": ["PageA", "PageB"],
                        "trip_2_logged_in_vip": ["PageB", "PageD"]})            # PageD 有 png 但分派表漏了 → 仍进（png 全集 = 分母）
    part, excluded = bb.android_edgewalk_partition(spec, base, batch_size=8)
    assert [c["pages"] for c in part["trip_1_logged_out"]] == [["PageA", "PageB"]]
    assert [c["pages"] for c in part["trip_2_logged_in_vip"]] == [["PageB", "PageD"]]
    assert all(c["source"] == "android_edgewalk_assignment" for chs in part.values() for c in chs)
    assert excluded == [{"page_id": "PageC", "trip_id": "trip_2_logged_in_vip", "status": "no_png", "reason": "no_android_baseline"}]
    # 按 batch_size 切
    part1, _ = bb.android_edgewalk_partition(spec, base, batch_size=1)
    assert [c["chunk_id"] for c in part1["trip_1_logged_out"]] == ["edgewalk_trip_1_logged_out_01", "edgewalk_trip_1_logged_out_02"]


def test_edgewalk_partition_absent_without_assignment(tmp_path):
    import build_batches as bb
    spec = tmp_path / "spec"; (spec / "visual-verify").mkdir(parents=True)
    assert bb.android_edgewalk_partition(spec, spec / "visual-verify" / "screenshots" / "android") == (None, [])


# ── ③ Phase 5/6 读 round-N 目录 ───────────────────────────────────────────────
TICKET = """---
id: ALIGN_P{pid}_text_mismatch_title
title: "[{pid}] 占位差异"
source: visual-verify
layer: ui
kind: ALIGNMENT_DIFF
severity: P1
category_pattern: text_mismatch__title
page_id: {pid}
multimodal_severity: high
disposition: null
---

# 占位
"""


def test_render_and_cluster_see_manifest_under_round_dir(tmp_path):
    root = tmp_path; fix = root / "spec" / "fix" / "round-0" / "ui"; fix.mkdir(parents=True)
    findings = []
    for pid in ("PageA", "PageB", "PageC"):
        (fix / f"ALIGN_P{pid}_text_mismatch_title.md").write_text(TICKET.format(pid=pid), encoding="utf-8")
        findings.append({"id": f"ALIGN_P{pid}_text_mismatch_title", "page_id": pid, "kind": "ALIGNMENT_DIFF",
                         "category_pattern": "text_mismatch__title", "severity": "P1", "multimodal_severity": "high",
                         "fix_file": f"spec/fix/round-0/ui/ALIGN_P{pid}_text_mismatch_title.md"})
    md = root / "spec" / "visual-verify" / "batches" / "round-0" / "replay-round-0-trip_1_logged_out"; md.mkdir(parents=True)
    (md / "manifest.json").write_text(json.dumps({
        "batch_id": "replay-round-0-trip_1_logged_out", "trip_id": "trip_1_logged_out", "current_round": 0,
        "pages_status": {p: {"status": "fail", "similarity": 0.5, "high_count": 1, "medium_count": 0, "low_count": 0}
                         for p in ("PageA", "PageB", "PageC")},
        "findings": findings}), encoding="utf-8")
    r = _run("render_round_summary.py", "--round", "0", "--project-root", root)
    assert r.returncode == 0, r.stderr
    out = json.loads([ln for ln in r.stdout.splitlines() if ln.startswith("{")][-1])
    assert out["manifests"] == 1 and out["pages"] == 3
    assert "| trip_1_logged_out | PageA |" in (root / "spec" / "fix" / "round-0" / "_summary.md").read_text(encoding="utf-8")
    c = _run("cluster_systemic_candidates.py", "--round", "0", "--project-root", root)
    assert c.returncode == 0, c.stderr
    assert "3 条 findings" in (c.stdout + c.stderr) or '"findings": 3' in c.stdout
