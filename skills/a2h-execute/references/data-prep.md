# Stage 1 iOS 输入预检

每页必须有真实 source_anchors、分页 spec、ios-semantics 同 ID 和 meta.json。
读取 UI 框架与源代码，不合成另一种平台布局；截图可为空，状态必须标 not_run。
核对 source-check 和源快照；新页面或缺少关键状态时回 a2h-spec Phase A/B 补齐。
SwiftUI 条件树/Binding/任务、UIKit 约束/事件连接须能支持当前转换。
返回 page_id、source_root、page_spec、ui_info、target、owning_slice、
wiring_ownership_map、registered_placeholders、owned_files。
页面未分析完成时不得根据类名创建“已转换”空壳。
