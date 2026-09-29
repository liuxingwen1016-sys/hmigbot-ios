# `spec/verify/ui/round-N/ui/` 单用例问题文件 Schema

`arkts-ui-verifier` 的 execute/reconcile 阶段按此 schema 写问题文件，`arkts-ui-fixer` 按此 schema 分诊和修复。

另读 `execution-session-contract.md`，确认前期导航/编写并行、最终包逐页准入、页会话与主动暂缓。DEFERRED 只存在 outcome/索引/汇总中，本文件的产品问题 frontmatter 仍只有三种 kind。

本 schema 的判断边界是用户可见行为：测试通过真实页面组件完成导航和操作，再从 UI 观察最终结果。应用内部状态、ViewModel 字段或测试探针不能作为验收结果。

## 目录

- [一、目录布局](#一目录布局)
- [二、文件名与 ID](#二文件名与-id)
- [三、Frontmatter](#三frontmatter)
- [四、kind：本轮最终用例状态](#四kind本轮最终用例状态)
- [五、failure_class：记录分类与根因路由](#五failure_class记录分类与根因路由)
- [六、disposition](#六disposition)
- [七、正文 5 个 Section](#七正文-5-个-section)
- [八、汇总文件](#八汇总文件)
- [九、_state.yaml](#九_stateyaml)
- [十、自检](#十自检)

## 一、目录布局

```text
spec/verify/ui/
├── plan/
│   ├── page-source-map.json
│   ├── navigation/P{NNNN}_{PageName}.md
│   └── pages/P{NNNN}_{PageName}.md
├── ui-report.md
├── _state.yaml
├── round-0/
│   ├── evidence/                     # 本轮日志、截图、控件树、runner 汇总
│   │   └── plan-snapshot/            # 只读计划快照与 snapshot.json
│   ├── _ui_index.md
│   ├── _ui_summary.md
│   └── ui/
│       ├── NAV_P0010_FROM_APP_ENTRY.md
│       └── P0010_UI_INTERACT_open_font_dialog.md
├── round-1/
│   ├── evidence/
│   ├── _ui_index.md
│   ├── _ui_summary.md
│   ├── _ui_delta.md
│   ├── fixer-summary-ui.md
│   └── ui/
└── round-2/ ...
```

约束：

- 一个 `it()` 只验证一个功能点；该功能点可由 1..N 个 UI 断言共同证明。
- 一个用例 ID 在一轮最多对应一个问题文件。不要按断言数量拆文件。
- `ui/<id>.md` 存在表示该用例本轮最终状态为 `RED`、`ERROR` 或 `BLOCKED_BY_NAVIGATION`；GREEN/DEFERRED 不写问题文件，但二者必须由显式 outcome 区分，不能看文件缺失推断通过。
- `BLOCKED_BY_NAVIGATION` 不是功能失败，不计为独立产品 RED。它必须引用唯一 `blocked_by` 导航首因。
- 业务用例只有当前最终包/会话实际点击准入、本例页面/基线确认、实际业务执行与必需断言通过，且清理复核成功，才可判 GREEN；前期导航 preflight 自身以到达及恢复契约实测判 GREEN；最终导航根由本轮 PAGE_ENTRY/RECOVERY 调用聚合，不要求独立 preflight 被执行。SKIP、NOT_RUN、runner 缺结果和导航阻塞都不能因文件缺失被推断为 GREEN。
- 当前映射与设计读取 `plan/`；本轮判定使用冻结在 `evidence/plan-snapshot/` 中的对应输入，遵守 execution-session-contract 的目录规则。
- 每轮证据复制到该轮 `evidence/`，问题文件引用稳定的仓内相对路径，不把易失的 `/tmp` 路径当唯一证据。

问题文件中的 `test_file` 与 `navigation_case` 对应以下测试布局：

```text
entry/src/ohosTest/ets/test/ui/
├── navigation/
│   └── to_<target_short>/
│       ├── from_<source_short>_<path>.flow.ets    # 所有到页操作，含系统/深链/跨应用真实入口
│       └── <flow_id>.preflight.test.ets           # canonical flow 导航用例；it ID 等于 flow ID
├── pages/
│   └── <page_short>/
│       ├── <PageName>Page.ets                     # 导航 selector、landmark、原子点击
│       ├── <PageName>Features.ets                 # 页内功能及 Dialog 的 selector/操作
│       └── *.test.ets                             # 围绕本页功能点的一到多个测试文件
├── journeys/
│   └── *.test.ets                                 # 仅放必须跨页才能验证的业务结果
└── support/                                       # 无页面业务语义的公共驱动辅助
```

页面到达设计位于 `spec/verify/ui/plan/navigation/P*.md`。页面测试引用 `navigation/` 中的 canonical flow；不得把页面跳转步骤复制进每个用例，也不得在页面对象中加入直达目标页逻辑。
所有 reachability flow 及同 ID preflight，包括 `SYSTEM_ENTRY`/`DEEPLINK_ENTRY`/`CROSS_APP_ENTRY`，都放在 `ui/navigation/to_<target_short>/`。`ui/journeys/` 只承载需跨页观察才能验证的业务结果，不承载单纯到页或入口 preflight。

定位证据必须遵守同一契约：只复用产品已有且稳定唯一的 ID；没有 ID 时使用唯一的用户可见文本，或在唯一可见容器语境内消歧。不得为测试修改生产组件或生成 ID manifest，也不得用坐标、数组下标或内部状态猜测目标。

## 二、文件名与 ID

| 用例 | ID 权威来源 | 生成约束 | 示例 |
|---|---|---|---|
| canonical 页面导航 | `plan/navigation/P*.md` 的 flow ID | flow 内上报原 ID；描述性 flow 文件名遵循设计；preflight 文件名与 `it()` 原样复制 ID | `NAV_P0010_FROM_APP_ENTRY` |
| 页面功能点 | 页面设计 `plan/pages/P*.md` §B 的用例 ID | planned/case inventory、页面 `it()`、outcome 与问题文件原样复制 | `P0010_UI_INTERACT_open_font_dialog` |
| 业务 journey | 第一个业务特定动作所在页设计 §B 的用例 ID | `owner=journey:<short>`，journey `it()`、outcome 与问题文件原样复制 | `P0020_UI_share_and_return` |
| feature UI AC | 页面设计 §B 的用例 ID | 同页面功能点 | `P0010_UI_remove_bookmark` |
| 不可自动化页面记录 | 页面稳定 `page_id=P{NNNN}` 确定性派生 | 每页最多一条，聚合该页全部 `UNREACHABLE_BY_UI` planned ID；不对应 `it()` | `UNREACHABLE_P0010` |

设计 inventory ID 是普通 plan/navigation/PAGE/JOURNEY 记录的主键，测试 `it()` 只是副本，不能反向作为 ID 来源。`UNREACHABLE_<page_id>` 是唯一允许由页面稳定 ID 确定性派生的页面记录 ID；其 affected planned ID 集合必须与设计完全相等。所有 ID 必须确定、跨轮稳定，不包含时间戳或轮次。文件名严格等于 `<id>.md`；同轮重复 ID、未知实际 `it()`、缺失设计 ID、不可达映射不闭合或 journey owner 漂移时 verifier 立即以 `ERROR/SETUP` 停止 reconcile，不得临时发明 ID 补洞。

机器账本遵循 `reconcile-rules.md` 的四个最小 schema：

- `planned-feature-inventory.json` 保存设计主键，以及 `case_kind/owner/page_id/feature_point/navigation_case/persistence_boundary/severity/planning_state/expected_test_file/design_source`。
- `non-runnable-page-records.json` 以 `UNREACHABLE_<page_id>` 每页聚合一次 `UNREACHABLE_BY_UI` planned ID，保存 reason codes 与证据；这些 planned ID 不进入 case inventory，也不各自生成 outcome。
- `case-inventory.json` 只从设计正向物化 navigation/function/journey；journey 与 function 具有同样字段和状态，且 journey 的 `page_id` 固定为第一个业务特定动作所在页。`RUNNABLE` 的 `test_file=expected_test_file`；静态项 `test_file=null`，但保留非空 `expected_test_file` 供修复后按原 ID 生成。
- `case-outcomes.json` 为每个 case inventory ID 保存恰好一条终态（含有调度证据的 DEFERRED 及 deferred_reason），并完整携带 problem writer 所需的 `feature_point/navigation_case/persistence_boundary/severity`；writer 不读 `it()` 源码重建这些字段。

闭环必须满足：

```text
planned PAGE/JOURNEY id + owner
  == case inventory id + owner
  == 生成的 it() id + 唯一目录 owner
  == case outcome id + owner
  == RED/ERROR/BLOCKED_BY_NAVIGATION 时 ui/<id>.md 的 id

planned UNREACHABLE ids by page
  == non-runnable record.affected_planned_ids
  --> 唯一 ui/UNREACHABLE_<page_id>.md
```

## 三、Frontmatter

```yaml
---
id: <文件名去掉 .md>
title: <一句话标题，≤ 60 字>
page_id: <页面稳定 ID；全局基础设施问题可为 null>
feature_point: <本用例唯一验证的功能点，一句话>
test_file: <对应测试文件的仓内相对路径；静态入口缺口/blocked/功能缺失、UNREACHABLE_BY_UI 或全局 infra 根可为 null>
navigation_case: <该页面 canonical 导航用例 ID；导航用例本身填自己的 ID>

source: arkts-ui-verifier
layer: ui
kind: <RED | ERROR | BLOCKED_BY_NAVIGATION>
failure_class: <NAVIGATION | SETUP | FUNCTION | INFRA | IMPL_MISSING | UNREACHABLE_BY_UI>
blocked_by: null                    # kind=BLOCKED_BY_NAVIGATION 时填首因用例 ID
cause_id: null                      # 共享 INFRA 导致逐用例 ERROR 时填共享根 ID；导航阻塞不用它
failed_step: <首个失败步骤或 null>
persistence_boundary: <none | reenter | relaunch>
severity: <P0 | P1 | P2>

suggested_files: []                 # 仅列证据直接指向的文件；非产品问题允许空
affected_test_ids: []               # 导航首因列出受阻用例；其余通常为空
related: []

evidence:
  - spec/verify/ui/round-N/evidence/<artifact>[：行号或锚点]

disposition: null                   # null | skipped | manual_review
disposition_reason: null
disposition_set_at_round: null
---
```

### 字段语义

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 与文件名严格一致，也是跨轮状态键 |
| `title` | string | 人类速览标题，≤ 60 字 |
| `page_id` | string \| null | 页面设计文件名中的稳定 `P{NNNN}`，用于按页归档与聚合；PAGE 使用自身页面 ID，JOURNEY 使用第一个业务特定动作所在页 ID，只有全局 infra 可为 null；不得写 `page_short` |
| `feature_point` | string | 普通用例的唯一功能点；不能拼接独立能力。页面不可自动化记录与 infra 根使用各自 schema 的固定概述 |
| `test_file` | string \| null | 对应 `ui/pages/<page_short>/*.test.ets`、`ui/navigation/**/<flow_id>.preflight.test.ets` 或 `ui/journeys/*.test.ets`；静态 `ENTRY_GAP` 根及其计划 blocked 项、`IMPL_MISSING_STATIC` 功能/journey、`UNREACHABLE_BY_UI` 或全局 infra 根为 null |
| `navigation_case` | string \| null | 到达此页的 canonical flow ID，也是其 preflight `it()` ID；导航根记录填自身 |
| `kind` | enum | 本轮最终用例状态，见 §四 |
| `failure_class` | enum | 本记录分类与修复所有者，见 §五；根记录表示独立首因，blocked 记录固定为 NAVIGATION，真实根分类通过 `blocked_by` 回查 |
| `blocked_by` | string \| null | 导航阻塞根 ID；只在 `BLOCKED_BY_NAVIGATION` 非空 |
| `cause_id` | string \| null | 非导航的共享首因根 ID；仅逐用例 `ERROR/INFRA` 可非空，必须指向同轮 `ERROR/INFRA` 根文件。它不改变该用例自身终态，也不能替代 `blocked_by` |
| `failed_step` | string \| null | 首个失败的导航步骤、用户操作或 UI 后置条件 |
| `persistence_boundary` | enum | `none`、经真实 UI 离页重进 `reenter`、重启后重新导航 `relaunch` |
| `severity` | enum | P0/P1/P2，继承功能 spec |
| `suggested_files` | list[string] | 当前证据直接指向的候选文件；fixer 仍须独立验证，允许空 |
| `affected_test_ids` | list[string] | navigation/共享 infra 根影响的 case ID，或 `UNREACHABLE_<page_id>` 页面记录聚合的 planned ID；必须能由 `blocked_by`、`cause_id` 或 non-runnable record 反向校验 |
| `related` | list[string] | 人工关联，不用于把多个功能点合成一个修复结论 |
| `evidence` | list[string] | 至少一条当前轮证据，优先日志行、截图、控件树或 runner 结果 |
| `disposition*` | nullable | fix-loop 的持久处置，只有主线程写 |

### 静态记录的派生字段

canonical writer 只消费最终 `case-outcomes.json` 的 RED/ERROR/BLOCKED_BY_NAVIGATION；GREEN/DEFERRED 跳过文件写入。静态记录也必须先有完整 outcome：

| 静态记录 | 必需字段 |
|---|---|
| `ENTRY_GAP_STATIC` navigation root | `id=navigation_case=<设计 flow ID>`；`page_id/entry_kind/start_context/first_missing_edge` 来自设计；`feature_point=经公开 UI 到达 <page_id> 页面 landmark`；`test_file=null`；`persistence_boundary=none`；`severity` 依次取导航设计显式值、dependents 最高严重度、页面 Spec 严重度、默认 P1；`kind=RED`；`failure_class=IMPL_MISSING`；`blocked_by=null`；`cause_id=null`；`business_assertions_run=false` |
| `ENTRY_GAP_BLOCKED` function/journey | 全部身份字段复制 planned/case inventory；`test_file=null`；`kind=BLOCKED_BY_NAVIGATION`；`failure_class=NAVIGATION`；`blocked_by=<上述 flow ID>`；`cause_id=null`；`business_assertions_run=false` |
| `IMPL_MISSING_STATIC` function/journey | 全部身份字段复制 planned/case inventory；`test_file=null`；`kind=RED`；`failure_class=IMPL_MISSING`；`blocked_by=null`；`cause_id=null`；`affected_test_ids=[]`；`business_assertions_run=false` |
| `UNREACHABLE_BY_UI` page record | 复制 `non-runnable-page-records.json` 的完整身份字段；`id=UNREACHABLE_<page_id>`；`test_file=null`；`kind=ERROR`；`failure_class=UNREACHABLE_BY_UI`；`blocked_by=null`；`cause_id=null`；`affected_test_ids=affected_planned_ids`；`business_assertions_run=false` |
| `INFRA_UI_SHARED_SETUP` root | `title=UI 测试共享环境准备失败`；`case_kind=INFRA_ROOT`；`owner=infrastructure`；`page_id/planning_state=null`；`feature_point=UI 测试共享环境准备`；`test_file/navigation_case=null`；`persistence_boundary=none`；`severity=P0`；`suggested_files=[]`；`kind=ERROR`；`failure_class=INFRA`；`blocked_by/cause_id=null`；`affected_test_ids` 等于所有引用它的 per-case ERROR ID；`business_assertions_run=false` |

`IMPL_MISSING_STATIC` 只适用于页面已可达，但构造用例必需的业务 trigger/action/control 完全不存在。若真实 action/control 可执行且 expected UI matcher 可由 Spec/资源/UI 契约确定，即使当前结果完全未呈现，也要生成 `RUNNABLE` 测试，让执行自然形成 RED，不能为节省运行而静态判失败。需求本身没有可表达的 UI 观察契约时使用 `ERROR/UNREACHABLE_BY_UI`，不能混入静态产品缺口。

## 四、`kind`：本轮最终用例状态

| `kind` | 含义 | 是否形成独立产品失败 |
|---|---|---|
| `RED` | 已通过真实执行形成有效产品判定，或iOS 行为与鸿蒙静态源码证据确认 iOS 源码确认要求的入口、目标 landmark 或页内业务能力完全未实现 | 仅当 `failure_class` 为 NAVIGATION/FUNCTION/IMPL_MISSING |
| `ERROR` | 本轮没有形成有效产品判定，例如测试 setup、环境、无 UI 观察面 | 否；先按 `failure_class` 路由 |
| `BLOCKED_BY_NAVIGATION` | canonical 导航首因已失败，本功能用例未执行其功能操作与断言 | 否；聚合到 `blocked_by` |

GREEN 不写文件，但必须存在于本轮有效执行的显式 case outcome 中。DEFERRED 同样不写问题文件：只有调度器证明因 NAVIGATION_GATE/SESSION_UNSAFE/PHASE_NOT_STARTED 尚未开始的项才可使用；failure_class/blocked_by/cause_id=null，origin=SCHEDULER，不算产品失败也不算已解决。`ERROR` 不能被笼统当成产品 bug。`IGNORE` 只属于 runner 原始统计，不是合法 `kind`：除有明确调度证据的 DEFERRED 外，inventory 中被过滤/标 Ignore/测试配置未执行的用例归一为 `ERROR/SETUP`，runner、注册或基础设施无法给出结果则归一为 `ERROR/INFRA`，并保留原始 Ignore 证据。

终态按 ID 唯一：同一轮同一 inventory ID 不能同时出现 ERROR 和 BLOCKED。本阶段构建/安装在任何 preflight 或页面准入开始前失败时，所有尚无静态终态的 RUNNABLE nav/function/journey ID 各自写一次 `ERROR/INFRA`，本轮不派生 blocked；只有 canonical flow 的真实调用观察已形成 `RED/*` 或 `ERROR/SETUP|INFRA` 结果后，其尚无终态 dependents 才写 `BLOCKED_BY_NAVIGATION`。preflight 与实际页面准入/恢复 flow 的观察在轮末汇总为同 flow ID 的唯一结果；未调用或未分类中止不能凭空生成导航失败。

不变式：

```text
kind == BLOCKED_BY_NAVIGATION
  => failure_class == NAVIGATION
  && blocked_by != null
  && cause_id == null
  && id != blocked_by
  && 本用例没有 FUNCTION 失败断言

cause_id != null
  => kind == ERROR
  && failure_class == INFRA
  && blocked_by == null
  && cause_id != id
  && cause_id 指向同轮 ERROR/INFRA 根文件

kind == RED
  => failure_class in [NAVIGATION, FUNCTION, IMPL_MISSING]

failure_class in [SETUP, INFRA, UNREACHABLE_BY_UI]
  => kind == ERROR
```

## 五、`failure_class`：记录分类与根因路由

对未引用其他根的 `RED`/`ERROR` 文件，该字段就是独立首因；`BLOCKED_BY_NAVIGATION` 的真实首因沿 `blocked_by` 读取，关联共享环境故障的逐用例 `ERROR/INFRA` 沿 `cause_id` 读取。不能只看下游文件的 failure_class 重复计根因。

| 分类 | 判定 | 后续所有者 |
|---|---|---|
| `NAVIGATION` | 合法 selector 存在且测试已对真实可见入口正确操作，但点击链、生产路由、参数传递或目标页 landmark 使 canonical UI 路径失败；同时用于下游 blocked 状态 | 真实导航行为缺陷交产品 fixer；blocked 用例等待重跑 |
| `SETUP` | 产品已有可用 stable ID/唯一可见文本/容器语境，但测试使用了陈旧或错误 locator、page object/helper 操作错、reset/测试初始化/等待策略错；产品 UI 证据本身正确 | verifier/test |
| `FUNCTION` | 已到正确页面并执行真实用户操作，但一个或多个 UI 后置条件错误 | 产品 fixer |
| `INFRA` | 构建、安装、设备、Driver、UiTest 服务、runner 或非产品超时 | 环境/主线程 |
| `IMPL_MISSING` | spec 明确要求的用户可见功能或组件在产品中确实不存在 | 产品 fixer或产品决策 |
| `UNREACHABLE_BY_UI` | 需求没有公开 UI 操作路径或 UI 可观察结果，或真实页面虽存在，但必需操作/landmark 无产品已有的稳定唯一 ID、唯一可见文本或合法关系语义 locator；不是应有 UI 被漏做 | 转 UT/集成测试或人工验证 |

分诊规则：

- UI dump/截图显示预期结果已正确出现，且存在符合规则的 stable ID 或唯一可见文本，而测试 locator 未命中，属于 `SETUP`，不得改产品迎合测试。
- 必需操作或 landmark 无产品已有的稳定唯一 ID，也无唯一可见文本/合法关系语义 locator 时，只写一份页面级 `ERROR/UNREACHABLE_BY_UI`，`test_file: null`。仅受影响需求移出 runnable UI inventory，转 UT/集成测试或人工验证；不生成受影响且无法执行的 flow/test 或下游 `BLOCKED_BY_NAVIGATION`，也不注入 ID、坐标硬点或修改生产组件。canonical 路径/landmark 不可定位才影响整页；单个业务 action/观察点不可定位不排除其他功能和页面 preflight。
- 已有合法 selector 且页面未到达时，不运行或评价该页功能断言；canonical 导航用例记录首因，下游用例记录 `BLOCKED_BY_NAVIGATION`。
- 页面已到达、真实控件可见，但点击无效或结果错误，属于 `FUNCTION`。
- spec 应有可见功能而源码完全没有，属于 `IMPL_MISSING`；不要用隐藏入口或假状态把它变“可测”。
- Tab 子页和 Dialog 不是天然不可达：存在真实 tab/按钮且可用允许的语义 locator 唯一定位时，必须通过它们进入。确实不存在公开 UI 路径/观察面，或无法形成合法唯一语义 locator 时，用 `UNREACHABLE_BY_UI`。
- `NETWORK_OFFLINE` 不是固定分类。若 Spec 验证离线体验，真实业务操作完成后的 UI 结果错误是 `RED/FUNCTION`；测试未建立其声明的网络前置是 `ERROR/SETUP`；非预期外部断网使产品无法判定是 `ERROR/INFRA`。必须引用网络检查与 UI 执行证据，不能仅按事件名归因。

## 六、`disposition`

只有 fix-loop 主线程能写，verifier 跨轮 carry forward。

| 值 | 含义 | fixer 行为 |
|---|---|---|
| `null` | 正常分诊/排队 | 按 `kind + failure_class` 处理 |
| `skipped` | 暂时不自动修，原因可解除 | 本轮跳过；主线程可清回 null |
| `manual_review` | 需要人工产品、安全或架构决策 | 自动 fixer 跳过 |

`SETUP/INFRA/UNREACHABLE_BY_UI` 的所有者已由 `failure_class` 决定，不必为了避免产品 fixer 修改而滥用 `manual_review`。

## 七、正文 5 个 Section

标题和顺序固定：

```markdown
# {title}

## 1. Spec 引用
> {原文直引，≤ 5 行}

来源: {spec/baseline/... §节标题}

## 2. 功能点与 UI 预期
- 功能点：{只写一个}
- 导航前置：{navigation_case；通过哪些真实可见组件到达；写明复用的现有 stable ID 或唯一可见文本/容器语境；根页可写启动后 landmark}
- 用户操作：{点击/输入/滑动/返回等 UI 操作}
- UI 后置条件 1：{可见组件及属性}
- UI 后置条件 2：{可选；与其他条件共同证明同一结果}
- 持久化边界：{none | reenter | relaunch；若非 none，写离页/重启后重新经 UI 到达}

## 3. 实际结果
- 最终状态：{RED | ERROR | BLOCKED_BY_NAVIGATION}
- 导航：{已到达 landmark | 首个失败步骤 | blocked_by}
- 操作：{是否真实执行及命中哪个组件}
- UI 观察 1：{日志/控件树/截图中的实际值}
- UI 观察 2：{可选}

## 4. 首因与归属
- failure_class：{六类之一}
- 首因：{第一个足以解释结果的位置，不重复列下游症状}
- 归属：{product | verifier/test | infrastructure | UT/integration | product decision}
- 证据定位：{file:line、test:line、控件树节点或日志行}

## 5. 修复建议
1. {按首因所有者给步骤；产品修复必须是真实用户链路}
2. {如何从 UI 黑盒重验；不得读取内部状态}
```

正文约束：

| Section | 约束 |
|---|---|
| 1 | 原文引用 ≤ 5 行并给来源；不要写修改历史 |
| 2 | 只定义一个功能点；UI 后置条件 1..N；不得出现应用内部状态或 ViewModel 字段断言 |
| 3 | 逐条写 UI 观察。blocked 用例明确“功能操作与功能断言未执行”，不能伪造 FUNCTION 失败 |
| 4 | 只写首因。selector/test 与产品缺陷必须分开；无 UI 观察面要写推荐测试层 |
| 5 | 建议是 hypothesis，fixer 要独立验证；不得建议隐藏入口、测试直达、ID 注入、坐标硬点或内部状态探针 |

持久化仍是一个功能点：用例可以在同一个 `it()` 中完成“UI 改值 → 离页或重启 → 真实 UI 重进 → 观察最终控件状态”，不把每个阶段拆成独立功能用例。

## 八、汇总文件

索引必须列出全部 case outcome，DEFERRED 行显示 deferred_reason 与 gate/session 证据，不生成不存在的问题文件链接。状态分母含 DEFERRED；额外根记录不混入用例分母。汇总分开报告前期导航包指纹/状态、最终包 run-context/page-admissions、会话与重启原因、逐例清理失败，不把门 PASS 当业务通过。

### `_ui_index.md`

按 `page_id` 分组，列出最终状态和首因：

```markdown
# Round {N} ui 索引

## settings
- [设置页 canonical 导航](ui/NAV_P0010_FROM_APP_ENTRY.md) [RED][NAVIGATION][P0]
- [字体 Dialog 功能](ui/P0010_UI_INTERACT_open_font_dialog.md) [BLOCKED_BY_NAVIGATION][blocked_by=NAV_P0010_FROM_APP_ENTRY]
```

### `_ui_summary.md`

至少包含两组统计：

```markdown
## 用例最终状态

| GREEN | RED | ERROR | BLOCKED_BY_NAVIGATION | DEFERRED | 合计 |
|---:|---:|---:|---:|---:|---:|
| x | x | x | x | x | n |

## 独立首因

| failure_class | 独立首因数 | 受影响用例数 |
|---|---:|---:|
| NAVIGATION | x | x |
| SETUP | x | x |
| FUNCTION | x | x |
| INFRA | x | x |
| IMPL_MISSING | x | x |
| UNREACHABLE_BY_UI | x | x |
```

独立首因数按 `root_id = blocked_by ?? cause_id ?? id` 去重。`BLOCKED_BY_NAVIGATION` 与引用共享 infra 根的逐用例 ERROR 只增加受影响用例数，不重复增加独立首因；根文件的 `affected_test_ids` 必须与反向引用集合一致。

`_ui_delta.md` 由 `reconcile-rules.md` 生成。

## 九、`_state.yaml`

```yaml
schema_version: 2
current_round: 3
last_verifier_run_at: 2026-09-09T10:00:00+08:00
last_verifier_source: arkts-ui-verifier
loop_status: running | paused | passed | failed | stalled
max_rounds: 10
no_progress_rounds: 0
```

`schema_version: 2` 对应本文件的最终状态/首因分离模型。verifier 遇到未知版本必须停止写入。

## 十、自检

```bash
ROUND_DIR="spec/verify/ui/round-${ROUND}"

# 文件名 = id；必填字段存在
for f in "$ROUND_DIR"/ui/*.md; do
  [ -e "$f" ] || continue
  id=$(awk '/^id:/{print $2; exit}' "$f")
  [ "$id" = "$(basename "$f" .md)" ] || echo "❌ $f: id 与文件名不一致"
  for field in id title page_id feature_point test_file navigation_case source layer kind failure_class blocked_by cause_id failed_step persistence_boundary severity suggested_files affected_test_ids related evidence disposition disposition_reason disposition_set_at_round; do
    rg -q "^${field}:" "$f" || echo "❌ $f: 缺字段 $field"
  done
done

# cause_id 仅用于共享 INFRA，且必须指向同轮根问题
for f in "$ROUND_DIR"/ui/*.md; do
  [ -e "$f" ] || continue
  cause=$(awk '/^cause_id:/{print $2; exit}' "$f")
  [ -n "$cause" ] && [ "$cause" != "null" ] || continue
  kind=$(awk '/^kind:/{print $2; exit}' "$f")
  class=$(awk '/^failure_class:/{print $2; exit}' "$f")
  [ "$kind" = "ERROR" ] && [ "$class" = "INFRA" ] && [ -f "$ROUND_DIR/ui/$cause.md" ] \
    || echo "❌ $f: cause_id 无效"
done

# enum 合法
rg --no-filename '^kind:' "$ROUND_DIR"/ui/*.md | rg -v '^kind: (RED|ERROR|BLOCKED_BY_NAVIGATION)$' && echo "❌ 非法 kind"
rg --no-filename '^failure_class:' "$ROUND_DIR"/ui/*.md | rg -v '^failure_class: (NAVIGATION|SETUP|FUNCTION|INFRA|IMPL_MISSING|UNREACHABLE_BY_UI)$' && echo "❌ 非法 failure_class"
rg --no-filename '^persistence_boundary:' "$ROUND_DIR"/ui/*.md | rg -v '^persistence_boundary: (none|reenter|relaunch)$' && echo "❌ 非法 persistence_boundary"

# 五个 section 齐全
for f in "$ROUND_DIR"/ui/*.md; do
  [ -e "$f" ] || continue
  for sec in '## 1. Spec 引用' '## 2. 功能点与 UI 预期' '## 3. 实际结果' '## 4. 首因与归属' '## 5. 修复建议'; do
    rg -qF "$sec" "$f" || echo "❌ $f: 缺 section [$sec]"
  done
done

# blocked 必须能指向本轮根问题；自身不能是 root
for f in "$ROUND_DIR"/ui/*.md; do
  [ "$(awk '/^kind:/{print $2; exit}' "$f")" = "BLOCKED_BY_NAVIGATION" ] || continue
  id=$(awk '/^id:/{print $2; exit}' "$f")
  root=$(awk '/^blocked_by:/{print $2; exit}' "$f")
  [ -n "$root" ] && [ "$root" != "null" ] && [ "$root" != "$id" ] && [ -f "$ROUND_DIR/ui/$root.md" ] \
    || echo "❌ $f: blocked_by 无效"
done
```

不通过自检的 round 不能交给 fixer。
