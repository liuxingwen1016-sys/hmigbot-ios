"""编译器消费安卓未达归因（2026-09-10 鸿蒙首跑实证）：
安卓运行时已判「这一趟到不了」的页，鸿蒙计划不许再排动作步——否则同一个发现要买两次，
第二次还因为鸿蒙没有代理接而直接停摆。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import compile_replay_plan as C  # noqa: E402


def test_loader_reads_only_entries_with_reason(tmp_path):
    p = tmp_path / "ro.json"
    p.write_text(json.dumps({
        "GhostPage": {"reason": "structurally_unreachable", "note": "一次性门已被消费"},
        "DataPage": {"reason": "data_precondition_missing", "note": "账号无订阅"},
        "NoReason": {"note": "只有备注没有结论"},
        "Junk": "不是字典",
    }), encoding="utf-8")
    got = C.load_android_unreached(str(p))
    assert set(got) == {"GhostPage", "DataPage"}
    assert got["GhostPage"]["reason"] == "structurally_unreachable"


def test_loader_tolerates_missing_and_broken(tmp_path):
    assert C.load_android_unreached(None) == {}
    assert C.load_android_unreached(str(tmp_path / "nope.json")) == {}
    bad = tmp_path / "bad.json"; bad.write_text("{ not json", encoding="utf-8")
    assert C.load_android_unreached(str(bad)) == {}


def _emit(steps, unreached):
    """复刻编译器步循环里那道闸的判据（与实现同源）：
    tap/deeplink 去够目标页 → 看 to；gate_pass 站在门那一页按键 → 看 from。"""
    out = []
    for s in steps:
        act = s["action"]
        need = s.get("from") if act == "gate_pass" else s.get("to")
        st = dict(s)
        if act in ("tap", "gate_pass", "deeplink") and need in unreached:
            st["action"] = "skip"
            st["skip_reason"] = f'android_unreached_{unreached[need]["reason"]}'
            st["android_attribution"] = unreached[need]["note"]
        out.append(st)
    return out


UNREACHED = {"GhostPage": {"reason": "structurally_unreachable", "note": "一次性门已被消费"}}


def test_action_steps_to_unreached_page_become_skip_with_provenance():
    steps = [{"step": 1, "action": "tap", "from": "Root", "to": "GhostPage"},
             {"step": 2, "action": "gate_pass", "from": "GhostPage", "to": "Root"},
             {"step": 3, "action": "deeplink", "from": None, "to": "GhostPage"}]
    out = _emit(steps, UNREACHED)
    assert out[0]["action"] == "skip"
    assert out[0]["skip_reason"] == "android_unreached_structurally_unreachable"
    assert "一次性门" in out[0]["android_attribution"]      # 安卓的结论透传，不重新发明理由
    assert out[2]["action"] == "skip"
    # ★gate_pass 看 from：门那一页安卓到不了 → 这一步也发不出去（真机实测纠正，第一版看 to 漏了它）
    assert out[1]["action"] == "skip"
    assert out[1]["skip_reason"] == "android_unreached_structurally_unreachable"


def test_gate_pass_on_reachable_gate_is_kept():
    """门那一页安卓到得了 → 放行步照发，不受本闸影响。"""
    steps = [{"step": 1, "action": "gate_pass", "from": "RealGate", "to": "Root"}]
    assert _emit(steps, UNREACHED)[0]["action"] == "gate_pass"


def test_back_and_verify_never_blocked():
    """back/verify 的 to 是父页或本页；拦了会破坏回位与判位。"""
    steps = [{"step": 1, "action": "back", "to": "GhostPage"},
             {"step": 2, "action": "verify", "to": "GhostPage"},
             {"step": 3, "action": "reconcile", "to": "GhostPage"}]
    out = _emit(steps, UNREACHED)
    assert [x["action"] for x in out] == ["back", "verify", "reconcile"]


def test_reachable_pages_untouched():
    steps = [{"step": 1, "action": "tap", "from": "Root", "to": "RealPage"}]
    assert _emit(steps, UNREACHED)[0]["action"] == "tap"


def test_no_attribution_file_means_zero_behaviour_change():
    steps = [{"step": 1, "action": "tap", "from": "Root", "to": "GhostPage"},
             {"step": 2, "action": "gate_pass", "from": "GhostPage", "to": "Root"}]
    assert _emit(steps, {}) == steps
