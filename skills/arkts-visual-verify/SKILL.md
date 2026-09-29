---
name: arkts-visual-verify
description: 按页面粒度对 Android 与 HarmonyOS 自动截图、真实点击遍历并做多模态 UI/功能对比。基于 fact-tree 分 batch 派子代理，将差异写入 spec/fix/round-N/ui 或 feat，再交 visual-fixer 修复；登录页自动调用 arkts-scenario-runner 到态。用户要求截图对比、视觉验证、检查 UI 一致性或全量迁移验收时触发；需 adb/hdc 与双端模拟器。
metadata:
  tags:
  - verification
  - visual
  references:
  - references/alignment-rules.md
  - references/fix-file-schema.md
  - references/output-layout.md
  - references/cli-cheatsheet.md
  - references/e2e-pipeline.md
  - references/limitations.md
  - references/batch-classification.md
  - references/sub-agent-batch-prompt.md
  - references/phase1-prepare.md
  - references/phase3-skeleton.md
  - references/phase4-dispatch.md
  - references/phase4-scenario.md
  - references/login-troubleshooting.md
  - references/layout-troubleshooting.md
  - references/wiring-gap-detection.md
  - references/windows-setup.md
  - references/phase4-navigation.md
  - references/phase4-capture.md
  - references/phase4-long-page.md
  - references/phase4-webview.md
  - references/phase4-multimodal.md
  - references/phase4-classify-write.md
  - references/phase4-replay-run.md
  - references/phase4-replay-judge.md
  - references/phase5-systemic.md
  - references/phase6-summary.md
  - references/phase7-stubborn-loop.md
  - references/phase2-edge-walk.md
  - references/phase2-android-batch-prompt.md
  - references/android-navigation-playbook.md
  - references/architecture.md
  - references/phase2-page-dispatcher.md
  - references/batch-sections/B4.5-dual-oracle.md
  - references/batch-sections/B0.5-via-variant.md
  - references/batch-sections/B0.6-dialog.md
  - references/batch-sections/B1-data-state.md
  - references/batch-sections/NAV-compose.md
  - references/rationale-log.md
  depends_on:
  - android-fact-tree
  - arkts-scenario-runner
  - a2h-spec
  - hmos-fix-build-errors
---

> **Codex subagent dispatch convention.** This skill dispatches subagents. In Codex, spawn them with the `spawn_agent` tool and pass `agent_type` = the role name **exactly as written in this skill** — the roles registered under `.codex/agents/*.toml` use the same hyphenated names, so no translation step is involved: `a2h-activity-converter`, `a2h-android-analyzer`, `a2h-closer`, `a2h-fixer`, `a2h-migration-worker`, `a2h-verifier`, `ad-profile-builder`, `compose-fact-analyzer`, `hmos-builder`, `metric-fixer`, `scenario-builder`, `spec-fixer-ui`, `spec-fixer-ut`, `visual-fixer`, `visual-fixer-reviewer`. The built-in `general-purpose` agent_type is unchanged. (Claude's `subagent_type` field is written `agent_type` for Codex; `Agent(...)` dispatch calls are `spawn_agent(...)`; there is no `Task` tool in Codex.)
>
> **Join 协议（收口五条款）。** Codex 子代理完成后**不会**唤醒主会话——结果必须由派发方主动收口，违者=静默卡死（实测事故）。
> ① **循环 wait**：每个 `spawn_agent` 句柄用循环调用 `wait_agent` 收口；单次超时只代表"还在跑"，继续再调；**禁止以"等待子代理"为由结束回合**。醒后必调 `list_agents` 确认是谁完成——**完成的唯一合法信号 = `agent_status` 为 `{"completed": …}`，绝不是产物文件的存在/条数**（文件会中途落盘，读半截=实测事故）；completed 态会在数轮后从 list 中消失，所以每次醒来都要及时查。正文所有"等待完成 / join / 到点即收"表述一律指此循环。
> ② **死句柄与验收**：连续 3 次超时后调 `list_agents` 核对，可配 `wait_for_artifact.py` 探产物活性；已 completed 且 summary 可读 → 直接消费；句柄消失且从未观测到 completed → 按断点重派（带原 prompt + 已落盘产物，上限 2 次），禁止继续等待。**completed ≠ 验收通过**：join 点跑 `python3 .agents/skills/a2h-join/scripts/join_gate.py --project .` 验产物完整性，FAIL 视同未取回、按本条重派。
> ③ **收口锚点**：本 skill 最终完成报告前必须收口全部句柄（join_gate exit 0）；正文写明的显式 join 点优先按正文执行。发用户门（Gate）时允许句柄跨 Gate 存活，但 Gate 摘要必须列明未收口句柄清单 + 各自的指定 join 点。
> ④ **放行 ≠ 遗弃**：正文"非阻塞放行/到点即收/降级继续"只推迟收口时机，不豁免收口义务。
> ⑤ **fire-and-forget**：仅正文显式声明"结果丢弃/不 gate"的派发（如 a2h-execute 的 env-prewarm）免收口；审计只认 join_gate 内静态 allowlist，正文声明只是文档层。
> **派发纪律**：`task_name` 必须唯一（带 page-id/slice-id/round-N 后缀）；并行派发前把预期产物清单写 `spec/a2h/_work/expected_<join点>.json`（join_gate 对账用，契约只认派发方、不认子代理自报）；**谁派谁收**——sub-agent 内部需要"等齐 N 片再合并"时禁止嵌套外派后自行退出，要么同步自做、要么把分片清单回报主会话代派（sub-agent 一停止，收口能力即丢）。**契约产物必须出自承担任务的子代理**：重派上限后仍产不出 → 如实报缺并停在未完成态；禁止派发方代写占位产物让 gate 转绿（声明过也不行——绿账必须对应真产物）。

> **路径约定**：下文 `$SKILLS_ROOT` = 本套 skills 的安装根目录（用户级安装=`~/.agents/skills`；项目级=`<project>/.agents/skills` 或 `<project>/skills`）。执行任何脚本前先设一次——bash: `SKILLS_ROOT="$(cd "$(dirname 本SKILL.md)/.." && pwd)"`；PowerShell: `$SKILLS_ROOT = Resolve-Path "<本SKILL.md所在目录>\.."`。命令示例中的行尾 `\` 是 bash 续行符——PowerShell 请合并成一行或改用反引号 `` ` `` 续行；`ENV=x python3 …` 这种 env 前缀写法 PowerShell 不支持，改 `$env:ENV="x"; python3 …` 或用脚本自带参数（如 `--trip`）。脚本一律 `python3 $SKILLS_ROOT/arkts-visual-verify/scripts/<name>.py`（Windows 读作 `python`）；Windows 前置见 [references/windows-setup.md](references/windows-setup.md)。

# arkts-visual-verify — 按页面截图对比 + 产出 fix-markdown

<!-- PIPELINE_VERSION（④增量重验用，2026-07-12）：判定管线的语义版本号。**任一变更必须 bump**：
     本 SKILL/sub-agent-batch-prompt 的判定规则、multimodal/oracle 三源逻辑、R9 类新规则、
     相似度阈值。bump 后旧 pass 缓存整体失效重审（判定变强=自动翻旧案）。递增即可，无需语义化。 -->
PIPELINE_VERSION = pv3   <!-- 单侧化+R9+零tap普查+写单骨架 全就位后的基线版本 -->


> **设备截图/dump 落点纪律（主会话与一切 agent，2026-08-26 客户实报后立规）**：
> 任何 `hdc snapshot_display` / `uitest dumpLayout` / `hdc file recv` 的**本地目标**一律落
> `spec/visual-verify/screenshots/adhoc/<page>__<tag>_<HHMMSS>.jpeg`（dump 配套同名 `.json`；
> 命名对齐 check_replay.py 现行形态），**禁止 recv 到项目根目录**——recv 的默认目标就是 cwd，
> 手写命令不带路径必污染客户工程。排查结束：有留存价值的移入对应 round 目录，其余删除。
> 收口时 `check_scratch_pollution.py` 会对项目根做卫生检查并点名清单。

## 0. Context Discipline（HARD-GATE，进入任何阶段前必遵守）

<HARD-GATE>
本 skill 历史上出过 **上下文压缩事故**（同时 Read 大 SKILL.md + 大 fact-tree + 业务文件触顶）。八条**强制行为铁律**（标题即铁律，完整说明+例子+历史教训见 [`references/context-discipline.md`](references/context-discipline.md)，存疑时读它）：

- **0.1 禁 Read `spec/toolkit-fact-tree.json`**：它给脚本吃。要页面队列只读 `build_page_queue.py` 产的 `page_queue.json`；要某页详情用 python 一行式/`grep` 取片段（例：`python3 -c "import json;t=json.load(open('spec/toolkit-fact-tree.json'));print([p for p in t['pages'] if p['id']=='<page_id>'])"`）。
- **0.2 reference 按需 Read，不预加载**：SKILL.md 保持精简（< 400 行）；references 仅对应 phase 用到时才 Read，禁一上来并行全读。
- **0.3 大文件走 script 不走 Read**：> 200 行的 JSON/spec 先用 python 脚本/一行式处理写小中间文件再 Read；progress.json 写小补丁不整读整写。
- **0.4 主会话禁 Read 截图（绝对铁律）**：永不 Read `screenshots/**/*.{png,jpeg,jpg}`。多模态读图整体外包 batch sub-agent。主会话只读 page_queue/batches.json、manifest.json、ui/*.md。唯一例外：用户明确要求抽检 ≤3 张。违反 = 回到 v2 爆栈失败模式，整轮判失败。
- **0.5 markdown schema 100% 合规**：写第一个 markdown 前必 Read [`fix-file-schema.md`](references/fix-file-schema.md) 一次（禁凭记忆猜）；写完即跑 §十 自检，连续 3 个错 → 停写退出。
- **0.6/0.7 截图命名 + reset_app**：路径分 `{trip_id}` 目录（trip_1_logged_out / trip_2_logged_in_vip）避免双态互覆盖；reset（★单侧化 2026-07-12：Phase 4 只 reset HMOS）trip 边界=主会话 `aa force-stop && bm clean -d -n` 后重建态，batch 内 sub-agent 只许 `aa force-stop`（清数据会抹掉 trip 态）。详 [`output-layout.md`](references/output-layout.md) + [`phase4-navigation.md`](references/phase4-navigation.md)。
- **0.8 一次 Agent dispatch = 一个 batch**：`next_batch.py` → (需要则先跑 `run_scenario_with_verify.py` **仅 harmonyos**——安卓真值已录制，Phase 4 不驱动安卓；禁直跑 scenario_run.py) → dispatch 1 个 batch → `mark_batch_done.py` → 下一轮。progress.json 是 SSOT。**scenario 退出码路由表 + 门禁功能对照实验铁律**（登录/上传等前置失败默认按功能退化判 P0，不默认归因环境）→ 见 [`phase4-dispatch.md`](references/phase4-dispatch.md) 末尾，**升级用户前必读**。

</HARD-GATE>

---

## 1. 定位

**独立自闭环的视觉/功能对齐验证器**：两端模拟器逐页 capture + multimodal diff → 写 markdown 到 `spec/fix/round-N/{ui,feat}/`（UI 差异落 `ui/`；功能维度 dual-oracle 差异落 `feat/`，kind=IMPL_MISSING；均遵守 [`fix-file-schema.md`](references/fix-file-schema.md)）→ Phase 6 末尾主动派 visual-fixer 修代码（本 skill 专属 agent，按 `fixer_layer` 覆盖 ui/feat/resource 三层）→ Phase 6.5 `round_budget.py` 自持轮次循环直至收敛或预算用尽。本 skill 自身不动 .ets。**单独调用即完整闭环**（验→修→重编重装→再验），不依赖任何编排器；也可被 a2h-verify CHECK-7 / arkts-spec-evolver / a2h-device-smoke 等作为调用方触发，统一走 §5 的调用方契约。

**前置树生产**：统一委托 `android-fact-tree` 调度器——它确定性判架构（XML / Compose / 混合）→ 分发到对应生成器（传统=`toolkit-fact-indexer`+`app-relationship-tree` / Compose=`compose-fact-tree` / 混合=两者叠加缝合）→ 自带产出闸 → 产物 `spec/toolkit-fact-tree.json`（三态字段同构）。Phase 1 Step 1.0 在 gate FAIL 时自动调用。本 skill 不直接关心架构，只要一棵就绪的树。

**a2h-spec 产物补齐**（同一自闭环模板）：Step 1.1.f 探针发现 a2h-spec 产物**整体缺失**（`spec/baseline/` 的 page_*.md 与 feature spec 双缺 = 从没跑过）时，自动调 `$a2h-spec` 补齐后复跑探针；只自动调一次，仍缺则按降级模式继续。部分缺失不触发（已跑过的 spec 不整重跑），只在维度表里降级告知。

### 职责分工

| 阶段 | 谁来做 | 产出 |
|---|---|---|
| 探测 / 队列 / 可达性 / batches.json | **主会话** | `page_queue.json` + `batches.json` |
| 单 batch scenario + 截图 + 多模态 + 写 markdown + 类内 systemic | **batch sub-agent**（独立 200K 上下文，5-10 页/batch） | `spec/fix/round-N/{ui,feat}/*.md`（UI 差异→ui/；功能维度 dual-oracle→feat/）+ `batches/{batch}/manifest.json` |
| 跨 batch systemic 聚类（只读 manifest，不读图） | **主会话** | `_systemic/SYSTEMIC_*.md` |
| _index / _summary / _delta / _state.yaml + 自检 | **主会话** | `spec/fix/round-N/_*.md` |
| 读 markdown + sbs 多模态诊断 + 修 .ets（ui+feat+resource 三层全包） | **visual-fixer agent**（Phase 6 末尾主动派，不调 a2h-fixer，feat 层不许默认转出） | 代码改动 |
| 决定下一轮 / 维护 current_round | **本 skill 自持**（`scripts/round_budget.py`，每次调用默认 3 轮）；a2h-verify 编排时也不必干预 | 轮次推进 + 收敛判定 |

主会话**永远不 Read 截图**（§0.4），只读 manifest（< 5KB/batch）+ markdown 文字。本 skill 只做 "scan + 产 markdown + 跨类聚类 + 派 visual-fixer"，不维护修复规则 / ArkUI 速查表 —— 那些归 visual-fixer。

```
本 skill 单 run：Phase 1 (探测/queue/可达性) → 2 (安卓基线，含 2.5 grounding，已完备则跳过)
              → 3 (round-N 骨架) → 3.5 (batches.json) → 4 (batch sub-agent 派发循环)
              → 5 (跨 batch systemic) → 6 (汇总+自检+派 visual-fixer)
Android 基线跨 round 复用（screenshots/android 该页 png 已存在即不重截）；HMOS 永远重截。
```

---

## 1.1 100% 对齐铁律

HMOS 与 Android **100% 视觉一致**为唯一目标，差不多/平台差异 全部不接受。

**关键 4 条**（详 [`alignment-rules.md`](references/alignment-rules.md)）：
1. **Differential test**（★单侧化 2026-07-12：安卓侧不再现场截，改查 Phase 2 录制档）：判 "page 不可达" 前必须 ①HMOS 实截一次 ②查安卓 baseline/BLOCKED 档 → 4 种状态分类（安卓有 baseline+HMOS 不到 → `page_missing_hmos` P0；安卓侧 BLOCKED（如 promo 挡）→ `android_promo_blocks_baseline`；两端到不同页 → `nav_chain_broken_hmos`；安卓 BLOCKED 且 HMOS 也不到 → 真 `scenario_failed`），禁止懒判 `unreachable` 掩盖 P0 finding
2. **`design_difference` / `platform_difference` / `dynamic_content` 三类降级不许 skill 自动判**，默认 bug，仅 (a) 用户对话明确豁免 (b) HMOS 系统级 UI 无 API 干预证据 (c) Android 源码证明动态随机 三选一才能改类
3. **本 skill 不升级"修不动"**（修不动由 visual-fixer 判断；预算耗尽后是否续跑由调用方按 §5.3 契约决定），仅模拟器/scenario/多模态/自检脚本故障才升级用户
4. **覆盖集恒等：鸿蒙采集集 ≡ 安卓覆盖集（2026-07-25 用户拍板，双向约束）**
   - **下界（安卓 ⊆ 鸿蒙）**：安卓覆盖到的每个页/功能点，鸿蒙一个都不许丢——少一个 = 漏测 P0。
   - **上界（鸿蒙 ⊆ 安卓）**：安卓**没**覆盖的**不强制**覆盖——**没有 GT 就没有判据**，拿鸿蒙截图跟空气比只能产生假 PASS 或纯噪音，不产真单。鸿蒙**多出的组件**由 `structural_diff.py` 的 `extra` → `ALIGN_*_extra_element` 单兜住（结构 oracle 确定性抓，不靠多模态眼力），**不需要**靠"多跑几页"发现。
   - **★覆盖分母的唯一定义（2026-07-25 定死，此前反复取错三次）**：
     ```
     分母 = 该 trip 的安卓 baseline **png 全集**（screenshots/android/<trip>/*.png）
     ```
     **不是** `walk.settles`（那是"计划要结账的"，含安卓自己都没截到的页，如毫秒级瞬态弹窗
     → 要求鸿蒙交付没有 oracle 的页，只产无效缺页单）；
     **也不是** `settles ∩ png`（会漏掉 materialize 出的破坏性变体 `*#via=*`——安卓采到了、
     鸿蒙该交付，只是走收尾趟而非正常趟）。
     一句话：**安卓实际交付了几张图，鸿蒙就欠几张**，一张不多一张不少。
     分子 = 通过**到达门控**的交付（见下条）；`settles − png` 的差额单独记，供回头补采安卓，不计入分母。
   - **★分子的唯一定义：只有通过到达门控的才算交付**。
     截图**存在 ≠ 交付**——文件名对而内容错（截了别的页存成目标页名）比缺图更坏：
     缺图会报缺，假图会让 judge 拿它去比对安卓基线、产出**幻觉差异单**。
     故 `capture()` 必须先验身份（屏签名未被别的节点占用）才允许按目的地命名，
     否则记 `not_arrived` + `actual_node`。这是 [phase4-replay-run.md](references/phase4-replay-run.md) §5
     「未到达绝不按目的地命名，否则截图账本说谎」的机械执行。
     ⚠️ 反面教训：判读制（"只产观察不判对错"）**不豁免身份校验**——"这张图是哪一页"是**事实**不是判定，
     把它一起删掉，账本就开始说谎。
   - **★覆盖是二维的：页覆盖 ∧ 功能点（行为）覆盖，两个分母都要对账（2026-07-25 补，"feat 单太少"追因后定死）**
     ```
     页覆盖    分母 = 该 trip 的安卓 baseline png 全集      分子 = 通过到达门控的交付
     行为覆盖  分母 = 计划全部 reconcile 元素               分子 = 真产生 behavior_observation 的元素
              （真值源 = 安卓 functional_checks + grounding_results）
     ```
     **页交付了 ≠ 页上的功能点验过了。** 反面教训：一轮实测页覆盖报"全绿"，
     行为覆盖却只有 **36/82 = 43%**，而 feat 单的素材**只能来自行为观察** —— 于是 ui 单 42 张、
     feat 单只有 7 张，其中 4 张还是源码静态推断的。**只对账页不对账功能点，等于给自己发了张假合格证。**
     行为覆盖 <1.0 一律按**漏测**处理（`assert_replay_artifacts.py` cond 4 卡死），
     欠账逐元素列名（`functional_coverage.gaps[].unobserved`），补跑或逐条说明原因，**不许静默通过**。
     ⚠️ `not_found` / `noop` **也是观察**，计入分子——它们恰恰是最可能出 P0 feat 单的那类。
   - **★每张截图必须配 dump（与安卓侧对齐）；失败现场也要留**。dump 不是可选附件，它是
     **归因的唯一证据**：没有失败现场的 dump，「app 缺控件」「我们没定位到」「handler 没实装」
     三者分不清，judge 只能猜。三分判据见
     [phase4-replay-judge.md §6](references/phase4-replay-judge.md)：
     点了没反应=`handler_not_implemented`(P0，**纯 UI 对比永远抓不到**) /
     控件不在 dump=`control_missing_in_hmos`(P0) / 控件在 dump 却没点到=`locator_failed`
     (**我们的工具缺陷，绝不出产品单**——否则是拿自己的 bug 冤枉被测物)。
     **机械兑现**：回放执行器有且只有一个落盘口 `_shot(name, txt)`（图 `X.jpeg` ↔ dump `X.hmos.json`
     同名配对），**禁止直接调 `drv.screencap()`**。反面教训：规约写在这儿一整轮，实现却只在
     11 个截图点里的 1 个兑现（60 张图 / 20 份 dump），照样"通过"——**没有机械闸的规约等于没有规约**，
     故 `assert_replay_artifacts.py` cond 2/6 卡死配对率。
   - **★产物必须落 canonical 布局，工作区不是交付位**（详 [`output-layout.md`](references/output-layout.md)）。
     回放跑完必须 `replay_place_artifacts.py` 摆位 + `assert_replay_artifacts.py` 验齐才准进判定。
     反面教训：回放自建目录约定，canonical `screenshots/harmony/round-1/` 里躺的是上一次页粒度采集的
     陈图，本轮真货只住在回放私有目录；`screenshots/sbs/` 近乎空，judge 出单时**在 markdown 里把
     evidence 路径改指回放目录绕了过去**——**下游一绕，缺陷就静默存活一整轮**。
   - **∴ 采集集必须抄安卓账，不许从树重推**：`build_batches.py` 主数据源 = 安卓 Phase 2 `phase2_batches/*/manifest.json`（trip 归属 + 分批一起抄），GT 判据 = **baseline png 存在性**（最硬，不是命名/preconditions 启发式）。仅在无 Phase 2 产物（纯鸿蒙项目）时才退回 `classify_trip()` 从树推。⚠️ 从树重推的历史事故：同项目 trip_1 树推 45 页 vs 安卓实跑 13 页，多出 29 页全无 GT；且「暧昧→双态都跑」把 trip_2 的页复制进 trip_1，分母虚高覆盖率虚低，还与闸（用 `_trip_assignment.json`）口径分裂 → **闸绿不代表采集有对照物**。
   - **"安卓没有"必须二分,禁止静默滑坡**：(a) 安卓**真没有**（该功能不存在/登出态真不可达）→ 合法出界；(b) 安卓**漏采了**（BLOCKED / trip 分派错 / 跑一半断）→ 是**债**不是"不用测"，记 `_baseline_debt.json` + `_hmos_queue_excluded.json`（status=`blocked` 为债须补采，`skipped_structural` 为声明式不可达合法出界），**债未清 ≠ 收敛**。把 (b) 当 (a) 会形成自我掩盖的反馈环——安卓越跑不动，鸿蒙测得越少，报告越绿。
   - **危险 ≠ 豁免**："危险 / 不可截"是**方法约束，不是覆盖豁免**。某节点无法安全截图（破坏性结果页：进页即执行不可逆操作、且安卓侧本就无 baseline）→ 覆盖**下沉到父页 `functional_check`**（B.4.5 deferred_destructive：遭遇→读 handler→末尾安全验，到弹窗即止**绝不点确定/确认/是**），记 `deferred_to_functional`，**绝不写"排除 / forbidden"**（把方法约束当覆盖豁免 = 吞掉迁移 bug）。路由 tree 驱动、机械化在 `build_batches.py`（入边全资金不可逆 + 无基线 → 出截图队列，挂父页功能点，产 `_destructive_deferred.json`）：父页也在破坏墙后 = 安卓无真值 → 合法出界；父页可截却缺 check = 真 grounding 债须补。判据同 [`phase4-replay-hmos-destructive-profile.md`](references/phase4-replay-hmos-destructive-profile.md)。

---

## 2. 前置条件

执行前必须验证以下条件，任何一项不满足则中止并提示用户：

| 条件 | 验证命令 | 失败提示 |
|------|---------|---------|
| adb 可用 | `python3 $SKILLS_ROOT/arkts-visual-verify/scripts/lib_tools.py`（打印真实 adb 路径；env `ADB` > PATH > 平台候选）| "请安装 Android SDK 并确保 adb 在 PATH 中" |
| hdc 可用 | 同上 `lib_tools.py`（env `HDC` > PATH > 平台候选；Windows 见 windows-setup.md）| "请安装 HarmonyOS SDK 并确保 hdc 在 PATH 中" |
| Android 模拟器运行中 | `adb devices`（输出除表头外至少一行 device）| **自动启动**（详见 phase1-prepare.md Step 1.1），失败再升级用户 |
| HarmonyOS 模拟器运行中 | `hdc list targets` | **自动启动**，失败再升级用户 |
| Android APK 已安装 | `adb shell pm list packages {package}`（pm 自带过滤，无需管道）| 自动 install，失败再升级 |
| HarmonyOS HAP 已安装 | `hdc shell bm dump -n {bundleName}` | 自动 install，失败再升级 |
| `toolkit-fact-tree.json` **完备**（不是存在检查）| `python3 $SKILLS_ROOT/arkts-visual-verify/scripts/check_prereq_freshness.py spec/toolkit-fact-tree.json --source <android_src>` exit 0（**--source 必带**：gate 判定本身依架构而变——compose/混合树合法 purpose=null，缺 --source 会被按 traditional 误判 NEED）| exit 2 → **调 `$android-fact-tree`**（指向 `<android_src>`；调度器自动判架构 → 调对应生成器 → 自带产出闸），跑完再跑一次 gate 确认 PASS。**本 skill 不挑生成器、不看 NEED 后缀**——树生产全权委托调度器；详见 [phase1-prepare.md Step 1.0](references/phase1-prepare.md) |
| 多模态模型可用 | 尝试读取一张图片 | "当前环境不支持多模态，无法执行视觉对比" |

> **hdc 路径备注**：DevEco Studio 自带 hdc 通常位于 `/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains/hdc`（Windows：`C:\Program Files\Huawei\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe`）；脚本内一律由 `scripts/lib_tools.find_hdc()` 定位（env `HDC` > PATH > 平台候选），手工执行时把该路径设为 env `HDC` 或加入 PATH（bash: `export HDC=...`；PowerShell: `$env:HDC="..."`）。
>
> **hdc 连接备注**：远程模拟器需要先连接：`hdc tconn 127.0.0.1:5557`。

---

## 3. 输入与输出

### 3.1 输入路径

| 输入 | 来源 | 说明 |
|------|------|------|
| `toolkit-fact-tree.json` | `spec/toolkit-fact-tree.json` | **首选**页面清单 + 导航关系 + 功能依赖图 |
| `feature-index.md` | `spec/baseline/feature-index.md` | 备选，当 toolkit-fact-tree.json 不存在时使用 |
| `page_scenarios.json` | `spec/visual-verify/page_scenarios.json` | 用户维护：page→scenario 映射 |
| `app.json5` | HarmonyOS 项目 | bundleName |
| `AndroidManifest.xml` | Android 项目 | package 名 + Activity 列表 |
| `progress.json` | `spec/visual-verify/progress.json` | 验证进度（如存在则断点续跑） |
| `_state.yaml` | `spec/fix/_state.yaml` | 拿当前全局 round 号 N + 本次调用的轮次预算（`invocation` 段） |

**调用参数**（唯一一个；其余输入全走文件路径）：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--budget N` | `3` | 本次调用最多推进几轮。传给 `round_budget.py begin`。多次调用**自由累计**（第 2 次从上次终点续起，预算重新起算），无全局天花板。 |

> **调用方映射**：`arkts-spec-evolver` 调本 skill 时传的 `retry_policy.max_rounds`（其
> `references/workflow.md:478`，默认也是 3）**就是这个参数**。此前本 skill 从未声明过
> `retry_policy`，那个值一直传进空气里；同时它判定表 (B)「视觉验证失败但已达 max_rounds」
> 等的终态信号也从不产出——是条双向断链，2026-08-11 修复。
> 现在 `round_budget.py end` 会打印机器可 grep 的 `VERDICT: BUDGET_EXHAUSTED |
> CLEAN_AT_EXIT | OPEN_REMAIN`，(B) 分支认 `BUDGET_EXHAUSTED`。

### 3.2 输出路径

**关键产物**（按重要性）：

| 产物 | 路径 | 说明 |
|---|---|---|
| 差异 markdown | UI: `spec/fix/round-N/ui/{ALIGN\|URL\|CRASH}_*.md`<br>功能(dual-oracle): `spec/fix/round-N/feat/*.md`（kind=IMPL_MISSING） | ★ 主交付，给 visual-fixer 用（按 fixer_layer 分流修） |
| 轮次汇总 | `spec/fix/round-N/_index.md` / `_summary.md` / `_delta.md` | 给人类 + 调用方（§5.3）用 |
| 状态更新 | `spec/fix/_state.yaml`（仅 last_verifier_results.visual-verify 段） | |
| 人类报告 | `spec/visual-verify/report.md` | 人类速览 |
| 内部状态 | `spec/visual-verify/progress.json` | 断点续跑 |
| 截图 | Android: `screenshots/android/{trip_id}/<id>.png`（跨轮，按 trip）<br>HMOS: `screenshots/harmony/round-N/{trip_id}/<id>.jpeg`（按轮+按 trip）<br>sbs: `screenshots/sbs/round-N/{trip_id}/<id>.jpeg`（按轮+按 trip） | HMOS+sbs 按轮归档不覆盖；Android baseline 跨轮复用；双端均按 trip 分目录避免双态页互覆盖 |
| **分类计划** | `spec/visual-verify/batches.json` | 主会话生成；sub-agent 派发依据 |
| **batch manifest** | `spec/visual-verify/batches/{batch_id}/manifest.json` | sub-agent 回填；主会话 Phase 5 / Phase 6 唯一可读来源 |
| **孤儿 dialog 清单** | `spec/visual-verify/orphan_dialogs.md` | 人工调研缺失触发条件的 dialog/fragment；`build_orphan_dialogs_doc.py` 产 |

**batch manifest schema**（每个 batch sub-agent 退出前必须落盘）：
```jsonc
{
  "batch_id": "home_main_tab",
  "current_round": 2,
  "started_at": "...", "finished_at": "...",
  "duration_seconds": 420,
  "scenario_chain": ["login"],
  "scenario_results": [
    {"scenario":"login","device":"harmonyos","success":true,"duration_ms":12500}
  ],
  "pages_status": {
    "HomeActivity": {"status":"fail","similarity":0.10,"high":1,"medium":0,"low":0,
                     "elapsed":{"scenario":12,"nav":38,"capture":9,"compare":95,"functional":140,"edges":60,"write":20},  // ★必填计时账单(2026-07-10),validate 警告缺失
                     "fix_files":["spec/fix/round-2/ui/ALIGN_P0001_..."]},
    "FragmentRecommend": {"status":"pass","similarity":0.94,...}
  },
  "findings": [          // 跨 batch 聚类用，每条 ≤ 200B
    {"page_id":"P0001","kind":"ALIGNMENT_DIFF","category_pattern":"missing_navheader",
     "severity":"P0","fix_file":"spec/fix/round-2/ui/ALIGN_P0001_missing_element_navheader.md"},
    // B.4.5 同页对账 fold 掉的条目带 folded_into（被 feat 单吸收）；Phase 5 聚类 + _summary 计数跳过
    {"page_id":"P0002","kind":"ALIGNMENT_DIFF","category_pattern":"text_mismatch",
     "severity":"P1","fix_file":null,"folded_into":"MineSetting_03_refund_oneclick"}
  ],
  "systemic_candidates": [  // sub-agent 自己已写的类内 SYSTEMIC
    {"pattern":"missing_navheader","affects":["P0001","P0003","P0005"],
     "local_systemic_file":"spec/fix/round-2/ui/_systemic/SYSTEMIC_home_main_tab_missing_navheader.md"}
  ]
}
```

**完整路径规约 + 生命周期 + 清理时机 + 跨 skill 接口**：见 [`references/output-layout.md`](references/output-layout.md)。

> **写盘前必读 output-layout.md**——所有读写位置都是契约，绕开规约写到别处会污染下游消费者。

---

## 4. 执行流程（骨架）

> 本节只给 phase 骨架 + 进入时机；每个 phase 的执行细则在对应 reference 文件里。**真正进入某 phase 之前**再 Read 那份 reference。

### Phase 2 — Android 全量基线（v4 主模式：边粒度行走；页粒度 dispatcher 降为补漏兜底）

> **★ 遍历模型统一（2026-07-25 用户拍板，读本节前先看这条）**：
> **两个 trip 都走边遍历，鸿蒙侧一律一笔画回放；页粒度只在"边遍历到不了"时兜底**（双端同规则）。
> （此前 trip_1 为何是"边粒度的特例"、为何鸿蒙侧掉回慢路径：见 [`rationale-log.md`](references/rationale-log.md) §遍历模型统一）
> 2026-09-09 晚起主会话编排由 `scripts/next_walk.py` 驱动（页粒度 `next_batch.py` 的边遍历对应物；每次调用输出下一步动作，见 phase2-edge-walk §3 开头）。
> 现已统一：`walk_0_first_launch`（trip_1，`reset_before: pm_clear`）+ `walk_1_main`（trip_2），
> 首启门发 `kind="wizard_step"` 边（**PRIO 最前**：门一次性消费，任何边不得插队），
> 回位 = `coldstart` + 重放前缀（不是 BACK，`one_way: true`），连败落 `needs_pagegranular_fallback`。
> **安卓侧实际动作一步不变**，变的是步序落成了 `walk_plan.json`。
> trip 作用域取自 `_trip_assignment.json`（单一事实源），**中转枢纽**（如 HomeActivity 被分派为
> trip_2-only 但 trip_1 必须途经）可 tap 但不结 capture 账（记 `transit_only`）；
> **中转只许走 `safety=="normal"` 的边**——绝不为了够到下游而途经破坏性页。

**★ v4 主模式 = 边粒度行走（edge-walk，2026-07-15；分工轴修订 2026-07-16）**：`plan_edge_walk.py` 从树确定性产出行走计划（DFS 步序+双闸哨兵+安全分级）→ **sub-agent 编排**按计划一次冷启走全图，每条边 tap 进→**三账合一**（capture 截图 + 节点普查 `node_sweep` 批量结 grounding+blackbox + 边真值）→ BACK 回，**跑完必须收尾**：`walk_finalize.py --trip <trip>` 一条命令串完三账反哺（继承→writeback 树/负面证据只标注不删边→materialize 黑盒账→落位基线→自检闸），exit 20 = 有真值没落地。同项目 A/B 实测：冷启 31→1、产出 57 条边真值（页粒度结构上为 0）、grounding 质量持平。

> **★ 走完 ≠ 落地（2026-07-17 事故，实录见 [`rationale-log.md`](references/rationale-log.md) §走完≠落地）**：**收尾必须是机械的，不能是自觉的**——所以有了 `walk_finalize.py`，别拆回成几条独立命令。`walk_ledger.py status --tree <t> --trip <trip>` 现在会查收尾账并报红。

> **分工轴铁律**：**LLM 编排 + 机械批处理**——机械化的边界是「确定性」。编排（决定下一步/撞事恢复）归 LLM，批处理已知的事（node_sweep 一次扫全节点元素、回放已确认路径、记账/反哺/落位）归脚本。对照实验：LLM 编排跑完 20 节点，脚本编排（walk_exec 全量）5 节点就断——真实页面的普查逃逸（元素启动外部 app / 选中即消费的页 / BACK 过冲）会反复打断 DFS 位置，脚本 exit 后需从零重建现场，LLM 在上下文里直接处理则进程不断。**3 倍杠杆来自 node_sweep 的批处理，不来自机械编排**；`walk_exec.py` 降级为「二轮/已确认路段的快速回放器」。

执行细则、工具、铁律、已知坑（含普查逃逸三形态 + 创作流雷区判据）全在 [`references/phase2-edge-walk.md`](references/phase2-edge-walk.md)——**进入 Phase 2 先读它**；本节下方的 dispatcher 模式仅在补漏/单页重采时使用（判据见该文档 §8）。⛔ **不存在"整体回退页粒度"**（2026-08-12 混合铁律）：计划盖到的节点（含 ⚠needs_discovery 投机节点）一律走边遍历，只有 coverage_gap/确认孤儿/行走 unreached 落账的才由 dispatcher 兜底；投机占比高的治本是补树（ART 带下钻），不是降级。

---

**Phase 2 trip 态建立（边遍历主模式 / 页粒度兜底两模式共用；`phase2-edge-walk.md` §2 指向这里）**

```text
# 2. 【每个 trip 起始，仅一次】建 trip 态 —— 边界真跑即验证（v2026-07-10c 删除了原"就绪态预检"
#    独立环节，四条理由见 references/rationale-log.md §trip 态预检删除）。状态一律"撞到才学"
#    （at-need 派 builder）；已知残留=state_required 空态静默采集，页级检查另项处理）：
#    a. trip 边界 pm clear 归零（建立 trip_1 未登录 / trip_2 待登录的干净起点）
#       adb -s <ANDROID_SERIAL> shell pm clear <pkg>
#    b. 首启门链一次过（**仅 trip_2**，2026-07-10 修正）：门链是"一次同意即持久"的一次性门，
#       过一次本 trip 内 force-stop 冷启不再弹——省掉 sub-agent 每页重过门链的最大浪费源
#       （trip_2 的 per-page 只 force-stop 不 clear）。
#       有 first_launch_gate 配方 → 跑之；**无配方 → 当场派 scenario-builder 合成**（树
#       precondition_recipe 带源码锚点，合成分钟级、不是盲探）；builder 报 NEED_* 才允许退化为
#       "sub-agent 每页现场过门"，且必须在 progress.json 记 warning，不许静默退化。
#       ⚠️ trip_1 **不在边界过门**——D 分派后 trip_1 人口≈门链页本身，过门=消费首启态毁其可达性。
#       trip_1 由 chunk sub-agent **链式连采**（一次 pm clear 顺链采全，见
#       phase2-android-batch-prompt Step 1.-1），边界只做 a 的归零。
#    c. trip_2 额外跑 login scenario 到登录态
#       ★ 顺序铁律（2026-09-09）：trip_1 的全部 walk 结清之后才跑 login；后端登录态常不可逆（mock 实证），
#         登录后再派 trip_1 walk 执行器直接拒（exit 3）。login 包装脚本成功即机械打点 android_walk_timeline.jsonl。
#       ★ 边遍历模式分支（2026-09-09 晚复核定稿）：**trip_2 边界不 pm clear、不过门链**——walk_0 已把首启门消费掉，
#         其终态（门已过、未登录）天然就是「待登录的干净起点」，直接跑 login；再 pm clear 会重新武装首启门（无门配方即撞死）
#         且清不掉后端登录态。上面 a/b 的「trip_2 边界 clear + 过门」只适用于页粒度模式。next_walk.py 按此实现。
#         收尾链趟（walk_6，finalize 5.8 排）是散文 §5 明许的登录后 pm clear 回走（本地门标记随 clear 复位），带 order_exempt 豁免顺序闸。
#    ★b/c 跑 scenario 一律走包装脚本（与 Phase 4 同一铁律，**建态/造态**禁直跑 scenario_run.py
#      ——裸跑丢失败计数与机械分诊。豁免=verify_outcome.py 判定与 builder 学习验收：它们是
#      嵌入引擎消费者，失败是判定数据不是要自修的故障，见 runner §9 划界）：
#      python3 $SKILLS_ROOT/arkts-visual-verify/scripts/run_scenario_with_verify.py \
#          <scenario> android --trip <trip> --device-id <ANDROID_SERIAL> --package <pkg>
#      （--trip 跨平台；bash 也可写 env 前缀 `TRIP_ID=<trip> python3 ...`，PowerShell 无此写法，用 --trip）
#      exit code 机械路由（同 phase4-dispatch.md 末尾表，升级用户前必过门禁对照实验铁律）：
#      0=继续 / 10=派 scenario-builder 学·修，learned 后重跑本脚本 / 20=升级用户建凭据档 /
#      30|40|50=**必跑 scripts/gate_experiment.py（对照实验执行器）**，按 verdict 机械分支
#      （functional_regression=写 P0 单禁升级环境；升级用户必附 GATE_EXPERIMENT_JSON，缺=无效）。**配方文件不存在 → 不算失败，直接派 builder 学**（等价 10 路由）。
#    ⚠️ trip-scoped 门控：本 trip 态未建成前，禁派本 trip 的任何 chunk；**不阻塞另一 trip**
#      （trip_1 不需要登录态——登录缺凭据只冻结 trip_2，trip_1 照常开采）。

# 2.5 数据态阶梯 checkpoint（2026-07-10 ③，派 chunk 前跑；"trip 边界建态"模式向下复制一级）：
#    对即将派发的 chunk：python 读树取出其页面的 preconditions[].kind=="state_required" 条目（含 data_hint）。
#    对每个 state（**按 (trip, device) 分键**——Phase 2 device=android，与 phase4-dispatch 0.b
#    的 harmonyos 键互不冒充；progress.json.states_provisioned 已 green 的秒过）：
#    · 有配方（progress.json 记过 check/create 名）→ 跑 check（包装脚本）→ 红 → create **造一次**
#      → progress.json 记 green + 配方名（它就是注册表，页级自愈梯从这里读名字）
#    · 无配方 → 派 scenario-builder（prompt 带 data_hint + unblocks）学 check/create 双配方
#      → builder 返回配方名 → create 造态 → 记 green。builder 报 NEED_HUMAN_FIXTURE → 冻结
#      **仅含该 state 页面**的采集（BLOCKED 占位），其余页照跑——不整体卡死。
#    经济性：create 多为消耗型（烧账号次数，铁律 10 禁例行重放）——checkpoint 保证每 trip 只造一次；
#    正确性兜底：checkpoint 之后态中途蒸发由 sub-agent 页级空态检查+自愈梯接（batch prompt 1.3.9）。
```

**页粒度 dispatcher 模式（v3.11，兜底：补漏 / 单页重采 / 行走 unreached 归因熔断漏采）**：架构、已知结构性缺陷、职责分工、
触发条件、主会话执行步骤 0/1/3/4、BLOCKED schema 与 reason 路由表、产物——全部在
[`references/phase2-page-dispatcher.md`](references/phase2-page-dispatcher.md)（2026-09-07 自本节迁出，正文逐字未改）。
**加载时机是机械的，不靠记忆**：`dispatch_phase2_batches.py --plan-only` 的 stderr 会点名该文件必读；
`check_android_screenshot.py` 的 reason 路由兜底文案指向它。何时进兜底的判据见 phase2-edge-walk.md §8。

**Phase 2.5 — 功能点 grounding（条件触发，dual-oracle 上游）**：若 fact-tree 某 page 带 `functional_checks[]`（a2h-functional-merge 注入），填 `expected_android` / `android_trusted` / `precondition`，作为下游鸿蒙判定的可信真值。**边粒度主模式下本步已并入行走**（三账合一：与导航边重合的 check 由行走那一下 tap 顺路结账，原地类走固化执行器 `ground_page_checks.py` 机械批跑+一次批判，实测 11s/条 vs 逐条交错 35s/条，见 phase2-edge-walk.md §5）；仅页粒度兜底补采时才按 [`references/phase2.5-grounding.md`](references/phase2.5-grounding.md) 的逐条流程做。判定标准（结构指纹自验/事务型 verify_outcome/破坏性到弹窗即止）两模式共用，均以 phase2.5-grounding.md 为准。

> **详见**
> - [`references/phase2-page-dispatcher.md`](references/phase2-page-dispatcher.md) 页粒度 dispatcher 兜底模式全文（架构/步骤/BLOCKED schema）
> - [`references/phase2-android-batch-prompt.md`](references/phase2-android-batch-prompt.md) sub-agent prompt 模板
> - [`references/android-navigation-playbook.md`](references/android-navigation-playbook.md) 公共导航 playbook
> - [`scripts/dispatch_phase2_batches.py`](scripts/dispatch_phase2_batches.py) chunk 切分 + 计划输出
> - [`scripts/run_phase2_android_survey.py`](scripts/run_phase2_android_survey.py) trip 编排外壳（v3.11 重构为 dispatcher 入口）

### Phase 1 — 准备

Step 1.0 **跑内容门控脚本** `check_prereq_freshness.py spec/toolkit-fact-tree.json --source <android_src>`（**--source 必带**——gate 判定本身依架构变：compose/混合树合法 purpose=null，缺 --source 会被当 traditional 误判 NEED，导致合法树永远过不了 Step 1.0）：
- PASS → **再跑功能维度门控**（补结构闸盲区）：`check_functional_dimension.py spec/toolkit-fact-tree.json <hmos_project>`——结构闸不看 `functional_checks`，结构完整但功能空的树会静默漏测（B.4.5 dual-oracle 不发生且不报错）。exit 2(NEED:functional-*) → **同样调 `$android-fact-tree`**（其 §3.5 自产 registry→注入→机械闸，XML/Compose 自动分流）→ 复跑本闸确认 OK；exit 0 → 进 Step 1.0.5。（防无限重触发：用 registry 文件存在性当"已尝试"标记，纯 UI/无功能点项目恒 OK。）
- 任一 NEED → **调 `$android-fact-tree`**（统一树调度器，指向 `<android_src>`）：它自动判架构（XML/Compose/混合）→ 分发到对应生成器（传统=toolkit-fact-indexer+app-relationship-tree / Compose=compose-fact-tree / 混合=两者叠加缝合）→ 自带产出闸。跑完再跑一次本 gate（同样带 --source）确认 PASS → 进 Step 1.0.5。
  > 本 skill **不再自己判架构、不手挑/串生成器、不看 NEED 后缀**——那是调度器的职责。visual-verify 只「要一棵就绪的树」（且只负责把 `--source` 传对让 gate 判得准），怎么产交给 android-fact-tree。这样 Compose/混合架构应用也自动支持（旧写死 toolkit+ART 链对 Compose 会产空树）。

Step 1.0.5 **反哺 anchors** `enrich_factree_anchors.py`：从 `spec/baseline/ui/page_*.md` 的 `android_source_anchors` YAML 段读出 Android 源路径写回 `fact-tree.pages[].android_source_refs`。**不跑这一步，工单 §1 全部退化为"Android 源参考缺失"，fixer 凭眼测改色（实测 41% 工单是这种情况）**。

→ Step 1.1 验证前置（含自动启动模拟器 + 1.1.d **新鲜检查**——Phase 6.8 fix 后置构建打过戳则秒过、无戳才重编，构建失败自动接 `$hmos-fix-build-errors` 修到出包 + **1.1.f 三级探针** `check_dimension_prereqs.py`：UNIT 级缺失 fail-fast、OPTIONAL 级降级第一屏告知、**a2h-spec 产物整体缺失时自动调 `$a2h-spec` 补齐**（exit 3，只自动调一次，仍缺则降级；部分缺失不触发），详 [`phase1-prepare.md`](references/phase1-prepare.md)）→ Step 1.2 构建 page_queue → Step 1.2.5 可达性预分类 → Step 1.3 创建输出目录 / progress.json。

> **三条不能跳的红线**：
> 1. 不要凭"上次跑过应该有 fact-tree"心算跳过 Step 1.0 —— 必须真跑 gate
> 2. gate FAIL 时不要自己挑生成器 / 不要按 `NEED:xxx` 后缀手动只调一个 —— 统一调 `$android-fact-tree`，让调度器判架构 + 路由 + 自检（它内部对三态各有写死链路 + 闸）
> 3. 不要 subprocess 调 Python 脚本绕过 Skill 工具 —— 会丢调度器/生成器的内部质量门和自愈循环

> **详见** [`references/phase1-prepare.md`](references/phase1-prepare.md)

### Phase 3 — round-N 骨架 + Android 缓存

准备 `spec/fix/round-N/` 目录 + carry-forward 上一轮 disposition。

> **详见** [`references/phase3-skeleton.md`](references/phase3-skeleton.md)

### Phase 3.5 — 按"类别 + 共享 scenario"分组 → batches.json

把 page_queue 切成 7-9 个高内聚 batch，每个 5-10 页共享 scenario_chain（[login] / [login, upload_image] 等）。

> **★建批前先生成 category_pattern 映射表（2026-09-07 N3-b，<1 s，纯脚本）**：
> `python3 $SKILLS_ROOT/arkts-visual-verify/scripts/build_pattern_vocab.py --shots-dir spec/visual-verify/screenshots/android --out spec/visual-verify/category-patterns.json`
> 从 Phase 2 安卓 dump 扫 resource-id → 概念（navheader.back / progress_indicator / tab_bar …）。judge 出单时骨架据此**自动推导**
> `category_pattern = <diff_kind>__<concept>`，不再由 judge 起名；`needs_confirm` 只记录不使用（不确定的不聚，宁多勿漏）。
> 文件缺失也能跑（词典兜底），但有它 rid 命中更准。

> **入口前可选优化：baseline 别名折叠（2026-07-13，Fitness 实证省 ~18% 页次/round）**：Phase 2 完成后跑 `scripts/build_baseline_aliases.py`，把"同一运行时屏幕的多个 node"（Activity 宿主壳/host_default fragment 对、主题皮肤变体等）折叠成 canonical+alias（**双钥匙缺一不折**：结构/来源证据 + 像素确认；全黑 hw_surface 伪影不参与）。产物 `spec/visual-verify/baseline_aliases.json`，build_batches 自动消费（alias 不进 HMOS 队列，fix 单/对比结果归 canonical，_index 注明继承）。**铁律：只许遍历后折叠（证据折叠）**——遍历前按结构推断折叠会误伤（主题激活方向要运行时才知道、tab/子tab 灰区、alias 不采集则折错永不暴露）；脚本输入即截图与 manifest，结构上自我强制此时序。

> **HARD-GATE（v3.10 / v3.12 / v3.13 三维度）**：`build_batches.py` 入口现在**机械强制**三道就绪度闸——不再靠 SKILL.md 散文提醒 agent 自觉跑。**站点共享**（都在此入口）、**信号分离**（独立退出码 + 维度自报，各维度绝不互相误判）：
> - **UI 维度**：`check_android_screenshot.py`——Android baseline 两 trip 任一 trip 覆盖率 < 90% 即 fail
>   - trip_2 失败但 trip_1 OK → **仍然 fail**（典型信号是 login scenario 没调通，必须读 Android 源码 + 看 scenario log + 改 login.yaml selector 修，详 stderr 指引）
>   - BLOCKED 占位文件不计入覆盖率（避免"login 全挂"伪装成"trip_2 完成"）——**合法不可达 BLOCKED
>     （data_precondition_missing 等 fixture / structurally_unreachable 声明式预判）除外**，脚本按 reason 区分，与此一致
> - **功能维度（v3.12 新增，堵"feat 生产段静默跳过"）**：`check_functional_dimension.py`——A2H 项目树里 `functional_checks` 为空（registry 未产 / merge 未注入）即 fail。以前这道闸只在 Step 1.0 散文里靠 agent 自觉，忘了就带空 feat 树纯 UI 开跑（已发生真实漏测）；现在焊进 build_batches 入口兜底。纯 UI 项目经 android-fact-tree §3.5 产空 registry → 合法放行，零误伤
> - **黑盒证据维度（v3.13 新增，堵"Step 1.6 黑盒探索静默跳过"）**：`check_blackbox_evidence.py`——**每个 chunk manifest（两 trip 都查，2026-07-10 起 1.6 每页在其分派 trip 跑）**必须带 `blackbox_stats`（即使全零），缺字段 = Step 1.6 未执行即 fail；stats 声称有发现但 `blackbox_discoveries/` 为空 = 不一致亦 fail。以前黑盒只在 prompt 散文里，出现过整轮静默未跑零报错（aippt_vvSpeed 2026-07 run）；现在焊进 build_batches 入口 + dispatch Post-step 警告双锚点。"跑了但零发现"（stats 全零）合法放行——机械区分"没跑"与"没发现"
> - **退出码语义**：`40`=UI 基线缺 / `41`=功能维度缺 / `42`=UI+功能双缺 / `43`=黑盒证据缺 / `44`=黑盒证据不一致（读码即知补哪维——41 去补 registry+merge 不是补截图；43/44 去补跑 Step 1.6）
> - 跳过开关仅限调试：`--skip-baseline-check`（UI）/ `--skip-functional-check`（功能）/ `--skip-blackbox-check`（黑盒，仅限"页面清单已人工穷尽核对"的显式豁免），正常流程禁用
> 配合 `capture_or_reuse.py harmony` 入口的同一 gate，构成 Phase 4 HMOS 操作的双保险。

> **详见** [`references/batch-classification.md`](references/batch-classification.md)（含 §9 执行入口）

### Phase 4 — batch sub-agent 派发循环

主会话只调度，每个 batch 派一个 sub-agent 进独立上下文跑批内全部页面。sub-agent 完成后回 manifest.json，主会话**不读截图**只读 manifest。

> **★prompt 机械渲染（2026-09-07 起，主会话禁手工填槽）**：
> ```bash
> python3 $SKILLS_ROOT/arkts-visual-verify/scripts/fill_batch_prompt.py --batch-id <id> --round <N> \
>     --hmos-target <t> --hmos-bundle <b> --hmos-ability <a> --android-serial <s> --android-pkg <p> \
>     [--blocked-pages '<JSON>'] [--retry-edges '<JSON>'] [--b-gaps '<JSON>']   # exit≠0 禁退回手工拼
> ```
> 它按**批内页种类**从 fact-tree 机械判定，只把用得着的条件段（Compose 导航 / B.0.5 反哺页 / B.0.6 dialog /
> B.1 数据态 / B.4.5 双 oracle，原文在 `references/batch-sections/`）注入 `sub-agent-batch-prompt.md`，其余留一行省略说明；
> 同时写 `batches/<id>/prompt_manifest.json` 凭证。**加载可靠性不靠自觉**：`validate_batch_output.py` 事后按树独立复算
> "该注入的段"与凭证对账，缺凭证/缺段 = `prompt_sections` FAIL（judge 角色走 J2 另一套 prompt，不在此闸）。

> **页粒度 = 保底，不是主路（2026-07-25 用户拍板）**：鸿蒙侧覆盖主路是**边 / 一笔画 replay**（与安卓 Phase 2 边遍历对称，见 [`phase4-replay-run.md`](references/phase4-replay-run.md)）；本节页粒度批派发是"replay 够不着 / 未覆盖页"的**兜底**。**保底不降级安全**——页粒度**必须继承边遍历的破坏性下沉路由**：破坏性结果页（进页即执行不可逆操作 / 无安卓基线）由 `build_batches.py` **自动移出截图队列、覆盖下沉父页功能点**（`_destructive_deferred.json`，见 §1.1 第 4 条覆盖完整性铁律），**不盲进、不丢弃**；页内撞破坏性控件**到弹窗即止，绝不点确定/确认/是**（B.4.5 deferred_destructive）。

> **★ 一笔画回放的固定五步（2026-07-25 定死，缺一步都算没跑完）**——详见
> [`phase4-replay-run.md`](references/phase4-replay-run.md) §4 / [`phase4-replay-judge.md`](references/phase4-replay-judge.md) J0–J1.5：
> ```
> ① compile_replay_plan.py     产计划（含无锚点 reconcile 补发：安卓有真值就必有承载步）
> ② replay_exec.py             跑（每图配 dump；reconcile 到页即结账；回位失败先重导航）
> ③ replay_place_artifacts.py  ★落位：replay/<run>/ 是工作区，canonical 布局才是交付位
> ④ assert_replay_artifacts.py ★闸：覆盖 ≡ 安卓 png 全集 / 图配 dump / sbs 齐 / 行为覆盖=1.0
> ⑤ build_judge_input.py       组判定包（--trip 必填，sbs 落 canonical）
> ⑤′ slice_judge_input.py      ★按负载切成 K 包、一包一个 judge 并派（J1.8；包数随 app 规模变，无"每包 N 页"常量）
> ⑥ judge 返回后 merge_judge_packets（K 份 notes → batch_notes，包齐闸）→ build_batch_manifest → batches/round-N/ + mark_batch_done   ★落 Phase 5/6 与 cond 1 读的账（J2.5）
> ```
> **跳过 ③ 下游全瞎，跳过 ④ 漏测当通过，跳过 ⑥ 聚类/汇总读到 0 份 manifest、整轮闸 cond 1 必红（0913 干跑实爆）。**（③④ 是 2026-07-25 补的；补齐前的后果实录见 [`rationale-log.md`](references/rationale-log.md) §一笔画五步）

> **详见** [`references/phase4-dispatch.md`](references/phase4-dispatch.md)（主会话调度）
> + [`references/sub-agent-batch-prompt.md`](references/sub-agent-batch-prompt.md)（sub-agent prompt 模板）

#### sub-agent 内部执行手册（Step 4.-1 ~ 4.5）

| Step | 主题 | 详见 |
|---|---|---|
| 4.-1 | scenario 准备 | [`references/phase4-scenario.md`](references/phase4-scenario.md) |
| 4.0 / 4.0.a | 导航 + 启动弹窗速关 | [`references/phase4-navigation.md`](references/phase4-navigation.md) |
| 4.1 / 4.1.2 / 4.1.5 | 截图主流程 + capture_mode 判定 + 崩溃检测 | [`references/phase4-capture.md`](references/phase4-capture.md) |
| 4.1.3 | 长页分段截图与拼接 | [`references/phase4-long-page.md`](references/phase4-long-page.md) |
| 4.1.4 | H5 / WebView 三段式验证 | [`references/phase4-webview.md`](references/phase4-webview.md) |
| 4.2 | 多模态对比 | [`references/phase4-multimodal.md`](references/phase4-multimodal.md) |
| 4.2.5 | **功能点双 oracle 判定**（条件:该 page 有 functional_checks）→ 产 feat 单 | [`sub-agent-batch-prompt.md`](references/sub-agent-batch-prompt.md) B.4.5 段 |
| 4.3 / 4.4 / 4.5 | 差异分类 + 写 markdown + 单页收尾 | [`references/phase4-classify-write.md`](references/phase4-classify-write.md) |
| B.7 / Phase C | **判断账每页落 `page_status.py`（做完才 `--done`，脚本核验）；manifest 由 `build_batch_manifest.py` 拼并反查；重派用 `fill_batch_prompt.py --resume` 只重做未完成页（2026-09-07）** | [`sub-agent-batch-prompt.md`](references/sub-agent-batch-prompt.md) B.7 / Phase C |

> **功能维度(dual-oracle)**:B.4.5 仅当 fact-tree page 带 `functional_checks[]` 时跑——鸿蒙实操功能点,按 `android_trusted` 用 `expected_android`(主,Phase 2.5 grounding 产)/ `expected_llm`(保底)判,产 `spec/fix/round-N/feat/` 单。纯 UI 项目无此步。
>
> **`functional_checks` 谁注入(接线,v6.8)**:由 `a2h-functional-merge` 注入,触发**不在本 skill**——`android-fact-tree` 出口契约 §3.5 已固化"产树后查契约路径 `spec/a2h/functional_registry.json`,**不存在则无条件自产**(XML/混合 → `$a2h-functional-registry` 读全源码+census 提取,锚点=真 resource-id;纯 Compose → `compose_registry_from_tree.py` 从树投影) → 接续 a2h-functional-merge 注入 → 机械闸验功能点入树"。所以 Step 1.0 `$android-fact-tree` 跑完,树就**已带** functional_checks(纯 UI 项目 registry 近空、注 0,合法),本 skill 直接消费即可,**不需自己调 registry/merge**。⚠️ 若 registry 存在但树里 functional_checks 为空 → 说明 android-fact-tree §3.5 接续漏跑,应回 android-fact-tree 补,**不要默默当纯 UI 项目跳过**。
>
> **registry 契约路径(固定)**:`a2h-functional-merge` **只从 `<hmos_project>/spec/a2h/{functional_registry,test_intents}.json` 读**,`a2h-functional-registry` 自产的产物也**只写这里**(单一契约路径,不"任意位置"搜——避免 workspace 多份 registry 摸错弱版/过期版);`--src-root` 安卓源根仍每次调用时声明(不进契约)。**功能维度零前置准备**——Step 1.0 跑 android-fact-tree 即可,registry 缺失由其 §3.5 自产补齐;契约路径已有 registry 则直接消费不重产,需强制重产时删掉这两份文件再跑。

### Phase 5 — 跨 batch systemic 聚类

主会话先跑 `cluster_systemic_candidates.py --round N` 拿机械候选簇（A：同完整键 high/medium ≥3 页；A2：同部位概念跨 diff_kind、仅 high；low/other 只列 unclustered 不聚——不确定的不聚，宁多勿漏），只对候选判同根因，写 cross-batch SYSTEMIC markdown，回填命中 ALIGN 的 `systemic_root` 字段。

> **详见** [`references/phase5-systemic.md`](references/phase5-systemic.md)

### Phase 6 — 汇总 + 自检 + 派 visual-fixer + 派 reviewer + 退出

按 4 步顺序（**机械化兜底**，详 §6）：

0. **★证据通道闸（派 fixer 之前必跑，2026-08-29 新增）**：
   ```text
   python3 $SKILLS_ROOT/arkts-visual-verify/scripts/assert_evidence_channel.py <项目根> <N>
   # exit 0 = 放行（SIDE_CHANNEL_HEAVY 只 WARN）/ exit 30 = EVIDENCE_BYPASSED → **停在这里**
   ```
   exit 30 = 本轮 canonical 采集**一张都没有**、工作全落在 `screenshots/adhoc/` 调试通道。
   adhoc 不进覆盖账、不合 sbs、不进判定 ⇒ **本轮没有任何可判定的新证据**：
   **不得派 fixer、不得给任何单定 disposition 终态、不得推进轮次计数**。
   先修主路（多半是上游门禁/登录/启动链），或把已有 adhoc 证据回灌落位后重跑本闸。
   > **为什么放在派 fixer 之前而不是 6.4**：判断力从来不缺，缺的是它亮在派发之前（2026-08-29 round-6 实录与数据见 [`rationale-log.md`](references/rationale-log.md) §证据通道闸）。

1. 写 _index.md / _summary.md / _delta.md / 更新 _state.yaml —— 三份文件**由 `render_round_summary.py --round N` 机械渲染**（2026-09-07），模型只填 `_summary.md`「人工补充」段
2. **跑机械化整轮兜底**（任一 fail 不许进 Phase 7）：
   ```bash
   python3 $SKILLS_ROOT/arkts-visual-verify/scripts/assert_run_success.py ${N}
   # exit 0 = PASS / exit 1 = recoverable（补救后重跑）/ exit 2 = unrecoverable 升级用户
   python3 $SKILLS_ROOT/arkts-visual-verify/scripts/check_scratch_pollution.py . --archive
   # 卫生自动归档（不依赖自觉）：项目根散落截图/dump → 自动移入 adhoc/archived-<mmdd>/ 并打印清单
   ```
3. PASS 后主动派 visual-fixer 闭环修复（Step 6.6）。
4. **fixer return 后主会话接着派 visual-fixer-reviewer 反摸鱼质检**（Step 6.7，2026-08-04 新增），
   过硬闸（attempts>0 则 reviewer report 必须存在且含 `## flag` 段，缺则 exit 1 禁止收轮）
   → 把 flag 落到 summary → 写人类报告 report.md。
   ⚠️ **reviewer 不由 visual-fixer 自派**——它的 tools 白名单无子代理派发权（不能调 `spawn_agent`），旧设计让它自派，
   结构上派不出且只留一行警告，反摸鱼闭环整轮空转。派发权在主会话，别改回去。

> **详见** [`references/phase6-summary.md`](references/phase6-summary.md)

### Phase 7 — 顽固 finding 集中冲刺（条件触发）

扫描域 **`ui/` + `feat/` 两层**（2026-08-29 实录：登录与模板两张最顽固的单都在 `feat/`，
原条款只扫 `ui/`，**功能类顽固单在设计上就享受不到集中冲刺**）。满足下列**任一**即判顽固，
移入 `spec/fix/stubborn/<id>/`：

1. §6 已 ≥ 3 个 attempt 且 disposition 仍未 fixed；
2. **跨轮次 ≥ 3 且仍 open**——不论 attempt 数（★治"卡得越死越不被升级"的反向激励：
   到不了页面 → 没人试 → attempt 不涨 → 永远 <3 → 永远不触发冲刺 → 继续到不了页面。
   实录：模板单跨 round-4/5/6 仍 open，attempt 只有 2，够不着原门槛）；
3. **连续 2 轮标 `blocked_by_*`**（到不了页/前置未就绪/上游阻断）→ **直接标 `manual_review`
   并在报告里点名阻断源，不进 mini-round**——这类单需要的是**解除上游阻断**，不是再修一遍本页。
   实录：模板单连续两轮 `blocked_by_startup_gate`，真正该修的是启动门（登录身份字段被回滚
   导致 `guestInitialized` 永不成立），在模板页本身打转永远无解。

判顽固后：对每条最多跑 5 轮 mini-round（单页截图+多模态+focused visual-fixer），
通过则回流原目录标 `partial`，5 轮失败则标 `manual_review` 升级用户。主流程在此 phase 暂停。

> **详见** [`references/phase7-stubborn-loop.md`](references/phase7-stubborn-loop.md)

### Phase 6.4 — 整轮硬闸（**必跑；不跑它，6.5 会直接拒绝给结论**）

> **为什么新增**（2026-08-16 事故）：此前 `assert_replay_artifacts.py` 会正确报红
> （实测 round-6：缺 13 页、欠 70 条行为、`exit=1`），但 `round_budget.py` **根本不读它**；
> 而缺页写成 `disposition: pending_upstream_fix` 就不算 open —— **缺页越多，账面越干净**。
> 于是 trip1 三轮没跑、trip2 只交付 6/20，照样 `open=0` → `CLEAN_AT_EXIT` → 报告"闭环完成"。
> 规则一直写在文档里（本 skill 5 处白纸黑字"红了=漏测，不许当通过"），**但没有一处是机械依赖**。
> 这就是本项目反复犯的病：**机械问题降级成自觉**。Phase 6.4 是自觉的终点。

```text
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/assert_round_complete.py <项目根> <N> \
    --trip-out trip_1_logged_out=<该 trip 本轮 replay 产物目录> \
    --trip-out trip_2_logged_in_vip=<该 trip 本轮 replay 产物目录>
#   0  ALIGNMENT_CLEAN        两 trip 全交付、行为全覆盖、无 open
#   10 ALIGNMENT_HAS_FINDINGS 执行完整，有产品差异
#   11 ACCOUNTED_WITH_DEBT    执行完整、缺口都出单，但债未清
#   20 ROUND_INCOMPLETE       缺 trip / 缺产物
#   21 GAP_UNTICKETED         缺页没被合法认领（含分类未举证）
#   22 STALE_ARTIFACTS        用了上一轮产物
```

三条不可协商的语义：

1. **`expected_trips` 由脚本从安卓基线目录实时枚举**，禁止写死、禁止继承上一轮。
   安卓有几个 trip，本轮鸿蒙就必须有几个——trip1 三轮没跑正是因为从没有人算过这个数。
2. **某个 trip 没给 `--trip-out` = 该 trip 没跑**，不是"可以省略"。
3. 它产 `spec/fix/round-N/_run_state.json` —— 这是 6.5 与 6.9 的**唯一事实源**（路径定义在 `lib_resolve_round.py`，写入端与两个读取端都走它；旧项目落在 `spec/visual-verify/round-N/run_state.json`，读取端只读回落）。

缺页出单的判据（由 `assert_gap_ticket_coverage.py` 机械执行，见 [`references/fix-file-schema.md`]）：

| 鸿蒙源码状态（`resolve_hmos_impl.py` 实时解析） | 允许 `is_migration_bug: false` 吗 |
|---|---|
| `absent` 无任何对位实现 | ❌ **绝不允许**——这就是迁移缺陷本身，必须出 P0 |
| `present` 有实现且注册了路由 | ✅ 但单里必须写 `hmos_impl:` 指认实现 |
| `ambiguous` 只有模糊/内联候选 | ⚠️ 必须写 `not_migration_evidence:` 显式举证，**不许写 unknown** |

> ★ **判"不是迁移缺陷"的依据绝不能是"我没到达"** —— 那是循环论证，"没到达"恰恰是待证明的东西。
> round-6 的 13 张 BLOCKED 单全是这个形态；实测其中 AccountInfo / ManageRenew / MemberCenter
> 手动 3 次点击即到达，源码和路由都在。

### Phase 6.5 — 轮次预算闸（**自持循环的唯一出口，必跑**）

Phase 6.4 结束后跑，**按退出码路由，禁止自行判断"是不是该再来一轮"**：

```text
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/round_budget.py next
#   0  → 已自增 current_round，**回到 Phase 1** 开下一轮
#        （fixer 的改动已在 Step 6.8 fix 后置构建上了设备并打戳，
#         Phase 1.1.d --skip-if-fresh 见戳秒过；若 6.8 没走到（会话中断等），
#         1.1.d 无戳会兜底重编——两个锚点保证任何路径下截图前包都新鲜）
#  10  → 本次调用预算用尽（默认 3 轮），收尾退出，并告知用户：
#        "再次调用本 skill 可从 round-{X} 续跑"
#  11  → CONVERGED（**仅当显式加了 --early-exit-on-clean 才可能返回**）
#   2  → 状态异常，升级用户
```

> **为什么默认不因 `open==0` 提前收敛**（2026-08-11 决策，勿轻易反转）：
> 两种退出的失败模式不对称——「跑满预算」失败只是费时间，**显性**；
> 「open==0 提前退出」失败是**漏检假阴性**：模型没识别出问题 → 判为收敛 →
> 看起来成功、实际遗留一堆问题，**静默**且会误导下游门控。
> 宁可多跑两轮，也不接受一次静默的假收敛。
> `open` 计数仍每轮打印、仍进结论行，但它是**诊断信息，不是控制流**。
>
> 相应地，**`open=0` 不可直接当作 PASS 上报**——它只说明「本轮没报出问题」，
> 漏检同样呈现为 0。结论必须结合 `_summary.md` 的实际比对页数一起看。

进入 Phase 1 之前（整个 skill 最开始）必须先跑一次 `round_budget.py begin [--budget N]`，
退出前跑 `round_budget.py end` —— 它打印**终态信号**与**进展判定**，两者都要转述给用户：

```
VERDICT: BUDGET_EXHAUSTED          # 机器可 grep，spec-evolver 判定表 (B) 认这个
◼ 本次调用结论：跑了 3/3 轮（round-0..2），最后一轮 open=5  [null=5]
  open 轨迹：12 → 9 → 5
  ✅ 本次有进展（open 12 → 5），若仍有 open 建议继续调用
```

进展判定三态（纯诊断，不参与控制流）：**有进展** → 建议继续调用；
**停滞**（最近 2 轮 open 持平且 >0）→ 提示先查 `_delta.md` 与各 finding 的 §6 尝试史，
判断是不是撞上平台差异/私仓黑盒这类修不动的项；**回升** → 提示查 regressed 段。
累计调用是手动的，「要不要再调一次」是用户的决策 —— 这几行就是给他的判断依据。

**为什么是差值预算而不是绝对上限**：`begin` 把进入那一刻的 `current_round` 冻结为
`started_at_round`，判据是 `current_round - started_at_round + 1 < budget`。
所以「每次调用最多 3 轮」与「多次调用可累计到 6、9 更多」是同一个算式的两面——
第二次调用的起点自然是上次的终点，预算重新起算。
**不需要、也不该再写一条「允许累计」的规则**：写在散文里的规则没有约束力，
这里的约束力来自退出码。

---

## 5. 门控与调用方契约

### 5.1 自身执行断言（run success）

```
visual-verify 单 run 的成功条件（全部满足才算 success）:
  1. Phase 1 / 2 全跑完（队列里每页都到达过 Step 4.4 或 Step 4.1.5 blocked）
  2. spec/fix/round-N/{ui,feat}/ 下所有差异都已写成 markdown（UI→ui/；功能 dual-oracle→feat/）
  3. _index.md / _summary.md / _state.yaml 已落盘
  4. round-N ≥ 1 时 _delta.md 已落盘
  5. schema §十 自检脚本通过（exit 0）

任一不满足 → 视为 visual-verify run failed，按 alignment-rules.md §3 升级用户。
```

### 5.2 终态契约（standalone 下这就是完整答案）

本次调用结束时（Phase 6.5 `round_budget.py end`），本 skill 给出**完备的机械终态**，不依赖任何外部裁决：

```
VERDICT: BUDGET_EXHAUSTED | CLEAN_AT_EXIT | OPEN_REMAIN   ← round_budget.py end 打印
ROUND_STATE: ROUND_UNVERIFIED | ROUND_INCOMPLETE | STALE_ARTIFACTS
           | GAP_UNTICKETED | OPEN_FINDINGS | ACCOUNTED_WITH_DEBT | ALIGNMENT_CLEAN
           ↑ 同上，精确态。**`CLEAN_AT_EXIT` 现在需三条同时成立**：
             open==0 且 debt==0 且 Phase 6.4 整轮闸 == ALIGNMENT_CLEAN。
             （旧逻辑只看 open==0 —— 而覆盖没做完时 open 必然为 0，
               "没测到"和"没问题"在账面上完全同形，这就是 round 4-6 假收敛的成因。）
+ 轮次轨迹（跑了 M/budget 轮，open 计数逐轮轨迹）
+ 进展三态诊断（有进展 / 停滞 / 回升，见 Phase 6.5）
+ spec/fix/round-N/_summary.md（页面维度明细）
+ spec/visual-verify/report.md（人类可读总览，含收敛段）
```

**单独调用时，用户拿到以上即闭环**：还有 open → 再调一次（差值预算天然累计 3→6→9），
或按停滞诊断转人工。**本 skill 不出业务层 PASS/FAIL/PARTIAL**——"是否对齐到可交付"
是调用方基于终态契约的**再解释**，不是本 skill 的出口条件。

### 5.3 调用方契约（a2h-verify / spec-evolver / device-smoke 等统一入口）

| 方向 | 内容 |
|---|---|
| 入参 | `--budget N`（可选，默认 3；spec-evolver 的 `retry_policy.max_rounds` 映射到此） |
| 出参 | §5.2 终态契约全量（VERDICT + `_summary.md` + report.md） |
| 状态 | `_state.yaml` 轮次字段**只读**（`current_round` 仅用于定位 `round-N/` 目录）；禁止写入 |
| 续跑 | 想再跑 = 直接再调一次本 skill；**不要**自增轮号、**不要**代跑 fixer（Phase 6 已内置） |

> 例：a2h-verify CHECK-7 读 VERDICT——`CLEAN_AT_EXIT` 映射 PASS、`OPEN_REMAIN`/`BUDGET_EXHAUSTED`
> 且无进展映射 FAIL、有进展则再调。在本 skill 眼里，standalone 的用户与编排器是**同一种调用方**。

---

## 6. 与 visual-fixer 的内置闭环

Phase 6 写完 markdown + _summary + _delta 后**主动派 visual-fixer**（本 skill 专属 agent，不调通用 a2h-fixer），处理**所有 fixer_layer**（ui / feat / resource 三层全包），仅真修不动（OG-03 私仓黑盒 / OS API 缺失 / 需后端配合）才按 alignment-rules.md §3 升级用户。

关键约束：
- 本 skill **自持修复循环**（每次调用默认 3 轮，`round_budget.py` 机械判定；见 §Phase 6.5）；**不删旧 round-(N-1)/**
- **fix 后必须顺利出包才算过**（Step 6.8 构建锚点，2026-08-12）：派 fixer 前清新鲜戳 → fixer 落盘 → 立即重编+重装+打戳；构建失败自动调 `$hmos-fix-build-errors` 修到出包（每构建点最多一次），修不动才升级用户。下一轮 Phase 1.1.d 见戳秒过——每个 fix 批次恰好编译一次
- **disposition 字段 fixer 不写**，仅 verifier（下轮）能写 `fixed`；未收口 finding 由 Phase 3 `carry_forward.py` **原名结转**（文件名恒 = id，结转轮次记在 frontmatter `carried_rounds`）
- **§6 "尝试过的修复方案" 追加式**：fixer 改完必追加 `### round-{N} attempt`，下轮 fixer 必读 §6 历史，假设根因+改动摘要不可与历史雷同（详 [`fix-file-schema.md`](references/fix-file-schema.md) §六）
- Phase 7 顽固 finding（≥3 attempts 仍未 fixed）→ 5 轮 mini-round 冲刺（详 [`phase7-stubborn-loop.md`](references/phase7-stubborn-loop.md)）

Phase 6 收尾派 visual-fixer 详见 [`phase6-summary.md`](references/phase6-summary.md)。

---

## 7. 命令速查 + 设备自动化铁律

hdc / adb 全部命令、坐标获取规范、5 条设备自动化铁律（含截图 ≤1800px / 系统进程可 dump / 坐标是物理像素 / 防熄屏 / aa dump 取证）—— **Phase 4 真要敲命令前**再 Read [`references/cli-cheatsheet.md`](references/cli-cheatsheet.md)。

---

## 8. 使用示例

```
用户: 截图对比一下
用户: 视觉验证
用户: 检查 UI 一致性
用户: 对比一下迁移前后的效果
用户: 跑一下视觉对比
用户: 你觉得这个页面和安卓差多少
```

---

## 9. Android 基线复用策略

Android 基线只在 Phase 2 截一次：`screenshots/android/{trip_id}/{page_id}.png` 存在即跨 round 直接复用（同时跳过 Android 端 scenario 准备）；HarmonyOS 每轮重截。强制全量重截 = `run_phase2_android_survey.py --invalidate-android-cache`（清空 screenshots/android）；单页重截 = 删该页 png 后重跑 Phase 2 补图。

---

## 10. 局限性

完整局限清单（登录墙 / 数据依赖 / 长页拼接 / H5/WebView / 动态内容 / 平台设计差异 等十余条）—— 被质疑"为什么不处理 X"时 Read [`references/limitations.md`](references/limitations.md)。

## 11. 完整链路（端到端）

详见 [`references/e2e-pipeline.md`](references/e2e-pipeline.md)。

用户全链路只需做的事：
1. 启动两个模拟器（Phase 1.1 也能自动拉起）；APK/HAP 由 `scripts/auto_install_artifacts.py` 自动找已构建产物安装
2. **一次性**建凭证档：`scenario_run.py --save-creds --device <android|harmonyos> --package <pkg> --phone <手机号> --code <万能码>`（仅写 `creds.local.json`，**与端无关、不实跑 login、不驱动设备**；两端账号不同就各存一份）。迁移产物已带 `spec/baseline/dev_info.json`（契约参考文件）时，手机号/万能码可直接从中取值建档，这步免人工
3. 说"跑视觉对比"

> ⚠️ **顺序铁律**：login scenario 的**首次实跑必落在安卓**（Phase 2 trip_2 基线），**绝不**先 `--device harmonyos` 实跑 login——那是越过 Phase 2 安卓基线（对齐真值）的越序。录凭证用上面 step 2 的 `--save-creds`（不驱动设备）即可，不需要先在 HMOS 实跑一遍。HMOS 端任何 scenario 都被 `run_scenario_with_verify.py` 的顺序闸（exit 60）拦在"安卓全量基线完成"之后。

---

## 12. 架构总览

核心策略：fact-tree 当有向图遍历 + 真实点击（非 am-start 直跳）+ Android 基准侧先点验 + HMOS 被测侧真点 + 失败 edge 阻塞子树 + 2 趟分态（logged_out / logged_in_vip）。性能 ~60 min/round。完整设计见 [`references/architecture.md`](references/architecture.md)。
