#!/usr/bin/env python3
"""判读债链路（C1）+ 跨 trip 采集产物归档（C2）—— 零设备、零应用常量。

C1 病：settle 撞 exit 16 把证据入池、债挂 pending_bindings，但 ①walk_finalize 从不查这个池
       ②驱动算判读任务只 glob run_meta ③未达清单把它归因成 nav_unreachable。三处断点全测。
C2 病：同节点被后一 trip 复访时 shots/<node>.* 被整份覆写，前一 trip 的基线被写成后一 trip 的画面。
"""
import json, os, subprocess, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))
SC = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, SC)
import next_walk as nw
import walk_ledger as wl

PY = sys.executable
TRIP_A, TRIP_B = "trip_x_out", "trip_y_in"      # 任意名字：全链路只认计划里的先后，不认 trip 名
NODE = "SomeListFragment"


# ── 合成产物 ────────────────────────────────────────────────────────────────
def _tree():
    return {"pages": [{"id": "Root", "inbound_triggers": []},
                      {"id": NODE, "inbound_triggers": [],
                       "functional_checks": [{"name": "c1", "grounded_by": "x"}]}],
            "fragments": [], "dialogs": []}


def _proj(tmp_path, walks_done=True):
    root = tmp_path / "proj"
    ew = root / "spec" / "visual-verify" / "edgewalk"
    ew.mkdir(parents=True)
    json.dump(_tree(), open(root / "spec" / "toolkit-fact-tree.json", "w"))
    plan = {"targets": ["Root", NODE], "orphans": [],
            "walks": [{"walk_id": "walk_0", "trip_id": TRIP_A,
                       "steps": [{"step": 1, "action": "coldstart", "to": "Root"}]}]}
    json.dump(plan, open(ew / "walk_plan.json", "w"))
    json.dump({"t0": 0, "coldstarts": [], "settled": {"Root": {"trip": TRIP_A}},
               "targets": ["Root", NODE]}, open(ew / "ledger.json", "w"))
    json.dump([], open(ew / "edge_results.json", "w"))
    json.dump([], open(ew / "needs_retap.json", "w"))
    (ew / "safety_review.md").write_text("已逐条核对，无补充")
    (ew / "run_env.md").write_text("- EW: x\n")
    (ew / "project_rules.md").write_text("# 规则\n## 安全铁律\n- 绝不点确定\n")
    if walks_done:
        json.dump({"walk_id": "walk_0", "status": "walk_done", "next_step": 9},
                  open(ew / "walk_exec_state.json", "w"))
    return str(root), str(ew)


def _debt(ew, node=NODE, trip=TRIP_B, **kw):
    shot = os.path.join(ew, "pending_shots", f"{node}__pending_1.png")
    dump = os.path.join(ew, "pending_shots", f"{node}__pending_1.android.xml")
    os.makedirs(os.path.dirname(shot), exist_ok=True)
    open(shot, "w").write("PENDING-PNG")
    open(dump, "w").write("<hierarchy/>")
    e = {"node": node, "trip": trip, "via": "Root--[auto:transition]-->",
         "classified": "uncertain", "why": "expected 弱命中（共享id/宿主漂移）——需看图判读",
         "current_activity": "pkg/HostActivity", "pending_shot": shot, "pending_dump": dump,
         "exit": 16, "verdict": None}
    e.update(kw)
    json.dump([e], open(os.path.join(ew, "pending_bindings.json"), "w"), ensure_ascii=False)
    return e


def _finalize(root, ew, *extra, trip=TRIP_B):
    return subprocess.run([sys.executable, os.path.join(SC, "walk_finalize.py"), "--trip", trip,
                           "--dir", ew, "--tree", os.path.join(root, "spec", "toolkit-fact-tree.json"),
                           "--project-root", root, *extra],
                          capture_output=True, text=True, errors="replace", cwd=root)
                          # errors=replace：finalize 日志混过非 UTF-8 字节（0910 实爆）


def _decide(root, ew, apply=False):
    return nw.decide(ew, root, os.path.join(root, "spec", "toolkit-fact-tree.json"),
                     None, None, None, apply)


# ── C1-0 判据本身（shell 闸 / 驱动 / 收尾账共用一个函数）────────────────────
def test_binding_debt_predicate_three_states():
    u, a = wl.binding_debt([{"node": "A"},                                   # 未判
                            {"node": "B", "verdict": "bind_as", "applied": False},   # 已判待结
                            {"node": "C", "verdict": "reject", "applied": True}])    # 已结
    assert [e["node"] for e in u] == ["A"] and [e["node"] for e in a] == ["B"]


def test_legacy_entry_without_applied_key_is_not_debt():
    """老产物（bind-from-evidence 改造前结的债）没有 applied 键 —— 一律不算债，行为不变。"""
    u, a = wl.binding_debt([{"node": "A", "verdict": "bind_as"}])
    assert not u and not a
    assert wl.binding_nodes([{"node": "A", "verdict": "bind_as"}]) == set()


# ── C1-1 finalize 2.6 闸 ───────────────────────────────────────────────────
def test_finalize_gate_reds_on_unjudged_binding_debt(tmp_path):
    root, ew = _proj(tmp_path)
    _debt(ew)
    r = _finalize(root, ew, "--dry-run")
    assert r.returncode == 20, r.stdout + r.stderr
    err = r.stderr
    assert NODE in err and "bind-from-evidence" in err and "--accept-binding-debt" in err
    assert "3. 树反哺" not in r.stdout          # 真拦：没往下反哺


def test_finalize_gate_reds_on_judged_but_unapplied(tmp_path):
    """结论回写了却没走 bind-from-evidence：证据还在池里没落地，同样是债。"""
    root, ew = _proj(tmp_path)
    _debt(ew, verdict="bind_as", applied=False)
    r = _finalize(root, ew, "--dry-run")
    assert r.returncode == 20 and "已判待结" in r.stderr


def test_finalize_gate_green_when_debt_settled(tmp_path):
    root, ew = _proj(tmp_path)
    _debt(ew, verdict="reject", applied=True)
    r = _finalize(root, ew, "--dry-run")
    assert "判读债已结清 ✓" in r.stdout and "3. 树反哺" in r.stdout


def test_finalize_no_pending_file_is_green(tmp_path):
    """老项目根本没有 pending_bindings.json —— 放行，不新增红。"""
    root, ew = _proj(tmp_path)
    r = _finalize(root, ew, "--dry-run")
    assert "本轮没挂过判读债" in r.stdout and "3. 树反哺" in r.stdout


def test_finalize_gate_reds_on_unreadable_pool(tmp_path):
    """池在却读不出来 —— 「对不了账」本身就是红，绝不能当成「没有债」放行。"""
    root, ew = _proj(tmp_path)
    open(os.path.join(ew, "pending_bindings.json"), "w").write("{ 坏掉的 json")
    r = _finalize(root, ew, "--dry-run")
    assert r.returncode == 20 and "读不出来" in r.stderr and "3. 树反哺" not in r.stdout
    wl.BASE = ew
    assert any("不可读" in p for p in wl.finalize_account(None, None, root)["pending"])


def test_accept_binding_debt_is_explicit_and_leaves_marker(tmp_path):
    root, ew = _proj(tmp_path)
    _debt(ew)
    r = _finalize(root, ew, "--accept-binding-debt", "--walk-id", "walk_test")
    assert "带 1 笔判读债反哺" in r.stdout, r.stdout + r.stderr
    t = json.load(open(os.path.join(root, "spec", "toolkit-fact-tree.json")))
    m = t["_phase_markers"]["walk_test"]["binding_debt"]
    assert m["count"] == 1 and m["unjudged"] == [NODE] and "别把它们当不可达" in m["note"]


# ── C1-2 驱动把判读债并进判读作用域 ─────────────────────────────────────────
def test_driver_puts_binding_debt_in_judge_scope(tmp_path):
    root, ew = _proj(tmp_path)
    e = _debt(ew)
    out = _decide(root, ew)
    assert out["action"] == "dispatch_judge" and out["binding_nodes"] == [NODE]
    p = open(out["prompt_file"], encoding="utf-8").read()
    assert e["pending_shot"] in p and e["pending_dump"] in p          # 判读拿证据判，不用回设备
    assert "bind_as|reject|new_node" in p and '"kind": "binding"' in p


def test_dispatch_walk_carries_binding_debt_as_parallel_judge(tmp_path):
    """行走还没派完时，判读债跟着 also_dispatch_judge 一起走（零设备，可并行）。"""
    root, ew = _proj(tmp_path, walks_done=False)
    _debt(ew)
    out = _decide(root, ew)
    assert out["action"] == "dispatch_walk"
    assert out["also_dispatch_judge"]["binding_nodes"] == [NODE]


# ── C1-3 判读结论回写 + 结债 ────────────────────────────────────────────────
def test_merge_judge_routes_binding_rows_out_of_check_space(tmp_path):
    root, ew = _proj(tmp_path)
    _debt(ew)
    j = tmp_path / "judge.json"
    j.write_text(json.dumps([{"kind": "binding", "node": NODE, "trip": TRIP_B,
                              "verdict": "bind_as", "note": "图就是它本人"}]), encoding="utf-8")
    res, err = nw.merge_judge(ew, str(j))
    assert err is None and res["added"] == 0 and res["bindings"]["judged"] == 1
    assert json.load(open(os.path.join(ew, "grounding_results.json"))) == []   # 不进 check 空间
    e = json.load(open(os.path.join(ew, "pending_bindings.json")))[0]
    assert e["verdict"] == "bind_as" and e["applied"] is False and e["judged_by"] == "judge_merge"
    # 幂等：再合一次不重复改判
    res2, _ = nw.merge_judge(ew, str(j))
    assert res2["bindings"] == dict(res2["bindings"], judged=0, skipped=1)


def test_merge_judge_still_takes_check_rows(tmp_path):
    root, ew = _proj(tmp_path)
    j = tmp_path / "judge.json"
    j.write_text(json.dumps([{"node": NODE, "check_name": "c1", "check_idx": 0,
                              "expected_android": "实测一句话", "android_trusted": True}]), encoding="utf-8")
    res, err = nw.merge_judge(ew, str(j))
    assert err is None and res["added"] == 1 and "bindings" not in res


def test_driver_settles_binding_debt_then_reopens_finalize(tmp_path):
    root, ew = _proj(tmp_path)
    _debt(ew, verdict="bind_as", applied=False)
    ok = os.path.join(ew, f"finalize_{TRIP_B}.ok")
    open(ok, "w").write("{}")
    dry = _decide(root, ew)
    assert dry["action"] == "settle_binding_debt" and dry["ran"] is False
    assert "bind-from-evidence" in dry["cmds"][0] and NODE in dry["cmds"][0]
    out = _decide(root, ew, apply=True)
    assert out["action"] == "settle_binding_debt" and out["ran"] is True and not out["failed"]
    led = json.load(open(os.path.join(ew, "ledger.json")))
    assert NODE in led["settled"] and led["settled"][NODE]["trip"] == TRIP_B
    assert open(os.path.join(ew, "shots", f"{NODE}.png")).read() == "PENDING-PNG"
    e = json.load(open(os.path.join(ew, "pending_bindings.json")))[0]
    assert e["applied"] is True
    assert not os.path.exists(ok)          # 撤 finalize 标记：新绑定的基线必须重新落位


def test_bind_from_evidence_accepts_already_judged_entry(tmp_path):
    """判读回写 verdict 之后再来结债，不能被「无未判条目」挡在门外。"""
    root, ew = _proj(tmp_path)
    _debt(ew, verdict="reject", applied=False)
    r = subprocess.run([PY, os.path.join(SC, "walk_ledger.py"), "--dir", ew, "bind-from-evidence",
                        "--node", NODE, "--tree", os.path.join(root, "spec", "toolkit-fact-tree.json")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "verdict=reject" in r.stdout
    e = json.load(open(os.path.join(ew, "pending_bindings.json")))[0]
    assert e["applied"] is True and NODE not in json.load(open(os.path.join(ew, "ledger.json")))["settled"]


# ── C1-4 未达/归因口径 ──────────────────────────────────────────────────────
def test_unreached_split_open_vs_judged(tmp_path):
    root, ew = _proj(tmp_path)
    _debt(ew)
    assert nw.unreached(ew, split=True) == ([], [NODE], [])
    _debt(ew, verdict="reject", applied=True)
    assert nw.unreached(ew, split=True) == ([], [], [NODE])


def test_draft_overrides_prefills_binding_pending(tmp_path):
    root, ew = _proj(tmp_path)
    _debt(ew)
    _, draft = nw.draft_overrides(ew)
    assert draft[NODE]["reason"] == "binding_pending"
    assert "不是不可达" in draft[NODE]["note"] and "bind-from-evidence" in draft[NODE]["note"]
    assert draft[NODE]["_binding_pending"]["trip"] == TRIP_B


def test_confirm_overrides_lists_binding_judged_separately(tmp_path):
    root, ew = _proj(tmp_path)
    _debt(ew, verdict="reject", applied=True)
    out = _decide(root, ew)
    assert out["action"] == "confirm_overrides"
    assert out["unreached"] == [] and out["unreached_binding_judged"] == [NODE]


def test_blocked_ticket_says_binding_pending_not_nav_unreachable(tmp_path):
    root, ew = _proj(tmp_path)
    _debt(ew, trip=TRIP_A)
    r = subprocess.run([PY, os.path.join(SC, "walk_place_baselines.py"), "--dir", ew,
                        "--trip", TRIP_A, "--project-root", root, "--no-resize"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    body = open(os.path.join(root, "spec", "fix", "baseline-blocked",
                             f"BLOCKED_baseline_{NODE}_{TRIP_A}.md")).read()
    assert body.splitlines()[1] == "reason: binding_pending"
    assert "证据已采、绑定待判" in body and "bind-from-evidence" in body
    # 自愈队列是给 trip 错配用的，绑定待判不该进
    assert not os.path.exists(os.path.join(root, "spec", "visual-verify", "_trip_retry_queue.json"))


def test_blocked_ticket_unchanged_without_binding_debt(tmp_path):
    root, ew = _proj(tmp_path)
    r = subprocess.run([PY, os.path.join(SC, "walk_place_baselines.py"), "--dir", ew,
                        "--trip", TRIP_A, "--project-root", root, "--no-resize"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    body = open(os.path.join(root, "spec", "fix", "baseline-blocked",
                             f"BLOCKED_baseline_{NODE}_{TRIP_A}.md")).read()
    assert body.splitlines()[1] == "reason: nav_unreachable"


# ── C2 跨 trip 复访归档 ─────────────────────────────────────────────────────
def _fake_capture(shots, png_body, xml_body, trip):
    def run(cmd, *a, **kw):
        os.makedirs(shots, exist_ok=True)
        open(os.path.join(shots, f"{NODE}.png"), "w").write(png_body)
        open(os.path.join(shots, f"{NODE}.android.xml"), "w").write(xml_body)
        return types.SimpleNamespace(returncode=0, stderr="",
                                     stdout=json.dumps({"page_id": NODE, "trip_id": trip}))
    return run


def _settle(monkeypatch, root, ew, trip, png="NEW", xml="<new/>"):
    shots = os.path.join(ew, "shots")
    # 只替 walk_ledger 名字空间里的 subprocess（patch 模块对象上的 run 会污染本测试自己起的子进程）
    monkeypatch.setattr(wl, "subprocess", types.SimpleNamespace(run=_fake_capture(shots, png, xml, trip)))
    monkeypatch.setattr(wl, "top_activity", lambda: "HostActivity")
    monkeypatch.setattr(sys, "argv", ["walk_ledger.py", "--dir", ew, "settle", "--node", NODE,
                                      "--via", "Root--[x]-->", "--tree",
                                      os.path.join(root, "spec", "toolkit-fact-tree.json"),
                                      "--trip", trip, "--pkg", "p", "--launcher", "L"])
    wl.main()


def _seed_shots(ew, png="OLD", xml="<old/>"):
    shots = os.path.join(ew, "shots")
    os.makedirs(shots, exist_ok=True)
    open(os.path.join(shots, f"{NODE}.png"), "w").write(png)
    open(os.path.join(shots, f"{NODE}.android.xml"), "w").write(xml)
    return shots


def _seed_settled(ew, trip, legacy=False):
    led = json.load(open(os.path.join(ew, "ledger.json")))
    rec = {"via": "Root--[x]-->", "mode": "walk", "capture": "verified",
           "capture_meta": {"page_id": NODE, "trip_id": trip}}
    if not legacy:
        rec["trip"] = trip
    led["settled"][NODE] = rec
    json.dump(led, open(os.path.join(ew, "ledger.json"), "w"))


def test_cross_trip_settle_archives_previous_pair(tmp_path, monkeypatch):
    root, ew = _proj(tmp_path)
    shots = _seed_shots(ew)
    _seed_settled(ew, TRIP_A, legacy=True)          # 老记录只有 capture_meta.trip_id
    _settle(monkeypatch, root, ew, TRIP_B)
    arch = os.path.join(shots, "_bytrip", TRIP_A)
    assert open(os.path.join(arch, f"{NODE}.png")).read() == "OLD"           # 前一 trip 的图保住
    assert open(os.path.join(arch, f"{NODE}.android.xml")).read() == "<old/>"
    assert open(os.path.join(shots, f"{NODE}.png")).read() == "NEW"          # 本 trip 的图照常落 shots/
    led = json.load(open(os.path.join(ew, "ledger.json")))
    assert led["settled"][NODE]["trip"] == TRIP_B
    assert led["settled"][NODE]["archived_prior"]["trip"] == TRIP_A
    old = led["settled_by_trip"][TRIP_A][NODE]                              # 前一 trip 的结账记录留档
    assert old["capture_meta"]["shots_archived"]["dir"] == arch


def test_same_trip_resettle_does_not_archive(tmp_path, monkeypatch):
    root, ew = _proj(tmp_path)
    shots = _seed_shots(ew)
    _seed_settled(ew, TRIP_B)
    _settle(monkeypatch, root, ew, TRIP_B)
    assert not os.path.isdir(os.path.join(shots, "_bytrip"))
    assert "settled_by_trip" not in json.load(open(os.path.join(ew, "ledger.json")))


def test_first_settle_of_node_does_not_archive(tmp_path, monkeypatch):
    root, ew = _proj(tmp_path)
    _settle(monkeypatch, root, ew, TRIP_A)
    assert not os.path.isdir(os.path.join(ew, "shots", "_bytrip"))


def _place(root, ew, trip):
    return subprocess.run([PY, os.path.join(SC, "walk_place_baselines.py"), "--dir", ew,
                           "--trip", trip, "--project-root", root, "--no-resize"],
                          capture_output=True, text=True)


def test_place_baselines_prefers_current_trip_archive(tmp_path, monkeypatch):
    root, ew = _proj(tmp_path)
    _seed_shots(ew)
    _seed_settled(ew, TRIP_A)
    _settle(monkeypatch, root, ew, TRIP_B)            # 复访：shots/ 被写成 TRIP_B 的画面
    r = _place(root, ew, TRIP_A)
    assert json.loads(r.stdout)["placed_from_archive"] == [NODE]
    base = os.path.join(root, "spec", "visual-verify", "screenshots", "android", TRIP_A, f"{NODE}.png")
    assert open(base).read() == "OLD"                 # 落的是登出态那张，不是复访图
    assert open(base.replace(".png", ".android.xml")).read() == "<old/>"
    r2 = _place(root, ew, TRIP_B)                     # 本 trip 无归档 → 回落 shots/
    assert json.loads(r2.stdout)["placed_from_archive"] == []
    b2 = os.path.join(root, "spec", "visual-verify", "screenshots", "android", TRIP_B, f"{NODE}.png")
    assert open(b2).read() == "NEW"


def test_place_baselines_legacy_project_unchanged(tmp_path):
    """没有 _bytrip 归档的老项目：照旧从 shots/ 落位（含旧裸采集的 安全名 + .xml 命名）。"""
    root, ew = _proj(tmp_path)
    shots = os.path.join(ew, "shots"); os.makedirs(shots)
    open(os.path.join(shots, f"{NODE}.png"), "w").write("LEGACY")
    open(os.path.join(shots, f"{NODE}.xml"), "w").write("<legacy/>")
    _seed_settled(ew, TRIP_A, legacy=True)
    r = _place(root, ew, TRIP_A)
    out = json.loads(r.stdout)
    assert out["placed"] == [NODE] and out["placed_from_archive"] == []
    d = os.path.join(root, "spec", "visual-verify", "screenshots", "android", TRIP_A)
    assert open(os.path.join(d, f"{NODE}.png")).read() == "LEGACY"
    assert open(os.path.join(d, f"{NODE}.android.xml")).read() == "<legacy/>"


def test_finalize_account_no_false_stale_when_archive_used(tmp_path, monkeypatch):
    """归档落位后，收尾账不能因为 shots/ 里那份更新（是别的 trip 的复访图）就报 stale。"""
    root, ew = _proj(tmp_path)
    _seed_shots(ew)
    _seed_settled(ew, TRIP_A)
    _settle(monkeypatch, root, ew, TRIP_B)
    _place(root, ew, TRIP_A)
    wl.BASE = ew
    acc = wl.finalize_account(None, TRIP_A, root)
    assert acc["capture_stale"] == 0 and not [p for p in acc["pending"] if "旧图占位" in p]
    assert acc["capture_placed"] == 1
