# 导航门槛与按页会话执行契约

设计、生成、执行、fixer 和 reconcile 共用本契约。它规定执行顺序、应用会话边界和主动暂缓的记账方式；具体 UiTest API 仍以项目 SDK 为准。

## 统一工作目录

项目内所有 UI 验证资料统一以 `spec/verify/ui/` 为根，所有角色使用同一组路径：

| 产物 | 唯一路径 | 写入者 |
|---|---|---|
| 当前页面/Android 映射 | `plan/page-source-map.json` | 主线程合并各角色建议 |
| 当前导航设计 | `plan/navigation/P{NNNN}_{PageName}.md` | NAVIGATION designer，PAGE_SCOPE 互斥 |
| 当前页面功能设计（含 Dialog/journey 定义） | `plan/pages/P{NNNN}_{PageName}.md` | FUNCTION designer，PAGE_SCOPE 互斥 |
| 当前用户报告 | `ui-report.md` | execute/reconcile，正文反映当前状态 |
| 跨轮调度状态 | `_state.yaml` | 主线程/账本 owner |
| 本轮计划快照、清单、日志、截图与执行观察 | `round-N/evidence/` | 单一 execute/账本 owner |
| 本轮问题与汇总 | `round-N/ui/<id>.md`、`round-N/_ui_*.md`、`round-N/fixer-summary-ui.md` | 对应 execute/reconcile/fixer owner |

表内路径相对此统一根；`round-N`、`plan/pages`、`plan/navigation` 的简写也均相对此根。`SKILL_ROOT/references/` 是 skill 的模板，不是项目产物目录；`entry/src/ohosTest/ets/test/ui/` 才是可执行测试源码根，两者不能混用。

每轮冻结输入时，将该轮实际使用的 `plan/page-source-map.json`、导航/功能设计复制至 `round-N/evidence/plan-snapshot/`，保留 plan 内相对层级，并在其中的 `snapshot.json` 记录文件列表、原始规范路径、快照相对路径、内容 sha256、mapping_revision、phase。该快照之后只读；NAVIGATION 只冻结映射和导航设计，不等待尚在编写的功能设计。当前计划可以迭代，但不能改写已封存轮次的证据。

生成 agent 读取当前 plan；execute/reconcile 的本轮结论及 fixer 的失败依据读取对应 round 快照。inventory 的 `design_source` 保留当前规范路径用于按稳定 ID 追溯，并由该轮快照提供当时内容；结果的 evidence 引用本轮归档路径。重测必须按当前计划和映射复核，不能用旧快照代替最新输入。源码原件仍在 Android/鸿蒙项目中，快照仅保存计划及其源码引用/哈希，不复制整个项目。

## 1. 模式与授权

| MODE | 导航未通过 | 导航通过后 |
|---|---|---|
| `verify_only`（默认） | 输出问题并停止，不修改产品 | 运行页面功能并报告，不自动修业务 |
| `verify_nav_fix` | 先修证据明确的到页产品缺陷，重编并全量导航回归 | 运行页面功能并报告，不自动修页内业务 |
| `verify_fix` | 先完成同样的导航修复循环 | 再对业务产品 RED 做受限修复回归 |

“先修好全部到页，再测各页面”选择 `verify_nav_fix`；用户另行要求修业务失败才用 `verify_fix`。测试 locator/helper 的修正由 verifier 的设计/生成 owner 完成，产品修理由具名 fixer 完成。环境、账号、不可自动化问题不转成产品修改；无法安全处理时停止并请求所缺条件。模式不授权添加 ID、测试入口、内部路由旁路或伪造数据，也不授权提交 Git。

## 2. 前期并行、最终包与逐页准入

```text
页面/Android 源码映射 → 导航设计与最小导航测试包
                         ├─ 全量导航执行 → 到页问题分诊/修复/回归
                         └─ 按页读取映射和 Android 源码 → 功能设计与测试编写
                         ↓ 两分支均完成，映射与草稿复核，冻结输入
                    构建安装最终测试包
                         ↓
            点击到页 → 确认 landmark → 本页功能 → 清理/切换下一页
```

- 前期 `PHASE=NAVIGATION` 只依赖完整导航设计、映射与导航工件，不依赖完整功能计划/测试。设备单一执行者运行已安装的固定导航包；其他 agent 在各自页面范围编写功能测试，不操作设备、不改共享导航/helper/注册或生产代码。
- 页面功能编写按需使用多 agent，MAX_PAGE_AGENTS=8；SOURCE_CONFIRMED 且设计就绪的页面入队，每 agent 一次一个 PAGE_SCOPE，完成即补位直至全量完成。同页设计与生成串行，若设计也并行则共享该 8 槽池；共享导航/映射/注册单 owner。主线程记账 ownership、版本、完成/阻塞/失效状态，未完成或失效稿不能进入最终构建。
- 全部必测到页及返回/切换路径必须在同一导航包、导航计划与设备配置下完成预检；真实问题按测试 SETUP、产品 NAVIGATION/IMPL_MISSING 或环境 INFRA 分诊。产品修复受 MODE/FIX_SCOPE 授权约束，不通过修改 selector、预期或添加测试入口掩盖。
- 导航构建使用不可变的导航输入快照，仅纳入已闭合的生产、harness 和导航工件；共享 owner 在受控的独立构建工作副本中准备，不删除工作区页面草稿，也不靠注释/Ignore 隐藏最终计划。前期修复重编只同步其导航快照所需的完成输入，不把正在编写的 Features/功能草稿带入编译。若项目无法隔离构建输入，先等待当前 writer 完成可编译交接并冻结，再重编；不得边写边构建或误把未完成草稿当产品错误。
- 前期路径未通过时继续可安全进行的其他导航诊断和页面编写；不能执行页面业务。界面不安全时停止设备操作，代码编写仍可继续。修复后重建导航包回归；共享输入变化须使相关草稿失效，由 owner 按新映射复核。
- 导航预检 PASS、全部功能设计/生成完成、单一 owner 生成 journey 并注册、映射与输入版本一致，是构建最终包的汇合条件。构建前暂停全部写入者并冻结输入快照，不能边构建边改源码。
- `PHASE=FUNCTION` 在新的 round 构建安装最终包一次，然后逐页实际准入并执行功能；不再先跑独立的全量 NAVIGATION。最终包安装允许新会话，不要求与早期导航包保持同一进程。
- 最终包每页先经 navigation 中的真实组件点击路径到达，等待唯一可见 landmark，记录该包自己的 PAGE_ENTRY 证据，然后运行该页用例、清理和切换。根页或已在本页可直接现场复核身份，不伪造点击。
- 最终执行计划以 EXPECTED_PAGES 驱动，不以已生成的 it 文件反推页面集合。没有 RUNNABLE 功能（仅静态缺口或无独立业务）的可达页面也须实际准入并记录 PAGE_ENTRY，再转下一页；不为凑页面生成伪业务 it。页面全部不可达/有未解决必测缺口时不能声称通过。
- 到页或恢复失败时停止新的业务操作，分诊并修测试或授权内产品代码，保留此前结果。修复后重新构建最终包并按页准入复测；不自动插入一轮独立全量导航。只有用户另行要求或明确改变了前期页面/导航范围，才重新安排前期诊断，不能静默扩大流程。

## 3. 预检证据与最终包证据分离

前期 `round-N/evidence/navigation-gate.json` 记录：

```json
{
  "schema_version": 2,
  "phase": "NAVIGATION",
  "round": 0,
  "build_id": "<前期主HAP与导航测试HAP指纹>",
  "plan_id": "<页面范围、导航flow与恢复路径指纹>",
  "mapping_revision": "<结构映射指纹>",
  "production_revision": "<生产源码快照指纹>",
  "navigation_revision": "<导航/helper/导航PageObject快照指纹>",
  "device_profile_id": "<设备/系统/语言与环境指纹>",
  "status": "PENDING",
  "required_flow_ids": ["NAV_P0010_FROM_APP_ENTRY"],
  "passed_flow_ids": [],
  "unresolved_entry_pages": [],
  "evidence": []
}
```

status 为 PENDING/PASS/FAILED/INVALIDATED；required 非空、与完整导航范围相等、全部有本包实测证据且无未解除缺口才 PASS。零 edge 根页也检查 landmark。映射、生产或导航输入变化后，前期快照失效，修复回归不能拼接不同包的 PASS。业务测试草稿的新增不改变导航计划，也不要求停掉已安装导航包的正常运行。

最终 `round-M/evidence/run-context.json` 记录 `phase=FUNCTION`、本轮 `build_id/plan_id/device_profile_id/mapping_revision`、完整功能计划指纹、`precheck_ref` 和 `precheck_build_id`。两种 build_id 不必相同；precheck 只证明前期工作完成，绝不复制为最终包 NAVIGATION PASS。首次合包前须对齐当前生产/导航/映射版本；最终阶段修复后的新 round 另记改动与重测范围，不能声称旧预检验收了新代码。

最终轮必须记录 `round` 和 `schema_version: 1`。`run-context.json` 还保留当前 production_revision/navigation_revision 与明确的 page_order、required_admission_flow_ids；仅前期要求的其他入口路径留在前期覆盖报告，不为最终未选 preflight 合成缺结果。

最终轮 `page-admissions.json` 以 schema_version=1/events 数组记录 `page_id/session_id/build_id/flow_id/landmark/status/evidence_refs`；status 为 PASS/FAILED，尚未入页的页面没有 PASS 记录。每条业务 GREEN 必须有当前最终包与当前会话的成功入页证据、逐例基线和真实业务/清理结果，不要求其他页提前通过。准入证据必须带顺序 ordinal 或时间及实际 flow 调用引用；用例关联其之前最近有效准入，后续成功不能倒补此前失败。已在本页/零 edge 时如实标 observed-in-place 并现场确认身份，不伪造跳转动作。

`navigation-observations.json` 仍按既有 flow ID 记录 PREFLIGHT/PAGE_ENTRY/RECOVERY；前期 PREFLIGHT 只放前期 round，最终轮只聚合本轮真实调用。不能把“本轮未选择独立 preflight”误判测试遗漏，也不能伪造 preflight 已执行。前期功能计划未齐时仅产导航账本与编写进度，不算功能通过率；最终轮再按完整 inventory reconcile。

`session-events.json` 保持 schema_version=1/events，记录 session_id、递增 ordinal、page_id、case_id、phase、kind、reason、证据路径；覆盖启动、入页、基线、清理、恢复失败和停止，保留实际进程身份证据。跨包、跨 round、崩溃后不能复用旧页面准入。

## 4. 按页复用会话，逐例隔离状态

- 一次普通功能批次保持被测应用运行；Driver 可以按 runner 会话复用，新建 Driver 也不代表应用重启。Page Object 可以复用 driver/selector 声明，但 Component 句柄及“当前页已就绪”结论不跨 UI 变化缓存。
- 页面 `beforeAll` 从当前已确认的可见界面经已验证 flow 进入本页。若已在本页且身份/环境检查通过，可原地准入；若在别页，先经已声明 UI 路径回到公共起点再到本页。不得读取内部导航栈或根据上一个测试名字猜位置。
- 每个 `beforeEach` 重新确认本页 landmark 和本例初始状态：关闭已知弹窗、恢复输入/选项或准备本例真实数据。不无条件走完整入口 flow、不调用启动/终止/复位 Ability。
- 每个 `it()` 仍只验证一个功能点。它可单独筛选运行；套级准入和本例状态建立不得依赖其他 `it()` 已执行。生命周期专项也保持独立 ID，不合并成一条巨型“点遍全页”测试。
- `afterEach` 用真实 UI 恢复本例改变的状态、关闭弹窗，并在动作导致离页时调用导航目录的恢复 flow 回到本页，最后验证基线。清理必须在业务断言失败时也尝试，但只允许已设计且当前界面可确认的有限恢复；不得盲目返回、无限重试或重启清场。
- 页面 `afterAll` 不重启、不终止应用，不新增可能失败且无法归属用例的 UI 清理；逐例清理负责基线，下一页 `beforeAll` 负责经验证的 UI 切换。
- 原业务已经 RED/ERROR 时，清理异常作为同 ID 的附加证据，不能覆盖首因。业务断言通过但清理失败时，本例最终为 `ERROR/SETUP`（设备/框架故障为 INFRA），保留业务观察已通过的证据，不声称整例 GREEN。
- 无法确认本页或恢复基线时记录 session unsafe 并停止新的业务操作。尚未执行的用例按 §6 记账；不让污染状态制造一串功能 RED。必须由明确的 UI 恢复及基线复核重新准入后才能续跑；不做 catch 后直接继续。

页面设计必须给出基线观察、可逆的 UI 准备/清理、离页后的恢复 flow 和恢复上限。删除/提交等不可逆行为使用隔离且获准的真实测试数据与回收契约；不能仅调整用例顺序来掩盖状态依赖。

## 5. 允许重启的明确例外

| 原因 | 处理 |
|---|---|
| `REINSTALL`：最终包或修复后安装新 HAP | 新 round/会话，旧准入失效；前期导航包按预检回归，最终包按页重新准入，不自动再跑独立全量导航 |
| `CRASH_RECOVERY`：有证据的应用崩溃或不可恢复进程故障（不含普通基线/清理失败） | 先保留失败及 crash 证据；允许一次受控恢复启动，不能抹掉原失败；开启新会话/round，最终阶段逐页重新准入；前期则继续导航诊断。反复崩溃时停止 |
| `LIFECYCLE_TEST`：用例明确验证冷启动/重启后持久化 | 用例设计显式声明 `persistence_boundary=relaunch` 或冷启动目标；必须真实跨应用进程/会话边界，只离页重进不算重启；放到普通页面批次之后单独执行，重启只属于该用例操作，不改 expected、不恢复待验证数据。新会话通过已验证 UI 路径回到目标页，观察完成后再清理 |

第一次正常启动记 `INITIAL_START`，不是逐例重启。以上事件均记录原因、原/新 session 与证据。生命周期专项必须实测重启后的到页路径并记录新准入，不能复用旧会话的页面 PASS；失败即暂停。专项完成后若还有普通测试，须重新建立会话与页面基线；不能沿用“当前页面”缓存。

不允许用重启替代普通 afterEach 清理，也不允许因用例失败自动重跑直到通过。若重启涉及尚未授权的数据清除、权限或外部操作，停止请求授权。

## 6. 主动暂缓不等于测试错误

保留既有 `GREEN | RED | ERROR | BLOCKED_BY_NAVIGATION`，另给 outcome 增加 `DEFERRED`，仅表示调度器明确尚未开始实际执行的用例：

- `deferred_reason=NAVIGATION_GATE`：自己的导航未失败，但因前期导航尚未完成或最终阶段实际导航失败导致调度停止而暂不运行。
- `deferred_reason=SESSION_UNSAFE`：前例清理/状态恢复失败，尚未运行的用例被安全暂停；也覆盖导航批次因界面不安全而尚未开始的 preflight，但不包括已开始后被崩溃中断的调用。
- `deferred_reason=PHASE_NOT_STARTED`：导航检查点成功后用户明确取消/仅运行导航，功能阶段未开始；必须有用户要求或调度停止证据，不能用于解释意外缺日志。
- `failure_class/blocked_by/cause_id=null`、`business_assertions_run=false`、`origin=SCHEDULER`，必须附门票或 session-events 证据。其他 outcome 的 `deferred_reason=null`。
- 自己的 canonical 导航已有实际或静态失败的下游，优先使用既有 `BLOCKED_BY_NAVIGATION`；已有业务/静态终态不覆盖。共享构建/设备崩溃导致的真实未完成运行仍为 `ERROR/INFRA`，不能以 DEFERRED 掩盖。
- DEFERRED 留在 planned/case 分母并在索引/汇总单列，不写产品问题文件，不自动交 fixer，不计 GREEN/fixed/stale，也不计独立错误首因。只有新的真实执行才能解除。
- 未知 runner 缺结果、Ignore 或意外过滤不等于 DEFERRED；没有调度器停止证据仍按原 SETUP/INFRA 规则处理。

报告分开列出前期导航预检状态、最终包页面准入/功能状态、会话与重启原因；前期全绿不等于最终包全绿。单纯功能编写仍在正常进行时记编写进度，不能凭尚无测试文件就合成 ERROR 或伪造 planned ID。
