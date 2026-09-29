# UI 测试代码模板

本模板供测试代码生成与执行验证时使用。目标是验证用户从页面声明的真实生产入口能够完成的真实操作，而不是证明测试桥能挂载某个组件。目标 UI surface 可以由被测应用、系统 UI 或系统宿主呈现；下文沿用 `Page Object` 文件命名，但它也负责封装系统/宿主 surface 上的 selector、唯一可见 landmark 与原子动作，不暗含 surface 必须属于被测应用。

先读 execution-session-contract.md 与 page-source-map.md：前期导航运行与页面编写并行；两侧完成后构建最终包，每页真实点击准入再测功能，不额外先跑独立全量导航。辅助类/方法由生成 owner 实装，不是 UiTest 自带 API。

## 1. 生成目录与职责

```text
entry/src/ohosTest/ets/test/ui/
├── support/                         # 会话、等待、SDK 适配；不放页面 selector
│   ├── UiTestSupport.ets
│   └── AppSession.ets
├── pages/
│   └── <page_short>/
│       ├── <PageName>Page.ets       # scaffold owner：导航 selector、landmark、原子动作
│       ├── <PageName>Features.ets   # page owner：页内功能/弹窗 selector 与动作
│       └── PNNNN_<PageName>.test.ets# 仅有 surface 内业务功能时生成
├── navigation/
│   └── to_<target_short>/
│       ├── from_<source_short>_<path>.flow.ets # 全部到页路径，含外部真实入口
│       └── <flow_id>.preflight.test.ets      # 同 ID 到页契约
└── journeys/                        # 可选；仅放有明确跨页业务验收的旅程
    └── <journey>.test.ets
```

职责边界：

- Page Object 独占当前应用、系统或宿主 UI surface 的 selector、唯一可见 landmark 和原子动作。它不写 `describe/it`，不决定如何从其他 surface 到达本 surface。
- navigation flow 只调用 Page Object 的动作：`IN_APP` 按真实可见组件逐跳点击，`SYSTEM_ENTRY`/`DEEPLINK_ENTRY`/`CROSS_APP_ENTRY` 使用有产品证据的真实入口触发；每一跳随后等待目标 UI surface 的唯一可见 landmark。flow 中禁止出现 `ON.id/text/type`。
- 页面测试只调用入口态恢复、canonical flow 和目标 Page Object/Features；一个 `it()` 只验证一个用户可观察功能点。
- 若“从本页点击进入下一页”本身就是该功能点，PAGE 用例可复用 `navigation/` 中对应 transition flow，并通过目标 Page Object 观察到达结果；点击与等待的编排仍集中在 navigation，不复制到 test 中。这次业务动作的失败归原 PAGE ID，不作为套级准入的导航观察。
- journeys 只在需求本身跨页时生成，不得把普通页面到达测试复制成“旅程”。
- support 不知道任何业务 selector，也不保存跨用例 `Component` 或滚动位置。

导航共享文件由 scaffold owner 先发布；page owner 在导航运行期间独占编写 Features.ets 和测试，不修改导航 Page Object/support/flow。Page Object 是逻辑角色，可拆成导航与 Features 两个文件；普通 Dialog 留在宿主页 Features/测试中。

## 2. SDK/API 探测与导入

先读项目使用的 SDK 与实际 `.d.ets`，再生成 import。不要依据旧案例猜 API：

1. 从项目 `build-profile.json5`、SDK 配置和 DevEco 当前 SDK 解析 compile/compatible API。
2. 在当前 SDK 中确认 `@kit.TestKit.d.ts` 是否导出 `Driver / ON / On / Component / abilityDelegatorRegistry`，并确认实际方法签名。
3. 把探测结果写入生成摘要；发现项目 API 与已安装 SDK 不一致时 BLOCK，不要靠 `@ts-ignore` 蒙混。

API 9+ 的默认写法：

```typescript
import { Driver, ON, On, Component, abilityDelegatorRegistry } from '@kit.TestKit'
```

`Driver / ON / On / Component` 是当前接口。API 8 的 `UiDriver / BY / By / UiComponent` 已废弃，只有项目确实锁定 API 8 且本机 SDK 声明可用时才整体切到 legacy 模板；禁止在同一文件混用两套命名。`@ohos.UiTest` 可以是 SDK 内部声明来源，但生成代码默认从 kit 聚合入口 `@kit.TestKit` 导入。

关键签名：

- `Driver.create(): Driver` 是同步工厂，写 `driver = Driver.create()`，不要 `await Driver.create()`。
- 除 `Driver.create()`、`Driver.createUIEventObserver()` 外，Driver 和 Component 操作均按 Promise 处理，逐个 `await`。
- UI 测试 API 不允许并发调用；禁止将任何 Driver/Component 操作放进 `Promise.all`、`Promise.race`、未等待的回调或自制超时竞速。

应用侧布局 dump/自动快照属于高版本能力。只有项目 SDK 与设备都达到 API 26，且当前 `.d.ets` 确实声明对应接口时才可生成；Release 6.1/API 23 等环境不得调用或用 `@ts-ignore` 假装支持。

## 3. Locator 规则（不修改生产组件）

Page Object 内按以下优先级声明 locator；证据可以来自被测应用源码/资源，也可以来自系统或宿主 surface 的运行时控件树与官方稳定界面契约：

1. `ON.id('<当前 UI surface 已暴露的 stable id>')`：被测产品可控组件必须由生产源码和运行时控件树共同证明其已存在；系统/宿主组件必须由运行时控件树及可用的稳定界面依据证明。两者都只有在当前 surface 稳定且唯一时才使用。
2. 组件没有 ID 时使用 `ON.text('<设备当前语言下的用户可见文本>')`。文本必须在当前界面唯一；若重复，只能通过 `within` 等当前 SDK 支持的关系 matcher，把它限制在唯一、可见且稳定的容器语境内。用于操作时，matcher 必须命中真实可操作的可见组件；若只能命中不可操作的文字子节点且无法按当前 SDK 关系 API 定位其操作容器，视为无合法 locator。
3. `ON.type('<源码/SDK 中确认的真实组件类型>')` 只可帮助限定可见容器语境，不能单独用来从多个同型可操作组件中猜一个。

可见文本必须能追溯到被测应用资源/源码、系统文案、宿主界面事实或运行时控件树。禁止凭空翻译、依赖列表固定下标、把通用 `Column/Row` 当 UI surface landmark、在 test/flow/support 中散落 locator；locator 变化只应修改 Page Object。

不得给生产组件新增、改写或拼接 `.id()`，不得增加 `idPrefix`、测试专用 prop 或 ID manifest。也不得用坐标硬点、内部路由、组件数组下标或内部状态绕过定位。

若某个必需操作或 landmark 既无可复用 stable ID，也无可唯一定位的可见文本/合法关系语义 locator，则不要生成猜测式 locator 或可执行 flow：

- iOS 源码确认要求且构成到页路径的入口、edge action、handler、route 或目标 landmark 根本未实现：`ENTRY_GAP` 导航根 `RED/IMPL_MISSING`。
- 已到达目标 landmark，但构造用例必需的页内业务 trigger/action/control 完全不存在：该功能点记 `IMPL_MISSING_STATIC` 并合成 `RED/IMPL_MISSING`；不生成导航根或下游 `BLOCKED_BY_NAVIGATION`。若 action/control 可执行且 expected matcher 可由 Spec/资源/UI 契约表达，即使当前结果完全未呈现也必须生成测试并真实运行。
- 存在真实页面/路径，但必需操作或 landmark 无法用上述规则唯一定位，或需求本身没有公开 UI 路径/观察面：只写一份页面级 `ERROR/UNREACHABLE_BY_UI`，移出 runnable UI inventory，转 UT/集成或人工验证。不生成 flow/test，也不生成下游 `BLOCKED_BY_NAVIGATION`。

上述“不生成/移出”只针对受影响需求与工件。canonical 路径或页面 landmark 无法定位才影响整页；仅一个页内 action/观察点无法定位时，仍保留页面 flow/preflight 和其他可执行功能。上述根问题不得通过修改生产组件来迎合测试。只有产品自身需求另行决定改善可访问语义时，才由产品流程独立处理；本 verifier 不实施此类变更。

## 4. Page Object 模板

下例将导航接口和功能接口分文件，分别由 scaffold owner 与页面 writer 维护。导航运行期间页面 writer 只写 Features 与测试，不改共享导航文件。

Page Object 不缓存 `Component`。每次操作前都重新查询；页面切换、弹窗开关、列表刷新、滚动或重渲染后，旧句柄视为失效。

```typescript
// SettingsPage.ets — scaffold owner
import { Driver, ON, On } from '@kit.TestKit'
import { waitForLandmark } from '../../support/UiTestSupport'

export class SettingsPage {
  private readonly driver: Driver

  // “设置”是设备当前语言下该页唯一可见标题；产品没有为页面根提供 ID。
  private static readonly ROOT: On = ON.text('设置')
  constructor(driver: Driver) {
    this.driver = driver
  }

  async waitUntilReady(): Promise<void> {
    await waitForLandmark(this.driver, SettingsPage.ROOT, 'settings root', 8000)
  }

}
```

```typescript
// SettingsFeatures.ets — page owner
import { Driver, ON, On, Component } from '@kit.TestKit'
import { requireComponent, waitForIdleChecked } from '../../support/UiTestSupport'

export class SettingsFeatures {
  private readonly driver: Driver
  // 已有产品 ID，只读复用；普通 Dialog 的动作也归宿主页。
  private static readonly AUTOPLAY: On = ON.id('settings_autoplay_toggle')
  private static readonly FONT_ENTRY: On = ON.text('字体大小')

  constructor(driver: Driver) {
    this.driver = driver
  }

  private async findAutoplayToggle(): Promise<Component> {
    return await requireComponent(
      this.driver, SettingsFeatures.AUTOPLAY, 'settings autoplay toggle', 5000)
  }

  async readAutoplayChecked(): Promise<boolean> {
    const toggle: Component = await this.findAutoplayToggle()
    return await toggle.isChecked()
  }

  async toggleAutoplay(): Promise<void> {
    const toggle: Component = await this.findAutoplayToggle()
    await toggle.click()
    await waitForIdleChecked(this.driver, 300, 3000)
  }

  async openFontDialog(): Promise<void> {
    const entry: Component = await requireComponent(
      this.driver, SettingsFeatures.FONT_ENTRY, 'visible font settings entry', 5000)
    await entry.click()
  }
}
```

`Component.scrollSearch()` 是长列表默认方案：先定位明确的可滚动容器，再在该容器中搜索目标。不要把有限次坐标 `swipe` 当通用搜索；确有自绘/特殊容器无法使用 `scrollSearch` 时，须在设计里记录 SDK/组件证据和边界，再在该 Page Object 中实现专用动作。

## 5. Navigation flow 模板

所有目标 UI surface 的 reachability flow 都集中在 `ui/navigation/to_<target_short>/`。每个文件表示“到某个目标 surface 的一条明确生产路径”，多条入口按路径拆文件。`SYSTEM_ENTRY`/`DEEPLINK_ENTRY`/`CROSS_APP_ENTRY` 也在这里生成 flow 与同 ID preflight；目标 surface 可位于被测应用、系统 UI 或系统宿主。`ui/journeys/` 只在到达之外还需跨 surface 验收业务结果时使用。

```typescript
import { Driver } from '@kit.TestKit'
import { HomePage } from '../../pages/home/HomePage'
import { SettingsPage } from '../../pages/settings/SettingsPage'

export const FLOW_TO_SETTINGS_FROM_HOME: string = 'NAV_P0010_FROM_APP_ENTRY'

export async function navigateToSettingsFromHome(driver: Driver): Promise<SettingsPage> {
  const home = new HomePage(driver)
  await home.waitUntilReady()
  await home.openOverflow()
  await home.chooseSettings()

  // 点击造成页面切换后，不再使用旧 Component；构造目标页对象并等待目标 landmark。
  const settings = new SettingsPage(driver)
  await settings.waitUntilReady()
  return settings
}
```

多跳 flow 必须逐跳执行 `sourcePage.<action>()` → `targetPage.waitUntilReady()`，并给每条边稳定 `edge_id`。flow 不允许直接调用 router、NavPathStack、`loadContent`、内部 ViewModel 或 AppStorage，也不允许注入测试专用目标页参数。

每条可执行 canonical flow 生成一个同 ID 的 preflight test。它完整重走 flow，并验证设计声明的 UI 返回/恢复路径；每跳记录 edge_id，失败时用首个失败 edge 作为 `failed_step`。普通 edge 不单独生成 setup `it()`；某条 edge 本身是独立需求时，另写一个业务导航用例。

## 6. 等待、串行与错误传播

```typescript
import { Driver, On, Component } from '@kit.TestKit'

export async function requireComponent(driver: Driver, selector: On,
  label: string, timeoutMs: number = 5000): Promise<Component> {
  const component: Component | null = await driver.waitForComponent(selector, timeoutMs)
  if (component === null) {
    throw new Error(`component not found: ${label}`)
  }
  return component
}

export async function waitForLandmark(driver: Driver, landmark: On,
  label: string, timeoutMs: number = 8000): Promise<void> {
  await requireComponent(driver, landmark, label, timeoutMs)
}

export async function waitForIdleChecked(driver: Driver, idleMs: number = 300,
  timeoutMs: number = 3000): Promise<void> {
  const becameIdle: boolean = await driver.waitForIdle(idleMs, timeoutMs)
  if (!becameIdle) {
    throw new Error(`UI did not become idle within ${timeoutMs}ms`)
  }
}
```

- 页面、系统 UI、宿主 surface、弹窗或菜单的到达以 `waitForComponent(target UI surface landmark)` 为主。
- `waitForIdle` 只作动画或批量重绘的辅助，必须检查返回的 boolean；它不能代替目标 landmark。
- 禁止用固定 `delayMs(500/1500/...)` 判断页面到达。只有被测需求本身包含明确时间语义（例如 debounce）时，才可使用与需求对应的时间等待，并仍断言最终可见结果。
- 不捕获 selector/点击/等待异常后返回 `null`、继续执行或静默 fallthrough。若为补充 edge 上下文而 catch，必须保留原始消息并立即重新抛出。
- 不用 setTimeout/Promise.race 给 UI API 做“可取消超时”；底层调用并未取消，会与下一次调用并发。

## 7. 按页会话与逐例 UI 基线

普通功能批次只连接运行中的应用，不主动重启。页面 beforeAll 检查最终包 run-context，经真实组件点击路径进入并确认 landmark/记录本包准入；beforeEach 重新确认页面及本例状态；afterEach 通过 UI 清理。所有页面切换/恢复编排在 navigation 内，未知界面或清理失败立即停止新的业务操作。

以下是设置页单功能点的生成形态。`AppSession` 的 attach/run-context/admission/safety/event 方法与 `enterSettingsFromObservedUi`、`restoreSettingsFromObservedUi` 都由 scaffold 根据执行会话契约和导航设计实装；不在本示例伪造生产返回按钮或默认页面位置。

```typescript
import { describe, it, expect, beforeAll, beforeEach, afterEach } from '@ohos/hypium'
import { Driver } from '@kit.TestKit'
import { AppSession } from '../../support/AppSession'
import { SettingsPage } from './SettingsPage'
import { SettingsFeatures } from './SettingsFeatures'
import { enterSettingsFromObservedUi, restoreSettingsFromObservedUi }
  from '../../navigation/to_settings/from_observed_ui.flow'

export default function P0010_SettingsPage_UI() {
  describe('PAGE_settings', () => {
    let driver: Driver
    let session: AppSession
    let page: SettingsPage
    let features: SettingsFeatures
    let originalAutoplay: boolean | null = null

    beforeAll(async () => {
      driver = Driver.create()
      session = new AppSession(driver)
      await session.attachRunningApplication() // 不调用 start/stop/reset Ability
      await session.requireFinalRunContext()
      page = await enterSettingsFromObservedUi(driver) // 真实组件点击，不猜导航栈
      await page.waitUntilReady()
      await session.recordPageAdmission('P0010') // 关联实际 flow/landmark/包与会话证据
      features = new SettingsFeatures(driver)
    })

    beforeEach(async () => {
      originalAutoplay = null
      await session.requireSafeBatch()
      try {
        await page.waitUntilReady()
        originalAutoplay = await features.readAutoplayChecked()
      } catch (error) {
        session.markUnsafe('P0010', 'baseline check failed')
        throw error
      }
    })

    afterEach(async () => {
      // 仅在本例已完成初态采集且会话允许恢复时执行；不能依赖上一例的值。
      if (originalAutoplay !== null) {
        try {
          page = await restoreSettingsFromObservedUi(driver)
          const current: boolean = await features.readAutoplayChecked()
          if (current !== originalAutoplay) {
            await features.toggleAutoplay()
          }
          expect(await features.readAutoplayChecked()).assertEqual(originalAutoplay)
        } catch (error) {
          session.markUnsafe('P0010', 'autoplay cleanup failed')
          throw error
        }
      }
    })

    it('P0010_UI_INTERACT_autoplay_toggle_changes_visible_state', 0, async () => {
      const before: boolean = await features.readAutoplayChecked()
      await features.toggleAutoplay()
      expect(await features.readAutoplayChecked()).assertEqual(!before)
    })
  })
}
```

本例只改 toggle；弹窗、输入、删除等用例按各自设计增加可逆清理，不能直接照抄它的恢复逻辑。生产 UI/真实数据契约无法提供独立基线时报告问题，不顺序依赖、不注入状态。

runner 必须把业务观察和 hook/清理观察分别归档后确定该 ID 的唯一结果：业务原失败优先保留；业务通过但清理失败不算整例 GREEN。无法安全恢复时停止新的业务操作，调度器明确未执行项用 DEFERRED；不能空返回伪通过，也不能把所有后续用例判功能失败。beforeAll 导航失败归其原 flow ID。

重新安装、崩溃恢复、冷启动/重启持久化专项是契约规定的例外；重启只到正常生产入口，然后依旧通过 UI 到页。专项安排在普通批次之后，不把重启逻辑藏入通用 beforeEach/afterEach。

## 8. 只断言用户可观察结果

允许的结果包括：目标组件出现/消失、可见文本、enabled/checked/selected 状态、列表可见项、Dialog/Menu/Sheet、通过生产导航到达的页面以及系统可见反馈。

禁止把 `AppStorage.get()`、`@State`、ViewModel 字段、数据库行、导航栈内容或“driver 不为 null”当 UI 功能验收。只有真实业务 action/control 可执行且预期 matcher 能由现有 UI 契约表达时，才按 iOS 源码证实的预期断言可见结果，让错误或缺失结果自然 RED。若目标 page/surface landmark 可达，但完成该功能所必需的业务 action/control 经源码与控件树确认完全不存在，则保留原稳定功能 ID 为 `IMPL_MISSING_STATIC`，不生成伪 action 或不可执行测试；由 reconcile 合成 `RED/IMPL_MISSING`、`test_file=null`、`business_assertions_run=false`。两种情形都不得写注定通过的替代断言。

持久化功能采用黑盒复核：

1. 在目标页通过 UI 修改设置/内容。
2. 通过真实组件离开该页。
3. 重新走 canonical flow 进入该页；若需求声明跨重启持久化，必须真实终止并重新启动被测应用并记录新会话，再按原 `entry_kind/start_context` 经真实 UI 重新建立入口后走 flow；只离页重进或重建入口不算跨重启。
4. 重新查询控件并断言 UI 显示的新状态。

一个 `it()` 只验证一个功能点。若同一动作必须同时产生多个可见结果，可在同一用例验证同一功能的必要结果；不同设置项、菜单项、CAB 动作和独立导航边分别拆开。

## 9. 生产入口分类

设计和生成必须给每页标一个入口类别：

| 类别 | 自动化方式 |
|---|---|
| `IN_APP` | 从默认应用入口开始，完全通过可见组件点击的 canonical flow 到达 |
| `SYSTEM_ENTRY` | 通过被测应用或系统宿主中的真实可见按钮、通知、分享项触发。在 `ui/navigation/to_<target_short>/` 中复现 `start_context` 并生成同 ID preflight，记录设备前置与目标 surface 的唯一可见 landmark |
| `DEEPLINK_ENTRY` | 点击真实页面上产品公开的可见链接组件；在 `ui/navigation/to_<target_short>/` 中生成 flow/preflight，不得直接启动 URI/Want 代替点击 |
| `CROSS_APP_ENTRY` | 通过另一应用中的真实可见操作触发；在 `ui/navigation/to_<target_short>/` 中生成 flow/preflight 并记录两端入口与环境前置 |
| `ENTRY_GAP` | iOS 源码确认要求生产入口但产品未实现；不生成 flow/test，登记 `RED/IMPL_MISSING` 导航根 |
| `UNREACHABLE_BY_UI` | 没有应用内点击路径/可验证的生产外部入口/UI 观察面，或必需操作/landmark 无合法唯一语义 locator；只写 `ERROR/UNREACHABLE_BY_UI`，移出 runnable UI inventory，不生成 flow/test 或 blocked 记录 |

`SYSTEM_ENTRY`/`DEEPLINK_ENTRY`/`CROSS_APP_ENTRY` 必须有 `module.json5`/skills 配置、跨应用产品链路或产品文档证据，但不是组件点击规则的例外。内部页面名、router URL、NavPathStack route 不是“生产深链”；即使 URI 已公开，也不能用 shell/Want/接口直达目标替代真实链接点击。只能正常启动应用/宿主默认入口建立起点。
这三类的到页 flow 和 preflight 与 `IN_APP` 一样都属于 `ui/navigation/to_<target_short>/`。只有另一个业务功能必须跨页验收结果时，才另写 `ui/journeys/` 用例。

## 10. 常见反模式

| 反模式 | 正确做法 |
|---|---|
| `await Driver.create()` | `Driver.create()` |
| EntryAbility / router / NavPathStack / loadContent 测试桥直达目标页 | `IN_APP` 启动默认 Ability 后走 canonical click flow；外部入口重建其设计声明的真实生产触发 |
| `__TARGET_PAGE__`、`__TEST_MODE__`、Service AppStorage 旁路 | 使用生产 UI 与显式真实环境前置 |
| 为测试给生产组件新增/改写 `.id()`、`idPrefix` 或 ID manifest | 只复用产品已有 stable ID；没有 ID 时使用唯一可见文本或唯一可见容器语境 |
| 无 stable ID/唯一可见文本/合法关系语义 locator 时用坐标、下标或同型组件猜测 | 只登记一份 `ERROR/UNREACHABLE_BY_UI`，移出 runnable UI inventory 并转其他测试层/人工；不生成测试或 blocked 记录 |
| selector 散落在 test/flow/support | 全部移入目标 Page Object |
| 点击后继续使用旧 `Component` | 等新 landmark，并重新查询目标组件 |
| `if (comp) { ... }` 导致未命中也 PASS | `waitForComponent` + 必要断言，失败立即结束 |
| 固定 delay 判断到页 | 等目标 landmark；idle 仅辅助且检查 bool |
| `Promise.all` 或超时 race 包 UI API | 每次只发一个 UI 调用并 `await` |
| catch 后忽略 | 直接传播，或补充上下文后 rethrow |
| 默认坐标 swipe 搜索长列表 | 找到 Scroll/List 容器后 `Component.scrollSearch` |
| 继承上个 it 的滚动/开关/导航状态 | 页准入一次；每例重新确认并通过 UI 准备/恢复本例基线，失败停止新业务 |
| 每例启动/终止/复位应用来清场 | 普通批次复用应用会话；只在声明的三类重启例外中重启 |
| AppStorage 双重断言 | 离页/重进/重启后从 UI 验证持久化 |
| 编译不过就注释注册或 Ignore | 修结构；仍失败则计入 infra/ERROR 分母 |

## 11. ArkTS 编译约束

- 所有变量、返回值和集合写明确类型；不用 `any/unknown`。
- 不在 `it()` 内定义嵌套函数；共享逻辑放 Page Object/support。
- Want 使用 SDK 声明的类型并带项目实际 `bundleName/moduleName/abilityName`。
- 对 `waitForComponent` 的返回类型按当前 SDK 声明处理；不要以 `@ts-ignore` 覆盖版本差异。
- `List.test.ets` 由单一 register owner 按实际 `*.test.ets` 确定性重建，不并发追加。
