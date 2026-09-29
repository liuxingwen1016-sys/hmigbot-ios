# -*- coding: utf-8 -*-
"""assembly_gate 穿刺自测集——固化 2026-08-24 对抗审核的绕过/误拦手法。
每个用例 = 一种手法；红线：绕过用例必须 FAIL，误拦用例必须 0 FAIL。"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "assembly_gate.py"

GUARDED = """export class RuntimeState {
  private hydrated: boolean = false
  hydrate(cfg: string): void { this.hydrated = true }
  require(): string {
    if (!this.hydrated) { throw new Error('not hydrated') }
    return 'ok'
  }
}
"""

def run_gate(root: Path) -> dict:
    out = root / "_r.json"
    subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(root),
                    "--output-json", str(out)], capture_output=True)
    return json.loads(out.read_text(encoding="utf-8"))

def fails(r, kind=None):
    return [f for f in r["findings"] if kind is None or f["kind"] == kind]

def w(root: Path, rel: str, text: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_t1_unassembled_fail(tmp_path):
    """基线：guarded 类零引用 → FAIL（NetworkRuntimeState 形态）。"""
    w(tmp_path, "src/Runtime.ets", GUARDED)
    assert fails(run_gate(tmp_path), "fail-closed-unassembled")


def test_f1_const_singleton_wired_ok(tmp_path):
    """误拦红线：export const 单例正确接线 → 0 FAIL（2026-08-24 审核 F1）。"""
    w(tmp_path, "src/Runtime.ets", GUARDED + "export const runtimeState = new RuntimeState()\n")
    w(tmp_path, "src/Boot.ets",
      "import { runtimeState } from './Runtime'\n"
      "export function boot(): void { runtimeState.hydrate('cfg') }\n")
    assert not fails(run_gate(tmp_path))


def test_injected_field_call_ok(tmp_path):
    """误拦红线：消费方经注入字段名调用装配方法 → 0 FAIL（CX SessionStore 形态）。"""
    w(tmp_path, "src/Store.ets", GUARDED.replace("RuntimeState", "SessionStore"))
    w(tmp_path, "src/Vm.ets",
      "import { SessionStore } from './Store'\n"
      "export class Vm {\n"
      "  private s: SessionStore = new SessionStore()\n"
      "  boot(): void { this.s.hydrate('x') }\n"
      "}\n")
    assert not fails(run_gate(tmp_path))


def test_b4_guard_consumed_fail(tmp_path):
    """B4：守卫方法被消费而装配零调用 → FAIL（830 DeviceIdentityService 形态）。"""
    w(tmp_path, "src/Dev.ets", GUARDED.replace("RuntimeState", "DevService"))
    w(tmp_path, "src/Auth.ets",
      "import { DevService } from './Dev'\n"
      "export class Auth {\n"
      "  private d: DevService = new DevService()\n"
      "  login(): string { return this.d.require() }\n"
      "}\n")
    assert fails(run_gate(tmp_path), "guard-consumed-assembly-never")


def test_b3_comment_new_still_fail(tmp_path):
    """B3：注释里的 new 不算实例化 → 仍 FAIL。"""
    w(tmp_path, "src/Port.ets",
      "export interface RefundPort { run(): void }\n"
      "export class UnavailableRefundPort implements RefundPort {\n"
      "  run(): void { throw new Error('x') }\n"
      "}\n"
      "export class TrackRefundPort implements RefundPort {\n"
      "  run(): void { console.info('real work here'); this.step() }\n"
      "  step(): void { console.info('multi'); console.info('stmt') }\n"
      "}\n")
    w(tmp_path, "src/Note.ets", "// TODO: new TrackRefundPort()\nexport const x = 1\n")
    assert fails(run_gate(tmp_path), "real-impl-never-installed")


def test_b2_dead_wire_still_fail(tmp_path):
    """B2：赋值后零引用的死接线不算装配 → 仍 FAIL。"""
    w(tmp_path, "src/Port.ets",
      "export interface RefundPort { run(): void }\n"
      "export class UnavailableRefundPort implements RefundPort {\n"
      "  run(): void { throw new Error('x') }\n"
      "}\n"
      "export class TrackRefundPort implements RefundPort {\n"
      "  run(): void { console.info('real'); this.aux() }\n"
      "  aux(): void { console.info('a'); console.info('b') }\n"
      "}\n")
    w(tmp_path, "src/Dead.ets",
      "import { TrackRefundPort } from './Port'\n"
      "export const deadWire = new TrackRefundPort()\n")
    assert fails(run_gate(tmp_path), "real-impl-never-installed")


def test_live_wire_ok(tmp_path):
    """对照：真接线（实例被消费）→ 0 FAIL。"""
    w(tmp_path, "src/Port.ets",
      "export interface RefundPort { run(): void }\n"
      "export class UnavailableRefundPort implements RefundPort {\n"
      "  run(): void { throw new Error('x') }\n"
      "}\n"
      "export class TrackRefundPort implements RefundPort {\n"
      "  run(): void { console.info('real'); this.aux() }\n"
      "  aux(): void { console.info('a'); console.info('b') }\n"
      "}\n")
    w(tmp_path, "src/Root.ets",
      "import { TrackRefundPort } from './Port'\n"
      "const wire = new TrackRefundPort()\n"
      "export function boot(): void { wire.run() }\n")
    assert not fails(run_gate(tmp_path))


def test_b1_empty_prefix_fail(tmp_path):
    """B1：清单外习惯前缀（Empty*）→ 命名扩容后 FAIL。"""
    w(tmp_path, "src/Ana.ets",
      "export interface AnaPort { send(): void }\n"
      "export class EmptyAnaPort implements AnaPort {\n"
      "  send(): void { }\n"
      "}\n")
    assert fails(run_gate(tmp_path), "capability-stubbed-no-real-impl")


def test_behavior_stub_fail(tmp_path):
    """B1/B6 兜底：无已知前缀但全方法平凡（throw/假值）→ 行为特征识别 FAIL。"""
    w(tmp_path, "src/Off.ets",
      "export interface PayPort { pay(): boolean }\n"
      "export class OfflinePayPort implements PayPort {\n"
      "  pay(): boolean { return false }\n"
      "}\n")
    assert fails(run_gate(tmp_path), "capability-stubbed-no-real-impl")


def test_b5_multi_interface_fail(tmp_path):
    """B5：implements A, B 两个接口都要查。"""
    w(tmp_path, "src/Multi.ets",
      "export interface PortA { a(): void }\n"
      "export interface PortB { b(): void }\n"
      "export class UnavailableBoth implements PortA, PortB {\n"
      "  a(): void { throw new Error('x') }\n"
      "  b(): void { throw new Error('x') }\n"
      "}\n")
    r = run_gate(tmp_path)
    ifaces = {f["interface"] for f in fails(r, "capability-stubbed-no-real-impl")}
    assert ifaces == {"PortA", "PortB"}


def test_b7_registry_prose_not_downgrade(tmp_path):
    """B7：registry 散文/否定句提及不降级 → 仍 FAIL。"""
    w(tmp_path, "src/Sale.ets",
      "export interface SalePort { go(): void }\n"
      "export class UnavailableSalePort implements SalePort {\n"
      "  go(): void { throw new Error('x') }\n"
      "}\n")
    w(tmp_path, "spec/placeholder-registry.md",
      "# 注册表\n\nSalePort 不豁免，必须实装。UnavailableSalePort 已知。\n")
    assert fails(run_gate(tmp_path), "capability-stubbed-no-real-impl")


def test_b7_registry_pid_row_downgrades(tmp_path):
    """对照：结构化 P-ID 行（status=registered）→ 降级 WARN。"""
    w(tmp_path, "src/Sale.ets",
      "export interface SalePort { go(): void }\n"
      "export class UnavailableSalePort implements SalePort {\n"
      "  go(): void { throw new Error('x') }\n"
      "}\n")
    w(tmp_path, "spec/placeholder-registry.md",
      "| P-ID | location | trigger | status | kind |\n"
      "|---|---|---|---|---|\n"
      "| P-S1-001 | src/Sale.ets#UnavailableSalePort | provider ready | registered | handoff |\n")
    r = run_gate(tmp_path)
    assert not fails(r)
    assert any(x["kind"] == "capability-stubbed-no-real-impl" for x in r["warnings"])


def test_strategy_pattern_ok(tmp_path):
    """误拦红线：策略模式（Unavailable 兜底 + 真实现已接线）→ 0 FAIL。"""
    w(tmp_path, "src/Pay.ets",
      "export interface PayProvider { pay(): void }\n"
      "export class UnavailablePayProvider implements PayProvider {\n"
      "  pay(): void { throw new Error('x') }\n"
      "}\n"
      "export class AlipayProvider implements PayProvider {\n"
      "  pay(): void { console.info('alipay'); this.sign() }\n"
      "  sign(): void { console.info('s1'); console.info('s2') }\n"
      "}\n")
    w(tmp_path, "src/Root.ets",
      "import { AlipayProvider } from './Pay'\n"
      "const p = new AlipayProvider()\n"
      "export function boot(): void { p.pay() }\n")
    assert not fails(run_gate(tmp_path))
