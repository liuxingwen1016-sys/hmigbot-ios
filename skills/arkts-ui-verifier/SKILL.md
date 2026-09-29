---
name: arkts-ui-verifier
description: "以 iOS 源码为主要行为依据、UI Spec 为参考，为鸿蒙可见页面设计、生成并执行 ArkXTest UiTest， 以黑盒方式验证页面是否能沿真实用户路径到达，以及页面功能是否产生可观察的 UI 结果。 适用于“从 spec 生成 UI 测试”“验证页面功能/导航”“统计 UI 验收通过率”“运行 UI RED/GREEN 验证”。 不验证 Repository、Service 等纯逻辑单元行为；这类需求使用 arkts-ut-verifier。"
metadata:
  type: domain
  domain: migration
  tags:
  - verification
  - testing
  - tdd
  - hypium
  - arkxtest
  - uitest
  - UI测试
  - 页面导航
  - 功能验证
---


> **Codex 子代理派发契约（必须遵守）**
>
> Skill 负责主线程编排，四个角色在独立的 `.codex/agents/*.toml` 中定义。
> 使用 `spawn_agent(agent_type="<下表具名角色>", message=...)` 按名派发；
> 不读取/拼接角色 prompt 副本，不用通用 agent 替代；角色未加载则报告安装缺口。
>
> 每次只传本轮任务与输入：`SKILL_ROOT`（实际 skill 绝对目录）、`PROJECT_ROOT`、
> `SOURCE_ROOT`、`PAGE_MAP`（持久化映射绝对路径）、`MAPPING_REVISION`、
> `PAGE_SCOPE`、`EXPECTED_PAGES`、文件 ownership、PHASE/MODE/TEST_SCOPE/FIX_SCOPE、
> ROUND、设备/冻结快照及检查点实值。agent 从 SKILL_ROOT 读 references，不递归编排；
> 项目资料统一在 `spec/verify/ui/`：当前映射/设计在 plan/，报告为 ui-report.md；每轮 evidence/plan-snapshot/ 保存实际输入。
> 可执行测试仍只写 ohosTest；不在验证资料目录维护第二份源码，失败定位区分当前 plan 与只读轮次快照。
> iOS 源码决定行为，UI Spec 为参考，鸿蒙现状决定 locator，普通 Dialog 归宿主页。
>
> | 工作 | 具名角色 | 调度约束 |
> |---|---|---|
> | 设计 | `arkts-ui-test-designer` | PHASE=NAVIGATION 先映射/导航；PHASE=FUNCTION 按页读映射和 iOS 写功能设计 |
> | 导航骨架/注册 | `arkts-ui-test-generator` | MODE=scaffold 后 register + TEST_SCOPE=NAVIGATION；单一共享 owner，完成后冻结导航包输入 |
> | 前期导航 | `arkts-ui-test-executor` | PHASE=NAVIGATION，单设备独占；不等待全部功能设计/测试 |
> | 并行页面编写 | `arkts-ui-test-generator` | MODE=generate；按需最多 8 agent，单 agent 单 PAGE_SCOPE，完成即补位；只写本页 Features.ets/测试 |
> | 最终合并注册 | `arkts-ui-test-generator` | 页面全部完成并复核映射后，单一 owner MODE=journeys，再 register + TEST_SCOPE=ALL |
> | 最终包及功能 | `arkts-ui-test-executor` | 前期导航 PASS 与代码完成两分支 barrier 后 PHASE=FUNCTION；构建安装一次，逐页点击到达/确认标识/业务/清理切换，不再独立全量导航 |
> | 产品修复 | `arkts-ui-fixer` | 显式 MODE 与 FIX_SCOPE 授权；源码/路径变化返回映射更新和受影响草稿 |
>
> 页面编写使用多 agent 队列，MAX_PAGE_AGENTS=8；并发 min(8, 就绪页面数, 可用槽位)，不足 8 不凑数，超过 8 补位覆盖全部页面。
> 并行 designer(FUNCTION) 与 generator(generate) 共用 8 个页面槽位，同页先设计后生成；主线程不批量代写，角色不递归派发。
> 主线程记录各页 owner/映射版本/输出及完成、阻塞、失效状态；共享 scaffold/journeys/register 不做八路并写。
>
> 单设备单一执行者；并行 writer 不操作设备、不改导航 Page Object、support、注册或公共映射。
> 主线程单一 owner 合并映射建议，版本变化后安排相关页面复核。构建/注册前暂停所有输入写入；
> 已安装的导航包可与页面草稿写作并行，但不能一边构建一边修改输入。所有角色保留他人改动。
>
> fix-loop 使用 `spawn_agent(agent_type="arkts-ui-fixer", message=...)`，定义为 `.codex/agents/arkts-ui-fixer.toml`。
> 前期仅在 verify_nav_fix/verify_fix 下修 FIX_SCOPE=NAVIGATION；测试 SETUP 回设计/生成 owner。
> 最终阶段只有 verify_fix 才修 FIX_SCOPE=FUNCTION，必须有本包准入与业务证据；环境问题不交产品 fixer。
> 修复影响源码映射/导航接口时，由主线程更新 revision、复核草稿并按需补工件。前期导航修复后回归；
> 最终阶段修复后构建新包并逐页准入复测，不自动插入独立全量导航。早期包 PASS 不是最终包 PASS。
> 普通页/用例不主动重启；最终包安装、崩溃恢复和生命周期专项按 execution-session-contract 处理。
<!-- codex-ui-dispatch:end -->

# ArkTS UI 功能验证

本 skill 先构建并运行全量导航点击测试、定位并修好到页问题，同时按需派发最多 8 个页面 agent 并发编写功能测试；两侧完成后构建安装最终测试包；随后逐页真实点击进入 → 确认页面标识 → 执行功能用例 → 清理并切换下一页。最终包不再先跑一轮独立的全量导航。普通功能批次不主动重启应用。默认 `verify_only`；要求修到页用 `verify_nav_fix`，额外授权修业务用 `verify_fix`；提交 Git 仍需用户明确要求。

默认采用黑盒边界：测试通过真实 UI 操作驱动应用，并以用户可观察结果判定功能。业务内部状态和测试专用路由状态不作为断言或到页手段。

## 页面范围、源码依据与映射


先按 ios-ui-analyzer 的入口与身份事实盘点页面；普通模态/嵌入 View 归宿主，独立 Tab/全屏目的地按真实可见边界分组。主线程持久化 `spec/verify/ui/plan/page-source-map.json`，保存鸿蒙页面、iOS 源文件/符号/哈希、附属 Dialog、Spec 引用、flow、landmark 和设备证据。分派单页 agent 时传入 `SOURCE_ROOT`、`PAGE_MAP`、`MAPPING_REVISION`；agent 直接读取对应源码，版本失效时复核，不能只读映射摘要。

## 核心契约

本文的“目标 UI surface”指 canonical flow 需要到达并由用户直接看到的目标界面。它可以由被测应用、系统 UI 或系统宿主呈现；`entry_kind` 按真实产品触发链选择，不以最终界面必须落在被测应用进程内为前提。每个可执行 flow 都必须等待该目标 UI surface 的唯一可见 landmark。

### 1. 真实到页

- 对 `IN_APP` 路径，冷启动、重新拉前台和生命周期恢复可以使用 `AbilityDelegator.startAbility()` 等框架能力；它们只负责进入应用声明的正常入口。
- 对 `IN_APP` 路径，进入应用后到目标页的每一跳必须查找真实可见组件、对组件执行用户动作，并等待下一目标 UI surface 的唯一可见 landmark。不得通过测试专用参数、内存状态或内部路由 API 直挂目标页。
- 返回键只有在系统 Back 本身就是用户交互契约时才使用；不得用它绕过产品入口。坐标点击只用于无语义组件可定位的手势类功能，不用于常规页面导航。
- 页面变化后重新查找组件，不缓存跳转前的 `Component`。所有 UiTest 异步调用串行 `await`，同一设备不并发执行 UI suite。
- 每页先产一份 canonical entry flow：`spec/verify/ui/plan/navigation/P{编号}_{PageName}.md`。每一跳都要记录来源 UI surface landmark、操作组件 selector、动作、目标 UI surface 的唯一可见 landmark、等待上限和源码/Spec 依据。

### 2. 到页判定与失败分类

- `waitForComponent(targetLandmark, timeout)` 是到达目标 UI surface 的主判据；landmark 必须在该 surface 上可见并能唯一标识它，不能只用通用 `Column`、重复标题或“应用仍在前台”。
- `waitForIdle()` 可辅助确认界面稳定，但必须检查返回值，且不能替代目标 UI surface 的唯一可见 landmark。
- 设计阶段找不到真实 UI 路径时先区分首因：iOS 源码确认要求该入口但产品缺失，使用 `entry_kind=ENTRY_GAP` 登记导航根缺口，执行阶段静态确认后为 `RED/IMPL_MISSING`；需求本身没有公开 UI 路径/观察面，或现有 UI 在“已有稳定 ID / 唯一可见文本”规则下无法形成唯一可操作、可观察 locator，记 `ERROR/UNREACHABLE_BY_UI` 并转 UT、集成或人工验证。真实入口的账号、应用权限或业务数据契约暂不可用时保留入口类型并记 `ERROR/SETUP`；目标设备、系统测试能力、系统宿主、runner/framework 或明确的目标设备网络基础设施不可用时记 `ERROR/INFRA`；一般网络或服务条件按责任证据判定，不凭“offline”字样固定归类。只有已有 canonical 导航根问题文件（含静态 `ENTRY_GAP`）且因此未执行的下游功能用例才使用 `BLOCKED_BY_NAVIGATION`，不得降级为直挂页面。
- 产品入口、点击行为和目标 UI surface 已由源码与控件树证实存在且可用，但测试 helper 使用了错误/过期 selector、错误作用域、reset 或等待策略时：记 `kind=ERROR`、`failure_class=SETUP`，阻断该页用例，不把页面功能误报为 RED。真实产品点击链或目标 UI surface 的唯一可见 landmark 失败仍按 `RED/NAVIGATION|IMPL_MISSING`。
- 如果“点击某入口并到达目标 UI surface”本身就是业务需求，则把它作为来源页的 `case_kind=PAGE` 单功能点用例，使用来源页的 `P{NNNN}` ID 并放在来源页测试目录；canonical navigation preflight 仍只验证 setup/reachability，不另造第三种业务用例类型。
- 系统入口、deeplink 和跨应用跳转是合法的真实产品入口类型，写入 `entry_kind` 与理由；其 flow 从已证实的真实生产触发上下文开始，不先强制启动默认 Ability，并等待目标 UI surface 的唯一可见 landmark。该 surface 可位于被测应用、系统 UI 或系统宿主，不能笼统要求“进入目标应用”后才判定可达。
- 这些入口类型不豁免组件点击要求：通知、分享入口、外部链接也必须通过真实可见组件触发。公开 URI 只是产品契约，不允许用 shell/Want/接口直接打开目标 URI 或指定业务 Ability 代替点击；没有可复现的可见触发组件时登记不可自动化。只允许以正常默认入口启动应用/外部宿主来建立起点。

### 3. 选择器只复用产品现状

- 已有稳定且唯一的产品组件 `id` 时优先复用该 `id`；没有 `id` 时使用用户在设备上实际可见的文本定位和点击。
- 可见文本必须按当前页面与语言环境校验唯一性；必要时可以组合组件类型或父子/相邻关系缩小范围，但核心点击目标仍由该可见文本确定，不退化为固定坐标。
- 不设计、生成或注入测试 ID，不创建 ID manifest，不因测试修改生产页面、组件、资源或导航实现。已有产品 `id` 只读复用，绝不覆盖或重命名。
- 如果目标既没有可复用的稳定 `id`，也没有能唯一定位的可见文本或关系 selector，则登记 selector gap，并按 `ERROR/UNREACHABLE_BY_UI` 转其他验证方式，不生成猜测式 flow/test。产品已有可用 locator、只是测试写错或过期时才是 `ERROR/SETUP`；真实点击链存在且被正确操作后仍跳转失败，才是 `RED/NAVIGATION`。不得通过修改生产组件绕过。
- 不可自动化只排除受影响需求：canonical 路径或页面 landmark 无法定位才影响整个依赖页面；仅某个业务 action/观察点不可定位时，保留该页 navigation/preflight 和其他可执行功能，只将相关 planned ID 聚合到该页唯一不可自动化记录。

### 4. 一个用例验证一个功能点

- `it()` 的名称、操作和预期必须共同描述一个可观察功能点。一个功能结果可以用多个 UI 断言共同证明，例如“保存成功”同时断言弹窗消失、结果文本更新和按钮状态变化。
- 不按每个顶层组件机械生成 `COMP_*_exists`。静态组件存在性应并入页面可用性或实际功能结果；只有组件本身就是验收对象时才单独成例。
- 菜单项、设置项等仅在行为结果不同、分别对应独立需求时拆分；等价输入与共同结果合并，关键正反路径分别成例。
- 页面用例以功能发起页归属，放到 `entry/src/ohosTest/ets/test/ui/pages/<page_short>/`。所有页面到达 flow/preflight（包括系统、deeplink、跨应用入口）统一放到 `ui/navigation/` 并标入口类型；只有跨多页才完整表达的业务结果放到 `ui/journeys/`。
- 每个业务 journey 由“第一个业务特定动作”所在页唯一拥有：只在该页 `plan/pages/P*.md` 的 §B planned inventory 定义一次，`case_kind=JOURNEY`，稳定用例 ID 继续使用该 owner 页的 `P{NNNN}` 前缀；其他涉及页只引用该 ID，不重复定义。到达业务起点之前的通用 canonical flow/guard 属于 setup，不算业务特定动作。

### 5. 黑盒断言

- 首选断言：目标组件存在/消失、文本、checked/enabled/selected 状态、列表内容或数量、Dialog/Toast 等可观察反馈，以及通过正常 UI 离开并返回或重启后的持久化结果。
- 不把环境准备完成、测试进程正常等 setup 事实当成功能断言。
- 无稳定 UI 可观察结果的纯逻辑行为转 `arkts-ut-verifier`；像素、动画手感或设备人工判断转人工/探索性测试。
- UI 没有稳定可观察结果时转 UT、集成或人工测试；本 skill 不生成内部探针、测试状态注入或替代数据路径。

以上关于目录、逐跳导航与一例一功能点是本 skill 的工程约定，不得描述成 OpenHarmony 官方强制规范。官方能力边界与版本依据见 [references/official-doc-basis.md](references/official-doc-basis.md)。

## 模式

设计、生成、执行和修复开始前均读取 [执行会话契约](references/execution-session-contract.md)，其中统一规定导航门票、两段执行、状态恢复、重启例外与 DEFERRED 记账。

| 模式 | 行为 |
|---|---|
| `verify_only`（默认） | 导航全绿才测功能；门未通过时报告并停止，不修改产品 |
| `verify_nav_fix`（用户要求先修到页） | 修到页问题并全量导航回归，通过后按页测功能；不自动修页内业务 |
| `verify_fix`（用户要求修业务） | 完成前期导航修复与测试编写，再逐页执行并修复业务；新最终包重新做逐页准入，不自动重跑独立全量导航 |

导航产品 RED 由导航修复阶段处理；SETUP 交设计/生成 owner，编译、设备和基础设施问题交对应 owner；blocked/DEFERRED 用例不独立做功能修复。fix-loop 不得通过增加测试专用路由、内部状态镜像或放宽断言制造 GREEN。

## Join 协议（收口五条款）

1. **主动收口**：主线程记录每个实例的唯一任务名、句柄、工作范围、文件所有权和预期产物，使用宿主等待工具持续跟进，并以宿主返回的任务完成状态确认交回。单次等待超时、文件存在或日志静默均不代表完成，不因这些信号终止重派，也不以“等待子代理”为由结束任务。
2. **完成后验收**：任务完成后回读准确产物，核对范围、ID、数量及本阶段契约；完成状态不等于验收通过。失败或句柄失联时先核实实际状态和已保存进度，确认旧实例不能继续写入后才恢复任务，不与原写者重复派发。
3. **按依赖汇合**：每个已完成且验收通过的 Feature/页面可以进入其下一阶段，无需等待无依赖的其它设计；共享注册、构建及设备执行严格遵循本文 barrier、冻结窗口和单一 owner 约束。最终报告前须收口全部本轮任务并对账产物，尚有阻塞时准确报告未完成范围。
4. **继续不等于遗弃**：局部缺口不妨碍独立任务继续，但主线程须持续记录并处理对应任务和恢复条件；不会因暂时放行或用户交互遗忘句柄，也不能以占位文件冒充子代理交付。
5. **派发方负责结果**：本 skill 的角色只执行分配阶段，不递归派发或 fire-and-forget；主线程统一接收、验收和协调返工。并发 owner 不覆盖其他任务或用户的改动；角色未注册时明确报告配置缺口。

## 三步执行模型

| 步骤 | 输入与产出 | 并发边界 | Agent 定义 |
|---|---|---|---|
| 1. 导航预检与并行编写 | designer 的 `PHASE=NAVIGATION` 先产页面映射与导航设计；generator 的 scaffold + register(NAVIGATION) 生成并冻结导航包输入；execute 跑全量导航与问题诊断，同时逐页 designer(FUNCTION) + generator(generate) 编写功能 | 同设备一个执行者；页面生成按需最多 8 agent；页面 owner 互斥；导航运行不等待全部功能设计/生成 | `.codex/agents/arkts-ui-test-designer.toml`、`.codex/agents/arkts-ui-test-generator.toml`、`.codex/agents/arkts-ui-test-executor.toml` |
| 2. 最终包 | 全量导航预检 PASS、所有页面功能草稿及 journey 完成、映射版本复核后，由单一 owner 注册全量测试，再冻结构建安装最终包 | 两分支汇合 barrier；构建期间无人修改输入；不自动再跑独立全量导航 | `.codex/agents/arkts-ui-test-generator.toml`、`.codex/agents/arkts-ui-test-executor.toml` |
| 3. 按页功能执行 | 最终包中每页经真实组件点击到达、确认 landmark，执行本页用例，清理后切换下一页；保存最终包自身的准入与业务结果 | 单设备串行、普通页复用会话，页面到达失败先分诊，不能带病运行业务 | `.codex/agents/arkts-ui-test-executor.toml` |

前期 scaffold 只准备导航必需的 support、Page Object、flow/preflight，不等待全部页内功能。页面 agent 的业务动作写独占 `<PageName>Features.ets`，不改导航使用的 `<PageName>Page.ets` 或公共文件；需要新增共享能力时向单一 owner 提交请求。journey 由 generator 的 `MODE=journeys` 单一 owner 在页面草稿完成后生成。

页面测试生成必须使用多 agent 队列，默认 `MAX_PAGE_AGENTS=8`：并发数为 `min(8, 当前可写的待处理页面数, 当前可用 agent 槽位)`，不是固定凑满 8 个，也不是只生成 8 页。按 SOURCE_CONFIRMED 映射和完成的页设计派发 `MODE=generate`，每个 agent 同一时刻独占一个 `PAGE_SCOPE`；有任务完成即回收/复用槽位，继续派发剩余页面，直到全部处理。设计和生成在同一页顺序交接；若并发派发页面设计，也共享这 8 个页面编写槽位，不能另起 8+8。导航执行者与共享文件 owner 不占页面生成配额，但受运行时总槽位和单设备限制；无可用槽位时排队，不静默退回主线程批量代写。

主线程维护待处理、运行、完成、阻塞、失效队列及每页 owner/输入版本/输出文件；失败或映射失效页回队列复核，阻塞页显式报告，不漏页、不重复写。公共 scaffold、journeys、register、共享映射由单一 owner 串行维护，不能派 8 个 agent 同改这些文件。

已安装的导航包与输入快照固定；后台页面写作不会改变设备正在执行的包。产品修复、共享导航/helper 修改与下一次构建受主线程 barrier 控制，变更需使相关映射/草稿失效并复核。严禁边构建边修改源文件。

每次调度传 `SKILL_ROOT`（实际绝对目录）、`PROJECT_ROOT`、`SOURCE_ROOT`、`PAGE_MAP`、`MAPPING_REVISION`、页面 ownership 和该角色本轮参数。设计/执行的 PHASE 与生成 MODE、验证 MODE 分别传递，不混用。角色从 SKILL_ROOT 读取 references，不递归执行主线程编排。

### Step 1 必读

设计 agent 必须原文读取：

- [references/test-design-template.md](references/test-design-template.md)：页面功能设计与一例一功能点规则。
- [references/navigation-design-template.md](references/navigation-design-template.md)：canonical entry flow、逐跳字段与失败分类。
- [references/official-doc-basis.md](references/official-doc-basis.md)：UiTest 官方能力、版本门禁与本 skill 约定边界。
- [references/test-case-template.md](references/test-case-template.md)：Page Object、selector 与测试生成规则。

### API 版本门禁

设计前先读项目 `build-profile.json5` 中 `compatibleSdkVersion` 与 `targetSdkVersion`。API 9 及以上使用 `Driver`、`ON`、`On`、`Component`；API 8 旧名 `UiDriver`、`BY`、`By`、`UiComponent` 已废弃。任何 matcher、事件观察或输入 API 都必须核对项目 SDK 可用性，不能直接照抄 `master` 文档；截至 2026-09-09，OpenHarmony 6.1 Release 对应 API 23，而 `master` 可能包含 API 26 能力。

## 产物结构

本 skill 的映射、设计、报告与运行账本统一归入 `spec/verify/ui/`；`plan/` 是当前共享计划，`round-N/` 是每轮证据与结果，`ui-report.md` 是当前汇总入口。具体读取/写入边界见 [执行会话契约](references/execution-session-contract.md) 的“统一工作目录”。

```text
<project_root>/
├── spec/verify/ui/
│   ├── plan/
│   │   ├── page-source-map.json
│   │   ├── navigation/P{NNNN}_{PageName}.md
│   │   └── pages/P{NNNN}_{PageName}.md
│   ├── ui-report.md
│   ├── _state.yaml
│   └── round-N/
│       ├── evidence/
│       │   ├── plan-snapshot/       # 本轮实际使用的计划及指纹
│       │   ├── case-inventory.json
│       │   ├── case-outcomes.json
│       │   └── ...                  # 按阶段保存导航/准入、会话、日志等
│       ├── ui/<test-id>.md
│       ├── _ui_index.md
│       ├── _ui_summary.md
│       ├── _ui_delta.md             # ROUND >= 1
│       └── fixer-summary-ui.md      # 本轮调用 fixer 时
└── entry/src/ohosTest/ets/test/
    ├── List.test.ets
    └── ui/
        ├── support/
        ├── navigation/to_<target_short>/
        │   ├── from_<source_short>_<path>.flow.ets
        │   └── <flow_id>.preflight.test.ets
        ├── pages/<page_short>/
        │   ├── <PageName>Page.ets
        │   ├── <PageName>Features.ets
        │   └── P{NNNN}_{PageName}.test.ets
        └── journeys/
```

`spec/baseline/` 与 iOS 源码仍是原位置的输入，不搬进验证目录。可执行 ArkTS 测试只在 `ohosTest` 下维护一份；`spec/verify/ui/` 不存第二份可编辑测试代码，也不生成重复报告或并行计划目录。前期导航与最终功能使用不同 round；两个阶段都写在此统一根下。

注册生成器必须递归扫描 `ui/**/*.test.ets`，再将确定性的显式 import 与 suite 调用静态写入 `List.test.ets`，覆盖 `pages/`、`navigation/` 与 `journeys/`；运行时不使用 glob，helper/page object 文件本身不注册。

## Step 1 设计门槛

每页都要完成：

1. 直接读取映射中的 iOS 源文件及必要调用链，拆分用户可观察功能需求；UI/Feature Spec 辅助追溯并记录差异。
2. 读页面、入口组件、路由注册、守卫、资源字符串和相关共享组件源码，确认真实入口，不只 grep `NavPathStack`。
3. 产 canonical entry flow；每跳 source action 与目标 UI surface 的唯一可见 landmark 都有源码/Spec/运行时界面事实依据。
4. 以需求覆盖设计最小用例集，不以组件树数量凑用例。
5. 每条用例引用 navigation flow，明确页会话准入、逐例 UI 基线准备/清理、离页恢复路径和恢复上限；同页连续执行但不依赖其他用例成功，不逐例重启。
6. 为目标 UI surface landmark、导航 action、功能 action 与结果观察点记录 selector：已有稳定产品 `id` 时复用，否则使用唯一可见文本；无法唯一定位时登记 gap，不修改生产组件补 ID。
7. 对跨页业务结果，在第一个业务特定动作所在页的 §B 以 `case_kind=JOURNEY` 定义唯一 planned 项；稳定 ID 使用该页 `P{NNNN}` 前缀，其他页面只写引用，禁止重复定义。

详细格式见两个 design references 与 test-case template。

## 前置检查

```bash
ls spec/baseline/ui/page_*.md 2>/dev/null | head -1
ls spec/baseline/features/F*.md 2>/dev/null | head -1
rg 'compatibleSdkVersion|targetSdkVersion' build-profile.json5
$HDC list targets
```

iOS 源码或页面映射缺失/有歧义时先补齐；UI Spec 缺失记录参考缺口，不取代源码 oracle。设备检查只在设备执行前强制，导航包就绪即可执行，不等待全部功能测试。

第三步执行还需确认测试签名、设备可用和当前系统要求的 UiTest 运行条件；具体命令以项目 SDK 与 `.codex/agents/arkts-ui-test-executor.toml` 为准，不从框架 `master` 仓库的开发者命令推断应用测试环境。

## 报告口径

- 报告称“UI 验收通过率”或“用例通过率”，除非有真实插桩数据，不称代码覆盖率。
- 失败文件的 `kind` 只能是 `RED | ERROR | BLOCKED_BY_NAVIGATION`，`failure_class` 只能是 `NAVIGATION | SETUP | FUNCTION | INFRA | IMPL_MISSING | UNREACHABLE_BY_UI`。
- 页面功能、实装缺口、被测导航边分别使用 `RED/FUNCTION`、`RED/IMPL_MISSING`、`RED/NAVIGATION`；导航 setup、执行环境、需求本身无公开 UI 路径/观察面或无合法语义 locator 分别使用 `ERROR/SETUP`、`ERROR/INFRA`、`ERROR/UNREACHABLE_BY_UI`。`BLOCKED_BY_NAVIGATION/NAVIGATION` 只用于引用 canonical flow 或静态 `ENTRY_GAP` 导航根问题的下游功能用例。
- outcome 另允许 `DEFERRED`：仅表示因全局导航门关闭、会话不安全或导航成功后用户明确停止而主动暂缓，必须有调度证据，不写产品问题文件、不交 fixer、不计通过。真实导航依赖失败仍用 `BLOCKED_BY_NAVIGATION`，构建/设备故障仍用 ERROR。
- 分母包含设计中应执行的功能用例；`kind=BLOCKED_BY_NAVIGATION`、`kind=ERROR` 以及编译/设备/基础设施错误单列，不当 PASS，也不冒充功能 RED。
- `IMPL_MISSING_STATIC` 保留在 planned 分母中，合成 `RED/IMPL_MISSING` 且 `business_assertions_run=false`；它不计入 GENERATED、REGISTERED 或 EXECUTED，不能通过伪造不可执行测试从分母删除。
- 导航预检与最终包使用不同 round/build，证据不得混用。前期 round 只报告导航与映射进度，功能设计未完整时不编造用例分母；最终 round 引用预检检查点，并独立记录逐页准入和功能结果。
- 有实际测试支撑的失败文件对应一个 `it()`；同一功能点的多个共同断言仍属于同一个失败项。静态 `ENTRY_GAP` 根、其尚未生成的计划 blocked 功能点、`IMPL_MISSING_STATIC` 功能点、`UNREACHABLE_BY_UI` 或全局基础设施根允许 `test_file: null`。

## 导航修复门槛与业务 fix-loop

产品修复角色为 `arkts-ui-fixer`，定义在 `.codex/agents/arkts-ui-fixer.toml`；以下两种 FIX_SCOPE 均调用该角色，并传入 `SKILL_ROOT` 和明确授权的本轮参数。

主线程先派 Step 3 `PHASE=NAVIGATION`。门未通过时先封存本轮结果：`verify_only` 报告并停止；`verify_nav_fix/verify_fix` 仅派发 `FIX_SCOPE=NAVIGATION` 的产品 fixer，测试侧 SETUP 则回设计/生成 owner。不得在此阶段修页内功能；无法安全修复、缺外部条件或无合法 UI 入口时暂停，不静默缩小范围。

修复改变路径、locator 或源码映射时，主线程更新映射 revision，通知相关页面 owner 复核草稿。前期导航问题须全部解决并完成导航回归；页面功能编写可继续并行。只有导航分支 PASS、全部页面/journey 编写完成且输入复核通过，才合并注册、构建安装最终包。

`PHASE=FUNCTION` 在最终包逐页进行真实点击到页、landmark 确认、功能执行与 UI 清理，不额外先跑独立全量导航。早期门票只是前期完成依据，不是最终包所有页面已通过的证据。页面到达/恢复失败先停止新业务操作并定位测试、产品或环境首因，保留已完成结果；修复后重新构建，按页准入复测，不自动加回全量导航阶段。

`verify_only/verify_nav_fix` 在功能报告后结束，`verify_fix` 才修真实页内业务 RED。普通页面和用例不主动重启；最终包安装、崩溃恢复和生命周期专项按执行会话契约显式记录。达到 MAX_ROUNDS、连续 NO_PROGRESS_ROUNDS 无进展、编译持续失败或需额外授权/产品决策时停止。

修复约束：

- 不修导航 setup、测试基础设施或设备问题来冒充业务修复。
- 不新增只供测试读取的内部状态镜像，不修改预期迎合现有 bug。
- 修复后的判定只来自下一轮设备实测，不能把“已编辑”视为 PASS。
- 保留用户已有改动；只有用户明确要求时才创建提交，不自动 reset 或回退用户工作树。

## 完成检查

- [ ] 每页有 `plan/pages/P*.md` 与 `plan/navigation/P*.md`，用例、flow、selector 和可观察结果可追溯。
- [ ] 前期全量导航完成与功能编写两分支均通过汇合检查；最终包每页先真实点击准入再测功能，不重复独立全量导航、不复用旧包 GREEN。
- [ ] 可见页面与 iOS 源文件映射已落盘并复核版本，普通 Dialog 属于宿主页，页面范围按 ID 对账无遗漏。
- [ ] 页面准入与逐例状态准备/清理分离；普通批次不主动重启，已授权的重启例外有原因和证据，清理失败不污染后续用例。
- [ ] 每条 IN_APP flow 都由真实可见组件逐跳到页；每种可执行 `entry_kind` 都等待其目标 UI surface 的唯一可见 landmark，并明确该 surface 由被测应用、系统 UI 或系统宿主中的哪一方呈现。
- [ ] 没有测试专用页面参数、内部路由调用或其他目标页直挂路径。
- [ ] selector 只复用已有稳定产品 `id`，没有 `id` 时使用唯一可见文本；没有 ID 注入、manifest 或任何为测试修改生产组件的流程。
- [ ] 每个页面/journey `it()` 只验证一个业务功能点；每个 canonical preflight `it()` 只验证一个“目标页沿该 flow 可达”的导航契约；断言均为可观察结果。
- [ ] 每个 journey 在第一个业务特定动作所在页的 §B planned inventory 中恰好定义一次，`case_kind=JOURNEY` 且沿 `PLANNED → GENERATED → REGISTERED → EXECUTED → outcome` 使用同一稳定 ID；其他页面仅引用。
- [ ] 页面测试、导航 flow、跨页 journey 按目录归档，注册文件递归覆盖所有测试。
- [ ] API 使用满足项目 compatible SDK；UiTest 操作串行且全部 `await`。
- [ ] 报告正确区分 `kind=RED`、`kind=ERROR` 与 `kind=BLOCKED_BY_NAVIGATION`，并写准确的 `failure_class`。
- [ ] round/state/delta 验证账本位于 `spec/verify/ui/`；面向用户的当前报告唯一写入 `spec/verify/ui/ui-report.md`。
