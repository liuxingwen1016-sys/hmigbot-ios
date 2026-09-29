"""node_sweep 三条通用规则的回归（2026-09-09，0909 安卓边遍历实测三缺陷）

C1 页内状态切换：结构签名不变但选中/文本变 → state_switch_inplace + 前向复位（绝不 BACK）
C2 回位阶梯 IME 感知：键盘弹起时第一下 BACK 只收键盘，不能算进弹栈
C3 position_lost 真值：pkg 离开本 app 即置真，activity 相同不足以抹掉

全部用合成 dump + 假设备（内存状态机），不碰 adb/模拟器。
"""
import json, os, sys, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import node_sweep as ns                                            # noqa: E402
from blackbox_explore import DeviceAdapter                          # noqa: E402

PKG = "com.demo.app"
STRUCT = lambda x: DeviceAdapter.page_signature_from_dump(x, "android")   # noqa: E731


# ── 合成 dump ────────────────────────────────────────────────────────────────
def _hier(inner):
    return '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">%s</hierarchy>' % inner


def _tab_page(selected_two):
    """两个 tab 的页：只有 selected 属性在变，文本/rid/bounds 全同 → 结构签名必然相同。"""
    def tab(rid, text, x1, x2, sel):
        return ('<node class="android.widget.TextView" resource-id="%s:id/%s" text="%s" '
                'selected="%s" clickable="true" bounds="[%d,400][%d,600]"/>'
                % (PKG, rid, text, "true" if sel else "false", x1, x2))
    return _hier('<node class="android.widget.LinearLayout" resource-id="%s:id/tab_bar" '
                 'bounds="[0,400][1080,600]">%s%s</node>'
                 % (PKG, tab("tab_one", "全部", 0, 540, not selected_two),
                    tab("tab_two", "草稿", 540, 1080, selected_two)))


def _long_page(content):
    """20 个占位文本节点（吃满结构签名的 20 个名额）+ 尾部内容节点：
    结构签名只看前 20 个 → 尾部文本换了它也不变；state_signature 看全量 → 变。"""
    fill = "".join('<node class="android.widget.TextView" text="f%02d" bounds="[0,%d][100,%d]"/>'
                   % (i, i * 10, i * 10 + 9) for i in range(20))
    btn = ('<node class="android.widget.TextView" resource-id="%s:id/btn_more" text="更多" '
           'clickable="true" bounds="[540,400][1080,600]"/>' % PKG)
    tail = '<node class="android.widget.TextView" text="%s" bounds="[0,700][1080,800]"/>' % content
    return _hier(fill + btn + tail)


def _simple(act_text, rid="btn_edit", label="编辑"):
    return _hier('<node class="android.widget.TextView" text="%s" bounds="[0,0][1080,300]"/>'
                 '<node class="android.widget.TextView" resource-id="%s:id/%s" text="%s" '
                 'clickable="true" bounds="[0,800][1080,900]"/>' % (act_text, PKG, rid, label))


def _clickable(rid, text, bounds):
    x1, y1, x2, y2 = bounds
    return {"bounds": (x1, y1, x2, y2), "center": ((x1 + x2) // 2, (y1 + y2) // 2),
            "text": text, "content_desc": "", "resource_id": "%s:id/%s" % (PKG, rid),
            "class": "android.widget.TextView"}


# ── 假设备（DeviceAdapter 接口子集，纯内存）───────────────────────────────────
class FakeDev:
    def __init__(self, screens, start, pkg=PKG, flip=None):
        self.screens = screens              # name -> (xml, activity)
        self.cur, self.pkg = start, pkg
        self.ime = False
        self.log = []
        self.tap_zones = []                 # [((x1,y1,x2,y2), handler)]
        self.back_handler = None
        self.flip, self.dumps = flip, 0     # (第 n 次 dump 起, 换到哪屏)：模拟迟到的状态变化

    page_signature_from_dump = staticmethod(DeviceAdapter.page_signature_from_dump)

    def screen_size(self):
        return (1080, 1920)

    def dump_layout(self, path=None):
        self.dumps += 1
        if self.flip and self.dumps >= self.flip[0]:
            self.cur = self.flip[1]
        xml = self.screens[self.cur][0]
        if path:
            open(path, "w").write(xml)
        return xml

    def current_activity(self):
        return self.screens[self.cur][1]

    def current_pkg(self):
        return self.pkg

    def shell(self, *args):
        cmd = " ".join(args)
        self.log.append("shell:" + cmd)
        if "input_method" in cmd:
            return "mInputShown=true" if self.ime else "mInputShown=false"
        return ""

    def tap(self, x, y):
        self.log.append(("tap", x, y))
        for (x1, y1, x2, y2), h in self.tap_zones:
            if x1 <= x <= x2 and y1 <= y <= y2:
                h(self)
                return

    def back(self):
        self.log.append("back")
        if self.back_handler:
            self.back_handler(self)

    def screencap(self, path):
        open(path, "wb").write(b"")

    def backs(self):
        return self.log.count("back")


def _tree(node, checks=(), extra_pages=(), page_extra=None):
    page = {"id": node, "type": "Activity", "fq_class": "%s.%sActivity" % (PKG, node),
            "inbound_triggers": [], "navigation": {"inbound": [], "outbound": []},
            "functional_checks": list(checks)}
    page.update(page_extra or {})
    return {"app": {}, "fragments": [], "dialogs": [], "pages": [page] + list(extra_pages)}


def run_sweep(monkeypatch, tmp_path, dev, bucket, node="ProfilePage", relaunch=None,
              extra_args=(), checks=(), extra_pages=(), page_extra=None):
    """跑一趟 main()，回 manifest（stdout 用 capsys 另取）。设备/枚举/adb 全部替身。"""
    tp = tmp_path / "tree.json"
    tp.write_text(json.dumps(_tree(node, checks, extra_pages, page_extra)), encoding="utf-8")
    bb = tmp_path / "bb"

    class Shim:                                     # DeviceAdapter(...) → 我们的假设备
        page_signature_from_dump = staticmethod(DeviceAdapter.page_signature_from_dump)

        def __new__(cls, *a, **kw):
            return dev

    monkeypatch.setattr(ns, "DeviceAdapter", Shim)
    monkeypatch.setattr(ns, "enumerate_clickables_with_scroll", lambda *a, **k: (list(bucket), 0))
    monkeypatch.setattr(ns.subprocess, "run",
                        lambda *a, **k: (relaunch(dev) if relaunch else None))
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)        # 测试里不真等
    monkeypatch.setattr(sys, "argv", ["node_sweep.py", "--serial", "fake", "--package", PKG,
                                      "--node", node, "--dir", str(tmp_path), "--tree", str(tp),
                                      "--out-blackbox", str(bb), "--toast-tags", ""] + list(extra_args))
    ns.main()
    return json.load(open(bb / ("%s__manifest.json" % node)))


def _stdout_json(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


# ── C1：状态签名 + 复位 ──────────────────────────────────────────────────────
def test_state_signature_sees_selected_while_struct_signature_does_not():
    a, b = _tab_page(False), _tab_page(True)
    assert STRUCT(a) == STRUCT(b)                       # 结构签名对 selected 变化不敏感（正是 0909 病灶）
    assert ns.state_signature(a) != ns.state_signature(b)
    assert ns.state_facts(a)["flags"] == ["sel:rid:tab_one"]
    assert ns.state_facts(b)["flags"] == ["sel:rid:tab_two"]
    # 文本一路：结构签名只看前 20 个节点 → 尾部内容换了它不变，状态签名变
    c, d = _long_page("内容A"), _long_page("内容B")
    assert STRUCT(c) == STRUCT(d) and ns.state_signature(c) != ns.state_signature(d)
    assert ns.state_signature("") == "" and ns.state_facts("<node")["flags"] == []


def test_find_selected_sibling_same_parent_only():
    a = _tab_page(False)                                # tab_one 选中，点 tab_two
    sib = ns.find_selected_sibling(a, rid="%s:id/tab_two" % PKG, bounds=(540, 400, 1080, 600))
    assert sib["resource_id"].endswith("tab_one") and sib["attr"] == "selected"
    assert sib["center"] == [270, 500] and sib["level"] == 1
    # 反过来点已选中的 tab_one：兄弟 tab_two 没有选中态 → 无从复位（不瞎猜一个去点）
    assert ns.find_selected_sibling(a, rid="%s:id/tab_one" % PKG, bounds=(0, 400, 540, 600)) is None
    assert ns.find_selected_sibling(_long_page("x"), rid="%s:id/btn_more" % PKG) is None
    assert ns.find_selected_sibling("<node", rid="a") is None                      # 非法 xml 不崩


def test_state_switch_inplace_records_and_restores(monkeypatch, tmp_path):
    dev = FakeDev({"A": (_tab_page(False), "ProfileActivity"),
                   "B": (_tab_page(True), "ProfileActivity")}, "A")
    dev.tap_zones = [((540, 400, 1080, 600), lambda d: setattr(d, "cur", "B")),
                     ((0, 400, 540, 600), lambda d: setattr(d, "cur", "A"))]
    m = run_sweep(monkeypatch, tmp_path, dev,
                  [_clickable("tab_two", "草稿", (540, 400, 1080, 600))])
    ent = m["behavior_ledger"][0]
    assert ent["outcome"] == "state_switch_inplace"          # 不再被谎报成 noop
    assert ent["restored"] is True and ent["state_reset_tap"]["center"] == [270, 500]
    assert ent["state_signature_before"] != ent["state_signature_after"]
    assert m["state_left_changed"] is False and m["position_lost"] is False
    assert dev.backs() == 0                                   # ★页内状态切换绝不 BACK
    assert dev.cur == "A"                                     # 复位到进来时那个 tab


def test_text_only_change_is_drift_not_state_switch(monkeypatch, tmp_path):
    dev = FakeDev({"C": (_long_page("内容A"), "ProfileActivity"),
                   "D": (_long_page("内容B"), "ProfileActivity")}, "C")
    dev.tap_zones = [((540, 400, 1080, 600), lambda d: setattr(d, "cur", "D"))]
    m = run_sweep(monkeypatch, tmp_path, dev, [_clickable("btn_more", "更多", (540, 400, 1080, 600))])
    ent = m["behavior_ledger"][0]
    # 主会话收敛（2026-09-09 晚）：只有文本变、选中/勾选集没变 → 不算状态切换（轮播/异步刷新页每次 dump 文本都不同），
    # 记 text_drift 供判读参考，outcome 仍 noop、不复位、不 BACK；位置由执行器普查后统一重判。
    assert ent["outcome"] == "noop" and ent.get("text_drift") is True
    assert "state_reset_tap" not in ent
    assert m["state_left_changed"] is False
    assert dev.backs() == 0


def test_exit_state_drift_is_reported_even_if_per_element_check_missed_it(monkeypatch, tmp_path):
    """兜底闸：状态变化迟到（tap 时那次 dump 还没变）→ 元素级判据抓不到，
    收尾时选中集与进来时不同 → 照样如实报 state_left_changed，不谎报「一切正常」。"""
    dev = FakeDev({"A": (_tab_page(False), "ProfileActivity"),
                   "B": (_tab_page(True), "ProfileActivity")}, "A", flip=(3, "B"))
    m = run_sweep(monkeypatch, tmp_path, dev, [_clickable("tab_two", "草稿", (540, 400, 1080, 600))])
    assert m["behavior_ledger"][0]["outcome"] == "noop"           # 元素级确实没抓到（构造如此）
    assert m["state_left_changed"] is True
    assert m["exit_state_drift"]["flags_at_entry"] == ["sel:rid:tab_one"]
    assert m["exit_state_drift"]["flags_at_exit"] == ["sel:rid:tab_two"]
    assert m["position_lost"] is False                             # 页还是那页，只是状态被留在别处


# ── C2：回位阶梯先判 IME ─────────────────────────────────────────────────────
def test_back_once_ime_aware_closes_keyboard_then_rejudges():
    dev = FakeDev({"P": ("<x/>", "HomeActivity")}, "P")
    dev.ime = True
    dev.back_handler = lambda d: setattr(d, "ime", False)     # 第一下 BACK 只被键盘吃掉
    info = ns.back_once_ime_aware(dev, stop_activity="HomeActivity")
    assert info["ime_closed"] is True and info["backed"] is False   # 收完键盘已在目标页 → 不再 BACK
    assert dev.backs() == 1
    dev2 = FakeDev({"P": ("<x/>", "EditorActivity")}, "P")
    dev2.ime = False
    info2 = ns.back_once_ime_aware(dev2, stop_activity="HomeActivity")
    assert info2["ime_closed"] is False and info2["backed"] is True and dev2.backs() == 1


def test_back_ladder_does_not_overshoot_when_ime_eats_back(monkeypatch, tmp_path):
    """0909 实测：点到无标签功能键 → 落地页自动聚焦输入框 → 第一下 BACK 被 IME 吃掉 →
    旧阶梯以为没回来继续按 → 一路退到桌面。修后：收键盘那下不计入弹栈。"""
    dev = FakeDev({"home": (_simple("首页"), "HomeActivity"),
                   "editor": (_simple("编辑页", "et_title", "标题"), "EditorActivity"),
                   "desktop": ("<hierarchy/>", "Launcher")}, "home")

    def _open_editor(d):
        d.cur, d.ime = "editor", True                     # 落地即自动聚焦

    def _back(d):
        if d.ime:                                          # 键盘吃掉这一下，页面不动
            d.ime = False
            return
        if d.cur == "editor":
            d.cur = "home"
        elif d.cur == "home":                              # 父页上再按 = 退出 app（0909 逃逸路径）
            d.cur, d.pkg = "desktop", "com.android.launcher"

    dev.tap_zones = [((0, 800, 1080, 900), _open_editor)]
    dev.back_handler = _back
    m = run_sweep(monkeypatch, tmp_path, dev, [_clickable("btn_edit", "编辑", (0, 800, 1080, 900))],
                  node="HomePage")
    assert m["behavior_ledger"][0]["outcome"] == "page_change"
    assert m["ime_closed_before_back"] == 1 and m["behavior_ledger"][0]["ime_closed_before_back"] == 1
    assert dev.backs() == 2                                # 一下收键盘 + 一下弹栈，没有第三下
    assert dev.pkg == PKG and dev.cur == "home"            # 没被退到桌面
    assert m["position_lost"] is False and m["escape_events"] == []


# ── C3：position_lost 真值 ───────────────────────────────────────────────────
def _escape_dev():
    dev = FakeDev({"home": (_simple("首页", "btn_share", "分享"), "HomeActivity"),
                   "other": ("<hierarchy/>", "ShareActivity"),
                   "home_wrong": (_simple("别的分支", "btn_share", "分享"), "HomeActivity")}, "home")
    dev.tap_zones = [((0, 800, 1080, 900),
                      lambda d: (setattr(d, "cur", "other"), setattr(d, "pkg", "com.other.app")))]
    return dev


def test_escape_sets_position_lost_and_same_activity_does_not_clear_it(monkeypatch, tmp_path):
    dev = _escape_dev()

    def relaunch(d):                    # 自愈重拉起：回到同一个 Activity，但不是锚点那一页
        d.pkg, d.cur = PKG, "home_wrong"

    m = run_sweep(monkeypatch, tmp_path, dev, [_clickable("btn_share", "分享", (0, 800, 1080, 900))],
                  node="HomePage", relaunch=relaunch)
    ent = m["behavior_ledger"][0]
    assert ent["outcome"] == "escaped_app" and ent["landed_pkg"] == "com.other.app"
    assert ent.get("soft_return") == "host_activity_ok_fragment_may_differ"   # activity 相同
    assert m["position_lost"] is True                       # ★但绝不因此抹掉 position_lost
    assert m["recovered_after_escape"] is False and "recovered_after_escape" not in ent
    assert m["escape_events"] == [{"elem_slug": "分享", "landing_pkg": "com.other.app",
                                   "landing_activity": "ShareActivity", "where": "tap"}]


def test_escape_recovered_only_when_anchor_double_verified(monkeypatch, tmp_path):
    dev = _escape_dev()
    m = run_sweep(monkeypatch, tmp_path, dev, [_clickable("btn_share", "分享", (0, 800, 1080, 900))],
                  node="HomePage",
                  relaunch=lambda d: (setattr(d, "pkg", PKG), setattr(d, "cur", "home")))
    assert m["behavior_ledger"][0]["recovered_after_escape"] is True
    assert m["position_lost"] is False and m["recovered_after_escape"] is True
    assert len(m["escape_events"]) == 1                     # 撤回了 position_lost，但逃逸事实留账


# ══════════════════════════════════════════════════════════════════════════════
# 2026-09-10 · 调用方三旋钮（--exclude-rids/--exclude-texts、--chain-mode、--only-rids）
# 判据全部只吃命令行 + dump 属性 + 树/计划字段，零具体应用信息。
# ══════════════════════════════════════════════════════════════════════════════
def _row(rid, text, y, x1, x2):
    return _clickable(rid, text, (x1, y, x2, y + 100))


def test_excluded_elements_are_not_tapped_but_ledgered_and_out_of_coverage(monkeypatch, tmp_path, capsys):
    """调用方点名的元素：不点、入账 excluded_by_caller（带 excluded_by），不进覆盖率分母。"""
    dev = FakeDev({"home": (_simple("首页"), "HomeActivity")}, "home")
    bucket = [_row("btn_agree", "同意", 1000, 0, 300),        # rid 命中（传全名也认）
              _row("btn_next", "下一步", 1100, 300, 700),      # 文案命中
              _row("btn_plain", "详情", 1200, 700, 1080)]      # 不命中 → 唯一被点的
    m = run_sweep(monkeypatch, tmp_path, dev, bucket, node="HomePage",
                  checks=[{"name": "看协议", "android_anchor": {"raw_identifier": "btn_agree"}}],
                  extra_args=["--exclude-rids", "%s:id/btn_agree" % PKG,
                              "--exclude-texts", "下一步,开始"])
    out = _stdout_json(capsys)
    by_oc = {}
    for x in m["behavior_ledger"]:
        by_oc.setdefault(x["outcome"], []).append(x)
    assert len(by_oc["excluded_by_caller"]) == 2
    assert {(x["trigger_text"], x["excluded_by"]) for x in by_oc["excluded_by_caller"]} == \
        {("同意", "rid"), ("下一步", "text")}
    # 只点了没被排除的那个（坐标来自枚举兜底）
    assert [t for t in dev.log if isinstance(t, tuple)] == [("tap", 890, 1250)]
    assert m["sweep_inventory_dispositions"] == {"excluded": 2, "unclaimed": 1}
    assert m["excluded"] == 2 and out["excluded"] == 2
    assert m["budget"] == 1                                   # ★覆盖率分母只剩 1（排除项不计）
    assert out["coverage_complete"] is True and m["position_lost"] is False
    # 被排除元素认领的 check 也如实结账（checks_total == len(checks)，不静默丢）
    rm = json.load(open(tmp_path / "grounding" / "HomePage" / "run_meta.json"))
    assert rm["checks_total"] == len(rm["checks"]) == 1
    assert rm["checks"][0]["status"] == "excluded_by_caller"


def test_exclusion_does_not_shadow_destructive_or_nav_back(monkeypatch, tmp_path):
    """排除集不吃掉 destructive / nav_back 两条既有判据（安全信号 + 返回件识别原样保留）。"""
    dev = FakeDev({"home": (_simple("首页"), "HomeActivity")}, "home")
    m = run_sweep(monkeypatch, tmp_path, dev,
                  [_row("btn_del", "删除账号", 1000, 0, 300),      # 破坏性 且 在排除集
                   _row("btn_close", "关闭", 1100, 300, 700)],     # nav_back 且 在排除集
                  node="HomePage",
                  extra_args=["--exclude-texts", "删除账号,关闭"])
    assert m["sweep_inventory_dispositions"] == {"destructive": 1, "nav_back": 1}
    assert [x["rid"] for x in m["unplanned_destructive"]] == ["%s:id/btn_del" % PKG]
    assert m["excluded"] == 0 and m["budget"] == 0
    assert [t for t in dev.log if isinstance(t, tuple)] == []


# ── chain-mode：链页当场普查，推进即停 ────────────────────────────────────────
def _guide_dev():
    dev = FakeDev({"guide": (_simple("引导页"), "GuideActivity"),
                   "next": (_simple("下一页", "btn_ok", "确定"), "NextActivity")}, "guide")
    dev.tap_zones = [((300, 1100, 700, 1200), lambda d: setattr(d, "cur", "next"))]
    return dev


_NEXT_PAGE = {"id": "GuideNext", "type": "Activity", "fq_class": "%s.NextActivity" % PKG,
              "inbound_triggers": [], "navigation": {"inbound": [], "outbound": []},
              "functional_checks": []}


def test_chain_mode_stops_at_first_advance_without_any_back(monkeypatch, tmp_path, capsys):
    """链页是一次性单向门：一旦 tap 推进（此例 activity 变），立即停手、绝不 BACK/回位，
    把落点与未点元素原样交回调用方。"""
    dev = _guide_dev()
    m = run_sweep(monkeypatch, tmp_path, dev,
                  [_row("btn_look", "查看", 1000, 0, 300),          # 点了没动静 → 继续扫
                   _row("btn_enter", "进入", 1100, 300, 700),        # 点了推进 → 就地停
                   _row("btn_skip", "跳过", 1200, 700, 1080)],       # 没轮到 → unswept
                  node="GuidePage", extra_args=["--chain-mode"],
                  extra_pages=[_NEXT_PAGE],
                  page_extra={"preconditions": [{"kind": "first_launch_onboarding"}]})
    out = _stdout_json(capsys)
    assert m["chain_mode"] is True and m["chain_advanced"] is True
    assert m["behavior_ledger"][0]["outcome"] == "noop"                  # 没推进的那个照常继续
    assert m["behavior_ledger"][1]["chain_advanced"] is True
    assert m["advanced_to"] == {"activity": "NextActivity", "landing_node": "GuideNext",
                                "elem_slug": "进入"}
    assert m["unswept"] == [{"rid": "%s:id/btn_skip" % PKG, "text": "跳过",
                             "content_desc": "", "center": [890, 1250]}]
    assert m["position_lost"] is True and out["coverage_complete"] is False
    assert dev.backs() == 0                       # ★零 BACK：链页回不去，回位一律交调用方
    assert dev.cur == "next" and dev.pkg == PKG   # 设备停在推进后的页，脚本没自作主张往回捞
    assert out["chain_advanced"] is True and out["unswept"] == m["unswept"]


def test_chain_mode_advance_also_covers_pkg_change_and_inplace_page_change(monkeypatch, tmp_path):
    """推进判据三选一：包名变 / 同 activity 内结构签名变且哨兵不在位（引导页 ViewPager）。"""
    # ① 包名变（链里被踢到外部 app）
    dev = FakeDev({"guide": (_simple("引导页"), "GuideActivity"),
                   "out": ("<hierarchy/>", "OtherActivity")}, "guide")
    dev.tap_zones = [((0, 1000, 300, 1100),
                      lambda d: (setattr(d, "cur", "out"), setattr(d, "pkg", "com.other.app")))]
    m = run_sweep(monkeypatch, tmp_path, dev,
                  [_row("btn_go", "去", 1000, 0, 300), _row("btn_rest", "剩下", 1100, 300, 700)],
                  node="GuidePage", extra_args=["--chain-mode"])
    assert m["chain_advanced"] is True and m["behavior_ledger"][0]["outcome"] == "escaped_app"
    assert m["advanced_to"]["landing_node"] is None            # 落点不在树内 → null，不硬猜
    assert [x["text"] for x in m["unswept"]] == ["剩下"]
    assert dev.backs() == 0 and dev.pkg == "com.other.app"     # ★没重拉起、没 BACK
    # ② 同 activity 内换页（结构签名变、无哨兵）
    dev2 = FakeDev({"p1": (_simple("引导一"), "GuideActivity"),
                    "p2": (_simple("引导二", "btn_ok", "确定"), "GuideActivity")}, "p1")
    dev2.tap_zones = [((0, 1000, 300, 1100), lambda d: setattr(d, "cur", "p2"))]
    m2 = run_sweep(monkeypatch, tmp_path, dev2,
                   [_row("btn_go", "去", 1000, 0, 300), _row("btn_rest", "剩下", 1100, 300, 700)],
                   node="GuidePage", extra_args=["--chain-mode"])
    assert m2["chain_advanced"] is True and m2["advanced_to"]["activity"] == "GuideActivity"
    assert dev2.backs() == 0 and dev2.cur == "p2"


def test_chain_mode_is_second_legal_entry_for_chain_page_gate(monkeypatch, tmp_path, capsys):
    """链页或门：裸跑仍 exit 21；--chain-mode 放行且 manifest 记 chain_mode，
    老入口 --allow-chain-sweep 行为不变（chain_mode=false）。"""
    def _run(extra):
        dev = FakeDev({"guide": (_simple("引导页"), "GuideActivity")}, "guide")
        return run_sweep(monkeypatch, tmp_path, dev, [_row("btn_look", "查看", 1000, 0, 300)],
                         node="GuidePage", extra_args=extra,
                         page_extra={"preconditions": [{"kind": "first_launch_onboarding"}]})
    try:
        _run([])
        assert False, "链页裸跑必须拒绝"
    except SystemExit as ex:
        assert ex.code == 21
    refused = _stdout_json(capsys)
    assert refused["refused"] == "chain_page_no_sweep"
    assert set(refused["signals"]) == {"first_launch_onboarding", "name_prefix"}
    assert _run(["--chain-mode"])["chain_mode"] is True
    assert _run(["--allow-chain-sweep"])["chain_mode"] is False       # 老入口不受影响


# ── only-rids：定向补点 + run_meta 合并写回 ──────────────────────────────────
_OLD_RM = {"node": "ProfilePage", "checks_total": 2, "t_total_s": 99.9,
           "checks": [{"idx": 0, "name": "看资料", "status": "ok", "hit_by": "sweep",
                       "landed_texts": ["资料页"]},
                      {"idx": 1, "name": "看订单", "status": "not_found", "hit_by": None}],
           "generated_by": "node_sweep"}


def _seed_run_meta(tmp_path, node="ProfilePage", data=None):
    g = tmp_path / "grounding" / node
    g.mkdir(parents=True, exist_ok=True)
    if data is not None:
        (g / "run_meta.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return g / "run_meta.json"


def test_only_rids_processes_named_anchor_only_and_merges_run_meta(monkeypatch, tmp_path, capsys):
    """边失败后的当场补点：只点集合内锚点，其余入账 skipped_not_in_only；
    run_meta **合并**写回——没被处理的 check 的旧证据一个字不动。"""
    rm_path = _seed_run_meta(tmp_path, data=_OLD_RM)
    dev = FakeDev({"home": (_simple("我的"), "ProfileActivity"),
                   "order": (_simple("订单页", "tv_empty", "暂无订单"), "OrderActivity")}, "home")
    dev.tap_zones = [((300, 1100, 700, 1200), lambda d: setattr(d, "cur", "order"))]
    dev.back_handler = lambda d: setattr(d, "cur", "home")
    m = run_sweep(monkeypatch, tmp_path, dev,
                  [_row("btn_a", "资料", 1000, 0, 300), _row("btn_b", "订单", 1100, 300, 700)],
                  checks=[{"name": "看资料", "android_anchor": {"raw_identifier": "btn_a"}},
                          {"name": "看订单", "android_anchor": {"raw_identifier": "btn_b"}}],
                  extra_args=["--only-rids", "btn_b"])
    out = _stdout_json(capsys)
    assert [t for t in dev.log if isinstance(t, tuple)] == [("tap", 500, 1150)]   # 只点了 btn_b
    assert m["sweep_inventory_dispositions"] == {"not_in_only": 1, "ground": 1}
    assert [x["outcome"] for x in m["behavior_ledger"]] == ["page_change", "skipped_not_in_only"]
    assert m["only_rids"] == ["btn_b"] and out["only_rids"] == ["btn_b"]
    assert m["skipped_not_in_only"] == 1 and m["budget"] == 1
    rm = json.load(open(rm_path))
    assert rm["merged_with_previous"] is True and rm["processed_check_idx"] == [1]
    got = {c["idx"]: c for c in rm["checks"]}
    assert got[0] == _OLD_RM["checks"][0]                    # ★旧证据原样保留，没被降级
    assert got[1]["status"] == "ok" and got[1]["hit_by"] == "sweep"
    assert got[1]["landed_activity"] == "OrderActivity"      # 本轮新证据覆盖旧的 not_found
    assert rm["t_total_s"] != 99.9                           # 顶层用本轮事实


def test_full_sweep_still_overwrites_and_knobs_default_off(monkeypatch, tmp_path):
    """不带旋钮时：manifest 契约字段有默认值（调用方免判存在）、run_meta 仍是整份覆写。"""
    rm_path = _seed_run_meta(tmp_path, data={"node": "ProfilePage", "checks_total": 1,
                                             "checks": [{"idx": 9, "name": "陈年", "status": "ok"}]})
    dev = FakeDev({"home": (_simple("我的"), "ProfileActivity")}, "home")
    m = run_sweep(monkeypatch, tmp_path, dev, [_row("btn_a", "资料", 1000, 0, 300)])
    assert (m["chain_mode"], m["chain_advanced"], m["advanced_to"], m["unswept"],
            m["excluded"], m["skipped_not_in_only"], m["only_rids"]) == \
        (False, False, None, [], 0, 0, [])
    rm = json.load(open(rm_path))
    assert rm["checks"] == [] and "merged_with_previous" not in rm      # 全量趟不合并


def test_merge_run_meta_unit_rules():
    new = {"node": "P", "checks": [{"idx": 0, "name": "a", "status": "skipped_not_in_only"},
                                   {"idx": 1, "name": "b", "status": "ok"},
                                   {"idx": 2, "name": "c", "status": "not_found"}]}
    old = {"node": "P", "extra": 1, "checks": [{"idx": 0, "name": "a", "status": "ok"},
                                               {"idx": 1, "name": "b", "status": "not_found"}]}
    got = ns.merge_run_meta(old, new, {1})
    assert [c["status"] for c in got["checks"]] == ["ok", "ok", "not_found"]   # 0 留旧、1 覆盖、2 新增
    assert got["extra"] == 1 and got["merged_with_previous"] is True
    assert ns.merge_run_meta(None, new, {1}) is new                      # 无旧账 = 首次写
    assert ns.merge_run_meta({"checks": "broken"}, new, {1}) is new      # 旧账结构不对不硬合
