# -*- coding: utf-8 -*-
"""Regression: pipeline component-orphan pass must cover /dialogs/ and must not
exempt dialog orphans via the VM usage-evidence path.

Graduated anchor from strategy2 issue I-C16-dead-components (2026-07-10):
  - dialogs/PrivacyPolicyDialog.ets  unreferenced @CustomDialog -> MUST be flagged
    (pre-fix escapes twice: dir-hint gate missed /dialogs/; Exemption-4 own-file-use
    matched the mandatory CustomDialogController self-reference)
  - dialogs/ConfirmDialog.ets        imported+rendered           -> must NOT be flagged
  - components/OrphanCard.ets        unreferenced                -> flagged (covered-dir control)
  - components/UsedCard.ets          imported+rendered           -> not flagged
  - services/DeadService.ets         true VM orphan              -> flagged (VM path intact)
  - services/ConfigService.ets       static-access only          -> exempted, not flagged

Run: python tests/test_component_orphan_dialogs.py   (from scripts/ dir, or any cwd)
"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "c16_component_orphans"


def main() -> int:
    sys.path.insert(0, str(SCRIPTS_DIR))
    import structural_loop

    out = Path(__file__).resolve().parent / "_c16_orphans_out.json"
    result = structural_loop._run_pipeline_orphans(FIXTURE, out)
    out.unlink(missing_ok=True)

    flagged = {o["class_name"] for o in result["orphans"]}
    exempted = {o["class_name"] for o in result.get("exempted", [])}

    checks = {
        "dialogs/ orphan flagged (C16 anchor)": "PrivacyPolicyDialog" in flagged,
        "referenced dialog not flagged": "ConfirmDialog" not in flagged,
        "components/ orphan flagged": "OrphanCard" in flagged,
        "referenced component not flagged": "UsedCard" not in flagged,
        "true VM orphan flagged": "DeadService" in flagged,
        "static-access VM exempted": "ConfigService" not in flagged and "ConfigService" in exempted,
    }
    ok = True
    for name, cond in checks.items():
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
