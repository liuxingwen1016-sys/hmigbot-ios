---
name: a2h-build
description: "验证原生 iOS 迁移的鸿蒙目标配置并运行真实 hvigor assembleHap，保存日志、退出码和 HAP 证据。"
---


# 鸿蒙目标编译

读取 `.migbot/config.json`，确认 source_platform=ios 与真实 harmonyos 目标根。
缺路径先用 a2h-init；缺工具用 hmos-env-doctor。已有路径不反复询问。

1. 运行 `python <runtime>/scripts/a2h_ios.py validate --project <target>`。
2. 通过后运行 `python <runtime>/scripts/a2h_ios.py build --project <target>`。
   runtime 是本插件根，工作区安装时为 `.hmigbot-ios/plugin`。
3. 检查实际退出码、构建成功标记和本轮 HAP 指纹，不使用旧 HAP 冒充新构建。
4. 失败调用 hmos-fix-build-errors，修复后重跑。日志保留，超时或环境错误不能写成功。
5. 报告构建范围、工具/SDK 版本、产物和限制；编译不等于设备行为验证。

Windows 可调用 `.migbot/bin/a2h-tool.ps1 validate|build`；POSIX 用 a2h-tool。
封装仅执行相同原生命令，不查询源设备或上传遥测。
