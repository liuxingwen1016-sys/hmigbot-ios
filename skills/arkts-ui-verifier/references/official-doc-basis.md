# UiTest 官方依据与本 skill 工程约定

本文件用于区分 OpenHarmony 可验证事实与 `arkts-ui-verifier` 自己的测试设计约定。设计、生成或审查 UiTest 代码时先读取项目 SDK 版本，再选择对应分支的 API 文档。

## 来源级别

### OpenHarmony 官方文档

- [UI 测试框架使用指导](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/application-test/uitest-guidelines.md)
- [@ohos.UiTest API 参考](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-test-kit/js-apis-uitest.md)
- [Hypium 单元测试框架使用指导](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/application-test/unittest-guidelines.md)
- [OpenHarmony 6.1 Release 版本说明](https://github.com/openharmony/docs/blob/master/zh-cn/release-notes/OpenHarmony-v6.1-release.md#L345-L353)

`openharmony/docs` 是这里用于 API 与使用方式判断的官方来源。

### 用户指定资料

- [openharmony-rs/openharmony-docs 对应指南](https://github.com/openharmony-rs/openharmony-docs/blob/8d6568a7330d24ca8f2457d65df40979941f127b/zh-cn/application-dev/application-test/uitest-guidelines.md)
- [testfwk_arkxtest/uitest/AGENTS.md](https://github.com/openharmony/testfwk_arkxtest/blob/68a54e0b15a0d1eb21778316be7fd9e51ad67a96/uitest/AGENTS.md)

第一项是社区镜像，不替代 `openharmony/docs` 官方版本。第二项位于 OpenHarmony 框架代码仓，但内容面向框架贡献/实现上下文；它可以佐证 client-server、组件查找和输入事件模拟机制，不能证明应用测试应采用某种 Page Object、目录或用例拆分方式。

## 可直接采用的官方事实

### 启动、操作、断言构成 UI 测试闭环

官方示例先通过 AbilityDelegator 启动被测 Ability 并确认 top Ability，再用 `findComponent` 找到页面组件、执行 `Component.click()`，最后断言点击后的页面变化。参见 [UI 测试示例](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/application-test/uitest-guidelines.md#L225-L300)。

由此可确认：

- 初次启动可以由 AbilityDelegator 完成，不要求启动动作本身来自应用页面组件。
- 应用 UI 交互可以采用“查找组件 → 组件操作 → 页面结果断言”。
- 断言应指向操作后的实际页面变化，而不是只确认应用仍在运行。

“应用内所有页面都必须逐跳组件点击”是本 skill 为保证黑盒真实性而采用的约定，不是该示例明文规定。

官方应用样例中也存在为验证 UiTest API 而直接启动专用 `clickAbility`，再由该 Ability `loadContent('pages/Click')` 的做法，见 [`clickEvent.test.ets`](https://github.com/openharmony/applications_app_samples/blob/a826ab0e75fe51d028c1c5af58188e908736b53b/code/Project/Test/uitest/entry/src/ohosTest/ets/test/operationExampleTest/ui/clickEvent.test.ets#L26-L37) 与 [`ClickAbility.ts`](https://github.com/openharmony/applications_app_samples/blob/a826ab0e75fe51d028c1c5af58188e908736b53b/code/Project/Test/uitest/entry/src/main/ets/clickability/ClickAbility.ts#L30-L39)。这类案例在验证框架操作能力，不等同于应用业务 E2E 的真实用户到页。为防止遗漏中间页、守卫和参数，本 skill 明确不采用这种目标页直挂方式。

### 控件查找与用户操作

官方指南说明 UiTest 可通过 `On` 的多个属性构造 matcher，查找一个或多个组件，并对 `Component` 操作或读取属性；示例包含 `findComponent`、`findComponents` 与 `within`。参见 [控件查找与操作](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/application-test/uitest-guidelines.md#L303-L342)。

官方入门示例也直接使用 `findComponent(ON.text('Next'))` 找到可见文本组件，再执行 `await next.click()`；`ON.text` 默认按 `EQUALS` 匹配，`Component.click()` 是正式异步 API。参见 [指南示例](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/application-test/uitest-guidelines.md#L118-L124)、[`On.text`](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-test-kit/js-apis-uitest.md#L382-L423) 与 [`Component.click`](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-test-kit/js-apis-uitest.md#L1359-L1394)。因此，没有产品 ID 时直接按设备实际可见文本定位并点击，是框架原生支持的方案，不需要先向生产组件注入测试 ID。

API 还支持组件 click/longClick/input、滚动查找及坐标级输入。坐标操作是框架能力，但“常规导航只点击可语义定位的可见组件，不使用坐标硬点”是本 skill 的稳定性约定。

官方文档证明 `On` 可以按组件属性或关系查找，并不要求测试为了定位而修改生产组件。基于用户的黑盒边界，本 skill 的 locator 约定是：优先复用产品已有且稳定唯一的 ID；没有 ID 时使用 `ON.text(...)` 定位设备当前语言下的唯一可见文本，文本重复时只在唯一可见容器语境内用受版本支持的关系 matcher 消歧。若必需操作或 landmark 仍无法形成合法唯一语义 locator，则按本 skill 工程策略只登记一份页面级 `ERROR/UNREACHABLE_BY_UI`，移出 runnable UI inventory，转 UT/集成测试或人工验证；不生成伪 flow/test 或下游 `BLOCKED_BY_NAVIGATION`，不新增生产 ID、ID manifest，也不用坐标或内部状态绕过。

### 页面加载等待

官方指南明确，页面交互后可以等待目标控件出现或等待页面空闲来判断加载/跳转进度，示例用 `waitForComponent` 等首页特征控件。参见 [页面加载等待](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/application-test/uitest-guidelines.md#L385-L412)。

- [`waitForComponent`](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-test-kit/js-apis-uitest.md#waitforcomponent9) 持续查找匹配组件，适合等待目标 UI surface 的 landmark。
- [`waitForIdle`](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-test-kit/js-apis-uitest.md#waitforidle9) 判断控件树是否在指定时段保持无变化。它只能说明界面稳定，不能证明当前是哪一页。

因此本 skill 规定：到达目标 UI surface 以该 surface 的唯一可见 landmark 为主判据；`waitForIdle` 仅辅助并检查返回值。目标 UI surface 可由被测应用、系统 UI 或系统宿主呈现，这是本 skill 对真实产品入口的建模，不是上述官方段落对应用目录或入口类型的额外规定。固定 `delayMs` 是合法 API，但条件等待优先是本 skill 的稳定性约定，并非官方禁用固定延时。

### 页面变化后重新定位组件

官方 FAQ 把“does not exist on current UI! Check if the UI has changed after you got the widget object”归因于：取得控件后设备界面又发生变化，导致该控件丢失、后续模拟操作失败。参见 [指南 FAQ](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/application-test/uitest-guidelines.md#L1021-L1033) 与 [`Component.click`](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-test-kit/js-apis-uitest.md#click9)。

据此，本 skill 进一步规定生成代码在每次 UI surface 或控件树变化后通过 selector 获取新的 `Component`；这是稳定性约定，不冒充官方原文。

### API 命名、异步与并发

API 9 及以上使用 `Driver`、`ON`/`On`、`Component`；API 8 的 `UiDriver`、`BY`/`By`、`UiComponent` 从 API 9 起废弃。当前官方示例从 `@kit.TestKit` 导入 `Driver`、`ON`、`Component`。参见 [API 总览](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-test-kit/js-apis-uitest.md#ohosuitest)。

`Driver.create(): Driver` 同步返回 Driver；除 `create`、`createUIEventObserver` 外的 Driver 方法以及全部 Component 方法均为 Promise。参见 [`Driver` API](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-test-kit/js-apis-uitest.md#L2603-L2623) 与 [`Component` API](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-test-kit/js-apis-uitest.md#L1353-L1363)。错误码 `17000002` 明确指出 UiTest 不支持并发调用，漏写 `await` 也会造成并行错误。参见 [UiTest 错误码](https://github.com/openharmony/docs/blob/f41b9345badd47c7ab0c263344cd7f4b5a549afb/zh-cn/application-dev/reference/apis-test-kit/errorcode-uitest.md#L32-L47)。因此所有异步操作必须逐个 `await`；同一 Driver/设备上的 UI 操作不得用 `Promise.all` 并发。

### Hypium suite 与 case

官方 Hypium 指南用 `describe` 定义 suite、`it` 定义一条 case，并提供 `beforeEach`/`afterEach` 做每例前置与清理。参见 [测试脚本结构](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/application-test/unittest-guidelines.md#L43-L93) 与 [测试函数](https://github.com/openharmony/docs/blob/master/zh-cn/application-dev/application-test/unittest-guidelines.md#L257-L274)。

这些套级和用例级钩子可以承载页面 beforeAll 准入、beforeEach 基线检查与 afterEach UI 清理。按页复用运行中应用、全局导航修复门和重启例外是本 skill 的执行约定，不是框架保证；实际 harness 是否保持被测进程必须在目标设备验证。

“一个 `it` 只验证一个功能点”是本 skill 的可维护性规则；官方 API 并未限制每个 case 只能调用一个操作或一个断言。

## SDK 版本门禁

项目代码是版本判断起点：先读根 `build-profile.json5` 的 `compatibleSdkVersion` 与 `targetSdkVersion`，再查匹配版本的官方 API 文档中每个符号的 `since`/`deprecated`。

- OpenHarmony 6.1 Release 的 Public SDK 是 API Version 23，见 [官方版本配套表](https://github.com/openharmony/docs/blob/master/zh-cn/release-notes/OpenHarmony-v6.1-release.md#L345-L353)。
- `master` 是开发中最新文档，可能包含 API 26 能力。不能因为 `master` 有某个 matcher、事件或输入 API，就假定 API 23 或项目 compatible SDK 已支持。
- 如果 `compatibleSdkVersion` 低于某 API 的 `since`，设计必须选择兼容 selector/操作或明确标 blocker；不得等到编译阶段才发现。

## 本 skill 的工程约定

以下规则服务于真实、稳定、可维护的黑盒 UI 验证，但不能写成“OpenHarmony 官方要求”：

1. 需要默认应用入口的 `IN_APP` flow 才用 AbilityDelegator 进入产品正常入口；外部 flow 服从其真实 `start_context`。flow 中每条 UI edge 都由当前 surface 上真实可见组件驱动，目标 surface 不预设属于被测应用、系统 UI 或系统宿主中的哪一方。
2. 每个目标页/surface 有一份 canonical entry flow，每跳等待下一 UI surface 的唯一可见 landmark；`entry_kind` 按真实触发链选择，不以目标 surface 的宿主决定合法性。
3. `navigation/to_<target_short>/` 集中所有入口的 reachability flow 与同 ID preflight，包括 `IN_APP`/`SYSTEM_ENTRY`/`DEEPLINK_ENTRY`/`CROSS_APP_ENTRY`；`pages/<page_short>/` 聚合 Page Object 与页面功能测试，`journeys/` 仅保存必须跨页才能验证的业务结果。
4. 一个 `it()` 验证一个功能点；多个断言可以共同证明同一结果。
5. locator 优先复用产品已有 stable ID；没有 ID 时使用唯一可见文本，必要时用受版本支持的关系 matcher 在唯一可见容器内消歧；不得为测试修改生产组件，常规导航不使用坐标。
6. 默认只断言用户可观察 UI，不读取应用内部状态。
7. 全部必测导航及 UI 恢复路径通过后才进入页面功能阶段；普通批次按页复用应用会话、逐例通过 UI 恢复状态。页面导航失败、业务失败和受控暂缓分别报告；完整规则见 `execution-session-contract.md`。
8. 系统、deeplink、跨应用入口也由真实可见组件点击触发；只允许正常默认入口启动来建立起点，不直接调用公开 URI/目标 Ability 代替链接或入口点击。这是用户要求的黑盒约束，不是框架 API 的能力限制。

## 设计核对表

- [ ] 事实性 API 结论来自官方文档，用户指定镜像与框架 AGENTS 未被称为应用测试规范。
- [ ] 已记录项目 compatible/target SDK，并核对实际使用 API 版本。
- [ ] 默认应用入口与外部/跨 surface `start_context` 的边界清楚，不强迫所有 flow 先启动或最终进入被测应用。
- [ ] 到达判定使用目标 UI surface 的唯一可见 landmark，并明确 surface 属于被测应用、系统 UI 或系统宿主；`waitForIdle` 没有替代 surface 身份断言。
- [ ] locator 只复用产品已有 stable ID；无 ID 时使用唯一可见文本或合法的唯一可见容器语境；无法形成合法唯一 locator 时已只写页面级 `ERROR/UNREACHABLE_BY_UI`，移出 runnable UI inventory 并转其他测试层/人工，未生成测试或 blocked 记录。
- [ ] 所有入口 reachability flow/preflight 都位于 `ui/navigation/to_<target_short>/`；`ui/journeys/` 只包含跨页业务结果。
- [ ] UI surface 或控件树变化后重新定位组件，异步操作逐个 await，设备 UI 执行不并发。
- [ ] Page Object、目录和一例一功能点明确标为本 skill 工程约定。
