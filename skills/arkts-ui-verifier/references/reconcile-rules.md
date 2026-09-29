# UI fix-loop Reconciliation 算法

execute 每轮结束后，用“完整用例清单 + 本轮显式最终结果”生成 `spec/verify/ui/round-N/`。不能只比较问题文件是否存在，也不能把单条断言或导航扇出当成独立功能失败。

依赖 fix-file-schema.md、execution-session-contract.md 与 page-source-map.md。前期 NAVIGATION 与最终 FUNCTION 使用独立 round/build，前期只对导航清单 reconcile 并报告页面编写进度；功能计划未完整时不创造功能 inventory/outcome 或通过率。最终 FUNCTION 使用完整计划及本包真实页面准入/业务观察，引用而不复制前期证据。

本文完整功能 inventory 规则适用于最终阶段；前期只应用导航相关子集，PLANNED_COMPLETE=false。最终 navigation_cases 增加 `execution_basis: "PAGE_ADMISSION"`（前期为 `"PREFLIGHT"`）及 `flow_file: "entry/src/ohosTest/ets/test/ui/navigation/to_<target>/<flow>.flow.ets"`；静态 ENTRY_GAP 的 flow_file 为 null，代表以原 flow ID 聚合实际到页/恢复调用，不要求最终轮独立 preflight it 被选中。最终 navigation inventory 从 run-context 的逐页准入/恢复计划正向派生，覆盖全部 EXPECTED_PAGES，不把仅前期使用的其他入口 preflight 当最终漏测；保留原 flow ID，不新造业务用例。无 RUNNABLE 功能的页面也由 scheduler 实际入页，不因没有业务 it 就删页。test_file 可保留已注册 preflight 的定义位置，另记 flow_file 及实际调用证据；不得把它计成实际执行过的 preflight it。

## 目录

- [一、权威输入与 ID 单向流](#一权威输入与-id-单向流)
- [二、GREEN 的充分条件](#二green-的充分条件)
- [三、静态 outcome、基础设施失败与 canonical 导航聚合](#三静态-outcome基础设施失败与-canonical-导航聚合)
- [四、首因聚合](#四首因聚合)
- [五、写 round-N 问题文件](#五写-round-n-问题文件)
- [六、跨轮状态迁移](#六跨轮状态迁移)
- [七、_ui_delta.md](#七_ui_deltamd)
- [八、收敛与 _state.yaml](#八收敛与-_stateyaml)
- [九、边界情况](#九边界情况)
- [十、自检](#十自检)

## 一、权威输入与 ID 单向流

下列当前设计的规范位置为 `spec/verify/ui/plan/`。本轮 reconcile 实际使用 `round-N/evidence/plan-snapshot/` 中对应内容和 snapshot.json 校验值；保留规范设计路径作为 ID 追溯来源，但不让后续计划改动改变旧轮次判定。详细目录边界见 execution-session-contract。

reconcile 必须同时读取：

1. **planned feature inventory**：直接抄录 `plan/pages/P*.md` §B 追溯矩阵中全部页面功能点和业务 journey。设计中的“用例 ID”是功能/journey 的唯一主键；即使计划项不可执行也不得改名或丢弃。允许的 `planning_state` 为 `RUNNABLE | ENTRY_GAP | UNREACHABLE_BY_UI | IMPL_MISSING_STATIC`。
2. **navigation design**：`plan/navigation/P*.md` 中的 canonical flow ID 是导航主键。flow 内记录并上报该 ID；flow 文件名按设计使用 `from_<source>_<path>.flow.ets`，preflight 文件名与 `it()` 必须复制 flow ID。
3. **case inventory**：由 planned inventory 和 navigation design 正向物化的 navigation/function/journey 记录。`RUNNABLE` 项必须对应生成并注册的测试；`ENTRY_GAP_STATIC`、`ENTRY_GAP_BLOCKED`、`IMPL_MISSING_STATIC` 不可执行且 `test_file=null`；`UNREACHABLE_BY_UI` 不进入 runnable case inventory。
4. **non-runnable page records**：Step 3 落盘的 `evidence/non-runnable-page-records.json`。它只聚合 `UNREACHABLE_BY_UI` planned 项；`ENTRY_GAP` 已作为 `ENTRY_GAP_STATIC/ENTRY_GAP_BLOCKED` 纳入 case inventory。每条记录必须引用 planned inventory 的原稳定 ID。
5. **case outcomes**：本轮每个 case inventory ID（包括静态导航根）恰好一条最终 outcome；只有不属于 case inventory 的 `UNREACHABLE_BY_UI` 页面记录或共享基础设施根可额外出现。
6. **execution control**：前期 navigation-gate；最终轮 run-context、page-admissions、session-events 及 precheck_ref。按包/轮次分开验证，业务只接受当前最终包/会话的成功入页，不能从旧包 PASS 或缺日志推断结果。
7. **previous round**：`spec/verify/ui/round-{N-1}/ui/`，仅用于状态迁移与 disposition carry forward。

ID 流向只能是：

```text
design §B 用例 ID ──> planned inventory.id ──> case inventory.id
                                           └──> *.test.ets 的 it('<同一 ID>')
navigation design flow ID ──> navigation_cases.id
                            ├──> <同一 ID>.preflight.test.ets
                            └──> preflight it('<同一 ID>')
case inventory.id ──> case outcomes.id ──> ui/<同一 ID>.md（仅 RED/ERROR/BLOCKED）
```

不得扫描实际 `it()` 再反向创造、重命名或补齐 inventory ID。实际文件/注册表只用于校验“设计 ID 是否被完整复制”；发现未知 `it()`、重复 ID、缺失设计 ID 或 owner 不一致时归 `ERROR/SETUP`，先修生成物，不把实际测试变成事实源。

### `planned-feature-inventory.json` 最小 schema

Step 3 在任何构建或运行前生成 `evidence/planned-feature-inventory.json`。顶层 `items` 以 `id` 为主键；页面功能与 journey 使用完全相同的 writer 必需字段：

```json
{
  "schema_version": 1,
  "items": [
    {
      "id": "P0010_UI_toggle_autoplay",
      "title": "切换自动播放后应显示新状态",
      "case_kind": "PAGE",
      "owner": "page:P0010",
      "page_id": "P0010",
      "feature_point": "切换自动播放并显示新状态",
      "navigation_case": "NAV_P0010_FROM_APP_ENTRY",
      "persistence_boundary": "none",
      "severity": "P1",
      "planning_state": "RUNNABLE",
      "expected_test_file": "entry/src/ohosTest/ets/test/ui/pages/settings/P0010_SettingsPage.test.ets",
      "design_source": "spec/verify/ui/plan/pages/P0010_SettingsPage.md#B"
    },
    {
      "id": "P0020_UI_share_and_return",
      "title": "分享后应能返回并显示成功结果",
      "case_kind": "JOURNEY",
      "owner": "journey:share_and_return",
      "page_id": "P0020",
      "feature_point": "分享后从目标应用返回并显示成功结果",
      "navigation_case": "NAV_P0020_FROM_APP_ENTRY",
      "persistence_boundary": "reenter",
      "severity": "P1",
      "planning_state": "RUNNABLE",
      "expected_test_file": "entry/src/ohosTest/ets/test/ui/journeys/share_and_return.test.ets",
      "design_source": "spec/verify/ui/plan/pages/P0020_DetailPage.md#B"
    }
  ]
}
```

约束：

- `case_kind` 只能是 `PAGE | JOURNEY`。journey 也必须在某个页面设计 §B 中拥有唯一稳定 ID；`owner` 写 `journey:<journey_short>`，且只能由第一个业务特定动作所在页声明一次。页面功能写 `owner=page:<page_id>`。
- `page_id` 固定为页面设计文件名中的 `P{NNNN}`，不得写 `page_short`。PAGE 使用自身页面 ID；JOURNEY 使用第一个业务特定动作所在页 ID，且两者均不得为 `null`；全局 infra root 才允许 `page_id=null`。
- `feature_point`、`navigation_case`、`persistence_boundary`、`severity` 是 canonical problem writer 的必需输入，不能等到 runner 结束后从日志猜测。`navigation_case` 仅在产品契约确实无页面到达前置时可为 `null`。
- `expected_test_file` 是设计 ID 将来应物化到的确定性路径。`RUNNABLE` 时它必须等于 case inventory 的 `test_file`；`ENTRY_GAP`、`IMPL_MISSING_STATIC` 时仍保留，供修复后按原 ID 生成测试，不能因当前没有文件而丢失。
- `IMPL_MISSING_STATIC` 仅用于“canonical 页面可到达，但构造该用例所必需的业务 trigger/action/control，经 Spec、源码与控件树证据确认完全不存在，因此无法生成可执行用例”。若真实 action/control 可执行，且 expected UI matcher 可由 Spec/资源/UI 契约确定，即使当前结果完全未呈现也必须保持 `RUNNABLE`，让真实 UI 执行自然形成 RED。需求本身没有可表达 UI 观察契约时使用 `UNREACHABLE_BY_UI`；入口/edge/target landmark 缺失仍用 `ENTRY_GAP`，不能混用。

### `non-runnable-page-records.json` 最小 schema

`evidence/non-runnable-page-records.json` 把同一页面的 `UNREACHABLE_BY_UI` planned 项聚合成一条确定性页面记录，避免为同一 locator/观察面首因复制多份 ERROR：

```json
{
  "schema_version": 1,
  "records": [
    {
      "id": "UNREACHABLE_P0010",
      "title": "P0010 页面中的部分需求无法由 UI 自动化验证",
      "case_kind": "PAGE_RECORD",
      "owner": "page:P0010",
      "page_id": "P0010",
      "feature_point": "P0010 页面中列出的需求缺少公开 UI 路径、可观察结果或合法唯一语义 locator",
      "navigation_case": "NAV_P0010_FROM_APP_ENTRY",
      "persistence_boundary": "none",
      "severity": "P1",
      "planning_state": "UNREACHABLE_BY_UI",
      "test_file": null,
      "affected_planned_ids": ["P0010_UI_unlocatable_action"],
      "reason_codes": ["NO_LEGAL_LOCATOR"],
      "evidence": ["spec/verify/ui/plan/pages/P0010_SettingsPage.md#B"]
    }
  ]
}
```

约束：

- `id` 严格等于 `UNREACHABLE_<page_id>`，每个 `page_id` 最多一条；`case_kind=PAGE_RECORD`、`owner=page:<page_id>`、`test_file=null`、`persistence_boundary=none` 固定。
- `affected_planned_ids` 恰好等于该页 planned inventory 中 `planning_state=UNREACHABLE_BY_UI` 的 ID 集合，排序确定且无重复；这些 ID 不进入 case inventory，不各自产生 outcome/问题文件，也不能同时出现在其他页面记录中。
- `reason_codes` 是排序去重后的 `NO_PUBLIC_UI_PATH | NO_OBSERVABLE_UI | NO_LEGAL_LOCATOR` 子集；每个 reason 必须有 Spec、源码、配置或控件树证据。
- 影响范围按需求精确限定：canonical 路径或页面 landmark 无法合法定位时影响依赖它的全部功能；仅某个页内 action/观察点无法定位时，只排除相关 planned ID，保留该页 flow/preflight 和其他可执行测试。以下“不生成 flow/test”均只针对受影响且无法执行的工件，不扩大到整页。
- `navigation_case` 复制页面设计的 canonical flow；只有 `NO_PUBLIC_UI_PATH` 导致根本没有合法 flow 时可为 `null`。`severity` 取 affected planned 项最高严重度；`feature_point` 使用上例固定句式。
- reconcile 从每条 record 合成一条同 ID 的额外 `ERROR/UNREACHABLE_BY_UI` outcome：复制身份字段，`blocked_by=null`、`cause_id=null`、`failed_step=null`、`business_assertions_run=false`、`affected_test_ids=affected_planned_ids`、`origin=RECONCILE_STATIC`。canonical writer 再由该 outcome 写唯一 `ui/UNREACHABLE_<page_id>.md`。

### `case-inventory.json` 最小 schema

`evidence/case-inventory.json` 由上述设计清单正向物化：

```json
{
  "schema_version": 1,
  "navigation_cases": [
    {
      "id": "NAV_P0010_FROM_APP_ENTRY",
      "title": "应能经公开 UI 到达设置页",
      "case_kind": "NAVIGATION",
      "owner": "navigation:NAV_P0010_FROM_APP_ENTRY",
      "page_id": "P0010",
      "feature_point": "经公开 UI 到达 settings 页面 landmark",
      "navigation_case": "NAV_P0010_FROM_APP_ENTRY",
      "persistence_boundary": "none",
      "severity": "P1",
      "entry_kind": "IN_APP",
      "start_context": "默认 EntryAbility",
      "first_missing_edge": null,
      "planning_state": "RUNNABLE",
      "expected_test_file": "entry/src/ohosTest/ets/test/ui/navigation/to_settings/NAV_P0010_FROM_APP_ENTRY.preflight.test.ets",
      "test_file": "entry/src/ohosTest/ets/test/ui/navigation/to_settings/NAV_P0010_FROM_APP_ENTRY.preflight.test.ets",
      "execution_basis": "PAGE_ADMISSION",
      "flow_file": "entry/src/ohosTest/ets/test/ui/navigation/to_settings/from_home.flow.ets",
      "dependent_ids": ["P0010_UI_toggle_autoplay"]
    },
    {
      "id": "NAV_P0020_FROM_APP_ENTRY",
      "title": "应能经公开 UI 到达详情页",
      "case_kind": "NAVIGATION",
      "owner": "navigation:NAV_P0020_FROM_APP_ENTRY",
      "page_id": "P0020",
      "feature_point": "经公开 UI 到达 P0020 页面 landmark",
      "navigation_case": "NAV_P0020_FROM_APP_ENTRY",
      "persistence_boundary": "none",
      "severity": "P1",
      "entry_kind": "IN_APP",
      "start_context": "默认 EntryAbility",
      "first_missing_edge": null,
      "planning_state": "RUNNABLE",
      "expected_test_file": "entry/src/ohosTest/ets/test/ui/navigation/to_detail/NAV_P0020_FROM_APP_ENTRY.preflight.test.ets",
      "test_file": "entry/src/ohosTest/ets/test/ui/navigation/to_detail/NAV_P0020_FROM_APP_ENTRY.preflight.test.ets",
      "execution_basis": "PAGE_ADMISSION",
      "flow_file": "entry/src/ohosTest/ets/test/ui/navigation/to_detail/from_home.flow.ets",
      "dependent_ids": ["P0020_UI_share_and_return"]
    }
  ],
  "function_cases": [
    {
      "id": "P0010_UI_toggle_autoplay",
      "title": "切换自动播放后应显示新状态",
      "case_kind": "PAGE",
      "owner": "page:P0010",
      "page_id": "P0010",
      "feature_point": "切换自动播放并显示新状态",
      "navigation_case": "NAV_P0010_FROM_APP_ENTRY",
      "persistence_boundary": "none",
      "severity": "P1",
      "planning_state": "RUNNABLE",
      "expected_test_file": "entry/src/ohosTest/ets/test/ui/pages/settings/P0010_SettingsPage.test.ets",
      "test_file": "entry/src/ohosTest/ets/test/ui/pages/settings/P0010_SettingsPage.test.ets"
    }
  ],
  "journey_cases": [
    {
      "id": "P0020_UI_share_and_return",
      "title": "分享后应能返回并显示成功结果",
      "case_kind": "JOURNEY",
      "owner": "journey:share_and_return",
      "page_id": "P0020",
      "feature_point": "分享后从目标应用返回并显示成功结果",
      "navigation_case": "NAV_P0020_FROM_APP_ENTRY",
      "persistence_boundary": "reenter",
      "severity": "P1",
      "planning_state": "RUNNABLE",
      "expected_test_file": "entry/src/ohosTest/ets/test/ui/journeys/share_and_return.test.ets",
      "test_file": "entry/src/ohosTest/ets/test/ui/journeys/share_and_return.test.ets"
    }
  ]
}
```

`journey_cases` 的字段与 `function_cases` 完全相同，只允许 `case_kind=JOURNEY`、`owner=journey:<journey_short>`，`test_file` 必须位于 `ui/journeys/`。每个 planned journey ID 必须在 `journey_cases` 中恰好出现一次，并由同 ID `it()`、outcome 和问题文件继续承接；不得把 journey 展开成多个临时 function ID。

静态 navigation root 记录由 navigation design 和其 dependents 确定性派生，不能临时编 ID：

- `id = navigation_case = <设计 flow ID>`；`case_kind=NAVIGATION`；`owner=navigation:<id>`。
- `page_id`、`entry_kind`、`start_context`、`first_missing_edge` 复制 navigation/page design；`first_missing_edge` 不得为空。
- `feature_point` 固定为“经公开 UI 到达 `<page_id>` 页面 landmark”；`persistence_boundary=none`；`test_file=null`；`planning_state=ENTRY_GAP_STATIC`；`expected_test_file` 保留修复入口后应生成的 preflight 路径。
- `severity` 优先使用 navigation design 显式值，否则取 `dependent_ids` 中最高严重度（`P0 > P1 > P2`），没有 dependent 时取页面 Spec 严重度，仍无声明时默认 `P1`。
- `dependent_ids` 恰好等于同一 `navigation_case` 下 `ENTRY_GAP_BLOCKED` 的 function/journey ID 集合，排序确定且无重复。

页面/journey case 的 `planning_state` 只能是 `RUNNABLE | ENTRY_GAP_BLOCKED | IMPL_MISSING_STATIC`：前者有非空 `test_file` 且 `test_file=expected_test_file`；后两者 `test_file=null` 但 `expected_test_file` 必须非空。`ENTRY_GAP_BLOCKED` 必须对应同一 inventory 中的 `ENTRY_GAP_STATIC` navigation root；`IMPL_MISSING_STATIC` 的 canonical 页面必须不处于 `ENTRY_GAP`。

### `case-outcomes.json` 最小 schema

`evidence/case-outcomes.json` 是终态账本，不是 runner 日志的别名：

```json
{
  "schema_version": 1,
  "outcomes": [
    {
      "id": "P0010_UI_toggle_autoplay",
      "title": "切换自动播放后应显示新状态",
      "case_kind": "PAGE",
      "owner": "page:P0010",
      "page_id": "P0010",
      "feature_point": "切换自动播放并显示新状态",
      "test_file": "entry/src/ohosTest/ets/test/ui/pages/settings/P0010_SettingsPage.test.ets",
      "navigation_case": "NAV_P0010_FROM_APP_ENTRY",
      "planning_state": "RUNNABLE",
      "kind": "GREEN",
      "failure_class": null,
      "deferred_reason": null,
      "blocked_by": null,
      "cause_id": null,
      "failed_step": null,
      "persistence_boundary": "none",
      "severity": "P1",
      "business_assertions_run": true,
      "affected_test_ids": [],
      "suggested_files": [],
      "evidence": ["spec/verify/ui/round-0/evidence/ui-run.log:42"],
      "origin": "RUNNER"
    }
  ]
}
```

`kind` 只能是 `GREEN | RED | ERROR | BLOCKED_BY_NAVIGATION | DEFERRED`；GREEN/DEFERRED 的 `failure_class=null`，其余遵循 `fix-file-schema.md`。`origin` 只能是 `RUNNER | RECONCILE_STATIC | RECONCILE_INFRA | SCHEDULER`。`blocked_by` 只表示导航阻塞；`cause_id` 只把逐用例 `ERROR/INFRA` 关联到共享 infra 根。每个 case inventory ID（包括 `ENTRY_GAP_STATIC` navigation root）恰好一条 outcome；只有符合 schema 的 `UNREACHABLE_BY_UI` 页面记录或 `INFRA_UI_SHARED_SETUP` 这类不属于 case inventory 的确定性 root 可额外出现。writer 必须直接复制 outcome 中的 `page_id/feature_point/test_file/navigation_case/persistence_boundary/severity`，不得从问题标题或实际 `it()` 反推。

DEFERRED 只接受执行会话契约定义的 NAVIGATION_GATE/SESSION_UNSAFE/PHASE_NOT_STARTED，`deferred_reason` 必须非空且有本轮调度证据；其他状态该字段为 null。它留在 case inventory 和结果分母，但不写产品问题文件。PHASE_NOT_STARTED 用于尚未开始的业务项；NAVIGATION_GATE 也可用于最终轮调度停止后尚未开始的 PAGE_ADMISSION 导航项；SESSION_UNSAFE 可用于导航批次安全停止后尚未开始的 preflight，不能掩盖已开始但崩溃的调用。

runner 原始结果规范化为：

| runner 结果 | reconcile 最终状态 |
|---|---|
| 用例已执行且该功能点所有必需 UI 后置条件通过 | `GREEN`，不写问题文件 |
| 已形成有效产品判定，但至少一个必需 UI 后置条件失败 | `RED` |
| 测试 setup、环境、无 UI 观察面或无合法唯一语义 locator，未形成有效产品判定 | `ERROR`；无合法 locator 的页面不进入 runnable inventory，只写静态页面记录 |
| canonical 导航失败，本页功能操作与断言未执行 | `BLOCKED_BY_NAVIGATION` |
| 调度器有 gate/session 证据的主动未开始项 | `DEFERRED`，不写问题文件，不算通过/错误首因 |
| 无主动暂缓证据的 SKIP/NOT_RUN/runner 缺结果，但 `planning_state=RUNNABLE` | 归一为 `ERROR`，按证据分到 `SETUP` 或 `INFRA`；绝不当 GREEN |
| `planning_state=ENTRY_GAP_STATIC` | 显式合成 navigation root outcome：`RED/IMPL_MISSING`、`blocked_by=null`、`business_assertions_run=false` |
| `planning_state=ENTRY_GAP_BLOCKED` | 由上述静态 navigation root 合成 `BLOCKED_BY_NAVIGATION`，`business_assertions_run=false`，不要求 runner 结果 |
| `planning_state=IMPL_MISSING_STATIC` | 显式合成该功能/journey 的 `RED/IMPL_MISSING`，`test_file=null`、`blocked_by=null`、`business_assertions_run=false` |
| ID 已明确不在当前 inventory | `STALE` 候选，不写问题文件 |

`RED/ERROR/BLOCKED_BY_NAVIGATION` 写一份 `ui/<id>.md`。一个用例有多个 UI 断言时仍只产生一个最终状态和一个问题文件；`failed_step` 记录第一个失败检查点，其余观察写在同一文件。

## 二、GREEN 的充分条件

业务用例只有同时满足以下条件才写入显式 GREEN outcome（导航 preflight 不以前置门 PASS 为条件，避免循环依赖；它以完整到达与恢复契约的实际执行决定 GREEN）：

1. 本轮实际执行了该 `it()`，不是编译跳过、过滤掉或沿用上轮结果。
2. 本轮最终包 run-context 有效，且本业务页面已通过当前 build/session 的真实点击到页与 landmark 确认；本例重新查询页面与 UI 基线。不要求其他页面先通过，也不接受前期门票替代本包准入。后续页面失败不追溯覆盖此前有效完成的结果。
3. 功能操作通过真实可见组件完成。
4. 该功能点定义的全部必需 UI 后置条件通过。
5. 若 `persistence_boundary=reenter`，已真实离页并经可见组件重新进入后再完成 UI 观察。
6. 若 `persistence_boundary=relaunch`，已在独立生命周期专项中记录重启原因，并从公开 UI 路径重新到达后再完成 UI 观察。
7. 本例要求的 UI 清理及基线复核成功；业务通过但 cleanup 失败不能给整例 GREEN。前期导航 GREEN 要求完整 preflight/恢复契约完成；最终 PAGE_ADMISSION 导航诊断按本包实际 flow/恢复调用聚合，不声称执行过独立 preflight。

内部状态值、测试代码分支或“未抛异常”都不能替代上述 UI 结果。

## 三、静态 outcome、基础设施失败与 canonical 导航聚合

先用 `emit_once(id, outcome)` 建立终态 map；同一 ID 重复写入即失败，不能选择性覆盖。执行顺序是：设计静态状态 → 已完成的真实业务 outcome → 全部 invocation 汇总后的导航结果及其未执行 dependents → 有证据的调度暂缓 → 剩余项的 setup/infra 归一化。静态终态不会因随后构建/runner 失败而再得到 ERROR 或 blocked。

下文是算法伪代码，不是预装命令。`outcome_from(record, overrides)` 复制 schema 的全部身份字段，并默认 `blocked_by/cause_id/failed_step/deferred_reason=null`、`affected_test_ids/suggested_files=[]`；`evidence` 必须显式传入或从 record 的本轮归档证据复制，不能为空。`kind/failure_class/business_assertions_run/origin` 必须由各分支明确给出。

### 静态 outcome

```pseudocode
for nav in navigation_cases.where(planning_state = ENTRY_GAP_STATIC):
    emit_once(nav.id, outcome_from(nav,
        kind = RED,
        failure_class = IMPL_MISSING,
        blocked_by = null,
        cause_id = null,
        test_file = null,
        failed_step = nav.first_missing_edge,
        business_assertions_run = false,
        affected_test_ids = nav.dependent_ids,
        origin = RECONCILE_STATIC))

    for dependent in cases_by_ids(nav.dependent_ids):
        assert dependent.planning_state == ENTRY_GAP_BLOCKED
        emit_once(dependent.id, outcome_from(dependent,
            kind = BLOCKED_BY_NAVIGATION,
            failure_class = NAVIGATION,
            blocked_by = nav.id,
            cause_id = null,
            test_file = null,
            business_assertions_run = false,
            origin = RECONCILE_STATIC))

for case in function_cases + journey_cases:
    if case.planning_state == IMPL_MISSING_STATIC:
        assert navigation_is_not_entry_gap(case.navigation_case)
        emit_once(case.id, outcome_from(case,
            kind = RED,
            failure_class = IMPL_MISSING,
            blocked_by = null,
            cause_id = null,
            test_file = null,
            business_assertions_run = false,
            affected_test_ids = [],
            origin = RECONCILE_STATIC))
```

静态分支的 `evidence` 从对应设计引用与本轮 `static-preflight.md` 取得并归档，不要求 inventory 的身份示例包含原始证据。`ENTRY_GAP_STATIC` 不只是写问题文件：root outcome 必须先进入 `case-outcomes.json`，然后由 canonical writer 生成同 ID 根文件。`IMPL_MISSING_STATIC` 表示页面已可达，但因构造用例必需的业务 trigger/action/control 完全不存在而无法生成测试；因此它是独立功能/journey RED，不允许挂到 navigation root，也不允许制造空测试。若 action/control 可执行且 expected matcher 可表达，则该项必须是 `RUNNABLE`；当前结果未呈现只会让真实执行形成 RED。

### 构建、安装或 runner 基础设施失败

共享构建、安装、设备、daemon 或 runner 故障使用额外根 `INFRA_UI_SHARED_SETUP`，同时仍给每个受影响的 case inventory ID 一条自身终态：

```pseudocode
def emit_shared_infra(remaining_cases, phase, evidence):
    if remaining_cases is empty:
        return

    root = infra_root(
        id = INFRA_UI_SHARED_SETUP,
        title = "UI 测试共享环境准备失败",
        case_kind = INFRA_ROOT,
        owner = infrastructure,
        page_id = null,
        feature_point = "UI 测试共享环境准备",
        test_file = null,
        navigation_case = null,
        persistence_boundary = none,
        planning_state = null,
        deferred_reason = null,
        severity = P0,
        kind = ERROR,
        failure_class = INFRA,
        blocked_by = null,
        cause_id = null,
        failed_step = phase,
        business_assertions_run = false,
        affected_test_ids = remaining_cases.ids,
        suggested_files = [],
        evidence = evidence,
        origin = RECONCILE_INFRA)
    emit_extra_once(root.id, root)

    for case in remaining_cases:
        emit_once(case.id, outcome_from(case,
            kind = ERROR,
            failure_class = INFRA,
            blocked_by = null,
            cause_id = root.id,
            failed_step = phase,
            business_assertions_run = false,
            affected_test_ids = [],
            evidence = evidence,
            origin = RECONCILE_INFRA))
```

- 如果共享故障发生在本阶段任何 preflight 或页面准入开始前，`remaining_cases` 是所有尚无静态终态的 `RUNNABLE` navigation/function/journey；本轮不派生 `BLOCKED_BY_NAVIGATION`，因为没有 canonical root 形成结果。
- runner 部分崩溃时先保留所有已完成的真实 business outcome，并按本轮全部 flow invocation 汇总已形成的 navigation 最终结果。尚无最终结果的 RUNNABLE navigation case 进入 `remaining_cases`；尚无结果的 function/journey 若其 navigation 最终为 RED/ERROR，则引用该 flow root 写 blocked，否则也进入 `remaining_cases`。因此 navigation 已 GREEN 但业务尚未执行的 case 明确为 `ERROR/INFRA + cause_id=INFRA_UI_SHARED_SETUP`，而不是 blocked。
- 如果某个 canonical flow 已形成 RED/ERROR 最终结果，只让依赖该 root 且尚无业务终态的 function/journey 写 `BLOCKED_BY_NAVIGATION`；root 自己只保留一条 outcome，已完成的业务 outcome不被覆盖。
- `INFRA_UI_SHARED_SETUP.affected_test_ids` 必须恰好等于反向扫描 `cause_id=INFRA_UI_SHARED_SETUP` 的 case ID 集合。共享根不替代每个 inventory ID 的终态；逐用例 ERROR 通过 `cause_id` 聚合后只计算一个独立 infra 首因。单个 case 自身的非共享 infra 问题可保留 `cause_id=null`。

最终轮 PAGE_ADMISSION 没有独立 preflight runner 结果是正常选择，按 page-admissions/navigation-observations 对账，不进入意外 filter/Ignore/缺 runner 结果分支；整页尚未准入必须有明确调度停止证据，否则仍是 SETUP/INFRA。最终构建失败只污染最终轮，不回写前期导航包结果。

### canonical 导航阻塞

每个可执行页面或共享页面组有一个稳定 `navigation_case`。它描述从该 `entry_kind` 允许的真实产品入口开始，经真实用户动作到目标页 landmark 的 canonical 路径。`IN_APP`、`SYSTEM_ENTRY`、`DEEPLINK_ENTRY`、`CROSS_APP_ENTRY` 的 reachability flow 与同 ID preflight 全部位于 `ui/navigation/to_<target_short>/`；`ui/journeys/` 只放必须跨页观察的业务结果，不承载单纯到页契约。

preflight 与页面准入/恢复/生命周期操作中对同一 flow 的实际调用先写入 `evidence/navigation-observations.json`，不能在 preflight GREEN 时提前写最终 outcome。顶层为 `schema_version: 1` 与 `observations` 数组；每条记录包含：

| 字段 | 约束 |
|---|---|
| `invocation_id`、`ordinal` | 本轮唯一调用 ID 与递增执行序号 |
| `flow_id` | 原 navigation design ID |
| `phase`、`caller_case_id` | `PREFLIGHT` 时 caller 为 flow ID；`PAGE_ENTRY` 为页面 ID；`RECOVERY/LIFECYCLE` 为原业务 ID。普通本页 beforeEach 身份检查不是 flow 调用 |
| `kind`、`failure_class` | 完成后为 `GREEN/RED/ERROR` 及对应分类；已开始但未完成时二者为 null |
| `failed_step`、`evidence` | 首个失败 edge 或 null；至少一条本轮证据 |

调用开始时落盘 pending 记录，完成时更新同一 invocation。全部执行结束或 runner 中止后按序归并：存在 RED/ERROR 时取最早非 GREEN invocation 作为 flow 的唯一最终结果；至少一次已完成、全部为 GREEN 且没有 pending invocation 时才得到最终 GREEN；没有观察或仍有未分类 pending 时保持无结果：从未开始且有安全停止证据可 DEFERRED，其余交由 infra 规则归一；已开始 pending 不能用主动暂缓掩盖。这样同一 flow ID 不会同时出现 GREEN 与后续失败。

```pseudocode
for record in non_runnable_page_records:
    assert record.id == "UNREACHABLE_" + record.page_id
    assert record.affected_planned_ids == planned_unreachable_ids(record.page_id)
    emit_once(record.id, outcome_from(record,
            kind = ERROR,
            failure_class = UNREACHABLE_BY_UI,
            blocked_by = null,
            cause_id = null,
            failed_step = null,
            test_file = null,
            business_assertions_run = false,
            affected_test_ids = record.affected_planned_ids,
            origin = RECONCILE_STATIC))
    refer_requirements_to_ut_integration_or_manual(record.affected_planned_ids)

for case in function_cases + journey_cases:
    if case.planning_state == RUNNABLE and has_case_execution_observation(case):
        # 合并真实业务、beforeEach 基线和 afterEach 清理观察；已失败业务首因优先
        # 套级导航失败、受控暂缓、SKIP/NOT_RUN 不在此分支，不能抢占 blocked/DEFERRED
        emit_once(case.id, normalize_business_and_hook_outcome(case))

for nav in navigation_cases.where(planning_state = RUNNABLE):
    result = final_navigation_results.get(nav.id)
    if result is null:
        continue                         # 没有观察不能凭空创造导航失败

    root = outcome_from(nav, normalize_navigation_result(result))
    # normalize 保留 runner 证据，origin=RUNNER，business_assertions_run=false
    blocked = []
    if root.kind != GREEN:
        blocked = cases_by_ids(nav.dependent_ids).where(
            planning_state = RUNNABLE and not outcomes.has(id))
    root.affected_test_ids = blocked.ids
    emit_once(nav.id, root)

    for case in blocked:
        emit_once(case.id, outcome_from(case,
            kind = BLOCKED_BY_NAVIGATION,
            failure_class = NAVIGATION,
            blocked_by = nav.id,
            cause_id = null,
            failed_step = root.failed_step,
            business_assertions_run = false,
            affected_test_ids = [],
            evidence = root.evidence,
            origin = RUNNER))

remaining = all_cases.where(planning_state = RUNNABLE and not outcomes.has(id))
for case in remaining.where(has_proven_scheduler_deferral):
    assert case_not_started(case) and no_real_infra_interruption(case)
    emit_once(case.id, outcome_from(case,
        kind = DEFERRED, failure_class = null,
        deferred_reason = scheduler_reason(case),  # NAVIGATION_GATE / SESSION_UNSAFE / PHASE_NOT_STARTED
        blocked_by = null, cause_id = null,
        business_assertions_run = false,
        evidence = scheduler_evidence(case), origin = SCHEDULER))

remaining = all_cases.where(planning_state = RUNNABLE and not outcomes.has(id))
for case in remaining.where(has_explicit_filter_or_ignore_evidence):
    emit_once(case.id, outcome_from(case,
        kind = ERROR, failure_class = SETUP,
        business_assertions_run = false,
        evidence = selection_evidence(case), origin = RUNNER))

remaining = all_cases.where(planning_state = RUNNABLE and not outcomes.has(id))
emit_shared_infra(remaining, missing_result_phase, missing_result_evidence)
# infra 最后生成：它的逐用例 ERROR 不是“已观察到的导航失败”，不再派生 blocked
```

规则：

- 导航首因只由 `navigation_case` 文件表达。下游页面功能与 journey 不运行功能操作，不写 FUNCTION 断言失败。
- 前期 preflight GREEN 只进入前期门票；最终 PAGE_ENTRY/RECOVERY 观察独立聚合为原 flow ID 的本包诊断。最终到页失败停止新业务：已完成结果保留，直接 dependents blocked，其余有明确停止证据的未开始业务/页面准入为 DEFERRED/NAVIGATION_GATE；不得混入前期 GREEN 或伪造独立 preflight 执行。
- 每个可执行页面的 `navigation_case` 等于 canonical flow ID，也等于其 preflight `it()` ID。多跳失败仍以 flow ID 写根文件，具体 edge 只写入 `failed_step`。
- `ENTRY_GAP` 没有可执行 preflight：基于本轮iOS 行为与鸿蒙静态源码证据先合成 `RED/IMPL_MISSING` root outcome（含默认/派生完整字段），再由 writer 写 `test_file: null` 根文件；随后使用 planned inventory 的稳定 function/journey ID 合成 `test_file: null` blocked outcome 与文件。不能从不存在的测试文件反推 ID。这不阻止其他页面完成设计/生成或导航诊断，但会关闭全局功能准入门。
- `IMPL_MISSING_STATIC` 没有测试文件：基于目标页已可达、但构造用例必需的业务 trigger/action/control 完全不存在的静态证据，生成自身 `RED/IMPL_MISSING` outcome/问题文件；`blocked_by=null`，不影响同页其他可运行功能。
- `UNREACHABLE_BY_UI` 包括“无公开 UI 路径/观察面”和“任一必需操作或 landmark 无产品已有稳定唯一 ID、唯一可见文本或合法关系语义 locator”。只写一份 `ERROR/UNREACHABLE_BY_UI` 页面级记录并转 UT/集成或人工验证，其需求不进入 runnable UI inventory；不生成 flow/test，也不生成下游 `BLOCKED_BY_NAVIGATION`。
- `blocked_by` 必须指向本轮存在的根问题文件。对 `ENTRY_GAP`，root outcome/根文件 `affected_test_ids`、planned inventory 中该 `navigation_case` 下的 `ENTRY_GAP` function/journey ID、case inventory 的 `ENTRY_GAP_BLOCKED` ID，以及 blocked outcome/文件按 `blocked_by` 的反向扫描结果必须全部一致；其他导航根至少保证 root outcome、根文件与反向扫描一致。
- 如果控件树/截图证明产品页面和入口正确，产品已有 stable ID 或可唯一定位的可见文本，而 navigation helper 使用了错误 locator、错误作用域或错误等待，根文件是 `ERROR + SETUP`，不得改产品。
- 如果产品有对应真实页面/组件，但必需操作或 landmark 无合法唯一语义 locator，走前述 `ERROR/UNREACHABLE_BY_UI` 前置分支，不得进入 navigation root 分类或派生 blocked 文件。不得注入 ID、生成 ID manifest、坐标硬点或修改生产组件来绕过。
- 如果 iOS 源码确认要求且构成到页路径的真实入口、edge action、handler、route 或目标 landmark 根本未实现，导航根文件是 `RED + IMPL_MISSING`。若目标 landmark 已到达但构造功能用例必需的页内业务 trigger/action/control 完全不存在，则只写该功能点 `RED + IMPL_MISSING`，不派生导航 blocked。若 action/control 可执行且 expected matcher 可表达，只是结果错误或完全未呈现，则保持 `RUNNABLE` 并由真实执行形成 `RED + FUNCTION`。如果合法 selector 存在、测试已正确操作真实组件，但 onClick、生产路由/参数或目标 landmark 仍失败，导航根文件是 `RED + NAVIGATION`。
- journey 的 canonical 前置失败时按其 `navigation_case` blocked；前置通过后 journey 自身操作/跨页结果失败归 journey ID 的 `RED/FUNCTION`。不能把 journey 失败改写成 owner 页面中的另一个功能 ID。
- 不允许在测试中直达、直接挂载目标页，也不允许给产品增加隐藏入口或测试专用路径。
- 导航恢复后的下一轮必须真实执行所有受影响功能用例。它们不能因为 blocked 文件消失就自动记 fixed。

## 四、首因聚合

状态统计和根因统计分开：

```pseudocode
problem_files = scan("round-N/ui/*.md")

for problem in problem_files:
    root_id = problem.blocked_by ?? problem.cause_id ?? problem.id
    group problem under root_id

for root_id, group in groups:
    root_problem = problem_files[root_id]
    assert root_problem.kind != BLOCKED_BY_NAVIGATION
    aggregate[root_id] = {
        "failure_class": root_problem.failure_class,
        "root_kind": root_problem.kind,
        "affected_case_count": count(id in case_inventory.ids in group),
        "affected_planned_count": count_distinct_affected_planned_ids(group),
        "blocked_case_count": count(kind == BLOCKED_BY_NAVIGATION in group)
    }
```

汇总必须同时报告：

- 用例最终状态数：仅计 case inventory 的 GREEN / RED / ERROR / BLOCKED_BY_NAVIGATION / DEFERRED；额外的页面记录和共享 infra 根单列，不混入用例分母。
- 独立首因数：按根文件的 `failure_class` 分布。
- 受影响用例数：只计 inventory 内的根用例及其受影响用例；额外的 infra/page 根本身不是测试用例。页面不可自动化记录另外报告 affected planned 功能点数。

因此一个设置页导航首因阻塞 30 条页面功能/journey 用例时，报告是“1 个独立首因、30 条 blocked”，不是 30 条 FUNCTION RED；一次共享构建/设备/runner 故障影响 N 个 ID 时也只计 1 个 INFRA 首因，同时保留 N 个逐用例 ERROR 终态。

## 五、写 round-N 问题文件

```pseudocode
def write_problem_file(round_n, outcome):
    assert outcome.kind in [RED, ERROR, BLOCKED_BY_NAVIGATION]
    assert_outcome_matches_inventory_identity(outcome,
        fields = [id, case_kind, owner, page_id, feature_point, test_file,
                  navigation_case, persistence_boundary, severity, planning_state])
    path = f"spec/verify/ui/round-{round_n}/ui/{outcome.id}.md"
    prev = latest_open_problem_before(round_n, outcome.id)
    # 中间仅 DEFERRED 的轮次不算解决；跨过它保留人工 disposition，遇显式 GREEN 则停止回溯

    fm = {
        "id": outcome.id,
        "title": outcome.title,
        "page_id": outcome.page_id,
        "feature_point": outcome.feature_point,
        "test_file": outcome.test_file,
        "navigation_case": outcome.navigation_case,
        "source": "arkts-ui-verifier",
        "layer": "ui",
        "kind": outcome.kind,
        "failure_class": outcome.failure_class,
        "blocked_by": outcome.blocked_by,
        "cause_id": outcome.cause_id,
        "failed_step": outcome.failed_step,
        "persistence_boundary": outcome.persistence_boundary,
        "severity": outcome.severity,
        "suggested_files": outcome.suggested_files,
        "affected_test_ids": outcome.affected_test_ids,
        "related": [],
        "evidence": archive_evidence(round_n, outcome.evidence),
        "disposition": None,
        "disposition_reason": None,
        "disposition_set_at_round": None,
    }

    if exists(prev):
        prev_fm = parse_frontmatter(prev)
        carry_disposition_and_related(prev_fm, fm)

    validate_kind_class_invariants(fm)
    write(path, fm, render_five_sections(outcome,
        business_assertions_run = outcome.business_assertions_run))
```

`assert_outcome_matches_inventory_identity` 对普通 case 要求逐字段相等；只对已声明的 `ENTRY_GAP_STATIC` navigation root、符合上述 schema 的 `UNREACHABLE_BY_UI` 页面记录和 `INFRA_UI_SHARED_SETUP` 使用本文件规定的派生默认值。writer 绝不读取测试源码来重建 `feature_point/navigation_case/persistence_boundary/severity`。

### Carry forward 不变式

1. `disposition`、`disposition_reason`、`disposition_set_at_round` 仅由主线程改；同 ID 仍开放时原样 carry。
2. `related` 可 carry；`kind`、`failure_class`、`blocked_by`、`cause_id`、`failed_step`、`affected_test_ids`、`suggested_files` 和 `evidence` 必须按本轮结果重算。
3. 证据先归档到 `round-N/evidence/`，再写引用。
4. blocked 文件不得携带独立产品修复建议；它只指向 `blocked_by` 并要求导航恢复后重跑。
5. 本轮 ERROR 可以在下轮重分类为产品 RED，反之亦然；运行状态与首因都以最新证据为准。

## 六、跨轮状态迁移

阶段范围切换不是删除用例：前期 NAVIGATION 没有功能 inventory、或最终轮不选择仅前期的额外入口 preflight，都不得标 stale/fixed。跨阶段只比较双方实际覆盖且具有有效结果的同一 ID，其他项保留原阶段结果与未在本阶段验证的范围说明；没有当前包准入证据不能承接旧 GREEN。

不能再用“文件存在/不存在”单独推断 fixed。对每个 inventory ID 使用显式 outcome；GREEN/DEFERRED 都可能没有问题文件，但两者语义完全不同：

| 上轮状态 | 本轮显式状态 | delta 分类 | 本轮问题文件 |
|---|---|---|---|
| 无/ GREEN | GREEN | `still_green` | 否 |
| 无/ GREEN | RED 或 ERROR | `newly_open`；若历史曾 GREEN 则 `regressed` | 是 |
| 无/ GREEN | BLOCKED_BY_NAVIGATION | `newly_blocked`，聚合到 root | 是 |
| RED/ERROR | GREEN | `fixed` | 否 |
| RED/ERROR | RED/ERROR | `still_failing`；若 kind/class 变更另记 transition | 是 |
| RED/ERROR | BLOCKED_BY_NAVIGATION | `now_blocked`，不算 fixed | 是 |
| BLOCKED_BY_NAVIGATION | GREEN | `unblocked_green` | 否 |
| BLOCKED_BY_NAVIGATION | RED/ERROR | `revealed_after_unblock`，不是 regression | 是 |
| BLOCKED_BY_NAVIGATION | BLOCKED_BY_NAVIGATION | `still_blocked` | 是 |
| 任意状态 | DEFERRED | `deferred`；不是 fixed/stale，保留最近开放问题的人工 disposition | 否 |
| DEFERRED | GREEN | `resumed_green`；原开放问题只有现在才可解除 | 否 |
| DEFERRED | RED/ERROR/BLOCKED_BY_NAVIGATION | `resumed_with_result`；据本轮证据分诊，不因上轮没文件算新问题 | 是 |
| 任意开放状态 | ID 明确从 inventory 删除 | `stale` | 否 |
| 任意开放状态 | ID 仍在 inventory，但本轮无 runner 结果 | 先保留静态/实际终态，真实导航依赖失败则 blocked；有调度证据则 DEFERRED；其余 ERROR/INFRA或SETUP | DEFERRED 否，其余是 |

`fixed` 的唯一依据是本轮显式 GREEN，且满足 §二。`stale` 需要 inventory 明确证明测试已删除或稳定改名；runner 没有打印该用例不等于 stale。

### Regression

某 ID 在任一历史轮有显式 GREEN，本轮又成为 RED/ERROR，且上轮不是 blocked，标 `regressed`。Regression 是时间维度，不是新的 `failure_class`；仍按当前证据分到六类首因，不自动降为 manual review，也不自动回滚其他已修结果。

## 七、`_ui_delta.md`

round-1 起写 `spec/verify/ui/round-N/_ui_delta.md`：

```markdown
# Round {N} ui delta（vs round-{N-1}）

> verifier source: arkts-ui-verifier
> 设备与应用：{device / bundle}
> runner 原始汇总：{Tests run / Pass / Failure / Error / Ignore}

## ✅ Explicitly fixed

本轮真实执行且该功能点全部必需 UI 后置条件通过：
- {id}

## 🔓 Unblocked and executed

- {id}: {GREEN | RED | ERROR}（上轮 blocked，本轮已实际执行）

## 🆕 Newly opened root causes

- {root_id} [{kind}][{failure_class}] — 影响 {N} 个用例

## 🚨 Regressed

- {id} [{failure_class}] — 曾显式 GREEN，本轮重新失败

## ⛔ Navigation blocked

- {navigation_root_id} [{root_failure_class}]
  - 首个失败步骤：{failed_step}
  - blocked dependents：{N}
  - {dependent ids}

## 🔁 Still failing root causes

- {root_id} [{kind}][{failure_class}] — 影响 {N} 个用例

## ↪ Referred, no product edit

- {id} [SETUP|INFRA|UNREACHABLE_BY_UI] — {owner/recommended layer}

## 🪦 Stale

- {id} — 已确认不在当前 case inventory

## 用例最终状态

| 状态 | round-{N-1} | round-{N} | Δ |
|---|---:|---:|---:|
| GREEN | x | x | ±x |
| RED | x | x | ±x |
| ERROR | x | x | ±x |
| BLOCKED_BY_NAVIGATION | x | x | ±x |
| DEFERRED | x | x | ±x |

## 独立首因

| failure_class | round-{N-1} | round-{N} | 受影响用例数 |
|---|---:|---:|---:|
| NAVIGATION | x | x | x |
| SETUP | x | x | x |
| FUNCTION | x | x | x |
| INFRA | x | x | x |
| IMPL_MISSING | x | x | x |
| UNREACHABLE_BY_UI | x | x | x |
```

空 section 写“无”，不要省略，以便机器和人都能区分“没有”与“未计算”。

## 八、收敛与 `_state.yaml`

```yaml
schema_version: 2
current_round: <N>
last_verifier_run_at: <ISO 时间戳>
last_verifier_source: arkts-ui-verifier
loop_status: running | paused | passed | failed | stalled
max_rounds: 10
no_progress_rounds: 0
```

收敛规则：

- `passed`：case inventory 中每个 ID 本轮都有显式 GREEN，且最终包每个必测页面有本轮成功准入和全部所需业务/清理证据，不存在额外的 `UNREACHABLE_BY_UI` 页面记录、RED、ERROR、BLOCKED_BY_NAVIGATION 或 DEFERRED。
- `running`：仍有独立首因，且本轮至少发生一项有效进展。
- `stalled`：达到主线程配置的连续无进展阈值。
- `failed`：达到 `max_rounds` 仍有非 GREEN，或出现不可恢复的执行失败。

有效进展至少包括以下之一：

- 一个独立首因由开放变为显式 GREEN；
- 一个或多个 blocked 用例恢复为可执行，并得到真实 GREEN/RED/ERROR；
- 显式 GREEN 用例数增加；
- `INFRA/SETUP` 首因被解决，使此前没有产品判定的用例得到有效判定。

仅修改文件、减少问题文件数、把 RED 改成 blocked、或把多个问题隐藏到 disposition 不算进展。`no_progress_rounds` 依据上述语义更新，而不是只比较问题文件数量。

## 九、边界情况

| 情形 | 处理 |
|---|---|
| 前期与最终包 | 独立 round/build；最终轮引用 precheck_ref，逐页真实准入，不复制旧 PASS，也不要求先跑独立全量导航 |
| 修复、重新安装、崩溃恢复 | 新 round/会话，旧页面准入失效；最终阶段按页真实点击重新准入，前期按导航诊断回归；不混入旧轮 GREEN |
| 前期导航未完成 / 最终实际到页失败后暂停 | 按明确调度证据将未开始项记 DEFERRED/NAVIGATION_GATE；不将未生成的未知业务伪造成 outcome |
| 前例清理失败导致主动停批 | 保留前例业务/清理结果，未开始项 DEFERRED/SESSION_UNSAFE，不制造功能 RED |
| 构建/安装在任何 preflight 前失败 | 所有尚无静态终态的 RUNNABLE nav/function/journey ID 各写一次 ERROR/INFRA；不派生 blocked |
| runner 崩溃，只得到部分结果 | 已明确结果照常写；已有明确失败的 canonical root 才让其无终态 dependents blocked，否则剩余无终态 ID 写 ERROR/INFRA；每个 ID 恰好一种终态 |
| 测试过滤或 Ignore | 若仍在 inventory，写 ERROR/SETUP 并解释过滤原因 |
| 产品存在合法 locator，但测试未命中且 UI 证据显示结果存在 | 根因 SETUP，转 verifier/test；不改产品 |
| 必需操作或 landmark 无产品已有稳定唯一 ID，且无唯一可见文本/合法关系语义 locator | 只写一份页面级 `ERROR/UNREACHABLE_BY_UI`，移出 runnable UI inventory，转 UT/集成或人工验证；不生成 flow/test 或下游 blocked，不注入 ID 或坐标硬点 |
| 账号、网络、权限或真实预置数据不满足 | 按证据归因；不伪造测试条件。未按测试契约准备环境归 ERROR/SETUP，外部网络/设备服务不可用归 ERROR/INFRA；不能仅凭事件名直接分类 |
| `NETWORK_OFFLINE` | 若 Spec 正在验证离线体验且已通过真实条件进入业务操作，UI 结果错误归 RED/FUNCTION；测试未建立声明的网络状态归 ERROR/SETUP；非预期外部断网导致无法判定产品归 ERROR/INFRA |
| navigation root 为 SETUP/INFRA | 下游仍记 BLOCKED_BY_NAVIGATION，但首因聚合到 root 的 SETUP/INFRA |
| navigation root 恢复 | 下一轮逐条真实执行 dependents；blocked 文件消失本身不能 fixed |
| 持久化即时 UI 正确，重进/重启后错误 | 同一功能点 RED/FUNCTION；证据写明生命周期边界后的 UI 观察 |
| 逻辑无任何公开 UI 路径/结果，或无法形成合法唯一语义 locator | 单一 ERROR/UNREACHABLE_BY_UI，移出 runnable UI inventory，转 UT/集成或人工验证；不生成伪测试或 blocked 记录 |
| spec 改名 | 只有 case inventory 明确删除旧 ID 时旧项 stale；新 ID 独立处理 |
| regression | 当前轮重新分诊 failure_class；不自动回滚或永久跳过 |

## 十、自检

先运行真实的文件存在性检查；将 `N` 替换为实际轮次：

```bash
N=0
ROOT="spec/verify/ui"
ROUND_DIR="$ROOT/round-$N"

test -d "$ROUND_DIR/ui" || echo "❌ 缺 ui 问题目录"
test -d "$ROUND_DIR/evidence" || echo "❌ 缺 evidence 目录"
for f in _ui_index.md _ui_summary.md; do
  test -f "$ROUND_DIR/$f" || echo "❌ 缺 $ROUND_DIR/$f"
done
[ "$N" -eq 0 ] || test -f "$ROUND_DIR/_ui_delta.md" || echo "❌ 缺 _ui_delta.md"

for f in planned-feature-inventory non-runnable-page-records case-inventory case-outcomes navigation-observations run-context page-admissions session-events; do
  test -f "$ROUND_DIR/evidence/$f.json" || echo "❌ 缺 $f.json"
done

state_round=$(awk '/^current_round:/{print $2; exit}' "$ROOT/_state.yaml")
[ "$state_round" = "$N" ] || echo "❌ _state.yaml current_round 未更新"
```

随后由 execute agent 使用项目已有校验器或编写本轮小型校验脚本完成以下语义检查，并归档命令与输出；这些是检查要求，不是本 skill 提供的可执行命令：

- 四份 inventory/record/outcome JSON 均符合 §一 schema；设计 §B、planned、case、实际 `it()`、注册表、outcome 的稳定 ID 与 owner 单向一致，writer 必需字段完整。
- 每个 case inventory ID 恰有一条 outcome；静态项不要求测试文件，但必须有正确合成终态。额外 ID 只能是已声明的页面记录或共享 infra 根。
- 每页不可自动化记录的 affected planned ID 集合准确，无重复，无误排除其他可执行功能。
- gate 的 required/passed 集合及指纹匹配本轮全部必测路径；FUNCTION 无越门执行，主动 DEFERRED 均有调度证据，且不掩盖真实基础设施中止。
- navigation observations 的 invocation ID/ordinal 唯一；最终 flow 结果符合 §三聚合规则，pending 不伪装 GREEN，业务已完成结果不被之后的导航失败覆盖。
- `blocked_by` 与 `cause_id` 互斥、无自引用、无链式引用，均指向本轮相应根文件；各根 `affected_test_ids` 与反向引用集合相等。
- 同 ID 开放问题正确 carry disposition；GREEN 必须来自本轮显式有效执行，不能由文件缺失推断。
- summary 的用例状态、独立首因和 affected planned 数能从账本重算；额外 root 不混入用例分母。所有失败必须在交付报告中明确呈现，不能把存在性检查当作语义验证通过。
