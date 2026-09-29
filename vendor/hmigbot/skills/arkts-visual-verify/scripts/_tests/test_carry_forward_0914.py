#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""carry_forward.py + render_round_summary.py 的 _delta 单测（2026-09-14，合成 fixture，无工程依赖）。

覆盖：三层目录 / pending_* 原样保留 / partial 原样保留 / 幂等 / legacy 前缀输入 /
      fixed 不结转 / delta 四类 + still_open / 两种目录形态（规范 vs legacy）结果一致。

运行：python3 -m pytest scripts/_tests/test_carry_forward_0914.py -q
     或 python3 scripts/_tests/test_carry_forward_0914.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SC = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, SC)
PY = sys.executable

import carry_forward as cf                                      # noqa: E402


# ── fixture 工具 ───────────────────────────────────────────────────────────
def ticket(root, rnd, layer, name, *, tid=None, page="PX", disposition="null",
           reason=None, set_at=None, extra="", body="正文段落\n\n### round-0 attempt by visual-fixer\n改了 A\n"):
    d = os.path.join(root, f"spec/fix/round-{rnd}/{layer}")
    os.makedirs(d, exist_ok=True)
    fm = [f"id: {tid or name}", f'title: "[{page}] {name}"', "source: visual-verify",
          f"layer: {'feat' if layer == 'feat' else 'ui'}", "kind: ALIGNMENT_DIFF", "severity: P1",
          f"page_id: {page}", "fixer_layer: ui", "suggested_files:", "  - a.ets",
          "evidence:", "  - shots/a.png", f"disposition: {disposition}"]
    if reason is not None:
        fm.append(f'disposition_reason: "{reason}"')
    if set_at is not None:
        fm.append(f"disposition_set_at_round: {set_at}")
    if extra:
        fm.append(extra)
    p = os.path.join(d, name + ".md")
    open(p, "w", encoding="utf-8").write("---\n" + "\n".join(fm) + "\n---\n\n" + body)
    return p


def run_cf(root, rnd, *args):
    p = subprocess.run([PY, os.path.join(SC, "carry_forward.py"), "--fix-dir",
                        os.path.join(root, "spec/fix"), "--round", str(rnd), "--json", *args],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def names(root, rnd, layer):
    d = os.path.join(root, f"spec/fix/round-{rnd}/{layer}")
    return sorted(f for f in os.listdir(d) if f.endswith(".md")) if os.path.isdir(d) else []


def fm_of(root, rnd, layer, base):
    p = os.path.join(root, f"spec/fix/round-{rnd}/{layer}", base)
    return cf.parse_frontmatter(open(p, encoding="utf-8").read())


def snapshot(d):
    out = {}
    for dp, _dn, fns in os.walk(d):
        for f in fns:
            fp = os.path.join(dp, f)
            out[os.path.relpath(fp, d)] = open(fp, encoding="utf-8", errors="replace").read()
    return out


# ── 1. 三层目录 + fixed 不结转 + pending/partial 保留 ──────────────────────
def _mk_three_layer(root):
    ticket(root, 0, "ui", "ALIGN_A", page="PA")                                   # null → 带
    ticket(root, 0, "ui", "ALIGN_B", page="PB", disposition="fixed", set_at=0)     # fixed → 不带
    ticket(root, 0, "ui", "ALIGN_C", page="PC", disposition="partial",
           reason="fixer 改了待重测", set_at=0)                                    # partial → 原样带
    ticket(root, 0, "ui", "ALIGN_D", page="PD", disposition="manual_review", set_at=0)
    ticket(root, 0, "ui", "ALIGN_E", page="PE", disposition="problematic", set_at=0)
    ticket(root, 0, "ui", "ALIGN_F", page="PF", disposition="skipped", set_at=0)
    ticket(root, 0, "ui", "BLOCKED_PG", page="PG", disposition="pending_upstream_fix",
           reason="上游未修", set_at=0, extra="blocked_by: spec/fix/round-0/ui/CRASH_X.md")
    ticket(root, 0, "feat", "FEAT_H", page="PH")
    ticket(root, 0, "feat", "FEAT_I", page="PI", disposition="fixed", set_at=0)
    ticket(root, 0, "ui/_systemic", "SYSTEMIC_J", page="PJ")
    ticket(root, 0, "ui/_systemic", "SYSTEMIC_K", page="PK", disposition="fixed", set_at=0)


def test_three_layers_and_closed_filter():
    root = tempfile.mkdtemp()
    try:
        _mk_three_layer(root)
        res = run_cf(root, 1)
        assert set(res["layers"]) == {"ui", "feat", "ui/_systemic"}, res["layers"]
        assert names(root, 1, "ui") == ["ALIGN_A.md", "ALIGN_C.md", "BLOCKED_PG.md"]
        assert names(root, 1, "feat") == ["FEAT_H.md"]
        assert names(root, 1, "ui/_systemic") == ["SYSTEMIC_J.md"]
        assert res["carried"] == 5 and res["skipped"] == 6, res
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_pending_and_partial_preserved_verbatim():
    root = tempfile.mkdtemp()
    try:
        _mk_three_layer(root)
        run_cf(root, 1)
        g = fm_of(root, 1, "ui", "BLOCKED_PG.md")
        assert g["disposition"] == "pending_upstream_fix"
        assert g["disposition_reason"] == "上游未修"
        assert str(g["disposition_set_at_round"]) == "0"
        assert g["blocked_by"] == "spec/fix/round-0/ui/CRASH_X.md"
        c = fm_of(root, 1, "ui", "ALIGN_C.md")
        assert c["disposition"] == "partial" and c["disposition_reason"] == "fixer 改了待重测"
        # §6 正文原样
        src = open(os.path.join(root, "spec/fix/round-0/ui/ALIGN_C.md"), encoding="utf-8").read()
        dst = open(os.path.join(root, "spec/fix/round-1/ui/ALIGN_C.md"), encoding="utf-8").read()
        assert src.split("\n---\n", 1)[1] == dst.split("\n---\n", 1)[1]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_filename_equals_id_and_carried_fields():
    root = tempfile.mkdtemp()
    try:
        _mk_three_layer(root)
        run_cf(root, 1)
        for layer in ("ui", "feat", "ui/_systemic"):
            for b in names(root, 1, layer):
                fm = fm_of(root, 1, layer, b)
                assert fm["id"] == b[:-3], (layer, b, fm["id"])
                assert str(fm["carried_from_round"]) == "0"
                assert fm["carried_rounds"] == ["0"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_idempotent_and_multi_round_accumulates():
    root = tempfile.mkdtemp()
    try:
        _mk_three_layer(root)
        run_cf(root, 1)
        first = snapshot(os.path.join(root, "spec/fix/round-1"))
        run_cf(root, 1)
        assert snapshot(os.path.join(root, "spec/fix/round-1")) == first, "重复跑不幂等"
        # 二次结转：round-1 → round-2，名字不叠加前缀，carried_rounds 累加
        run_cf(root, 2)
        assert names(root, 2, "ui") == ["ALIGN_A.md", "ALIGN_C.md", "BLOCKED_PG.md"]
        assert fm_of(root, 2, "ui", "ALIGN_A.md")["carried_rounds"] == ["0", "1"]
        assert str(fm_of(root, 2, "ui", "ALIGN_A.md")["carried_from_round"]) == "1"
        run_cf(root, 2)
        assert fm_of(root, 2, "ui", "ALIGN_A.md")["carried_rounds"] == ["0", "1"], "幂等失败：轮号重复追加"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dry_run_writes_nothing():
    root = tempfile.mkdtemp()
    try:
        _mk_three_layer(root)
        res = run_cf(root, 1, "--dry-run")
        assert res["carried"] == 5
        assert names(root, 1, "ui") == []
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_no_prev_round_is_noop():
    root = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(root, "spec/fix"))
        res = run_cf(root, 0)
        assert res["carried"] == 0 and "note" in res
        res = run_cf(root, 5)
        assert res["carried"] == 0 and "note" in res
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ── 2. legacy 前缀输入 ─────────────────────────────────────────────────────
def test_legacy_prefix_inputs_land_as_canonical_names():
    root = tempfile.mkdtemp()
    try:
        # legacy 反向补丁形态：id 跟文件名走，真实 id 存 carried_from_id
        ticket(root, 0, "ui", "CARRYOVER_ALIGN_A_from_r0", page="PA",
               extra="carried_from_id: ALIGN_A")
        # legacy 无 carried_from_id：靠剥前后缀还原
        ticket(root, 0, "ui", "CARRYOVER_ALIGN_B_from_r0", tid="ALIGN_B", page="PB")
        # 叠加前缀
        ticket(root, 0, "ui", "CARRYOVER_CARRYOVER_ALIGN_C_from_r0", tid="ALIGN_C", page="PC")
        # RESOLVED_ = 已收口，即便 disposition 没写 fixed 也不结转
        ticket(root, 0, "ui", "RESOLVED_ALIGN_D", tid="ALIGN_D", page="PD")
        ticket(root, 0, "ui", "CARRYOVER_BLOCKED_PE_from_r0", tid="BLOCKED_PE", page="PE",
               disposition="pending_precondition", set_at=0)
        res = run_cf(root, 1)
        assert names(root, 1, "ui") == ["ALIGN_A.md", "ALIGN_B.md", "ALIGN_C.md", "BLOCKED_PE.md"], names(root, 1, "ui")
        for b in names(root, 1, "ui"):
            fm = fm_of(root, 1, "ui", b)
            assert fm["id"] == b[:-3]
            assert "carried_from_id" not in fm, "legacy carried_from_id 未清理"
        # BLOCKED 占位恢复成 lib_ledger / build_batch_manifest 认得的字面名
        import lib_ledger
        assert lib_ledger.blocked_placeholders(os.path.join(root, "spec/fix/round-1")) == {"E"}
        assert res["skipped"] == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_id_conflict_is_reported_not_silent():
    root = tempfile.mkdtemp()
    try:
        ticket(root, 0, "ui", "ALIGN_A", page="PA")
        ticket(root, 0, "ui", "CARRYOVER_ALIGN_A_from_r0", tid="ALIGN_A", page="PA")
        res = run_cf(root, 1)
        assert len(res["conflicts"]) == 1 and res["conflicts"][0]["id"] == "ALIGN_A"
        assert names(root, 1, "ui") == ["ALIGN_A.md"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_norm_id_pure():
    assert cf.norm_id("CARRYOVER_X_from_r12.md") == "X"
    assert cf.norm_id("CARRYOVER_CARRYOVER_X_from_r0") == "X"
    assert cf.norm_id("RESOLVED_X.md") == "X"
    assert cf.norm_id("X.md") == "X"
    # 页名本身含 `_from_` 但不是轮号后缀 → 不误剥
    assert cf.norm_id("ALIGN_P_nav_from_rowlist.md") == "ALIGN_P_nav_from_rowlist"


# ── 3. _delta：四类 + still_open ───────────────────────────────────────────
def render(root, rnd, out):
    p = subprocess.run([PY, os.path.join(SC, "render_round_summary.py"), "--round", str(rnd),
                        "--project-root", root, "--out-dir", out], capture_output=True, text=True, cwd=root)
    assert p.returncode == 0, p.stderr
    return open(os.path.join(root, out, "_delta.md"), encoding="utf-8").read()


def sec_ids(delta: str, key: str) -> list:
    out, on = [], False
    for line in delta.split("\n"):
        if line.startswith("## "):
            on = line.startswith("## " + key)
            continue
        if on and line.startswith("- `"):
            out.append(line[3:].rstrip("`"))
    return sorted(out)


def _mk_delta_fixture(root, legacy=False):
    """round-0: A,B,C,D,E   round-1: B 消失   round-2: A 修好 / C 仍开 / D 回归 / F 新出"""
    for n in ("ALIGN_A", "ALIGN_B", "ALIGN_C", "ALIGN_D"):
        ticket(root, 0, "ui", n, page="P" + n[-1])
    # round-1：A/C/D 结转（D 本轮消失 → round-2 才回来）
    ticket(root, 1, "ui", "ALIGN_A", page="PA")
    ticket(root, 1, "ui", "ALIGN_C", page="PC")
    ticket(root, 1, "ui", "ALIGN_E", page="PE")                      # round-1 新出
    # round-2
    if legacy:
        ticket(root, 2, "ui", "RESOLVED_ALIGN_A", tid="RESOLVED_ALIGN_A", page="PA",
               disposition="fixed", set_at=2, extra="carried_from_id: ALIGN_A")
        ticket(root, 2, "ui", "CARRYOVER_ALIGN_C_from_r1", tid="CARRYOVER_ALIGN_C_from_r1",
               page="PC", extra="carried_from_id: ALIGN_C")
    else:
        ticket(root, 2, "ui", "ALIGN_A", page="PA", disposition="fixed", set_at=2)
        ticket(root, 2, "ui", "ALIGN_C", page="PC")
    ticket(root, 2, "ui", "ALIGN_D", page="PD")                      # regressed
    ticket(root, 2, "ui", "ALIGN_F", page="PF")                      # new
    ticket(root, 2, "ui", "ALIGN_E", page="PE", disposition="manual_review", set_at=2)


def test_delta_five_sections():
    root = tempfile.mkdtemp()
    try:
        _mk_delta_fixture(root)
        d = render(root, 2, "out")
        assert sec_ids(d, "fixed") == ["ALIGN_A"], d
        assert sec_ids(d, "new") == ["ALIGN_F"], d
        assert sec_ids(d, "regressed") == ["ALIGN_D"], d
        assert sec_ids(d, "unchanged") == ["ALIGN_C"], d           # E 从 null→manual_review 不算
        assert sec_ids(d, "still_open") == ["ALIGN_C"], d
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_delta_same_for_legacy_and_canonical_dirs():
    a, b = tempfile.mkdtemp(), tempfile.mkdtemp()
    try:
        _mk_delta_fixture(a, legacy=False)
        _mk_delta_fixture(b, legacy=True)
        da, db = render(a, 2, "out"), render(b, 2, "out")
        for k in ("fixed", "new", "regressed", "unchanged", "still_open"):
            assert sec_ids(da, k) == sec_ids(db, k), (k, sec_ids(da, k), sec_ids(db, k))
    finally:
        shutil.rmtree(a, ignore_errors=True); shutil.rmtree(b, ignore_errors=True)


def test_delta_does_not_count_unclosed_disappearance_as_fixed():
    """旧算法把「上轮有、本轮无」一律算 fixed —— manual_review 不结转、改名结转都会被误记。"""
    root = tempfile.mkdtemp()
    try:
        ticket(root, 0, "ui", "ALIGN_X", page="PX", disposition="manual_review", set_at=0)
        ticket(root, 0, "ui", "ALIGN_Y", page="PY", disposition="fixed", set_at=0)
        ticket(root, 1, "ui", "ALIGN_Z", page="PZ")
        d = render(root, 1, "out")
        assert sec_ids(d, "fixed") == [], d
        assert sec_ids(d, "new") == ["ALIGN_Z"], d
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ── 4. 与 carry_forward 串起来：结转后 delta 仍正确 ────────────────────────
def test_carry_then_delta_endtoend():
    root = tempfile.mkdtemp()
    try:
        _mk_three_layer(root)
        run_cf(root, 1)
        # 本轮把 ALIGN_A 判 fixed
        p = os.path.join(root, "spec/fix/round-1/ui/ALIGN_A.md")
        t = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8").write(cf.upsert_scalar(t, "disposition", "fixed"))
        d = render(root, 1, "out")
        assert sec_ids(d, "fixed") == ["ALIGN_A"], d
        assert sec_ids(d, "new") == [], d
        assert sec_ids(d, "still_open") == ["ALIGN_C", "BLOCKED_PG", "FEAT_H", "SYSTEMIC_J"], d
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v(); n += 1; print("  ✓", k)
    print(f"ALL PASSED ({n} tests)")
