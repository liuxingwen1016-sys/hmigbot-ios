# iOS 广告依赖与行为定位

读取 ios-project-inspector/ios-api-inventory 的 Package.resolved、Podfile.lock、
project linked frameworks、实际 import 和初始化调用；依赖表只提供线索。
核验广告格式、placement ID 来源、初始化/隐私授权顺序、delegate/closure 回调、
展示宿主、频控、前后台/取消、收益/奖励发放与失败降级。
Info.plist、ATT/隐私配置和实际调用交叉核验，不能凭权限声明推断 SDK 已使用。
记录厂商、iOS 版本、实际类型/API、源位置与平台配置；目标 SDK 另查官方鸿蒙版本。
没有完全对应 SDK 时使用 arkts-library-migration 的契约映射和决策流程。
