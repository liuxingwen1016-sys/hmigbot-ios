# 真实页面导航设计模板

规划阶段为每个 Page 写 `spec/verify/ui/plan/navigation/P{编号}_{PageName}.md`。这份文档是该目标 UI surface 唯一的 canonical entry flow 设计：从该 `entry_kind` 允许的真实生产入口开始，按真实用户操作逐步前进，直到目标 UI surface 的唯一可见 landmark 出现。这里的 UI surface 是当前由用户直接看到和操作的界面，可属于被测应用、系统 UI 或系统宿主；landmark 标识 surface，不暗含它必须落在被测应用中。`IN_APP` 才固定从默认 Ability 入口开始；外部入口必须声明并复现真实 `start_context`，它可以是应用内触发页、系统 UI、公开 URI、系统宿主或另一应用，不能被统一预启动/复位逻辑覆盖。

集中导航的目的，是让页面测试复用同一条可审计到页路径，并将“到不了页面”和“页面功能失败”分开。它是本 skill 的工程约定，不是 OpenHarmony 官方目录规范。

## 到页规则

先读 `execution-session-contract.md` 和 `page-source-map.md`。先设计并运行前期全量导航（含 UI 返回/切换），同时编写页面功能测试；两侧完成后构建最终包，每页实际点击进入并确认 landmark 后运行该页功能，不额外先跑独立全量导航。普通批次保持应用运行，以真实 UI 恢复和切换。

页面集合来自实际可见页面盘点及共享 PAGE_MAP，普通 Dialog/Sheet/嵌入式 Fragment 是宿主页内交互或 guard，不因有独立 Android/Spec 文件就另建页面。Android 源文件、符号、调用关系确定迁移预期；鸿蒙源码/控件树确定实际 selector。导航运行返回 flow/landmark/截图证据和映射修正建议，由主线程写入 `spec/verify/ui/plan/page-source-map.json`。源码对应关系须经静态核实，不能仅凭一次点击成功或同名页面确定。

除正常默认入口启动外，系统、deeplink 和跨应用路径也必须由可见组件点击触发。`start_context=公开 URI` 指用户可点击该链接的真实页面上下文，不是直接执行 URI/Want；无法复现这种上下文时按不可自动化处置。入口分类不构成直达目标页的例外。

1. `IN_APP` 的冷启动、重新拉前台或生命周期恢复可由 AbilityDelegator 完成，但只能进入产品声明的正常入口；外部入口必须执行真实生产触发。
2. 每条可执行 UI edge 都必须对当前 UI surface 的真实可见组件执行用户动作，不调用应用内部路由 API；该 surface 可以由被测应用、系统 UI 或系统宿主呈现。
3. 每条 edge 完成后调用 `waitForComponent(targetLandmark, timeout)`；target landmark 必须在下一 UI surface 上可见并唯一标识该 surface。
4. `waitForIdle()` 只可辅助判断稳定且必须检查返回值，不能替代 landmark。
5. UI surface 或控件树变化后重新查找组件；不要跨 edge 缓存 `Component`。
6. 所有 UiTest 操作串行 `await`。导航 flow 不使用 `Promise.all` 或并发 UiTest 调用。
7. 坐标点击不是常规导航手段。只有产品功能本身是无语义手势且无法用组件表示时才可作为功能用例，并写出理由；canonical flow 应选择可定位组件路径。
8. 对被测产品可控组件，只复用已经存在且稳定唯一的 ID；对系统或宿主组件，只复用运行时确实暴露且有证据确认稳定唯一的 ID。没有这类 ID 时使用用户实际可见文本。文本必须在当前 UI surface 唯一，或通过唯一可见容器语境消歧后再操作；执行 click 时 locator 必须命中真实可操作的可见组件。
9. 不得为了测试给生产组件新增、改写或拼接 `.id()`，也不得用数组下标、坐标硬点、内部路由或内部状态替代语义定位。若组件真实存在但既无可复用 stable ID，也无可唯一定位的可见文本/合法关系语义 locator，则只登记一份页面级 `ERROR/UNREACHABLE_BY_UI`，移出 runnable UI inventory 并转其他测试层/人工；不生成 edge/flow/preflight 或 blocked 记录。Android 源码确认要求的入口、edge action 或目标 landmark 根本未实现时先按 `ENTRY_GAP` 处理，不能因其自然没有 locator 而误分为不可达。

## `entry_kind`

本文件对“无合法 locator 不生成 flow/preflight”的处置针对到页路径或目标 landmark。若只是目标页某个业务 action/观察点不可定位，保留原 `entry_kind`、可执行 flow/preflight 和其他功能，仅在页面设计中排除相关 planned ID；不要把整页改成 `UNREACHABLE_BY_UI`。

| 值 | 使用条件 | flow 要求 |
|---|---|---|
| `IN_APP` | 从应用正常入口经可见组件到达；根页可为零 edge | 记录启动 surface landmark 与全部应用内 edge |
| `SYSTEM_ENTRY` | 产品真实链路从应用内按钮、通知、分享面板、系统设置/Picker 或系统宿主触发，且必须跨入或由系统 UI/宿主呈现 | 记录真实 `start_context`、系统触发依据、环境前置、每次 surface 转换后的 landmark 与最终目标 UI surface landmark |
| `DEEPLINK_ENTRY` | 产品公开声明的 deeplink/URI 入口 | 记录真实 `start_context`、声明配置、URI 形态和最终目标 UI surface landmark |
| `CROSS_APP_ENTRY` | 产品真实流程必须跨越两个或多个应用的可见 UI surface | 记录真实 `start_context`、各端产品入口、跨应用动作、环境前置和最终目标 UI surface landmark；在 `ui/navigation/to_<target_short>/` 生成 flow/preflight |
| `ENTRY_GAP` | Android 源码确认要求构成到达目标 UI surface 路径的生产入口、edge action、handler、route 或 landmark，但源码/配置中尚未实现 | 记录应有入口/edge、首个缺失 edge 与证据；预期导航根为 `RED/IMPL_MISSING`，不生成直达替代 |
| `UNREACHABLE_BY_UI` | 需求本身没有公开 UI 路径/观察面，或必需操作/landmark 无合法唯一语义 locator；不是产品漏做了 Android 源码确认要求的入口 | 只写一份 `ERROR/UNREACHABLE_BY_UI`；移出 runnable UI inventory，转 UT/集成或人工，不生成 flow/preflight/blocked 或直达替代 |

`SYSTEM_ENTRY`/`DEEPLINK_ENTRY`/`CROSS_APP_ENTRY` 是合法的真实产品入口类型，不是测试后门。`entry_kind` 描述真实触发链，不由最终 UI surface 的进程或宿主单独决定；目标可在被测应用、系统 UI 或系统宿主。它们的 reachability flow 和同 ID preflight 与 `IN_APP` 一样都写入 `ui/navigation/to_<target_short>/`。若页面同时有 IN_APP 路径和外部路径，canonical flow 默认选稳定的 IN_APP 路径；外部入口本身是需求时也使用 navigation preflight。`ui/journeys/` 只在另有必须跨页验收的业务结果时使用。

## canonical flow 选择

- 从该 `entry_kind` 的真实生产入口出发，选择跳数少、条件可重复、locator 稳定且能覆盖真实守卫的路径。
- 不为缩短 setup 绕过登录、权限、首次启动、路由参数或中间页面。
- 首次启动引导、权限弹窗、账号角色等条件分支必须写成显式 guard；flow 不得静默 catch 后继续。
- Tab、Drawer、菜单、列表项、Dialog 和嵌套 Navigation 都可构成 edge，只要它们是用户可见路径。
- 若一个动态列表项是入口，优先使用该项唯一的用户可见文本；同名项必须在唯一可见容器语境内消歧。无法消歧时按页面级 `ERROR/UNREACHABLE_BY_UI` 处理，不依赖未排序数组下标或坐标。

## 稳定流程标识

- Flow ID：`NAV_P{目标页编号}_FROM_{真实入口短名}`；`IN_APP` 可用 `APP_ENTRY`，外部入口使用稳定的 `SYSTEM_<trigger>`、`DEEPLINK_<name>` 或 `<source_app>` 短名。
- Edge ID：`EDGE_<source_short>_TO_<target_short>_<purpose>`；同一来源/目标多条边时 purpose 必填。
- Guard ID：`GUARD_<page_short>_<condition>`。

Flow/Edge/Guard ID 必须全局唯一、语义稳定。导航设计、Page Object、flow 文件和失败报告使用同一标识；它们是测试工件标识，不要求或触发生产组件 ID 变更。

## 输出格式

严格按以下顺序写：

```markdown
# P{编号} 真实导航设计：{PageName}

> PAGE_MAP / MAPPING_REVISION：{映射路径与本次版本}
> Android 行为依据：{文件、符号、哈希与相关 Activity/Fragment/Dialog；实际读取}
> 页面归组：{独立可见页、包含的 Dialog/Sheet/嵌入 Fragment}
> 参考 Page Spec：spec/baseline/ui/page_{编号}_{Xxx}.md
> 入口/路由相关源码：entryability/EntryAbility.ets, pages/HomePage.ets, ...
> compatibleSdkVersion：{实测值}
> targetSdkVersion：{实测值}
> page_id：P{编号}
> page_short：{settings}
> entry_kind：IN_APP | SYSTEM_ENTRY | DEEPLINK_ENTRY | CROSS_APP_ENTRY | ENTRY_GAP | UNREACHABLE_BY_UI
> start_context：{默认应用入口 / 应用内触发页 / 系统 UI / 公开 URI / 系统宿主 / 另一应用；按真实产品路径填写}
> Canonical flow ID：NAV_P{编号}_FROM_{真实入口短名}
> Target UI surface owner：TESTED_APP | SYSTEM_UI | SYSTEM_HOST
> Target UI surface landmark：`ON.text('设置')`（设备当前语言下唯一可见标题；若当前 surface 已有并暴露 stable ID，也可直接复用）

## 1. 目标 UI surface 身份契约

| UI surface | page_short | 唯一可见 landmark locator | 到达可见条件 | 唯一性证据 | 定位来源 |
|---|---|---|---|---|---|
| HomePage | home | `ON.id('home_page_landmark')` | 正常入口首屏 | 产品已有 stable ID，当前控件树唯一 | HomePage.ets + 运行时控件树 |
| SettingsPage | settings | `ON.text('设置')` | 页面主体加载且标题可见 | 当前页面标题文本唯一 | string.json/SettingsPage.ets + 运行时控件树 |

landmark 不使用通用类型、跨 surface 复用标题或应用根容器。被测产品可控组件优先复用已有 stable ID；系统或宿主组件只复用运行时已暴露且经证据确认稳定唯一的 ID；没有这类 ID 时使用唯一可见文本。若文本重复，只能在唯一、可见且稳定的容器语境内消歧。目标 UI surface 若存在 loading/empty/error 多种状态，landmark 应是这些状态共同保留的可见身份组件；否则分别写允许的身份 locator 集合并说明互斥关系。

## 2. IN_APP 正常入口

- **适用范围**：仅 `IN_APP` 填写；外部入口写 `(不适用，见 §5)`。
- **启动方式**：AbilityDelegator 启动产品声明的 `{EntryAbility}`。
- **启动后 landmark**：`ON.id('home_page_landmark')`（产品已有 stable ID）或 `ON.text('{入口页唯一可见标题}')`。
- **启动前真实环境**：{登录角色、网络、权限、受控真实数据；不包含凭据值}。
- **恢复策略**：首批正常启动；之后通过已验证 UI 路径回到已知起点，不逐例启动/复位 Ability。只依据当前可见 landmark 决定路径，不能读取或猜测导航栈。
- **零 edge 说明**：{仅当目标就是正常入口页时填写}。

## 3. Canonical flow

| 顺序 | edge_id | 来源页 + landmark | source action locator / Page Object 方法 | 用户动作 | guard/参数 | 目标页 + landmark | 等待与上限 | Spec/源码证据 |
|---|---|---|---|---|---|---|---|---|
| 1 | EDGE_home_TO_profile_open_account | HomePage / 产品已有 `home_page_landmark` | `HomePage.openAccount()` → `ON.text('我的')` | click | `GUARD_home_logged_in`；账号角色=user | ProfilePage / `ON.text('个人中心')` | `waitForComponent(..., 5000)` | HomePage.ets:71 可见文本 + onClick → route Profile |
| 2 | EDGE_profile_TO_settings_open_settings | ProfilePage / `ON.text('个人中心')` | `ProfilePage.openSettings()` → `ON.text('设置')` | click | 无 | SettingsPage / `ON.text('设置')`（标题容器内） | `waitForComponent(..., 5000)` | ProfilePage.ets:104 可见文本 + onClick → Settings |

每行必须同时包含 source action 与 target landmark。行号以当前源码实测，目标注册/handler/参数传递形成完整证据链。

### UI 返回、恢复与页间切换

- **公共起点**：{唯一可见 landmark 与真实环境}
- **本页 → 公共起点**：{按同表字段列真实关闭/返回/首页组件、稳定 edge ID、目标 landmark 与时限}
- **其他已知页面 → 本页**：{复用上述恢复路径 + canonical flow；或有证据且纳入 preflight 的直接可见组件路径}
- **未识别界面**：{停止并保留控件树/截图；不盲点、不循环 Back、不以重启清场}

恢复 flow 与到页 flow 都位于 `ui/navigation/to_<target_short>/`，由目标 Page Object 封装选择器与原子动作。canonical preflight 使用原 flow ID 验证到达及其声明的恢复步骤；页面套级准入/业务后的恢复只记录实际调用，不伪装成另一次全量 preflight。

## 4. Guards 与条件分支

| guard_id | 出现条件 | 观察 locator | 真实 UI 处理 | 处理后 landmark | 不满足时分类 |
|---|---|---|---|---|---|
| GUARD_home_logged_in | 未登录显示登录入口 | `ON.text('登录')` | 使用专用真实测试账号走登录 UI | `ON.text('我的')` | Environment blocker |
| GUARD_home_permission | 系统权限弹窗出现 | 设备实际可见权限按钮文本 | 按场景授权/拒绝 | 入口页唯一 landmark | `kind=ERROR`, `failure_class=SETUP` |

无 guard 时写 `(无)`。不得用 catch-all 忽略 guard，也不得假定它一定不出现。

## 5. 外部/跨 surface 真实路径

仅 `SYSTEM_ENTRY`、`DEEPLINK_ENTRY` 或 `CROSS_APP_ENTRY` 填写：

| 字段 | 内容 |
|---|---|
| 真实生产路径依据 | module.json5 skills/uris、通知点击 handler、应用内系统设置按钮、系统宿主声明、分享目标声明等源码/配置 |
| start_context | flow 开始前真实可见上下文；禁止无条件启动/复位被测应用覆盖它 |
| 触发动作 | 用户在 `start_context` 所属真实 UI surface 或公开 URI 上执行的动作 |
| 环境前置 | 设备能力、系统权限、真实通知/文件/URI 条件 |
| 目标 UI surface owner | `TESTED_APP | SYSTEM_UI | SYSTEM_HOST`；按最终真实可见界面填写 |
| 目标 UI surface 的唯一可见 landmark | 当前 surface 已暴露的 stable ID，或唯一可见文本/可见容器语境 + timeout；附源码、配置或运行时控件树证据 |
| 例外理由 | 为什么不存在或不应使用 IN_APP canonical path |
| 对应 navigation flow | `ui/navigation/to_<target_short>/from_<external_source>_<path>.flow.ets` |
| 对应 reachability preflight | `ui/navigation/to_<target_short>/<flow_id>.preflight.test.ets`；`it` ID 等于 flow ID |
| 可选业务 journey | 仅在另有必须跨页才能验证的业务结果时填写，否则 `(无)` |

`IN_APP`、`ENTRY_GAP` 与 `UNREACHABLE_BY_UI` 写 `(不适用)`。

## 6. 失败分类与下游处理

| 情况 | 分类 | 下游行为 |
|---|---|---|
| Android 源码确认要求且构成目标 UI surface 到达路径的真实入口、edge action、handler、route 或目标 landmark 根本未实现 | 导航根 `RED/IMPL_MISSING` | 下游计划功能用例标 `BLOCKED_BY_NAVIGATION/NAVIGATION` 并引用根 ID |
| 已到达目标 UI surface 的唯一可见 landmark，但构造用例必需的 surface 内业务 trigger/action/control 完全不存在 | 业务用例 `RED/IMPL_MISSING` | 记 `IMPL_MISSING_STATIC`，不生成导航根，不产生下游 blocked；该功能点的业务断言未执行 |
| 入口依赖当前环境无法提供的账号、权限或系统条件 | 导航根 `ERROR/SETUP`；设备/框架不可用则 `ERROR/INFRA` | 下游功能用例标 `BLOCKED_BY_NAVIGATION/NAVIGATION` 并引用根 ID |
| 需求本身没有公开 UI 路径/观察面，或必需操作/landmark 无合法唯一语义 locator | 只写一份页面级 `ERROR/UNREACHABLE_BY_UI` | 移出 runnable UI inventory，转 UT/集成或人工验证；不生成 edge/flow/preflight、目标页 UI 用例、blocked 记录或直达替代 |
| flow 有源码依据，但运行时 selector/测试 helper 错误 | 导航根 `ERROR/SETUP` | 下游功能用例标 `BLOCKED_BY_NAVIGATION/NAVIGATION`；保留导航诊断，不计为功能 RED |
| 合法 selector 存在且测试正确命中/操作真实组件，但 onClick、生产 route/参数或目标 UI surface landmark 仍失败 | 导航根 `RED/NAVIGATION` | 下游功能用例标 `BLOCKED_BY_NAVIGATION/NAVIGATION` 并引用根 ID |
| 已成功到达来源 UI surface，且业务需求就是“点击该入口后到达目标 UI surface”，正确点击后仍未到达 | 来源页 `case_kind=PAGE` 用例的 `RED/NAVIGATION` | 用来源页 `P{NNNN}` 业务用例 ID；不创建额外 navigation case_kind，也不把它当 canonical setup root 阻塞无关用例 |
| 已到目标 UI surface 的唯一可见 landmark，surface 内业务功能断言失败 | `RED/FUNCTION` | 归目标页面功能用例 |

## 7. 生成映射

| 工件 | 目标路径 | 内容边界 |
|---|---|---|
| 页面源码映射 | `spec/verify/ui/plan/page-source-map.json` | 主线程维护，关联 page_id、Android 文件/符号/哈希、鸿蒙文件、flow/landmark 与证据 |
| 来源 Page/Surface Object | `ui/pages/<source_short>/<SourcePage>Page.ets` | 当前应用、系统或宿主 surface 的 selector、landmark 与原子动作 |
| 目标 Page/Surface Object | `ui/pages/<target_short>/<TargetPage>Page.ets` | 目标应用、系统或宿主 surface 的 landmark 与原子动作 |
| Flow | `ui/navigation/to_<target_short>/from_<source_short>_<path>.flow.ets` | 所有可执行 entry_kind 的到页路径；调 Page Object 动作、逐步等 landmark，不直接定义 selector |
| Flow preflight | `ui/navigation/to_<target_short>/<flow_id>.preflight.test.ets` | 所有可执行 entry_kind 均生成；原 flow ID 验证到达及声明的 UI 恢复路径，失败步骤记录 edge_id；递归注册 |
| 页面测试 | `ui/pages/<target_short>/P{编号}_{PageName}.test.ets` | 仅当目标 surface 有页内业务功能验收时生成；canonical flow 只作 setup |
| 业务 journey | `ui/journeys/<journey>.test.ets` | 可选；只验证必须跨页观察的业务结果，不承载页面 reachability/preflight |

## 8. ENTRY_GAP / UNREACHABLE_BY_UI 证据

仅这两类 `entry_kind` 填写：

- 已检查的入口页/组件：...
- 已检查的路由/目标注册：...
- 已检查的系统/deeplink 声明：...
- 缺失的 source action 或真实环境条件：...
- 结论：`ENTRY_GAP → RED/IMPL_MISSING`；或 `UNREACHABLE_BY_UI →` 单一页面级 `ERROR/UNREACHABLE_BY_UI`，移出 runnable UI inventory 并转 UT/集成或人工验证，不生成 flow/preflight/blocked
```

## 运行时伪代码边界

flow 的职责形态如下；具体 API 以项目 SDK 为准：

以下仅为 `IN_APP` 示例；外部入口先按 `start_context` 准备真实上下文，并以真实触发动作替换 `openNormalEntry()`。目标 surface 可以位于系统 UI 或系统宿主，不要求 flow 最终进入被测应用：

```typescript
// 当前已由批次启动或 UI 恢复到正常入口；flow 内不启动/重启应用。
await home.waitForLandmark()
await home.openAccount()
await profile.waitForLandmark()
await profile.openSettings()
await settings.waitForLandmark()
```

每个 Page/Surface Object 动作内部应重新 `findComponent`、确认非空并执行一个用户动作。`waitForLandmark` 应使用条件等待并校验返回组件。被测产品组件只复用已有 stable ID；系统/宿主组件只复用运行时已暴露且有稳定性证据的 ID；无 ID 时使用唯一可见文本或唯一可见容器语境。flow 不直接拼 locator，不吞异常，也不包含页面业务断言。

## 完成检查

- [ ] `entry_kind` 与源码/配置证据一致。
- [ ] 到页、返回公共起点和批次所用页间切换路径都已设计并纳入全局导航门；不以重启替代 UI 恢复。
- [ ] IN_APP flow 从正常入口开始，根页以外每一跳都是可见组件用户动作；preflight ID 等于 flow ID。
- [ ] 每条 edge 同时包含 source action、目标 UI surface 的唯一可见 landmark、timeout 与证据。
- [ ] target landmark 在目标 UI surface 上唯一且可见，已明确该 surface 由被测应用、系统 UI 或系统宿主呈现；`waitForIdle` 未被当作 surface 身份断言。
- [ ] 每个 locator 都有运行时唯一性证据：产品已有 stable ID 优先；无 ID 时使用唯一可见文本或唯一可见容器语境。
- [ ] 未给生产组件新增/改写 `.id()`，未使用坐标硬点、数组下标或内部状态替代定位；无法形成合法唯一语义 locator 的页面已写单一 `ERROR/UNREACHABLE_BY_UI` 并移出 runnable inventory，未生成 edge/flow/preflight/blocked。
- [ ] guard、登录、权限、参数与首次启动分支没有被绕过或静默忽略。
- [ ] SYSTEM/DEEPLINK/CROSS_APP 入口是产品真实能力，不是测试专用入口；`entry_kind` 与真实触发链一致，不强迫目标 surface 落在被测应用；其 reachability flow/preflight 已位于 `ui/navigation/to_<target_short>/`，`ui/journeys/` 未承载到达契约。
- [ ] 无真实路径时已区分 `RED/IMPL_MISSING`、`ERROR/SETUP|INFRA` 与 `ERROR/UNREACHABLE_BY_UI`；不可达页没有下游 blocked，只有真实导航/入口根失败的下游功能用例使用 `BLOCKED_BY_NAVIGATION`，且没有替代直达方案。
- [ ] 生成路径与 page_short/flow_id/edge_id 一致。
