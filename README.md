# HMigBot-iOS 0.5.0

读取原生 iOS 源码与功能特征，按原 HMigBot 五阶段生成 spec、计划和原生鸿蒙代码。
本工具基于独立 HMigBot CodeX 1.6.1；完整所需资源随包提供，无需原插件目录。

**主入口：`$a2h-run`。主线：a2h-spec → a2h-plan → a2h-execute → a2h-verify → a2h-retrospect。**
由宿主模型执行技能规程完成理解、设计、编码和修复；脚本负责索引、检查、构建与证据记录。
`bin/a2h` 是原运行支持程序，不能单独完成语义迁移。

## 安装

需要 Python 3.11+。解压发行包，进入 `hmigbot-ios` 目录，在 Windows 执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Workspace 'D:\Ios2Harmony'
```

指定解释器可增加 `-Python 'C:\路径\python.exe'`。安装到实际迁移工作区即可。
macOS 安装入口为 `PYTHON=python3 sh install.sh /absolute/workspace`；本轮只在 Windows x64 实测。
原校验器提供 Windows x64 / macOS arm64 资产；Linux 缺多个原编译校验器，不能视为完整可运行平台。
建议为 ZIP、解压与安装预留 4 GB。鸿蒙编译需要另装 DevEco Studio/SDK。

再次运行安装脚本即升级；用户修改的托管文件会报冲突并保留，不能强删绕过。
卸载使用 `uninstall.ps1 -Workspace 'D:\Ios2Harmony'`，只删除未修改的托管文件。
应用源码、spec、目标产物和用户规则保留。[完整安装说明](docs/INSTALL.md)

## 使用

安装后重新打开工作区会话，使宿主重新发现技能。源、目标目录须互不包含。

```text
$a2h-run 将 D:/Projects/MyNativeApp 的原生 iOS 源工程迁移到当前鸿蒙工作区。
按源行为生成保留 iOS 特征的 spec，沿原 a2h 流水线持续实现、编译和验证。
缺少运行环境的检查保留待验状态，不把生成或静态检查当成行为一致。
```

也可仅运行 `$a2h-spec`、`$a2h-plan` 或已授权范围。尚未选定源 App 时只安装工具，
不会把内置夹具当用户应用。初始化由 `$a2h-init` 维护真实配置：

```powershell
python .hmigbot-ios/plugin/scripts/a2h_ios.py init --source 'D:/Projects/MyNativeApp' --project '.'
```

配置使用 `source_platform: ios`、`ios`、`harmonyos`；构建工具路径按实际环境填写。
没有 Mac 仍可读源码和实施鸿蒙代码；源编译、iPhone 安装、源运行与双端验收单独记录。

## iOS 理解能力

| 技能 | 职责与输出 |
|---|---|
| ios-source-analysis | 源分析编排、证据来源、范围和缺口；汇总给 a2h-spec |
| ios-project-inspector | workspace/project、target/scheme/configuration、编译成员、依赖、扩展、语言桥接 |
| ios-ui-analyzer | SwiftUI 视图/状态/导航；UIKit 控制器/约束/事件；Storyboard/XIB；混合承载 |
| ios-feature-analyzer | 调用链、状态转移、错误/取消、并发、持久化、独立行为真值与 AC |
| ios-api-inventory | 网络协议、系统能力、权限/entitlements、依赖接缝和待验证契约 |
| ios-resources-convert | Asset Catalog、strings/xcstrings、应用身份与资源映射，接入 Stage 0 |
| ios-ui-to-arkui | 依据分页 spec 和真实源码，调用原 ArkTS 领域技能实施 Stage 1 |

iOS 的主要开发语言是 **Swift、Objective-C**，也可能含 Objective-C++/C/C++；
**SwiftUI、UIKit 是界面框架**，Storyboard/XIB 是界面描述资源。
spec 保留 SwiftUI modifier 顺序、视图身份、状态所有权、Binding/Environment、任务生命周期，
以及 UIKit controller 生命周期、Auto Layout、outlet/action/delegate。Optional、值/引用语义、
actor/Task、ARC/nullability/动态派发独立记录，目标 ArkUI 映射另写，不能覆盖源事实。

## 框架复用与资源组织

保留 baseline、ui-manifest、page/feature spec、decision-ledger、indexed-v1 双计划、
Base/UI/Feature Slice、brief、唯一写入者、findings 与 AC 覆盖链。通用源字段为
`source_anchors` / `source_anchors_ref`；新增 `spec/baseline/ios-semantics.json`。
真实原消费者已用原生样例验证这些字段能贯穿计划、UT 输入及目标接线检查。

- **96 个可发现技能、29 个角色**：启用的源规程原生面向 iOS，目标实施与检查尽量复用原框架。
- **vendor/hmigbot**：完整 99 个原技能、31 个原角色及脚本、模板、参考、二进制，共 3,516 文件逐字节保留。
  该目录供资源和目标检查器复用，不在插件技能发现路径内；保留原作者文字和历史平台名称。
- 10 个原源平台专用技能退出发现范围；7 个 iOS 技能接入。旧源画像、路由和默认密度推断入口退出。
- 62 项研究原子清单仅是内部检查参考，不能作为完成度或独立可执行技能数。

新增 source-check 检查源新鲜度、锚点、归属、AC 真值和条件化原生语义字段。
字段存在不证明语义理解正确；仍需沿真实源码、独立预期和运行结果核验。

## Apple 官方能力的真实状态

本包上述 iOS 分析技能为自编迁移规程，**本次没有加载 Apple 官方导出的 skill，也没有连接 Xcode MCP**。
Apple 已提供 Xcode 27 agent skills，并说明可用 `xcrun agent skills export` 导出 Markdown；
Xcode 也提供外部 agent MCP 接入。两者可作为具备 Mac/Xcode 环境时的补充。
[官方技能说明](https://developer.apple.com/videos/play/wwdc2026/278/) ·
[官方 MCP 说明](https://developer.apple.com/documentation/xcode/giving-external-agents-access-to-xcode)

这不等于 Apple 提供了现成的 iOS→ArkUI 转译器。每次真正加载的 skill、文档与工具结果均须记录来源、版本和状态。
[官方能力及接入边界](docs/PROVIDERS.md) · [云端构建与 iPhone](docs/CLOUD-IPHONE.md)

## 验证与边界

本发行的检查范围包括工具测试、原消费者兼容、源语义缺项阻断、图片尺寸前置检查、资源完整性、
安装/升级/卸载与独立 ZIP 冒烟。结果以随交付的验证报告为准。
原结构检查可能放过空事件处理器，图片检测器按行分析可能对紧凑链式写法误报；规程要求复核、
按多行写法重查并补独立行为测试，不以自动推断尺寸或静态 PASS 代替验收。

尚无完整用户源 App 的双端运行验收。自绘/游戏引擎、硬件、后台/扩展、三方 SDK 与平台账号能力
需按实际源码和目标可用能力决定；不承诺任意 App 无损全自动转换。

## 开发与复现

```powershell
python -X utf8 scripts/sync_skill_catalog.py
python -X utf8 -m unittest discover -s tests -v
python -X utf8 scripts/audit_native_surface.py
python -X utf8 scripts/validate_release.py --output work/release-check
python scripts/package_plugin.py --output dist/hmigbot-ios-0.5.0.zip
python scripts/smoke_package.py --package dist/hmigbot-ios-0.5.0.zip --output work/package-check.json
```

技能正文、参考和模板直接维护，同步脚本只更新目录。旧实验 CLI 与 provider 用于按需机械任务，
其受限生成器不承担通用迁移。包不包含 DevEco SDK、用户工程、证书或 Apple 账号凭据。

[架构与改造边界](docs/HMIGBOT-ARCHITECTURE-AUDIT.md) · [完整技能目录](docs/SKILLS.md) ·
[流水线](docs/WORKFLOW.md) · [实施状态](docs/IMPLEMENTATION-STATUS.md) ·
[来源清单](docs/THIRD-PARTY-NOTICES.md) · [变更记录](CHANGELOG.md)

[GitHub 版本基线与提交范围](docs/VERSION-HISTORY.md) · [验证复现](docs/VALIDATION.md)
