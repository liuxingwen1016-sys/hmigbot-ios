#!/usr/bin/env bash
# run_all_phases.sh — app-relationship-tree 完整 5 phase 编排
#
# 串行跑所有 phase；脚本能跑的直接跑，LLM phase 用 preflight 检测后打印明确指令
# 让用户在对话里派 sub-agent。
#
# 用法:
#   run_all_phases.sh --android-root <ANDROID_ROOT>
#     [--tree spec/toolkit-fact-tree.json]
#     [--page-md-dir spec/baseline/ui]
#     [--skip-llm-check]   仅跑确定性 phase，不强制 LLM phase 完成（debug 用）
#     [--tree-feedback <edgewalk/tree_feedback.json>]  遍历侧反馈（Phase 1.7 给未解节点附注记，可选）
#
# 退出码:
#   0  全部完成（含 LLM phase 都已补全）
#   1  确定性 phase 跑通，但 LLM phase 待人工派 sub-agent
#   2  脚本失败 / 输入缺失

set -eo pipefail

TREE="spec/toolkit-fact-tree.json"
ANDROID_ROOT=""
PAGE_MD_DIR="spec/baseline/ui"
TREE_FEEDBACK=""
SKIP_LLM_CHECK=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --android-root) ANDROID_ROOT="$2"; shift 2 ;;
    --tree) TREE="$2"; shift 2 ;;
    --page-md-dir) PAGE_MD_DIR="$2"; shift 2 ;;
    --tree-feedback) TREE_FEEDBACK="$2"; shift 2 ;;   # arkts-visual-verify walk_finalize 产的 tree_feedback.json（可选）
    --skip-llm-check) SKIP_LLM_CHECK=1; shift ;;
    *) echo "unknown: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$ANDROID_ROOT" ]]; then
  echo "❌ --android-root required" >&2
  exit 2
fi
if [[ ! -d "$ANDROID_ROOT" ]]; then
  echo "❌ android-root not found: $ANDROID_ROOT" >&2
  exit 2
fi
if [[ ! -f "$TREE" ]]; then
  echo "❌ tree not found: $TREE  — 先跑 toolkit-fact-indexer" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "═══ app-relationship-tree 完整流程 ═══"
echo "tree: $TREE"
echo "android-root: $ANDROID_ROOT"
echo "page-md-dir: $PAGE_MD_DIR"
echo ""

# Phase 1.5: 节点校准（脚本）
echo "── Phase 1.5: 节点级校准 ──"
python3 "$SCRIPT_DIR/calibrate_nodes.py" "$TREE" \
  --android-root "$ANDROID_ROOT" --page-md-dir "$PAGE_MD_DIR"
echo ""

# Phase 1.6: 源码 popup 类正向扫描（v6.5 新增）
# 补 Phase 1.5 "page_*.md 反查" 的鸡生蛋盲区：a2h-spec 还没写 page_*.md 时
# 直接从源码扫 *Dialog/*Popup/*Window/*Sheet 类（+继承链白名单 + 命名兜底），
# 把 toolkit 漏识、page_*.md 也没写的 popup 一次性补进 fact-tree.dialogs[]。
echo "── Phase 1.6: 源码 popup 类正向扫描 ──"
python3 "$SCRIPT_DIR/scan_popup_classes.py" "$TREE" \
  --android-root "$ANDROID_ROOT"
echo ""

# Phase 1.7（2026-09-11，确定性）：方法现场节点归位
#   toolkit 把 `Outer$showXxx` 这种**方法现场**当成独立的屏入树，与真弹窗类节点重复（0910r3 实测 8/30）；
#   下游安卓归因「已消费不可再现」自洽盖住、鸿蒙回放按影子节点排放行步卡死。读方法体判真身：
#   纯复制 → merge 进真节点删影子；共享参数化弹窗的状态 → 保留并继承布局+调用点文案；解不出 → 标 uncertain。
#   必须排在 1.6 之后：目标类常由 1.6 类扫描补进树。可选 --tree-feedback 读 arkts-visual-verify 收尾产的 tree_feedback.json。
echo "── Phase 1.7: 方法现场节点归位（fold_call_site_nodes）──"
python3 "$SCRIPT_DIR/fold_call_site_nodes.py" "$TREE" \
  --android-root "$ANDROID_ROOT" ${TREE_FEEDBACK:+--tree-feedback "$TREE_FEEDBACK"}
echo ""

# Phase 2.4（2026-09-08，确定性）：宿主归属 + 宿主/弹窗边 + 机械候选 inbound_triggers
#   popup 扫描新增的弹窗此前零入边；无 LLM 阶段时下游对树零边。零 app 常量（tree_generic）。
echo "── Phase 2.4: 机械候选边（宿主边 / 弹窗边 / inbound_triggers）──"
python3 "$SCRIPT_DIR/synthesize_candidate_edges.py" "$TREE" --android-root "$ANDROID_ROOT" ${TOOLKIT_OUT:+--toolkit-out "$TOOLKIT_OUT"}
echo ""

# Phase 2.3: 多源 BFS reach_path（脚本）
echo "── Phase 2.3: 多源 BFS reach_path ──"
python3 "$SCRIPT_DIR/compute_reach_paths.py" "$TREE"
echo ""

# Phase 2.6: navigation_contract 启发式骨架（脚本）
# LLM 补全部分由 preflight 检测后让用户派 sub-agent
echo "── Phase 2.6: navigation_contract 启发式骨架 ──"
python3 "$SCRIPT_DIR/compute_navigation_contract.py" "$TREE" \
  --android-root "$ANDROID_ROOT" --page-md-dir "$PAGE_MD_DIR"
echo ""

# Phase 2.8（2026-09-09 晚，确定性）：边体检 edge_lint —— 机械注解 guard_flags（owner≠from / 一站点两目标 /
#   rid 不在起点布局 / rid 无点击证据 / 二跳压直达）。幂等，可在 LLM 阶段前后各跑一次：
#   LLM 2.5 读到带 flag 的候选边优先核实；vv 计划器读 flag 把这些边排后并标 suspect（执行器不熔断）。
echo "── Phase 2.8: 边体检 edge_lint（guard_flags 机械注解）──"
python3 "$SCRIPT_DIR/edge_lint.py" "$TREE" --write | head -8
echo ""

# 跑完确定性 phase，开始 preflight 看 LLM phase 状态
if [[ "$SKIP_LLM_CHECK" -eq 1 ]]; then
  echo "⏭️  --skip-llm-check 已设，不检查 LLM phase 完成度"
  exit 0
fi

echo "── preflight: LLM phase 完成度检查 ──"
if bash "$SCRIPT_DIR/preflight_check.sh" "$TREE"; then
  echo ""
  echo "✅ app-relationship-tree 完整流程已完成"
  exit 0
else
  echo ""
  echo "⚠️  确定性 phase 已跑完，LLM phase 待人工派 sub-agent（见上方提示）"
  exit 1
fi
