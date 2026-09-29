"""第四轮通用修复 B 批（2026-09-10）：

B1 node_sweep `--only-rids` 与 `--from-plan` 互斥失效
    病：`--from-plan` 把计划边的触发键灌进 walk_keys → 目标元素先被判 walk/same_dest（「不点」），
        只做收窄的 only_rids 不会把命中项提回可点档 ⇒ 补点这条**唯一的补救路径**被计划自己堵死。
    治：only_rids 命中 = 调用方显式点名「这一个我要你点」→ 强制提档为 ground/unclaimed，
        压过 walk/same_dest/h5_oracle/nav_back/in_plan；destructive/input_field 两个安全档不提。

B2 walk_back_to 回位过冲把应用弹出去
    病：命中目标宿主后不停、继续按计数 → 把栈按穿，露出别的应用的任务栈。
    治：①每按之后立刻判位，命中即返回；②根 activity（树 activity_root / 计划 coldstart 的 to /
        derived_config 根）上零 BACK，返回结构化「已在根、无法继续回退」。

铁律：零应用硬编码（判据只吃命令行 / dump 属性 / 树与计划字段），夹具用占位名；
      全部合成 dump + 内存假设备，绝不碰 adb / 模拟器。
"""
import json, os, sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))

from test_node_sweep_rules import (FakeDev, PKG, _row, _simple,            # noqa: E402
                                   _stdout_json, run_sweep)

# walk_back_to 在 import 期解析设备串号（多台在线会 sys.exit(2)）→ 借一个占位串号跨过 import，随后还原
_HAD_SERIAL = "ANDROID_SERIAL" in os.environ
os.environ.setdefault("ANDROID_SERIAL", "placeholder-serial")
import walk_back_to as wb                                                  # noqa: E402
if not _HAD_SERIAL:
    os.environ.pop("ANDROID_SERIAL", None)


# ══════════════════════════════════════════════════════════════════════════════
# B1 · --only-rids 定向补点提档
# ══════════════════════════════════════════════════════════════════════════════
def _write_plan(tmp_path, node, steps, planned_edge_vids=(), webview=(), tree_rel="tree.json"):
    """合成 walk_plan.json（只放 --from-plan 真正读的字段，全部是契约名）。"""
    plan = {"tree": tree_rel,
            "derived_config": {"main_root": "RootActivity", "launcher": "RootActivity",
                               "webview": list(webview)},
            "planned_edge_vids": list(planned_edge_vids),
            "sentinels": {},
            "walks": [{"walk_id": "walk_x", "steps": [dict(s, **{"from": s.pop("from_", node)})
                                                      for s in steps]}]}
    (tmp_path / "walk_plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return plan


def _child(node, pid, vid):
    """一个子页节点：带一条来自 node 的入边，trigger_view_id=vid（same_dest / in_plan 判据的来源）。"""
    return {"id": pid, "type": "Activity", "fq_class": "%s.%s" % (PKG, pid),
            "inbound_triggers": [{"from_page": node, "trigger_view_id": vid,
                                  "trigger_label": "去" + pid}],
            "navigation": {"inbound": [], "outbound": []}, "functional_checks": []}


def test_from_plan_no_longer_deadlocks_only_rids_supplementary_tap(monkeypatch, tmp_path, capsys):
    """★B1 主用例（0910 实测死锁的原样复现）：`--from-plan --only-rids <rid>`。

    两个命中元素分别落在 walk（计划边触发键）与 same_dest（锚点==出边 trigger_view_id）两档——
    修复前两者都「不点」，inventory={"walk":1,"same_dest":1}、processed_check_idx=[]，
    check 结成 deferred_same_destination 原地不动；修复后两者都被提档 ground 并真 tap。"""
    node = "HostPage"
    _write_plan(tmp_path, node,
                steps=[{"action": "tap", "from_": node, "to": "AlphaPage", "trigger": "甲功能"},
                       {"action": "tap", "from_": node, "to": "BetaPage", "trigger": None}])
    dev = FakeDev({"host": (_simple("宿主页"), "HostActivity"),
                   "alpha": (_simple("甲页", "tv_alpha", "甲内容"), "AlphaActivity"),
                   "beta": (_simple("乙页", "tv_beta", "乙内容"), "BetaActivity")}, "host")
    dev.tap_zones = [((0, 1000, 300, 1100), lambda d: setattr(d, "cur", "alpha")),
                     ((300, 1100, 700, 1200), lambda d: setattr(d, "cur", "beta"))]
    dev.back_handler = lambda d: setattr(d, "cur", "host")
    m = run_sweep(monkeypatch, tmp_path, dev,
                  [_row("btn_alpha", "甲功能", 1000, 0, 300),      # 计划边触发键 → 修复前判 walk
                   _row("btn_beta", "乙功能", 1100, 300, 700)],    # 锚点==出边 vid → 修复前判 same_dest
                  node=node,
                  checks=[{"name": "甲检查", "android_anchor": {"raw_identifier": "btn_alpha"}},
                          {"name": "乙检查", "android_anchor": {"raw_identifier": "btn_beta"}}],
                  extra_pages=[_child(node, "AlphaPage", "btn_alpha"),
                               _child(node, "BetaPage", "btn_beta")],
                  extra_args=["--from-plan", "--only-rids", "btn_alpha,btn_beta"])
    out = _stdout_json(capsys)
    assert m["sweep_inventory_dispositions"] == {"ground": 2}          # 两个都提到可点档
    assert {(p["from"], p["to"]) for p in m["only_rids_promoted"]} == \
        {("walk", "ground"), ("same_dest", "ground")}
    assert out["only_rids_promoted"] == m["only_rids_promoted"]
    assert len([t for t in dev.log if isinstance(t, tuple)]) == 2       # ★真的点了（修复前 0 次）
    # 提档留痕进 behavior_ledger，判读可复核
    assert {x["only_rids_promoted_from"] for x in m["behavior_ledger"]} == {"walk", "same_dest"}
    # run_meta 两条 check 都结成 ok，且都进了 processed_check_idx（修复前是 []）
    rm = json.load(open(tmp_path / "grounding" / node / "run_meta.json"))
    assert rm["processed_check_idx"] == [0, 1]
    assert {c["status"] for c in rm["checks"]} == {"ok"}
    assert "deferred_same_destination" not in json.dumps(rm, ensure_ascii=False)


def test_promotion_also_covers_navback_inplan_and_h5_dispositions(monkeypatch, tmp_path):
    """提档压过其余「不点」档：nav_back / in_plan / h5_oracle 一律提到 ground。"""
    node = "HostPage"
    _write_plan(tmp_path, node,
                steps=[{"action": "tap", "from_": node, "to": "OtherPage", "trigger": "别的"}],
                planned_edge_vids=["btn_inplan"], webview=["WebPage"])
    dev = FakeDev({"host": (_simple("宿主页"), "HostActivity"),
                   "sub": (_simple("子页", "tv_sub", "子内容"), "SubActivity")}, "host")
    dev.tap_zones = [((0, 0, 1080, 1920), lambda d: setattr(d, "cur", "sub"))]
    dev.back_handler = lambda d: setattr(d, "cur", "host")
    m = run_sweep(monkeypatch, tmp_path, dev,
                  [_row("btn_close", "关闭", 1000, 0, 300),        # nav_back
                   _row("btn_inplan", "计划内", 1100, 300, 700),   # in_plan（rid ∈ planned_edge_vids）
                   _row("btn_h5", "网页入口", 1200, 700, 1080)],   # h5_oracle（落点在 webview 集）
                  node=node,
                  checks=[{"name": "关闭检查", "android_anchor": {"raw_identifier": "btn_close"}},
                          {"name": "计划检查", "android_anchor": {"raw_identifier": "btn_inplan"}},
                          {"name": "网页检查", "android_anchor": {"raw_identifier": "btn_h5"}}],
                  extra_pages=[_child(node, "WebPage", "btn_h5")],
                  extra_args=["--from-plan", "--only-rids",
                              "btn_close,btn_inplan,%s:id/btn_h5" % PKG])   # 传全名也认
    assert m["sweep_inventory_dispositions"] == {"ground": 3}
    assert {p["from"] for p in m["only_rids_promoted"]} == {"nav_back", "in_plan", "h5_oracle"}
    assert len([t for t in dev.log if isinstance(t, tuple)]) == 3
    assert m["only_rids_kept_safe"] == []


def test_promotion_never_touches_destructive_or_input_field(monkeypatch, tmp_path, capsys):
    """★反例（安全面不许放宽）：destructive / input_field 即使被点名也不提档、不 tap。

    两者不点是**安全判据**（破坏性动作不可逆 / tap 输入框只弹键盘污染位置），
    调用方点名只放宽「留给别人点」这类调度性归宿，绝不放宽安全档。"""
    node = "HostPage"
    _write_plan(tmp_path, node, steps=[{"action": "tap", "from_": node, "to": "X", "trigger": "删除账号"}])
    dev = FakeDev({"host": (_simple("宿主页"), "HostActivity")}, "host")
    bucket = [_row("btn_del", "删除账号", 1000, 0, 300),
              dict(_row("et_name", "", 1100, 300, 700), **{"class": "android.widget.EditText"})]
    m = run_sweep(monkeypatch, tmp_path, dev, bucket, node=node,
                  checks=[{"name": "删除检查", "android_anchor": {"raw_identifier": "btn_del"}},
                          {"name": "输入检查", "android_anchor": {"raw_identifier": "et_name"}}],
                  extra_args=["--from-plan", "--only-rids", "btn_del,et_name"])
    out = _stdout_json(capsys)
    assert m["sweep_inventory_dispositions"] == {"destructive": 1, "input_field": 1}
    assert m["only_rids_promoted"] == []                                  # ★一个都没提
    assert {k["kept"] for k in m["only_rids_kept_safe"]} == {"destructive", "input_field"}
    assert out["only_rids_kept_safe"] == m["only_rids_kept_safe"]
    assert [t for t in dev.log if isinstance(t, tuple)] == []             # ★一下都没点
    assert m["budget"] == 0
    # 两条 check 如实结成安全档状态，不谎报 ok、也不静默丢
    rm = json.load(open(tmp_path / "grounding" / node / "run_meta.json"))
    assert {c["name"]: c["status"] for c in rm["checks"]} == \
        {"删除检查": "skipped_destructive", "输入检查": "input_field_no_tap"}
    assert rm["processed_check_idx"] == []                                # 没处理就别覆盖旧账


def test_exclude_still_beats_only_rids_and_misses_still_narrow(monkeypatch, tmp_path):
    """边界不变：--exclude-* 命中的元素绝不提档；不在集合内的元素照旧 not_in_only（不点、不进分母）。

    ★这里的元素同时被计划边认领（disposition=walk，排除档压在 ground 正上方够不着它）——
    只看 disposition=="excluded" 的话提档会从上面绕过排除集，所以判据必须是「是否在排除集」。"""
    node = "HostPage"
    _write_plan(tmp_path, node, steps=[{"action": "tap", "from_": node, "to": "X", "trigger": "甲功能"}])
    dev = FakeDev({"host": (_simple("宿主页"), "HostActivity")}, "host")
    m = run_sweep(monkeypatch, tmp_path, dev,
                  [_row("btn_alpha", "甲功能", 1000, 0, 300),      # 既在 only 又在 exclude → 不点
                   _row("btn_other", "旁的", 1100, 300, 700)],     # 不在 only → not_in_only
                  node=node,
                  extra_args=["--from-plan", "--only-rids", "btn_alpha",
                              "--exclude-rids", "btn_alpha"])
    assert m["sweep_inventory_dispositions"] == {"walk": 1, "not_in_only": 1}
    assert m["only_rids_promoted"] == []                            # ★没被提档
    assert [k["kept"] for k in m["only_rids_kept_safe"]] == ["excluded_by_caller"]
    assert [t for t in dev.log if isinstance(t, tuple)] == []
    assert m["budget"] == 0


def test_exclude_by_text_also_blocks_promotion_of_a_ground_claimed_element(monkeypatch, tmp_path):
    """--exclude-texts 同样挡得住提档（排除判据两路都验，别只验 rid 那路）。"""
    node = "HostPage"
    dev = FakeDev({"host": (_simple("宿主页"), "HostActivity")}, "host")
    m = run_sweep(monkeypatch, tmp_path, dev,
                  [_row("btn_alpha", "甲功能", 1000, 0, 300)],
                  node=node,
                  checks=[{"name": "甲检查", "android_anchor": {"raw_identifier": "btn_alpha"}}],
                  extra_args=["--only-rids", "btn_alpha", "--exclude-texts", "甲功能"])
    assert m["sweep_inventory_dispositions"] == {"excluded": 1}
    assert m["only_rids_promoted"] == [] and m["excluded"] == 1
    assert [t for t in dev.log if isinstance(t, tuple)] == []


def test_named_rid_without_a_live_check_is_promoted_to_unclaimed_and_still_tapped(monkeypatch, tmp_path):
    """命中项没有活着的 check 认领（已 settled_by_walk / 本就无主）→ 提档为 unclaimed 照点，
    行为进 behavior_ledger。补点这条路径不会因为「没有可认领的 check」而空转。"""
    node = "HostPage"
    _write_plan(tmp_path, node, steps=[{"action": "tap", "from_": node, "to": "X", "trigger": "甲功能"}])
    (tmp_path / "walked_grounding.json").write_text(
        json.dumps([{"node": node, "check_name": "甲检查", "check_idx": 0}]), encoding="utf-8")
    dev = FakeDev({"host": (_simple("宿主页"), "HostActivity"),
                   "sub": (_simple("子页", "tv_sub", "子内容"), "SubActivity")}, "host")
    dev.tap_zones = [((0, 0, 1080, 1920), lambda d: setattr(d, "cur", "sub"))]
    dev.back_handler = lambda d: setattr(d, "cur", "host")
    m = run_sweep(monkeypatch, tmp_path, dev,
                  [_row("btn_alpha", "甲功能", 1000, 0, 300)], node=node,
                  checks=[{"name": "甲检查", "android_anchor": {"raw_identifier": "btn_alpha"}}],
                  extra_args=["--from-plan", "--only-rids", "btn_alpha"])
    assert m["sweep_inventory_dispositions"] == {"unclaimed": 1}
    assert [(p["from"], p["to"]) for p in m["only_rids_promoted"]] == [("walk", "unclaimed")]
    assert len([t for t in dev.log if isinstance(t, tuple)]) == 1
    rm = json.load(open(tmp_path / "grounding" / node / "run_meta.json"))
    assert [c["status"] for c in rm["checks"]] == ["settled_by_walk"]   # 已结的账不被本轮改写


def test_only_rids_fields_are_contract_defaults_when_knob_off(monkeypatch, tmp_path):
    """不开 --only-rids 时两个新字段恒在且为空表（调用方免判存在），全量普查行为不变。"""
    dev = FakeDev({"host": (_simple("宿主页"), "HostActivity")}, "host")
    m = run_sweep(monkeypatch, tmp_path, dev, [_row("btn_a", "甲", 1000, 0, 300)], node="HostPage")
    assert m["only_rids_promoted"] == [] and m["only_rids_kept_safe"] == []
    assert m["sweep_inventory_dispositions"] == {"unclaimed": 1}


# ══════════════════════════════════════════════════════════════════════════════
# B2 · walk_back_to 回位不过冲
# ══════════════════════════════════════════════════════════════════════════════
OTHER_PKG = "com.other.demo"


class FakeStack:
    """内存 activity 栈（栈底在前）。BACK 弹一层；**在栈底再按就整包弹出去**——
    B2 的全部用例都要证明这一下永远不发生（escaped 恒 False）。"""

    def __init__(self, stack, pkg=PKG, ime=()):
        self.stack, self.pkg = list(stack), pkg
        self.presses, self.escaped = 0, False
        self.ime = list(ime)                      # 第 n 下是否被键盘吃掉

    def cur(self):
        if self.escaped:
            return (OTHER_PKG, "OtherAppActivity")     # 露出同设备上另一个应用的任务栈
        return (self.pkg, self.stack[-1])

    def ime_shown(self):
        return bool(self.ime) and self.ime[0]

    def sh(self, cmd, timeout=15):
        if "keyevent 4" not in cmd:
            return ""
        self.presses += 1
        if self.ime and self.ime.pop(0):
            return ""                                  # 这一下只收键盘，不弹栈
        if len(self.stack) > 1:
            self.stack.pop()
        else:
            self.escaped = True
        return ""


def _tree_with_root(root_id):
    return {"app": {}, "fragments": [], "dialogs": [],
            "pages": [{"id": root_id, "fq_class": "%s.%s" % (PKG, root_id),
                       "navigation_contract": {"relationship_kind": "activity_root"}},
                      {"id": "HostActivity", "fq_class": "%s.HostActivity" % PKG,
                       "navigation_contract": {"relationship_kind": "activity_jump"}}]}


def _bed(tmp_path, plan=None, tree=None):
    """写计划/树到临时目录；两者都可缺省（用来证明单一信源够不够）。"""
    if plan is not None:
        (tmp_path / "walk_plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    tp = tmp_path / "fact_tree.json"
    if tree is not None:
        tp.write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    return str(tp)


def _run_back(monkeypatch, capsys, fake, argv):
    monkeypatch.setattr(wb, "cur", fake.cur)
    monkeypatch.setattr(wb, "sh", fake.sh)
    monkeypatch.setattr(wb, "ime_shown", fake.ime_shown)
    monkeypatch.setattr(wb.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["walk_back_to.py"] + argv)
    wb.main()
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_stops_the_moment_expect_host_is_reached_instead_of_burning_the_count(monkeypatch, tmp_path, capsys):
    """★B2 主用例（0910 实测逃逸的原样复现）：调用方把弹窗也算进了 --steps（报 3，真实只沉 1 层）。

    修复前：按计数一路按 → 第 2 下把栈按穿 → 露出别的应用 → 目标包栈清零，只能冷启回来。
    修复后：第 1 下回到宿主即返回，remaining_steps>0 是故意的。"""
    tp = _bed(tmp_path, tree=_tree_with_root("RootActivity"))
    fake = FakeStack(["HostActivity", "ChildActivity"])          # 宿主已是栈底之上第一层
    got = _run_back(monkeypatch, capsys, fake,
                    ["--steps", "3", "--package", PKG, "--expect-host", "HostActivity",
                     "--dir", str(tmp_path), "--tree", tp])
    assert (got["reached_host"], got["stop_reason"]) == (True, "host_reached")
    assert got["final"] == "HostActivity" and got["presses"] == 1
    assert got["remaining_steps"] == 2                            # 剩的计数**故意不按**
    assert fake.escaped is False and fake.presses == 1            # ★应用没被弹出去
    assert fake.stack == ["HostActivity"]


def test_zero_back_when_already_at_target_host(monkeypatch, tmp_path, capsys):
    """已经在目标宿主上 → 一下都不按。"""
    tp = _bed(tmp_path, tree=_tree_with_root("RootActivity"))
    fake = FakeStack(["RootActivity", "HostActivity"])
    got = _run_back(monkeypatch, capsys, fake,
                    ["--steps", "2", "--package", PKG, "--expect-host", "HostActivity",
                     "--dir", str(tmp_path), "--tree", tp])
    assert (got["reached_host"], got["stop_reason"], got["presses"]) == (True, "already_at_host", 0)
    assert fake.presses == 0 and fake.escaped is False


def test_zero_back_on_activity_root_from_tree_alone(monkeypatch, tmp_path, capsys):
    """★反例要求的「根 activity 上零 BACK」：根白名单只来自树 activity_root（无计划文件）。"""
    tp = _bed(tmp_path, tree=_tree_with_root("RootActivity"))
    fake = FakeStack(["RootActivity"])
    got = _run_back(monkeypatch, capsys, fake,
                    ["--steps", "2", "--package", PKG, "--dir", str(tmp_path), "--tree", tp])
    assert got["stop_reason"] == "root_guard" and got["at_root"] is True
    assert got["presses"] == 0 and fake.presses == 0 and fake.escaped is False
    assert "已在根、无法继续回退" in got["note"]
    assert got["roots"] == ["RootActivity"]
    assert got["roots_why"]["tree.activity_root"] == ["RootActivity"]


def test_zero_back_on_root_from_plan_coldstart_step_alone(monkeypatch, tmp_path, capsys):
    """根白名单第二信源：计划 coldstart 步的 to（derived_config 空、树也没 activity_root）。"""
    plan = {"derived_config": {}, "walks": [{"walk_id": "w",
                                             "steps": [{"action": "coldstart", "to": "BootPage"}]}]}
    tp = _bed(tmp_path, plan=plan, tree={"pages": [], "fragments": [], "dialogs": []})
    fake = FakeStack(["BootPage"])
    got = _run_back(monkeypatch, capsys, fake,
                    ["--steps", "1", "--package", PKG, "--dir", str(tmp_path), "--tree", tp])
    assert got["stop_reason"] == "root_guard" and got["at_root"] is True and got["presses"] == 0
    assert got["roots_why"]["plan.coldstart.to"] == ["BootPage"]
    assert fake.escaped is False


def test_root_guard_stops_midway_right_after_the_press_that_lands_on_root(monkeypatch, tmp_path, capsys):
    """中途退到根 → 当场停（不等下一轮循环头），剩余计数不再消费。"""
    tp = _bed(tmp_path, tree=_tree_with_root("RootActivity"))
    fake = FakeStack(["RootActivity", "ChildActivity"])
    got = _run_back(monkeypatch, capsys, fake,
                    ["--steps", "3", "--package", PKG, "--dir", str(tmp_path), "--tree", tp])
    assert got["stop_reason"] == "root_guard" and got["at_root"] is True
    assert got["presses"] == 1 and fake.presses == 1 and fake.escaped is False


def test_ime_press_does_not_count_and_still_stops_at_host(monkeypatch, tmp_path, capsys):
    """键盘吃掉的那一下不算弹栈，也不因此过冲：收完键盘继续按到宿主即停。"""
    tp = _bed(tmp_path, tree=_tree_with_root("RootActivity"))
    fake = FakeStack(["HostActivity", "ChildActivity"], ime=[True])
    got = _run_back(monkeypatch, capsys, fake,
                    ["--steps", "1", "--package", PKG, "--expect-host", "HostActivity",
                     "--dir", str(tmp_path), "--tree", tp])
    assert got["reached_host"] is True and got["stop_reason"] == "host_reached"
    assert fake.presses == 2 and fake.escaped is False
    assert any("ime_close" in x for x in got["log"])


def test_plain_count_run_without_expect_host_still_settles_as_count_done(monkeypatch, tmp_path, capsys):
    """回归：不传 --expect-host 的纯计数回位语义不变。"""
    tp = _bed(tmp_path, tree=_tree_with_root("RootActivity"))
    fake = FakeStack(["RootActivity", "MidActivity", "ChildActivity"])
    got = _run_back(monkeypatch, capsys, fake,
                    ["--steps", "1", "--package", PKG, "--dir", str(tmp_path), "--tree", tp])
    assert (got["reached_host"], got["stop_reason"], got["final"]) == (True, "count_done", "MidActivity")
    assert fake.presses == 1 and fake.escaped is False


def test_pkg_escape_is_caught_on_the_press_itself(monkeypatch, tmp_path, capsys):
    """兜底：万一根白名单没盖住（树/计划都没标），按穿的那一下当场判 pkg_escape，不再继续按。"""
    tp = _bed(tmp_path, tree=_tree_with_root("SomeUnrelatedRoot"))
    fake = FakeStack(["LoneActivity"])                 # 栈底但不在白名单 → 这一下会按穿
    got = _run_back(monkeypatch, capsys, fake,
                    ["--steps", "2", "--package", PKG, "--dir", str(tmp_path), "--tree", tp])
    assert got["stop_reason"] == "pkg_escape" and got["reached_host"] is False
    assert fake.presses == 1                            # ★只按穿一次就停，不会连按到 limit
    assert got["final"] == "OtherAppActivity"


def test_refuses_to_run_without_any_root_source(monkeypatch, tmp_path, capsys):
    """三个信源都给不出根 → 拒跑（没有白名单就没有过冲保护），语义不变。"""
    tp = _bed(tmp_path, plan={"derived_config": {}, "walks": []},
              tree={"pages": [], "fragments": [], "dialogs": []})
    fake = FakeStack(["AnyActivity"])
    with pytest.raises(SystemExit) as ex:
        _run_back(monkeypatch, capsys, fake,
                  ["--steps", "1", "--package", PKG, "--dir", str(tmp_path), "--tree", tp])
    assert ex.value.code == 2
    assert fake.presses == 0


def test_tree_path_is_resolved_from_plan_when_not_passed(monkeypatch, tmp_path, capsys):
    """--tree 缺省时从计划的 tree 字段推路径（相对 --dir 的各级祖先），零应用硬编码。"""
    proj = tmp_path / "proj"
    ew = proj / "spec" / "visual-verify" / "edgewalk"
    ew.mkdir(parents=True)
    (proj / "spec").joinpath("fact_tree.json").write_text(
        json.dumps(_tree_with_root("RootActivity"), ensure_ascii=False), encoding="utf-8")
    (ew / "walk_plan.json").write_text(
        json.dumps({"tree": "spec/fact_tree.json", "derived_config": {}, "walks": []},
                   ensure_ascii=False), encoding="utf-8")
    fake = FakeStack(["RootActivity"])
    got = _run_back(monkeypatch, capsys, fake,
                    ["--steps", "1", "--package", PKG, "--dir", str(ew)])
    assert got["stop_reason"] == "root_guard" and got["presses"] == 0
    assert got["roots_why"]["tree.activity_root"] == ["RootActivity"]
