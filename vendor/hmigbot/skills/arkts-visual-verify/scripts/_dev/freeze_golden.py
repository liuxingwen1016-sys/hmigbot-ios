#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""freeze_golden.py — 把 `.sh` 侧观测固化成 golden（**退役 .sh 之前跑一次**，2026-09-14 阶段 B）。

用法：
    python3 scripts/_dev/freeze_golden.py            # 全量重新固化（要求 23 个 .sh 还在）
    python3 scripts/_dev/freeze_golden.py --only walk_finalize

产物落 `scripts/_tests/fixtures/golden_sh_0914/`，由 `_tests/test_py_golden_0914.py` 消费。

★ `.sh` 已经退役后要重新固化：先从 git 历史取回，例如
    git show 915_vvSpeed:arkts-skills/skills/arkts-visual-verify/scripts/walk_finalize.sh > walk_finalize.sh
  （取回的文件丢执行位，`chmod +x` 一下；固化完记得删掉，`test_no_sh_left_in_scripts` 守着 scripts/ 无 .sh）

★ 落盘里**不许出现任何绝对路径**（2026-09-15 阶段 C）：观测正文由 sh_py_parity.normalize 归一
  （`<ROOT>` / `<SCRIPTS>` / `<SKILLS>` / `<TMP>` / `<REAL_PROJECT>`），元数据 `requires_fixture`
  写占位符 `<REAL_PROJECT>`。`_tests/test_py_golden_0914.py::test_goldens_have_no_absolute_paths`
  是这条的机械闸——否则换 checkout / 换机器就红（阶段 B 实爆两例）。
  真实工程用例要跑得先 `export VV_PARITY_REAL_PROJECT=<鸿蒙工程根>`，否则那 8 例 SKIP。
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import golden as G  # noqa: E402
import parity_cases  # noqa: E402

if sys.platform.startswith("win"):
    for _st in (sys.stdout, sys.stderr):
        try:
            _st.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def fixture_digest(path):
    """夹具目录的内容指纹（真实工程夹具会随工程演进漂移 → 用它让套件 skip 而不是误红）。"""
    h = hashlib.sha256()
    if not path or not os.path.isdir(path):
        return ""
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(d for d in dirnames if d not in (".git", "__pycache__"))
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, path).replace(os.sep, "/")
            h.update(rel.encode("utf-8"))
            try:
                with open(p, "rb") as fh:
                    while True:
                        b = fh.read(1 << 20)
                        if not b:
                            break
                        h.update(b)
            except OSError:
                h.update(b"<UNREADABLE>")
    return h.hexdigest()[:16]


COMPOSE_LABEL_H = 60      # 标签带高度：唯一允许不同的区域（.sh 的 PingFang.ttc 在 macOS 15+ 已不存在）


def freeze_compose_geometry(out_dir):
    """compose_side_by_side 的**几何**golden：画布尺寸 + 标签带以下像素的哈希。

    为什么不冻 jpeg 本体：那张图 165 KB，且字节随 Pillow/字体版本漂移。真正要锁住的断言是
    「.py 的拼图与 .sh 的拼图**只在标签带不同**，画布尺寸与两张图的粘贴区逐像素相同」
    —— 存 (W,H) + crop(0,60,W,H) 的 sha256 就够，且只有几十字节。
    """
    try:
        from PIL import Image
    except ImportError:
        print("SKIP  compose 几何 golden（无 Pillow）")
        return
    d = tempfile.mkdtemp(prefix="fx_compose_")
    try:
        parity_cases._fx_two_imgs(d)
        a_png, b_png = os.path.join(d, "a.png"), os.path.join(d, "b.png")
        out = os.path.join(d, "o_sh.jpeg")
        sh = os.path.join(os.path.dirname(_HERE), "compose_side_by_side.sh")
        import subprocess
        subprocess.run(["bash", sh, a_png, b_png, out], capture_output=True, check=True)
        im = Image.open(out).convert("RGB")
        w, h = im.size
        body = hashlib.sha256(im.crop((0, COMPOSE_LABEL_H, w, h)).tobytes()).hexdigest()
        rec = {"label_band_h": COMPOSE_LABEL_H, "size": [w, h], "body_sha256": body,
               "why": ".sh 侧实跑冻结；.py 侧必须画布同尺寸、标签带以下逐像素相同"}
        with open(os.path.join(out_dir, "_compose_geometry.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        print("OK    compose 几何 golden → _compose_geometry.json  %sx%s" % (w, h))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只固化这个脚本名")
    ap.add_argument("--out", default=G.GOLDEN_DIR)
    a = ap.parse_args()

    missing = [n for n in G.RETIRED_SH_0914
               if not os.path.isfile(os.path.join(os.path.dirname(_HERE), n + ".sh"))]
    if missing and not a.only:
        print("✗ 这些 .sh 不在场，固化会不完整：%s" % missing, file=sys.stderr)
        print("  从 git 历史取回：git show 915_vvSpeed:<skill>/scripts/<name>.sh > <name>.sh", file=sys.stderr)
        return 2

    os.makedirs(a.out, exist_ok=True)
    for old in os.listdir(a.out):
        if old.endswith(".json") and (not a.only or ("_%s__" % a.only) in old):
            os.remove(os.path.join(a.out, old))

    cases = parity_cases.build_cases()
    manifest = {"generated_for": "arkts-visual-verify 全 py 化（阶段 B，2026-09-14）",
                "source": "23 个 .sh 退役前的实跑观测；用例矩阵 = _dev/parity_cases.py",
                "retired_sh": G.RETIRED_SH_0914, "cases": []}
    n_ok = n_skip = 0
    for idx, case in enumerate(cases):
        if a.only and case["script"] != a.only:
            continue
        need = case.get("requires_fixture")
        if need and not os.path.exists(need):
            print("SKIP  %s（缺真实工程夹具 %s）" % (G.case_id(case), need))
            n_skip += 1
            continue
        tmp = None
        try:
            fx = case.get("fixture_factory")
            if fx:
                tmp = tempfile.mkdtemp(prefix="fx_")
                fx(tmp)
            obs = G.observe_sh(case, case.get("args", []), tmp)
            rec = {"script": case["script"], "name": case.get("name", ""),
                   "args": list(case.get("args", [])), "case_index": idx,
                   "ignore": list(case.get("ignore") or []),
                   "observation": obs}
            if need:
                rec["fixture_digest"] = fixture_digest(tmp or case.get("fixture"))
                # 只落占位符：绝对路径进 golden = 换机器必红（阶段 C）
                rec["requires_fixture"] = (parity_cases.REAL_PROJECT_PLACEHOLDER
                                           if need == parity_cases.real_spec_root() else need)
            fn = G.golden_name(idx, case)
            with open(os.path.join(a.out, fn), "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False, indent=1, sort_keys=True)
                f.write("\n")
            manifest["cases"].append({"file": fn, "id": G.case_id(case)})
            n_ok += 1
            print("OK    %s → %s" % (G.case_id(case), fn))
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    if not a.only or a.only == "compose_side_by_side":
        freeze_compose_geometry(a.out)

    mpath = os.path.join(a.out, "_manifest.json")
    if a.only and os.path.isfile(mpath):
        # `--only` 是**局部**重固化：整份 manifest 直接覆盖会把没重跑的用例从清单里抹掉
        # （2026-09-15 阶段 C 实测的坑）。按 file 名合并，保持全量清单与 golden 目录同步。
        with open(mpath, encoding="utf-8") as f:
            old = json.load(f)
        merged = {c["file"]: c for c in (old.get("cases") or [])}
        merged.update({c["file"]: c for c in manifest["cases"]})
        manifest = dict(old, **{k: v for k, v in manifest.items() if k != "cases"})
        manifest["cases"] = [merged[k] for k in sorted(merged)]
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print("\n固化 %d 例，跳过 %d 例 → %s" % (n_ok, n_skip, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
