# -*- coding: utf-8 -*-
"""binding_gate 穿刺自测——固化「我的」页四按钮消失事故的判据。"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "binding_gate.py"

def run_gate(root: Path, manifest=None) -> dict:
    out = root / "_r.json"
    cmd = [sys.executable, str(SCRIPT), "--project-root", str(root), "--output-json", str(out)]
    if manifest:
        cmd += ["--manifest", str(manifest)]
    subprocess.run(cmd, capture_output=True)
    return json.loads(out.read_text(encoding="utf-8"))

def w(root: Path, rel: str, text: str):
    p = root / "entry/src/main/ets" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

COMP = """@ComponentV2
export struct Mine {{
  @Local {flag}: boolean = {default}
  build() {{
    Column() {{
      if (this.{flag}) {{
        Text('四按钮')
      }}
    }}
  }}
{extra}
}}
"""

def test_dead_flag_false_fail(tmp_path):
    """事故本尊：默认 false + 零赋值 → FAIL（内容蒸发）。"""
    w(tmp_path, "components/Mine.ets", COMP.format(flag="showServiceCenter", default="false", extra=""))
    r = run_gate(tmp_path)
    assert any(f["kind"] == "dead-render-flag" for f in r["findings"])

def test_dead_flag_true_warn(tmp_path):
    """CC 形态：默认 true + 零赋值 → WARN（阀门失灵，界面侥幸正常）。"""
    w(tmp_path, "components/Mine.ets", COMP.format(flag="showRow", default="true", extra=""))
    r = run_gate(tmp_path)
    assert not r["findings"]
    assert any(x["kind"] == "dead-render-flag" for x in r["warnings"])

def test_wired_flag_ok(tmp_path):
    """接了赋值链 → 0。"""
    w(tmp_path, "components/Mine.ets",
      COMP.format(flag="showServiceCenter", default="false",
                  extra="  refresh(v: boolean): void { this.showServiceCenter = v }"))
    r = run_gate(tmp_path)
    assert not r["findings"] and not r["warnings"]

def _manifest(tmp_path, drivers):
    m = tmp_path / "vb.json"
    m.write_text(json.dumps({"schema": "visibility-bindings.v1", "rows": [
        {"kind": "runtime-toggle", "screen": "MineFragment", "view_id": "ll_service_center",
         "view_id_camel": "llServiceCenter", "drivers": drivers, "src": "MineFragment.kt:115"}]}),
        encoding="utf-8")
    return m

def test_manifest_dropped_fail(tmp_path):
    """安卓绑定的数据驱动名在迁移侧零出现 → binding-dropped FAIL。"""
    w(tmp_path, "components/Mine.ets", COMP.format(flag="somethingElse", default="true",
                                                   extra="  set(): void { this.somethingElse = true }"))
    r = run_gate(tmp_path, _manifest(tmp_path, ["showServiceCenter"]))
    assert any(f["kind"] == "binding-dropped" for f in r["findings"])

def test_manifest_present_ok(tmp_path):
    """驱动名在迁移侧出现 → 该行核销。"""
    w(tmp_path, "components/Mine.ets",
      COMP.format(flag="showServiceCenter", default="false",
                  extra="  refresh(v: boolean): void { this.showServiceCenter = v }"))
    r = run_gate(tmp_path, _manifest(tmp_path, ["showServiceCenter"]))
    assert not r["findings"]

def test_manifest_viewish_driver_skipped(tmp_path):
    """驱动全是视图 id 形态 → 不强判（噪音红线，CC 基线 37FAIL 教训）。"""
    w(tmp_path, "components/Mine.ets", COMP.format(flag="x", default="true",
                                                   extra="  s(): void { this.x = true }"))
    r = run_gate(tmp_path, _manifest(tmp_path, ["ivBack", "llBottom"]))
    assert not any(f["kind"] == "binding-dropped" for f in r["findings"])

STACK_MISUSE = """@ComponentV2
export struct P {
  build() {
    Stack({ alignContent: Alignment.Center }) {
      Text('标题')
      Image($r('app.media.ic')).width(21).height(20).align(Alignment.End)
    }
  }
}
"""

def test_stack_align_misuse_fail(tmp_path):
    """事故本尊：Stack 子项 .align 定位直觉 → FAIL。"""
    w(tmp_path, "pages/P.ets", STACK_MISUSE)
    r = run_gate(tmp_path)
    assert any(f["kind"] == "stack-align-misuse" for f in r["findings"])

def test_stack_align_fullsize_ok(tmp_path):
    """合法惯用法：撑满子项钉自身内容 → 0（CC 基线三处形态）。"""
    w(tmp_path, "pages/P.ets", STACK_MISUSE.replace(
        ".width(21).height(20).align(Alignment.End)",
        ".width('100%').height('100%').align(Alignment.TopStart)"))
    r = run_gate(tmp_path)
    assert not any(f["kind"] == "stack-align-misuse" for f in r["findings"])

def test_patrol_receipt_missing_fail(tmp_path):
    """dice_patrol 首跑实锤：批次收货但巡检被跳过 → FAIL。"""
    w(tmp_path, "pages/A.ets", "@ComponentV2\nexport struct A { build() { Column() {} } }\n")
    wb = tmp_path / "spec/execution/writeback/writeback-batch-01.json"
    wb.parent.mkdir(parents=True, exist_ok=True)
    wb.write_text('{"mode": "batch", "files": ["entry/src/main/ets/pages/A.ets"]}', encoding="utf-8")
    r = run_gate(tmp_path)
    assert any(f["kind"] == "patrol-receipt-missing" for f in r["findings"])

def test_patrol_receipt_present_ok(tmp_path):
    """凭证在（空单也算收货）→ 不报。"""
    w(tmp_path, "pages/A.ets", "@ComponentV2\nexport struct A { build() { Column() {} } }\n")
    wb = tmp_path / "spec/execution/writeback/writeback-batch-01.json"
    wb.parent.mkdir(parents=True, exist_ok=True)
    wb.write_text('{"mode": "batch", "files": ["entry/src/main/ets/pages/A.ets"]}', encoding="utf-8")
    rc = tmp_path / "spec/fix/round-1/patrol/ui-build-batch-01.md"
    rc.parent.mkdir(parents=True, exist_ok=True)
    rc.write_text("---\nsource: patrol\n---\nfindings: 0\n", encoding="utf-8")
    r = run_gate(tmp_path)
    assert not any(f["kind"] == "patrol-receipt-missing" for f in r["findings"])

def test_patrol_receipt_nondomain_batch_skipped(tmp_path):
    """纯编译/账本批（无域目录文件）无巡检义务 → 不报（两端路由一致）。"""
    wb = tmp_path / "spec/execution/writeback/writeback-base-07.json"
    wb.parent.mkdir(parents=True, exist_ok=True)
    wb.write_text('{"build": "BUILD SUCCESSFUL"}', encoding="utf-8")
    r = run_gate(tmp_path)
    assert not any(f["kind"] == "patrol-receipt-missing" for f in r["findings"])
