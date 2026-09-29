# HMigBot 1.6.1 架构核对与 iOS 改造边界

核对日期：2026-09-29。对象是用户提供的独立HMigBot CodeX 1.6.1发行目录，非HMigBot Plus。以实际文件为准：99份SKILL.md、31份agent TOML；README的90技能/7角色是旧口径。

## 运行结构

HMigBot不是Python流水线程序。Codex读取技能规程完成判断、派发与编码；技能中的确定性校验器检查产物。`bin/a2h`是阶段标记、行数和遥测客户端，不负责语义转换或调度模型。`agents-codex`保存领域角色和写入职责，安装后位于`.codex/agents`；技能位于`.agents/skills`；项目配置和运行时位于`.migbot`。

原`a2h-run`依次执行`a2h-spec → a2h-plan → a2h-execute → a2h-verify → a2h-retrospect`，根据同一组产物恢复。原来按阶段确认；当前用户已授权持续施工或持续迁移时使用已有授权，不重复要求确认。阶段记录只是恢复线索，实际检查失败不能因文件存在被当成通过。

## 五阶段与数据协议

| 阶段 | 关键步骤 | 原产物及消费者 |
| --- | --- | --- |
| spec | 源仓分析；Phase 0模块依赖；Phase A页面证据；Phase B UI；Phase C功能和决策 | `spec/ref`、`baseline/ui-manifest.md`、`ui/page_*.md`、`ui-snapshots/*/meta.json`、`feature-index.md`、`feature-base.md`、`features/F*.md`、API清单、decision-ledger；plan读取 |
| plan | P0归属/拓扑裁决；UI、Base、slice各有写入者；P2汇总和覆盖 | `baseline/plans/ui-plan.md`、`feature-plan.md`（indexed-v1）、`base-plan.md`、`slices/*`、`coverage-matrix.md`、`placeholder-registry.md`；execute读取 |
| execute | Stage 0资源；Stage 1 UI批次；Stage 2 Base；Stage 3逐功能与组接线；最终结构闭包 | 实际ArkTS、`execution/briefs`、source-understanding、writeback、`migration-report.md`；verify读取 |
| verify | 静态/身份、按范围视觉和UT；源oracle、测试设计/生成/执行；失败修复 | `spec/verify-report.md`及各verifier原始结果，PASS/FAIL/PARTIAL/DEFERRED/SKIP分别保留 |
| retrospect | 对实际问题归因；确定性经验/项目决策沉淀；代码行数和阶段水位 | `docs/retrospect-report-*.md`、原运行时生成的阶段记录；run恢复 |

共同控制面：`spec/.a2h/open-findings.json`由每个检查器只更新自己section；`requirements-index.json → plan-coverage.json → impl-claims.json → verification.json`实现AC级对账。稳定AC ID、源/决策锚点、判定强度、独立真值来源不能换成旧适配器自建contract。页面/功能状态由execute唯一回写；plan只读；brief记录完成证据。

## iOS 必须替换和保留的接口

| 原实现中的源端假设 | iOS处理 | 保留内容 |
| --- | --- | --- |
| AndroidManifest/Gradle/Activity/Fragment/Compose | Xcode target/scheme/配置、SwiftUI App/View、UIKit控制器、Storyboard/XIB、扩展、Objective-C桥接 | feature/page ID、spec目录与模板结构 |
| Kotlin/Java源锚点 | 真实Swift/ObjC/IB路径；声明source_platform=ios | 使用通用 `source_anchors`；真实原消费者已验证兼容，不保留误导性的旧源字段 |
| XML/UIAutomator三源 | 源代码/IB + 明确来源的页面元数据 + 有则使用iOS运行截图/层级 | page spec、meta页面ID、状态接口和导航关系；不能把静态推导标成运行采集 |
| Android源码画像/页面穷举 | iOS源成员、页面/功能责任和源预期校验 | 原findings队列、AC索引及后续计划/实现/验证对账 |
| Android资源/应用身份 | Asset Catalog、strings/xcstrings、Info.plist、entitlements → 鸿蒙资源与配置 | 原资源前置顺序、资源引用门槛、目标i18n与身份校验 |
| Android页面converter/oracle采集 | iOS源分析和页面converter协议、Swift/ObjC真值查找 | 原组件/状态/数据/服务技能、测试设计/生成/设备执行、修复闭环 |
| Android adb前置 | 仅需要源端动态证据时使用Xcode/云构建/iPhone材料 | 目标DevEco、Hvigor、hdc和真实HAP验收 |

iOS特征作为扩展保留：target/scheme、SwiftUI状态所有权、UIKit生命周期和委托、IB连接、Swift并发/actor、ObjC动态派发、entitlement/扩展/后台限制。不能丢掉这些事实后只翻译API名称。

## 资源和宿主限制

完整收录原技能目录及其templates/references/scripts/bin、agents-codex、运行时和政策/来源材料；来源摘要形成清单，改动另列。安装后的迁移不访问原发行目录。旧六入口/绑定任务包不再是主线。

原编译校验器在本发行中多数只有Windows x64与macOS arm64版本；Linux可安装不等于这些校验器能运行。必须报告缺少实际二进制的平台，不能以空脚本返回PASS。Windows的结构校验优先调用随包Python launcher，避免把bash伪代码当作PowerShell。

本分支保留原运行时资源，安装不自动添加上传会话的遥测hooks，也不修改用户宿主权限。源端扩展不依赖上传协议；阶段标记仍由实际工具依据产物产生，不手工伪造完成水位。

## 核对依据

已读取原README、PORTING、安装脚本、AGENTS.dispatch、五阶段SKILL及其关键模板、brief/单写者规程、结构闭包、UI覆盖与UT oracle协议；实际运行原build_traceability_index、lint_coverage、lint_plan_coverage的帮助入口确认参数。技能/agent/依赖完整清单以随包来源清单为准。后续以真实原消费者能读取iOS spec、负例会被阻断、脱离原目录仍可运行作为验收依据。

## 0.5.0 修正

原 3,516 资源文件完整保存在 vendor/hmigbot，全部 SHA256 与导入基线相同。
启用目录重新组织为 96 技能、29 角色；源分析分成工程/UI/功能/API 四规程，由 ios-source-analysis 编排。
a2h-spec 正文与模板按原生源重写，不再叠加“优先级补丁”掩盖旧平台算法。
保留公共 spec 路径和消费者契约，新增 ios-semantics.json；source-check 按框架/语言检查维度与溯源。
Stage 0/1 通过 ios-resources-convert/ios-ui-to-arkui 进入原目标实施；其余原框架继续承担目标工作。
源专用画像、源码路由和尺寸默认推断器只在归档中保留，不是启用入口。
原图片只读检查器被前置使用，有待核实图片则不进入原自动尺寸修改；紧凑链式写法误报须复核后多行重查。
原 theme gate 是目标绑定检查器，不能从 iOS 源自行推断主题真值；主题必须先按实际 appearance/trait/状态建模。
