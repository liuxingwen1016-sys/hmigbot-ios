#!/usr/bin/env python3
"""Phase 2.4 重算 layout_facts 后并回 Phase 1.7 状态节点的调用点文案（A 链实跑抓出的覆盖问题）。零 app 常量。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import tree_generic as G  # noqa: E402


def test_merge_appends_and_dedupes_and_is_idempotent():
    r = {"call_site_texts": ["标题甲", "正文乙", "占位通用"],
         "layout_facts": {"file": "l.xml", "static_texts": ["占位通用", "确定"]}}
    assert G.merge_call_site_texts(r) == 2
    assert r["layout_facts"]["static_texts"] == ["占位通用", "确定", "标题甲", "正文乙"]   # 布局文案在前
    assert r["layout_facts"]["call_site_texts"] == ["标题甲", "正文乙", "占位通用"]
    assert G.merge_call_site_texts(r) == 0                                              # 幂等


def test_merge_noop_without_field_or_facts():
    assert G.merge_call_site_texts({"layout_facts": {"static_texts": ["x"]}}) == 0
    assert G.merge_call_site_texts({"call_site_texts": ["x"]}) == 0
    r = {"call_site_texts": ["  ", None], "layout_facts": {"static_texts": []}}
    assert G.merge_call_site_texts(r) == 0 and r["layout_facts"]["static_texts"] == []
