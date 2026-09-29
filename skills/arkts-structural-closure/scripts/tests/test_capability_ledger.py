# -*- coding: utf-8 -*-
"""capability_ledger_gate 穿刺自测集——三审四 P0 + 契约核心路径全覆盖。"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "capability_ledger_gate.py"

def w(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def plan(root, slices3c="AuthService", base=True):
    if base:
        w(root, "spec/baseline/plans/base-plan.md",
          "# Base\n- Base-3: Network — HttpClient\n- Base-8: 组装根（能力表装配）\n")
    w(root, "spec/baseline/plans/slices/slice-01-f001.md",
      f"- Step 3b: ViewModel — scope: FooCoordinator | x\n"
      f"- Step 3c: 数据层 — scope: {slices3c} | x\n")

def run_gate(root):
    out = root / "_r.json"
    subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(root),
                    "--output-json", str(out)], capture_output=True)
    return json.loads(out.read_text(encoding="utf-8"))

def kinds(r):
    return {f["kind"] for f in r["findings"]}

E = "entry/src/main/ets/"
REAL_AUTH = ("export class AuthService {\n"
             "  login(): void { console.info('a'); this.aux() }\n"
             "  aux(): void { console.info('b'); console.info('c') }\n"
             "}\n")
REAL_NET = ("export class NetworkCore {\n"
            "  request(): void { console.info('r'); this.aux() }\n"
            "  aux(): void { console.info('x'); console.info('y') }\n"
            "}\n")
TABLE = ("import { AuthService } from './services/AuthService'\n"
         "import { NetworkCore } from './network/NetworkCore'\n"
         "const auth = new AuthService()\n"
         "const net = new NetworkCore()\n"
         "export interface CapabilityTable { base_network?: NetworkCore; svc_AuthService?: AuthService }\n"
         "export const capabilityTable: CapabilityTable = {\n"
         "  base_network: net,\n"
         "  svc_AuthService: auth,\n"
         "}\n")


def test_happy_path(tmp_path):
    plan(tmp_path)
    w(tmp_path, E + "services/AuthService.ets", REAL_AUTH)
    w(tmp_path, E + "network/NetworkCore.ets", REAL_NET)
    w(tmp_path, E + "AppAssembly.ets", TABLE)
    r = run_gate(tmp_path)
    assert not r["findings"], r["findings"]


def test_root_missing_fail(tmp_path):
    """三审 P0-3：plan 启用契约而组装根缺席 → FAIL，删文件不降级。"""
    plan(tmp_path)
    w(tmp_path, E + "services/AuthService.ets", REAL_AUTH)
    assert "assembly-root-missing" in kinds(run_gate(tmp_path))


def test_slot_missing_fail(tmp_path):
    """差集：清单键缺席且无 P-ID → FAIL。"""
    plan(tmp_path)
    w(tmp_path, E + "network/NetworkCore.ets", REAL_NET)
    w(tmp_path, E + "AppAssembly.ets",
      "import { NetworkCore } from './network/NetworkCore'\n"
      "const net = new NetworkCore()\n"
      "export interface CapabilityTable { base_network?: NetworkCore }\n"
      "export const capabilityTable: CapabilityTable = {\n  base_network: net,\n}\n")
    r = run_gate(tmp_path)
    assert "capability-slot-missing" in kinds(r)
    assert any(f["class"] == "svc.AuthService" for f in r["findings"])


def test_absent_registered_blessed_warn(tmp_path):
    """缺席 + P-ID + D 祝福键名 → WARN 明账，不 FAIL。"""
    plan(tmp_path)
    w(tmp_path, E + "network/NetworkCore.ets", REAL_NET)
    w(tmp_path, E + "AppAssembly.ets",
      "import { NetworkCore } from './network/NetworkCore'\nconst net = new NetworkCore()\n"
      "export interface CapabilityTable { base_network?: NetworkCore }\n"
      "export const capabilityTable: CapabilityTable = {\n  base_network: net,\n}\n")
    w(tmp_path, "spec/placeholder-registry.md",
      "| P-ID | location | trigger | status | kind |\n|---|---|---|---|---|\n"
      "| P-B1-001 | svc.AuthService | provider ready | registered | handoff | D-010 |\n")
    w(tmp_path, "spec/decision-ledger.md",
      "### D-010 渠道决策\n- 豁免键：svc.AuthService（无官方 SDK，保持缺席）\n")
    r = run_gate(tmp_path)
    assert not r["findings"], r["findings"]
    assert any(x["kind"] == "capability-absent-registered" for x in r["warnings"])


def test_absent_registered_not_blessed_fail(tmp_path):
    """缺席 + P-ID 但 D 没点名该键 → FAIL（护身符防复发）。"""
    plan(tmp_path)
    w(tmp_path, E + "network/NetworkCore.ets", REAL_NET)
    w(tmp_path, E + "AppAssembly.ets",
      "import { NetworkCore } from './network/NetworkCore'\nconst net = new NetworkCore()\n"
      "export interface CapabilityTable { base_network?: NetworkCore }\n"
      "export const capabilityTable: CapabilityTable = {\n  base_network: net,\n}\n")
    w(tmp_path, "spec/placeholder-registry.md",
      "| P-ID | location | trigger | status | kind |\n|---|---|---|---|---|\n"
      "| P-B1-001 | svc.AuthService | x | registered | handoff | D-012 |\n")
    w(tmp_path, "spec/decision-ledger.md", "### D-012 错误处理\n- 与本键无关的正文\n")
    assert "debt-not-blessed" in kinds(run_gate(tmp_path))


def test_remote_stub_in_slot_fail(tmp_path):
    """三审 P0-1：stub 定义在别的文件，槽里只有 import → 定义闭包 lint 抓到。"""
    plan(tmp_path)
    w(tmp_path, E + "network/NetworkCore.ets", REAL_NET)
    w(tmp_path, E + "services/AuthService.ets",
      "export class AuthService {\n  login(): void { throw new Error('unavailable') }\n}\n")
    w(tmp_path, E + "AppAssembly.ets", TABLE)
    assert "stub-in-slot" in kinds(run_gate(tmp_path))


def test_double_instance_fail(tmp_path):
    """三审 P0-2：槽里喂闸一个实例，消费方另 new 一个 → 装饰表旁路 FAIL。"""
    plan(tmp_path)
    w(tmp_path, E + "services/AuthService.ets", REAL_AUTH)
    w(tmp_path, E + "network/NetworkCore.ets", REAL_NET)
    w(tmp_path, E + "AppAssembly.ets", TABLE)
    w(tmp_path, E + "pages/Login.ets",
      "import { AuthService } from '../services/AuthService'\n"
      "const rogue = new AuthService()\nexport function f(): void { rogue.login() }\n")
    assert "non-canonical-instance" in kinds(run_gate(tmp_path))


def test_lifecycle_install_fail(tmp_path):
    """三审 P0-4：槽位类带 hydrate 族装配方法，EntryAbility 没调 install → FAIL。"""
    plan(tmp_path, slices3c="RuntimeState")
    w(tmp_path, E + "network/NetworkCore.ets", REAL_NET)
    w(tmp_path, E + "services/RuntimeState.ets",
      "export class RuntimeState {\n"
      "  private hydrated: boolean = false\n"
      "  hydrate(c: string): void { this.hydrated = true }\n"
      "  require(): string {\n"
      "    if (!this.hydrated) { throw new Error('not hydrated') }\n"
      "    return 'ok'\n"
      "  }\n"
      "}\n")
    w(tmp_path, E + "AppAssembly.ets",
      "import { RuntimeState } from './services/RuntimeState'\n"
      "import { NetworkCore } from './network/NetworkCore'\n"
      "const rt = new RuntimeState()\nconst net = new NetworkCore()\n"
      "export interface CapabilityTable { base_network?: NetworkCore; svc_RuntimeState?: RuntimeState }\n"
      "export const capabilityTable: CapabilityTable = {\n"
      "  base_network: net,\n  svc_RuntimeState: rt,\n}\n")
    w(tmp_path, E + "entryability/EntryAbility.ets",
      "export default class EntryAbility {\n  onCreate(): void { console.info('boot') }\n}\n")
    assert "lifecycle-install-missing" in kinds(run_gate(tmp_path))


def test_lifecycle_install_present_ok(tmp_path):
    """对照：EntryAbility 调了 AppAssembly.install → 0 FAIL。"""
    plan(tmp_path, slices3c="RuntimeState")
    w(tmp_path, E + "network/NetworkCore.ets", REAL_NET)
    w(tmp_path, E + "services/RuntimeState.ets",
      "export class RuntimeState {\n"
      "  private hydrated: boolean = false\n"
      "  hydrate(c: string): void { this.hydrated = true }\n"
      "  require(): string {\n"
      "    if (!this.hydrated) { throw new Error('not hydrated') }\n"
      "    return 'ok'\n"
      "  }\n"
      "}\n")
    w(tmp_path, E + "AppAssembly.ets",
      "import { RuntimeState } from './services/RuntimeState'\n"
      "import { NetworkCore } from './network/NetworkCore'\n"
      "const rt = new RuntimeState()\nconst net = new NetworkCore()\n"
      "export interface CapabilityTable { base_network?: NetworkCore; svc_RuntimeState?: RuntimeState }\n"
      "export const capabilityTable: CapabilityTable = {\n"
      "  base_network: net,\n  svc_RuntimeState: rt,\n}\n"
      "export function installCapabilities(ctx: object): void { rt.hydrate('cfg') }\n")
    w(tmp_path, E + "entryability/EntryAbility.ets",
      "import { installCapabilities } from '../AppAssembly'\n"
      "export default class EntryAbility {\n"
      "  onCreate(): void { installCapabilities({}) }\n}\n")
    assert not kinds(run_gate(tmp_path))


def test_as_cast_fail(tmp_path):
    """表字面量内 as → FAIL。"""
    plan(tmp_path)
    w(tmp_path, E + "services/AuthService.ets", REAL_AUTH)
    w(tmp_path, E + "network/NetworkCore.ets", REAL_NET)
    w(tmp_path, E + "AppAssembly.ets", TABLE.replace(
      "svc_AuthService: auth,", "svc_AuthService: (auth as object) as AuthService,"))
    assert "table-cast-forbidden" in kinds(run_gate(tmp_path))
