#!/usr/bin/env python3
"""capture_page_e2e 的瞬态连拍包（2026-09-11）：优先吃 walk_exec 打的包绑定；包过期/不匹配不吃。
账本闸：没包且 dump 验不上时 capture-only 不再按链位绑定（那条路的实现改成 raise Esc(16, transient_missed)，
在 main() 里，此处用源码断言接线）。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import capture_page_e2e as K  # noqa: E402


def _png(path, w=300, h=600):
    from PIL import Image
    Image.new("RGB", (w, h), (200, 200, 250)).save(path)


def _bundle(tmp_path, page="LoadingX", age=0):
    pend = tmp_path / "pending_shots"; pend.mkdir(parents=True, exist_ok=True)
    shot = pend / f"step9_{page}_t2.5.png"; _png(str(shot))
    xml = pend / f"{page}__transient.android.xml"
    xml.write_text('<hierarchy dump-source="dumpsys" text-source="layout"><node text="占位" resource-id="p:id/t" bounds="[0,0][1,1]"/></hierarchy>', encoding="utf-8")
    b = {"node": page, "step": 9, "shot": str(shot), "xml": str(xml), "identity_by": "dumpsys_resumed_fragment",
         "activity": "HostX", "first_seen_s": 0.7, "last_seen_s": 5.6, "left_at_s": 5.9, "budget_s": 8.7,
         "frames": 9, "ticks": 20, "dump_source": "dumpsys", "text_source": "layout+runtime_text_writes", "texts_mapped": 1}
    p = pend / f"{page}__transient.json"; p.write_text(json.dumps(b), encoding="utf-8")
    if age:
        os.utime(p, (time.time() - age, time.time() - age))
    return str(pend)


def test_load_bundle_matches_page_and_files(tmp_path):
    pend = _bundle(tmp_path)
    b = K.load_transient_bundle(pend, "LoadingX")
    assert b and b["identity_by"] == "dumpsys_resumed_fragment" and b["_path"].endswith("LoadingX__transient.json")
    assert K.load_transient_bundle(pend, "OtherPage") is None
    assert K.load_transient_bundle(None, "LoadingX") is None


def test_load_bundle_rejects_stale_or_broken(tmp_path):
    pend = _bundle(tmp_path, age=3600)
    assert K.load_transient_bundle(pend, "LoadingX") is None                   # 过期包不绑（旧包绑新趟=基线污染）
    pend2 = _bundle(tmp_path / "b")
    os.remove(os.path.join(pend2, "step9_LoadingX_t2.5.png"))
    assert K.load_transient_bundle(pend2, "LoadingX") is None                  # 图缺失


def test_bind_bundle_places_shot_and_returns_xml_and_marks_used(tmp_path):
    pend = _bundle(tmp_path)
    b = K.load_transient_bundle(pend, "LoadingX")
    result, notes = {}, []
    shots = tmp_path / "shots"
    shot, xml = K.bind_transient_bundle(b, "LoadingX", str(shots), result, notes)
    assert os.path.isfile(shot) and shot.endswith("LoadingX.png")
    assert 'dump-source="dumpsys"' in xml
    assert result["identity_by"] == "dumpsys_resumed_fragment" and result["dump_source"] == "dumpsys"
    assert result["transient_capture"]["frames"] == 9 and any("连拍包" in n for n in notes)
    assert not os.path.exists(b["_path"]) and os.path.exists(b["_path"] + ".used")   # 用过即改名
    assert K.load_transient_bundle(pend, "LoadingX") is None                   # 不会绑第二次


def test_capture_only_no_longer_binds_by_chain_position():
    src = open(K.__file__, encoding="utf-8").read()
    assert 'v = "chain_position"' not in src
    assert 'classified="transient_missed"' in src
    assert "load_transient_bundle(_pend, a.page)" in src


class _FakeDrv:
    """只给 on_page 用：current_activity 固定、adb dumpsys 返回夹具。"""
    def __init__(self, dumpsys_text, activity="com.example.app/com.example.app.page.HostActivity"):
        self.t = dumpsys_text; self.a = activity
    def current_activity(self):
        return self.a
    def adb(self, args, timeout=30):
        class R: pass
        r = R(); r.stdout = self.t if "dumpsys" in args else ""; r.returncode = 0; return r


def test_on_page_falls_back_to_dumpsys_when_texts_are_shared_or_unique_ids_missing():
    import test_lib_dumpsys as L
    K._BY_ID.clear()
    K._BY_ID.update({"HostActivity": {"id": "HostActivity", "type": "Activity"},
                     "PrevFragment": {"id": "PrevFragment", "type": "Fragment", "parent_in_nav": "HostActivity"},
                     "LoadingFragment": {"id": "LoadingFragment", "type": "Fragment", "parent_in_nav": "HostActivity"},
                     "NextFragment": {"id": "NextFragment", "type": "Fragment", "parent_in_nav": "HostActivity"}})
    K._PKG = "com.example.app"
    drv = _FakeDrv(L.DUMP)
    xml = "<hierarchy><node text=\"占位共享词\" bounds=\"[0,0][10,10]\"/></hierarchy>"
    # 三页文本相同 → 签名判不出 → dumpsys 说 LoadingFragment RESUMED
    assert K.on_page(drv, K._BY_ID["LoadingFragment"], xml) == "dumpsys_resumed_fragment"
    assert K.on_page(drv, K._BY_ID["PrevFragment"], xml) is None            # 不是当前页，dumpsys 也不放行
    K._BY_ID.clear(); K._PKG = ""

