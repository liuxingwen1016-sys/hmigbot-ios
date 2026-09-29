# iOS 迁移目标工程初始化

输入已审批的 app/target 范围、目标 bundle、SDK、页面/feature 索引与依赖决策。
使用本技能的 HarmonyOS Stage 模型与目标工程模板，配置真实 EntryAbility 和入口页面。
按计划建立 pages/components/viewmodels/services/models/resources，避免无业务意义空模块。
源 workspace/target 不强制一对一对应目标模块，边界由部署/复用/平台决策决定。
初始构建只验证工程骨架；后续必须经过资源、页面、Base、Slice 与接线/终编译闭环。
