"""next_walk.py 状态机：合成 $EW，按 §3 散文流程逐站验证动作序列（零设备、零应用常量）。"""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import next_walk as nw
import walk_timeline as wtl

T1, T2 = "trip_a_out", "trip_b_in"      # 任意名字：驱动只认计划里的先后顺序，不认 trip 名


def _plan():
    return {"walks": [
        {"walk_id": "walk_0_first", "trip_id": T1, "reset_before": "pm_clear", "chain_protected": True,
         "steps": [{"step": 1, "action": "coldstart", "to": "Root", "settles_capture": "Root"},
                   {"step": 2, "action": "tap", "from": "Root", "to": "PageA", "trigger": "go", "settles_capture": "PageA"}]},
        {"walk_id": "walk_1_main", "trip_id": T2,
         "steps": [{"step": 1, "action": "coldstart", "to": "Root"},
                   {"step": 2, "action": "tap", "from": "Root", "to": "PageB", "trigger": "b", "settles_capture": "PageB",
                    "safety": "stop_at_dialog"}]},
        {"walk_id": "walk_2_generation_X", "trip_id": None, "stop_if_settled": "X",
         "steps": [{"step": 1, "action": "coldstart", "to": "Root"}]},
    ]}


def _ew(tmp_path, with_review=True):
    root = tmp_path / "proj"
    ew = root / "spec" / "visual-verify" / "edgewalk"
    ew.mkdir(parents=True)
    (root / "spec" / "scenarios").mkdir(parents=True)
    (root / "spec" / "scenarios" / "login_android.yaml").write_text("steps: []")
    (root / "spec" / "toolkit-fact-tree.json").write_text("{}")
    json.dump(_plan(), open(ew / "walk_plan.json", "w"))
    (ew / "run_env.md").write_text("- EW: x\n- SCRIPTS: y\n")
    (ew / "project_rules.md").write_text("# 规则\n## 安全铁律\n- 绝不点确定\n")
    if with_review:
        (ew / "safety_review.md").write_text("已逐条核对，无补充")
    json.dump({"t0": 0, "coldstarts": [], "settled": {}, "targets": ["Root", "PageA", "PageB", "X"]}, open(ew / "ledger.json", "w"))
    return str(root), str(ew)


def _state(ew, walk_id, status=None, next_step=0, done_steps=(), ended_at=None, archived=False):
    st = {"walk_id": walk_id, "next_step": next_step, "done_steps": list(done_steps), "escalations": 0,
          "step_times": [{"step": 1, "ended_at": ended_at or time.time()}] if ended_at or done_steps else []}
    if status:
        st["status"] = status
    name = f"walk_exec_state.{walk_id}.json" if archived else "walk_exec_state.json"
    json.dump(st, open(os.path.join(ew, name), "w"))


def _decide(root, ew, **kw):
    return nw.decide(ew, root, os.path.join(root, "spec", "toolkit-fact-tree.json"),
                     kw.get("serial"), kw.get("package"), kw.get("login"), kw.get("apply", False))


def test_plan_missing_then_review_missing(tmp_path):
    root, ew = _ew(tmp_path, with_review=False)
    os.remove(os.path.join(ew, "walk_plan.json"))
    assert _decide(root, ew)["action"] == "plan"
    json.dump(_plan(), open(os.path.join(ew, "walk_plan.json"), "w"))
    assert _decide(root, ew)["action"] == "write_safety_review"


def test_first_dispatch_is_walk0_and_locks_then_waits(tmp_path):
    root, ew = _ew(tmp_path)
    out = _decide(root, ew)
    assert out["action"] == "dispatch_walk" and out["walk_id"] == "walk_0_first" and out["trip_id"] == T1
    assert os.path.isfile(out["prompt_file"]) and "walk_0_first" in open(out["prompt_file"]).read()
    assert os.path.isfile(os.path.join(ew, nw.LOCK))
    # 在飞：不派、不合并
    assert _decide(root, ew)["action"] == "wait_in_flight"
    # 交接报告缺字段 → 拒
    bad = tmp_path / "bad.json"; bad.write_text(json.dumps({"position": {}}))
    dest, err = nw.record_handoff(ew, str(bad))
    assert dest is None and "resume_step" in err
    good = tmp_path / "good.json"; good.write_text(json.dumps({"position": {"node": "PageA"}, "resume_step": 3, "observation_notes": ["n1"]}))
    dest, err = nw.record_handoff(ew, str(good))
    assert err is None and dest.endswith("walk_0_first.1.json") and not os.path.exists(os.path.join(ew, nw.LOCK))


def test_login_required_before_second_trip_and_order_gate(tmp_path):
    root, ew = _ew(tmp_path)
    # 树带账号态前置 → 后一 trip 需要登录建态（无前置的应用见 test_login_less_app_skips_run_login）
    json.dump({"pages": [{"id": "P", "preconditions": [{"kind": "login_required", "polarity": "required", "evidence": "x"}]}]},
              open(os.path.join(root, "spec", "toolkit-fact-tree.json"), "w"))
    os.utime(os.path.join(ew, "walk_plan.json"), None)        # 计划比树新（否则新鲜度闸会要求重出计划）
    _state(ew, "walk_0_first", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=1000.0)
    out = _decide(root, ew)
    assert out["action"] == "run_login" and out["trip_id"] == T2 and out["scenario"] == "login_android"
    assert "--trip " + T2 in out["cmd"] and "run_scenario_with_verify.py" in out["cmd"]   # 全 py 化后 trip 走参数不走 env（PowerShell 无 VAR=x cmd）
    # 登录事件落时间线后 → 派 walk_1
    wtl.mark(ew, "scenario:login_android", trip=T2)
    out = _decide(root, ew)
    assert out["action"] == "dispatch_walk" and out["walk_id"] == "walk_1_main" and out["trip_id"] == T2
    nw.clear_lock(ew)
    # 顺序闸：walk_0 未完成却已有登录事件 → blocked
    os.remove(os.path.join(ew, "walk_exec_state.json"))
    out = _decide(root, ew)
    assert out["action"] == "blocked" and out["blocked_on"] == "trip_order_violation"


def test_resume_in_progress_uses_latest_handoff(tmp_path):
    root, ew = _ew(tmp_path)
    _state(ew, "walk_0_first", next_step=1, done_steps=(1,), ended_at=1000.0)
    os.makedirs(os.path.join(ew, "handoffs"))
    hp = os.path.join(ew, "handoffs", "walk_0_first.1.json")
    json.dump({"walk_id": "walk_0_first", "position": {"node": "Root"}, "resume_step": 2, "device_residue": {"ime_open": True}}, open(hp, "w"))
    out = _decide(root, ew)
    assert out["action"] == "dispatch_walk" and out["walk_id"] == "walk_0_first" and out["resume_from"] == hp
    assert '"ime_open": true' in open(out["prompt_file"]).read()


def test_generation_walk_inherits_trip_and_judge_runs_in_parallel(tmp_path):
    root, ew = _ew(tmp_path)
    _state(ew, "walk_0_first", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=1000.0, archived=True)
    wtl.mark(ew, "scenario:login_android", trip=T2)
    _state(ew, "walk_1_main", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=2000.0)
    # 一条普查观测未判定
    gd = os.path.join(ew, "grounding", "PageB"); os.makedirs(gd)
    json.dump({"node": "PageB", "checks": [{"idx": 0, "name": "标题", "status": "ok", "outcome": "noop"},
                                           {"idx": 1, "name": "跳过的", "status": "skipped_in_plan"}]}, open(os.path.join(gd, "run_meta.json"), "w"))
    out = _decide(root, ew)
    assert out["action"] == "dispatch_walk" and out["walk_id"] == "walk_2_generation_X" and out["trip_id"] == T2
    j = out["also_dispatch_judge"]
    assert j["nodes"] == ["PageB"] and os.path.isfile(j["prompt_file"])
    body = open(j["prompt_file"]).read()
    assert "标题(idx=0,ok/noop)" in body and "跳过的" not in body and "不写任何文件" in body
    assert os.path.isfile(os.path.join(ew, "judge_snapshots", os.listdir(os.path.join(ew, "judge_snapshots"))[0], "PageB", "run_meta.json"))


def test_merge_judge_idempotent_and_refused_in_flight(tmp_path):
    root, ew = _ew(tmp_path)
    jp = tmp_path / "judge.json"
    jp.write_text(json.dumps([{"node": "PageB", "check_name": "标题", "check_idx": 0, "expected_android": "x", "android_trusted": True},
                              {"node": "PageB", "check_name": "缺字段"}]))
    res, err = nw.merge_judge(ew, str(jp))
    assert err is None and res == {"added": 1, "total": 1, "rejected": 1}
    res, err = nw.merge_judge(ew, str(jp))
    assert res["added"] == 0 and res["total"] == 1


def test_overrides_then_finalize_then_done(tmp_path):
    root, ew = _ew(tmp_path)
    _state(ew, "walk_0_first", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=1000.0, archived=True)
    wtl.mark(ew, "scenario:login_android", trip=T2)
    _state(ew, "walk_1_main", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=2000.0, archived=True)
    _state(ew, "walk_2_generation_X", status="walk_skipped_target_settled", next_step=0)
    json.dump([{"from": "Root", "to": "X", "status": "not_reproduced", "note": "入口不渲染"}], open(os.path.join(ew, "edge_results.json"), "w"))
    out = _decide(root, ew)
    assert out["action"] == "confirm_overrides" and "X" in out["unreached"]
    draft = json.load(open(out["draft"]))
    assert draft["X"]["_not_reproduced_notes"] == ["入口不渲染"] and draft["X"]["reason"].startswith("TODO")
    json.dump({"X": {"reason": "data_precondition_missing", "note": "…"}}, open(os.path.join(ew, "reason_overrides.json"), "w"))
    out = _decide(root, ew)
    assert out["action"] == "finalize" and out["trip_id"] == T1 and "--reason-overrides" in out["cmd"] and out["ran"] is False
    # 只有日志（闸红也会留日志）不算完成；成功标记 .ok 新于产物才算 → done
    time.sleep(0.05)
    for t in (T1, T2):
        open(os.path.join(ew, f"finalize_{t}.log"), "w").write("闸红")
    assert _decide(root, ew)["action"] == "finalize"
    for t in (T1, T2):
        open(os.path.join(ew, f"finalize_{t}.ok"), "w").write("{}")
    out = _decide(root, ew)
    assert out["action"] == "done"
    # 产物又变新（finalize 5.8 追加 walk 后执行器写了新状态）→ 再 finalize
    time.sleep(0.05)
    _state(ew, "walk_6_chain_sweep_Root", status="walk_done", next_step=1, done_steps=(1,), ended_at=3000.0, archived=True)
    assert _decide(root, ew)["action"] == "finalize"


def test_login_scenario_resolution(tmp_path):
    root, ew = _ew(tmp_path)
    assert nw.find_login_scenario(root)[0] == "login_android"
    # 名字含 login 但不是建态配方的一律排除（复核 e''）
    for n in ("login_check", "relogin", "oauth_login", "logout_android"):
        open(os.path.join(root, "spec", "scenarios", f"{n}.yaml"), "w").write("")
    assert nw.find_login_scenario(root)[0] == "login_android"
    open(os.path.join(root, "spec", "scenarios", "login.yaml"), "w").write("")
    assert nw.find_login_scenario(root)[0] == "login_android"          # 多候选时取含 android 的那个
    open(os.path.join(root, "spec", "scenarios", "login_android2.yml"), "w").write("")
    name, err = nw.find_login_scenario(root)
    assert name is None and "指名" in err
    assert nw.find_login_scenario(root, "custom")[0] == "custom"
    # run_env.md 冻结值优先于反查
    open(os.path.join(ew, "run_env.md"), "a").write("\n- login_scenario: `login_sms_x`\n")
    assert nw.find_login_scenario(root, None, ew)[0] == "login_sms_x"


def test_dynamic_walks_exempt_from_order_gate_and_first_trip_debt(tmp_path):
    root, ew = _ew(tmp_path)
    plan = _plan()
    plan["walks"].append({"walk_id": "walk_6_chain_sweep_Root", "trip_id": T1, "reset_before": "pm_clear",
                          "dynamic": True, "order_exempt": True, "steps": [{"step": 1, "action": "coldstart", "to": "Root"}]})
    json.dump(plan, open(os.path.join(ew, "walk_plan.json"), "w"))
    _state(ew, "walk_0_first", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=1000.0, archived=True)
    wtl.mark(ew, "scenario:login_android", trip=T2)
    _state(ew, "walk_1_main", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=2000.0, archived=True)
    led = json.load(open(os.path.join(ew, "ledger.json"))); led["settled"]["X"] = {"capture_meta": {"trip_id": T2}}
    json.dump(led, open(os.path.join(ew, "ledger.json"), "w"))
    out = _decide(root, ew)
    assert out["action"] == "dispatch_walk" and out["walk_id"] == "walk_6_chain_sweep_Root"   # 登录后回走首启链：豁免顺序闸
    nw.clear_lock(ew)
    assert nw.first_trip_debt(ew) == []                                                    # 动态走不算首 trip 的债


def test_first_trip_debt_lists_unfinished_first_trip_walks(tmp_path):
    root, ew = _ew(tmp_path)
    assert nw.first_trip_debt(ew) == ["walk_0_first"]
    _state(ew, "walk_0_first", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=1000.0)
    assert nw.first_trip_debt(ew) == []


def test_plan_stale_when_tree_newer_and_nothing_started(tmp_path):
    root, ew = _ew(tmp_path)
    time.sleep(0.05)
    open(os.path.join(root, "spec", "toolkit-fact-tree.json"), "w").write("{}")
    out = _decide(root, ew)
    assert out["action"] == "plan" and "tree 比计划新" in out["reason"]
    # 已有 walk 开走后不再因 tree 变新（finalize 会回写树）要求重出计划
    _state(ew, "walk_0_first", next_step=1, done_steps=(1,), ended_at=1000.0)
    assert _decide(root, ew)["action"] == "dispatch_walk"


def test_escalated_at_first_step_is_in_progress_with_packet_in_extras(tmp_path):
    root, ew = _ew(tmp_path)
    st = {"walk_id": "walk_0_first", "next_step": 0, "done_steps": [], "escalations": 1,
          "escalation": {"step": 1, "reason": "position_mismatch"}, "step_times": []}
    json.dump(st, open(os.path.join(ew, "walk_exec_state.json"), "w"))
    out = _decide(root, ew)
    assert out["action"] == "dispatch_walk" and "续走" in out["why"]
    body = open(out["prompt_file"]).read()
    assert "escalations/step1.json" in body and "position_mismatch" in body


def test_generation_walk_skipped_when_target_already_settled(tmp_path):
    root, ew = _ew(tmp_path)
    _state(ew, "walk_0_first", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=1000.0, archived=True)
    wtl.mark(ew, "scenario:login_android", trip=T2)
    _state(ew, "walk_1_main", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=2000.0)
    led = json.load(open(os.path.join(ew, "ledger.json")))
    led["settled"]["X"] = {"capture_meta": {"trip_id": T2}}
    json.dump(led, open(os.path.join(ew, "ledger.json"), "w"))
    out = _decide(root, ew)
    assert out["action"] in ("confirm_overrides", "finalize")           # 生成走不再派：目标已结账


def test_login_less_app_skips_run_login(tmp_path):
    root, ew = _ew(tmp_path)
    _state(ew, "walk_0_first", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=1000.0)
    # 树无任何登录/会员类前置（空树）→ 后一 trip 免登录，直接派 walk_1
    out = _decide(root, ew)
    assert out["action"] == "dispatch_walk" and out["walk_id"] == "walk_1_main"
    nw.clear_lock(ew)
    # 树有 login_required → 仍要求登录
    json.dump({"pages": [{"id": "P", "preconditions": [{"kind": "login_required", "polarity": "required", "evidence": "x"}]}]},
              open(os.path.join(root, "spec", "toolkit-fact-tree.json"), "w"))
    out = _decide(root, ew)
    assert out["action"] == "run_login"


def test_explicit_trip_build_scenario_runs_even_without_login_kinds(tmp_path):
    root, ew = _ew(tmp_path)
    open(os.path.join(ew, "run_env.md"), "a").write("\n- trip_build_scenario: `seed_local_feed`\n")
    _state(ew, "walk_0_first", status="walk_done", next_step=2, done_steps=(1, 2), ended_at=1000.0)
    out = _decide(root, ew)
    assert out["action"] == "run_login" and out["scenario"] == "seed_local_feed"
    # 建态事件（trip_built:*）落时间线后 → 派 walk_1
    wtl.mark(ew, "trip_built:" + T2, trip=T2, scenario="seed_local_feed")
    out = _decide(root, ew)
    assert out["action"] == "dispatch_walk" and out["walk_id"] == "walk_1_main"
