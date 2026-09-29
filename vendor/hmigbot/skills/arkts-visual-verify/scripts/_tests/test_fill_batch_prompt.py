#!/usr/bin/env python3
"""fill_batch_prompt.py 单测：条件段注入判定 / 省略说明 / 槽位 / 凭证 / 失败出口（无设备，纯文件）。
运行：python3 scripts/_tests/test_fill_batch_prompt.py
"""
import json, os, subprocess, sys, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, "..", ".."))
SCRIPT = os.path.join(SKILL, "scripts", "fill_batch_prompt.py")
PASSED = 0

def run(args, root):
    return subprocess.run([sys.executable, SCRIPT, *args, "--project-root", root],
                          capture_output=True, text=True, cwd=root)

def check(cond, msg):
    global PASSED
    if not cond:
        print("  ✗", msg); sys.exit(1)
    PASSED += 1; print("  ✓", msg)

def mk_project(root, via=False, dialog=False, functional=False, state=False, toolkit="harmony-migration-toolkit"):
    os.makedirs(os.path.join(root, "spec", "visual-verify"), exist_ok=True)
    pages = [{"page_id": "HomeActivity", "kind": "Activity", "preconditions": [], "edges_to_test": []}]
    tree = {"source": {"toolkit": toolkit},
            "pages": [{"id": "HomeActivity", "functional_checks": [{"name": "x"}] if functional else [],
                       "preconditions": [{"kind": "state_required"}] if state else []}],
            "fragments": [], "dialogs": []}
    if via:
        pages.append({"page_id": "HomeActivity#via=导入文档", "kind": "Activity"})
    if dialog:
        pages.append({"page_id": "PayDialog", "kind": "Dialog"})
        tree["dialogs"].append({"id": "PayDialog", "functional_checks": []})
    spec = {"trips": [{"trip_id": "trip_1_logged_out", "trip_label": "T1", "scenario_chain": [],
                       "batches": [{"batch_id": "b1", "starting_page": "HomeActivity", "pages": pages,
                                    "page_count": len(pages)}]}]}
    json.dump(spec, open(os.path.join(root, "spec", "visual-verify", "batches.json"), "w"))
    json.dump(tree, open(os.path.join(root, "spec", "toolkit-fact-tree.json"), "w"))

tmp = tempfile.mkdtemp(prefix="fbp_")
try:
    # 1) 纯 Activity 批：五段全省略，槽位全填，凭证落盘
    r1 = os.path.join(tmp, "p1"); mk_project(r1)
    p = run(["--batch-id", "b1", "--round", "2", "--hmos-target", "127.0.0.1:5555", "--hmos-bundle", "com.x"], r1)
    check(p.returncode == 0, f"纯 Activity 批渲染 exit 0 (got {p.returncode}: {p.stderr[-200:]})")
    s = json.loads(p.stdout.strip().splitlines()[-1])
    check(s["sections_included"] == [] and len(s["sections_omitted"]) == 5, "五个条件段全部省略")
    body = open(os.path.join(r1, s["out"]), encoding="utf-8").read()
    check("<!-- SECTION:" not in body, "输出里没有残留标记")
    check("已由 fill_batch_prompt.py" in body and "prompt_section_missing" in body, "省略说明含自检逃生口")
    for slot in ("{role}", "{nav_mode}", "{batch_id}", "{N}", "{trip_id}", "{hmos_target}", "{blocked_pages_json}", "{batch_json_inline}"):
        check(slot not in body, f"槽位已填 {slot}")
    check("{page_id}" in body, "运行期伪代码变量 {page_id} 保持原样")
    check("round-2/" in body and "trip_1_logged_out" in body, "轮号/trip 已代入路径")
    check("## 调用契约" not in body, "主会话专用尾段已裁掉")
    man = json.load(open(os.path.join(r1, s["prompt_manifest"])))
    check(man["schema"] == "prompt_manifest.v1" and man["sections_omitted"] == s["sections_omitted"], "prompt_manifest.json 落盘且一致")
    check(man["page_conditions"]["HomeActivity"]["has_functional_checks"] is False, "逐页条件记录")

    # 2) 四条件全开 + compose 树：五段全注入
    r2 = os.path.join(tmp, "p2"); mk_project(r2, via=True, dialog=True, functional=True, state=True, toolkit="compose-fact-tree")
    p = run(["--batch-id", "b1", "--round", "1"], r2)
    check(p.returncode == 0, "全条件批渲染 exit 0")
    s = json.loads(p.stdout.strip().splitlines()[-1])
    check(sorted(s["sections_included"]) == sorted(["NAV-compose", "B0.5-via-variant", "B0.6-dialog", "B1-data-state", "B4.5-dual-oracle"]), "五段全部注入")
    body = open(os.path.join(r2, s["out"]), encoding="utf-8").read()
    check("# B.4.5 功能点双 oracle 判定（dual-oracle）" in body and "BUSINESS_VERB_BAG" in body and "Compose 导航规则" in body, "注入的是原文正文")
    check(s["nav_mode"] == "compose", "nav_mode auto → compose")

    # 3) 仅 functional：只注 B4.5
    r3 = os.path.join(tmp, "p3"); mk_project(r3, functional=True)
    s = json.loads(run(["--batch-id", "b1", "--round", "0"], r3).stdout.strip().splitlines()[-1])
    check(s["sections_included"] == ["B4.5-dual-oracle"], "只带 functional_checks → 只注 B4.5")

    # 4) b_gaps 重派：retry_reason 自动缺省
    r4 = os.path.join(tmp, "p4"); mk_project(r4)
    s = json.loads(run(["--batch-id", "b1", "--round", "0", "--b-gaps", '[{"page":"HomeActivity","action":"补图"}]'], r4).stdout.strip().splitlines()[-1])
    body = open(os.path.join(r4, s["out"]), encoding="utf-8").read()
    check('retry_reason: "B 审核发现' in body and '"page": "HomeActivity"' in body, "b_gaps 重派槽位注入 + 缺省 retry_reason")

    # 5) 失败出口：条件段文件缺失 → exit 3；batch 不存在 → exit 2
    r5 = os.path.join(tmp, "p5"); mk_project(r5, functional=True)
    empty = os.path.join(tmp, "empty_sections"); os.makedirs(empty)
    p = run(["--batch-id", "b1", "--round", "0", "--sections-dir", empty], r5)
    check(p.returncode == 3 and "条件段文件缺失" in p.stderr, "需注入但段文件缺失 → exit 3（不静默降级）")
    p = run(["--batch-id", "nope", "--round", "0"], r5)
    check(p.returncode == 2, "batch 不存在 → exit 2")
    print(f"ALL PASSED ({PASSED} checks)")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
