#!/usr/bin/env python3
"""三本账机械化单测：page_status / build_batch_manifest / append_attempt / render_round_summary（无设备，合成项目）。
运行：python3 scripts/_tests/test_ledgers.py
"""
import json, os, re, subprocess, sys, tempfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); SC = os.path.abspath(os.path.join(HERE, ".."))
PY = sys.executable; N = 0
def run(script, args, root):
    return subprocess.run([PY, os.path.join(SC, script), *args, "--project-root", root], capture_output=True, text=True, cwd=root)
def check(c, msg):
    global N
    if not c: print("  ✗", msg); sys.exit(1)
    N += 1; print("  ✓", msg)
def ticket(root, rnd, layer, fid, page, kind="ALIGNMENT_DIFF", sev="P1", msev="high", extra=""):
    d = os.path.join(root, f"spec/fix/round-{rnd}/{layer}"); os.makedirs(d, exist_ok=True)
    body = f"""---
id: {fid}
title: "[{page}] t-{fid}"
source: visual-verify
layer: {layer}
kind: {kind}
severity: {sev}
page_id: {page}
multimodal_severity: {msev}
disposition: null
{extra}---
# t

## 1. Spec 引用
x
## 2. 期望
x
## 3. 实际
x
## 4. 源码缺口
x
## 5. 修复建议
x
## 6. 尝试过的修复方案（仅由 visual-fixer 追加，禁删历史条目）

<!-- 首次写 markdown 时本段为空 -->

## 7. 实际可达路径
x
"""
    p = os.path.join(d, fid + ".md"); open(p, "w", encoding="utf-8").write(body); return p

tmp = tempfile.mkdtemp(prefix="ledger_")
try:
    root = tmp
    os.makedirs(os.path.join(root, "spec/visual-verify/batches/b1"), exist_ok=True)
    spec = {"trips": [{"trip_id": "trip_1", "trip_label": "T1", "scenario_chain": [], "batches": [
        {"batch_id": "b1", "starting_page": "Home", "pages": [{"page_id": "Home", "kind": "Activity"}, {"page_id": "Mine", "kind": "Fragment"}, {"page_id": "Blk", "kind": "Activity"}, {"page_id": "Ghost", "kind": "Activity"}]}]}]}
    json.dump(spec, open(os.path.join(root, "spec/visual-verify/batches.json"), "w"))
    json.dump({"pages": [{"id": "Home", "label": "首页"}, {"id": "Mine"}, {"id": "Blk"}, {"id": "Ghost"}], "fragments": [], "dialogs": []}, open(os.path.join(root, "spec/toolkit-fact-tree.json"), "w"))
    for pg in ("Home", "Mine"):
        d = os.path.join(root, "spec/visual-verify/screenshots/harmony/round-0/trip_1"); os.makedirs(d, exist_ok=True); open(os.path.join(d, pg + ".jpeg"), "w").close()
    # 工单：Home 2 张 ui（high, medium）+ Mine 1 张 feat（subsumes 一张已删 ui）+ Blk 占位
    ticket(root, 0, "ui", "ALIGN_PHome_a", "Home", msev="high"); ticket(root, 0, "ui", "ALIGN_PHome_b", "Home", msev="medium")
    ticket(root, 0, "feat", "Mine_feat_x", "Mine", kind="IMPL_MISSING", sev="P0", extra="subsumes_ui: [ALIGN_PMine_gone]\n")
    d = os.path.join(root, "spec/fix/round-0/ui"); open(os.path.join(d, "BLOCKED_PBlk.md"), "w").write("---\nid: BLOCKED_PBlk\npage_id: Blk\nkind: BLOCKED\nlayer: ui\nseverity: P3\n---\n")
    # 1) page_status 合并写
    bd = "spec/visual-verify/batches/b1"
    p = run("page_status.py", ["--batch-dir", bd, "--page", "Home", "--status", "fail", "--set", "similarity=0.7", "--elapsed", "nav=10"], root); check(p.returncode == 0, "page_status 首写")
    p = run("page_status.py", ["--batch-dir", bd, "--page", "Home", "--set", "high_count=5", "--elapsed", "compare=30"], root)
    st = json.load(open(os.path.join(root, bd, "pages/Home.status.json"))); check(st["status"] == "fail" and st["elapsed"] == {"nav": 10, "compare": 30} and st["high_count"] == 5, "page_status 合并：字段累加、elapsed 按桶合并")
    run("page_status.py", ["--batch-dir", bd, "--page", "Mine", "--status", "pass"], root)          # pass 但有 feat 单 → hard
    run("page_status.py", ["--batch-dir", bd, "--page", "Blk", "--status", "blocked"], root)
    # Ghost 没有判断账 → hard missing_page_status
    json.dump({"unstable_edges": [{"from_page": "Home", "reason": "x"}], "scenario_results": [{"scenario": "login", "success": True}]}, open(os.path.join(root, bd, "batch_notes.json"), "w"))
    # 2) 拼 manifest
    p = run("build_batch_manifest.py", ["--batch-id", "b1", "--round", "0"], root)
    check(p.returncode == 20, f"有 hard 不一致 → exit 20 (got {p.returncode})")
    m = json.load(open(os.path.join(root, bd, "manifest.json")))
    ids = {f["id"] for f in m["findings"]}
    check(ids == {"ALIGN_PHome_a", "ALIGN_PHome_b", "Mine_feat_x", "ALIGN_PMine_gone"}, "findings[] 从工单文件拼出（含 subsumes_ui 反推的 folded 项）")
    fold = next(f for f in m["findings"] if f["id"] == "ALIGN_PMine_gone"); check(fold.get("folded_into") == "Mine_feat_x" and fold["fix_file"] is None, "folded_into 由 feat 单 subsumes_ui 反推")
    hs = m["pages_status"]["Home"]; check(hs["high_count"] == 1 and hs["medium_count"] == 1 and hs["ui_findings"] == ["ALIGN_PHome_a", "ALIGN_PHome_b"], "计数/清单以工单为准（模型自报 high=5 被纠正）")
    checks = {h["check"] for h in m["assembly_checks"]["hard"]}
    check("pass_with_findings" in checks and "missing_page_status" in checks, f"hard 闸：pass 却有工单 / 批内页缺账 → {sorted(checks)}")
    check(any(s["check"] == "count_mismatch" for s in m["assembly_checks"]["soft"]), "soft：自报计数≠工单计数被记录")
    check(m["unstable_edges"][0]["from_page"] == "Home" and m["scenario_results"][0]["scenario"] == "login", "batch_notes 判断字段透传")
    check(m["blocked_placeholders"] == ["spec/fix/round-0/ui/BLOCKED_PBlk.md"] and m["fix_files"] and all(os.path.exists(os.path.join(root, f)) for f in m["fix_files"]), "blocked_placeholders / fix_files 来自磁盘且都存在")
    # 修正判断后 → exit 0
    run("page_status.py", ["--batch-dir", bd, "--page", "Mine", "--status", "fail"], root); run("page_status.py", ["--batch-dir", bd, "--page", "Ghost", "--status", "skipped"], root)
    p = run("build_batch_manifest.py", ["--batch-id", "b1", "--round", "0"], root); check(p.returncode == 0, "判断改对后 → exit 0")
    # fail 但无工单且无关联 → hard；有 blocked_by → 放行
    run("page_status.py", ["--batch-dir", bd, "--page", "Ghost", "--status", "fail"], root)
    p = run("build_batch_manifest.py", ["--batch-id", "b1", "--round", "0"], root); m = json.load(open(os.path.join(root, bd, "manifest.json")))
    check(p.returncode == 20 and any(h["check"] == "fail_without_findings" for h in m["assembly_checks"]["hard"]), "fail 无工单无关联 → hard")
    open(os.path.join(root, "spec/visual-verify/screenshots/harmony/round-0/trip_1/Ghost.jpeg"), "w").close()   # 有凭证，只测关联
    run("page_status.py", ["--batch-dir", bd, "--page", "Ghost", "--set", "blocked_by=upstream_x"], root)
    p = run("build_batch_manifest.py", ["--batch-id", "b1", "--round", "0"], root); check(p.returncode == 0, "fail 带 blocked_by（失败源在上游）→ 放行为 soft")
    # 动态批（不在 batches.json）
    os.makedirs(os.path.join(root, "spec/visual-verify/batches/dyn"), exist_ok=True)
    run("page_status.py", ["--batch-dir", "spec/visual-verify/batches/dyn", "--page", "Home", "--status", "pass"], root)
    p = run("build_batch_manifest.py", ["--batch-id", "dyn", "--round", "0", "--trip-id", "trip_1"], root); check(p.returncode in (0, 20) and "动态批" in p.stderr, "不在 batches.json 的动态批可拼（页集=判断账）")
    # 3) append_attempt：追加 / 防重复 / replace / check
    t = "spec/fix/round-0/ui/ALIGN_PHome_a.md"
    p = run("append_attempt.py", ["--ticket", t, "--round", "0", "--files", "a.ets:1", "--summary", "S0", "--hypothesis", "H0", "--expected", "E0", "--not-done", "N0"], root); check(p.returncode == 0, "追加 round-0 attempt")
    p = run("append_attempt.py", ["--ticket", t, "--round", "0", "--files", "a.ets:1", "--summary", "S0", "--hypothesis", "H0", "--expected", "E0", "--not-done", "N0"], root); check(p.returncode == 4, "同轮重复追加 → exit 4")
    # round-1 的 attempt 追加在 round-1 目录里的 carry-forward 副本上（真实流程：Phase 3 把上轮未了结单带入本轮，§6 历史随之带入）
    os.makedirs(os.path.join(root, "spec/fix/round-1/ui"), exist_ok=True)
    t1 = "spec/fix/round-1/ui/ALIGN_PHome_a.md"; shutil.copy(os.path.join(root, t), os.path.join(root, t1)); t = t1
    p = run("append_attempt.py", ["--ticket", t, "--round", "1", "--files", "b.ets:2", "--summary", "S1", "--hypothesis", "H1", "--expected", "E1", "--not-done", "N1", "--log-dir", "docs/autofix-log/round-1"], root)
    txt = open(os.path.join(root, t), encoding="utf-8").read()
    check(txt.count("### round-0 attempt by visual-fixer") == 1 and txt.count("### round-1 attempt by visual-fixer") == 1 and txt.index("round-0 attempt") < txt.index("round-1 attempt") < txt.index("## 7."), "两轮块按序追加在 §6 末尾、§7 之前")
    aj = json.load(open(os.path.join(root, "docs/autofix-log/round-1/attempts.json")))
    check(aj[0]["new_attempt"]["改动摘要"] == "S1" and aj[0]["history_attempts"] == [{"round": 0, "改动摘要": "S0", "假设根因": "H0"}], "attempts.json 逐字 + history 从 §6 机械提取")
    p = run("append_attempt.py", ["--check", "--round", "1", "--log-dir", "docs/autofix-log/round-1"], root); check(p.returncode == 0, "--check 一致 → 0")
    json.dump(aj + [{"finding_id": "phantom", "finding_md_path": "nope.md"}], open(os.path.join(root, "docs/autofix-log/round-1/attempts.json"), "w"))
    p = run("append_attempt.py", ["--check", "--round", "1", "--log-dir", "docs/autofix-log/round-1"], root); check(p.returncode == 1 and "phantom" in p.stdout, "--check 抓到只在 json 里的幽灵条目 → 1")
    p = run("append_attempt.py", ["--ticket", t, "--round", "1", "--replace", "--files", "b.ets:2", "--summary", "S1b", "--hypothesis", "H1", "--expected", "E1", "--not-done", "N1", "--log-dir", "docs/autofix-log/round-1"], root)
    check(p.returncode == 0 and "S1b" in open(os.path.join(root, t), encoding="utf-8").read() and "S1\n" not in open(os.path.join(root, t), encoding="utf-8").read(), "--replace 覆盖同轮块")
    # 4) render_round_summary
    ticket(root, 1, "ui", "ALIGN_PHome_b", "Home"); ticket(root, 1, "ui", "ALIGN_PHome_new", "Home")
    # ★2026-09-14：_delta 的 fixed 改成「上轮 open → 本轮 disposition=fixed」的同 id 迁移，
    #   不再是「上轮有、本轮无」的集合差（那把"不结转"和"改名结转"都误记成修好了）。
    #   本轮把 b 判 fixed；Mine_feat_x 只是本轮没出现（disposition 未知）→ 不算 fixed。
    _pb = os.path.join(root, "spec/fix/round-1/ui/ALIGN_PHome_b.md")
    _tb = open(_pb, encoding="utf-8").read().replace("disposition: null", "disposition: fixed", 1)
    open(_pb, "w", encoding="utf-8").write(_tb)
    p = run("render_round_summary.py", ["--round", "1"], root); check(p.returncode == 0, "渲染 round-1")
    sm = open(os.path.join(root, "spec/fix/round-1/_summary.md"), encoding="utf-8").read(); dl = open(os.path.join(root, "spec/fix/round-1/_delta.md"), encoding="utf-8").read(); ix = open(os.path.join(root, "spec/fix/round-1/_index.md"), encoding="utf-8").read()
    for sec in ("## 总计", "## 页面维度", "## 缓存性能", "## Checks performed", "## Top 10", "## 未变化项", "## 人工补充"):
        check(sec in sm, f"_summary 含 {sec}")
    check("| **合计** | **3** | **3** |" in sm, "总计表机器算（3 张）")
    fixed_sec = dl.split("## new")[0]; new_sec = dl.split("## new")[1].split("## regressed")[0]
    check("- `ALIGN_PHome_b`" in fixed_sec and "- `Mine_feat_x`" not in fixed_sec and "- `ALIGN_PHome_a`" not in fixed_sec and "- `ALIGN_PHome_new`" in new_sec, "_delta fixed 按 disposition 迁移（消失≠修好）/ new 集合正确")
    _so = dl.split("## still_open")[1] if "## still_open" in dl else ""
    check("- `ALIGN_PHome_a`" in _so and "- `ALIGN_PHome_b`" not in _so, "_delta still_open = 两轮都在且本轮未收口")
    check("[ALIGNMENT_DIFF][P1]" in ix and "<<LLM:" in sm and not re.search(r"(已完成|收敛|通过)\b", sm.split("## 人工补充")[0]), "_index 列表 / 人工补充占位 / 机械段无结论用语")
    # 5) render_finding_skeleton --from-json：差异项原文灌 §2/§3，evidence 并入，§4/§5 仍留占位
    dj = os.path.join(root, "diff.json")
    json.dump({"category": "missing", "element": "返回箭头", "description": "鸿蒙顶栏左侧无返回箭头", "root_cause_hint": "NavHeader 未设 backButton",
               "expected": "顶栏左侧 24vp 返回箭头", "evidence": ["spec/visual-verify/screenshots/sbs/round-0/trip_1/Home.struct.json"]}, open(dj, "w"), ensure_ascii=False)
    p = subprocess.run([PY, os.path.join(SC, "render_finding_skeleton.py"), "--project-root", root, "--round", "0", "--layer", "ui", "--id", "ALIGN_PHome_fromjson",
                        "--title", "[Home] x", "--kind", "ALIGNMENT_DIFF", "--severity", "P1", "--category-pattern", "missing_element", "--page", "Home", "--trip", "trip_1",
                        "--from-json", dj, "--tree", os.path.join(root, "spec/toolkit-fact-tree.json")], capture_output=True, text=True, cwd=root)
    check(p.returncode == 0, f"skeleton --from-json exit 0 ({p.stdout[:80]})")
    md = open(os.path.join(root, "spec/fix/round-0/ui/ALIGN_PHome_fromjson.md"), encoding="utf-8").read()
    s2 = md.split("## 2. 期望")[1].split("## 3. 实际")[0]; s3 = md.split("## 3. 实际")[1].split("## 4. 源码缺口")[0]
    check("顶栏左侧 24vp 返回箭头" in s2 and "<<LLM" not in s2, "§2 期望 = expected 原文")
    check("description: 鸿蒙顶栏左侧无返回箭头" in s3 and "root_cause_hint: NavHeader 未设 backButton" in s3 and "--from-json，未改写" in s3 and "<<LLM" not in s3, "§3 实际 = description/root_cause_hint 原文 + 来源标注")
    check("Home.struct.json" in md and md.count("<<LLM") == 2, "evidence 并入；§4/§5 占位仍留给模型")
    p = subprocess.run([PY, os.path.join(SC, "render_finding_skeleton.py"), "--project-root", root, "--round", "0", "--layer", "ui", "--id", "ALIGN_PHome_bad",
                        "--title", "x", "--kind", "ALIGNMENT_DIFF", "--severity", "P1", "--page", "Home", "--trip", "trip_1", "--from-json", "[1,2]"], capture_output=True, text=True, cwd=root)
    check(p.returncode == 2 and "单个 JSON 对象" in p.stdout, "--from-json 传数组 → exit 2（先分类再逐条传）")
    # 6) N7/N2：--done 校验 + 时间戳 + --resume 续跑
    bd2 = "spec/visual-verify/batches/b1"
    st = json.load(open(os.path.join(root, bd2, "pages/Home.status.json")))
    check(st.get("_ts_first") and st.get("_ts_last") and st.get("_writes", 0) >= 2, "page_status 记 _ts_first/_ts_last/_writes")
    p = run("page_status.py", ["--batch-dir", bd2, "--page", "Home", "--status", "fail", "--done", "--round", "0", "--trip", "trip_1"], root)
    check(p.returncode == 0 and json.load(open(os.path.join(root, bd2, "pages/Home.status.json"))).get("done") is True, "fail 页有工单+截图 → --done 通过")
    p = run("page_status.py", ["--batch-dir", bd2, "--page", "Ghost", "--status", "fail", "--set", "blocked_by=", "--done", "--round", "0", "--trip", "trip_1"], root)
    st = json.load(open(os.path.join(root, bd2, "pages/Ghost.status.json")))
    check(p.returncode == 3 and not st.get("done") and "无工单" in p.stderr, "fail 页无工单无 blocked_by → --done 拒绝(exit 3)，done 未置")
    os.remove(os.path.join(root, "spec/visual-verify/screenshots/harmony/round-0/trip_1/Ghost.jpeg"))
    p = run("page_status.py", ["--batch-dir", bd2, "--page", "Ghost", "--status", "pass", "--done", "--round", "0", "--trip", "trip_1"], root)
    check(p.returncode == 3 and "无该页鸿蒙截图" in p.stderr, "pass 页无截图 → --done 拒绝")
    run("page_status.py", ["--batch-dir", bd2, "--page", "Blk", "--status", "blocked", "--done", "--round", "0", "--trip", "trip_1"], root)
    p = run("fill_batch_prompt.py", ["--batch-id", "b1", "--round", "0", "--resume"], root)
    sm = json.loads(p.stdout.strip().splitlines()[-1]); pm = json.load(open(os.path.join(root, sm["prompt_manifest"])))
    check(sorted(pm["resume"]["completed"]) == ["Blk", "Home"] and sorted(pm["resume"]["remaining"]) == ["Ghost", "Mine"], f"--resume：仅 done 且证据齐的页算完成 {pm['resume']['completed']}，其余重做 {pm['resume']['remaining']}")
    check("Ghost" in pm["resume"]["rejected"] and "未标 done" in pm["resume"]["rejected"]["Ghost"][0], "有账但未标 done 的页记 rejected 原因")
    body = open(os.path.join(root, sm["out"]), encoding="utf-8").read()
    check("已完成页" in body and '"Home"' in body.split("已完成页")[1].split("\n")[0] and "跳过不重做" in body, "prompt 注入已完成页清单")
    p = run("fill_batch_prompt.py", ["--batch-id", "b1", "--round", "0"], root); pm = json.load(open(os.path.join(root, sm["prompt_manifest"])))
    check(pm["resume"]["enabled"] is False and len(pm["resume"]["remaining"]) == 4, "非 --resume 派发：全部页待做")
    # 7) N5 precheck：占位改动文件 / 与历史完全相同 / 死路径
    ld = os.path.join(root, "docs/autofix-log/round-3"); os.makedirs(ld, exist_ok=True)
    json.dump([{"finding_id": "A", "finding_md_path": "spec/fix/round-1/ui/ALIGN_PHome_a.md", "new_attempt": {"改动文件": ["无"], "改动摘要": "S", "假设根因": "H", "预期效果": "E", "未做的事": "N"}, "history_attempts": []},
               {"finding_id": "B", "finding_md_path": "nope.md", "new_attempt": {"改动文件": ["x.ets:1"], "改动摘要": "S1", "假设根因": "H1", "预期效果": "E", "未做的事": "N"}, "history_attempts": [{"round": 2, "改动摘要": "`S1`", "假设根因": "H1。"}]}], open(os.path.join(ld, "attempts.json"), "w"), ensure_ascii=False)
    open(os.path.join(ld, "git-diff.patch"), "w").write("diff --git a/x.ets b/x.ets\n--- a/x.ets\n+++ b/x.ets\n@@ -1 +1 @@\n-a\n+b\n")
    p = run("precheck_attempts.py", ["--round", "3"], root); rep = json.load(open(os.path.join(ld, "attempts_precheck.json")))
    fl = {r["finding_id"]: sorted(f["flag"] for f in r["flags"]) for r in rep["results"]}
    check(p.returncode == 1 and fl["A"] == ["empty_diff"] and fl["B"] == ["dead_path", "duplicate_hypothesis"], f"precheck：占位改动→empty_diff；反引号/句号归一后与历史相同→duplicate；死路径 {fl}")
    check(rep["results"][1]["reviewer_can_skip"] == ["check1_empty_diff"], "diff 命中的 attempt 标 reviewer 可跳过 Check 1")
    # 8) N3 候选器：category_pattern 缺失时走启发式；有 pattern 走正规则
    os.makedirs(os.path.join(root, "spec/visual-verify/batches/b2/pages"), exist_ok=True); os.makedirs(os.path.join(root, "spec/visual-verify/batches/b3"), exist_ok=True)
    for pg in ("P1", "P2", "P3"):
        ticket(root, 0, "ui", f"ALIGN_P{pg}_layout_drift_progress-indicator", pg, extra="category_pattern: progress_indicator_drift\n")
    json.dump({"current_round": 0, "batch_id": "b2", "findings": [{"id": f"ALIGN_P{pg}_layout_drift_progress-indicator", "page_id": pg, "kind": "ALIGNMENT_DIFF", "category_pattern": "layout_drift__progress_indicator", "category_pattern_confidence": "high", "fix_file": f"spec/fix/round-0/ui/ALIGN_P{pg}_layout_drift_progress-indicator.md"} for pg in ("P1", "P2")]}, open(os.path.join(root, "spec/visual-verify/batches/b2/manifest.json"), "w"))
    json.dump({"current_round": 0, "batch_id": "b3", "findings": [{"id": "ALIGN_PP3_layout_drift_progress-indicator", "page_id": "P3", "kind": "ALIGNMENT_DIFF", "category_pattern": "layout_drift__progress_indicator", "category_pattern_confidence": "medium", "fix_file": "x"}, {"id": "ALIGN_PP4_layout_drift_title-overlap", "page_id": "P4", "kind": "ALIGNMENT_DIFF", "category_pattern": None, "fix_file": "y"}, {"id": "ALIGN_PP5_layout_drift_title-gap", "page_id": "P5", "kind": "ALIGNMENT_DIFF", "category_pattern": None, "fix_file": "y"}, {"id": "ALIGN_PP6_layout_drift_title-color", "page_id": "P6", "kind": "ALIGNMENT_DIFF", "category_pattern": None, "fix_file": "y"}]}, open(os.path.join(root, "spec/visual-verify/batches/b3/manifest.json"), "w"))
    p = run("cluster_systemic_candidates.py", ["--round", "0"], root); rep = json.load(open(os.path.join(root, "spec/fix/round-0/_systemic_candidates.json")))
    keys = {(c["rule"], c["key"]) for c in rep["candidates"]}
    check(("A:category_pattern", "layout_drift__progress_indicator") in keys and next(c for c in rep["candidates"] if c["key"] == "layout_drift__progress_indicator")["cross_batch"], "A 规则：同完整键(high+medium)跨 2 批 3 页 → 候选")
    check(any(h["key"] == "title" for h in rep["hints"]) and not any(c["key"] == "title" for c in rep["candidates"]) and rep["category_pattern_missing"] >= 3, "无 pattern 的单只进 hints（不聚），并报缺失数")
    # 9) N3-b：词表生成（合成 dump）→ 推导 → 骨架自动填 → 聚类门槛
    dd = os.path.join(root, "spec/visual-verify/screenshots/android/trip_1"); os.makedirs(dd, exist_ok=True)
    xml = ('<hierarchy><node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">'
           '<node text="" resource-id="com.x:id/iv_back" class="android.widget.ImageView" bounds="[20,80][120,180]"/>'
           '<node text="标题" resource-id="com.x:id/tv_title" class="android.widget.TextView" bounds="[400,80][680,180]"/>'
           '<node text="" resource-id="com.x:id/mine_feedback" class="android.widget.ImageView" bounds="[20,80][120,180]"/>'
           '<node text="" resource-id="com.x:id/ll_bottom_tab" class="android.widget.LinearLayout" bounds="[0,2200][1080,2400]"/>'
           '<node text="" resource-id="com.x:id/tv_outline_title" class="android.widget.TextView" bounds="[0,1200][1080,1300]"/>'
           '</node></hierarchy>')
    for pg in ("Home", "Mine", "Blk"):
        open(os.path.join(dd, pg + ".android.xml"), "w", encoding="utf-8").write(xml)
    p = run("build_pattern_vocab.py", ["--out", "spec/visual-verify/category-patterns.json"], root); check(p.returncode == 0, "词表生成 exit 0")
    vb = json.load(open(os.path.join(root, "spec/visual-verify/category-patterns.json")))
    check("iv_back" in vb["concepts"]["navheader.back"]["rids"] and "tv_title" in vb["concepts"]["navheader.title"]["rids"] and "ll_bottom_tab" in vb["concepts"]["tab_bar"]["rids"], "rid 按词元+带位映射到概念")
    check(not any("mine_feedback" in c["rids"] for c in vb["concepts"].values()), "feedback 不再子串命中 back")
    check("tv_outline_title" in vb["needs_confirm"] and not any("tv_outline_title" in c["rids"] for c in vb["concepts"].values()), "带位不符的 title 进 needs_confirm，不进映射（不确定的不聚）")
    p = run("derive_pattern.py", ["--diff-kind", "layout_drift", "--element", "返回箭头", "--rid", "iv_back"], root); d = json.loads(p.stdout.strip())
    check(d["category_pattern"] == "layout_drift__navheader.back" and d["confidence"] == "high", "derive：rid+中文 → 高置信概念")
    p = run("derive_pattern.py", ["--diff-kind", "color_mismatch", "--element", "zzqq"], root); d = json.loads(p.stdout.strip())
    check(d["concept"].startswith("other:") and d["confidence"] == "none", "derive：推不出 → other:，置信 none")
    md = open(os.path.join(root, "spec/fix/round-0/ui/ALIGN_PHome_fromjson.md"), encoding="utf-8").read()
    check("category_pattern: missing_element__navheader.back" in md and ("category_pattern_confidence: high" in md or "category_pattern_confidence: medium" in md), "骨架 --from-json 自动填 category_pattern + 置信度（此前骨架根本不写该字段）")
    # 聚类门槛：3 页 high 同概念成簇；low 的不进；other 不进
    os.makedirs(os.path.join(root, "spec/visual-verify/batches/b4"), exist_ok=True)
    json.dump({"current_round": 1, "batch_id": "b4", "findings": [
        {"id": "ALIGN_PA_layout_drift_x", "page_id": "A", "kind": "ALIGNMENT_DIFF", "category_pattern": "layout_drift__navheader.back", "category_pattern_confidence": "high", "fix_file": "a"},
        {"id": "ALIGN_PB_missing_element_x", "page_id": "B", "kind": "ALIGNMENT_DIFF", "category_pattern": "missing_element__navheader.back", "category_pattern_confidence": "high", "fix_file": "b"},
        {"id": "ALIGN_PC_layout_bug_x", "page_id": "C", "kind": "ALIGNMENT_DIFF", "category_pattern": "layout_bug__navheader.back", "category_pattern_confidence": "high", "fix_file": "c"},
        {"id": "ALIGN_PD_layout_bug_y", "page_id": "D", "kind": "ALIGNMENT_DIFF", "category_pattern": "layout_bug__navheader.back", "category_pattern_confidence": "low", "fix_file": "d"},
        {"id": "ALIGN_PE_layout_bug_z", "page_id": "E", "kind": "ALIGNMENT_DIFF", "category_pattern": "layout_bug__other:z", "category_pattern_confidence": "none", "fix_file": "e"}]},
        open(os.path.join(root, "spec/visual-verify/batches/b4/manifest.json"), "w"))
    p = run("cluster_systemic_candidates.py", ["--round", "1"], root); rep = json.load(open(os.path.join(root, "spec/fix/round-1/_systemic_candidates.json")))
    a2 = [c for c in rep["candidates"] if c["rule"] == "A2:concept" and c["key"] == "navheader.back"]
    check(len(a2) == 1 and sorted(a2[0]["pages"]) == ["A", "B", "C"], "A2 概念级：3 个 high 跨 diff_kind 成簇，low 页 D 不进")
    check({u["id"] for u in rep["unclustered"]} >= {"ALIGN_PD_layout_bug_y", "ALIGN_PE_layout_bug_z"} and not any("E" in c["pages"] for c in rep["candidates"]), "low/other 只进 unclustered 清单")
    # 10) N5-b：report_need_info 写入校验（白名单 / 先修后问 / 参考文件覆盖 / 手写判无效）
    ld3 = os.path.join(root, "docs/autofix-log/round-3"); os.makedirs(os.path.join(root, "spec/baseline/api-inventory"), exist_ok=True)
    for rf in ("api-inventory.json", "raw_apis.json"):
        open(os.path.join(root, "spec/baseline/api-inventory", rf), "w").close()
    base = ["--round", "3", "--log-dir", "docs/autofix-log/round-3", "--blocked-layer", "卡在签名层", "--request", "服务端代签契约",
            "--searched-refs", "spec/baseline/api-inventory/api-inventory.json,spec/baseline/api-inventory/raw_apis.json", "--searched-source", "Api.kt:12"]
    p = run("report_need_info.py", ["--finding", "spec/fix/round-1/ui/ALIGN_PHome_a.md", "--info-type", "api_contract", *base], root)
    check(p.returncode == 3 and "不在白名单" in p.stdout, "info_type 不在白名单 → exit 3 未写")
    p = run("report_need_info.py", ["--finding", "spec/fix/round-1/ui/ALIGN_PHome_a.md", "--info-type", "backend_env", *base, "--prior-attempts", "A"], root)
    check(p.returncode == 3 and ("占位" in p.stdout or "empty_diff" in p.stdout), "prior_attempt A 改动文件是占位词/被预检标 empty_diff → 拒（空手过场不能当先修证据）")
    p = run("report_need_info.py", ["--finding", "spec/fix/round-1/ui/ALIGN_PHome_a.md", "--info-type", "backend_env", *base, "--prior-attempts", "nope"], root)
    check(p.returncode == 3 and "不在本轮 attempts.json" in p.stdout, "prior_attempt 不存在 → 拒（没先修就问）")
    p = run("report_need_info.py", ["--finding", "spec/fix/round-1/ui/ALIGN_PHome_a.md", "--info-type", "backend_env", "--round", "3", "--log-dir", "docs/autofix-log/round-3",
                                    "--blocked-layer", "x", "--request", "y", "--searched-refs", "spec/baseline/api-inventory/api-inventory.json", "--searched-source", "z", "--prior-attempts", "A"], root)
    check(p.returncode == 3 and "未覆盖存在的参考文件" in p.stdout and "raw_apis.json" in p.stdout, "searched_refs 漏一份存在的参考文件 → 拒")
    # A 的改动文件是占位 → 也该拒；先给 A 一个真实 attempt 再报
    aj = json.load(open(os.path.join(ld3, "attempts.json"))); aj[0]["new_attempt"]["改动文件"] = ["x.ets:1"]; json.dump(aj, open(os.path.join(ld3, "attempts.json"), "w"), ensure_ascii=False)
    os.remove(os.path.join(ld3, "attempts_precheck.json"))
    p = run("report_need_info.py", ["--finding", "spec/fix/round-1/ui/ALIGN_PHome_a.md", "--info-type", "backend_env", *base, "--prior-attempts", "A", "--affects", "B"], root)
    check(p.returncode == 0, f"证据齐 → 写入 (got {p.returncode}: {p.stdout[:120]})")
    ni = json.load(open(os.path.join(ld3, "need-info.json")))
    check(len(ni) == 1 and ni[0]["_written_by"] == "report_need_info.py" and ni[0]["exhaustion"]["prior_attempts"] == ["A"] and ni[0]["affects"] == ["B"], "落盘为规范列表形状 + _written_by")
    p = run("report_need_info.py", ["--finding", "spec/fix/round-1/ui/ALIGN_PHome_a.md", "--info-type", "test_account", *base, "--prior-attempts", "A"], root)
    check(len(json.load(open(os.path.join(ld3, "need-info.json")))) == 1, "同 finding 重报 → 覆盖不重复")
    json.dump([{"finding_ids": ["X"], "missing": "y"}], open(os.path.join(ld3, "need-info.json"), "w"))
    p = run("report_need_info.py", ["--check", "--round", "3", "--log-dir", "docs/autofix-log/round-3"], root)
    check(p.returncode == 1 and '"hand_written": 1' in p.stdout and "缺 finding_id" in p.stdout, "--check：手写异形文件判无效并列原因")
    p = run("precheck_attempts.py", ["--round", "3"], root); rep = json.load(open(os.path.join(ld3, "attempts_precheck.json")))
    check(rep["need_info"]["invalid"] == 1 and any(f["flag"] == "lazy_escalation" for f in rep["need_info"]["results"][0]["flags"]), "预检把无效/手写报缺逐条标 lazy_escalation")
    print(f"ALL PASSED ({N} checks)")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
