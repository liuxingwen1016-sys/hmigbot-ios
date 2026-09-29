"""walk_exec 通用规则闸单测（2026-09-09 B1~B9）

铁律：全部用合成计划 + 合成 dump 字符串 + 假设备（FakeDev），**绝不触碰 adb / 模拟器**。
计划字段一律走契约名（step.action/safety/gate/suspect、walk.trip_id/stop_if_settled、
sentinels[].verify_signal），断言里不出现任何真实 app 的页名/控件名。
"""
import json, os, sys, types
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import walk_exec as we  # noqa: E402


# ── 测试替身 ────────────────────────────────────────────────────────────────
class FakeDev:
    """假设备：dump/activity 由脚本给定，所有动作只记账。dumps 用完后恒返回最后一条。"""

    def __init__(self, dumps=None, activity="com.x.HomeActivity", pkg="com.x"):
        self.dumps = list(dumps or [""])
        self.act, self.pkg = activity, pkg
        self.shell_log, self.taps, self.shots = [], [], []
        self.backs = 0
        self.kbd = False

    def dump(self):
        return self.dumps.pop(0) if len(self.dumps) > 1 else self.dumps[0]

    def current_activity(self):
        return self.act, self.pkg

    def shell(self, cmd, timeout=30):
        self.shell_log.append(cmd)
        return ""

    def screenshot(self, path):
        self.shots.append(path)

    def tap(self, x, y):
        self.taps.append((x, y))

    def back(self):
        self.backs += 1

    def keyboard_shown(self):
        return self.kbd

    def dismiss_keyboard(self):
        pass

    def launch(self, pkg):
        pass


@pytest.fixture
def ew(tmp_path):
    """$EW 目录。必须是子目录——时间线文件按契约落在 $EW 的**上一级**，
    直接拿 pytest 的 tmp_path 当 $EW 会让用例之间串味。"""
    d = tmp_path / "edgewalk"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _reset_ui_words():
    """UI_WORDS 是模块全局：每个用例跑完复位成默认，避免 B9 覆盖串味。"""
    yield
    we.load_ui_words("/nonexistent-dir-for-reset")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(we.time, "sleep", lambda *_a, **_k: None)


def mk_args(d, walk="w1", **kw):
    a = types.SimpleNamespace(
        dir=str(d), walk=walk, serial="fake-serial", package="com.x", tree=None,
        device_state="trip_1", launcher="com.x.Main", ad_profile=None,
        resume=False, assume_at=None, skip_step=None, skip_reason="", mark_step_done=None,
        allow_side_effects=False, allow_trip_backtrack="", no_grounding=True, no_blackbox=True,
        blackbox_out="bb", blackbox_budget=5, max_steps=None, dry_run=False)
    for k, v in kw.items():
        setattr(a, k, v)
    return a


def write_plan(d, walks, sentinels=None):
    (d / "walk_plan.json").write_text(
        json.dumps({"walks": walks, "sentinels": sentinels or {}}, ensure_ascii=False), encoding="utf-8")


def write_ledger(d, settled=None):
    (d / "ledger.json").write_text(json.dumps(
        {"t0": 1.0, "coldstarts": [], "targets": [], "settled": settled or {}}, ensure_ascii=False),
        encoding="utf-8")


def mk_exec(d, dev=None, **kw):
    ex = we.Exec(mk_args(d, **kw))
    ex.dev = dev or FakeDev()
    return ex


def wrap(inner, w=1080, h=1920):
    """把节点串包成合法 uiautomator dump（extract_clickables 走 ET.fromstring，必须单根合法）。
    根节点 bounds 同时是 visible_in_viewport 的视口。"""
    return f'<hierarchy rotation="0"><node bounds="[0,0][{w},{h}]">{inner}</node></hierarchy>'


def esc_of(d):
    return json.load(open(d / "walk_exec_state.json"))["escalation"]


def last_edge(d):
    return json.load(open(d / "edge_results.json"))[-1]


# ── B1 trip 顺序闸 ──────────────────────────────────────────────────────────
TRIP_WALKS = [{"walk_id": "w0", "trip_id": "trip_a", "steps": [{"step": 1, "action": "note", "to": "P"}]},
              {"walk_id": "w1", "trip_id": "trip_b", "steps": [{"step": 1, "action": "note", "to": "P"}]}]


def test_b1_refuses_when_later_trip_already_settled(ew, capsys):
    write_plan(ew, TRIP_WALKS)
    write_ledger(ew, {"P": {"via": "x", "capture_meta": {"trip_id": "trip_b"}}})
    with pytest.raises(SystemExit) as e:
        mk_exec(ew, walk="w0").run()
    assert e.value.code == 3
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["status"] == "refused" and out["reason"] == "trip_order_violation"
    assert out["walk_trip"] == "trip_a" and out["later_trip_seen"] == "trip_b" and "复位" in out["hint"]


def test_b1_refuses_first_trip_after_login_timeline(ew, capsys):
    write_plan(ew, TRIP_WALKS)
    write_ledger(ew)
    (ew.parent / "android_walk_timeline.jsonl").write_text(
        '{"phase": "scenario_login_ok", "epoch": 1}\n', encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        mk_exec(ew, walk="w0").run()
    assert e.value.code == 3
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["later_trip_seen"].startswith("timeline:")
    # 登录点只挡「序号 0 的 trip」，后一 trip 照跑
    mk_exec(ew, walk="w1")._check_trip_order()


def test_b1_backtrack_flag_allows_and_records_reason(ew):
    write_plan(ew, TRIP_WALKS)
    write_ledger(ew, {"P": {"capture_meta": {"trip_id": "trip_b"}}})
    ex = mk_exec(ew, walk="w0", allow_trip_backtrack="已 pm clear + 换测试账号，见 notes/reset.log")
    ex._check_trip_order()                                   # 不抛 = 放行
    assert any("allow-trip-backtrack" in n for n in ex.state["notes"])
    assert any("reset.log" in n for n in ex.state["notes"])


def test_b1_later_trip_and_no_trip_id_walks_pass(ew):
    """后一个 trip 自己跑、以及无 trip_id 的走（深链/生成链），都不受此闸约束。"""
    write_plan(ew, TRIP_WALKS + [{"walk_id": "w2", "steps": [{"step": 1, "action": "note", "to": "P"}]}])
    write_ledger(ew, {"P": {"capture_meta": {"trip_id": "trip_b"}}})
    mk_exec(ew, walk="w1")._check_trip_order()
    mk_exec(ew, walk="w2")._check_trip_order()


# ── B2 type 动作 ───────────────────────────────────────────────────────────
def test_b2_input_text_arg_ascii_and_space():
    assert we.input_text_arg("hello world") == ("hello world", "hello%sworld")
    assert we.input_text_arg("abc") == ("abc", "abc")
    # 非 ASCII / 空 → 中性默认串（adb input text 吃不下中文，实测丢字）
    assert we.input_text_arg("测试文案")[0] == we.DEFAULT_INPUT_TEXT
    assert we.input_text_arg(None) == (we.DEFAULT_INPUT_TEXT, "test%sinput%s1")


def test_b2_do_type_taps_types_and_verifies(ew):
    step = {"step": 1, "action": "type", "from": "P", "to": "P", "view_id": "com.x:id/et_field",
            "text": "hello world", "precondition_kind": "input_required"}
    write_plan(ew, [{"walk_id": "w1", "steps": [step]}])
    before = wrap('<node resource-id="com.x:id/et_field" text="" clickable="false" bounds="[0,100][400,200]"/>')
    after = wrap('<node resource-id="com.x:id/et_field" text="hello world" clickable="false" bounds="[0,100][400,200]"/>')
    dev = FakeDev([before, after])
    dev.kbd = True                                            # 键盘弹起 → 必须按一次 BACK 收掉
    ex = mk_exec(ew, dev=dev)
    ex.do_type(step)
    assert dev.taps == [(200, 150)] and dev.backs == 1        # 不限 clickable 也能定位输入框
    assert "input text hello%sworld" in dev.shell_log
    assert any("type et_field" in n for n in ex.state["notes"])


def test_b2_do_type_escalates_on_missing_target_and_failed_input(ew):
    step = {"step": 1, "action": "type", "from": "P", "to": "P", "view_id": "et_field", "text": None}
    write_plan(ew, [{"walk_id": "w1", "steps": [step]}])
    empty = wrap('<node resource-id="com.x:id/other" bounds="[0,0][10,10]"/>')
    with pytest.raises(SystemExit) as e:
        mk_exec(ew, dev=FakeDev([empty])).do_type(step)
    assert e.value.code == 30 and esc_of(ew)["reason"] == "input_target_not_found"

    box = wrap('<node resource-id="com.x:id/et_field" text="" clickable="false" bounds="[0,0][10,10]"/>')
    with pytest.raises(SystemExit):
        mk_exec(ew, dev=FakeDev([box, box])).do_type(step)    # 回读仍为空 → input_failed
    assert esc_of(ew)["reason"] == "input_failed"


# ── B3 计划内门步 / gate_pass ────────────────────────────────────────────────
GATE_XML = wrap('<node resource-id="com.x:id/tv_body" text="服务协议与隐私政策" clickable="false" bounds="[0,0][900,300]"/>'
                '<node resource-id="com.x:id/btn_agree" text="同意并继续" clickable="true" bounds="[0,400][400,500]"/>')


def test_b3_gate_pass_taps_whitelisted_control_then_verifies(ew):
    step = {"step": 1, "action": "gate_pass", "from": "GateDlg", "to": "P"}
    write_plan(ew, [{"walk_id": "w1", "steps": [step]}],
               sentinels={"P": {"kind": "activity_suffix", "value": "HomeActivity"}})
    ex = mk_exec(ew, dev=FakeDev([GATE_XML]))
    ex.do_gate_pass(step)
    assert ex.dev.taps == [(200, 450)]
    assert ex.state["gates"][-1]["via"] == "gate_pass" and ex.state["gates"][-1]["rid"] == "btn_agree"


def test_b3_gate_pass_unknown_escalates_without_guessing(ew):
    step = {"step": 1, "action": "gate_pass", "from": "GateDlg", "to": "P"}
    write_plan(ew, [{"walk_id": "w1", "steps": [step]}])
    plain = wrap('<node resource-id="com.x:id/btn_x" text="下一步" clickable="true" bounds="[0,0][10,10]"/>')
    ex = mk_exec(ew, dev=FakeDev([plain]))
    with pytest.raises(SystemExit) as e:
        ex.do_gate_pass(step)
    assert e.value.code == 30 and ex.dev.taps == []           # 选不出放行控件就**不猜**
    assert esc_of(ew)["reason"] == "gate_pass_unknown"


def test_b3_b8_gate_tap_step_settles_as_dialog_and_keeps_post_frame(ew, monkeypatch):
    """gate:true 的 tap 步：不调放行器、门目标是 dialog 节点时按 dialog 直接结账（非弹窗门走正常结账，2026-09-09 晚收敛）、门上不普查，并留 _post 证据帧（B8）。"""
    calls = []
    monkeypatch.setattr(we, "choose_gate_control", lambda xml: calls.append(1) or None)
    step = {"step": 1, "action": "tap", "from": "P", "to": "Host$GateDlg", "trigger": "打开协议",
            "gate": True, "static_rid": "btn_open", "settles_capture": "Host$GateDlg"}
    write_plan(ew, [{"walk_id": "w1", "steps": [step]}],
               sentinels={"P": {"kind": "activity_suffix", "value": "HomeActivity"},
                          "Host$GateDlg": {"kind": "resource_id_unique", "value": ["tv_body"], "hosts": []}})
    write_ledger(ew)
    src = wrap('<node resource-id="com.x:id/btn_open" text="打开协议" clickable="true" bounds="[0,0][200,100]"/>')
    ex = mk_exec(ew, dev=FakeDev([src, GATE_XML]))
    ex.do_tap(step)
    assert calls == []                                        # 计划内门步绝不被机械放行掉
    assert json.load(open(ew / "ledger.json"))["settled"]["Host$GateDlg"]["capture"] == "dialog_direct"
    edge = last_edge(ew)
    assert edge["gate"] is True and edge["evidence_post"].endswith("_post.png")
    assert edge["evidence_post"] in ex.dev.shots and edge["pre_evidence"] in ex.dev.shots
    assert ex.state["sweep_skipped_gate"] == ["Host$GateDlg"]      # 门上普查=烧门


# ── B4 stop_at_dialog ──────────────────────────────────────────────────────
STOP_STEP = {"step": 1, "action": "tap", "from": "P", "to": "ConfirmDlg", "trigger": "删除",
             "safety": "stop_at_dialog", "static_rid": "btn_del"}
STOP_SENTINELS = {"P": {"kind": "activity_suffix", "value": "HomeActivity"},
                  "ConfirmDlg": {"kind": "resource_id_unique", "value": ["tv_confirm"], "hosts": []}}
STOP_SRC = wrap('<node resource-id="com.x:id/btn_del" text="删除" clickable="true" bounds="[0,0][200,100]"/>')


def test_b4_stop_at_dialog_never_calls_gate_chooser_and_escalates(ew, monkeypatch):
    calls = []
    monkeypatch.setattr(we, "choose_gate_control", lambda xml: calls.append(1) or None)
    write_plan(ew, [{"walk_id": "w1", "steps": [STOP_STEP]}], sentinels=STOP_SENTINELS)
    ex = mk_exec(ew, dev=FakeDev([STOP_SRC]))                 # 到达判定永远不中 → 只能熔断
    with pytest.raises(SystemExit) as e:
        ex.do_tap(STOP_STEP)
    assert e.value.code == 30 and calls == []                 # 一次放行控件都没挑过
    assert esc_of(ew)["reason"] == "arrival_unverified"       # 不放行、不重试点任何按钮


def test_b4_stop_at_dialog_marks_edge_when_arrived(ew, monkeypatch):
    monkeypatch.setattr(we, "choose_gate_control", lambda xml: pytest.fail("stop_at_dialog 不得选放行控件"))
    write_plan(ew, [{"walk_id": "w1", "steps": [STOP_STEP]}], sentinels=STOP_SENTINELS)
    dlg = wrap('<node resource-id="com.x:id/tv_confirm" text="确认删除？" bounds="[0,0][900,300]"/>')
    mk_exec(ew, dev=FakeDev([STOP_SRC, dlg])).do_tap(STOP_STEP)
    edge = last_edge(ew)
    assert edge["status"] == "confirmed" and edge["safety"] == "stop_at_dialog"


# ── B5 verify_signal / 到达侧向导接受 ────────────────────────────────────────
def _plan_vs(vs, hosts=("WizardActivity",), value=("ll_step",)):
    return {"sentinels": {"P": {"kind": "resource_id_shared", "value": list(value), "weak": True,
                                "hosts": list(hosts), "verify_signal": vs}}}


def test_b5_verify_signal_three_shapes_are_strong():
    xml_txt = wrap('<node text="第二步 选择模板" bounds="[10,10][500,80]"/>')
    ok, weak, why = we.sentinel_check(_plan_vs({"text_contains": "选择模板"}), "P", xml_txt, "com.x.WizardActivity")
    assert (ok, weak) == (True, False) and "text_contains" in why

    xml_vid = wrap('<node resource-id="com.x:id/tv_step2" bounds="[10,10][500,80]"/>')
    ok, weak, why = we.sentinel_check(_plan_vs({"view_id": "com.x:id/tv_step2"}), "P", xml_vid, "com.x.WizardActivity")
    assert (ok, weak) == (True, False) and "view_id" in why

    xml_ord = wrap('<node resource-id="com.x:id/ll_step" bounds="[10,10][500,80]"/>')
    ok, weak, why = we.sentinel_check(_plan_vs({"ordinal_in_wizard": 2}), "P", xml_ord, "com.x.WizardActivity")
    assert (ok, weak) == (True, False) and "ordinal_in_wizard" in why

    assert we.sentinel_check(_plan_vs({"text_contains": ["别的词", "选择模板"]}), "P",
                             xml_txt, "com.x.WizardActivity")[0] is True      # 候选列表形态


def test_b5_host_mismatch_stays_weak():
    xml_txt = wrap('<node text="选择模板" bounds="[10,10][500,80]"/>')
    ok, weak, why = we.sentinel_check(_plan_vs({"text_contains": "选择模板"}), "P", xml_txt, "com.x.OtherActivity")
    assert weak is True and "宿主" in why                      # 宿主不符绝不因 verify_signal 升强判
    # 屏外预加载（bounds 在视口外）同样不给强判
    off = wrap('<node text="选择模板" bounds="[2000,10][2400,80]"/>')
    assert we.sentinel_check(_plan_vs({"text_contains": "选择模板"}), "P", off, "com.x.WizardActivity")[1] is True
    # 没给 verify_signal 的哨兵行为不变
    plain = {"sentinels": {"P": {"kind": "resource_id_shared", "value": ["ll_step"], "weak": True, "hosts": []}}}
    assert we.sentinel_check(plain, "P", xml_txt, "com.x.WizardActivity")[1] is True


WIZ_STEP = {"step": 1, "action": "tap", "from": "P", "to": "W2", "trigger": "下一步", "static_rid": "btn_next"}
WIZ_SENTINELS = {"P": {"kind": "resource_id_unique", "value": ["btn_next"], "hosts": []},
                 "W2": {"kind": "resource_id_shared", "value": ["ll_step"], "weak": True, "hosts": ["WizardActivity"]}}
WIZ_TREE = {"pages": [], "dialogs": [],
            "fragments": [{"id": "W2", "navigation_contract": {"relationship_kind": "wizard_step"}}]}


def test_b5_tap_arrival_accepts_wizard_weak_sentinel(ew):
    """到达判定此前对 ok+weak 无条件熔断；现在与 verify_at 同尺：向导步 + 宿主相符即接受。"""
    write_plan(ew, [{"walk_id": "w1", "steps": [WIZ_STEP]}], sentinels=WIZ_SENTINELS)
    src = wrap('<node resource-id="com.x:id/btn_next" text="下一步" clickable="true" bounds="[0,0][200,100]"/>')
    dst = wrap('<node resource-id="com.x:id/ll_step" text="第二步" bounds="[0,0][900,300]"/>')
    ex = mk_exec(ew, dev=FakeDev([src, dst], activity="com.x.WizardActivity"))
    ex.tree = WIZ_TREE
    ex.do_tap(WIZ_STEP)                                        # 不熔断
    assert last_edge(ew)["status"] == "confirmed"
    assert any("向导步弱哨兵" in n for n in ex.state["notes"])


def test_b5_tap_arrival_wizard_host_mismatch_still_melts_down(ew):
    write_plan(ew, [{"walk_id": "w1", "steps": [WIZ_STEP]}], sentinels=WIZ_SENTINELS)
    src = wrap('<node resource-id="com.x:id/btn_next" text="下一步" clickable="true" bounds="[0,0][200,100]"/>')
    dst = wrap('<node resource-id="com.x:id/ll_step" text="第二步" bounds="[0,0][900,300]"/>')
    ex = mk_exec(ew, dev=FakeDev([src, dst], activity="com.x.OtherActivity"))
    ex.tree = WIZ_TREE                                         # 顺序语义只在同宿主内成立
    with pytest.raises(SystemExit):
        ex.do_tap(WIZ_STEP)
    assert esc_of(ew)["reason"] == "weak_sentinel_confirm"


def test_b5_tap_arrival_accepts_weak_with_assume_at_once(ew):
    write_plan(ew, [{"walk_id": "w1", "steps": [WIZ_STEP]}], sentinels=WIZ_SENTINELS)
    src = wrap('<node resource-id="com.x:id/btn_next" text="下一步" clickable="true" bounds="[0,0][200,100]"/>')
    dst = wrap('<node resource-id="com.x:id/ll_step" text="第二步" bounds="[0,0][900,300]"/>')
    ex = mk_exec(ew, dev=FakeDev([src, dst], activity="com.x.OtherActivity"), assume_at="W2")
    ex.do_tap(WIZ_STEP)                                        # 无 tree（非向导）也能靠人工确认收
    assert last_edge(ew)["status"] == "confirmed" and ex.state["_assume_consumed"] is True


# ── B6 suspect 快路 ────────────────────────────────────────────────────────
def _suspect_plan(d, settles=None, extra_settler=False):
    """steps: 1 冷启→P / 2 tap P→Q（suspect）/ 3 back Q→P / 4 note。子树 = 第 3 步。"""
    steps = [{"step": 1, "action": "coldstart", "to": "P"},
             {"step": 2, "action": "tap", "from": "P", "to": "Q", "trigger": "入口", "static_rid": "btn_q",
              "suspect": ["stale_edge", "unverified_runtime"], "settles_capture": settles},
             {"step": 3, "action": "back", "from": "Q", "to": "P"},
             {"step": 4, "action": "note", "from": "P", "to": "P"}]
    if extra_settler:                                          # 兄弟边也结同一目标
        steps.append({"step": 5, "action": "tap", "from": "P", "to": "Q", "trigger": "兄弟入口",
                      "settles_capture": settles})
    write_plan(d, [{"walk_id": "w1", "steps": steps}],
               sentinels={"P": {"kind": "activity_suffix", "value": "HomeActivity"},
                          "Q": {"kind": "resource_id_unique", "value": ["tv_q"], "hosts": []}})
    write_ledger(d)
    return steps[1]


OTHER_SRC = wrap('<node resource-id="com.x:id/btn_other" text="别的" clickable="true" bounds="[0,0][200,100]"/>')


def test_b6_suspect_control_missing_does_not_meltdown(ew):
    step = _suspect_plan(ew, settles=None)
    ex = mk_exec(ew, dev=FakeDev([OTHER_SRC]))
    ex.do_tap(step)                                            # 控件不在 → 记账跳子树，不抛
    edge = last_edge(ew)
    assert edge["status"] == "not_reproduced" and "suspect:stale_edge,unverified_runtime" in edge["note"]
    assert ex._jump_to == 3 and ex.state["skipped"] == [3]     # 配对的 back 步一起跳


def test_b6_suspect_arrival_unverified_recovers_and_skips(ew):
    step = _suspect_plan(ew, settles=None)
    src = wrap('<node resource-id="com.x:id/btn_q" text="入口" clickable="true" bounds="[0,0][200,100]"/>')
    ex = mk_exec(ew, dev=FakeDev([src]))                       # 点了但落点判不到
    ex.do_tap(step)
    assert last_edge(ew)["status"] == "not_reproduced" and ex._jump_to == 3
    assert ex.dev.backs == 0                                   # 一探就确认还在起点，不乱按 BACK


def test_b6_sole_settler_still_melts_down(ew):
    """覆盖优先：目标未结账且本步是唯一结账步 → 仍走原熔断路径。"""
    step = _suspect_plan(ew, settles="Q")
    with pytest.raises(SystemExit) as e:
        mk_exec(ew, dev=FakeDev([OTHER_SRC])).do_tap(step)
    assert e.value.code == 30 and esc_of(ew)["reason"] == "control_not_found"


def test_b6_fastpath_when_sibling_also_settles(ew):
    step = _suspect_plan(ew, settles="Q", extra_settler=True)
    mk_exec(ew, dev=FakeDev([OTHER_SRC])).do_tap(step)
    assert last_edge(ew)["status"] == "not_reproduced"


def test_b6_fastpath_when_target_already_settled(ew):
    step = _suspect_plan(ew, settles="Q")                      # 唯一结账步，但目标已在账上 → 让位
    write_ledger(ew, {"Q": {"via": "别处"}})
    mk_exec(ew, dev=FakeDev([OTHER_SRC])).do_tap(step)
    assert last_edge(ew)["status"] == "not_reproduced"


def test_b6_no_suspect_flag_keeps_old_meltdown(ew):
    step = dict(_suspect_plan(ew, settles=None))
    step.pop("suspect")
    with pytest.raises(SystemExit):
        mk_exec(ew, dev=FakeDev([OTHER_SRC])).do_tap(step)
    assert esc_of(ew)["reason"] == "control_not_found"


# ── B7 stop_if_settled ─────────────────────────────────────────────────────
def test_b7_walk_skipped_when_target_already_settled(ew, capsys):
    write_plan(ew, [{"walk_id": "w1", "trip_id": "trip_a", "stop_if_settled": "T",
                     "steps": [{"step": 1, "action": "coldstart", "to": "R"}]}])
    write_ledger(ew, {"T": {"via": "上一轮"}})
    ex = mk_exec(ew)
    assert ex.run() is None
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out == {"status": "walk_skipped_target_settled", "walk_id": "w1", "target": "T"}
    assert json.load(open(ew / "walk_exec_state.json"))["status"] == "walk_skipped_target_settled"
    assert ex.dev.taps == [] and ex.dev.shots == []             # 一步都没跑


def test_b7_not_settled_walk_proceeds(ew):
    write_plan(ew, [{"walk_id": "w1", "stop_if_settled": "T",
                     "steps": [{"step": 1, "action": "note", "to": "R"}]}])
    write_ledger(ew)
    mk_exec(ew).run()
    assert json.load(open(ew / "walk_exec_state.json"))["status"] == "walk_done"


# ── B9 词表可覆盖 ───────────────────────────────────────────────────────────
EN_GATE = wrap('<node resource-id="com.x:id/tv_body" text="Terms of Service and data use" clickable="false" bounds="[0,0][900,300]"/>'
               '<node resource-id="com.x:id/btn_x" text="Accept all" clickable="true" bounds="[0,400][400,500]"/>')


def test_b9_ui_words_project_override(ew):
    assert we.choose_gate_control(EN_GATE) is None             # 默认词表认不出「Accept all」
    (ew / "ui_words.json").write_text(json.dumps(
        {"GATE_TEXT_OK": ["Accept all"], "CANCEL_TEXT_OK": ["Dismiss"], "unknown_key": 1}), encoding="utf-8")
    assert we.load_ui_words(str(ew)) == ["CANCEL_TEXT_OK", "GATE_TEXT_OK"]     # 未知键忽略
    pt, rid, txt = we.choose_gate_control(EN_GATE)
    assert (rid, txt) == ("btn_x", "Accept all") and pt == (200, 450)
    _p, rid2, _t = we.choose_cancel_control(
        wrap('<node resource-id="com.x:id/btn_d" text="Dismiss" clickable="true" bounds="[0,0][100,50]"/>'))
    assert rid2 == "btn_d"
    # 未覆盖的键保留默认；重复加载幂等（不叠加）
    assert "同意并继续" not in we.UI_WORDS["GATE_TEXT_OK"] and we.UI_WORDS["GATE_BODY_RE"].search("隐私")
    we.load_ui_words(str(ew))
    assert we.UI_WORDS["GATE_TEXT_OK"] == ("Accept all",)


def test_b9_regex_keys_overridable(ew):
    (ew / "ui_words.json").write_text(json.dumps({"GATE_ID_RE": "(btn_x)"}), encoding="utf-8")
    we.load_ui_words(str(ew))
    assert we.choose_gate_control(EN_GATE)[1] == "btn_x"        # 正则键给字符串，加载时编译


def test_b9_exec_loads_project_words_from_dir(ew):
    write_plan(ew, [{"walk_id": "w1", "steps": [{"step": 1, "action": "note", "to": "P"}]}])
    (ew / "ui_words.json").write_text(json.dumps({"GATE_TEXT_OK": ["Accept all"]}), encoding="utf-8")
    ex = mk_exec(ew)
    assert ex.ui_words_overridden == ["GATE_TEXT_OK"] and we.UI_WORDS["GATE_TEXT_OK"] == ("Accept all",)


def test_b9_broken_override_file_falls_back_to_defaults(ew):
    (ew / "ui_words.json").write_text("{ not json", encoding="utf-8")
    assert we.load_ui_words(str(ew)) == []
    assert "同意并继续" in we.UI_WORDS["GATE_TEXT_OK"]
