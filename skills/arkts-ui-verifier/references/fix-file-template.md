# `spec/verify/ui/round-N/ui/<id>.md` 模板

execute/reconcile 仅为 RED/ERROR/BLOCKED_BY_NAVIGATION outcome 写一份文件，包括静态 `ENTRY_GAP_STATIC` root、其 planned blocked 项和 `IMPL_MISSING_STATIC` 功能/journey。GREEN/DEFERRED 只留在账本、索引与汇总中；对移出 runnable UI inventory 的 planned 项，按 `page_id` 只写一份确定性 `UNREACHABLE_<page_id>` 页面记录，列出完整 affected planned IDs。普通文件描述一个设计 ID 对应的功能点；不可达页面文件描述同一页面共享的不可自动化首因。完整字段定义见 `fix-file-schema.md`。

## 目录

- [通用模板](#通用模板)
- [示例一：一个功能点由多个 UI 断言共同证明](#示例一一个功能点由多个-ui-断言共同证明)
- [示例二：持久化通过离页重进后的 UI 观察](#示例二持久化通过离页重进后的-ui-观察)
- [示例三：canonical 导航失败时，下游功能只记 blocked](#示例三canonical-导航失败时下游功能只记-blocked)
- [示例四：页面可达但功能完全未实现的静态 RED](#示例四页面可达但功能完全未实现的静态-red)
- [填写检查](#填写检查)

## 通用模板

```markdown
---
id: {复制 case outcome.id；与文件名一致，不从实际 it() 推导}
title: {一句话标题，≤ 60 字}
page_id: {页面稳定 ID 或 null}
feature_point: {直接复制 outcome.feature_point；本用例唯一功能点}
test_file: {对应测试文件仓内相对路径或 null}
navigation_case: {直接复制 outcome.navigation_case；canonical 导航用例 ID 或 null}

source: arkts-ui-verifier
layer: ui
kind: {RED | ERROR | BLOCKED_BY_NAVIGATION}
failure_class: {NAVIGATION | SETUP | FUNCTION | INFRA | IMPL_MISSING | UNREACHABLE_BY_UI}
blocked_by: {null | canonical 导航首因 ID}
cause_id: {null | 共享 INFRA 根 ID；仅逐用例 ERROR/INFRA 使用}
failed_step: {首个失败步骤或 null}
persistence_boundary: {直接复制 outcome；none | reenter | relaunch}
severity: {直接复制 outcome；P0 | P1 | P2}

suggested_files:
  - {证据直接指向的生产/测试文件；没有则写 []}
affected_test_ids: []
related: []

evidence:
  - spec/verify/ui/round-{N}/evidence/{日志、截图或控件树}[：行号或锚点]

disposition: null
disposition_reason: null
disposition_set_at_round: null
---

# {title}

## 1. iOS 源码依据与 Spec 参考
> {原文直引，≤ 5 行}

来源: {spec/baseline/ui/page_00xx.md §节标题 或 spec/baseline/features/F00x.md §ACn}

## 2. 功能点与 UI 预期
- 功能点：{只写一个可验证行为}
- 导航前置：{通过哪些真实可见组件到达；引用 navigation_case；写明产品已有 stable ID 或唯一可见文本/容器语境}
- 用户操作：{对可见组件执行的点击/输入/滑动/返回；不得用坐标、下标或内部状态代替定位}
- UI 后置条件 1：{可见组件及预期属性}
- UI 后置条件 2：{可选；必须仍服务于同一功能结果}
- 持久化边界：{none；或 reenter/relaunch 的真实 UI 返回路径}

## 3. 实际结果
- 最终状态：{RED | ERROR | BLOCKED_BY_NAVIGATION}
- 导航：{已命中目标页 landmark；或失败步骤/blocked_by}
- 操作：{是否执行、命中的组件}
- UI 观察 1：{控件实际存在性/文本/checked/enabled/列表/Dialog 等}
- UI 观察 2：{可选}

## 4. 首因与归属
- failure_class：{六类之一}
- 首因：{第一个足以解释结果的位置}
- 归属：{product | verifier/test | infrastructure | UT/integration | product decision}
- 证据定位：{file:line、test:line、控件树节点或日志行}

## 5. 修复建议
1. {按首因给最小修复步骤；不向产品添加测试捷径、测试专用 ID 或内部状态探针}
2. {写下轮如何经真实 UI 重验}
```

当 `suggested_files` 为空时，写成单行 `suggested_files: []`，不要保留空列表项。

正文 §1 必须引用 PAGE_MAP/MAPPING_REVISION、实际读取的 iOS 文件/符号/哈希及相关 Dialog，再附 UI Spec 作为参考。以下示例中的 Spec 链接仅演示参考字段，不足以单独支撑产品判定；writer 必须按目标项目补齐源码依据，不得编造。

问题 writer 的身份与预期字段只能来自 `case-outcomes.json`，而 outcome 必须与 planned/case inventory 的设计主键和 owner 一致。页面/journey `it()` 与 navigation preflight 都只是复制设计 ID，不能用扫描到的实际测试名反向生成本文件。静态项在 outcome 中必须明确 `business_assertions_run=false`；正文 `## 3` 要写“未生成/未执行功能断言，结论来自当前轮iOS 行为与鸿蒙静态源码证据”。

## 示例一：一个功能点由多个 UI 断言共同证明

`spec/verify/ui/round-0/ui/P0010_UI_INTERACT_open_font_dialog.md`

```markdown
---
id: P0010_UI_INTERACT_open_font_dialog
title: 点击字体设置行应打开字体对话框
page_id: P0010
feature_point: 打开字体设置对话框
test_file: entry/src/ohosTest/ets/test/ui/pages/settings/P0010_SettingsPage.test.ets
navigation_case: NAV_P0010_FROM_APP_ENTRY

source: arkts-ui-verifier
layer: ui
kind: RED
failure_class: FUNCTION
blocked_by: null
cause_id: null
failed_step: 点击唯一可见文本“字体大小”后等待 Dialog
persistence_boundary: none
severity: P0

suggested_files:
  - entry/src/main/ets/pages/SettingsPage.ets
  - entry/src/main/ets/components/FontDialog.ets
affected_test_ids: []
related: []

evidence:
  - spec/verify/ui/round-0/evidence/ui-run.log:3422
  - spec/verify/ui/round-0/evidence/settings-after-font-click.json#/root/0/2

disposition: null
disposition_reason: null
disposition_set_at_round: null
---

# 点击字体设置行应打开字体对话框

## 1. iOS 源码依据与 Spec 参考
> 点击字体设置项后，显示字体选择对话框。

来源: spec/baseline/ui/page_0010_SettingsPage.md §交互行为

## 2. 功能点与 UI 预期
- 功能点：打开字体设置对话框
- 导航前置：运行 `NAV_P0010_FROM_APP_ENTRY`，经首页头像 → `ON.text('设置')` 的唯一可见入口，到达设置页唯一标题“设置”
- 用户操作：点击设置列表中唯一可见文本“字体大小”
- UI 后置条件 1：存在可见 Dialog
- UI 后置条件 2：Dialog 标题文本为“字体大小”
- UI 后置条件 3：关闭按钮存在且 enabled=true
- 持久化边界：none

## 3. 实际结果
- 最终状态：RED
- 导航：已命中设置页唯一可见标题“设置”
- 操作：已点击设置列表中唯一可见且 enabled=true 的“字体大小”入口
- UI 观察 1：5 秒内未出现预期 Dialog
- UI 观察 2：页面仍停留在设置列表，未出现 Dialog 标题或关闭按钮

## 4. 首因与归属
- failure_class：FUNCTION
- 首因：字体设置行的生产 onClick 未打开已声明的 FontDialog
- 归属：product
- 证据定位：entry/src/main/ets/pages/SettingsPage.ets:88；ui-run.log:3422

## 5. 修复建议
1. 连接真实“字体大小”设置行的 onClick 与生产 FontDialog 控制器，保留用户可见交互链完整。
2. 下轮仍从首页经可见组件进入设置页，点击该行后同时检查 Dialog、标题和可用关闭按钮。
```

这里的三个后置条件共同证明“打开了正确且可操作的字体对话框”，仍然只算一个功能点和一个用例。

## 示例二：持久化通过离页重进后的 UI 观察

```markdown
---
id: P0010_UI_PERSIST_enable_autoplay_reenter
title: 自动播放设置离页重进后仍保持开启
page_id: P0010
feature_point: 自动播放设置持久化
test_file: entry/src/ohosTest/ets/test/ui/pages/settings/P0010_SettingsPage.test.ets
navigation_case: NAV_P0010_FROM_APP_ENTRY

source: arkts-ui-verifier
layer: ui
kind: RED
failure_class: FUNCTION
blocked_by: null
cause_id: null
failed_step: 离页重进后检查产品已有 stable ID `settings_autoplay_toggle`
persistence_boundary: reenter
severity: P0

suggested_files:
  - entry/src/main/ets/pages/SettingsPage.ets
  - entry/src/main/ets/preferences/SettingsPreferences.ets
affected_test_ids: []
related: []

evidence:
  - spec/verify/ui/round-0/evidence/ui-run.log:3518
  - spec/verify/ui/round-0/evidence/settings-reentered.json#/root/0/4

disposition: null
disposition_reason: null
disposition_set_at_round: null
---

# 自动播放设置离页重进后仍保持开启

## 1. iOS 源码依据与 Spec 参考
> 自动播放开关的设置在再次进入设置页时保持不变。

来源: spec/baseline/features/F010.md §AC3

## 2. 功能点与 UI 预期
- 功能点：自动播放设置持久化
- 导航前置：运行 `NAV_P0010_FROM_APP_ENTRY`，经唯一可见文本“设置”到达设置页标题
- 用户操作：点击产品已有且唯一的 `settings_autoplay_toggle` 使其开启；按返回键离开；再经首页可见“设置”入口进入
- UI 后置条件 1：重进后的产品既有 `settings_autoplay_toggle.isChecked()==true`
- UI 后置条件 2：同一行摘要文本显示“已开启”
- 持久化边界：reenter；返回首页后按 canonical 路径重新进入设置页

## 3. 实际结果
- 最终状态：RED
- 导航：两次均命中设置页唯一可见标题“设置”
- 操作：首次点击后开关显示 checked=true，随后真实离页并重进
- UI 观察 1：重进后开关恢复为 checked=false
- UI 观察 2：摘要文本为“已关闭”

## 4. 首因与归属
- failure_class：FUNCTION
- 首因：生产设置保存或页面恢复链路未恢复用户选择
- 归属：product
- 证据定位：ui-run.log:3518；settings-reentered.json#/root/0/4

## 5. 修复建议
1. 沿真实设置保存与页面恢复链路定位首个未写入或未读取的位置并修复，不新增测试专用状态。
2. 下轮重复“UI 开启 → 离页 → UI 重进”，只从开关和摘要文本确认持久化结果。
```

若规格要求跨进程保存，把 `persistence_boundary` 改为 `relaunch`，并在用户操作中写明终止/重启应用后仍需从可见组件重新导航回来。

## 示例三：canonical 导航失败时，下游功能只记 blocked

```markdown
---
id: P0010_UI_INTERACT_open_font_dialog
title: 字体对话框用例被设置页导航失败阻塞
page_id: P0010
feature_point: 打开字体设置对话框
test_file: entry/src/ohosTest/ets/test/ui/pages/settings/P0010_SettingsPage.test.ets
navigation_case: NAV_P0010_FROM_APP_ENTRY

source: arkts-ui-verifier
layer: ui
kind: BLOCKED_BY_NAVIGATION
failure_class: NAVIGATION
blocked_by: NAV_P0010_FROM_APP_ENTRY
cause_id: null
failed_step: EDGE_home_TO_settings_open_settings 点击唯一可见文本“设置”后未出现目标页标题
persistence_boundary: none
severity: P0

suggested_files: []
affected_test_ids: []
related: []

evidence:
  - spec/verify/ui/round-0/evidence/navigation-settings.log:87

disposition: null
disposition_reason: null
disposition_set_at_round: null
---

# 字体对话框用例被设置页导航失败阻塞

## 1. iOS 源码依据与 Spec 参考
> 点击字体设置项后，显示字体选择对话框。

来源: spec/baseline/ui/page_0010_SettingsPage.md §交互行为

## 2. 功能点与 UI 预期
- 功能点：打开字体设置对话框
- 导航前置：`NAV_P0010_FROM_APP_ENTRY`
- 用户操作：导航成功后点击设置列表中唯一可见文本“字体大小”
- UI 后置条件 1：存在带可见标题“字体大小”的 Dialog
- 持久化边界：none

## 3. 实际结果
- 最终状态：BLOCKED_BY_NAVIGATION
- 导航：`NAV_P0010_FROM_APP_ENTRY` 的 `EDGE_home_TO_settings_open_settings` 失败，blocked_by=`NAV_P0010_FROM_APP_ENTRY`
- 操作：未执行功能操作
- UI 观察 1：未执行功能断言，不生成 FUNCTION RED

## 4. 首因与归属
- failure_class：NAVIGATION
- 首因：见 `NAV_P0010_FROM_APP_ENTRY` 问题文件；本文件不是独立首因
- 归属：等待 navigation root cause
- 证据定位：navigation-settings.log:87

## 5. 修复建议
1. 不单独修改字体设置功能；先修复或分诊 `NAV_P0010_FROM_APP_ENTRY`。
2. canonical 导航恢复后，必须真实重跑本用例并按新的 UI 结果决定 GREEN/RED/ERROR。
```

## 示例四：页面可达但功能完全未实现的静态 RED

此例的 ID 来自页面设计 §B，`planning_state=IMPL_MISSING_STATIC`。canonical 页面已有可达证据，但构造用例所需的业务 trigger/control 由 iOS 源码确认应有，但在鸿蒙源码和控件树中均确认不存在，因此不生成空 `it()`。planned/case inventory 仍保留非空 `expected_test_file`，问题 outcome/frontmatter 的 `test_file` 则为 `null`。

```markdown
---
id: P0010_UI_export_settings
title: 设置页缺少导出设置功能
page_id: P0010
feature_point: 用户点击导出设置后看到导出结果
test_file: null
navigation_case: NAV_P0010_FROM_APP_ENTRY

source: arkts-ui-verifier
layer: ui
kind: RED
failure_class: IMPL_MISSING
blocked_by: null
cause_id: null
failed_step: 设置页缺少 iOS 源码确认要求的导出 trigger/control
persistence_boundary: none
severity: P1

suggested_files:
  - entry/src/main/ets/pages/SettingsPage.ets
affected_test_ids: []
related: []

evidence:
  - spec/verify/ui/round-0/evidence/settings-source-audit.txt:21
  - spec/verify/ui/round-0/evidence/settings-tree.json#/root

disposition: null
disposition_reason: null
disposition_set_at_round: null
---

# 设置页缺少导出设置功能

## 1. iOS 源码依据与 Spec 参考
> 设置页提供导出设置入口，点击后显示导出结果。

来源: spec/baseline/ui/page_0010_SettingsPage.md §导出设置

## 2. 功能点与 UI 预期
- 功能点：用户点击导出设置后看到导出结果
- 导航前置：`NAV_P0010_FROM_APP_ENTRY`；已有证据确认可通过真实可见组件到达设置页 landmark
- 用户操作：点击 iOS 源码确认要求的导出设置入口
- UI 后置条件 1：显示导出成功结果或 iOS 源码定义的错误反馈
- 持久化边界：none

## 3. 实际结果
- 最终状态：RED
- 导航：静态证据确认 canonical 设置页存在且可达，不是 navigation gap
- 操作：未生成、未执行功能操作；必需业务 trigger/control 完全不存在
- UI 观察 1：当前源码和控件树均无导出设置入口；business_assertions_run=false

## 4. 首因与归属
- failure_class：IMPL_MISSING
- 首因：iOS 源码确认要求的导出设置业务入口及行为未实现
- 归属：product
- 证据定位：settings-source-audit.txt:21；settings-tree.json#/root

## 5. 修复建议
1. 以 iOS 源码为主要依据实现真实用户可见的导出入口、处理行为和可观察结果，不增加测试专用入口或 ID。
2. 实现后将原设计 ID 改回 RUNNABLE，按 canonical UI 路径生成并执行同 ID 用例。
```

若真实 action 已可执行且 expected UI matcher 可由 iOS 行为/鸿蒙资源契约确定，即使预计产品会失败，也不能使用此静态模板；应生成 `RUNNABLE` 测试并让真实执行形成 RED。

## 填写检查

同样是“没有找到组件”，先按证据判断首因：

| 证据 | 正确记录 |
|---|---|
| 合法 locator 已正确命中并执行真实用户操作，但生产 route/参数链失败或目标页 landmark 未出现 | 导航根用例 `RED/NAVIGATION`；本页功能用例 `BLOCKED_BY_NAVIGATION` |
| 目标页和预期结果已在截图/控件树中，产品已有 stable ID 或唯一可见文本，但测试使用了错误 locator/作用域 | `ERROR/SETUP`，建议修测试，不改产品 |
| 必需操作或 landmark 无产品已有的稳定唯一 ID，也无唯一可见文本/合法关系语义 locator | 只写一份页面级 `ERROR/UNREACHABLE_BY_UI`，移出 runnable UI inventory 并转 UT/集成或人工验证；不生成 flow/test、不生成 `BLOCKED_BY_NAVIGATION`，不注入 ID、不坐标硬点、不修改生产组件 |
| 目标页已确认，操作也命中，但应出现的 UI 结果缺失 | `RED/FUNCTION` |
| 页面可达，但构造用例必需的业务 trigger/action/control 完全不存在 | 设计 ID 保持不变，`IMPL_MISSING_STATIC` 合成 `RED/IMPL_MISSING`；`test_file:null`、`blocked_by:null`、`business_assertions_run=false` |
| 真实 action 可执行、expected matcher 可由 iOS 行为/鸿蒙资源契约确定，但运行后结果缺失 | 保持 RUNNABLE，由同 ID `it()` 的真实结果形成 `RED/FUNCTION`，不静态判失败 |
| Driver、设备、构建或 runner 无法形成产品判定 | `ERROR/INFRA`；若发生在任何 preflight 前，所有 RUNNABLE ID 各自单一 ERROR，本轮不派生 blocked |
| 需求本身没有 UI 操作路径/可观察结果，或无法形成合法唯一语义 locator | 只写 `ERROR/UNREACHABLE_BY_UI`，移出 runnable UI inventory，转 UT/集成或人工验证，不生成伪测试或 blocked 记录 |
| `NETWORK_OFFLINE` | 按证据判断：离线功能真实执行后的 UI 错误为 RED/FUNCTION；测试未准备声明状态为 ERROR/SETUP；非预期外部断网为 ERROR/INFRA |

填写前逐项检查：

1. YAML 使用空格缩进；空列表显式写 `[]`。
2. 路径用仓内相对路径；证据归档到当前 round 的 `evidence/`。
3. `id/feature_point/navigation_case/persistence_boundary/severity` 逐字复制 case outcome；outcome 与设计 planned/case inventory 一致，不能从实际 `it()` 反推。
4. journey ID 由第一个业务特定动作所在页的设计 §B 唯一拥有；`owner=journey:<short>` 与非空 `page_id` 在 planned → case → outcome 闭环一致。
5. `## 2` 只写一个功能点，UI 后置条件可有多条，但不能夹带第二个独立能力。
6. 所有导航和重进都通过真实可见组件操作；只复用产品已有 stable ID，无 ID 时使用唯一可见文本或唯一可见容器语境。测试不得直达、直接挂载或使用隐藏入口。
7. UI 后置条件只读用户可观察属性，不读取应用内部状态。
8. `BLOCKED_BY_NAVIGATION` 必须填 `blocked_by` 且 `cause_id=null`，并明确功能操作/断言未执行；同一 ID 同轮不得又写 ERROR。共享构建/设备/runner 故障导致的逐用例 `ERROR/INFRA` 使用 `cause_id` 指向同轮共享根，不能借用 `blocked_by`。
9. 构建/安装在任何 navigation preflight 前失败时，所有尚无静态终态的 RUNNABLE nav/function/journey ID 各写一次 `ERROR/INFRA`，不派生 blocked。
10. 产品已有合法 locator 而测试选错、等待或初始化错误归 `SETUP`；产品行为正确时不要建议改生产 UI。
11. 账号、网络、权限、真实预置数据或设备条件不足必须按证据归 `SETUP`、`INFRA` 或已执行离线功能的 `FUNCTION`，不得按事件名硬编码，也不得伪造条件使测试通过。
12. 没有 UI 操作路径/观察面，或无产品已有 stable ID、唯一可见文本/合法关系语义 locator 的页面，只标一份 `ERROR/UNREACHABLE_BY_UI`，移出 runnable UI inventory 并转 UT/集成或人工验证；不创建测试专用 UI、伪测试或下游 blocked 记录。
13. 不为测试新增/改写生产组件 ID，不生成 ID manifest，不用坐标、数组下标或内部状态绕过定位。
14. 不写历史尝试或修订记录。
