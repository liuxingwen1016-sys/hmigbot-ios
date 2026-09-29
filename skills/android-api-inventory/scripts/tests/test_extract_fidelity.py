#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_android_apis.py 抽取保真常驻回归单测（毕业自 I-C2-extract-fidelity Track-1）。

守护 4 类历史缺陷不复发：
  #1 >15 行签名截断(静默丢 endpoint) / #2 泛型类型逗号截断 /
  #3 vararg 漏参 / #6 @HTTP 自定义方法丢 endpoint。
真值 ground_truth.json = 逐字读 fixtures 得(非脚本导出，破循环)。

用法: python test_extract_fidelity.py     # exit 0 = 全过；exit 1 = 有回归
未来任何改 extract_android_apis.py 后必跑本测、须保持全过。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "extract_android_apis.py")
FIXTURES = os.path.join(HERE, "fixtures")
OUT = os.path.join(HERE, "_out")
GT = os.path.join(HERE, "ground_truth.json")


def judge(g, ex):
    if ex is None:
        return False, f"ENDPOINT 丢失（真值 {len(g['params'])} 参）"
    names = [p.get("name") for p in ex.get("params", [])]
    reasons = []
    missing = [p for p in g["params"] if p not in names]
    if missing:
        reasons.append(f"缺参{missing}")
    for pname, ttype in g.get("param_types", {}).items():
        exp = next((p for p in ex.get("params", []) if p.get("name") == pname), None)
        if exp is not None and exp.get("type", "").strip() != ttype:
            reasons.append(f"类型漂移{pname}:`{exp.get('type','').strip()}`≠`{ttype}`")
    if "resolved_path" in g:
        got = ex.get("resolved_path") or ex.get("path")
        if got != g["resolved_path"]:
            reasons.append(f"路径未resolve:`{got}`")
    return (not reasons), ("; ".join(reasons) if reasons else f"OK({len(names)}参)")


def main():
    subprocess.run([sys.executable, SCRIPT, "--source-dir", FIXTURES, "--output-dir", OUT],
                   check=True, stdout=subprocess.DEVNULL)
    raw = json.load(open(os.path.join(OUT, "raw_apis.json"), encoding="utf-8"))
    gt = json.load(open(GT, encoding="utf-8"))
    idx = {e.get("method_name"): e for s in raw.get("services", []) for e in s.get("endpoints", [])}

    fails = []
    print("=" * 70)
    for g in gt["endpoints"]:
        ok, why = judge(g, idx.get(g["method_name"]))
        print(f"  {'PASS' if ok else 'FAIL'}  {g['method_name']:<15} {why}")
        if not ok:
            fails.append(g["method_name"])
    n = len(gt["endpoints"])
    print("=" * 70)
    print(f"{n - len(fails)}/{n} pass" + (f"  · 回归: {fails}" if fails else "  · 全过"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
