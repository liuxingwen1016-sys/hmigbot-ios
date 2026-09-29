#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_android_apis.py v1.3 特性常驻回归单测（Track-1 脚本单测轨，毕业自 v1.3 验证轮 2026-07-17）。

守护 v1.3 新增 8 项抽取能力不回退：
  ① Java Retrofit 接口（Observable/Call 返回 + @Field/@Query/@Path/@Body/@HeaderMap，
     单行长签名与多行对齐签名）
  ② @Url 动态端点（裸 @GET/@POST + path_is_dynamic 标记）
  ③ @Headers 静态注解（endpoint.static_headers；Kotlin 圆括号多值 / Java 单串 / Java 花括号数组）
  ④ 调用点回溯（endpoint.callers：非 Service 文件 `.methodName(` 的 file+line）
  ⑤ 拦截器抽取（`: Interceptor`/`implements Interceptor` + evidence 标签正负例、同文件多实现）
  ⑥ body_assembly_sites（mutableMapOf / JSONObject().put / FormBody.Builder().add 三模式，
     含 enclosing_function 与字段表）
  ⑦ gradle_config（buildConfigField / manifestPlaceholders / applicationId / flavor 行）
  ⑧ base_urls 的 environment=build-config（BuildConfig 动态拼接）

fixtures_v13/ 改编自真实工程 D:\\Coding\\Android\\AndroidProject\\xiaoyibang（去业务化，
synthetic 项在各文件头注明）。真值 ground_truth_v13.json = 逐字读 fixtures 手工推导
（反循环：非脚本输出回抄）。判定为超集通过：scanner 多抽不算错，漏抽/值错才 FAIL。
另含 advisory 探针（Gson JsonObject.addProperty 组装，真实工程主流模式）：只打印不计入 exit code。

缺陷锚（feature 前缀 `D-`，当前预期 FAIL、修复后应翻绿，FAIL 清单交 skill-mutator）：
  D-A  Java 注解数组花括号形态 @Headers({...}) 的 static_headers 全丢
       （@Headers 回溯步 `'}' in prev` 停用条件误吞注解自身花括号）
  D-B  Java 常量车道全漏：接口体 `String X = "...";` / `public static final String`
       不解析 → url_constants/api_related_constants 空、base_urls 缺 Java 来源、
       ApiPath.X 引用端点无 resolved_path（另叠加 url_constants 前导 `/` 过滤阻塞）

用法:
  python test_extract_v13.py                       # 候选 v1.3 脚本；exit 0=全过 1=有回归
  EXTRACT_SCRIPT=<path> python test_extract_v13.py # 判别力验证：指向旧版脚本应大量 FAIL
未来任何改 extract_android_apis.py 后必跑本测 + test_extract_fidelity.py，须保持全过。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("EXTRACT_SCRIPT") or os.path.join(HERE, "..", "extract_android_apis.py")
FIXTURES = os.path.join(HERE, "fixtures_v13")
OUT = os.environ.get("EXTRACT_OUT") or os.path.join(HERE, "_out_v13")
GT = os.path.join(HERE, "ground_truth_v13.json")

results = []  # (feature, id, ok, why)


def rec(feature, item_id, ok, why):
    results.append((feature, item_id, ok, why))
    print(f"  {'PASS' if ok else 'FAIL'}  {item_id:<28} {why}")


def judge_endpoint(g, ep):
    if ep is None:
        return False, "ENDPOINT 丢失"
    reasons = []
    if g.get("http_method") and ep.get("http_method") != g["http_method"]:
        reasons.append(f"method:{ep.get('http_method')}≠{g['http_method']}")
    if "resolved_path" in g:
        got = ep.get("resolved_path") or ep.get("path")
        if got != g["resolved_path"]:
            reasons.append(f"路径未resolve:`{got}`")
    elif "path" in g and ep.get("path", None) != g["path"]:
        reasons.append(f"path:`{ep.get('path')}`≠`{g['path']}`")
    if "path_is_dynamic" in g and bool(ep.get("path_is_dynamic")) != g["path_is_dynamic"]:
        reasons.append(f"path_is_dynamic:{ep.get('path_is_dynamic')}≠{g['path_is_dynamic']}")
    if "path_is_constant" in g and bool(ep.get("path_is_constant")) != g["path_is_constant"]:
        reasons.append("path_is_constant 标记错")
    if "is_suspend" in g and bool(ep.get("is_suspend")) != g["is_suspend"]:
        reasons.append("is_suspend 标记错")
    names = [p.get("name") for p in ep.get("params", [])]
    missing = [p for p in g.get("params", []) if p not in names]
    if missing:
        reasons.append(f"缺参{missing}")
    got_headers = ep.get("static_headers", [])
    miss_h = [h for h in g.get("static_headers", []) if h not in got_headers]
    if miss_h:
        reasons.append(f"缺static_headers{miss_h}(实际{got_headers})")
    for exp_c in g.get("callers", []):
        got_pairs = {(c.get("file_path"), c.get("line_number")) for c in ep.get("callers", [])}
        for ln in exp_c["lines"]:
            if (exp_c["file_path"], ln) not in got_pairs:
                reasons.append(f"缺caller {exp_c['file_path']}:{ln}(实际{sorted(got_pairs)})")
    return (not reasons), ("; ".join(reasons) if reasons else f"OK({len(names)}参)")


def judge_interceptor(g, entries):
    hits = [e for e in entries if e.get("name") == g["name"]]
    if not hits:
        return False, "拦截器丢失"
    e = hits[0]
    reasons = []
    if e.get("file_path") != g["file_path"]:
        reasons.append(f"file:{e.get('file_path')}")
    if e.get("implements") != g["implements"]:
        reasons.append(f"implements:{e.get('implements')}≠{g['implements']}")
    ev = set(e.get("evidence", []))
    miss = [t for t in g["evidence_expect"] if t not in ev]
    if miss:
        reasons.append(f"缺evidence{miss}(实际{sorted(ev)})")
    bad = [t for t in g["evidence_absent"] if t in ev]
    if bad:
        reasons.append(f"误报evidence{bad}")
    return (not reasons), ("; ".join(reasons) if reasons else f"OK(evidence={sorted(ev)})")


def judge_body_site(g, sites):
    hits = [s for s in sites
            if s.get("file_path") == g["file_path"]
            and s.get("enclosing_function") == g["enclosing_function"]
            and s.get("kind") == g["kind"]]
    if not hits:
        near = [s for s in sites if s.get("file_path") == g["file_path"]]
        return False, f"组装点丢失(同文件实际{[(s.get('enclosing_function'), s.get('kind')) for s in near]})"
    got_fields = {f.get("name") for s in hits for f in s.get("fields", [])}
    miss = [f for f in g["fields"] if f not in got_fields]
    if miss:
        return False, f"缺字段{miss}(实际{sorted(got_fields)})"
    return True, f"OK({len(got_fields)}字段)"


def judge_gradle(g, entries):
    hits = [e for e in entries
            if e.get("kind") == g["kind"]
            and e.get("file_path") == g["file_path"]
            and g["raw_contains"] in e.get("raw", "")]
    if not hits:
        return False, f"gradle行丢失 kind={g['kind']} contains`{g['raw_contains']}`"
    return True, "OK"


def judge_base_url(g, entries):
    hits = [e for e in entries
            if e.get("name") == g["name"] and e.get("environment") == g["environment"]]
    if not hits:
        same_name = [(e.get("name"), e.get("environment")) for e in entries if e.get("name") == g["name"]]
        return False, f"base_url丢失(同名实际{same_name})"
    e = hits[0]
    if "url" in g and e.get("url") != g["url"]:
        return False, f"url:`{e.get('url')}`≠`{g['url']}`"
    if "url_contains" in g and g["url_contains"] not in e.get("url", ""):
        return False, f"url不含`{g['url_contains']}`:`{e.get('url')}`"
    return True, f"OK({e.get('url')[:60]})"


def main():
    subprocess.run([sys.executable, SCRIPT, "--source-dir", FIXTURES, "--output-dir", OUT],
                   check=True, stdout=subprocess.DEVNULL)
    raw = json.load(open(os.path.join(OUT, "raw_apis.json"), encoding="utf-8"))
    gt = json.load(open(GT, encoding="utf-8"))

    ep_idx = {e.get("method_name"): e
              for s in raw.get("services", []) for e in s.get("endpoints", [])}
    interceptors = raw.get("interceptors", [])
    sites = raw.get("body_assembly_sites", [])
    gradle = raw.get("gradle_config", [])
    base_urls = raw.get("base_urls", [])

    print("=" * 78)
    print("· 端点（①Java / ②@Url动态 / ③@Headers / ④callers）")
    for g in gt["endpoints"]:
        ok, why = judge_endpoint(g, ep_idx.get(g["method_name"]))
        rec(g["feature"], g["method_name"], ok, why)

    print("· 拦截器（⑤）")
    for g in gt["interceptors"]:
        ok, why = judge_interceptor(g, interceptors)
        rec(g["feature"], g["name"], ok, why)

    print("· 请求体组装点（⑥）")
    for g in gt["body_assembly_sites"]:
        ok, why = judge_body_site(g, sites)
        rec(g["feature"], f"{g['enclosing_function']}[{g['kind']}]", ok, why)

    print("· gradle_config（⑦）")
    for g in gt["gradle_config"]:
        ok, why = judge_gradle(g, gradle)
        rec(g["feature"], f"{g['kind']}:{g['raw_contains'][:24]}", ok, why)

    print("· base_urls（⑧）")
    for g in gt["base_urls"]:
        ok, why = judge_base_url(g, base_urls)
        rec(g["feature"], g["name"], ok, why)

    db = gt.get("db_java_const_resolution")
    if db:
        print("· D-B Java 常量车道（缺陷锚组：当前预期 FAIL，修复后应翻绿）")
        for g in db.get("resolved_paths", []):
            ep = ep_idx.get(g["method_name"])
            if ep is None:
                ok, why = False, "ENDPOINT 丢失"
            elif ep.get("resolved_path") != g["resolved_path"]:
                ok, why = False, f"resolved_path:`{ep.get('resolved_path')}`≠`{g['resolved_path']}`"
            else:
                ok, why = True, f"OK({g['resolved_path']})"
            rec("D-B①resolve", f"resolve:{g['method_name']}", ok, why)
        ucs = raw.get("url_constants", [])
        for g in db.get("url_constants", []):
            hit = any(u.get("constant_ref") == g["constant_ref"]
                      and u.get("resolved_value") == g["resolved_value"] for u in ucs)
            rec("D-B②url_const", g["constant_ref"], hit,
                "OK" if hit else f"url_constants 缺条目(实际共{len(ucs)}条)")
        arcs = raw.get("api_related_constants", [])
        for g in db.get("api_related_constants", []):
            hit = any(a.get("name") == g["name"] and a.get("value") == g["value"]
                      and a.get("category") == g["category"] for a in arcs)
            near = [a.get("category") for a in arcs if a.get("name") == g["name"]]
            rec("D-B③api_const", g["name"], hit,
                "OK" if hit else f"api_related_constants 缺 {g['category']} 桶条目(同名实际桶{near})")
        for g in db.get("base_urls", []):
            ok, why = judge_base_url(g, base_urls)
            rec(g["feature"], g["name"], ok, why)

    fails = [(f, i) for f, i, ok, _ in results if not ok]
    anchor_fails = [i for f, i in fails if f.startswith("D-")]
    other_fails = [i for f, i in fails if not f.startswith("D-")]
    n = len(results)
    print("=" * 78)
    print(f"{n - len(fails)}/{n} pass")
    if anchor_fails:
        print(f"  · 缺陷锚 FAIL（D-A/D-B 已知现状，清单交 skill-mutator）×{len(anchor_fails)}: {anchor_fails}")
    if other_fails:
        print(f"  · 非锚回归 FAIL ×{len(other_fails)}: {other_fails}")
    if not fails:
        print("  · 全过（含缺陷锚全部翻绿）")

    # ── advisory（不计入 exit code）──
    adv = gt.get("advisory", {}).get("gson_addproperty_probe")
    if adv:
        probe_hits = [s for s in sites if s.get("file_path") == adv["file_path"]]
        if probe_hits:
            print(f"  ADVISORY  Gson addProperty 探针：scanner 抽到了 {len(probe_hits)} 个组装点（超预期覆盖）")
        else:
            print("  ADVISORY  Gson addProperty 探针：scanner 未抽到（预期缺席=文档三模式 vs 真实工程"
                  "主流 JsonObject.addProperty 的覆盖缺口证据；不计 FAIL）")

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
