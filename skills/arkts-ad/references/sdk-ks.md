# sdk-ks：目标 SDK 资料与 iOS 契约

完整 HMigBot 原资料在 runtime 的 `vendor/hmigbot/skills/arkts-ad/references/sdk-ks.md`。
从本包 runtime 读取，不从外部安装路径读取；原资料保留平台标注和出处，不能重命名源 API。
该资料只用于目标鸿蒙集成参考；源调用/回调类型、初始化与资源生命期以 ios-api-inventory 为准。

1. 从源调用链列真实厂商版本、使用子集、授权/初始化时序、数据协议和回调线程。
2. 在随包原资料中定位明确的目标鸿蒙依赖/权限/初始化/API 段，保持目标代码原义。
3. 对当前版本敏感的签名、包名、许可证和支持范围查厂商官方文档或实际 d.ts。
4. 按源行为契约写适配层；不存在等价能力的变化走 decision，不按同名 API 猜等价。
5. 按 owning_slice 接线，编译并执行对应真实场景；未取得 SDK/账号/设备时保持缺口。
