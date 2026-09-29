# Phase 2 边粒度行走（edge-walk，v4 主模式，2026-07-15；分工轴修订 2026-07-16）

> 取代页粒度 per-page 冷启作为 Phase 2 主模式。设计依据：同项目 A/B 实测（页粒度 124m/31 冷启/边真值 0 vs 边粒度 114m/1 冷启/57 条边真值）。**边粒度的价值主张 = 三账合一 + 边真值反哺，不是省时间**；时间收益来自机械**批处理**与冷启税消除。页粒度 dispatcher 模式降级为补漏兜底（见 §8）。

## 0. 分工轴铁律（2026-07-16 对照实验结论，先读这条再动手）

**LLM 编排 + 机械批处理单元**——机械化的边界是「确定性」，越过这条线就交 LLM：

| 谁 | 干什么 | 为什么 |
|---|---|---|
| **LLM（sub-agent）** | **编排**：读计划决定下一步、导航、撞事恢复、批量判定 | 编排的本质是处理**意料之外**（元素启动外部 app / 选中即消费的页 / BACK 过冲），这是脚本最弱、LLM 最强处 |
| **机械脚本** | **批处理已知的事**：node_sweep 一次扫全节点元素、_replay_to 回放已确认路径、记账/反哺/落位 | 3 倍杠杆来自**批处理**（一次调用扫 20 元素、11s/check），不来自机械编排 |

**同项目对照实验（决定性证据）**：LLM 编排（Arm B）**跑完 20 节点**；脚本编排（walk_exec 全量）**5 节点就断**——真实页面的普查逃逸（Google 外部 app / 选中即消费 / H5 路由）会反复打断 DFS 位置，脚本 exit 后需从零重建现场（每次~2min），而 LLM 在上下文里直接处理、进程不断位置不丢。
**速度不丢**：LLM 导航决策~60s + node_sweep 机械~113s ≈ 173s/节点；机械编排 ~10s+113s=123s **但每几步断一次+2min 恢复**，实际更慢且要人盯。
**推论**：`walk_exec` 降级为「**已确认路段的快速回放器**」——二轮（反哺 rid 后不确定性大减）才划算，首轮别用它当主编排（见 §3 末）。

## 1. 定位：一次行走结三本账

一次冷启沿导航图 DFS，每条边 tap 进 → 顺路结账 → 返回。到达一个新节点时**就地结清三本账**：

| 账 | 动作 | 产物（**只是产物，不是终点**） | 谁消费（`walk_finalize.py` 串，§3 step 4） |
|---|---|---|---|
| capture | `walk_ledger.py settle --tree --trip --pkg --launcher`（**内部调 `capture_page_e2e --capture-only`**：身份断言/广告排水/签名/黑屏检查，与页粒度同一防线，2026-08-13 收权；exit 15=不在对应页拒入账·修位重试一次，exit 11=need_ad_profile·at-need 路由带 ad_repro 块；exit 12=empty_state·自愈梯，13=dump_unavailable / 14=screenshot_failed·重试 1 次仍败写 BLOCKED——完整路由见 §4 settle 退出码路由表） | `shots/<node>.png` + `.android.xml` + reach 证据（via 链）。**shots/ 不是正式 baseline** | `walk_place_baselines.py` → `screenshots/android/{trip}/` |
| grounding | **节点普查 node_sweep**（§5） | `grounding/<node>/run_meta.json` → LLM 批判定 → `grounding_results.json` | `writeback_walk.py` → 树 `functional_checks[]` 三字段 |
| blackbox | 同上（`--out-blackbox`） | `blackbox_discoveries/round-0/<node>/<node>__manifest.json`（schema 与 blackbox_explore 一致；dialog/#via 不探） | `materialize_blackbox_to_factree.py` → 树 `blackbox_behavior`（Phase 4 鸿蒙单侧遍历的清单外元素 oracle）+ 静态 `#via` 变体 |
| 边真值 | 每条走过的边记 confirmed / not_reproduced / deferred_*（BACK 结果回填 back_returns_to_parent） | `edge_results.json` | `writeback_walk.py` → 树 `inbound_triggers[].runtime` |

**★ 这张表的第四列是 2026-07-17 补的，补之前那一栏的位置写着「phase2_needs/materialize 零感知」——
技术上没错（schema 确实兼容），但它读起来像「集成已完成」。真相是：schema 对齐了，调用没对齐。**
实测代价：首次全链路行走 110 分钟、三本账全产出，**三条反哺路一条都没跑**，而 `walk_ledger status`
照报「settled 19/39」。**产出账本 ≠ 反哺账本**——没有第四列的账本就是一堆没人读的文件。

**与页粒度的本质区别**：页粒度每节点付一次冷启+门链重放（30-90s/页），且只走 reach_path 一条边、其余边永不验证；边粒度冷启只留给「顺路盖不到」的场景（副作用隔离/孤儿探测/熔断补漏），且顺带审计树上每条边。

## 2. 前置条件（与页粒度同）

- Phase 1 prepare 已跑（phase2_scope 判死、dialog_id_catalog）；canonical 顺序不变 = Phase 1 → Phase 2 → Phase 3/3.5 → Phase 4。
- trip 态建立同 SKILL.md Phase 2「trip 态建立（两模式共用）」段（原步骤 2/2.5；pm clear 归零 / trip_2 跑 login scenario 走包装脚本）。**包装脚本内置 trip_1 封账闸（2026-08-13，两模式通用）：trip_1 有债时拒绝建登录态 exit 31**——顺序不再依赖编排者自觉；chunk 交接同理受墙钟约束：单 chunk 超预算（~30 步 ×2min）即提前交接（交接机制既有，别硬撑到上下文枯竭）。
- **trip_1 首启链已并入边遍历（2026-07-25 修订，旧文"边粒度的特例，不变"作废）**：
  计划里是 `walk_0_first_launch`（`reset_before: pm_clear`，起点 launcher），首启门发
  `kind="wizard_step"` 边、`PRIO` 最前（门一次性消费，别的边不得插队）。
  **实际动作与旧「链式连采」完全一致**（一次 pm clear 顺链走到底、顺路截图），
  区别只是**步序落成了 walk_plan.json**，从而鸿蒙侧可一笔画回放而不必 LLM 重推。
  单行道回位：BACK 失效属**预期**（记 `BACK_NOOP_one_way`）→ `coldstart` + 重放前缀，
  连败落 `needs_pagegranular_fallback` 交页粒度兜底；**绝不为了回位硬按**。
- 工作目录：`spec/visual-verify/edgewalk/`（下称 $EW；工具默认读 env `VV_EDGEWALK_DIR` 或此路径）。

## 3. 主会话执行步骤

> **2026-09-09 晚起：本节流程由 `scripts/next_walk.py` 机械驱动，散文仍是规格之源。** 主会话的循环只有两句：
> `python3 $SCRIPTS/next_walk.py --dir $EW [--serial S --package P] [--apply]` → 按它输出的 `action` 做**一件事**：
> `plan`/`write_safety_review`（先出计划、写计划级安全复核）· `dispatch_walk`（派行走代理，prompt 已填好；
> 附 `also_dispatch_judge` 时同时派判读代理）· `run_login`（--apply 真跑登录包装，成功自动打点）· `dispatch_judge` ·
> `confirm_overrides`（草稿已聚合 not_reproduced note，主会话归因后另存 reason_overrides.json）· `finalize`（--apply 真跑）·
> `wait_in_flight`（行走在飞，主会话不碰 $EW）· `blocked`（预期外：顺序违规/登录失败/finalize 闸红/retap 债，看它给的文件）· `done`。
> 行走代理返回后 `--handoff <报告.json>`，判读代理返回后 `--merge-judge <json>`（在飞期间会被拒到下一个边界窗口）。
> 它无状态、可重入（每次从计划/账本/状态文件/时间线重算），派子代理永远由主会话做，脚本类动作只在 --apply 时真跑。
> 安全复核口径：**计划级一次**（`$EW/safety_review.md`，各 walk 共用；旧文「本段逐条」作废）。登录包装脚本退出码以脚本头部为准
> （0/10/20/30/31/40/50/60；30|40|50 升级用户前必跑 gate_experiment.py，SKILL Phase 2 c 与驱动路由表同口径）。
> finalize 成功才落 `finalize_<trip>.ok`，驱动只认它（闸红不会被下一次调用洗绿）。
> 派发单位 = 一个 walk（执行器模式下代理上下文只随熔断增长）；代理按处置卡在 12 次熔断或墙钟到预算时交接，
> 驱动看到状态文件 in_progress 就续派下一个代理。下面的散文步骤是它逐条实现的规格；改流程先改散文再改脚本。

```bash
# 0. 【2026-09-09 晚新增·出计划前的三件机械事】
#    a. 树侧边体检（ART 脚本，机械注解 guard_flags：owner≠from / 一站点两目标 / rid 不在起点布局 /
#       rid 无点击证据 / 二跳压直达；计划器读 guard_flags 把这些边排到兄弟之后并标 suspect，
#       执行器对 suspect 边找不到控件只记 not_reproduced 不熔断）：
python3 $SKILLS_ROOT/app-relationship-tree/scripts/edge_lint.py spec/toolkit-fact-tree.json --write
#    b. 分派表必须从**当前树**重生成（计划器校验分派表页集合 ⊆ 树 record，含树外页直接拒出计划）：
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/trip_assign.py spec/toolkit-fact-tree.json --project-root .
#    c. 态清单（零 LLM）：按 kind:polarity 汇总前置条件、列出极性缺失与无 input 配方的输入守卫、每个 trip
#       需要什么账号态/数据态——**派 chunk 前人看一遍**，缺的账号/数据先造，别到设备上走几十分钟才发现：
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/walk_state_inventory.py spec/toolkit-fact-tree.json
#    ★ trip 顺序铁律：计划里 walk 的先后即 trip 的先后（trip_1 登出态在前）。后端登录态常不可逆
#      （0909 实证：mock 后端一次登录后 pm clear 也回不到游客态），所以 **前一 trip 的 walk 必须全部结清
#      再建后一 trip**；登录包装脚本成功后机械打点时间线（walk_timeline.py），执行器开工发现「后一 trip 已
#      有 settle / 时间线已有登录事件」而当前 walk 属前一 trip → 直接拒（exit 3），确需回走先复位环境再带
#      `--allow-trip-backtrack '<证据>'`。
# 1. 产行走计划（确定性，零 LLM；配置从树的 relationship_kind 自动推导，
#    仅 --generation-targets（有不可逆副作用需隔离的目标节点）需人工给）
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/plan_edge_walk.py \
    --tree spec/toolkit-fact-tree.json --out spec/visual-verify/edgewalk \
    [--generation-targets NodeA,NodeB]
# 产物：walk_plan.json（walks[].steps 完整步序 + sentinels 哨兵表 + targets）+ 人读版 walk_plan.txt

# 2. 读 walk_plan.txt 检查：孤儿清单是否合理 / destructive 边是否都标了 stop_at_dialog
#    / 覆盖分层（coverage_executable/speculative/gap）。⛔ 投机占比高**不是回退页粒度的理由**
#    （2026-08-12 混合铁律，实爆：15/39 覆盖被"needs_discovery>50%整体回退"全员降级页粒度31次冷启）
#    ——计划盖到的全走，投机步做有界探索；治本是重跑 ART 带间接下钻补 label（实证 61%→13%），
#    但补树是异步待办，不阻塞本轮行走

# 3. 【首选·首轮】LLM 编排 + 机械批处理（§0 分工轴；实证：LLM 编排跑完 20 节点，脚本编排 5 节点断）
#    主会话把 walk_1_main 按步数切 2-3 个 chunk（每 chunk ~25-35 步——**甜点位实测，别切碎**：
#    chunk 变多=交接开销吃掉并行收益）。walk_2/walk_3 各一个 chunk（常被 walk_1 顺路白捡，
#    派发前 walk_ledger.py status 查欠账，结清即跳过）。
#    **chunk 间就地交接、绝不冷启**；sub-agent 每步循环见 §4、每节点必调 node_sweep 见 §5。
#    ★★ 派发 prompt **必须用模板填槽，禁止临场手写协议部分**（2026-07-20 A/B 实测落地：手写 4 篇
#    逐次变长且相互漂移——铁律「转人工不碰」4 篇全丢、安全步 10 条只点名 4 条；模板 24/24 全覆盖）：
#      python3 $SCRIPTS/fill_chunk_prompt.py --chunk N --steps chunkN_steps.json \
#          --resume <上一交接报告文件|-> --extras <接力推理文件|-> --safety-review <复核文件> --dir $EW
#    模板 = references/phase2-chunk-dispatch-template.md（协议不变部分,要改协议改模板本身,勿在派发时重写）。
#    信息按对上游质量的依赖分三层：
#      规则层  $EW/project_rules.md（安全铁律+已知坑,项目冻结+append-only）——整文件机械注入,
#              填槽闸校验「安全铁律」节存在,缺了拒绝生成（规则一条不落是机械承诺,不是自觉）;
#      树依赖层 安全关键步表/首达节点表（机械提取自计划 safety/settles_capture）**+ 强制安全复核**
#              ——机械表可能有洞(实测:退出登录边被计划标 normal),复核为空填槽闸拒绝生成,
#              哪怕写「已逐条核对,无补充」也必须显式留痕,沉默不放行;
#      接力层  --extras 手写(只写交接报告里**没有**的接力推理;报告已有的别重抄——raw 报告原样进 RESUME 槽)。
#    $EW/run_env.md（$EW/$PKG/$SERIAL/$TRIP/$TREE 等本轮冻结值）由主会话计划阶段写一次。
#    （判读 agent 的 prompt 模板化未实验,暂仍手写——待办。）
#    ★ sub-agent 的价值正在「撞事当场处理」：元素启动外部 app→BACK/重拉起再点回来；页面选中即消费→
#      换条路进；BACK 过冲→重新导航。这些**不要**升级主会话，在 chunk 上下文里解决（进程不断、位置不丢）。
#
#  ★★ 双派并行时序（2026-07-18，agent 审核后定稿。设计铁律：**并行只发生在主会话层**，
#     行走/判读 agent 都是「一个输入、一个动作、一个返回」的直线，prompt 里绝不嵌套后台任务）：
#
#       设备    [chunk1 行走]      [chunk2 行走]      [chunk3 行走]
#                          ▲W1              ▲W2              ▲W3
#       主会话  ──等待──────╬──等待───────────╬──等待───────────╬──归因确认 ∥ 等判定3──→ finalize
#                          ║双派             ║双派             ║派判定3
#       判读agent           [判定chunk1]      [判定chunk2]      [判定chunk3]
#                              └→JSON 暂存 scratchpad,窗口期才进主文件
#
#     节拍（主会话逐字执行）：收到 chunk N 交接报告 →
#       ① 边界窗口 W：此刻无行走 agent 在飞、$EW 无人在写 → 把上一轮判读 agent 暂存在
#          scratchpad 的 JSON **原子合并**进 grounding_results.json（判重键 idx 感知）。
#       ② 拷 chunk N 的 run_meta 快照到 scratchpad（防跨 chunk 重扫覆写原文件）。
#       ③ **同时**派：chunk N+1 行走 agent（占设备，吃交接报告）+ chunk N 判读 agent
#          （零设备，读快照+异常注记，返回 JSON **不写文件**，契约见 §5）。
#       ④ 回到等待。**行走 agent 在飞期间，主会话绝不碰 $EW 下任何文件。**
#     写冲突由时间片结构性消灭：行走飞行期 = 行走 agent 独占 $EW（含 §5 当场处置直写），
#     边界窗口 = 主会话独占。两个互斥域交替，零锁、零分片文件（勿引入——审核已否，违 §5.4 禁侧文件）。
#     兜底：判读 agent 挂掉/主会话忘合并 → finalize 2.5 闸机械报红（观测未判逐条列），
#     按交接报告 swept_nodes 重派 / 去 scratchpad 找回——数据最多晚到，不会丢。
#     收尾错位：最后一个 chunk 返回后，派判定 3 的**同时**主会话自己做归因确认——
#     读 edge_results 的 not_reproduced note + ledger unreached（**都在末 chunk 返回时已冻结，
#     不依赖判定产物；BLOCKED 单是 finalize 的产物，此刻还不存在，别去读**），预产
#     reason-overrides → finalize 在「判定全合并 + overrides 就绪」后只跑一遍。
#
#  ★ 交接报告模板（结构化，2026-07-18 定稿。散文报告靠自觉，跨 chunk 依赖必须变字段）：
#     {position:        实际位置{activity, node, tab, 有无弹层}——不是计划位置,exit_off_anchor 时两者不同,
#      resume_step:     下一 chunk 从计划第几步续走(步序偏差时以此为准,别让下家推导),
#      step_deviations: [计划步N: 实际发生了什么(提前首达/降级复访/跳过)],
#      skipped_subtrees:[因边失败被跳过的整棵子树步号——机械切分会把子树切进下一 chunk],
#      settled_extra:   [顺路白捡结账的节点],
#      discovered:      [本 chunk 的 discovered edges / unplanned_destructive 处置结果],
#      swept_nodes:     [{node, coverage_complete, truncated, position_lost, exit_off_anchor}]
#                       ——判读 agent 的作用域清单 + 下家「别反复重扫」的依据(§7.1),
#      observation_notes:[现场才知道的观测异常——如「分类tab sig判noop是假阴性,截图实际变了」,
#                        判读 agent 只读 run_meta 会照单全收假 noop,现场知识必须随报告转移],
#      device_residue:  {ime_open, input_text_left, armed_state}——输入残留/键盘/再按一次退出态
#                       会毒化下家首步判位,
#      incidents:       [熔断/冷启/逃逸事件],
#      （2026-09-09 下午：范围事实源 = 安卓 ledger settled + 边真值；walkability 只给计划器省探测与报告解释，不过滤鸿蒙范围；walk_5 深链走已删）
#      （2026-09-09 起孤儿探测 walk_3 不在初始计划里：walk_1 走完、finalize 回填树后由 plan_orphan_probe.py 重算，剩余孤儿才排；
#        普查落点由 lib_landing 解析成树节点，materialize 直接挂回该节点当首达结账，孤儿在普查那一刻闭环）
#      （2026-09-09 起时间账由执行器机械记：walk_exec_state.json 的 step_times/llm_gaps，收尾 walk_timing.py 出三分账；交接报告不用手写耗时）
#      stopped_early:   {budget_min, elapsed_min, last_step}——仅墙钟止损提前交接时填（§4），正常收尾省略}
#
# 3b.【可选·二轮/已确认路段】机械执行器快速回放（不确定性小时才划算）：
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/walk_exec.py \
    --dir spec/visual-verify/edgewalk --serial $ANDROID_SERIAL --package <pkg> \
    --tree spec/toolkit-fact-tree.json --device-state <trip_id> [--max-steps N]
#    exit 0=完成 / exit 30=熔断（stdout JSON 带 reason/evidence/resume_hint）→ 三选一续走：
#      --resume / --mark-step-done N --assume-at <node> / --skip-step N --skip-reason "..."
#    ⚠ 两层词表别混（2026-08-14）：exit 30 的步级 reason（needs_discovery/control_not_found/
#      arrival_unverified/weak_sentinel_confirm/back_failed…）是执行器熔断词表，按 §4 处置；
#      blocked_reason_routes.json 是 BLOCKED **单据**词表（页粒度/收口路由用）。互不映射。
#    **首轮别拿它当主编排**（实测每几步断一次、每次 ~2min 重建现场，反而比 LLM 编排慢）。
#    适用：树已反哺（边带 runtime.control.rid）、needs_discovery 少、目标是重放已知路径。

# 4. 【收尾·一条命令，全部 walk 完成后必跑】三账反哺 + 自检闸（铁律见 §6）
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/walk_finalize.py --trip <trip_id> \
    [--tree spec/toolkit-fact-tree.json] [--dir spec/visual-verify/edgewalk] \
    [--walk-id walk_<date>] [--reason-overrides ov.json] [--dry-run]
#  ★★ 为什么是一条命令而不是四条（2026-07-17 事故根因，别拆回去）：
#     边遍历用 LLM 编排换掉了老的页粒度 dispatcher（dispatch_phase2_batches.py），dispatcher 里反哺是**机械 post-step**
#     （无条件跑 materialize），不依赖任何人记得。拆成四条独立命令 = 四个记忆点 = 收尾变成「自觉」。
#     实测：首次全链路行走跑完 110 分钟、三本账全产出，**三条反哺路一条都没跑**（树里
#     blackbox_behavior/#via 全 0、screenshots/android 里 0 个本轮文件），而 walk_ledger status
#     照样报「settled 19/39」一片祥和。**凡是没有机械物件承接的 LLM 步，都会在 chunk 边界上掉。**
#  内部顺序（不可换）：
#    ① walk_inherit（§3.9 同落点证据继承，**必须先于反哺**——顺序错了继承真值进不了树）
#       node_sweep 把 anchor rid==出边 view_id 的 check 标 deferred_same_destination（不点、省一趟
#       进子页+BACK）；边 confirmed→check 继承落地证据(trusted=true,
#       evidence_source=inherited_from_edge 可审计)；边 not_reproduced/未走到→写 needs_retap.json
#       ★needs_retap 非空 → **闸红**：这些 check 必须回行走补单独 tap（绝不因 defer 丢覆盖），
#        主会话读它派补点，补完重跑 finalize。
#    ② writeback_walk（grounding 三字段 + 边 runtime；exit 20 = 有边消歧失败被**拒写**→闸红，
#       真值没进树，须人工消歧后重跑。拒写是故意的：静默错写 >> 漏写）
#    ③ materialize_blackbox_to_factree（老 dispatcher 的 Post-step 2，边遍历模式下由本命令接线——
#       §5 让 sub-agent 传 --out-blackbox **生产**黑盒账，却从没让任何人**消费**。
#       它的主要价值是 behavior_ledger→pages[].blackbox_behavior（Phase 4 鸿蒙单侧遍历的
#       清单外元素 oracle），#via 变体是次要的：动态内容不物化，实测 13 个 discovery 全判动态→0 变体）
#    ④ walk_place_baselines（shots→screenshots/android/{trip}/{原id含$}.png +resize +.android.xml；
#       unreached 自动产 BLOCKED_baseline_*.md：孤儿=structurally_unreachable，其余默认
#       nav_unreachable **会让验收闸红，这是故意的**——主会话按行走报告归因后用 --reason-overrides
#       改写 data_precondition_missing 等，禁静默改绿；trip 归属对齐 _trip_assignment.json）
#       ★「已有禁覆盖」会静默跳过 → finalize 把 skipped_exist 报**红**，逼人决定旧图去留
#    ⑤ 自检闸：§6 的 inbound 边数 t0==t1（删0增0）+ 三账落地对账
#  exit 0=全绿 / 20=闸红。**禁静默改绿**——红 = 有真值没落地，不是脚本坏了。反哺前自动备份树。
# 5. 补漏：walk_ledger.py report 的 unreached 逐个归因——
#    ★归因方法 = 聚合，不是调查（2026-07-18 责任分离）：walk_place_baselines 的 nr_notes 已自动
#      汇总该节点全部 not_reproduced 边的 note（各 sub-agent 按 §4 边失败协议写的一处源码死因）。
#      死因同源（如全是 isVip）→ 直接写 data_precondition_missing + 各边源码锚点，纯读账零设备；
#      死因异源 / 有计划内边压根没走到 → 才值得人看一眼。**禁在归因阶段发起源码穷举**——
#      需要的证据行走时已逐边记下，树外活边有 blackbox 兜底反哺。
#    前置态缺失(VIP/数据) → 记账挂起、由主会话派 scenario-builder(sub-agent 只上报不自派)；真孤儿 → BLOCKED(structurally_unreachable)；
#    熔断漏采 → 页粒度 dispatcher 单页补采（§8）
# 6. 验收同页粒度：check_android_screenshot.py（baseline 落位 screenshots/android/{trip}/ 后）
#    ledger 的 shots/ 需按 trip 落位到 screenshots/android/{trip_id}/{page_id}.png（cp+resize）
```

## 4. sub-agent 行走循环（每条边）

工具（输出极小，**绝不 cat 完整 uiautomator dump**——爆上下文铁律同 §0.3）：

```text
python3 $SCRIPTS/walk_whereami.py --expect <node> [--wait 8] [--dir $EW]  # 双闸判位：{"match","hits","why","weak"}
#   --wait N = 轮询到落点匹配或超时(回报 waited_s=真实落地耗时)。tap 后判位**一律用它，别用固定 sleep**
python3 $SCRIPTS/walk_clickables.py [--grep 文本] [--rid xxx] [--all]  # 可点元素+tap 坐标
python3 $SCRIPTS/walk_ledger.py [--dir $EW] settle --node <id> --via "<父>--[标签]-->" --mode walk
python3 $SCRIPTS/walk_ledger.py [--dir $EW] coldstart --reason "..."   # 任何 force-stop 重启必记
```

**settle 退出码路由表（2026-08-13 补齐；2026-08-14 批一分类器化——settle 内核=capture_page_e2e，非零一律有出口，禁静默重试）**：
- exit 15=未绑定，reason 三分：
  · `not_on_page` → 修位重试**一次**（whereami 重判+导航校正）；仍 15 → 如实记 nav_failed 按边失败协议走
  · `dialog_over_page`（已知弹窗盖页，滤网检出）→ 先排水（dismiss_popups/ad_dismiss）再重 settle 一次
  · `landed_elsewhere`（分类命中树上另一节点 Y，**不自动绑**——越 trip/非 canonical 乱绑=基线污染；证据已入池）
    → 编排层修位后重 settle；该边真值记 `status=landed_elsewhere` + landed=Y（writeback 独立立账，别写 not_reproduced）
- exit 16=classification_pending（unknown/uncertain/无 dump——证据已入池 `pending_shots/` + 债已落 `pending_bindings.json`）
  → **不停走**（位置由哨兵另行把关）；债在边界窗口用 `walk_ledger bind-from-evidence` 结（离线重分类零设备，
  或 --verdict 人工判读留痕）；unknown=树缺陷信号 → 源码补树环（批二）。finalize 2.6 闸兜底：有债未判 exit 20 红。
  执行器已内置连续 3 笔 16 熔断（带病盲走征兆：广告墙/dump 退化 → LLM 看现场）
- exit 11=need_ad_profile → 计入步 0 广告止损（同一节点累计 2 次禁第 3 次 → BLOCKED(need_ad_profile)+ad_repro）
- exit 12=empty_state → 数据态自愈梯（页粒度 1.3 exit 12 同款语义）：check 配方复验 → create 重放（走包装脚本，**限 1 次**）→ 重 settle；仍 12 / 无配方 → 写 BLOCKED(data_precondition_missing)（附已尝试记录，主会话派 scenario-builder）→ 按 `subtree_end_step` 砍分支继续兄弟边
- exit 13=dump_unavailable / 14=screenshot_failed → 重试 **1 次**；仍败 → 写 BLOCKED(dump_unavailable)（reason 枚举无 screenshot_failed，14 归 dump_unavailable、单内注明真因是 screenshot_failed）→ 砍分支继续兄弟边。13 且屏有促销/倒计时内容 → 改按 11 路由（need_ad_profile+ad_repro，计入步 0 止损）
- **同款「累计 2 次禁第 3 次」止损语义**：同一节点 12/13/14 各自累计 2 次即写单砍分支，禁第 3 次尝试——失败路径必须落 BLOCKED/记账，绝不静默丢覆盖

每步：
0. **广告止损铁律（2026-08-13 补齐——此前只在页粒度 batch prompt，边遍历缺失致 codex 原地重试实爆）**：
   同一节点的广告/付费墙相关处置（settle exit 11 / ad_dismiss 抛 NeedProfileBuild / dump 因促销·倒计时失败）
   累计 **2 次** → 立即按 playbook §3.2 写 BLOCKED(need_ad_profile) 单（**必带 ad_repro 块**——hop 轨迹
   就在你上下文里）→ 按该步 `subtree_end_step` 砍分支 → 继续兄弟边。**禁第 3 次尝试**——你不是学配方的人，
   builder 刷完 profile 后按 needs 账回头补采。
1. `walk_whereami --expect <父页>` 确认位置（**weak=true 必须看截图确认，禁当机械真值**）
2. 找触发控件：有标签 → `walk_clickables --grep`；步序带 `runtime_rid`（上轮行走反哺，2026-08-12 起 plan 直接透传）→ 按 rid 定位零探索；⚠needs_discovery → **有界探索三段**（2026-08-12 混合护栏）：
   a. 步序标 `auto_transition`（倒计时/EventBus/首启自动弹——树里 confirmed 但无 rid 的边全是这类）→ **先 wait 不 tap**：`walk_whereami --expect <子节点> --wait 8` 等它自己发生；
   b. wait 不中 → 列全部 clickables 按目标页语义挑，**限一次 tap 尝试**；挑中的控件文本命中 DESTRUCTIVE_RE（blackbox_explore.py 词表，node_sweep 已 import）→ 放弃该边记 unreached(destructive_risk)，绝不用覆盖换安全；
   c. tap 不中 → 记该边 unreached，按本步 `subtree_end_step` **整段跳过该分支子树**（plan 已机械标注区间，无需自己括号匹配），继续兄弟边。禁第二次尝试——你不是修树的人，探索失败的信息价值第一次就拿全了。
   **中文标签常不在 text 属性里（自定义组合控件），优先用树边/上轮反哺的 rid**
3. tap → `walk_whereami --expect <子节点> --wait 8`（**轮询到落点，禁用固定 sleep**）
   ★ 有的边落地是**异步**的：实测 `CreateOutLinePage--[选择PPT模版]-->ChoicePPTTemplatePage` 的 onClick 里
     `lifecycleScope.launch{ checkTextIsCheat }` 先跑反作弊校验，**落地要 3-5s**。固定 sleep 1.5-2 后判位
     会得到 match=false → **把一条好边误记成 nav_failed**（假阴性，且会连累依赖它的整条 DFS 子树）。
     `--wait` 命中即返回不白等；超时才报，且注明是真 nav_failed 而非门禁误判。回报的 `waited_s` 就是
     该边的真实落地耗时，可反哺 `runtime`（下轮回放据此设等待）。
4. 到了：🆕 步 settle + §5 节点普查（`node_sweep --from-plan`，与机械模式同一工具同一安全前提）；↻ 步只验落点。没到：如实记 nav_failed + 原因，回父页续走，**禁硬凑**
   **★ 边失败归因协议（2026-07-18 责任分离，三连砍定稿）**：只读【被点控件】的 onClick 链**一处**，
   把死因（源码锚点，如 `if(isVip())return`）写进本条边的 note → 走下一条边。
   ☠️ **禁止节点级调查**（「这个节点还有没有别的活路」「穷举全部调用点」）——三条理由：
   ①同节点的其他入边各有其主（计划已把树上每条边分给各 chunk），你只对自己这条 path 负责；
   ②每个 sub-agent 都做全称调查 = 同一穷举被执行 N 次（MemberCenter 10 条入边分散多 chunk，实测那次
     只做一遍纯属时序运气）；
   ③「节点在本 trip 不可达」是**收尾的机械聚合**（见 §3 step 5），不是行走者的现场命题；
     树漏的活边由 blackbox sweep 兜（入口渲染着→unclaimed tap 必碰到→discovered/§5；
     入口不渲染→本 trip 本来就不可达，归因照真）——**行走流程不承担任何全称证明**。
5. **◀ 步一律走 `walk_back_to.py`**（2026-07-19，真机 5 场景验证；单次多次同一命令，LLM 逐次按 BACK 废止）：
   ```text
   python3 $SCRIPTS/walk_back_to.py --steps N --package <pkg> [--expect-host <宿主activity短名>]
   ```
   **先做 return path 分段**（回退前看自己的下沉账，反转分类）：
   - `push` 的反向 = BACK → **计入 --steps（只数 Activity）**
   - `dialog` 的反向 = 关弹窗 → **调原语之前自己点取消**（已知的事预排，别让探针白按两下去"发现"）
   - `tab_switch` 的反向 = **调原语之后自己 re-tap 原 tab**（tab 永远不用 BACK 回）
   原语只吃纯 Activity-pop 段；fragment/dialog 目标传宿主 activity 当 --expect-host，页内落位
   原语送到门口后你用 whereami 终验。
   **返回语义**：`count_done` = 到家（仍要 whereami 终验页内态）；`root_guard` = 已在根上（0 按，
   过冲被物理拦截）；`anomaly_count_vs_identity` = **计数与落点打架，中途有诈，现场接管**；
   `no_progress/pkg_escape/probe_dead` = 打不动/逃逸/探针死 → 你接管现场（§4 边失败协议照走）。
   tab_switch/sub_tab_switch 步不 BACK（宿主内切换）；embed 步不执行（包含关系无控件可点）
6. **每条边记 edge_results.json**（追加）：
```jsonc
{"from":"MineFragment","to":"AboutUsActivity","status":"confirmed",   // 或 not_reproduced
 "device_state":"trip_2_logged_in_vip",
 "control":{"rid":"mine_setting_about_us","text":"关于我们","center":[x,y]},
 "landed":"AboutUsActivity","back_returns_to_parent":true,
 "evidence":"shots/AboutUsActivity.png","note":"not_reproduced 必须写清为什么（VIP态不渲染/空态无入口/异步边非tap/控件无响应）"}
```

**熔断协议**：BACK×3 回不到父页 = 熔断 → `walk_ledger coldstart --reason "熔断补漏: <哪步>"` → force-stop 重启 → **冷启弹窗排水**（ad_dismiss 之后必须再跑 dismiss_popups——dialog_id_catalog 驱动，capture_page_e2e 的 drain_boot_popups 同源逻辑：单遍 ad_dismiss 关掉第一个就返回，赶不上序列/延迟接力弹窗，2026-08-13 补齐）→ 导航回断点父页续走。chunk 收尾必须报告设备停在哪个节点（下一 chunk 就地接力）。
- **chunk 墙钟止损（2026-08-13 给公式——§2「~30 步 ×2min」落成可执行判据）**：预算 = `max(30min, 本 chunk 步数×2min)`。超时 → 把**当前步**走完结案（settle/记账落盘，不半途丢账）→ 立即提前交接：交接报告加 `stopped_early: {budget_min, elapsed_min, last_step}` 字段说明止损原因，`resume_step` 照常给下家。别硬撑到上下文枯竭。
- **异步等待超预算的判死必须由 `meltdown_probe.py` 出具判据**（§7.2，硬上限 ≤60s），探针 JSON 原样进交接报告 `incidents`；禁 LLM 临场无上限观察。
- 冷启后**先续走不依赖卡死结果的计划步，把复现重试排到顺路**（run-2 实测正确处置：熔断窗口被计划内步 14-36 填满，死账仅 ≈8 分）。

### 4.x 2026-09-09 首趟真走后的补充（执行器 3b 模式）
- **dialog 节点的结账不走 `walk_ledger settle`**（capture 内核对 dialog 设计性拒跑 exit 2）：执行器到达弹窗后 `settle_dialog_direct`
  截图+dump 直接入 ledger（capture=dialog_direct，身份=到达哨兵）；LLM 手工完成弹窗步用 `--mark-step-done N --assume-at <dialog>`，
  执行器会补边真值并直接结账。别再试 settle 三次。
- `--mark-step-done` 会按计划 static_rid 补一条 confirmed 边（matched_by=llm_manual）；`--skip-step` 对 back/verify/skip 步只跳自己。
- 计划外首启门/声明浮层执行器自动放行（只认协议/隐私/声明/权限说明正文 + 同意类按钮，正文含退出登录/注销/删除/退款等一律不碰）；
  BACK 弹确认窗执行器自动点白名单「取消/关闭」；向导步弱哨兵按顺序语义接受；auto 边瞬态落点沿 auto 链探下一落点记 transient_missed。
- `walk_whereami/walk_clickables/walk_back_to` 不带 ANDROID_SERIAL 时取唯一在线设备，多台在线报错退出。
- 普查后执行器自行重新判位（tab 切走会按 static_rid 重点回）；首启链页的普查欠账由 finalize 5.8 生成 `walk_6_chain_sweep_*`（一页一冷启，`sweep` 步带 --allow-chain-sweep）。
- 时间账：`walk_timing.py $EW` 跨 walk 聚合（每 walk 一份 walk_exec_state.<walk_id>.json 归档）。

### 4.y 2026-09-09 晚：第二批（36 次熔断归因后的计划字段与执行器动作契约，全部只吃树/计划字段）
计划步新形态（plan_edge_walk 产、walk_exec 消费）：
- `type` 步：边的 `edge_preconditions[]` 里 `state_required` 带 `input:{view_id,text_hint}`（LLM 2.7 契约）→ tap 前先发
  `{"action":"type","view_id":..,"text":..}`；执行器按 rid 找输入框、`input text`（非 ASCII 用中性默认串、空格转 %s）、
  收 IME、回读校验，失败熔断 `input_target_not_found / input_failed`。无 `input` 但起点布局 `edit_ids` 里某 id 逐字出现在
  证据文本里 → 机械回退出步（`input_source: evidence_id_match`）。
- 门步：带 `first_launch*` 前置的 auto 边在 walk_0 里**按发生位置**发 `tap(gate=true, auto)` + `gate_pass` 两步（门目标
  即使不在本趟 trip 作用域也结账，它只在这趟存在）；其他 walk 遇到门边发 `skip(first_launch_gate_consumed)`。
  执行器 `gate_pass`：按放行词表点唯一放行控件后验回起点，认不出 → 熔断 `gate_pass_unknown`（不乱点）。
- 尾部回栈剪枝：walk 末尾回到 launcher / 已消费向导链的 back 步整段删除（`pruned_tail_steps` 留审计），step 重编号、
  `subtree_end_step` 重算。
- 生成目标：每个 inbound 调用方各排一条 `walk_2_generation_<tgt>_via_<from>`，walk 顶层 `stop_if_settled: <tgt>`，
  执行器开工发现目标已结账即整趟跳过（首跑不依赖 runtime_status）。
- `suspect: [flags]`：树侧 `guard_flags` 直接复制进步；执行器找不到控件/到达未判定时，目标已结账或本步不结账 → 记
  not_reproduced 跳子树不熔断；本步是目标唯一结账步 → 仍熔断（覆盖优先）。
哨兵表：`derive_sentinel` 把树的 `navigation_contract.verify_signal`（text_contains / view_id / ordinal_in_wizard）
  复制进哨兵；共享 rid 页有 verify_signal 即判强（宿主 + LLM 信号），执行器 tap 到达判定与起点判定同一套接受规则
  （--assume-at 一次性 / 向导序号语义）。0909 实测这一条治 8 次弱哨兵熔断。
共用弹窗变体：同一 dialog 节点被不同调用方到达，执行器各落一张 `<node>#via=<调用方>__<控件>` 变体基线（首个调用方用本尊；
  同调用方复访不重拍；变体不普查），落位随本尊进 screenshots/android/<trip>/，鸿蒙侧逐变体对账。判据只看 (node, from, rid|文案)。
执行器其他：`stop_at_dialog` 步显式分支（到达判定禁用门放行，失败只熔断不点任何按钮）；dialog/auto 目标到达后再拍
  `pending_shots/step<N>_<to>_post.png`（哨兵已命中的帧；`_pre` 是 tap 后即拍的早帧，弹窗入场动画常拍不到——判读
  优先看 `_post` 与 shots/ 结账帧）；门放行/取消/破坏性三张词表收成 `UI_WORDS`，项目可放 `$EW/ui_words.json`
  按键覆盖（词表是跨项目 UI 词汇，逻辑不认任何项目常量）。
- 极性与 trip 态：计划器按 `TRIP_STATES`（登出趟无 login/vip 态，登录趟两态都有）逐边判前置极性，矛盾的边发
  `skip(precondition_polarity_mismatch)`（disproven 的前置不算）；auto 边目标已结账发 `skip(auto_revisit)`（转场不可按需重触发）。
  trip_assign 同口径：跳过 disproven，absent→登出趟、required→登录趟、两者都有→两趟。
派发前：§3 步 0（edge_lint → trip_assign 重生成 → 态清单）；trip 顺序闸见 §3 步 0 ★。

### 4.z 2026-09-10 第三轮（0910 真机回归 41 次熔断归因后拍板的目标逻辑；全部只吃树/计划/状态字段）
目标逻辑（用户拍板）：机械准备 → 驱动编排 → 执行器行走时**首次到达即普查**（含首启链页，排除推进/同意类控件；
普查推进了链就顺着走并记债）→ 普查发现当场入账 → 边失败当场同宿补点 → BACK 落点回写树、下趟改 `renav` →
只在位置丢失时熔断 → 机械收尾；收尾链趟合并成一趟；孤儿噪音不排走。
- **链页当场普查**：执行器 `_maybe_sweep` 对 `chain_protected` 趟改调 `node_sweep --chain-mode --exclude-rids <出口/出边 rid> --exclude-texts <UI_WORDS.wizard_advance_texts>`；
  普查 tap 推进了链（manifest `chain_advanced:true`）→ 执行器按落点在计划里找落脚步续走，中间步记 `state.skipped`，
  未结账的采集记 `state.capture_debt[页 id]`、未点完的元素记 `state.sweep_debt{node:[…]}`（不熔断；落点解析不出才熔断 `chain_advanced_unresolved`）。
- **普查发现当场入账**（`_ingest_discoveries`）：manifest `discoveries[]` 里 `landing_node` 是树内未结账节点 → dialog 直接用普查截图/dump 结账；
  页类按 `trigger_center` 重点进入 → settle → 回起点（≤3 个/次）；补 `discovered:true` 边给 writeback。
- **边失败当场补点**（`_repair_same_dest_check`）：not_reproduced 后若起点 run_meta 有同锚点的 `deferred_same_destination` check → `node_sweep --only-rids <rid>` 补点一次。
- **BACK 落点闭环**：执行器 `do_back` 每次产 BACK 观测记录 `{"action":"back","from":按 BACK 的页,"to":期望页,"landed":实际落点|null,"back_dialog":确认窗|null,"status":confirmed|not_reproduced}`
  （**不是 tap 边真值**——按 (from,to) 索引边的消费方一律按 `action` 跳过）；`writeback_walk` 汇总成 `record.runtime.back_landing`
  `{node,n,matched_n,matches_parent,confirm_dialog,expects,walk_id}`；计划器 `ret()` 见 `confirm_dialog`→`back_needs_confirm`、`matches_parent=false`→`back_landing_mismatch`，
  回位步改发 **`renav`** `{"action":"renav","from":X,"to":P,"reason":…,"observed_landing":…,"confirm_dialog":…}`（位置语义同 back）。
  执行器 `do_renav`：已在 P 免动作 → 否则沿计划到达路径（`plan_path_to`：栈模拟 root→…→P 及各层入栈步）从深到浅探当前层，
  从该层往下重放推进 tap（含同层 `type` 前置）→ 哪层都不在则**重新拉起**（force-stop+launcher，不 pm clear，冷启计数如实入账）再重放 →
  仍回不到 P 才熔断 `position_mismatch`。全程不结账不普查不记边真值；`state.renavs[]` 记账。
- **裸重跑保护**：本 walk 已有状态却不带 `--resume`/`--restart` → exit 5（`state_exists_without_resume`）；`--restart` 归档旧状态归零重走。
- **熔断预算按代理算**：`escalations_scope=agent`（以驱动在飞锁 ts 起算），`handoff_due` 据此；`--budget-min` 墙钟止损不变。
- **收尾链趟合并成一趟** `walk_6_chain_sweep`（`plan_chain_sweep.py`）：三源欠账（`sweep_skipped_chain`−已有 run_meta ∪ `sweep_debt` ∪ `capture_debt`）沿 walk_0 步序一次扫完，
  前缀完整抄 `coldstart/tap/gate_pass/type/back/back_inpage/renav/verify`（0910 漏抄 `gate_pass` 每趟必熔断），`capture_debt` 页恢复 `settles_capture`。
- **孤儿噪音过滤**（`plan_orphan_probe.py`）：id 带 `#via=` **且**机械候选为空 → 不排走，记 `plan.orphan_probe.skipped_noise[]`。
- **驱动**：`run_env.md` 可写 `trip_build_scenario: <场景名>`（无登录应用建后一 trip 数据态，如订阅/造数）——有它就跑它，不看树有无登录类前置；
  树无登录/会员类前置且未指定 → 后一 trip 免建态直接派；只认真跑过场景的 `trip_built:*` 时间线事件为「已建态」。

### 4.aa 2026-09-10 晚第四轮（第三轮验证跑后归因的 10 条工具缺陷；契约回显）
- **到达即结账**（治「结账步被跳过 ⇒ 该节点整轮零基线」）：执行器结账判据从「本步计划标了 `settles_capture`」改成
  「标了 **或** 目标尚未入账」；补结账用手上已有的帧/dump（dialog 走 dialog_direct），记 `state.late_settled[]`，
  **不带普查**（避免在确认窗上碰确定键），`#via=` 变体除外；四参不齐时非 dialog 目标不补。
  变体基线机制（`<node>#via=<调用方>__<控件>`）由此自然生效：本尊结上了，后续不同调用方各落一张。
- **多重边控件消歧**（治破坏性边假 confirmed）：`_runtime_rid(from,to,step)` 在同 (from,to) 多候选时，按本步
  `static_rid/item_rid/trigger/span_text` 对齐候选的 `trigger_view_id/trigger_label/span_text`，**唯一命中才用，否则返回 None**
  （退回计划 static_rid，绝不返回兄弟边 rid）；实际命中与计划不符时边真值记 `control.rid_mismatch_with_plan` + note。
- **熔断菜单三修**：① 一次性门已消费（`step.gate` + 控件不在 dump/可点集 + 强落点只在本步之后出现）→ `skip` 旋到首位；
  ② `chain_advanced_unresolved` 首项换成 `--mark-step-done N --assume-at <强落点>`（判不出则 `skip`），**首项永不含 `--resume`**，
  且 `_maybe_sweep` 对本 walk 已普查过的节点直接返回（否则续走会再推一次链）；③ `action=="verify"` 首项换成
  「先把设备弄回宿主再 `--resume`」（子 activity 单次 BACK / 否则按 `plan_path_to` 重新导航；根 activity 禁 BACK 写进 effect）。
- **门放行落点漂移**：`do_gate_pass` 校验失败时，强落点若是计划后续步的 `from` 则接受并同步 position，记
  `state.gate_landing_drift[]`（供回写树），不熔断；判不出才走原熔断。
- **`node_sweep --only-rids` 强制提档**（治「边没走通→回退单独 tap」被计划自己堵死的死循环）：点名命中的元素提到可点档，
  压过 `walk/same_dest/h5_oracle/nav_back/in_plan`；**`destructive` / `input_field` 即使被点名也不提档**（安全面不放宽）；
  判据看「是否在排除集」而非档名（被 walk/destructive 认领的元素会带着排除标记却不叫 excluded）。
  manifest/stdout 双通道回显 `only_rids_promoted` / `only_rids_kept_safe`。
- **回位不过冲**（`walk_back_to.py`）：每按一次立刻判位，命中即返回；当前已是**根 activity**（树 `relationship_kind==activity_root`
  或计划 coldstart 的 `to`）时**绝不再按 BACK**，返回 `at_root` 交调用方处置；已在目标宿主则返回 `already_at_host` 零按键。
- **判读债链路接通**（治「证据已采、绑定待判」被误算成不可达）：采集内核 exit 16 = 证据入池挂债（`pending_bindings.json`）。
  三处断点全部接上：① `walk_finalize.py` 新增 §2.6 判读债闸（真拦 exit 20，`--accept-binding-debt` 显式豁免并写
  `_phase_markers.<walk_id>.binding_debt`）；② `next_walk.py` 把未判绑定债并进判读作用域、`--merge-judge` 回写 `verdict`
  （不进 check 空间）、新增动作 `settle_binding_debt`（调 `walk_ledger bind-from-evidence`，结债后撤 `finalize_<trip>.ok`）；
  ③ `unreached(split=)` 三分「真未达 / 绑定待判 / 绑定已判」，归因草稿预填 `binding_pending`，BLOCKED 单附零设备结债命令。
- **跨 trip 采集隔离**（治「同节点在后一 trip 复访把前一 trip 的绑定图整份覆写」）：settle 前若 ledger 有**不同 trip** 的结账记录，
  先把现有 `shots/<node>.{png,android.xml}` 归档到 `shots/_bytrip/<旧trip>/`，ledger 记 `settled_by_trip`；
  `walk_place_baselines.py` 落位时**优先本 trip 归档**，无归档才用 `shots/<node>.*`，并报 `placed_from_archive`/`stale_blocked`。


## 4.ab 瞬态页：不等 idle 的身份尺 + 连拍（2026-09-11，安卓真机实证后落地）

**病**（0910r3 实爆）：`GuideInitFragment` 是 5s 倒计时加载页。交付基线 `GuideInitFragment.png/.android.xml` 内容是**首页**，
账本却 `capture: verified / identity_by: chain_position`。链路：tap 后"早拍帧"（screencap 自身 ~0.3–1s）拍到**上一页**；
uiautomator 到达判定要等 idle，进度条一直动 → 窗口内一次 dump 实测 **7.44s**；settle 内核再拍时已是**下一页**；
capture_page_e2e 的 `chain_position` 路径把早拍帧按链位直接绑定——**标签对、内容错**，且没有任何一步核过那张图的身份。

**尺子换掉，不是时间点换掉**：`adb shell dumpsys activity top` 由 ActivityManager 直接吐当前 Activity、androidx
FragmentManager（每个 Fragment 的 `mState`：当前页唯一 RESUMED，其余 STARTED）、View 树（类名/resource-id/相对父 bounds/可见可点
标志），**0.05s 一次、不看动画**。真机时间线：点「继续」后 0.7s→5.66s 连续 18 次 `GuideInitFragment` RESUMED，5.96s 切
`HomeActivity`；ViewPager2 页容器 bounds 当前页 `0,0-1440`、相邻 ±1440（预建页在屏外，`visible_rids` 排除）。
它唯一给不了 TextView 的 text（Android 12 dumpsys 不打印）→ 文本从布局 XML（`android:id → android:text`，`@string/` 按
values/strings.xml 解）与树 `runtime_text_writes` 纯字面量补，合成的 xml 根上标 `dump-source="dumpsys" text-source="layout"`。

**机械落地**（`lib_dumpsys.py` 纯函数 + `walk_exec._transient_burst` + `capture_page_e2e.load/bind_transient_bundle`）：
1. **候选**从计划机械筛：`transient_candidates(walk)` = 有 `auto_transition` 且 `kind=push` 且 `wait_hint≠immediate` 出边的节点
   （页面自己跳走）。宿主装默认子页（immediate）、自动弹窗（目标是 dialog）起点不消失，不算。本树 2 个（Splash 走冷启路径已有早拍）。
2. 到达候选页：tap 后**立刻**进窗口循环（不拍 `_pre`、不睡 0.8s）：每 tick dumpsys 判身份（`identity_on_node`：resumed activity /
   RESUMED fragment / 屏内 view_ids 兜底）→ 成立就 `exec-out screencap` 一帧（0.3s）→ **身份一离开即止**；预算
   `burst_budget_s`（countdown×1.5+1，默认 6s，≤30s）只是上限。
3. 绑定图 = **最后一帧**（最接近稳定）；dump = 该时刻 dumpsys View 树合成的 uiautomator 格式 xml（只收可见+屏内子树）。
   打包 `pending_shots/<node>__transient.json`；到达判定直接采信包（`_mech_notes: transient_burst_arrival`），
   边真值 `waited_s`=首次见到的秒数、`landed`=包里的 activity、附 `transient_capture{}`。
4. settle：capture_page_e2e `--capture-only` **优先吃包**（`identity_by`=包里的 dumpsys 判据，`dump_source=dumpsys`，包用过即改名
   `.used`，过期 30 分钟不吃）；**没包且 dump 验不上 → `Esc(16, transient_missed)` 挂判读债**，`chain_position` 绑定路径删除。
   闸红是故意的：瞬态页没截获就是欠账，不许拿别页的图充数。
5. 文本身份：合成 xml 里的 rid→文案让 T-4（`rid_texts`）对瞬态页也能给鸿蒙元素身份；判读侧看 `text-source=layout` 知道文本非运行时观测。

**通用性**：只吃 dumpsys 格式（平台层，Android 12 实测）、树字段、布局 XML；RESUMED 不写死 7（取同组最大）；
ViewPager v1 的子页偏移看不出滚动量 → Fragment 状态为主判据、容器 bounds 为兜底。成本：只对候选，每页净增 0–3s。

6. **同一把尺也接进到达判定与 settle**：walk_exec 全部 `sentinel_check` 调用经 `self._sentinel` ——哨兵不中或弱 → dumpsys 兜底；
   capture_page_e2e `on_page` 宿主闸与末尾两处 → `_dumpsys_on_page`。治两类实爆：向导三页文本相同（settle 连挂 exit 16 → streak 熔断）；
   共享参数化弹窗每个状态只渲染部分子 View（现场 dump 就是 AppTipsDialog 却"唯一 id 可见命中 0/5"）。弹窗叠宿主时两者都
   RESUMED：判弹窗在场即成立，判宿主页多出的只许是弹窗。
7. streak 熔断（连续 3 笔 exit 16）前把游标推到下一步、位置=本步落点、熔断包带真实步号——此前记 `step ?` 且游标停在本步，
   `--resume` 会在已到达的设备上再点一次（验收实爆：把瞬态页整段点穿）。

8. **宿主页补结账遇弹窗叠层 → 推迟**（a)，2026-09-11 验收实爆）：late_settle 时若树里的弹窗节点在 dumpsys 里 RESUMED 叠在宿主上
   （`lib_dumpsys.overlay_dialogs`），uiautomator 只 dump 顶层窗口 → 宿主基线=弹窗内容却因 activity 后缀相符判 verified
   （HomeActivity.android.xml md5 == AppTipsDialog 的）。现在：不结、记 `state.late_settle_deferred[]`；每步开始前 `_retry_deferred_settle`
   ——dumpsys 判位仍在该节点且弹窗已不在 → 补结（`late_settled.reason=deferred_dialog_overlay_then_settled`）。**不排水**（弹窗多半是
   计划内下一步的目标，如 auto 边 → AppTipsDialog）。capture 内核同判据硬闸：`on_page` 顶部 `_dumpsys_overlay_ids` 命中 → 不按 activity/
   dumpsys 尺绑宿主；`classify_arrival(overlay_ids)` → `dialog_over_page(source=dumpsys)`，与 catalog 唯一 id 命中同一出口。
   `_tests/test_walk_exec_overlay_defer.py`（3 例）+ `test_ab_fixes_pure_0911.py`。

**验证**：`_tests/test_lib_dumpsys.py`（11 例，含假时钟窗口循环、弹窗叠宿主）+ `_tests/test_transient_bundle.py`（5 例，含 on_page 假驱动兜底）；真机 28 份 dumpsys 快照离线复核身份时间线；walk_0 首启链真跑验收（连拍 5 帧 0.35→4.31s，绑定图=83% 真加载页）。

## 5. 节点普查 node_sweep（grounding + blackbox 融合，三账在此闭合）

**★★链页禁普查铁律（2026-08-14 补入散文——此前只活在机械代码里，codex LLM 编排因此复发
8-13 同款事故：Splash 上跑 sweep 触发声明浮层、烧掉首启门、六个向导页全无 GT）**：
**首启链页（walk_0 全趟 / 隐私·Guide·向导类页）一律不普查**。首启链是一次性门，census
逐个点未认领元素=当场烧门，门过了 pm clear 之外无法回来。防线三层：walk_exec 对
chain_protected 趟自动跳过（趟级零识别）；node_sweep 自带或门拒绝（first_launch_onboarding
∪ wizard_step ∪ 页名前缀，任一命中 exit 21，宁枉勿纵）；被拒的普查**不是放弃**——欠账由
**收尾链趟**统一补：全部遍历收尾后专门 pm clear → 重走首启链 → 带 `--allow-chain-sweep`
放开普查（此刻烧门已无代价，与"破坏性下沉到最后"同一哲学）。除收尾链趟外**任何场合
禁带 --allow-chain-sweep**。

**首达 🆕 节点后必调**——整条链路的机械杠杆所在（一次调用批量扫全节点元素；11s/check vs LLM 逐条 35s，
3 倍杠杆来自这里，**不来自机械编排**）。sub-agent 编排模式手动调、walk_exec 回放模式自动调，
两种模式都**必须带 `--from-plan`**（同一安全前提，禁手填）：

```text
python3 $SCRIPTS/node_sweep.py --serial $ANDROID_SERIAL --package <pkg> \
    --node <id> --dir $EW --tree spec/toolkit-fact-tree.json --from-plan \
    --trip-id <trip> --out-blackbox spec/visual-verify/blackbox_discoveries/round-0/<id> \
    [--skip-walked 关于我们,续订管理] [--budget-s 90]
```

机制：**一次滚动全量枚举** → 元素级定性分账（六类归宿全入账，治"名义已探"假绿）→ 单循环扫"点完必回"的元素：
- `walk`（出边 trigger）→ **普查不点**，留给 DFS 下降时点（双认领也留给行走，落地证据双记账）
- `same_dest`（check 的 anchor rid == 本节点某出边的 trigger_view_id）→ **普查不点**，标 deferred_same_destination + inherit_from_edge → 行走走那条边时的落地证据经 §3.9 walk_inherit 继承（省一趟进子页+BACK；实测 MineFragment 17 条省 6 条）。★覆盖率兜底：边没走通 → walk_inherit 写 needs_retap → 回行走补点，绝不丢覆盖
- `ground`（check 锚点，非同落点）→ tap→抓证据→BACK
- `unclaimed`（无主）→ tap→观察→BACK 入 behavior_ledger；落到树内已知节点=顺手 discovered edge
- `destructive` / `nav_back` / `input_field` → 不点，入账（输入框 tap 只弹键盘，实测污染回位判定）

**★ `unplanned_destructive` 当场处置协议（2026-07-17，sweep stdout 非空 = 必须执行，不许留账走人）**：
sweep 会把「destructive 且计划没认领（rid 不在 planned_edge_vids、无 walk 认领）」的元素上报为
`unplanned_destructive[]` —— 这= **树漏的破坏性边**：边发现兜底靠 tap 落点，而 destructive 不 tap，
机械路径在这类元素上全断；**安卓只遍历一次，「记待办等下轮复核」= 死账**。sub-agent 收到后**当场**走完：
1. **读源码**（还在本节点上，位置零成本）：按 rid 找 onClick 全链，判「点了会怎样」。
2. **源码证实落点是带取消键的确认弹窗** → 当场按 stop_at_dialog 补点：tap 入口 → 弹窗截图
   （`shots/_evi_<Dialog>_<rid>.png`）→ **点取消/BACK，绝不点确定** → 边（confirmed，landed=弹窗）
   + grounding 证据当场 append `edge_results.json` / `grounding_results.json`，note 带源码锚点。
3. **源码证实直接执行/无确认门/看不清** → **不点**，把源码证据本身当真值入账：
   `edge_results.json` append 一条 `status=deferred_destructive`（from/trigger rid/源码锚点/
   「无确认门，点即执行」）——「此控件无确认门」就是有价值的边真值，writeback 会写进 `deferred_in[]`。
4. 两种结局**都必须落 `edge_results.json`** —— 这是唯一有下游的账本（writeback→树）。
   **禁写自由命名的侧文件**（`discovered_edges_<node>_*.json` 这类调查产物零消费者，实测直接变孤儿）。
5. **点到弹窗的（第 2 类）还必须回流 blackbox 账**，否则弹窗截图永远只是证据、变不成基线：
   ①截图 cp 进 `round-0/<node>/{node}__via__{trigger文本}__{idx}.png` ②该节点 manifest 的
   `discoveries[]` 追加一条（trigger_text/trigger_resource_id/landing_ability/**screenshot**/key，
   rid 非空=天然静态必物化）→ materialize 幂等重跑时自动物化 `{Dialog}#via={trigger}` 变体节点 +
   extras_variants + outbound 边 + **截图落位成正式基线** `screenshots/android/{trip}/{variant_id}.png`。
   多态共享弹窗（AppTipsDialog 一个节点 17 个 caller 17 种内容）只有按 #via 分变体才有可对账的基线——
   实测「取消订阅/一键退款」两变体走完全链：variants_added 2 / baselines_copied 2。
实测案例：MineFragment 的 `tv_fast_unsign`(取消订阅)/`tv_fast_refund`(一键退款) 树内零出边、
计划零步序、sweep 判 skipped_destructive → 三层全不碰，B2 agent 读了源码（`MineFragment.kt:215-217`
→ 弹 AppTipsDialog 确认窗）却只写了孤儿侧文件——**它做对了判断，缺的就是本协议这条授权和下游**。

四条判重/继承规则：元素级 rid 判重（文本匹配漏认 58% 的教训）；双认领留给行走；**边走失败时 check 继承边的 not_reproduced 观察**（同一控件同一事实，不点第二次"确认失败"）；脏锚点双点即侦错。

`--from-plan` 是安全前提（机械/人肉两模式**同一来源**，禁手填）：从 walk_plan.json 推导 ①排除键=**跨所有 walk** 的全部边 trigger+反哺 rid（单 walk 派生会漏掉隔离在 walk_2 的副作用边——普查点掉=真实触发生成，实测过）②哨兵全列表 any 命中 ③已有证据的 check 自动跳过。启动时**位置自检**：哨兵不匹配拒跑（防证据错挂到错误节点）。已知残余风险：无标签的副作用边首跑仍可能被当无主点掉（反哺 rid 后二跑消失）。

回位三级：noop（sig 未变）天然在位+ESC 收键盘；page_change/overlay → BACK 梯；escaped → 轮询式重拉起（宿主 activity 对即软回位）。每元素独立保险丝，连续 2 个回不来才中止普查。

产物：`round-0/<node>/manifest`（behavior_ledger/discoveries 同 blackbox schema + 新增 sweep_inventory_dispositions 全清单归宿）+ `$EW/grounding/<id>/run_meta.json`（**每条 check 恰好一条记录**：ok / deferred_to_walk / settled_by_walk / deferred_outcome / input_field_no_tap / not_found）。
兜底：ground_page_checks.py 保留给"只补单页 grounding、无行走计划"的场景。

**批判定的归属 = 判读制（2026-07-18 二改；判定为何从行走 agent 剥离成专职 agent 的演进史见 [`rationale-log.md`](rationale-log.md) §判读制）**：
- **行走 chunk 只出观测**：sweep 落 run_meta + 交接报告里写 `swept_nodes[]` 与「观测异常注记」
  （现场才知道的事，如「分类 tab 的 sig 判 noop 是假阴性、截图实际变了」——判读 agent 只读
  run_meta 会照单全收假 noop，这类现场知识必须随报告转移）。
- **判定归专职判读 agent**：主会话在 chunk 边界派出（时序见 §3），输入 = 该 chunk 的 run_meta
  **快照**（主会话拷到 scratchpad——原文件跨 chunk 重扫时会被整文件覆写，读快照防半截 JSON）
  + 截图目录路径 + 交接报告的异常注记；只判 `swept_nodes` 清单内、`status ∈ {ok, found_no_text}`
  的观测（**只判观测过的，代判=伪造证据**）；**返回 JSON，不写任何文件**。
- **主会话在边界窗口合并**（见 §3）；finalize 2.5 闸机械兜底：观测了没判定 → 红 + 逐条明细
  （判重键 idx 感知 + 对账面含 found_no_text）。判读 agent 挂掉/超时 → 按 swept_nodes 重派即可。
判定产物 schema —— 追加 `$EW/grounding_results.json`（由主会话写入）：
   `{"node","check_name","expected_android":"实测一句话","android_trusted":bool,"precondition":"已登录VIP"}`
   - 落点与 check 语义吻合才 trusted=true；没真到达绝不写 true
   - `hit_by=="text_fallback"` = 树内 rid 不存在（真机兜底命中）→ 记边真值缺陷，勿当正常 ok
   - **`outcome=toast_only` + `toasts[]` = 脚本已替你抓好 toast 原文**（2026-07-17 实装，此前本行只写「**可** logcat 抓」——是建议不是步骤，于是从没实现，只 toast 的 check 一律记 `noop`、证据永久蒸发）。**toast 不进 a11y 树**，dump 和 `landed_texts` 永远抓不到它；node_sweep 现在 tap 前打设备时间戳、tap 后按 `--toast-tags`（默认 `Toaster`）做时间窗 logcat 查询（**0.03s/次**，对比 uidump 2.1s，白菜价）。toast 原文带源码行号，够直接写 `expected_android`——实测 `检查更新` → `(MineFragment.kt:245) 未安装市场客户端`、`清除缓存` → `(MineViewModel.kt:27) 已清除缓存`。
     ★ **换 App 必须重认 tag**：先 `adb logcat -d` 输出里搜 toast（忽略大小写）找它的统一封装类；没有统一封装的 App 给 `--toast-tags ""` 关掉，别让它假装抓过。
     ★ `noop` 与 `toast_only` 的分界是**有没有新 activity 压栈**，不是「有没有发生事情」——两者都不下沉，回位一律走 ESC 收键盘、**绝不 BACK**（见 node_sweep 的 `NON_DESCENDING`）。
   - `still_on_page=true` 且**没有** `toasts[]` 又疑有反馈 → 看截图（可能是 Snackbar/自绘浮层等不走统一封装的）
   - `deferred_outcome`（事务型）→ 按 phase2.5-grounding §2a 走 verify_outcome，排本 trip 最后

安全铁律（违反即轮次作废）：destructive check（执行器 DESTRUCTIVE 表自动垫底+到弹窗即止）**绝不点确定/确认/是**；绝不点退出登录/注销确认；`[skip_unless_verified]` 边看清弹窗语义，可能确认退款/退订 → 直接跳过记 deferred_destructive。**执行器 DESTRUCTIVE 表宁可宽**（漏一个词=整轮登录态报销的未遂事故实测过）。

## 6. 反哺铁律（writeback_walk.py 已内置，prompt 里仍须声明）

- **负面证据永不删边、不动 inbound_triggers 存在性**（"VIP 态不渲染"≠"边不存在"；删边 → inbound 空 → phase2_scope 误杀，18/40 事故根因）。not_reproduced 只写 `runtime.not_reproduced_in[]` 态标注。
- 行走发现的树上没有的边 → 只进 `discovered_edges[]` 待复核，**不直接插 inbound_triggers**（那是源码级真值的地盘：运行时观测只能证明"我点了它跳了"，证明不了"源码里这条边长什么样、有几个调用点、有没有门禁"——插进去 = 拿弱证据冒充强证据）。
  **★ `discovered_edges[]` 没有自动消费者，这是故意的，但必须有人看**：`materialize_blackbox_to_factree.py` 只读 `blackbox_discoveries/` 下的 manifest，**从不读树里的 `discovered_edges[]`**；这个字段全 skill 只有 `writeback_walk.py` 写、**零处读**，是个只写字段。复核只能靠**重跑 ART 带下钻提取**（实证 needs_discovery 61%→13%、边 43→73，且纠正了 18 条挂错页的边）或人读源码。`walk_finalize.py` 会把条数报出来当待办，**别让它无声堆积**。
  ★ 教训：**指向不存在的下游 = 比没有下游更危险**。"走 materialize 路径"读起来像一次干净的交接，于是三任读者（含写下它的人）都以为责任已经安置好了——这正是 blackbox 账 147 条 behavior_ledger 躺了一整轮没人管的同款根因。**凡在规范里写"这个走 X 处理"，必须当场验证 X 真的读它。**
- grounding 只写三字段（expected_android/android_trusted/precondition），绝不碰 navigation/reach_path/purpose。
- 反哺后自检：inbound_triggers 边数必须 t0 == t1（删 0 增 0）。

## 7. 已知坑（多轮实测，prompt 注入 sub-agent）

### 7.1 普查逃逸三形态（全量跑实证——**sub-agent 当场处理，别升级主会话**）
node_sweep 会点无主元素，真实页面这些元素常把设备带走。安全机制（熔断器/破坏性拦截/WebView 守卫）保证**不乱飞不污染**，但**位置会丢**，恢复归 sub-agent：
- **启动外部 app**（实测 MineFragment 某元素拉起 Google 搜索）→ 重拉起本 app + 重新导航回该节点续走；
- **选中即消费的瞬态选择页**（实测 ChoicePPTTemplatePage：18 个模板卡片是同构列表全跳预览页，选中后本页 finish，BACK 从预览过冲回 CreateOutLinePage）→ 该页普查注定 truncated，**别反复重扫**（重扫会再逃一次）；capture 账已结即可，coverage 不全如实记；
- **H5 路由**（WebView 页）→ node_sweep 已有守卫自动跳过，不会发生；
- ~~**titleBar 返回箭头**（无 rid 无 text 被判无主 → 点掉=BACK 弹页；run-2 实测带 titleBar 的 Activity 3/3 逃逸）~~
  → **已修（2026-07-20）**：node_sweep 几何指纹（无 rid/text/desc + 整体落顶栏带 y<12% + 贴左缘 x<3% + 宽<20%）
  判 nav_back 不点，账记 `skipped_titlebar_back`（带 bounds，判读可复核是否误拦真功能键）。
  19 页 dump 离线回归:9 命中全真箭头、零误伤（右上角无身份分享/搜索键靠贴左缘条件幸免）；真机 AboutUsActivity
  实扫 position_lost=false。**sweep 后独立验位的要求不变**（自报位置仍不可信，此修只是消掉最大逃逸源）。

### 7.2 创作流：**可带预算尝试**（2026-07-16 实测更新），超预算才按原方案挂起
旧结论「通用机械行走覆盖不了 → 直接挂起」**过于保守**，会让 app 的核心功能永远验不了（AIPPT 的核心就是生成 PPT，把它跳过等于验了一圈外围）。同项目真机端到端实测已跑通，但**只推翻其中两条**，另两条保留：

| 旧列病因 | 现状 | 依据强度 |
|---|---|---|
| BACK 过冲 | **已修**：count 驱动回位 + 向上走检测 + 位置守卫（见 node_sweep / §7.3） | 结构性改动，不依赖样本 |
| 选中即消费（18 卡片） | **已解**：卡片 rid 在 `planned_edge_vids` 里 → 普查不碰；行走只**故意点 1 张** | 结构性，同上 |
| 输入门禁 | **有配方**（见下），但样本少 | 实测 1 次 |
| 异步生成卡死 | **⚠ 未证伪，见下** | — |

**真前提（照配方做，别再无脑挂起）**：
1. **输入必须 ASCII**——`adb input text` 打不进中文（NPE，§7.3），空格用 `%s`。输入内容与目标输入框**来自树**：边的 `state_required` 前置带 `input:{view_id,text_hint}`（2.7 契约），计划器据此出 `type` 步（§4.y）；`text_hint` 缺省时执行器用中性 ASCII 默认串。守卫阈值（非空/长度上限）以前置的 `evidence`/`data_hint` 为准，不在文档里写死任何项目的字段名。
2. **两个异步等待点必须轮询、禁固定 sleep**（用 `walk_whereami --expect X --wait N`，§4 步 3）：
   ①**大纲生成**——`group_next`(选择PPT模版/重新生成/保存本地) 默认 `gone`，`pptOutlineCreateSuccLiveData` 触发才可见 → 轮询 `tv_create_ppt` 出现；
   ②**PPT 生成**——PPTCreatingDialog 显示「PPT生成中，请勿关闭页面...」→ 轮询 activity 变 `PPTFilePage`。
   另注：`CreateOutLinePage--[选择PPT模版]-->ChoicePPTTemplatePage` 的 onClick 里有 `lifecycleScope.launch{checkTextIsCheat}` 反作弊校验，**落地要 3-5s**（§4 步 3 已记）。

**⚠ 异步耗时无上界——这条不变，是唯一真正致命的风险**：
单次实测（trip_2 已登录 VIP）：大纲 2.5s / 选模板 ~4.5s / PPT 生成 34.7s / 全链 ≈55s——**N=1，只配当设预算的参考，不是上界**。§7.3 记的「生成/上传类真实异步任务可能产品级卡死（15min 零轮询实测）」**未被证伪**（服务端负载/网络/账号额度都可能让它卡，两个观测并不矛盾）。
★**必须设硬预算（建议 ≤180s）；超预算 → 立刻跑机械判死探针，禁临场发挥无上限观察**
（run-2 步6 实测：walker 临场取证花 2m43s，机械动作只值 30-60s，其余全是 LLM 回合延迟）：
```text
python3 $SCRIPTS/meltdown_probe.py --package <pkg> --tag <哪步> [--dir $EW]   # 全程硬上限 ≤60s
```
探针先无损判活（两次 uidump 间隔比对文本层——**静止前绝不按 BACK**：弹窗若可取消，先按会亲手杀掉活着的慢生成；spinner 旋转是 drawable 动画不进 view 树，不会误报活），静止才 BACK 逐按逐验探可取消性（一有响应立即停手）。按 verdict 三分支：
- `alive`（间隔内文本仍在变）→ 一次性延长预算 ≤120s 再等；二次超时按 unreached 记账，不再延长
- `static_back_changed`（静止但 BACK 有响应）→ 读输出的 `now_texts`/`final_activity` 现场处置（弹窗已关？确认门弹出？——确认门铁律禁点确定）
- `static_back_eaten`（静止且 BACK×3 无响应）→ **判死成立**，探针输出即完整熔断证据（截图×2 + dump×2 + 进度文本），按 §4 熔断协议冷启；随后视情况派 `arkts-scenario-runner` 学配方
- 其余（`pkg_escape`/`dump_failed`/`cap_exceeded`）→ 事实报回交 LLM；`dump_failed`（could not get idle）多半 = 有动画在跑，偏「活」
不对称性决定了保守边：不走只丢覆盖（可补）；硬走卡死毁掉整轮（贵且要人盯）。

判据（保留）：一条链上连续 ≥2 个节点出现 7.1 形态 → 停止硬走，记账挂起。**但创作流本身不再默认属于此类。**

### 7.3 其余
- **单 activity 尺失效**：fragment tab 切换不改 activity——判位必须用 walk_whereami 双闸，禁自行 dumpsys 判"没动"。
- **软键盘遮底部导航**：自动聚焦输入框的页（首页）键盘弹起会遮住 tab 栏 → tab 边定位全失败。键盘弹起时按 BACK 收（IME 先吃 BACK 不弹栈；ESC 对部分 app 无效）。node_sweep/walk_exec 已内建，人肉导航时也要注意。
- **activity_root 宿主壳与 tab 共屏**：HomeActivity 等 root 的屏幕就是当前 tab 的内容——普查 root 会点到 tab 的边跳走。root 只结 capture、不普查（walk_exec 已按 relationship_kind 拦；人肉模式同理）。
- **入边种类决定 BACK 行为**：同一页从 tab 进 BACK×1 正常、从生成链进是新栈底 BACK 退桌面——炸栈边选便宜可逆的入边，walk_plan 的 DFS 已按 PRIO 排序。
- **树 4 类假边**（静态分析固有）：异步跳转当 tap 边（trigger_method 含 LiveData/观察→ 字样）/ 2 跳压直达 / 标签指错 / 包含关系（embed 步计划已拦）。撞到即记 not_reproduced + 归类 note，是产物不是浪费。
- **首启单行道**（wizard_step）：tap 可能推进链不可回——先截图后测点，误推进 pm clear 重走。
- 输入框中文打不进（adb input text NPE）→ 用 ASCII；空格用 %s。
- `keyevent 111`(ESC) 会直接关 dialog，误用后需重开补测。
- 生成/上传类真实异步任务可能产品级卡死（15min 零轮询实测）——设超时预算，超时记 unreached+证据，别死等。
- **后端登录态可能是进程级、不可逆的**（2026-09-09 实证：mock 后端一次登录后，任何 pm clear + 冷启都回到已登录账号；
  只有登出接口或重启后端能复位，而登出确认铁律禁点）→ 登出态 trip 必须在登录前**全部走完**；登录后再派登出态 walk
  注定白跑（执行器已拒）。会员/购买漏斗这类「非会员才显示」入口靠前置极性 `absent` 进登出趟，不需要改后端造态。
- **同宿主子 tab 切换对结构签名不可见**：普查点子 tab 判 noop 却真切了页，下一条边打在错分支上。node_sweep 现用
  状态签名（selected/checked/文本集）识别 `state_switch_inplace` 并回点原 selected 兄弟复位；执行器普查后仍独立判位。
- **回位阶梯第一下 BACK 会被自动聚焦的 IME 吃掉**，后续 BACK 一路退到桌面且 manifest 曾报 position_lost=false。
  现每次 BACK 前先查 mInputShown 收键盘；任何时刻包名变化即 position_lost=true，只有哨兵+签名双验证回锚点才撤销。

## 8. 与页粒度 dispatcher 的关系

页粒度（dispatch_phase2_batches + phase2-android-batch-prompt + capture_page_e2e）**保留为补漏兜底**（全文 2026-09-07 自 SKILL.md 迁至 [`phase2-page-dispatcher.md`](phase2-page-dispatcher.md)；`dispatch_phase2_batches.py --plan-only` 的 stderr 会点名它必读）：
- blackbox_explore.py 在边粒度主路径已被 node_sweep 取代（融合普查），但**保留**为共享库（DeviceAdapter/枚举/DESTRUCTIVE_RE 被 hmos_capture 等 import）+ 页粒度兜底模式的 runner，勿删勿改签名
- 边行走 unreached 且归因为「熔断漏采/需单页重采」的节点 → 按页粒度单页流程补（它的 BLOCKED schema/自愈梯照用）
- 单页失效重截（删 png 重跑）场景仍走页粒度
- ⛔ **不存在"整体回退"**（2026-08-12 删除旧条款「needs_discovery>50% → 整体回退页粒度」，实爆：15/39 可走节点被全员降级陪葬）。**永远混合**：计划盖到的（含投机）全走边遍历——投机边走通一条就多一条 runtime 真值反哺，下轮它就是可执行边（飞轮）；页粒度产零边真值。页粒度只接三类：coverage_gap / 确认孤儿 / 行走 unreached 落 needs 账的
- 行走连续熔断 >5 次 → **只砍剩余行走**（当前 walk 余量 + 未启动的 walk），已走的照常 `walk_finalize.py --trip <trip>` 落位——被砍分支上 defer 的 check 会触发 needs_retap 闸（exit 20），熔断收口走 `--accept-retap-debt` 留痕（进 `_phase_markers.retap_debt`，债不消失）；剩余节点标 BLOCKED(reason=meltdown_curtailed) 交页粒度单页补采（routes.json 已有该 reason 的路由处方）。真值资产绝不因回退动作陪葬
- ⚠️ 对"投机链深页"的清醒预期：这些页的 reach_path 恰是树边质量差的部分，页粒度兜底大概率也是 LLM 人肉导航（capture_page_e2e 单 activity 尺对 fragment 结构性失效，见下）且产零边真值——兜底 ≠ 更优，只是不阻塞；治本是补树
已知缺陷提醒：capture_page_e2e 的 chain_walk/on_page 是单 activity 尺（fragment 页判进结构性失效，AIPPT 实测 nav_by:llm 14/15），补漏时预期脚本 exit 10/15 后 LLM 接管导航属正常路径。

## 9. 产物清单

- `$EW/walk_plan.json|txt`、`ledger.json`、`shots/`（结账证据，落位 baseline 前的原始件）
- `$EW/grounding_results.json`、`edge_results.json`、`grounding/<node>/run_meta.json`
- 反哺后树内：`functional_checks[].expected_android` 等三字段、`inbound_triggers[].runtime`（含 back_returns_to_parent）、`discovered_edges[]`、`_phase_markers.walk_*`
- baseline 落位（walk_place_baselines.py）：`screenshots/android/{trip_id}/{page_id}.png`（+ .android.xml）+ unreached 的 `BLOCKED_baseline_*.md`——phase2_needs / 验收闸 / Phase 4 零改动消费
- blackbox：`blackbox_discoveries/round-0/<node>/{manifest,截图}`——materialize / behavior_ledger 既有路径零改动消费
