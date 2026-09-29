#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_finding_skeleton.py 「拒绝为已结转单再渲染一份」的单测（2026-09-14，合成 fixture，无工程依赖）。

背景：Phase 3 `carry_forward.py` 改成「按 id **原名**结转」后，round-N 目录里出现同 id 文件的
两种可能必须分开处理：
  ① 带 `carried_rounds` / `carried_from_round` → **结转单**，judge 应原地更新；再渲染一份 =
     同一问题两份工单（fixer 修两次、_delta 计数翻倍）→ 脚本拒绝新建，exit 21。
  ② 不带 carried 字段 → 同轮两条不同差异撞了同一个 id → 仍走 `-2` / `-3`。

运行：python3 -m pytest scripts/_tests/test_skeleton_carried_0914.py -q
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SC = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, SC)
PY = sys.executable
SKEL = os.path.join(SC, "render_finding_skeleton.py")

import render_finding_skeleton as rfs                           # noqa: E402


# ── fixture ────────────────────────────────────────────────────────────────
def write_ticket(root, rnd, layer, tid, *, carried=None, body="正文\n"):
    d = os.path.join(root, "spec", "fix", f"round-{rnd}", layer)
    os.makedirs(d, exist_ok=True)
    fm = [f"id: {tid}", f'title: "[PX] {tid}"', "source: visual-verify",
          f"layer: {layer}", "kind: ALIGNMENT_DIFF", "severity: P1",
          "page_id: PX", "fixer_layer: ui", "suggested_files:", "  - a.ets",
          "evidence:", "  - shots/a.png", "disposition: null"]
    if carried is not None:
        fm.append(f"carried_from_round: {carried}")
        fm.append(f"carried_rounds: [{carried}]")
    p = os.path.join(d, f"{tid}.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("---\n" + "\n".join(fm) + "\n---\n\n# t\n\n" + body)
    return p


def run_skeleton(root, rnd, tid, layer="ui"):
    cmd = [PY, SKEL, "--project-root", root, "--round", str(rnd), "--layer", layer,
           "--id", tid, "--title", f"[PX] {tid}", "--kind", "ALIGNMENT_DIFF",
           "--severity", "P1", "--page", "PX", "--trip", "trip_x",
           "--suggested-files", "unknown", "--similarity", "0.5",
           "--multimodal-severity", "medium", "--no-must-read"]
    return subprocess.run(cmd, capture_output=True, text=True)


# ── is_carried_ticket 纯函数 ───────────────────────────────────────────────
def test_is_carried_ticket_pure():
    with tempfile.TemporaryDirectory() as root:
        p_carried = write_ticket(root, 1, "ui", "ALIGN_PX_a", carried=0)
        p_plain = write_ticket(root, 1, "ui", "ALIGN_PX_b")
        assert rfs.is_carried_ticket(p_carried) is True
        assert rfs.is_carried_ticket(p_plain) is False
        # 不存在 / 无 frontmatter → False（宁可走 -2 也不静默覆盖）
        assert rfs.is_carried_ticket(os.path.join(root, "nope.md")) is False
        p_nofm = os.path.join(root, "nofm.md")
        open(p_nofm, "w", encoding="utf-8").write("# 没有 frontmatter\n")
        assert rfs.is_carried_ticket(p_nofm) is False


def test_is_carried_ticket_accepts_either_key():
    with tempfile.TemporaryDirectory() as root:
        d = os.path.join(root, "spec", "fix", "round-1", "ui")
        os.makedirs(d)
        for i, key in enumerate(rfs.CARRIED_KEYS):
            p = os.path.join(d, f"k{i}.md")
            open(p, "w", encoding="utf-8").write(f"---\nid: k{i}\n{key}: 0\n---\n\n正文\n")
            assert rfs.is_carried_ticket(p) is True, key


# ── CLI 行为 ───────────────────────────────────────────────────────────────
def test_refuses_to_render_over_carried_ticket():
    """结转单已在本轮 → 拒绝新建 + exit 21 + 不产 -2 文件 + 原文件一字未动。"""
    with tempfile.TemporaryDirectory() as root:
        tid = "ALIGN_PX_color_mismatch_titlebar"
        p = write_ticket(root, 1, "ui", tid, carried=0, body="原文正文，不许被覆盖\n")
        before = open(p, encoding="utf-8").read()
        r = run_skeleton(root, 1, tid)
        assert r.returncode == rfs.EXIT_CARRIED_EXISTS == 21, (r.returncode, r.stderr)
        assert "结转单已存在" in r.stderr
        assert json.loads(r.stdout)["error"] == "carried_ticket_exists"
        d = os.path.join(root, "spec", "fix", "round-1", "ui")
        assert sorted(os.listdir(d)) == [f"{tid}.md"], os.listdir(d)   # 无 -2
        assert open(p, encoding="utf-8").read() == before              # 原文未动


def test_new_id_still_renders():
    with tempfile.TemporaryDirectory() as root:
        write_ticket(root, 1, "ui", "ALIGN_PX_old", carried=0)
        r = run_skeleton(root, 1, "ALIGN_PX_new")
        assert r.returncode == 0, r.stderr
        out = json.loads(r.stdout)
        assert out["file"].endswith("ALIGN_PX_new.md"), out
        assert os.path.isfile(os.path.join(root, out["file"])) or os.path.isfile(out["file"])


def test_same_round_true_conflict_still_gets_dash2():
    """同轮真冲突（无 carried 字段）→ 仍落 -2，老行为不变。"""
    with tempfile.TemporaryDirectory() as root:
        tid = "ALIGN_PX_layout_drift_card"
        write_ticket(root, 1, "ui", tid)                 # 无 carried 字段
        r = run_skeleton(root, 1, tid)
        assert r.returncode == 0, r.stderr
        assert json.loads(r.stdout)["file"].endswith(f"{tid}-2.md")
        # 再来一次 → -3
        r3 = run_skeleton(root, 1, tid)
        assert r3.returncode == 0, r3.stderr
        assert json.loads(r3.stdout)["file"].endswith(f"{tid}-3.md")


def test_feat_layer_and_systemic_same_rule():
    """feat/ 与 ui/_systemic/ 两层同样按 carried 字段拒绝。"""
    with tempfile.TemporaryDirectory() as root:
        write_ticket(root, 2, "feat", "FEAT_PX_missing", carried=1)
        r = run_skeleton(root, 2, "FEAT_PX_missing", layer="feat")
        assert r.returncode == 21, (r.returncode, r.stderr)

        d = os.path.join(root, "spec", "fix", "round-2", "ui", "_systemic")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "SYSTEMIC_foo.md"), "w", encoding="utf-8").write(
            "---\nid: SYSTEMIC_foo\ncarried_rounds: [1]\n---\n\n正文\n")
        cmd = [PY, SKEL, "--project-root", root, "--round", "2", "--layer", "ui",
               "--id", "SYSTEMIC_foo", "--title", "[PX] sys", "--kind", "SYSTEMIC",
               "--severity", "P0", "--page", "PX", "--trip", "t", "--systemic",
               "--suggested-files", "unknown", "--similarity", "null",
               "--multimodal-severity", "high", "--no-must-read"]
        r2 = subprocess.run(cmd, capture_output=True, text=True)
        assert r2.returncode == 21, (r2.returncode, r2.stderr)


def test_carry_forward_then_skeleton_endtoend():
    """真链路：round-0 未收口单 → carry_forward.py 原名结转到 round-1 → skeleton 对同 id 被拒。"""
    import carry_forward as cf                                       # noqa: E402
    with tempfile.TemporaryDirectory() as root:
        tid = "ALIGN_PX_icon_mismatch_back"
        write_ticket(root, 0, "ui", tid)                             # round-0 open 单
        os.makedirs(os.path.join(root, "spec", "fix", "round-1", "ui"), exist_ok=True)
        rc = subprocess.run([PY, os.path.join(SC, "carry_forward.py"),
                             "--fix-dir", os.path.join(root, "spec", "fix"), "--round", "1"],
                            capture_output=True, text=True)
        assert rc.returncode == 0, rc.stderr
        carried = os.path.join(root, "spec", "fix", "round-1", "ui", f"{tid}.md")
        assert os.path.isfile(carried), os.listdir(os.path.join(root, "spec", "fix", "round-1", "ui"))
        assert rfs.is_carried_ticket(carried) is True
        r = run_skeleton(root, 1, tid)
        assert r.returncode == 21, (r.returncode, r.stderr)
        assert cf.parse_frontmatter(open(carried, encoding="utf-8").read())["id"] == tid


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"  ✓ {name}")
            except AssertionError as e:
                fails += 1; print(f"  ✗ {name}: {e}")
    print("ALL PASSED" if not fails else f"{fails} FAILED")
    sys.exit(1 if fails else 0)
