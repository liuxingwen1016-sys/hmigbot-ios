# Phase 2 页粒度 dispatcher 模式（v3.11，兜底保留）

> 2026-09-07 自 SKILL.md Phase 2 原地整段迁出（正文逐字未改；仅步骤 2/2.5 因两种模式共用而留在 SKILL.md）。
> **何时读**：边遍历 unreached 归因「熔断漏采 / 需单页重采」、单页失效重截、行走 unreached 落账后的补漏——判据见
> [`phase2-edge-walk.md`](phase2-edge-walk.md) §8。**加载是机械触发的**：`dispatch_phase2_batches.py --plan-only`
> 会在 stderr 点名本文件必读；`check_android_screenshot.py` 的 reason 路由兜底文案亦指向本文件 §BLOCKED schema。

**以下为页粒度 dispatcher 模式（v3.11，兜底保留）**

**架构**（2026-05-25 重构）：保留 v3 「Android 全量基线 → HMOS round loop」骨架，但**用 LLM-driven sub-agent 实现导航**（v2 老 Step 4.0 的精髓——force-stop → cold launch → dismiss popups → 看 dumpsys/uiautomator dump 真实点击导航）。

已知结构性缺陷（2026-07-15 A/B 实证，兜底使用时须知）：`capture_page_e2e.py` 的 chain_walk/on_page 是单 activity 尺，fragment 页判进失效（tab 切换不改 activity → 重复 tap 撞 hop_limit，AIPPT 实测 trip_2 脚本导航 1/15，`--capture-only` 同尺拒截）——脚本 exit 10/15 后 LLM 接管导航属预期路径，不是异常。

**职责分工**

| 谁 | 做什么 |
|---|---|
| `dispatch_phase2_batches.py` | 切 chunk（5-10 page/chunk，自适应：≤30 records 切 8/chunk，>80 切 10）+ 输出 chunk 计划 JSON |
| 主会话 | 读计划 → 对每 chunk 用 `spawn_agent` 派 sub-agent |
| sub-agent | 按 `references/phase2-android-batch-prompt.md` 跑一个 chunk：每 page 调 `capture_page_e2e.py` 一次打包（reset→dismiss→机械导航 reach_path 重放/chain_walk→截图+dump+签名），LLM 只按退出码路由异常（接管导航/自愈梯/BLOCKED）——2026-07-11 编排税优化，旧逐条编排废止 |
| `references/android-navigation-playbook.md` | 公共导航 playbook，sub-agent 必读 |
| `check_android_screenshot.py` | dispatcher 出口验收 gate + Phase 3.5 入口 gate（双保险） |

**触发条件**（满足任一即跑，B 修复 2026-07-10——"缺图"只是三本账之一，只看它会漏 grounding/blackbox 欠账）：
- `python3 $SKILLS_ROOT/arkts-visual-verify/scripts/phase2_needs.py spec/toolkit-fact-tree.json --trip <trip>` **exit 1**（三本账任一有欠：缺图 / grounding 未填真值 / blackbox 未探索；两个 trip 各跑一次判定）
- `--invalidate-android-cache` 强制全量

**主会话执行步骤**

# 0. 顺序前置（2026-07-10 明确——历史上三处文档顺序互相打架）：**Phase 1 prepare 必须先跑**
#    （其 Step 1.1.6 产 dialog_id_catalog.json——dispatcher 入口有硬闸，缺它 exit 2 并给出构建命令）。
#    canonical 顺序 = Phase 1(prepare) → Phase 2(本节) → Phase 3/3.5 → Phase 4。

# 1. 产 chunk 计划（也写一份到 spec/visual-verify/phase2_batches/_plan.json）
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/dispatch_phase2_batches.py --plan-only

# 2. / 2.5 【trip 态建立 + 数据态 checkpoint】——两种模式共用，正文在 SKILL.md Phase 2
#    「trip 态建立（两模式共用）」段，此处不重抄；跑完 2/2.5 再进 3。

# 3. 对每个 chunk，主会话 `spawn_agent` **串行**派 sub-agent（一次一个，等返回再派下一个），
#    prompt 渲染自 references/phase2-android-batch-prompt.md，注入：
#    trip_id / chunk_id / chunk_pages / android_serial / android_pkg / launcher_activity
#    ⚠️ chunk_pages 富化归主会话：_plan.json 里是纯 id 数组，渲染前须 jq 树把每页的
#       fq_class/inbound_triggers/navigation_contract/preconditions 附上（sub-agent 铁律 R7 禁读全树）
#    ⚠️ 串行铁律：单 Android 模拟器是物理唯一资源，并发派 sub-agent 会让 adb dump / am start /
#       input tap 互相串扰、chunk manifest.json 多写损坏。禁止并发。

# 4. 全部 chunk 完成后 → 验收
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/check_android_screenshot.py
# Exit 0 = PASS → 进 Phase 3/3.5/4
# Exit 2 = 仍有缺图 → 主会话决定补图 / 升级用户
```

**BLOCKED schema**（详 [`android-navigation-playbook.md`](references/android-navigation-playbook.md) §3.3）

每个失败 page 写 `spec/fix/baseline-blocked/BLOCKED_baseline_<page>_<trip>.md`，含 `reason` 枚举字段：

> **机器路由单一事实源 = [`scripts/blocked_reason_routes.json`](scripts/blocked_reason_routes.json)**（check_android_screenshot.py 按它在闸 stderr 打印逐 reason 恢复指引，债单 `_baseline_debt.json` 也携带 route——失忆会话跑一次闸即知派谁）。下表是语义详版；改枚举/路由必须与 routes.json、playbook §3.2 三处同改。派发主语一律主会话，sub-agent 只写单上报。

| reason | 含义 | 后续修法 |
|---|---|---|
| `nav_unreachable` | 6 hop 内未达 target | 检查 fact-tree.inbound_triggers |
| `dump_unavailable` | uiautomator dump 连失败 3 次（已排除广告） | 关动画 / 加 sleep |
| `need_ad_profile` | dump 持续失败 + 屏有促销/倒计时（广告挡 idle）且无/失效 ad_profile | **主会话**派 ad-profile-builder（BLOCKED 单必带 ad_repro 块，见 playbook §3.3）→ 重跑本 chunk。**禁 rm 本单**（ad_repro 是 builder 学习素材） |
| `data_precondition_missing` | 需数据态（如收藏页非空），sub-agent 自愈梯已试尽 | 派 scenario-builder 按 data_hint 学 check/create 建 fixture → 删该页 png 重跑补图 |
| `hop_limit_exceeded` | 到了合理 parent 但 trigger 不响应 | 看 last_dump_path 排查 |
| `structurally_unreachable` | **声明式预判，零设备尝试**（dispatch 前置步按 phase2_scope 判据写：树判死+无活路佐证 / callback 外部回跳 / 无入口非骨架面；2026-07-11 白烧优化——旧账单 chunk_02 曾 839s 烧在 6 个注定 BLOCK 页的导航尝试上） | 无需修——树翻案（补出活 inbound / 摘除判死）后前置步自动删占位、页自动回采集集；若怀疑误判先对质源码（WorksPage 教训：真误判的根多半在树，顺手修树） |

**产物**

- `spec/visual-verify/screenshots/android/{trip_id}/{page_id}.png` baseline（被 Phase 4 直接复用）
- `spec/visual-verify/phase2_batches/<chunk_id>/manifest.json`（每 chunk 进度，sub-agent 写）
- `spec/visual-verify/phase2_batches/_plan.json`（dispatcher 产的全局计划）
- `spec/visual-verify/_trip_assignment.json`（trip 分派单一事实源，`trip_assign.py` 产；D 优化 2026-07-10——不再全部页 ×2 trips：前缀白名单→trip_1 / preconditions login|vip→trip_2 / **默认 trip_2（保守：登录态覆盖面最大）** / `trip_overrides.json` 人工拍板最高优先；错配自愈经 `_trip_retry_queue.json`。dispatcher 切 chunk / phase2_needs 记账 / check_android_screenshot 分母三处共用）
- `spec/fix/baseline-blocked/BLOCKED_baseline_*.md`（失败 page，含真实 reason）
- `spec/visual-verify/blocked_dumps/<page>_<trip>_<ts>.xml`（失败时最后一次 dump，便于排查）

**后果**：Phase 4 sub-agent 截图阶段 Android 端**全部复用 Phase 2 baseline**（png 已存在即不重截），跳过 Android scenario 准备 → HMOS-only 截图职责。
