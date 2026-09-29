#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_dismiss_popups_offline_0914.py —— dismiss_popups 的**离线**判定闸（2026-09-14 阶段 B）。

为什么补这个：阶段 A 的 116 例 parity 里，dismiss_popups 是**覆盖最薄的一个**——只验到
参数闸（缺 device/platform、未知参数），L1~L4 关闭阶梯一步都没验，因为每轮都要真设备 dump。
退役 `.sh` 之后如果还不补，这个脚本的核心判定就成了裸奔。

做法：判定内核 `_parse_dump(catalog, xml, W, H, overlay)` 是**纯函数**（输入 = catalog JSON +
一份 dump + 屏幕尺寸 + overlay JSON，输出 = 单行协议串），拿合成 dump 直接喂它，
全程零设备、零 adb。

★ dump 格式说明：本脚本是 **Android 专属**（uiautomator XML；HMOS 端无 dialog catalog，
main() 对 `--platform harmonyos` 直接 exit 3 —— 这条也在下面断言）。所以合成的是
Android XML dump，不是 hmos JSON dump。

覆盖：L1 catalog id / L2 文本启发式（含"不同意"负向保护与"正文比按钮大"排序）/
L3 几何角标 / L4 BACK / CLEAN / overlay 签名复用 / 签名跨坐标稳定 / HMOS 拒绝。
"""
import json
import os
import subprocess
import sys

import pytest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPTS)

import dismiss_popups as D  # noqa: E402

W, H = 1080, 2340


def _node(cls="android.widget.TextView", rid="", txt="", desc="", clk=False, b=(0, 0, 10, 10)):
    return ('<node class="%s" resource-id="%s" text="%s" content-desc="%s" clickable="%s" '
            'bounds="[%d,%d][%d,%d]" />' % (cls, rid, txt, desc, "true" if clk else "false",
                                            b[0], b[1], b[2], b[3]))


def _dump(nodes):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<hierarchy rotation="0">\n'
            + "\n".join(nodes) + "\n</hierarchy>\n")


def _files(tmp_path, xml, catalog=None, overlay=None):
    cat = catalog if catalog is not None else {"dialogs": {}}
    ov = overlay if overlay is not None else {"signatures": {}}
    xp = tmp_path / "dump.xml"
    cp = tmp_path / "catalog.json"
    op = tmp_path / "overlay.json"
    xp.write_text(xml, encoding="utf-8")
    cp.write_text(json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    op.write_text(json.dumps(ov, ensure_ascii=False), encoding="utf-8")
    return str(cp), str(xp), str(op)


def _parse(tmp_path, nodes, catalog=None, overlay=None):
    cp, xp, op = _files(tmp_path, _dump(nodes), catalog, overlay)
    return D._parse_dump(cp, xp, W, H, op)


# ── CLEAN ────────────────────────────────────────────────────────────────
def test_clean_no_modal_no_hit(tmp_path):
    """普通页：无 modal 证据、无可点关闭件 → CLEAN（绝不能乱点普通页的角标图标）。"""
    out = _parse(tmp_path, [
        _node(cls="android.widget.FrameLayout", b=(0, 0, W, H)),
        # 右上角有个小 clickable（设置图标），但没有 modal 证据 → L3 不许出手
        _node(cls="android.widget.ImageView", rid="com.x:id/ic_setting", clk=True,
              b=(W - 120, 80, W - 20, 180)),
    ])
    assert out == "CLEAN"


# ── L1 catalog ───────────────────────────────────────────────────────────
def test_l1_catalog_close_id_wins(tmp_path):
    """catalog 的 close_ids 命中 → strategy=catalog_close，坐标取节点中心。"""
    cat = {"dialogs": {"AppTipsDialog": {"close_ids": ["com.x:id/iv_close"],
                                         "confirm_ids": ["com.x:id/btn_ok"]}}}
    out = _parse(tmp_path, [
        _node(cls="android.app.Dialog", b=(100, 700, 980, 1500)),
        _node(cls="android.widget.ImageView", rid="com.x:id/iv_close", clk=True, b=(900, 720, 960, 780)),
        _node(cls="android.widget.Button", rid="com.x:id/btn_ok", txt="确定", clk=True, b=(400, 1300, 700, 1400)),
    ], catalog=cat)
    kind, cid, cx, cy, owner, strat, sig = out.split("|")
    assert kind == "HIT" and cid == "com.x:id/iv_close" and strat == "catalog_close"
    assert (int(cx), int(cy)) == (930, 750) and owner == "AppTipsDialog" and sig != "none"


def test_l1_close_ordered_before_confirm(tmp_path):
    """close_ids 整体优先于 confirm_ids（跨 dialog 也是先扫一遍 close 再扫 confirm）。"""
    cat = {"dialogs": {"A": {"confirm_ids": ["com.x:id/btn_ok"]},
                       "B": {"close_ids": ["com.x:id/iv_x"]}}}
    out = _parse(tmp_path, [
        _node(cls="android.app.Dialog", b=(0, 600, W, 1600)),
        _node(cls="android.widget.Button", rid="com.x:id/btn_ok", clk=True, b=(400, 1400, 700, 1500)),
        _node(cls="android.widget.ImageView", rid="com.x:id/iv_x", clk=True, b=(900, 620, 960, 680)),
    ], catalog=cat)
    assert out.split("|")[1] == "com.x:id/iv_x" and out.split("|")[5] == "catalog_close"


# ── L2 文本启发式 ─────────────────────────────────────────────────────────
def test_l2_text_heuristic_picks_close_over_agree(tmp_path):
    """同屏既有「跳过」又有「同意」→ 取高分的「跳过」（close/skip 桶 10 分 > agree 桶 4 分）。"""
    out = _parse(tmp_path, [
        _node(cls="android.widget.TextView", txt="跳过", clk=True, b=(820, 200, 980, 280)),
        _node(cls="android.widget.Button", txt="同意并继续", clk=True, b=(300, 1900, 780, 2020)),
    ])
    assert out.startswith("HIT|heuristic:")
    assert out.split("|")[5] == "heuristic" and (int(out.split("|")[2]), int(out.split("|")[3])) == (900, 240)


def test_l2_never_taps_disagree(tmp_path):
    """铁律：绝不点破坏性的「不同意」——负向 lookbehind 必须把它挡在 agree 桶外。
    此屏只有「不同意」可点且无 modal 证据 → 不许命中，落 CLEAN。"""
    out = _parse(tmp_path, [
        _node(cls="android.widget.Button", txt="不同意", clk=True, b=(120, 1900, 500, 2020)),
    ])
    assert out == "CLEAN", "点了「不同意」会直接退出 app 或死循环"


def test_l2_button_beats_body_text_of_same_score(tmp_path):
    """同分时取**面积最小**的：对话框正文也含「我知道了」字样，但按钮才是能 dismiss 的那个。"""
    out = _parse(tmp_path, [
        _node(cls="android.app.Dialog", b=(60, 700, 1020, 1600)),
        _node(cls="android.widget.TextView", txt="请阅读后点我知道了", clk=True, b=(80, 760, 1000, 1300)),
        _node(cls="android.widget.Button", txt="我知道了", clk=True, b=(400, 1400, 700, 1520)),
    ])
    assert out.startswith("HIT|heuristic:")
    assert (int(out.split("|")[2]), int(out.split("|")[3])) == (550, 1460), "点到正文不会 dismiss"


# ── L3 几何角标 ──────────────────────────────────────────────────────────
def test_l3_geometry_corner_needs_modal(tmp_path):
    """H5 促销浮层（WebView 覆盖 >40% 屏）：无 id 无文本 → 取右上小 clickable 当关闭键。"""
    out = _parse(tmp_path, [
        _node(cls="android.webkit.WebView", b=(0, 400, W, 2000)),          # 面积 > 40% 屏 → modal
        _node(cls="android.view.View", clk=True, b=(W - 130, 430, W - 40, 520)),   # 右上小件
        _node(cls="android.view.View", clk=True, b=(40, 1900, 130, 1990)),         # 左下小件（低分）
    ])
    kind, cid, cx, cy, owner, strat, _sig = out.split("|")
    assert kind == "HIT" and cid == "geometry:corner" and strat == "geometry" and owner == "modal_overlay"
    assert int(cx) > 0.72 * W and int(cy) < 0.30 * H, "应取右上角那个，不是左下角"


def test_l3_skips_oversized_clickable(tmp_path):
    """>6% 屏的 clickable 不是关闭键（是内容区）——滤掉后无候选 → 落 L4 BACK。"""
    out = _parse(tmp_path, [
        _node(cls="android.app.Dialog", b=(0, 0, W, H)),
        _node(cls="android.view.View", clk=True, b=(W - 600, 100, W - 20, 700)),   # 面积 ≈ 13.8% 屏
    ])
    assert out.startswith("BACK|")


# ── L4 BACK ──────────────────────────────────────────────────────────────
def test_l4_back_when_modal_but_no_closable(tmp_path):
    """全屏 scrim（clickable 覆盖 >70% 屏）→ modal 成立，但没有可点关闭件 → BACK。"""
    out = _parse(tmp_path, [_node(cls="android.view.View", clk=True, b=(0, 0, W, H))])
    kind, sig = out.split("|")
    assert kind == "BACK" and sig and sig != "none"


# ── overlay 自愈复用 ──────────────────────────────────────────────────────
def test_overlay_reuse_back(tmp_path):
    """同签名上次是 BACK 关掉的 → 这次直接 BACK，不再走阶梯。"""
    nodes = [_node(cls="android.app.Dialog", b=(0, 600, W, 1600)),
             _node(cls="android.widget.ImageView", rid="com.x:id/iv_close", clk=True, b=(900, 620, 960, 680))]
    sig = _parse(tmp_path, nodes,
                 catalog={"dialogs": {"D": {"close_ids": ["com.x:id/iv_close"]}}}).split("|")[-1]
    out = _parse(tmp_path, nodes,
                 catalog={"dialogs": {"D": {"close_ids": ["com.x:id/iv_close"]}}},
                 overlay={"signatures": {sig: {"strategy": "back"}}})
    assert out == "BACK|" + sig, "overlay 里记的 back 必须压过 L1 catalog"


def test_overlay_reuse_geometry_is_resolution_independent(tmp_path):
    """角标按**比例**存（cx_ratio/cy_ratio）→ 换分辨率仍能还原出正确坐标。"""
    nodes = [_node(cls="android.app.Dialog", b=(0, 600, W, 1600))]
    sig = _parse(tmp_path, nodes).split("|")[-1]
    ov = {"signatures": {sig: {"strategy": "geometry", "cx_ratio": 0.9, "cy_ratio": 0.25}}}
    cp, xp, op = _files(tmp_path, _dump(nodes), None, ov)
    out = D._parse_dump(cp, xp, 720, 1560, op)          # 换一块屏
    kind, cid, cx, cy, owner, strat, _s = out.split("|")
    assert kind == "HIT" and cid == "overlay:geometry" and strat == "overlay_geometry"
    assert (int(cx), int(cy)) == (648, 390) and owner == "overlay_reuse"


def test_signature_is_structural_not_positional(tmp_path):
    """签名取 class/id 指纹，不含坐标：同一弹窗挪个位置，签名必须不变（否则 overlay 永远复用不上）。"""
    a = _parse(tmp_path, [_node(cls="android.app.Dialog", b=(0, 600, W, 1600)),
                          _node(cls="android.view.View", rid="com.x:id/tip", b=(10, 610, 100, 700))])
    b = _parse(tmp_path, [_node(cls="android.app.Dialog", b=(30, 300, W - 30, 1200)),
                          _node(cls="android.view.View", rid="com.x:id/tip", b=(50, 320, 140, 410))])
    assert a.split("|")[-1] == b.split("|")[-1] != "none"


# ── 平台闸（HMOS 明确不支持）────────────────────────────────────────────
def test_harmonyos_rejected(tmp_path):
    """HMOS 端无 dialog catalog：main() 必须 exit 3 且给出原因，不许静默当 android 跑。"""
    cat = tmp_path / "catalog.json"
    cat.write_text('{"dialogs": {}}', encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "dismiss_popups.py"),
                        "--device", "sim-0", "--platform", "harmonyos", "--catalog", str(cat)],
                       capture_output=True, text=True, errors="replace", cwd=str(tmp_path))
    assert r.returncode == 3
    assert "only android supported" in (r.stderr or "")


def test_missing_catalog_rejected(tmp_path):
    """catalog 不存在 → exit 3（在任何 adb 调用之前，所以离线可测）。"""
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "dismiss_popups.py"),
                        "--device", "sim-0", "--platform", "android",
                        "--catalog", str(tmp_path / "nope.json")],
                       capture_output=True, text=True, errors="replace", cwd=str(tmp_path))
    assert r.returncode == 3 and "catalog not found" in (r.stderr or "")
