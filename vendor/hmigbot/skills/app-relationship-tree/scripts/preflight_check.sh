#!/usr/bin/env bash
# preflight_check.sh — 检查 fact-tree 是否完成所有 LLM phase
#
# 每个 LLM phase 的完成判定:
#   Phase 2   补 purpose:            所有 record.purpose != null
#   Phase 2.5 补 inbound_triggers:   有 inbound 的 record 必有 inbound_triggers
#   Phase 2.6 补 navigation_contract: 所有 Fragment/Dialog/Activity 都有 contract，
#                                     且 contract_uncertain==false（除 host_default）
#   Phase 2.7 补 preconditions:      有 preconditions 字段的 record，其 source 不能全是 toolkit
#
# 用法:
#   preflight_check.sh [path/to/toolkit-fact-tree.json]
#
# 退出码:
#   0  所有 LLM phase 完成（可进入下游）
#   1  存在未完成 LLM phase（打印明确指令）
#   2  fact-tree 不存在 / 损坏

set -eo pipefail

SKILLS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"  # <SKILLS_ROOT>/<skill>/scripts → SKILLS_ROOT
SCRIPT_DIR_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="${1:-spec/toolkit-fact-tree.json}"

if [[ ! -f "$TREE" ]]; then
  echo "❌ fact-tree not found: $TREE" >&2
  echo "   先跑 toolkit-fact-indexer:" >&2
  echo "   python3 $SKILLS_ROOT/toolkit-fact-indexer/scripts/toolkit_to_fact_tree_draft.py \\" >&2
  echo "       --toolkit-out . --android-root <ANDROID_ROOT> --out spec/.cache/fact-tree" >&2
  exit 2
fi

if ! jq empty "$TREE" >/dev/null 2>&1; then
  echo "❌ fact-tree 损坏: $TREE" >&2
  exit 2
fi

INCOMPLETE=0
MESSAGES=()

# Phase 2: purpose 完整度
purpose_null=$(jq '[(.pages[],.fragments[],.dialogs[]) | select(.purpose==null)] | length' "$TREE")
purpose_total=$(jq '[(.pages[],.fragments[],.dialogs[])] | length' "$TREE")
if [[ "$purpose_null" -gt 0 ]]; then
  MESSAGES+=("📌 Phase 2 (LLM 补 purpose): $purpose_null / $purpose_total record purpose=null")
  MESSAGES+=("   派 sub-agent: 跑 app-relationship-tree Phase 2 LLM 补 purpose")
  INCOMPLETE=$((INCOMPLETE+1))
fi

# Phase 2.5: inbound_triggers —— 对齐 SKILL Phase 5 HARD 契约：**每条 record 都必须有"有效"inbound_triggers（≥1）**
# 旧口径只查"有 toolkit inbound 边但缺 label"，隐含假设 toolkit 必给边骨架。字符串路由框架
# （ARouter/TheRouter/WMRouter）项目 toolkit 追不到边 → navigation.inbound 全空 → 孤儿 record
# 对旧闸完全不可见（Fitness 实测 131/137 孤儿只报 22 欠账，下游 67 页被误判 structurally_unreachable）。
# v2 口径（2026-07-13，堵"纸面边"空子）：**有效边 = trigger_label 是真实可点文案**——
#   非空、非 *unknown*、非方法名/代码锚点形态（含 . / ( 的纯标识符串，如 "initView/onClick"）。
#   无效边照样凑得出 reach_path≥3 的纸面链，chain_walk 到那跳必匹配不到 → 不许计入分子。
#   确实查无入口的 LLM 应填 trigger_label_unknown + notes（诚实），该 record 计入欠账但不算违规。
# 2026-09-08 夜：只算 walkable record（walkability 缺失按 walkable）；list_item 带根 id / span 带子串 也算可执行
trigger_missing=$(jq '
  def actionable: (((.trigger_label // "") != "")
    and ((.trigger_label | test("unknown"; "i")) | not)
    and ((.trigger_label | test("^[A-Za-z_$][A-Za-z0-9_$]*([./(][A-Za-z0-9_$/.()]*)+$")) | not))
    or (.trigger_kind == "list_item" and (.trigger_view_id // "") != "")
    or (.trigger_kind == "span" and (.span_text // "") != "")
    or (.trigger_kind == "auto" or .trigger_kind == "back" or .trigger_kind == "async_after_tap");
  [(.pages[],.fragments[],.dialogs[]) | select((.walkability.status // "walkable") == "walkable")
    | select([(.inbound_triggers // [])[] | select((.disproven | not) and actionable)] | length == 0)] | length' "$TREE")
orphan_missing=$(jq '[(.pages[],.fragments[],.dialogs[]) | select((.walkability.status // "walkable") == "walkable") | select((.navigation.inbound|length)==0 and (.inbound_triggers==null or .inbound_triggers==[]))] | length' "$TREE")
nc_manifest=$(jq '(.stats.node_completeness.manifest_activities_not_in_tree // []) | length' "$TREE")
nc_sub=$(jq '[(.stats.node_completeness.subclasses_not_in_tree // {}) | to_entries[] | .value | length] | add // 0' "$TREE")
nonwalk_n=$(jq '[(.pages[],.fragments[],.dialogs[]) | select((.walkability.status // "walkable") != "walkable")] | length' "$TREE")
MESSAGES+=("ℹ️  可走性/完备性（不判定）: 非 walkable record $nonwalk_n 个（不计入缺口）；manifest 声明但不在树 $nc_manifest / 继承页面基类但不在树 $nc_sub（stats.node_completeness，1.5 补 record 的依据）")
if [[ "$trigger_missing" -gt 0 ]]; then
  MESSAGES+=("📌 Phase 2.5 (LLM 补 inbound_triggers): $trigger_missing 个 walkable record 缺**有效**inbound_triggers（label 须为真实可点文案；其中 $orphan_missing 个连 toolkit inbound 边也没有——先看 walkability.facts（死码/外部拉起/抽象类已剔除），再看 stats.node_completeness；只有确认项目用字符串路由（@Route/ARouter 类注解、路由表）时才走「路由表→调用点→按钮文案」反查，别预设）")
  MESSAGES+=("   派 sub-agent: 跑 app-relationship-tree Phase 2.5 LLM 读源码反查 onClick 按钮文案")
  INCOMPLETE=$((INCOMPLETE+1))
fi

# Phase 2.5b（2026-09-08，同日改为只报数不判定）：机械候选边的核实欠账 + 边级文案覆盖（记分卡 E2）
#   Phase 2.4 把 navigation.inbound 的候选机械落成 inbound_triggers（provenance.status=candidate，文案尽力解析）。
#   这里只把"仍是候选且无文案"的条数与 E2 打印出来当**测量**，不计入 INCOMPLETE：
#   核实范围/抽样/完成判据由 LLM 阶段按项目自定并在报告里说明（E2 的可达上限因项目而异——
#   菜单/抽屉/动态文案多的项目机械上限只有个位数百分比，用固定阈值会把"诚实"判成"未完成"）。
pending_candidates=$(jq '
  [(.pages[],.fragments[],.dialogs[]) | (.inbound_triggers // [])[]
   | select(((.provenance.status // "") == "candidate" or .candidate == true) and (.disproven | not)
            and ((.trigger_label // "") == "" or (.trigger_label | test("unknown"; "i"))))] | length' "$TREE")
e2_pct=$(python3 "$SCRIPT_DIR_SELF/tree_coverage_report.py" "$TREE" --json /tmp/_tcr_$$.json >/dev/null 2>&1 && python3 -c "import json;print(int(round(json.load(open('/tmp/_tcr_$$.json'))['E2']['r']*100)))" 2>/dev/null || echo 0)
rm -f /tmp/_tcr_$$.json
MESSAGES+=("ℹ️  Phase 2.5 测量（不判定）: 未核实且无文案的机械候选 $pending_candidates 条，边级真文案覆盖 E2=${e2_pct}%；核实策略与完成口径见 LLM 阶段报告")
# Phase 2.3: reach_path 链契约 —— 焊死 SKILL Phase 5 HARD 契约"非 launcher 至少 3 元素(root+token+self)"
# （2026-07-13：此契约原只存在于 SKILL 散文，无脚本执行 → Fitness 97/137 单节点纸面链静默过闸，
#   烧掉一轮设备时间后才暴露。单节点 = 无"根→目标"链 = 下游 chain_walk 必卡 + 鸿蒙侧无链可镜像。）
# ⚠️ 编排顺序坑：run_all_phases 里 2.3 跑在 2.5 之前——2.5 补完有效边后**必须重跑 compute_reach_paths.py**，
#   否则新边不入链。本闸红时若 2.5 已完成，多半就是漏了重跑 2.3。
launcher_id=$(jq -r '.app.launcher_short // ""' "$TREE")
chain_missing=$(jq --arg L "$launcher_id" '
  [(.pages[],.fragments[],.dialogs[]) | select(.id != $L and ((.reach_path // []) | length) < 3)] | length' "$TREE")
if [[ "$chain_missing" -gt 0 ]]; then
  MESSAGES+=("📌 Phase 2.3 (reach 链合成): $chain_missing record reach_path<3（单节点=纸面链，无根→目标可走链）")
  MESSAGES+=("   修法: 先补 Phase 2.5 有效边 → 再重跑 python3 \$SKILLS_ROOT/app-relationship-tree/scripts/compute_reach_paths.py <tree>")
  INCOMPLETE=$((INCOMPLETE+1))
fi

# Phase 2.6: navigation_contract.contract_uncertain
contract_uncertain=$(jq '[(.pages[],.fragments[],.dialogs[]) | select(.navigation_contract.contract_uncertain==true)] | length' "$TREE")
contract_total=$(jq '[(.pages[],.fragments[],.dialogs[]) | select(.navigation_contract!=null)] | length' "$TREE")
if [[ "$contract_uncertain" -gt 0 ]]; then
  MESSAGES+=("📌 Phase 2.6 (LLM 补 navigation_contract.label): $contract_uncertain / $contract_total contract_uncertain=true")
  MESSAGES+=("   派 sub-agent: 跑 app-relationship-tree Phase 2.6 LLM 补 contract.label + verify_signal")
  MESSAGES+=("   清单: spec/visual-verify/contracts_uncertain.md")
  INCOMPLETE=$((INCOMPLETE+1))
fi

# Phase 2.7: preconditions LLM 扩充（toolkit enhancer 已抽的 5 类基础不算 LLM）
# 检查是否有 record 的 preconditions 含 source: app_relationship_tree:* 前缀
llm_preconditions=$(jq '[(.pages[],.fragments[],.dialogs[]) | select(.preconditions!=null) | .preconditions[] | select(.source | startswith("app_relationship_tree:"))] | length' "$TREE")
toolkit_preconditions=$(jq '[(.pages[],.fragments[],.dialogs[]) | select(.preconditions!=null) | .preconditions[] | select(.source=="preconditions_enhancer")] | length' "$TREE")
if [[ "$toolkit_preconditions" -gt 0 && "$llm_preconditions" -eq 0 ]]; then
  MESSAGES+=("📌 Phase 2.7 (LLM 扩 preconditions): 仅有 $toolkit_preconditions 条 toolkit 抽的基础，0 条 LLM 扩充")
  MESSAGES+=("   派 sub-agent: 跑 app-relationship-tree Phase 2.7 LLM 从 page_*.md 扩 preconditions")
  INCOMPLETE=$((INCOMPLETE+1))
fi

# Phase 2.7 极性覆盖（2026-09-09）——账号态前置必须有 polarity
#   `vip_required` 的字面语义是「和会员有关」，不是「必须是会员」：0909 安卓边遍历 6 次熔断源于
#   一族「未登录/非会员才显示」的入口（源码 `if (!isVip())` 形态）被 trip 分派排进了会员态，
#   页面根本不出现 → 边走不通 → 按熔断收尾。record 级与边级 edge_preconditions 一起统计。
polarity_total=$(jq '
  def acct: (.kind == "login_required" or .kind == "vip_required" or .kind == "login_conditional");
  [(.pages[],.fragments[],.dialogs[])
   | ((.preconditions // [])[] | select(acct)), ((.inbound_triggers // [])[] | (.edge_preconditions // [])[] | select(acct))
  ] | length' "$TREE")
polarity_ok=$(jq '
  def acct: (.kind == "login_required" or .kind == "vip_required" or .kind == "login_conditional");
  [(.pages[],.fragments[],.dialogs[])
   | ((.preconditions // [])[] | select(acct)), ((.inbound_triggers // [])[] | (.edge_preconditions // [])[] | select(acct))
  ] | map(select(.polarity == "required" or .polarity == "absent")) | length' "$TREE")
if [[ "$polarity_total" -gt 0 && "$polarity_ok" -lt "$polarity_total" ]]; then
  MESSAGES+=("📌 Phase 2.7 极性覆盖: $polarity_ok / $polarity_total 条 login/vip 类前置带 polarity（缺 $((polarity_total-polarity_ok)) 条）")
  MESSAGES+=("   补法: 每条写 polarity=\"required\"（有该态才可达）或 \"absent\"（**没有**该态才显示，源码 \`if (!isX)\` 形态）；record 级与边级 edge_preconditions 都要")
  MESSAGES+=("   验: python3 \$SKILLS_ROOT/app-relationship-tree/scripts/llm_phase_guard.py verify <before> <after>（ART_ALLOW_MISSING_POLARITY=1 可临时降为 WARN）")
  INCOMPLETE=$((INCOMPLETE+1))
elif [[ "$polarity_total" -gt 0 ]]; then
  MESSAGES+=("ℹ️  Phase 2.7 极性覆盖: $polarity_ok / $polarity_total（100%）")
fi

# 边级机械注解（2026-09-09，信息行，不判定）：guard_flags 命中数 —— 六种假边/弱哨兵形态的计划前拦截
_EL_JSON="/tmp/_edge_lint_$$.json"
if python3 "$SCRIPT_DIR_SELF/edge_lint.py" "$TREE" --dry-run --json "$_EL_JSON" >/dev/null 2>&1; then
  _EL_LINE=$(python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
c=d.get('counts') or {}
print('%d/%d 条边带 guard_flags: %s' % (d.get('flagged_edges',0), d.get('total_edges',0),
      ', '.join('%s=%d' % kv for kv in sorted(c.items()) if kv[1]) or '无'))
" "$_EL_JSON" 2>/dev/null || echo "unavailable")
  MESSAGES+=("ℹ️  边级机械注解（edge_lint，不判定）: $_EL_LINE；逐条见 edge_lint.py <tree> --dry-run")
fi
rm -f "$_EL_JSON"

# 输出
if [[ "$INCOMPLETE" -eq 0 ]]; then
  echo "✅ preflight OK: 所有 LLM phase 完成 (purpose / inbound_triggers / contract / preconditions)"
  # 2026-09-09：ℹ️ 测量行以前只在有欠账时才打印 —— 树干净时反而看不到 edge_lint / 极性覆盖，补印
  for msg in "${MESSAGES[@]}"; do
    if [[ "$msg" == ℹ️* ]]; then echo "$msg"; fi
  done
  exit 0
fi

echo "❌ fact-tree 未完成 $INCOMPLETE 个 LLM phase："
echo ""
for msg in "${MESSAGES[@]}"; do
  echo "$msg"
done
echo ""
echo "怎么补："
echo "  方法 A: 在对话里说 \"跑 app-relationship-tree 完整流程\" / \"补全 fact-tree LLM phase\""
echo "  方法 B: 跑 orchestrator: bash $SKILLS_ROOT/app-relationship-tree/scripts/run_all_phases.sh"
echo "  方法 C: 单 phase 派: 在对话里说 \"跑 Phase 2.6 LLM 补 contract\"（或其它 phase）"
echo ""
echo "补完后再跑下游（visual-verify 等）。"
exit 1

# ── 2026-09-08：覆盖率记分卡（信息，不改 preflight 退出码；--gate 由 Phase 1 调用方决定）──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/tree_coverage_report.py" "${TREE:-${1:-spec/toolkit-fact-tree.json}}" || true
