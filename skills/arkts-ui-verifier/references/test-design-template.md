# 页面 UI 功能测试设计模板

规划阶段为每页写一份 `spec/verify/ui/plan/pages/P{编号}_{PageName}.md`。该文件回答“这个页面有哪些用户可观察功能、每个 `it()` 验证哪个功能点”；页面如何到达以及沿途 locator 由配套 `plan/navigation/P{编号}_{PageName}.md` 单独回答，本页 locator 则在 Page Object 中集中实现。

页面测试代码按页面聚合到：

```text
entry/src/ohosTest/ets/test/ui/pages/<page_short>/
├── <PageName>Page.ets
└── P{编号}_{PageName}.test.ets
```

`<PageName>Page.ets` 持有本页 selector、landmark 与原子动作；测试文件只表达功能场景和断言。跨多页才能完整判定的业务结果放到 `ui/journeys/`。

同一份页面设计也负责记录从该页发起的 journey：以“第一个业务特定动作所在页”为唯一 owner，保留在该 owner 页的 §B planned feature inventory 中，不在途经页或结果页重复登记。journey 用例 ID 仍使用 owner 页的 `P{编号}`；到达 owner 页之前的点击只算 setup/navigation，不算“第一个业务特定动作”。


## 设计原则

### 黑盒可测性

先把 iOS 源码证实的行为拆成原子需求，并以 Spec 辅助追溯，再按下列口径处置：

| 判定 | 处置 |
|---|---|
| 用户可从真实界面触发，且结果可由 UI 观察 | 纳入页面 UI 测试 |
| 必须跨多个页面才能形成完整业务结果 | 转 journey |
| 无 UI 触发或只能读取内部逻辑/状态判断 | 转 `arkts-ut-verifier` |
| 像素、动画手感、主观视觉或设备人工判断 | 转人工/探索性 |
| iOS 源码确认要求真实可见入口，但产品没有实现 | 保留需求，登记导航根缺口；运行后预期 `RED/IMPL_MISSING` |
| 目标页 landmark 已存在且可到达，但 iOS 源码确认要求的业务 action/control 在源码与控件树中完全不存在 | 保留稳定功能点 ID，计划状态记 `IMPL_MISSING_STATIC`；不伪造不可执行测试，由执行阶段合成单一 `RED/IMPL_MISSING` |
| 需求本身没有公开 UI 路径或 UI 观察面 | `ERROR/UNREACHABLE_BY_UI`，转 UT/集成测试 |

“未崩溃”“Driver 非空”“测试数据已准备”不是功能结果。

### 一个 `it()` 一个功能点

- 用例名应能完整表达单个功能结果，如 `P0010_UI_toggle_autoplay_updates_and_persists`。
- 一个功能点可以包含为证明同一结果所必需的多个 UI 断言。例如保存功能可同时断言编辑态关闭、详情文本更新和成功提示出现。
- 一条用例不得顺带验证多个无关设置、多个菜单动作或一串独立业务功能。
- 不为每个顶层组件机械创建 `COMP_*_exists`。标题、容器、图标等静态存在性并入实际功能断言；只有“该内容必须展示”本身是独立需求时才单独成例。
- 行为与结果完全等价的输入合并；行为或结果不同且各有需求依据时拆分。关键成功与失败/边界结果通常分别成例。

### 导航属于 setup

每条页面用例引用配套导航文件的 canonical flow，但不逐例重走。前期导航与功能编写并行；最终包安装后按 execution-session-contract.md，每页 beforeAll 经真实 UI 点击准入并确认 landmark，`beforeEach` 只检查本页身份并建立本例基线，`afterEach` 经 UI 清理并复核基线。普通批次不重启，外部入口也不能无条件预启动/复位。单独选择任一用例时同样可独立准入和执行。

- canonical flow 在运行时失败：先为导航根用例按证据写 `RED/NAVIGATION`、`RED/IMPL_MISSING`、`ERROR/SETUP` 或 `ERROR/INFRA`；该页未执行功能操作的下游用例才记 `BLOCKED_BY_NAVIGATION/NAVIGATION` 并引用该根 ID。
- 设计阶段没有可行 flow：按“产品缺少应有入口 / 外部前置不可用 / 需求本身 UI 不可达”分别登记根分类，不直接把页面本身写成无根引用的 `BLOCKED_BY_NAVIGATION`。
- “点击当前页入口并到达目标 UI surface”本身就是需求时，把它作为来源页的 `case_kind=PAGE` 单功能点，放在来源页测试目录；来源页已成功到达后再调用 `ui/navigation/` 中对应 transition flow 完成业务动作。跳转编排仍集中在 navigation，业务验收和最终结果归 PAGE 用例，不把它另建成 canonical setup 根。

### 只断言可观察结果

可用结果包括：

- 页面唯一 landmark、内容、空态或错误态出现/消失；
- 文本、checked/enabled/selected 状态或可见列表内容变化；
- Dialog、Toast 或其他用户反馈；
- 通过真实 UI 离开并返回、或正常重启后再次观察到持久化结果。

不读取业务内存、私有组件状态、Repository/Service 状态或数据库内部值。若 UI 没有稳定可观察结果，重新分流为 UT 或人工测试，而不是制造内部探针。

### 独立与稳定

- 每例写清真实账号、网络、权限和受控真实测试数据等 environment prerequisites。
- 页内初始状态与清理通过真实 UI 或声明的可重复真实环境流程完成；明确基线观察、恢复 flow、恢复上限与失败后暂停范围。清理失败不能默默继续，也不以重启兜底。
- 重启专项明确冷启动目标或 `persistence_boundary=relaunch`，放普通批次之后单独执行；重新安装和崩溃恢复按执行会话契约记录新 session，不改变用例业务预期。
- 用例不能依赖上一例的滚动位置、导航栈、选中态或执行顺序。
- 等待目标条件，不用固定时长猜测完成。页面变化后重新查找组件；不要复用旧 `Component`。

### Locator 契约

- 先检查运行中控件树与生产源码，复用产品已经存在、稳定且当前页面唯一的 ID。
- 组件没有 ID 时使用设备当前语言下的用户可见文本：文本必须在当前界面唯一，或限制在唯一、可见且稳定的容器语境内消歧。
- 可见文本需能追溯到生产资源、源码或运行时控件树，不凭空翻译，也不假定固定列表下标。
- 不得为测试给生产组件新增、改写或拼接 `.id()`，不得生成 ID manifest，也不得用坐标硬点、内部路由或内部状态替代定位。
- 按首个成立条件分类：构成到页路径的入口、edge action、handler、route 或目标 landmark 根本未实现，登记 `ENTRY_GAP` 导航根 `RED/IMPL_MISSING` 并阻断其计划功能点；目标页 landmark 已存在且可到达，但 iOS 源码确认要求的业务 action/control 在源码与控件树中完全不存在，功能点记 `IMPL_MISSING_STATIC`，保留稳定 ID 且不生成测试，执行阶段合成单一 `RED/IMPL_MISSING`，`test_file=null`、`blocked_by=null`、`business_assertions_run=false`；业务 action/control 已存在且可执行，只是可见结果失败、缺失或不符合 iOS 源码确定的预期，仍记 `RUNNABLE` 并生成测试，让真实执行自然判 RED；真实页面/路径存在，但必需操作或 landmark 既无可复用 stable ID，也无唯一可见文本/合法关系语义 locator，则按页聚合一份 `ERROR/UNREACHABLE_BY_UI`，仅把受影响需求移出 runnable UI inventory，转 UT/集成测试或人工验证，不生成相关不可执行工件或下游 `BLOCKED_BY_NAVIGATION`，也不修改生产组件。只有 canonical 路径/landmark 无法定位才影响整页；页内单个功能无法定位不取消页面 flow/preflight 或其他可执行测试。

## 输出格式

严格按以下顺序写：

```markdown
# P{编号} 页面 UI 测试设计：{PageName}

> 页面源码映射：spec/verify/ui/plan/page-source-map.json；MAPPING_REVISION={版本}
> Page Spec：spec/baseline/ui/page_{编号}_{Xxx}.md
> Feature Spec：spec/baseline/features/F*.md（列实际读取项）
> 相关源码：pages/{PageName}.ets, components/{Sub}.ets ...
> compatibleSdkVersion：{实测值}
> targetSdkVersion：{实测值}
> page_id：P{编号}
> page_short：{settings}
> 测试代码目录：entry/src/ohosTest/ets/test/ui/pages/{page_short}/
> entry_kind：IN_APP | SYSTEM_ENTRY | DEEPLINK_ENTRY | CROSS_APP_ENTRY | ENTRY_GAP | UNREACHABLE_BY_UI
> start_context：{默认应用入口 / 应用内触发页 / 系统 UI / 公开 URI / 系统宿主 / 另一应用；按真实产品路径填写}
> Canonical flow：NAV_P{编号}_FROM_{真实入口短名}
> 导航设计：spec/verify/ui/plan/navigation/P{编号}_{PageName}.md
> Locator 依据：{产品已有 stable ID 清单；无 ID 项对应的唯一可见文本、容器语境与控件树证据}

## A. 原子需求与可测性

| 需求 ID | 来源 | 单一功能结果 | 可测性 | 处置 | 备注 |
|---|---|---|---|---|---|
| R1 | page §设置项 | 用户切换自动播放后开关状态更新，并在重新进入页面后保持 | UI 可观察 | 纳入 UI | checked 状态 + 重进页 |
| R2 | F010 AC3 | 保存失败时展示错误提示，原值不变 | UI 可观察 | 纳入 UI | 反向结果 |
| R3 | page §排序算法 | 相同权重按时间稳定排序 | 纯逻辑 | 转 UT | UI 不提供充分判据 |
| R4 | page §入场动画 | 动画节奏自然 | 主观/动画过程 | 转人工 | |
| R5 | page §清空记录 | 用户点击清空后列表展示空态 | UI 可观察，但 action/control 完全未实装 | 保留 UI 静态实装缺口 | `IMPL_MISSING_STATIC`；页面 landmark 已存在，源码与控件树均无清空入口 |
| R6 | F011 AC1 | 用户从设置页发起导出后，系统分享页展示待分享文件名 | 必须跨页观察完整业务结果 | 纳入 UI journey | 第一个业务特定动作是设置页“导出” |

## B. 需求—用例追溯矩阵

| 需求 ID | 用例 ID | page_id | 单一功能点 | case_kind | 唯一 owner | severity | 计划状态 | navigation_case | 结果断言摘要 |
|---|---|---|---|---|---|---|---|---|---|
| R1 | P0010_UI_toggle_autoplay_updates_and_persists | P0010 | 自动播放设置切换并保持 | PAGE | page:P0010 | P0 | RUNNABLE | NAV_P0010_FROM_APP_ENTRY | checked 翻转；重进页后保持 |
| R2 | P0010_UI_save_failure_keeps_previous_value | P0010 | 保存失败保持原值 | PAGE | page:P0010 | P1 | RUNNABLE | NAV_P0010_FROM_APP_ENTRY | 错误提示；展示值未变化 |
| R5 | P0010_UI_clear_history_shows_empty_state | P0010 | 清空记录后展示空态 | PAGE | page:P0010 | P1 | IMPL_MISSING_STATIC | NAV_P0010_FROM_APP_ENTRY | 点击清空入口；空态出现 |
| R6 | P0010_UI_export_shows_file_in_share_sheet | P0010 | 从设置页导出后分享页展示文件名 | JOURNEY | journey:export_share | P2 | RUNNABLE | NAV_P0010_FROM_APP_ENTRY | 点击导出；系统分享页出现目标文件名 |

这张表是 PAGE 与 JOURNEY 共用的 planned feature inventory 权威来源。每个“纳入 UI”的需求至少有一行；`page_id` 固定为本设计的 `P{编号}`，不写 `page_short`；`case_kind` 只能是 `PAGE | JOURNEY`，唯一 owner 只能写 `page:<page_id>` 或 `journey:<journey_short>`，`计划状态` 只能是 `RUNNABLE | ENTRY_GAP | IMPL_MISSING_STATIC | UNREACHABLE_BY_UI`，后三类即使不生成测试也保留稳定用例 ID。`severity` 优先原样采用对应 Spec 的显式值；Spec 未给出时由页面设计按用户影响、核心路径与失败后果评定，并在该用例详细设计中写明依据，后续生成与 canonical writer 不得擅自重算。`JOURNEY` 仅在第一个业务特定动作所在页登记一次，并使用该页的 `P{编号}`，禁止在途经页/结果页重复计入 PLANNED。`ENTRY_GAP` 只描述入口实装后的未来功能点，不展示可运行 flow/preflight/test；`IMPL_MISSING_STATIC` 只用于页面 landmark 可到达、但完成该功能所需的业务 action/control 完全不存在的功能点，不得用于“action 可执行但结果错误/缺失”的情形；`UNREACHABLE_BY_UI` 只记录分流去向，不创建 case outcome。多个需求只有在共同描述同一个不可拆功能结果时才可映射到同一用例，并在 notes 说明原因。

## C. 用例详细设计

### P0010_UI_toggle_autoplay_updates_and_persists

- **功能点**：用户切换自动播放设置后，页面立即更新，并在正常离开和重新进入后保持。
- **类型**：页面功能 / 正向
- **severity**：`P0`（示例：Page Spec 显式声明）。
- **追溯**：R1
- **归属页**：settings
- **Canonical flow**：`NAV_P0010_FROM_APP_ENTRY`
- **Environment prerequisites**：真实测试账号已登录；账号允许修改设置；网络可用。
- **独立初始状态**：到达设置页后读取 Toggle 的 UI checked 状态作为 before；不依赖固定初值。
- **操作**：点击自动播放 Toggle；通过可见返回入口离开设置页；再次执行 canonical flow 回到设置页。
- **可观察结果**：
  1. 首次点击后重新查找 Toggle，其 checked 值等于 `!before`。
  2. 重新进入设置页后再次查找 Toggle，其 checked 值仍等于 `!before`。
- **清理**：点击 Toggle 恢复 before；重新进入页面确认 UI 已恢复。
- **稳定性**：中；每次页面变化均等待目标 landmark，再重新查找 Toggle。
- **Spec↔源码差异**：(无 / 具体差异；预期以 iOS 源码为主，记录 Spec 差异)
- **当前实装**：已实现 → 预期 GREEN / 部分或未实现 → 预期 RED（写证据）

### P0010_UI_save_failure_keeps_previous_value

- **功能点**：保存条件不满足时展示错误反馈且原展示值不变。
- **类型**：页面功能 / 反向
- **severity**：`P1`（示例：Feature Spec F010 显式声明）。
- **追溯**：R2
- **归属页**：settings
- **Canonical flow**：`NAV_P0010_FROM_APP_ENTRY`
- **Environment prerequisites**：真实测试账号已登录；使用专用可回收记录；服务处于 Spec 定义的可复现失败条件。
- **独立初始状态**：通过界面读取保存前展示值。
- **操作**：通过页面控件提交 Spec 定义的无效输入。
- **可观察结果**：错误提示出现；重新查找展示值，其内容与保存前一致。
- **清理**：关闭错误提示，恢复输入控件。
- **稳定性**：中；瞬态提示使用当前 SDK 支持的事件观察或条件等待。
- **Spec↔源码差异**：(无 / 具体差异)
- **当前实装**：...

### P0010_UI_clear_history_shows_empty_state

- **功能点**：用户点击清空入口后，列表展示空态。
- **类型**：页面功能 / 静态实装缺口
- **severity**：`P1`（示例：Spec 未显式声明；页面设计依据数据清理功能对用户可恢复性的影响评定）。
- **追溯**：R5
- **归属页**：settings
- **Canonical flow**：`NAV_P0010_FROM_APP_ENTRY`
- **计划状态**：`IMPL_MISSING_STATIC`
- **用户预期操作与结果**：点击 iOS 源码确认要求的清空入口；列表内容消失且空态出现。
- **静态证据**：目标页 landmark 已存在且 canonical flow 可到达；生产源码与运行控件树均不存在清空 action/control，不是 selector 缺失或控件禁用。
- **生成处置**：保留本稳定功能点 ID，不生成 Page Object 业务动作或 `.test.ets`；执行阶段合成一条 `RED/IMPL_MISSING` outcome，`test_file=null`、`blocked_by=null`、`business_assertions_run=false`。
- **当前实装**：未实现；若后续补齐可执行 action/control，下一轮改为 `RUNNABLE` 并生成真实 UI 测试。

### P0010_UI_export_shows_file_in_share_sheet

- **功能点**：用户从设置页发起导出后，系统分享页展示待分享文件名。
- **case_kind**：`JOURNEY`
- **severity**：`P2`（示例：Feature Spec F011 显式声明）。
- **唯一 owner**：`journey:export_share`；发起页为 P0010 settings，第一个业务特定动作是点击“导出”。
- **追溯**：R6
- **Canonical flow**：`NAV_P0010_FROM_APP_ENTRY`（只负责到达 owner 页）
- **Environment prerequisites**：系统分享能力可用；应用已有一份可导出的真实记录。
- **独立初始状态**：执行 canonical flow 到达设置页并确认 landmark。
- **业务操作**：点击设置页导出入口；按真实 UI 完成必要选择并进入系统分享页。
- **可观察结果**：系统分享页出现与被导出记录对应的用户可见文件名。
- **清理**：通过系统可见返回操作退出分享页，并按入口契约清理。
- **生成目录**：`entry/src/ohosTest/ets/test/ui/journeys/`；只生成一次，不在分享页设计或页面测试目录复制。

## D. 覆盖边界、缺口与风险

### 维度检查

| 维度 | 纳入的不同结果分支 | N/A 原因 |
|---|---|---|
| 状态 | 正常、空、错误（仅列 Spec/源码存在者） | |
| 交互 | 正常提交、无效输入 | |
| 流程 | 离开后返回保持 | |
| 数据流转 | 参数在下一页可见（若需跨页则转 journey） | |
| 适配 | 深色/字体/多语言中与本页需求直接相关者 | 其余由专项 skill 验证 |

- **未覆盖需求**：(无 / 需求 + 原因)
- **转 UT**：R3
- **转人工**：R4
- **转 journey**：(无 / 列出 JOURNEY 稳定用例 ID、唯一 owner 与第一个业务特定动作；这些用例仍在本页 §B planned inventory，不另建重复计划项)
- **导航根缺口**：(无 / `RED/NAVIGATION | RED/IMPL_MISSING | ERROR/SETUP` + 原因 + navigation 文件)
- **受影响功能点**：(无 / 运行时将在上述导航根问题存在时记 `BLOCKED_BY_NAVIGATION` 的用例 ID)
- **IMPL_MISSING_STATIC**：(无 / 页面 landmark 已存在且可到达、但业务 action/control 完全不存在的稳定功能点 ID + Spec/源码/控件树证据；不生成测试，不挂导航 blocked)
- **UNREACHABLE_BY_UI**：(无 / 无公开 UI 路径/观察面或无合法语义 locator 的页面/需求 + 证据 + 转人工/UT/集成；不生成 blocked 下游)
- **Environment blockers**：(无 / 账号、权限、网络或受控真实数据条件)
- **flaky 风险**：列异步 UI、瞬态结果与对应条件等待。

## E. 环境、状态与清理计划

- **entry_kind**：{IN_APP / SYSTEM_ENTRY / DEEPLINK_ENTRY / CROSS_APP_ENTRY / ENTRY_GAP / UNREACHABLE_BY_UI}
- **start_context**：{IN_APP 的默认 EntryAbility，或真实产品路径声明的应用内触发页/系统 UI/公开 URI/系统宿主/另一应用；不可执行类型写调查证据}
- **Canonical flow**：`NAV_P{编号}_FROM_{真实入口短名}`
- **真实账号**：{账号角色、权限；不写凭据值}
- **网络/系统权限**：{要求与可复现检查}
- **受控真实测试数据**：{最小数据集、唯一前缀、归属和回收方式}
- **页会话准入**：{当前可见起点 → 本页 flow；已在本页时的身份/环境检查}
- **页内状态准备**：{每例应观察的基线与真实 UI 准备步骤，不依赖其他用例}
- **每例清理**：{真实 UI/真实环境恢复步骤与完成后的可见基线}
- **离页恢复 flow**：{navigation/ 中的已验证路径；返回本页或公共起点}
- **恢复上限与失败处理**：{有限步骤/时限；失败停止新业务操作并记 session unsafe}
- **重启声明**：{普通用例为 none；生命周期专项给出冷启动目标或 relaunch 验收与独立执行位置}
- **外部入口契约**：(无 / 真实触发、环境前置、落地 landmark 与清理；reachability 仍属于 navigation，不因外部入口自动转 journey)
```

## 用例取舍判据

对每个候选用例问四个问题：

1. 名称是否描述一个用户能理解的功能结果？
2. 去掉该用例后，是否有一个独立需求或结果分支失去覆盖？
3. 所有断言是否共同证明同一个结果？
4. 测试是否能从声明的 `entry_kind/start_context` 独立准备、执行和清理？

若第 1、2 项为否，优先合并或删除；第 3 项为否，拆成多个用例；第 4 项为否，补环境契约或标 blocker。

## 字段约束

| 字段 | 要求 |
|---|---|
| 用例 ID | `P{编号}_UI_<单一结果>`；全局唯一、跨 round 稳定 |
| page_id | 当前设计文件的 `P{NNNN}`；与 Page Spec/导航设计一致，不能使用 `page_short` 代替 |
| 功能点 | 一句话，包含用户动作和可观察结果 |
| case_kind | `PAGE | JOURNEY`；跨页才能判定的业务结果用 `JOURNEY`，且只归属第一个业务特定动作所在页，ID 使用该 owner 页的 P 编号 |
| 唯一 owner | PAGE 写 `page:<page_id>`，JOURNEY 写 `journey:<journey_short>`；值必须全局稳定，并与生成目录和 case inventory 一致 |
| severity | `P0 | P1 | P2`；优先读取对应 Spec 的显式值。Spec 未声明时由页面设计按用户影响、核心路径与失败后果给出，并在用例详细设计中说明依据；canonical writer 原样继承 |
| 计划状态 | `RUNNABLE | ENTRY_GAP | IMPL_MISSING_STATIC | UNREACHABLE_BY_UI`；由 §B 权威记录，生成与执行不得擅自改 ID。只有业务 action/control 完全不存在时使用 `IMPL_MISSING_STATIC`；action 可执行而可见结果失败/缺失仍为 `RUNNABLE` |
| entry_kind / start_context | 与配套 navigation 设计一致；不得给外部入口统一套默认 Ability 生命周期 |
| Canonical flow | 必须引用配套 navigation 文件中的有效 flow ID |
| 独立初始状态 | 由本例建立或读取 UI before 值；不引用上一例 |
| 可观察结果 | 具体 locator/属性/文本关系；可有多个共同断言。已有 stable ID 可复用；无 ID 时写唯一可见文本或可见容器语境 |
| 清理 | UI 恢复及可见基线、恢复 flow 与上限；普通用例不重启，失败不污染下一例 |
| 会话边界 | 页面准入一次，逐例基线独立；生命周期专项显式标记，不混入普通批次 |
| 当前实装 | 以源码证据判断预期 GREEN/RED，不修改 Spec 预期 |

目录拆分、一例一功能点，以及“复用已有 stable ID、否则使用唯一可见文本”的 locator 优先级，是本 skill 的工程约定，不是 OpenHarmony 官方目录规范。UiTest 官方支持范围与版本信息见 `official-doc-basis.md`。
