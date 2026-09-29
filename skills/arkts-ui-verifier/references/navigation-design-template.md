# page_NNNN 导航设计

- source_platform: ios
- PAGE_MAP / MAPPING_REVISION: <实际路径和版本>
- 源证据: <真实 SwiftUI/UIKit/IB 文件、符号、行、hash>
- 页面归组: <独立可见页、内嵌 View、模态、Tab 及条件>
- 目标入口: <EntryAbility/页面/路由真实路径>
- entry_kind: IN_APP | SYSTEM_ENTRY | DEEPLINK_ENTRY | CROSS_APP_ENTRY | ENTRY_GAP
- 运行环境: <SDK、设备、系统、应用包指纹>

## 导航流
前置数据/账号/权限 → 实际操作 → 目标 locator → 观察结果/landmark → 返回与恢复。
每条对应源路由值、条件、参数、模态状态和 stable page ID。
无公开可达入口按根因记录 ENTRY_GAP 或不可 UI 测范围，不直挂页面伪装到达。
设备未跑记 NOT_RUN；映射已确认与运行已通过是独立状态。
