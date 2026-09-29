#!/usr/bin/env python3
"""lib_dumpsys（2026-09-11 瞬态页尺子）：dumpsys activity top 解析 / 当前页身份 / 合成 uiautomator xml /
布局文案映射 / 瞬态候选与窗口循环。夹具按真机 dumpsys 格式手写，页名/Fragment 名/控件 id 全占位串。

真机实证（AIPPT GuideInit 5s 倒计时页）：dumpsys 0.05s/次连续 18 次身份成立，uiautomator dump 窗口内跑了 7.4s；
ViewPager2 预建相邻页：当前页 Fragment 唯一 RESUMED(7) 其余 STARTED(5)，页容器 bounds 当前 0、相邻 ±宽。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lib_dumpsys as D  # noqa: E402
import compile_replay_plan as C  # noqa: E402

PKG = "com.example.app"
SECTION = """  ACTIVITY com.example.app/com.example.app.page.HostActivity 4242ad2 pid=1
    Local Activity 4242ad2 State:
      Active Fragments in 4242ad2:
        #0: ReportFragment{8de67a3 #0 androidx.lifecycle.LifecycleDispatcher.report_fragment_tag}
          mFragmentId=#0 mContainerId=#0 mTag=androidx.lifecycle.LifecycleDispatcher.report_fragment_tag
          mState=5 mIndex=0 mWho=android:fragment:0 mBackStackNesting=0
    View Hierarchy:
      com.android.internal.policy.DecorView{a1 V.E...... R.....ID 0,0-1440,3120}
        android.widget.LinearLayout{a2 V.E...... ........ 0,0-1440,3120}
          android.widget.FrameLayout{a3 V.E...... ........ 0,0-1440,2952 #1020002 android:id/content}
            androidx.viewpager2.widget.ViewPager2{a4 V.E...... ........ 0,0-1440,2952 #7f0a03f5 app:id/pager}
              androidx.viewpager2.widget.ViewPager2$RecyclerViewImpl{a5 VFED..... ........ 0,0-1440,2952 #1}
                android.widget.FrameLayout{b1 V.E...... ........ -1440,0-0,2952 #6}
                  androidx.appcompat.widget.AppCompatTextView{b2 V.ED..... ........ 160,480-1207,609 #7f0a03d6 app:id/tv_prev_title}
                  com.hjq.shape.view.ShapeTextView{b3 VFED..C.. ........ 120,2592-1320,2832 #7f0a0388 app:id/btn_prev}
                android.widget.FrameLayout{c1 V.E...... ........ 0,0-1440,2952 #8}
                  androidx.appcompat.widget.AppCompatImageView{c2 V.ED..... ........ 372,672-1360,1028 #7f0a038b app:id/iv_bubble}
                  android.widget.LinearLayout{c3 V.E...... ........ 0,1300-1440,1707 #7f0a01c1 app:id/layout_progress}
                    androidx.appcompat.widget.AppCompatTextView{c4 V.ED..... ........ 644,0-795,107 #7f0a03ae app:id/tv_pct}
                    android.widget.ProgressBar{c5 V.ED..... ........ 120,120-1320,140 #7f0a01c2 app:id/bar}
                  androidx.appcompat.widget.AppCompatTextView{c6 G.ED..... ........ 0,1800-1440,1900 #7f0a03af app:id/tv_hidden}
                android.widget.FrameLayout{d1 V.E...... ........ 1440,0-2880,2952 #9}
                  com.hjq.shape.view.ShapeTextView{d2 VFED..C.. ........ 480,0-1280,240 #7f0a0389 app:id/btn_next}
    Looper (main, tid 2) {a2ba331}
    Local FragmentActivity 4242ad2 State:
      FragmentManager misc state:
      Active Fragments:
        PrevFragment{61ab402} (9a7e9745-9ff5-427a-9b97-d3571369814d tag=f1)
          mFragmentId=#0 mContainerId=#0 mTag=f1
          mState=5 mWho=9a7e9745 mBackStackNesting=0
          mHidden=false mDetached=false mMenuVisible=true mHasMenu=false
          mUserVisibleHint=true
        LoadingFragment{18448b7} (a71aef1d-5d01-4e84-b384-9d55890d972a tag=f2)
          mFragmentId=#0 mContainerId=#0 mTag=f2
          mState=7 mWho=a71aef1d mBackStackNesting=0
          mHidden=false mDetached=false mMenuVisible=true mHasMenu=false
          mUserVisibleHint=true
        NextFragment{809006a} (7cd375f1-3938-4d9a-837d-94b1ee53a69e tag=f3)
          mFragmentId=#0 mContainerId=#0 mTag=f3
          mState=5 mWho=7cd375f1 mBackStackNesting=0
          mHidden=false mDetached=false mMenuVisible=true mHasMenu=false
          mUserVisibleHint=true
"""
DUMP = "  ACTIVITY com.other.launcher/.MainActivity 1 pid=9\n    View Hierarchy:\n" + SECTION
KNOWN = {"HostActivity", "PrevFragment", "LoadingFragment", "NextFragment", "HomeActivity"}


def test_section_for_pkg_picks_our_task_only():
    act, sec = D.section_for_pkg(DUMP, PKG)
    assert act == "com.example.app.page.HostActivity" and sec.startswith("ACTIVITY com.example.app/")
    assert "com.other.launcher" not in sec
    assert D.section_for_pkg(DUMP, "com.nope") == (None, "")


def test_parse_fragments_both_formats_and_current_by_max_state():
    frs = D.parse_fragments(SECTION)
    names = {f["name"]: f["state"] for f in frs}
    assert names["LoadingFragment"] == 7 and names["PrevFragment"] == 5 and names["ReportFragment"] == 5
    assert D.current_fragments(frs, KNOWN) == {"LoadingFragment"}          # 唯一最大 = 当前页
    # 不写死 7：全体都是 5 时最大集合含多个 → 调用方判"分不出"
    frs5 = [dict(f, state=5) for f in frs]
    assert D.current_fragments(frs5, KNOWN) == {"PrevFragment", "LoadingFragment", "NextFragment"}
    assert D.current_fragments([], KNOWN) == set()


def test_parse_views_absolute_bounds_flags_and_brace_bug():
    views = D.parse_views(SECTION)
    by = {v["rid_short"]: v for v in views if v["rid_short"]}
    assert by["tv_pct"]["bounds"] == [644, 1300, 795, 1407]                 # 相对父累加成绝对坐标
    assert by["btn_prev"]["bounds"][0] == -1320 and by["btn_next"]["bounds"][0] == 1920   # 相邻页在屏外
    assert by["btn_prev"]["clickable"] is True and by["tv_pct"]["clickable"] is False
    assert by["tv_hidden"]["visible"] is False                                # G = gone
    assert "}" not in by["pager"]["rid"] and by["pager"]["rid_short"] == "pager"   # `app:id/pager}` 的 } 不入 rid


def test_visible_rids_excludes_offscreen_pages_and_gone():
    vis = D.visible_rids(D.parse_views(SECTION), 1440)
    assert {"iv_bubble", "tv_pct", "bar", "layout_progress"} <= vis
    assert not ({"btn_prev", "btn_next", "tv_prev_title", "tv_hidden"} & vis)


def test_identity_on_node_activity_fragment_and_fallback():
    act = "com.example.app.page.HostActivity"
    assert D.identity_on_node(SECTION, act, "HostActivity", {"type": "Activity"}, KNOWN, 1440) == "dumpsys_activity"
    assert D.identity_on_node(SECTION, act, "LoadingFragment", {"type": "Fragment"}, KNOWN, 1440) == "dumpsys_resumed_fragment"
    assert D.identity_on_node(SECTION, act, "PrevFragment", {"type": "Fragment"}, KNOWN, 1440) is None
    assert D.identity_on_node(SECTION, act, "HomeActivity", {"type": "Activity"}, KNOWN, 1440) is None
    # Fragment 状态分不出时（全 5）→ 屏内 view_ids 兜底
    sec5 = SECTION.replace("mState=7", "mState=5")
    rec = {"type": "Fragment", "layout_facts": {"view_ids": ["iv_bubble", "tv_pct", "bar"]}}
    assert D.identity_on_node(sec5, act, "LoadingFragment", rec, KNOWN, 1440) == "dumpsys_visible_view_ids"
    rec_prev = {"type": "Fragment", "layout_facts": {"view_ids": ["tv_prev_title", "btn_prev"]}}
    assert D.identity_on_node(sec5, act, "PrevFragment", rec_prev, KNOWN, 1440) is None      # 屏外预建页不算


def test_synthesize_xml_is_uiautomator_compatible_and_filters_offscreen(tmp_path):
    views = D.parse_views(SECTION)
    xml = D.synthesize_uia_xml(views, PKG, {"tv_pct": "40%", "btn_next": "下一页"}, 1440, 3120)
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    assert root.get("dump-source") == "dumpsys" and root.get("text-source") == "layout"
    (tmp_path / "LoadingFragment.android.xml").write_text(xml, encoding="utf-8")
    rt = C.rid_texts(str(tmp_path))["LoadingFragment"][0]
    assert rt == {"tvpct": "40%"}                                            # 屏外的 btn_next 文案没混进来
    ck = C.clickable_rids(str(tmp_path))
    assert "btn_prev" not in ck["present"]["LoadingFragment"] and "tv_hidden" not in ck["present"]["LoadingFragment"]
    assert f'resource-id="{PKG}:id/tv_pct"' in xml and 'resource-id="android:id/content"' in xml


def test_layout_and_runtime_texts(tmp_path):
    root = tmp_path / "app"
    (root / "src/main/res/values").mkdir(parents=True)
    (root / "src/main/res/layout").mkdir(parents=True)
    (root / "src/main/res/values/strings.xml").write_text(
        '<resources><string name="entering">正在进入占位</string></resources>', encoding="utf-8")
    (root / "src/main/res/layout/frag_loading.xml").write_text(
        '<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android">'
        '<TextView android:id="@+id/tv_tip" android:text="@string/entering"/>'
        '<TextView android:id="@+id/tv_pct" android:text="40%"/>'
        '<include layout="@layout/inc_footer"/>'
        '<ImageView android:id="@+id/iv_bubble"/></LinearLayout>', encoding="utf-8")
    (root / "src/main/res/layout/inc_footer.xml").write_text(
        '<TextView xmlns:android="http://schemas.android.com/apk/res/android" android:id="@+id/tv_foot" android:text="页脚占位"/>',
        encoding="utf-8")
    rec = {"layout_file": "app/src/main/res/layout/frag_loading.xml",
           "layout_facts": {"file": "app/src/main/res/layout/frag_loading.xml", "includes": ["inc_footer"]},
           "runtime_text_writes": [{"view_id": "tv_pct", "expr": 'bind.tvPct.text = "100%"'},
                                   {"view_id": "tv_dyn", "expr": 'bind.tvDyn.text = "$progress%"'},
                                   {"view_id": "tv_cat", "expr": 'bind.tvCat.text = a + "x"'},
                                   {"view_id": "tv_lit", "expr": 'bind.tvLit.text = "字面量占位"'}]}
    tx = D.texts_for_node(rec, str(tmp_path))
    assert tx["tv_tip"] == "正在进入占位" and tx["tv_pct"] == "40%" and tx["tv_foot"] == "页脚占位"   # 布局优先，@string 已解，include 一层
    assert tx["tv_lit"] == "字面量占位" and "tv_dyn" not in tx and "tv_cat" not in tx        # 只认纯字面量
    assert D.texts_for_node(rec, None) == {"tv_pct": "100%", "tv_lit": "字面量占位"}          # 无源码根：只剩 runtime 字面量


def test_transient_candidates_and_budget():
    walk = {"steps": [
        {"step": 1, "from": "SplashX", "to": "GuideX", "action": "tap", "auto_transition": True, "kind": "push",
         "wait_hint": "until_text:占位"},
        {"step": 2, "from": "GuideX", "to": "StepA", "action": "tap", "auto_transition": True, "kind": "wizard_step",
         "wait_hint": None},                                                    # 宿主装子页：不算
        {"step": 3, "from": "HostY", "to": "ChildY", "action": "tap", "auto_transition": True, "kind": "push",
         "wait_hint": "immediate"},                                            # immediate：不算
        {"step": 4, "from": "LoadingZ", "to": "HomeZ", "action": "tap", "auto_transition": True, "kind": "push",
         "wait_hint": "countdown_ms:5110"},
        {"step": 5, "from": "PageQ", "to": "DlgQ", "action": "tap", "auto_transition": True, "kind": "dialog",
         "wait_hint": "immediate"},                                            # 自动弹窗：起点不消失
        {"step": 6, "from": "PageR", "to": "PageS", "action": "tap", "kind": "push", "trigger": "占位键"},   # 普通 tap
    ]}
    assert D.transient_candidates(walk) == {"SplashX": "until_text:占位", "LoadingZ": "countdown_ms:5110"}
    assert D.burst_budget_s("countdown_ms:5110") == 8.7
    assert D.burst_budget_s("until_text:x") == 6.0 and D.burst_budget_s(None) == 6.0
    assert D.burst_budget_s("countdown_ms:60000") == 30.0 and D.burst_budget_s("countdown_ms:100") == 2.0


def test_run_burst_binds_last_frame_and_stops_when_identity_leaves():
    """假时钟：tick 0-1 上一页；tick 2-5 目标页；tick 6 起下一页 → 4 帧，离开即止，不等满预算。"""
    clock = {"t": 0.0}
    seq = iter(["prev", "prev", "cur", "cur", "cur", "cur", "next", "next", "next"])
    r = D.run_burst(poll_fn=lambda: next(seq), shot_fn=lambda t: f"f_{t}.png",
                    is_on_fn=lambda raw: "dumpsys_resumed_fragment" if raw == "cur" else None,
                    budget_s=10.0, clock=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + s),
                    tick_s=0.5)
    assert len(r["frames"]) == 4 and r["first_seen"] == 1.0 and r["last_seen"] == 2.5 and r["left_at"] == 3.0
    assert r["frames"][-1]["raw"] == "cur" and r["ticks"] == 7                  # 没等满 10s


def test_run_burst_never_seen_returns_empty():
    clock = {"t": 0.0}
    r = D.run_burst(poll_fn=lambda: "other", shot_fn=lambda t: "x", is_on_fn=lambda raw: None,
                    budget_s=2.0, clock=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + s), tick_s=0.5)
    assert r["frames"] == [] and r["first_seen"] is None and r["ticks"] == 4


def test_identity_dialog_overlay_on_host_page():
    """DialogFragment 叠在宿主页上：两者都 RESUMED。判弹窗→在场即成立；判宿主页→多出来的只许是弹窗。"""
    sec = SECTION.replace(
        "        NextFragment{809006a}",
        "        TipsDialogX{ab12cd3} (11111111-2222-3333-4444-555555555555 tag=d1)\n"
        "          mState=7 mWho=11111111 mBackStackNesting=0\n"
        "          mHidden=false mDetached=false mMenuVisible=true mHasMenu=false\n"
        "          mUserVisibleHint=true\n"
        "        NextFragment{809006a}")
    known = KNOWN | {"TipsDialogX"}; dialogs = {"TipsDialogX"}
    act = "com.example.app.page.HostActivity"
    assert D.identity_on_node(sec, act, "TipsDialogX", {"type": "Dialog"}, known, 1440, dialogs) == "dumpsys_resumed_dialog"
    assert D.identity_on_node(sec, act, "LoadingFragment", {"type": "Fragment"}, known, 1440, dialogs) == "dumpsys_resumed_fragment"
    assert D.identity_on_node(sec, act, "PrevFragment", {"type": "Fragment"}, known, 1440, dialogs) is None
    # 不给 dialog_ids：两者并列最大 → 判不出（保守）
    assert D.identity_on_node(sec, act, "LoadingFragment", {"type": "Fragment"}, known, 1440) is None
    # Dialog 节点不走 activity 路径（弹窗 id 永远不等于 activity 尾名）
    assert D.identity_on_node(SECTION, act, "HostActivity", {"type": "Dialog"}, KNOWN, 1440, {"HostActivity"}) is None

