# arkts-visual-verify 规则由来归档（rationale-log）

> **这个文件不在任何必读清单里。** 2026-09-07 从热路径文档（SKILL.md / phase 手册）里把「讲历史、讲为什么」的纯叙事段落原文搬到这里，
> 规则本体与一句话护栏留在原位并指向本文件对应小节。**改规则不改这里；这里只增不删。** 想知道某条铁律是哪次事故换来的，来这里查。

## 遍历模型统一——此前 trip_1 特例的由来

> 来源：SKILL.md Phase 2 引言，2026-07-25；2026-09-07 迁入，原文逐字。

> 此前 trip_1 是"边粒度的特例"（`plan_edge_walk.py` 里 `targets = capset - cfg["trip1"]` 把首启链
> 整个减掉，改由 chunk 链式连采）——链式连采**本来就是一笔画**，但**步序没落盘**，只留下散文
> `reach_path` 的 chunk manifest，于是鸿蒙 trip_1 只能靠 LLM 重新推导怎么走，白白掉回慢路径。

## 走完≠落地——2026-07-17 事故实录

> 来源：SKILL.md Phase 2 引言；2026-09-07 迁入，原文逐字。

> **★ 走完 ≠ 落地（2026-07-17 事故）**：首次全链路行走跑完 110 分钟、三本账全产出，**三条反哺路一条都没跑**——树里 `blackbox_behavior`/`#via` 全 0、`screenshots/android/` 里 0 个本轮文件，而 `walk_ledger status` 照报「settled 19/39」一片祥和。根因：v4 用 LLM 编排换掉了老的 `dispatch_phase2_batches.sh`，**拿走了它的身体却没接管它的收尾**（老 dispatcher 里反哺是无条件跑的 shell post-step，不靠人记得）。**收尾必须是机械的，不能是自觉的**——所以有了 `walk_finalize.sh`，别拆回成几条独立命令。`walk_ledger.py status --tree <t> --trip <trip>` 现在会查收尾账并报红。

## trip 态预检删除的四条理由

> 来源：SKILL.md Phase 2 trip 态建立步骤 2，v2026-07-10c；2026-09-07 迁入，原文逐字。

# 2. 【每个 trip 起始，仅一次】建 trip 态 —— 边界真跑即验证（v2026-07-10c：**删除了原"就绪态
#    预检"独立环节**。理由：①真跑一遍本身就是最准的验证，且发生在恰好需要该状态的时刻——预检
#    与本步纯重复 ②旧预检非 trip-scoped，trip_1 会被 trip_2 才需要的登录卡住 ③预检是纯散文
#    无脚本无闸，可被静默跳过 ④其枚举源=树的 preconditions，树坏即假绿（state_required 曾整维度
#    丢失）。状态一律"撞到才学"（at-need 派 builder）；已知残留=state_required 空态静默采集，
#    页级检查另项处理）：

## 一笔画五步——③④补齐前的后果

> 来源：SKILL.md Phase 4 引言，2026-07-25；2026-09-07 迁入，原文逐字。

> **③④ 是 2026-07-25 补的，此前没有** —— 后果：canonical 目录停在上一轮页粒度残骸、sbs 近乎空、
> 行为覆盖 43% 却报"全绿"。**跳过 ③ 下游全瞎，跳过 ④ 漏测当通过。**

## 证据通道闸为何前置到派 fixer 之前

> 来源：SKILL.md Phase 6 Step 0，2026-08-29；2026-09-07 迁入，原文逐字。

   > **为什么放在这一步**（2026-08-29 round-6 实录）：整轮闸 6.4 **算得完全正确**
   > （`ROUND_INCOMPLETE`，报告首行就写着"结论无效"），但它跑在 Phase 6.4——
   > **那时 fixer 早派完了**。判断力从来不缺，缺的是它亮在派发之前。
   > 同一批数据：canonical 34→31→14→**0** 逐轮萎缩，adhoc 0→46→59→**64** 逐轮膨胀。

## 判读制的演进史

> 来源：phase2-edge-walk.md §5，2026-07-18；2026-09-07 迁入，原文逐字。

**批判定的归属 = 判读制（2026-07-18 二改。初版被动语态没说归谁 → 11 条滞留一整轮；一改为
「chunk 收尾自判」；二改为判读制以配合 §3 的双派并行——把判定从行走 agent 的附加职责剥离成
专职 agent 的唯一职责，prompt 越薄越不会掉）**：

## replay 冒烟实测 2026-07-22

> 来源：phase4-replay-run.md §5.95；2026-09-07 迁入，原文逐字。

## 5.95 ★冒烟实测发现(2026-07-22,Batch C+B 真机跑,见 aippt_vvCompare/spec/visual-verify/replay/SMOKE_REPORT.md)
切 3 段独立冷启 batch 跑了 C(推荐/作品 23步35s)+B(我的/会员 98步48s)。**架构骨架(切段/安全剪枝/弹窗/webview/tab导航)验证有效**;
blocker 全在前置态+上游数据+编译器健壮性,非骨架:
- ✅已修(2026-07-22)**T1[执行器·preflight] 登录检测查错页→根治=执行器删建态职责**:错不在查哪页,在**层**——
  建态+验证归 dispatch 层(next_batch 算 first_batch_in_trip→trip 首 batch 跑一次 scenario_chain;**验证步在 login YAML 自身**,
  login_harmonyos.yaml 结尾本就切「我的」tab 验 ui_gone:点击登录 + ID:)。执行器零建态职责:不查态不登录不硬停;
  态中途丢→到达门控+级联升级接住,按门禁铁律交 judge 判 P0(不归因环境)。preflight 自动登录块已整段删除。
- 🔴**T2[环境] 设备实为登出**(点击登录/剩余体验次数:0次,零 ID:/VIP;VIP有效期到7-31却登出=session没跨重启存活)→
  会员区 expect 全用登录真值→step43 我的tab WRONG_LANDING→9页 blocked。**印证"登录是被测前置不能假设已登好"**;需先把 login_harmonyos 在鸿蒙跑通(progress=0)。
- 🟠**T3[编译器] trigger_label_unknown 照 emit 空primary tap**(compile L192 fallback ""):C 的 3 条无trigger边→tried:[]→ABANDON+拖垮reconcile。
  修:见 trigger_label_unknown 且 prim=="" 且 rid空→emit skip(no_trigger_captured)(L85兄弟函数已跳,主emit循环漏)。
- 🟠**T4[上游·安卓侧] 3边 trigger_label_unknown**(Recommend→List/→Search、Works→Preview):安卓遍历没采到触发控件label(疑无文本图标入口)→鸿蒙无oracle。
- 🟡**T5[annotations] 引擎门边budget不足**:打开作品→PPTFile撞「PPT引擎启动中」(~15s)>默认4s→ABANDON;edge_overrides补 locate_budget_s。
- ✅**正向**:安全11条SKIP_DESTRUCTIVE_PRUNED(编译期静态剪,登出态识别乱套也零接触危险边)/tab导航稳/弹窗20条移reconcile/webview闭环/冷启15-18s非hang(受控复现推翻初判)。

## 设备包新鲜度检查的由来

> 来源：phase1-prepare.md Step 1.1.d，2026-08-11；2026-09-07 迁入，原文逐字。

# ★ 历史（2026-08-11，血泪）：
#   visual-fixer 改完 .ets 是「落盘即退，不重编、不复测」。更旧的版本这里写的是
#   `IF !APK_INSTALLED OR !HAP_INSTALLED` 才装、且装的是现成产物——于是第二轮起
#   整个分支被跳过，截的还是上一轮那个**旧二进制**。修改永远上不了设备 →
#   similarity 永远 < 0.95 → disposition 永远到不了 fixed → 无限轮次且"修复效果不佳"。
#   （再旧的设计把重编委托给 a2h-verify，单独调用时整条断掉。）

## ad_profile 前置的代价

> 来源：phase1-prepare.md，2026-08-11；2026-09-07 迁入，原文逐字。

> 实爆 2026-08-11：项目无 `script_test/config/ad_profile.json`，chunk 内撞上冷启付费墙 →
> "chunk 投降写单(47m) → 派 builder(68m) → 重派补采(3h+)" 三段全新上下文往返，只为关一个弹窗。
> ad_profile 是**每项目学一次**的资产，天然属于准备阶段——最常见的冷启墙在这里就能撞出来。
