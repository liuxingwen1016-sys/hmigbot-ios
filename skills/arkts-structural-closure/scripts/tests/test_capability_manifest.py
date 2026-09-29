# -*- coding: utf-8 -*-
"""gen_capability_manifest 守卫回归（dice_patrol 首跑乱码键事故）。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gen_capability_manifest import derive_keys, emit_interface
import pytest

def _mk(tmp_path, scope):
    d = tmp_path / "spec/baseline/plans/slices"
    d.mkdir(parents=True)
    (d / "slice-01-f001.md").write_text(
        f"- Step 3c: 数据层 — scope: {scope} | input: x\n", encoding="utf-8")
    return tmp_path

def test_scope_none_produces_no_key(tmp_path):
    """scope=无（说明性中文）→ 0 键，不产 svc______________ 空壳。"""
    m = derive_keys(_mk(tmp_path, "无（仅本地随机与资源映射）"))
    assert not m["keys"]

def test_scope_classnames_kept(tmp_path):
    m = derive_keys(_mk(tmp_path, "FooService, BarStore"))
    assert set(m["keys"]) == {"svc.FooService", "svc.BarStore"}

def test_emit_interface_rejects_garbage_key():
    with pytest.raises(ValueError):
        emit_interface({"keys": {"svc.无效键！": {"provenance": "x"}}})
