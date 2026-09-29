#!/usr/bin/env python3
"""parity_cases.py — .sh ↔ .py 等价用例矩阵（给 sh_py_parity.py --all 用；也被
scripts/_tests/test_py_golden_0914.py 复用，保证"开发工具跑的"和"套件跑的"是同一份用例）。

★ 2026-09-14 阶段 B：`.sh` 已退役。本矩阵**仍是单一事实源**——golden 按 `case_index` 回指这里，
  改了用例就要重跑 `_dev/freeze_golden.py`（而那需要先从 git 历史取回 `.sh`，见 sh_py_parity.py 头注）。

铁律：**任何用例都不许走到会碰设备的分支**（adb/hdc/scenario_run 真跑）。
每个脚本至少覆盖：PASS 分支 / FAIL(闸红) 分支 / 参数错分支；能用真实工程夹具的另加一例。

case 字段：
  script          脚本名（不带扩展名）
  name            用例名（报告里显示）
  args            传给两边的参数（完全一样）
  fixture_factory 可选，f(tmpdir) 在临时目录里造夹具；两边各拷一份
  env             额外环境变量
  ignore          已知等价豁免的 diff 前缀列表（每条都要在 REPORT_A 写理由）
  requires_fixture 真实工程夹具根（见下）；缺席则该例 skip

★ 真实工程夹具（2026-09-15 阶段 C 改为环境变量，此前是硬编码的本机绝对路径）：
    export VV_PARITY_REAL_PROJECT=/path/to/<鸿蒙工程根>     # 里面要有 spec/
  可指工程根（自动取其 `spec/`），也可直接指 `spec/` 目录本身。
  **不设 / 路径不存在 → 那 8 个「【真实工程】」用例整体 skip**（不报红，也不静默假绿：
  `sh_py_parity --all` 会打 SKIP 行，pytest 侧打 skip reason，都会明说"你少跑了 8 例"）。
  这些用例**只读**工程：夹具工厂只往沙箱里拷/软链，绝不回写。
  golden 里也不落这个绝对路径——写占位符 `<REAL_PROJECT>`（见 REAL_PROJECT_PLACEHOLDER）。
"""
import json
import os


def _w(root, rel, text):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _wj(root, rel, obj):
    return _w(root, rel, json.dumps(obj, ensure_ascii=False, indent=2))


# ── run_scenario_with_verify ──────────────────────────────────────────────
def _fx_walk_debt(d):
    """边遍历模式：首 trip 还有没跑完的 walk → next_walk.py --first-trip-debt 非 0 → exit 31。"""
    _wj(d, "spec/visual-verify/edgewalk/walk_plan.json", {
        "walks": [
            {"walk_id": "walk_0_bootstrap", "trip_id": "trip_1_logged_out",
             "steps": [{"action": "coldstart", "to": "占位页甲"}]},
            {"walk_id": "walk_1_main", "trip_id": "trip_1_logged_out",
             "steps": [{"action": "tap", "from": "占位页甲", "to": "占位页乙", "trigger": "占位入口"}]},
            {"walk_id": "walk_2_after_login", "trip_id": "trip_2_logged_in",
             "steps": [{"action": "coldstart", "to": "占位页甲"}]},
        ]})
    _wj(d, "spec/visual-verify/edgewalk/ledger.json", {"settled": {}})


def _fx_attempt_exhausted(d):
    """自修计数已到上限 → exit 40（不碰设备）。"""
    _wj(d, "spec/visual-verify/progress.json",
        {"scenario_attempts": {"default:占位场景:android": 3}})


def _fx_empty(d):
    pass


# ── check_scratch_pollution ───────────────────────────────────────────────
def _fx_clean(d):
    _w(d, "spec/keep.txt", "占位")


def _fx_polluted(d):
    from PIL import Image
    for n in ("route_甲.jpeg", "route_乙.png", "占位_ui.json"):
        p = os.path.join(d, n)
        if n.endswith(".json"):
            _w(d, n, "{}")
        else:
            Image.new("RGB", (8, 8), (255, 255, 255)).save(p)


def _fx_polluted_one(d):
    _w(d, "占位_ui.json", "{}")


# ── check_functional_dimension ────────────────────────────────────────────
def _tree(n_checks=0):
    pg = {"id": "占位页甲"}
    if n_checks:
        pg["functional_checks"] = [{"id": "fc%d" % i} for i in range(n_checks)]
    return {"schema_version": 1, "source": "x", "app": {}, "features": [],
            "pages": [pg], "fragments": [], "dialogs": [], "flow_graph": {}, "stats": {}}


def _fx_fd_reg_missing(d):
    _wj(d, "tree.json", _tree(0))


def _fx_fd_not_injected(d):
    _wj(d, "tree.json", _tree(0))
    _wj(d, "hm/spec/a2h/functional_registry.json", {"entries": [{"id": "e1"}, {"id": "e2"}]})


def _fx_fd_empty_reg(d):
    _wj(d, "tree.json", _tree(0))
    _wj(d, "hm/spec/a2h/functional_registry.json", {"entries": []})


def _fx_fd_ok(d):
    _wj(d, "tree.json", _tree(3))
    _wj(d, "hm/spec/a2h/functional_registry.json", {"entries": [{"id": "e1"}, {"id": "e2"}]})


# ── inject_factree_refs / inject_spec_oracle ──────────────────────────────
def _fx_factree_full(d):
    _wj(d, "spec/toolkit-fact-tree.json", {
        "pages": [{"id": "占位页甲",
                   "android_source_refs": ["app/src/占位/甲.kt", "app/src/占位/乙.xml"],
                   "screenshots": {"trip_1_logged_out": {"reach_path": ["scenario: login", "click 占位入口"]}}}],
        "fragments": []})


def _fx_factree_bare(d):
    _wj(d, "spec/toolkit-fact-tree.json", {"pages": [{"id": "占位页甲"}], "fragments": []})


def _fx_oracle(d):
    _wj(d, "spec/visual-verify/spec_oracle.json", {
        "page_to_feature": {"占位页甲": "F003"},
        "domain_to_feature": {"同步": "F010"},
        "by_feature": {"F003": {"feature_name": "占位功能丙", "locator": "spec/baseline/features/F003-占位.md#验收标准",
                                "acceptance_snapshot": "- [ ] 占位判据一\n- [ ] 占位判据二"},
                       "F010": {"feature_name": "占位同步", "locator": "spec/baseline/features/F010.md",
                                "acceptance_snapshot": ""}}})


# ── check_blackbox_evidence ───────────────────────────────────────────────
def _fx_bb_none(d):
    _w(d, "spec/keep.txt", "占位")


def _fx_bb_missing_field(d):
    _wj(d, "spec/visual-verify/phase2_batches/chunk_1/manifest.json", {"chunk_id": "chunk_1"})
    _wj(d, "spec/visual-verify/phase2_batches/chunk_2/manifest.json",
        {"chunk_id": "chunk_2", "blackbox_stats": {"pages_explored": 3, "discoveries": 0}})


def _fx_bb_inconsistent(d):
    _wj(d, "spec/visual-verify/phase2_batches/chunk_1/manifest.json",
        {"chunk_id": "chunk_1", "blackbox_stats": {"pages_explored": 5, "discoveries": 2}})


def _fx_bb_ok(d):
    _wj(d, "spec/visual-verify/phase2_batches/chunk_1/manifest.json",
        {"chunk_id": "chunk_1", "blackbox_stats": {"pages_explored": 5, "discoveries": 2}})
    _w(d, "spec/visual-verify/blackbox_discoveries/round-0/占位发现.md", "# 占位")


# ── resize_screenshot / compose_side_by_side ──────────────────────────────
def _img(d, rel, w, h, color=(200, 30, 30)):
    from PIL import Image
    p = os.path.join(d, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    im = Image.new("RGB", (w, h), color)
    for x in range(0, w, 7):            # 加点纹理，防止纯色图缩放后无差别掩盖 bug
        for y in range(0, h, 11):
            im.putpixel((x, y), (10, 10, 250))
    im.save(p)
    return p


def _fx_img_small(d):
    _img(d, "小图.png", 120, 90)


def _fx_img_big(d):
    _img(d, "大图.png", 2400, 1000)


def _fx_two_imgs(d):
    _img(d, "a.png", 300, 600, (220, 220, 220))
    _img(d, "b.png", 280, 640, (180, 200, 220))


# ── gate_experiment ───────────────────────────────────────────────────────
def _fx_gate_no_artifact(d):
    _w(d, "spec/keep.txt", "占位")


def _fx_gate_fast_fail(d):
    _wj(d, "spec/scenarios/artifacts/20260101_120000_占位场景/result.json",
        {"device": "harmonyos", "success": False, "duration_ms": 4200})


def _fx_gate_timeout_like(d):
    _wj(d, "spec/scenarios/artifacts/20260101_120000_占位场景/result.json",
        {"device": "harmonyos", "success": False, "duration_ms": 90000})


# ── lib_resolve_round ─────────────────────────────────────────────────────
def _fx_round_state(d):
    _w(d, "spec/fix/_state.yaml", "current_round: 2\nnote: 占位\n")


def _fx_round_no_state(d):
    _w(d, "spec/keep.txt", "占位")


# ── check_dimension_prereqs ───────────────────────────────────────────────
def _dp_skills(d, with_runner=True, with_fixbuild=False):
    if with_runner:
        _w(d, "skills/arkts-scenario-runner/scripts/scenario_run.py", "# 占位")
    if with_fixbuild:
        _w(d, "skills/hmos-fix-build-errors/SKILL.md", "# 占位")


def _fx_dp_unit_missing(d):
    """UNIT 全缺：无 scenario_run、无 agent（HOME 被隔离到沙箱内）→ exit 2。"""
    _w(d, "home/keep.txt", "占位")


def _fx_dp_spec_never_ran(d):
    """UNIT 齐、a2h-spec 产物整体缺 → exit 3。"""
    _dp_skills(d)
    for a in ("visual-fixer", "visual-fixer-reviewer"):
        _w(d, ".codex/agents/%s.md" % a, "# 占位")
    _w(d, "home/keep.txt", "占位")


def _fx_dp_all_green(d):
    """UNIT 齐 + OPTIONAL 大部分在 → exit 0。"""
    _fx_dp_spec_never_ran(d)
    _dp_skills(d, with_fixbuild=True)
    _w(d, "spec/baseline/ui/page_占位甲.md", "# 占位")
    _w(d, "spec/baseline/features/F001-占位.md", "# 占位")
    _w(d, "spec/baseline/feature-index.md", "# 占位")
    _wj(d, "spec/baseline/dev_info.json", {})
    _wj(d, "spec/visual-verify/page_scenarios.json", {})
    _wj(d, "spec/toolkit-fact-tree.json", {"pages": [{"id": "占位页甲", "functional_checks": []}]})


# ── check_prereq_freshness ────────────────────────────────────────────────
def _rec(rid, **kw):
    r = {"id": rid, "purpose": "占位用途",
         "reach_paths": [["根", "令牌", rid]],
         "navigation_contract": {"trigger_actions": [{"label": "占位入口"}],
                                 "verify_signal": {"text_contains": "占位锚点"}}}
    r.update(kw)
    return r


def _pf_tree(pages, **top):
    t = {"schema_version": 1, "source": "占位", "app": {}, "features": [],
         "pages": pages, "fragments": [], "dialogs": [], "flow_graph": {}, "stats": {}}
    t.update(top)
    return t


def _fx_pf_missing(d):
    _w(d, "spec/keep.txt", "占位")


def _fx_pf_empty_pages(d):
    _wj(d, "spec/toolkit-fact-tree.json", _pf_tree([]))


def _fx_pf_missing_keys(d):
    _wj(d, "spec/toolkit-fact-tree.json", {"pages": [_rec("占位页甲")]})


def _fx_pf_pass(d):
    _wj(d, "spec/toolkit-fact-tree.json", _pf_tree([_rec("占位页甲"), _rec("占位页乙")]))


def _fx_pf_enrich_need(d):
    """navnet/verify 判据全不满足（trigger_actions label 空 + 无 verify_signal）→ NEED 富化。"""
    bad = {"id": "占位页丙", "purpose": None,
           "navigation_contract": {"trigger_actions": [{"label": ""}], "verify_signal": {}}}
    _wj(d, "spec/toolkit-fact-tree.json", _pf_tree([_rec("占位页甲"), bad, dict(bad, id="占位页丁")]))


def _fx_pf_walkability_filter(d):
    """dead/abstract/external_entry + dead_code_hint 必须**不进分母**：
    2 个可走全合格 + 3 个不可走全不合格 → 旧口径 40% 判红，新口径 100% PASS。"""
    dead = [{"id": "占位死甲", "walkability": {"status": "dead"}},
            {"id": "占位抽象", "walkability": {"status": "abstract"}},
            {"id": "占位外部", "walkability": {"status": "external_entry"}},
            {"id": "占位死码", "dead_code_hint": "unreferenced"}]
    _wj(d, "spec/toolkit-fact-tree.json", _pf_tree([_rec("占位页甲"), _rec("占位页乙")] + dead))


def _fx_pf_navnet_kinds(d):
    """navnet 走 inbound_triggers 三条支路：trigger_kind=auto / list_item+view_id / 真文案。"""
    def n(rid, trig):
        return {"id": rid, "purpose": "占位", "reach_paths": [["根", "令牌", rid]],
                "inbound_triggers": [trig],
                "navigation_contract": {"verify_signal": {"view_id": "占位/vid"}}}
    _wj(d, "spec/toolkit-fact-tree.json", _pf_tree([
        n("占位页甲", {"trigger_kind": "auto"}),
        n("占位页乙", {"trigger_kind": "list_item", "trigger_view_id": "占位/item_root"}),
        n("占位页丙", {"trigger_label": "去看看"}),
    ]))


def _fx_pf_navnet_rejected(d):
    """三条**假阳**必须被拒：unknown 文案 / 代码锚点形态 / 容器 view id → navnet 0% 判红。"""
    def n(rid, trig):
        return {"id": rid, "purpose": "占位", "reach_paths": [["根", "令牌", rid]],
                "inbound_triggers": [trig],
                "navigation_contract": {"verify_signal": {"ordinal_in_wizard": 1}}}
    _wj(d, "spec/toolkit-fact-tree.json", _pf_tree([
        n("占位页甲", {"trigger_label": "Unknown入口"}),
        n("占位页乙", {"trigger_label": "com.x.Foo.onClick()"}),
        n("占位页丙", {"trigger_view_id": "占位/main_container"}),
    ]))


def _fx_pf_polarity_need(d):
    """Gate 3.5：login/vip 类前置缺 polarity → NEED（VV_ALLOW_MISSING_POLARITY=1 时降 warn）。"""
    p = _rec("占位页甲")
    p["preconditions"] = [{"kind": "login_required"},
                          {"kind": "vip_required", "polarity": "absent"}]
    q = _rec("占位页乙")
    q["inbound_triggers"] = [{"trigger_label": "去看看",
                              "edge_preconditions": [{"kind": "login_conditional"}]}]
    _wj(d, "spec/toolkit-fact-tree.json", _pf_tree([p, q]))


def _fx_pf_polarity_ok(d):
    p = _rec("占位页甲")
    p["preconditions"] = [{"kind": "login_required", "polarity": "required"},
                          {"kind": "vip_required", "polarity": "absent"},
                          {"kind": "login_required", "disproven": True}]
    _wj(d, "spec/toolkit-fact-tree.json", _pf_tree([p, _rec("占位页乙")]))


def _fx_pf_all_dead(d):
    """全部记录都不可走 → 分母 0：.sh 的 jq 在此除零、stdout 空、bash read 得空串。"""
    _wj(d, "spec/toolkit-fact-tree.json", _pf_tree(
        [{"id": "占位死甲", "walkability": {"status": "dead"}},
         {"id": "占位死乙", "walkability": {"status": "dead"}}]))


def _fx_pf_hybrid(d):
    """hybrid：按 arch 分半取最小覆盖率。xml 半全合格、compose 半全不合格 → 按半最小 0% 判红。"""
    ok = dict(_rec("占位页甲"), arch="xml")
    ok2 = dict(_rec("占位页乙"), arch="xml")
    bad = {"id": "占位页丙", "arch": "compose", "reach_paths": [["根", "令牌", "丙"]],
           "navigation_contract": {"trigger_actions": [{"label": ""}], "verify_signal": {}}}
    _wj(d, "spec/toolkit-fact-tree.json", _pf_tree([ok, ok2, bad]))


# ── walk_finalize ─────────────────────────────────────────────────────────
def _wf_tree():
    def rec(rid, **kw):
        r = {"id": rid, "inbound_triggers": [{"from_page": "占位页甲", "trigger_view_id": "占位/btn",
                                              "runtime": {"verified": True}}],
             "functional_checks": [{"name": "占位检查", "grounded_by": "占位证据"}]}
        r.update(kw)
        return r
    return {"schema_version": 1, "source": "占位", "app": {}, "features": [],
            "pages": [rec("占位页甲"), rec("占位页乙")], "fragments": [], "dialogs": [],
            "flow_graph": {}, "stats": {}}


def _wf_base(d, pending=None, needs_retap=None):
    ew = "spec/visual-verify/edgewalk"
    _wj(d, ew + "/walk_plan.json", {"walks": [
        {"walk_id": "walk_0", "trip_id": "trip_1_logged_out",
         "steps": [{"action": "coldstart", "to": "占位页甲"},
                   {"action": "tap", "from": "占位页甲", "to": "占位页乙", "trigger": "占位入口"}]}]})
    _wj(d, ew + "/edge_results.json", [{"from": "占位页甲", "to": "占位页乙",
                                        "control": {"rid": "占位/btn", "text": "占位入口"},
                                        "result": "ok"}])
    _wj(d, ew + "/ledger.json", {"settled": {"占位页甲": {}, "占位页乙": {}}})
    _wj(d, ew + "/grounding_results.json", [])
    if needs_retap is not None:
        _wj(d, ew + "/needs_retap.json", needs_retap)
    if pending is not None:
        _wj(d, ew + "/pending_bindings.json", pending)
    _wj(d, "spec/toolkit-fact-tree.json", _wf_tree())


def _fx_wf_missing_products(d):
    _wj(d, "spec/toolkit-fact-tree.json", _wf_tree())


def _fx_wf_ok(d):
    _wf_base(d, needs_retap=[])


def _fx_wf_binding_debt(d):
    """2.6 判读债闸：未判 1 笔 + 已判待结 1 笔 → 闸红 exit 20。"""
    _wf_base(d, needs_retap=[], pending=[
        {"node": "占位页丙", "trip": "trip_1_logged_out", "pending_shot": "shots/丙.png"},
        {"node": "占位页丁", "trip": "trip_1_logged_out", "verdict": "bind_as", "applied": False}])


def _fx_wf_binding_clean(d):
    _wf_base(d, needs_retap=[], pending=[
        {"node": "占位页丁", "trip": "trip_1_logged_out", "verdict": "bind_as", "applied": True}])


def _fx_wf_binding_broken(d):
    """pending_bindings.json 读不出来 → 与「有债」同等对待，真拦 exit 20。"""
    _wf_base(d, needs_retap=[])
    _w(d, "spec/visual-verify/edgewalk/pending_bindings.json", "{ 这不是 JSON")


def _fx_wf_retap_debt(d):
    _wf_base(d, needs_retap=[{"node": "占位页甲", "check": "占位检查"}])


# ── 剩余脚本的夹具 ─────────────────────────────────────────────────────────
def _fx_capture_reuse(d):
    """android 端 baseline 已存在 → 复用(exit 1)，不碰设备。"""
    from PIL import Image
    p = os.path.join(d, "spec/visual-verify/screenshots/android/trip_1_logged_out")
    os.makedirs(p, exist_ok=True)
    Image.new("RGB", (8, 8)).save(os.path.join(p, "占位页甲.png"))


def _fx_install_stamp(d):
    _w(d, "hm/spec/visual-verify/cache/install.stamp", "占位戳")


def _cas_tree(pages, **kw):
    t = {"schema_version": 1, "source": "占位", "app": {}, "features": [],
         "pages": pages, "fragments": [], "dialogs": [], "flow_graph": {},
         "stats": {"pages": len(pages)}}
    t.update(kw)
    return t


def _fx_cas_no_tree(d):
    _w(d, "spec/keep.txt", "占位")


def _fx_cas_empty_pages(d):
    _wj(d, "spec/toolkit-fact-tree.json", _cas_tree([]))


def _fx_cas_uncovered(d):
    """有页、无截图 → 覆盖率 0%，闸红。"""
    _wj(d, "spec/toolkit-fact-tree.json", _cas_tree(
        [{"id": "占位页甲"}, {"id": "占位页乙"}]))


def _fx_cas_covered(d):
    from PIL import Image
    _fx_cas_uncovered(d)
    for trip in ("trip_1_logged_out", "trip_2_logged_in_vip"):
        p = os.path.join(d, "spec/visual-verify/screenshots/android", trip)
        os.makedirs(p, exist_ok=True)
        for n in ("占位页甲", "占位页乙"):
            Image.new("RGB", (8, 8)).save(os.path.join(p, n + ".png"))


def _fx_fsc_missing_round(d):
    _w(d, "spec/keep.txt", "占位")


_FSC_BODY = """---
id: {id}
title: 占位标题
source: visual-verify
layer: ui
kind: ALIGN
severity: P2
fixer_layer: ui
page_id: 占位页甲
multimodal_severity: minor
is_migration_bug: true
similarity: 0.82
suggested_files:
  - entry/src/main/ets/占位.ets
evidence:
  - spec/visual-verify/占位证据.png
---

## 1. Spec 引用
> 占位

## 2. 期望
占位

## 3. 实际
占位

## 4. 源码缺口
占位

## 5. 修复建议
占位
"""


def _fx_fsc_pass(d):
    _w(d, "spec/fix/round-0/ui/ALIGN_占位甲.md", _FSC_BODY.format(id="ALIGN_占位甲"))
    _w(d, "spec/visual-verify/占位证据.png", "占位")


def _fx_fsc_fail(d):
    """id 与文件名不一致 + similarity 越界 + evidence 路径不存在 + 指向 replay 工作区。"""
    body = _FSC_BODY.format(id="ALIGN_对不上").replace("similarity: 0.82", "similarity: 7")
    body = body.replace("spec/visual-verify/占位证据.png",
                        "spec/visual-verify/replay/run_占位/shots/占位.png")
    _w(d, "spec/fix/round-0/ui/ALIGN_占位甲.md", body)


def _fx_ars_bare(d):
    _w(d, "spec/keep.txt", "占位")


def _fx_ars_partial(d):
    _wj(d, "spec/visual-verify/progress.json", {"pages": {"占位页甲": {}}})
    _wj(d, "spec/visual-verify/batches.json",
        {"trips": [{"batches": [{"pages": [{"page_id": "占位页甲"}, {"page_id": "占位页乙"}]}]}]})
    _w(d, "spec/fix/_state.yaml", "current_round: 0\n")
    _w(d, "spec/fix/round-0/_index.md", "# 占位")
    _w(d, "spec/fix/round-0/_summary.md", "# 占位")


def _fx_ara_missing(d):
    _w(d, "spec/keep.txt", "占位")


def _fx_ara_no_manifest(d):
    os.makedirs(os.path.join(d, "spec/visual-verify/screenshots/android/trip_1_logged_out"), exist_ok=True)


def _fx_ara_no_canonical(d):
    _fx_ara_no_manifest(d)
    _wj(d, "cap/capture_manifest.json", {"started_at": "2026-09-14T10:00:00", "pages_status": {}})


# ── 真实工程夹具（只读拷贝；缺失则 skip）──────────────────────────────────
# 拿一份真工程的 spec/ 当夹具，验"合成夹具盖不到的规模与形态"
# （MB 级 fact-tree、真 ledger/pending_bindings、真 fix 单）。
# 铁律：**只拷进沙箱、绝不回写真工程**；截图目录用符号链接，且只跑只读/dry-run 分支。
#
# 2026-09-15 阶段 C：路径由硬编码改为环境变量——此前写死 `/Users/<人>/Desktop/...`，
# 换机器上 8 个用例**静默 skip**（有 os.path.isdir 兜底，不红也不吭声），既是本仓
# 唯一一处工程专有绝对路径，也让"少跑了 8 例"看不出来。现在：
#   env 未设 / 路径不存在 → 同样 skip，但 skip 理由里明写环境变量名与例数。
REAL_PROJECT_ENV = "VV_PARITY_REAL_PROJECT"
REAL_PROJECT_PLACEHOLDER = "<REAL_PROJECT>"     # golden 里 requires_fixture 的落盘形态


def real_project_root():
    """真实工程根目录（含 spec/）；未设或不存在 → None。"""
    v = (os.environ.get(REAL_PROJECT_ENV) or "").strip()
    if not v:
        return None
    v = os.path.abspath(os.path.expanduser(v))
    if os.path.isdir(os.path.join(v, "spec")):
        return v
    # 也允许直接指 spec/ 目录本身
    if os.path.isdir(v) and os.path.basename(v) == "spec":
        return os.path.dirname(v)
    return None


def real_spec_root():
    """真实工程的 spec/ 目录；缺席 → None（8 个【真实工程】用例整体 skip）。"""
    r = real_project_root()
    return os.path.join(r, "spec") if r else None


def _cp(src, dst_root, rel):
    import shutil
    s2 = os.path.join(src, *rel.split("/"))
    if not os.path.exists(s2):
        return False
    d2 = os.path.join(dst_root, "spec", *rel.split("/"))
    os.makedirs(os.path.dirname(d2), exist_ok=True)
    if os.path.isdir(s2):
        shutil.copytree(s2, d2, dirs_exist_ok=True)
    else:
        shutil.copy2(s2, d2)
    return True


def _fx_real_tree(d):
    _cp(real_spec_root(), d, "toolkit-fact-tree.json")


def _fx_real_tree_and_shots(d):
    root = real_spec_root()
    _cp(root, d, "toolkit-fact-tree.json")
    # 截图只做**符号链接**（7MB，且本用例只读）
    src = os.path.join(root, "visual-verify", "screenshots", "android")
    dst = os.path.join(d, "spec", "visual-verify", "screenshots", "android")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isdir(src) and not os.path.exists(dst):
        os.symlink(src, dst)


def _fx_real_edgewalk(d):
    root = real_spec_root()
    _cp(root, d, "toolkit-fact-tree.json")
    for f in ("walk_plan.json", "edge_results.json", "ledger.json", "needs_retap.json",
              "pending_bindings.json", "grounding_results.json", "reason_overrides.json"):
        _cp(root, d, "visual-verify/edgewalk/" + f)


def _fx_real_fix_round(d):
    root = real_spec_root()
    _cp(root, d, "fix/_state.yaml")
    _cp(root, d, "fix/round-0")


# ── 用例矩阵 ──────────────────────────────────────────────────────────────
def build_cases():
    cases = []

    # run_scenario_with_verify：4 个分支，全部不碰设备
    cases += [
        {"script": "run_scenario_with_verify", "name": "参数错(缺 device)",
         "args": ["占位场景"], "fixture_factory": _fx_empty,
         # .py 的 usage 行多了 `--trip <trip_id>`（PowerShell 无 `VAR=x cmd` 前缀写法，
         # 2026-08-17 移植时加的**功能超集**）→ stderr 文案必然不同，只对齐退出码/stdout。
         "ignore": ["stderr 不一致"]},
        # ★ 下面两例用 LC_ALL=C 跑：源侧 .sh 第 74 行写的是 `walk（$_DEBT）`——**变量紧贴全角标点没加花括号**，
        #   macOS 自带 bash 3.2 在 UTF-8 locale 下会把「）」的首字节吃进变量名 → `_DEBT?: unbound variable`
        #   → set -u 当场中止，exit 1，闸的文案一个字都没打出来（**这是源侧 .sh 的真 bug，阶段 A 不动 .sh，见 REPORT**）。
        #   LC_ALL=C 下 bash 不做多字节解析，.sh 走出它**本来要走的**分支，两边逐字一致。
        {"script": "run_scenario_with_verify", "name": "顺序闸②边遍历-首trip有债(exit 31)",
         "args": ["login", "android"], "fixture_factory": _fx_walk_debt, "env": {"LC_ALL": "C"}},
        {"script": "run_scenario_with_verify", "name": "顺序闸②边遍历-大小写前缀(LoginAndroid)",
         "args": ["LoginAndroid", "android"], "fixture_factory": _fx_walk_debt, "env": {"LC_ALL": "C"}},
        # 同一分支在 UTF-8 locale 下：记录 .sh 的崩溃行为，证明 .py 修好了它（差异是**已知且期望**的）。
        {"script": "run_scenario_with_verify", "name": "顺序闸②边遍历-UTF8下.sh全角变量崩(已知.sh bug)",
         "args": ["login", "android"], "fixture_factory": _fx_walk_debt,
         "env": {"LC_ALL": "en_US.UTF-8"},
         "ignore": ["退出码", "stderr 不一致"],
         "why": ".sh L74 `$_DEBT）` 未写 ${} → bash3.2+UTF8 吃掉「）」首字节 → unbound variable，exit 1；.py 正确 exit 31"},
        {"script": "run_scenario_with_verify", "name": "自修上限(exit 40)",
         "args": ["占位场景", "android"], "fixture_factory": _fx_attempt_exhausted},
        {"script": "run_scenario_with_verify", "name": "凭据缺失(exit 20)",
         "args": ["sms_login", "android"], "fixture_factory": _fx_empty},
        {"script": "run_scenario_with_verify", "name": "越权开关放行顺序闸后仍被上限拦(exit 40)",
         "args": ["login", "android"], "fixture_factory": _fx_attempt_exhausted,
         "env": {"A2H_SKIP_TRIP1_GATE": "1"}},
    ]

    # check_scratch_pollution（新写，无移植件）
    cases += [
        {"script": "check_scratch_pollution", "name": "PASS-项目根干净", "args": ["."],
         "fixture_factory": _fx_clean},
        {"script": "check_scratch_pollution", "name": "WARN-单文件(exit 1)", "args": ["."],
         "fixture_factory": _fx_polluted_one,
         # 提示行 .sh 指向自己(.sh)、.py 指向自己(.py) → 归一规则已覆盖
         },
        {"script": "check_scratch_pollution", "name": "WARN-三文件(清单只比集合)", "args": ["."],
         "fixture_factory": _fx_polluted, "sort_lines": True},
        {"script": "check_scratch_pollution", "name": "--archive-自动归档(exit 0)", "args": [".", "--archive"],
         "fixture_factory": _fx_polluted, "sort_lines": True},
    ]

    # check_functional_dimension（5 个判定分支 + 参数错）
    cases += [
        {"script": "check_functional_dimension", "name": "参数错(exit 1)", "args": ["tree.json"],
         "fixture_factory": _fx_fd_reg_missing,
         # bash `${2:?usage}` 的报错是 bash 自己打的（`x.sh: line N: 2: usage: ...`），只能对齐退出码
         "ignore": ["stderr 不一致"]},
        {"script": "check_functional_dimension", "name": "树缺(exit 2)", "args": ["无此树.json", "hm"],
         "fixture_factory": _fx_fd_reg_missing},
        {"script": "check_functional_dimension", "name": "registry 未产(exit 2)", "args": ["tree.json", "hm"],
         "fixture_factory": _fx_fd_reg_missing},
        {"script": "check_functional_dimension", "name": "registry 未注入(exit 2)", "args": ["tree.json", "hm"],
         "fixture_factory": _fx_fd_not_injected},
        {"script": "check_functional_dimension", "name": "空 registry 合法跳过(exit 0)", "args": ["tree.json", "hm"],
         "fixture_factory": _fx_fd_empty_reg},
        {"script": "check_functional_dimension", "name": "功能维度就绪(exit 0)", "args": ["tree.json", "hm"],
         "fixture_factory": _fx_fd_ok},
    ]

    # inject_factree_refs
    cases += [
        {"script": "inject_factree_refs", "name": "双注入命中", "args": ["占位页甲", "trip_1_logged_out"],
         "fixture_factory": _fx_factree_full},
        {"script": "inject_factree_refs", "name": "缺 refs/reach 的兜底文案", "args": ["占位页甲", "trip_1_logged_out"],
         "fixture_factory": _fx_factree_bare},
        {"script": "inject_factree_refs", "name": "fact-tree 整份缺", "args": ["占位页甲", "trip_1_logged_out"],
         "fixture_factory": _fx_clean},
        {"script": "inject_factree_refs", "name": "参数错(exit 1)", "args": ["占位页甲"],
         "fixture_factory": _fx_factree_full, "ignore": ["stderr 不一致"]},
    ]

    # inject_spec_oracle
    cases += [
        {"script": "inject_spec_oracle", "name": "page_exact 命中", "args": ["占位页甲"],
         "fixture_factory": _fx_oracle},
        {"script": "inject_spec_oracle", "name": "domain 兜底命中但无验收段", "args": ["无此页", "更多>同步"],
         "fixture_factory": _fx_oracle},
        {"script": "inject_spec_oracle", "name": "全 miss → UNRESOLVED", "args": ["无此页", "无此域"],
         "fixture_factory": _fx_oracle},
        {"script": "inject_spec_oracle", "name": "旁路缺失 → UNRESOLVED", "args": ["占位页甲"],
         "fixture_factory": _fx_clean},
        {"script": "inject_spec_oracle", "name": "参数错(exit 1)", "args": [],
         "fixture_factory": _fx_oracle, "ignore": ["stderr 不一致"]},
    ]

    # check_blackbox_evidence
    cases += [
        {"script": "check_blackbox_evidence", "name": "无 manifest 放行(exit 0)", "args": [],
         "fixture_factory": _fx_bb_none},
        {"script": "check_blackbox_evidence", "name": "缺 blackbox_stats(exit 43)", "args": [],
         "fixture_factory": _fx_bb_missing_field},
        {"script": "check_blackbox_evidence", "name": "stats↔产物不一致(exit 44)", "args": [],
         "fixture_factory": _fx_bb_inconsistent},
        {"script": "check_blackbox_evidence", "name": "PASS(exit 0)", "args": [],
         "fixture_factory": _fx_bb_ok},
    ]

    # resize_screenshot（Pillow 唯一后端；.sh 的 sips/ImageMagick 兜底在 .py 已删，见 REPORT）
    cases += [
        {"script": "resize_screenshot", "name": "文件不存在(警告 exit 0)", "args": ["无此图.png"],
         "fixture_factory": _fx_clean},
        {"script": "resize_screenshot", "name": "缺参数(当文件不存在处理)", "args": [],
         "fixture_factory": _fx_clean},
        {"script": "resize_screenshot", "name": "小图不缩(无输出 exit 0)", "args": ["小图.png"],
         "fixture_factory": _fx_img_small},
        {"script": "resize_screenshot", "name": "大图缩到 1800", "args": ["大图.png"],
         "fixture_factory": _fx_img_big},
        {"script": "resize_screenshot", "name": "自定义 max_dim", "args": ["大图.png", "600"],
         "fixture_factory": _fx_img_big},
    ]

    # compose_side_by_side
    cases += [
        # ★ 产物字节必然不同，且是 **.py 更对**：.sh 写死 `/System/Library/Fonts/PingFang.ttc`，
        #   该字体在 macOS 15+ 已不存在 → .sh 一路回落到 ImageFont.load_default()（6px 位图字，
        #   标签带几乎不可读）；lib_image._cjk_font 按平台候选，命中 STHeiti Light.ttc 正常画 28px。
        #   实测差异**只在标签带**（y 16..48），画布尺寸与两张图的粘贴区逐像素相同——
        #   由 test_compose_only_label_band_differs 单独断言。
        {"script": "compose_side_by_side", "name": "默认标签拼图", "args": ["a.png", "b.png", "out.jpeg"],
         "fixture_factory": _fx_two_imgs, "ignore": ["产物 out.jpeg"],
         "why": ".sh 的 PingFang.ttc 在 macOS 15+ 不存在 → 回落 load_default；.py 命中 STHeiti，仅标签带不同"},
        {"script": "compose_side_by_side", "name": "自定义标签", "args": ["a.png", "b.png", "out.jpeg", "安卓 | 鸿蒙"],
         "fixture_factory": _fx_two_imgs, "ignore": ["产物 out.jpeg"],
         "why": "同上"},
        {"script": "compose_side_by_side", "name": "参数错(exit 1)", "args": ["a.png", "b.png"],
         "fixture_factory": _fx_two_imgs},
    ]

    # gate_experiment（不给 --android-id/--hmos-id → 健康检查短路，不碰设备）
    cases += [
        {"script": "gate_experiment", "name": "参数错-未知参数(exit 3)", "args": ["--nope"],
         "fixture_factory": _fx_gate_no_artifact},
        {"script": "gate_experiment", "name": "参数错-缺必填(exit 3)", "args": ["--scenario", "占位场景"],
         "fixture_factory": _fx_gate_no_artifact},
        {"script": "gate_experiment", "name": "无 artifact → unknown + environment",
         "args": ["--scenario", "占位场景", "--failed-device", "harmonyos", "--skip-other-replay"],
         "fixture_factory": _fx_gate_no_artifact},
        {"script": "gate_experiment", "name": "fast_fail 形态",
         "args": ["--scenario", "占位场景", "--failed-device", "harmonyos", "--skip-other-replay"],
         "fixture_factory": _fx_gate_fast_fail},
        {"script": "gate_experiment", "name": "timeout_like 形态",
         "args": ["--scenario", "占位场景", "--failed-device", "harmonyos", "--skip-other-replay"],
         "fixture_factory": _fx_gate_timeout_like},
        {"script": "gate_experiment", "name": "FAST_FAIL_MS 阈值可调",
         "args": ["--scenario", "占位场景", "--failed-device", "harmonyos", "--skip-other-replay"],
         "fixture_factory": _fx_gate_fast_fail, "env": {"FAST_FAIL_MS": "1000"}},
    ]

    # lib_resolve_round（.sh 是**只能 source 的 lib**，用 cmd_sh 包一层拿到同一语义）
    cases += [
        {"script": "lib_resolve_round", "name": "显式传 round 优先", "args": ["round_7"],
         "fixture_factory": _fx_round_state,
         "cmd_sh": ["bash", "-c", 'source "$0" && resolve_round "$1"', "{SH}", "{ARGS1}"]},
        # .sh 用 `yq` 读 _state.yaml，本机没装 yq → .sh 只能报"yq 未装"(exit 1)；
        # .py 用 PyYAML/退化正则读，正常返回 2(exit 0)。**这是有意的去 yq 依赖**（Windows 原生要求），
        # 装了 yq 的机器上两者一致。差异已知，退出码与文案都列进 REPORT。
        {"script": "lib_resolve_round", "name": "从 _state.yaml 读 current_round(.sh 需 yq)", "args": [],
         "fixture_factory": _fx_round_state,
         "cmd_sh": ["bash", "-c", 'source "$0" && resolve_round ""', "{SH}"],
         "ignore": ["退出码", "stdout 不一致", "stderr 不一致"],
         "why": ".sh 依赖 yq（本机未装）；.py 去 yq 依赖用 PyYAML/正则。装了 yq 才可能逐字一致"},
        # .sh 缺 _state.yaml 时先撞 `command -v yq` → 文案是"未传 round_N 且 yq 未装"；
        # .py 去了 yq 依赖，直接报"无 current_round"。**两者退出码同为 1**，文案不同（见 REPORT）。
        {"script": "lib_resolve_round", "name": "无 _state.yaml(exit 1，文案不同)", "args": [],
         "fixture_factory": _fx_round_no_state,
         "cmd_sh": ["bash", "-c", 'source "$0" && resolve_round ""', "{SH}"],
         "ignore": ["stderr 不一致"],
         "why": ".sh 先查 yq 再读文件；.py 无 yq 依赖直接读文件。退出码同为 1"},
    ]

    # check_dimension_prereqs（HOME 隔离到沙箱内，避免命中开发机真实的 ~/.agents/agents）
    _HOME = {"HOME": "{ROOT}/home", "USERPROFILE": "{ROOT}/home", "CLAUDE_PROJECT_DIR": "{ROOT}"}
    cases += [
        {"script": "check_dimension_prereqs", "name": "参数错-未知参数(exit 64)", "args": ["--nope"],
         "fixture_factory": _fx_dp_unit_missing, "env": _HOME},
        {"script": "check_dimension_prereqs", "name": "参数错-缺 --project-root(exit 64)", "args": [],
         "fixture_factory": _fx_dp_unit_missing, "env": _HOME},
        {"script": "check_dimension_prereqs", "name": "UNIT 全缺(exit 2)",
         "args": ["--project-root", ".", "--skills-root", "skills"],
         "fixture_factory": _fx_dp_unit_missing, "env": _HOME},
        {"script": "check_dimension_prereqs", "name": "UNIT 齐但 a2h-spec 从没跑过(exit 3)",
         "args": ["--project-root", ".", "--skills-root", "skills"],
         "fixture_factory": _fx_dp_spec_never_ran, "env": _HOME},
        # ★ LC_ALL=C：源侧 .sh 第 87 行 `× $PAGE_MD_N，Step 1.0.5` —— 变量紧贴全角逗号没加 ${}，
        #   bash 3.2 + UTF-8 locale 把「，」首字节吃进变量名 → `PAGE_MD_N?: unbound variable`，
        #   set -u 当场中止 → **OPTIONAL 表一行都打不出、exit 0/3 永远到不了**（源侧 .sh 真 bug，见 REPORT）。
        #   这行是 0817 之后的改动引入的（基线版写的是 `${PAGE_MD_N}`）。
        {"script": "check_dimension_prereqs", "name": "全绿(exit 0)",
         "args": ["--project-root", ".", "--skills-root", "skills"],
         "fixture_factory": _fx_dp_all_green, "env": dict(_HOME, LC_ALL="C")},
        {"script": "check_dimension_prereqs", "name": "UTF8 下 .sh 全角变量崩(已知 .sh bug)",
         "args": ["--project-root", ".", "--skills-root", "skills"],
         "fixture_factory": _fx_dp_all_green, "env": dict(_HOME, LC_ALL="en_US.UTF-8"),
         "ignore": ["退出码", "stdout 不一致", "stderr 不一致"],
         "why": ".sh L87 `$PAGE_MD_N，` 未写 ${} → bash3.2+UTF8 unbound variable，exit 1；.py 正常 exit 0"},
    ]

    # check_prereq_freshness（0908/0909 三处判据口径是本次追平的重点，逐条穿刺）
    cases += [
        {"script": "check_prereq_freshness", "name": "树缺(NEED:both)", "args": [],
         "fixture_factory": _fx_pf_missing},
        {"script": "check_prereq_freshness", "name": "树缺-compose(NEED:compose-fact-tree)",
         "args": ["--arch", "pure_compose"], "fixture_factory": _fx_pf_missing},
        {"script": "check_prereq_freshness", "name": "pages 空(NEED:toolkit-fact-indexer)", "args": [],
         "fixture_factory": _fx_pf_empty_pages},
        {"script": "check_prereq_freshness", "name": "顶层键缺(NEED:toolkit-fact-indexer)", "args": [],
         "fixture_factory": _fx_pf_missing_keys},
        {"script": "check_prereq_freshness", "name": "PASS", "args": [],
         "fixture_factory": _fx_pf_pass},
        {"script": "check_prereq_freshness", "name": "富化不足(NEED:app-relationship-tree)", "args": [],
         "fixture_factory": _fx_pf_enrich_need},
        {"script": "check_prereq_freshness", "name": "★0909 walkability 剔除出分母 → PASS", "args": [],
         "fixture_factory": _fx_pf_walkability_filter},
        {"script": "check_prereq_freshness", "name": "★0908/09 navnet 三支路(auto/list_item/真文案) → PASS",
         "args": [], "fixture_factory": _fx_pf_navnet_kinds},
        {"script": "check_prereq_freshness", "name": "★0908 navnet 拒假阳(unknown/代码锚点/容器id)",
         "args": [], "fixture_factory": _fx_pf_navnet_rejected},
        {"script": "check_prereq_freshness", "name": "★0909 Gate3.5 极性缺 → NEED", "args": [],
         "fixture_factory": _fx_pf_polarity_need},
        {"script": "check_prereq_freshness", "name": "★0909 Gate3.5 越权放行(降 warn)", "args": [],
         "fixture_factory": _fx_pf_polarity_need, "env": {"VV_ALLOW_MISSING_POLARITY": "1"}},
        {"script": "check_prereq_freshness", "name": "★0909 Gate3.5 极性齐全 + disproven 不计", "args": [],
         "fixture_factory": _fx_pf_polarity_ok},
        {"script": "check_prereq_freshness", "name": "分母 0（全不可走）—— jq 除零行为复刻", "args": [],
         "fixture_factory": _fx_pf_all_dead},
        {"script": "check_prereq_freshness", "name": "hybrid 按半最小覆盖率", "args": ["--arch", "hybrid"],
         "fixture_factory": _fx_pf_hybrid},
    ]

    # walk_finalize（本次追平最大一块：2.6 判读债闸 / 5.5 reach_path / 5.7 / 5.8 / 6.5 / 计时）
    # 全部走 --dry-run 或早退分支，绝不落到 walk_place_baselines 的设备/文件搬运。
    cases += [
        {"script": "walk_finalize", "name": "缺 --trip(exit 2)", "args": [],
         "fixture_factory": _fx_wf_ok},
        {"script": "walk_finalize", "name": "未知参数(exit 2)", "args": ["--nope"],
         "fixture_factory": _fx_wf_ok},
        {"script": "walk_finalize", "name": "产物不齐(exit 2)", "args": ["--trip", "trip_1_logged_out"],
         "fixture_factory": _fx_wf_missing_products},
        {"script": "walk_finalize", "name": "★2.6 判读债未结(exit 20)",
         "args": ["--trip", "trip_1_logged_out", "--dry-run"],
         "fixture_factory": _fx_wf_binding_debt},
        {"script": "walk_finalize", "name": "★2.6 判读债已结清 → 放行",
         "args": ["--trip", "trip_1_logged_out", "--dry-run"],
         "fixture_factory": _fx_wf_binding_clean},
        {"script": "walk_finalize", "name": "★2.6 pending_bindings 读不出来 → 真拦(exit 20)",
         "args": ["--trip", "trip_1_logged_out", "--dry-run"],
         "fixture_factory": _fx_wf_binding_broken, "norm_traceback": True,
         "why": ".sh 的 python 是 heredoc（帧 `File \"<stdin>\", line 4`），.py 是真文件（带函数名+源码行）；"
                "帧明细必然不同，折成 <FRAME> 后异常类型/判定行/退出码逐字一致"},
        {"script": "walk_finalize", "name": "★2.6 带债豁免 --accept-binding-debt",
         "args": ["--trip", "trip_1_logged_out", "--dry-run", "--accept-binding-debt"],
         "fixture_factory": _fx_wf_binding_debt},
        {"script": "walk_finalize", "name": "无 pending_bindings.json → ✓",
         "args": ["--trip", "trip_1_logged_out", "--dry-run"],
         "fixture_factory": _fx_wf_ok},
        {"script": "walk_finalize", "name": "needs_retap 未结(exit 20)",
         "args": ["--trip", "trip_1_logged_out", "--dry-run"],
         "fixture_factory": _fx_wf_retap_debt},
        {"script": "walk_finalize", "name": "★全流程落盘（5.5 reach_path/5.7/5.8/6.5/计时 全跑）",
         "args": ["--trip", "trip_1_logged_out", "--walk-id", "walk_edge_占位"],
         "fixture_factory": _fx_wf_ok},
    ]

    # capture_or_reuse（只覆盖不碰设备的分支：参数错 / 平台错 / baseline 复用 / HMOS 闸）
    cases += [
        {"script": "capture_or_reuse", "name": "参数不足(exit 3)", "args": ["android", "占位设备"],
         "fixture_factory": _fx_capture_reuse},
        {"script": "capture_or_reuse", "name": "未知平台(exit 3)",
         "args": ["ios", "占位设备", "占位页甲", "trip_1_logged_out"],
         "fixture_factory": _fx_capture_reuse},
        {"script": "capture_or_reuse", "name": "android baseline 复用(exit 1)",
         "args": ["android", "占位设备", "占位页甲", "trip_1_logged_out"],
         "fixture_factory": _fx_capture_reuse},
        {"script": "capture_or_reuse", "name": "HMOS 被安卓基线闸拦(exit 9)",
         "args": ["harmony", "占位设备", "占位页甲", "trip_1_logged_out"],
         "fixture_factory": _fx_capture_reuse},
    ]

    # auto_install_artifacts（构建/装机要设备，只覆盖参数与戳分支）
    cases += [
        {"script": "auto_install_artifacts", "name": "未知参数(exit 2)", "args": ["--nope"],
         "fixture_factory": _fx_install_stamp},
        {"script": "auto_install_artifacts", "name": "--clear-stamp 缺 --hmos-root(exit 2)",
         "args": ["--clear-stamp"], "fixture_factory": _fx_install_stamp},
        {"script": "auto_install_artifacts", "name": "--clear-stamp 清戳(exit 0)",
         "args": ["--clear-stamp", "--hmos-root", "hm"], "fixture_factory": _fx_install_stamp},
        # ★ LC_ALL=C：.sh L90 `$hvigorw（可用 …）` 同族全角变量 bug（set -uo pipefail → 崩）
        {"script": "auto_install_artifacts", "name": "--rebuild 找不到 hvigorw",
         "args": ["--rebuild", "--hmos-root", "hm"], "fixture_factory": _fx_install_stamp,
         "env": {"HVIGORW": "/占位/不存在/hvigorw", "LC_ALL": "C"}},
        {"script": "auto_install_artifacts", "name": "UTF8 下 .sh 全角变量崩(已知 .sh bug)",
         "args": ["--rebuild", "--hmos-root", "hm"], "fixture_factory": _fx_install_stamp,
         "env": {"HVIGORW": "/占位/不存在/hvigorw", "LC_ALL": "en_US.UTF-8"},
         "ignore": ["退出码", "stdout 不一致", "stderr 不一致", "删除的文件不一致"],
         "why": ".sh L90 `$hvigorw（` 未写 ${} → bash3.2+UTF8 unbound variable，崩在清戳之前"},
    ]

    # check_android_screenshot
    # ★ LC_ALL=C：.sh 用 `sort -u` / `comm -23` 做页集合运算却**没有** `export LC_ALL=C`
    #   （assert_replay_artifacts.sh 2026-07-25 已为同一个坑加过这道保险，这里漏了）。
    #   macOS 的 en_US.UTF-8 collation 下 `sort -u` 会把不同的中文页名判成相等并吃掉
    #   （实测 `设置页`/`关于页` → 只剩一个）⇒ **分母塌缩、覆盖率虚高、闸假绿**。见 REPORT。
    cases += [
        {"script": "check_android_screenshot", "name": "树缺(exit 3)", "args": [],
         "fixture_factory": _fx_cas_no_tree},
        {"script": "check_android_screenshot", "name": "pages 空(exit 3)", "args": [],
         "fixture_factory": _fx_cas_empty_pages},
        {"script": "check_android_screenshot", "name": "覆盖率 0（闸红）", "args": [],
         "fixture_factory": _fx_cas_uncovered, "env": {"LC_ALL": "C"}, "sort_lines": True},
        {"script": "check_android_screenshot", "name": "两 trip 全覆盖", "args": [],
         "fixture_factory": _fx_cas_covered, "env": {"LC_ALL": "C"}},
        {"script": "check_android_screenshot", "name": "UTF8 下 .sh 页集合塌缩(已知 .sh bug)", "args": [],
         "fixture_factory": _fx_cas_covered, "env": {"LC_ALL": "en_US.UTF-8"},
         "ignore": ["stdout 不一致", "stderr 不一致", "退出码"],
         "why": ".sh 缺 LC_ALL=C，macOS sort -u 把不同中文页名判等 → 分母 2 塌成 1，覆盖率虚高；.py 用集合无此问题"},
    ]

    # run_fix_self_check（round 显式传参，避开 .sh 的 yq 依赖）
    cases += [
        {"script": "run_fix_self_check", "name": "round 目录不存在(exit 2)", "args": ["0"],
         "fixture_factory": _fx_fsc_missing_round},
        {"script": "run_fix_self_check", "name": "PASS", "args": ["0"],
         "fixture_factory": _fx_fsc_pass},
        {"script": "run_fix_self_check", "name": "多项不合规(exit 1)", "args": ["0"],
         "fixture_factory": _fx_fsc_fail, "sort_lines": True},
    ]

    # assert_run_success（同样缺 LC_ALL=C 保险，cond1 的 comm -23 会塌缩中文页名 → 走 C collation 对比）
    cases += [
        {"script": "assert_run_success", "name": "光板项目(全 cond 缺)", "args": ["0"],
         "fixture_factory": _fx_ars_bare, "env": {"LC_ALL": "C"}},
        {"script": "assert_run_success", "name": "部分产物齐（cond1 warn）", "args": ["0"],
         "fixture_factory": _fx_ars_partial, "env": {"LC_ALL": "C"}},
    ]

    # assert_replay_artifacts
    cases += [
        {"script": "assert_replay_artifacts", "name": "安卓基线目录缺(exit 2)",
         "args": [".", "0", "trip_1_logged_out", "cap", "plan.json"],
         "fixture_factory": _fx_ara_missing},
        {"script": "assert_replay_artifacts", "name": "capture_manifest 缺(exit 2)",
         "args": [".", "0", "trip_1_logged_out", "cap", "plan.json"],
         "fixture_factory": _fx_ara_no_manifest},
        {"script": "assert_replay_artifacts", "name": "canonical 鸿蒙目录缺(exit 1)",
         "args": [".", "0", "trip_1_logged_out", "cap", "plan.json"],
         "fixture_factory": _fx_ara_no_canonical},
        {"script": "assert_replay_artifacts", "name": "参数错(缺 round)", "args": ["."],
         "fixture_factory": _fx_ara_no_canonical, "ignore": ["stderr 不一致"]},
    ]

    # reverify_transaction（真跑要 hdc/hvigorw，只覆盖参数错与降级分支）
    cases += [
        {"script": "reverify_transaction", "name": "未知参数(exit 2)", "args": ["--nope"],
         "fixture_factory": _fx_clean},
        {"script": "reverify_transaction", "name": "缺必填(exit 2)",
         "args": ["--project-root", "."], "fixture_factory": _fx_clean},
    ]

    # dismiss_popups（全部真活都要设备，只能覆盖参数错闸）
    cases += [
        {"script": "dismiss_popups", "name": "参数错-缺 device/platform(exit 3)", "args": [],
         "fixture_factory": _fx_clean},
        {"script": "dismiss_popups", "name": "参数错-未知参数(exit 3)", "args": ["--nope"],
         "fixture_factory": _fx_clean},
    ]

    # run_phase2_android_survey / dispatch_phase2_batches（ANDROID_SERIAL 显式给，避免摸 adb）
    _SER = {"ANDROID_SERIAL": "占位serial"}
    cases += [
        {"script": "run_phase2_android_survey", "name": "未知参数(exit 1)", "args": ["--nope"],
         "fixture_factory": _fx_cas_no_tree, "env": _SER},
        {"script": "run_phase2_android_survey", "name": "fact-tree 缺(exit 1)", "args": ["--plan-only"],
         "fixture_factory": _fx_cas_no_tree, "env": _SER},
        {"script": "dispatch_phase2_batches", "name": "--plan-only（无树）", "args": ["--plan-only"],
         "fixture_factory": _fx_cas_no_tree, "env": _SER},
        {"script": "dispatch_phase2_batches", "name": "--plan-only（有树）", "args": ["--plan-only"],
         "fixture_factory": _fx_cas_uncovered, "env": _SER},
    ]

    # ── 真实工程夹具（缺就 skip）──────────────────────────────────────────
    # ★ 这 8 例**恒定在矩阵里**（不再按夹具在不在场增删）：golden 靠 `case_index` 回指本矩阵，
    #   条目数随环境变量变 = 换台机器所有 golden 全部错位。夹具缺席由 runner 显式 skip 承担。
    _REAL = real_spec_root() or REAL_PROJECT_PLACEHOLDER
    if True:
        cases += [
            {"script": "check_prereq_freshness", "name": "【真实工程】1.8MB fact-tree 判据", "args": [],
             "fixture_factory": _fx_real_tree, "requires_fixture": _REAL},
            {"script": "check_android_screenshot", "name": "【真实工程】真基线覆盖率", "args": [],
             "fixture_factory": _fx_real_tree_and_shots, "requires_fixture": _REAL,
             "env": {"LC_ALL": "C"}, "sort_lines": True},
            {"script": "check_functional_dimension", "name": "【真实工程】功能维度",
             "args": ["spec/toolkit-fact-tree.json", "."],
             "fixture_factory": _fx_real_tree, "requires_fixture": _REAL},
            {"script": "walk_finalize", "name": "【真实工程】收尾闸 dry-run（真 pending_bindings/ledger）",
             "args": ["--trip", "trip_1_logged_out", "--dry-run"],
             "fixture_factory": _fx_real_edgewalk, "requires_fixture": _REAL,
             "norm_traceback": True},
            {"script": "run_fix_self_check", "name": "【真实工程】round-0 真单自检", "args": ["0"],
             "fixture_factory": _fx_real_fix_round, "requires_fixture": _REAL,
             "env": {"LC_ALL": "C"}, "sort_lines": True},
            {"script": "assert_run_success", "name": "【真实工程】整轮兜底", "args": ["0"],
             "fixture_factory": _fx_real_fix_round, "requires_fixture": _REAL,
             "env": {"LC_ALL": "C"}, "sort_lines": True},
            {"script": "dispatch_phase2_batches", "name": "【真实工程】--plan-only", "args": ["--plan-only"],
             "fixture_factory": _fx_real_tree, "requires_fixture": _REAL,
             "env": {"ANDROID_SERIAL": "占位serial"}},
            {"script": "check_scratch_pollution", "name": "【真实工程】收口卫生", "args": ["."],
             "fixture_factory": _fx_real_tree, "requires_fixture": _REAL},
        ]

    return cases


if __name__ == "__main__":
    for c in build_cases():
        print(c["script"], "|", c.get("name"), "|", c.get("args"))
