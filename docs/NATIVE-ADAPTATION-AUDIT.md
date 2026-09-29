# 0.5.0 原生适配验收

## 本轮修正

启用规程、模板、角色和入口全局清理旧源平台假设；替换源码解析、主题/显隐证据、路由、资源尺度和测试真值入口。
ios-source-analysis 编排 ios-project-inspector、ios-ui-analyzer、ios-feature-analyzer、ios-api-inventory。
a2h-spec 保留 HMigBot 公共产物和稳定 AC，新增原生事实伴随文件；SwiftUI/UIKit 与语言语义独立保存。
目标仍由原 a2h-plan/execute/verify/retrospect 和 ArkTS 领域能力实施。

## 实际结果

- 82 项自动化测试通过；包括原生事实缺项、证据无效、图片前置阻断不改目标、oracle 通用路径及 Windows 长路径安装/升级/卸载。
- 19 项真实原流水线消费者/负例兼容检查通过。
- 96 个启用技能、29 个角色的结构检查通过；官方插件和技能校验器通过。
- 3,516 个原资源文件 SHA256 与导入基线一致，均在 vendor/hmigbot 中。
- 启用层文字扫描通过；完整文本扫描的其余命中均分类保留在原始归档、历史来源资料、旧兼容拒绝/负例测试或扫描表达式中。

这里的“通过”仅表示相应检查范围通过。原资源必须保持来源真实，故不宣称整个归档包没有旧平台文字。
完整 ZIP 的安装/升级/卸载与本机升级结果另附交付目录的 package-check.json / workspace-install.json。

## 可复查证据

[验证范围与复现步骤](VALIDATION.md) · [原资源清单](upstream/derivative-manifest.json)

## 仍需应用级验收

Apple 官方 skills 未加载，Xcode MCP 未连接；本次没有完整用户应用的 iPhone/鸿蒙双端行为验收。
原结构检查可放过空 handler，原图片检查可对单行链式写法误报；规程和测试已记录边界。
不能把技能数量、文件存在、字段完整或编译成功当作任意 iOS 应用转换成功。
