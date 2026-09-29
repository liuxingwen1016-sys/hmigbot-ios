# 0.5.0 验证范围与复现

0.5.0 交付验证在 Windows x64 完成：82 项自动化测试、19 项真实原流水线消费者与负例检查、96 个技能及 29 个角色结构检查通过；官方插件/技能校验器通过。3,516 个随包原资源文件的 SHA256 与导入清单一致。完整 ZIP 的 10 项安装、升级、卸载及独立使用检查通过。

原始报告和运行日志保留在本地交付资料中，不纳入 Git 历史。仓库保留测试源码、必要夹具、资源校验清单与以下复现入口。每次执行必须使用新的输出目录。

```powershell
python -X utf8 scripts/validate_release.py --output work/release-check
python scripts/package_plugin.py --output dist/hmigbot-ios-0.5.0.zip
python scripts/smoke_package.py --package dist/hmigbot-ios-0.5.0.zip --output work/package-check.json
```

`validate_release.py` 默认运行单元测试、原资源审计、启用规程扫描、原流水线兼容、版本、目录、角色和文档链接检查。官方插件/技能校验器需通过 `--plugin-validator` / `--skill-validator` 指定本机脚本路径；未提供时不会冒充已执行。上述输出均为本机生成，不应提交。

这里验证的是工具和契约；本版尚无完整用户源 App 的 iPhone/鸿蒙双端行为验收。Apple 官方 skills 未加载，Xcode MCP 未连接。其他平台的随包资源存在不代表已在该平台实测。详见[实施状态](IMPLEMENTATION-STATUS.md)和[原生适配边界](NATIVE-ADAPTATION-AUDIT.md)。
