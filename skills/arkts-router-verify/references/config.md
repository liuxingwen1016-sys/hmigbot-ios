# 原生导航核验参考

执行本技能 SKILL.md 和 ios-ui-analyzer 的原生导航规程。
源路由使用实际 SwiftUI NavigationPath 或 UIKit push/present/segue 及参数/状态；
目标路由以当前 Navigation/NavPathStack、事件处理、页面注册为准。
静态检查与真实到态分开，缺源事实回 spec；历史探针不用于 iOS 源代码。
