<!-- when: Phase B Step B1 生成 ui-manifest.md 时加载 -->
<!-- topics: ui-manifest, 页面清单, 全局约定, 页面状态生命周期, 转换批次, 共享组件 -->

# ui-manifest.md 模板

必填字段：全局约定（导航架构 / 设计令牌 / 命名规范 / 图标方案 / **沉浸式 + 安全区四件套**）、页面清单表（序号 / iOS / ArkTS 产出 / 优先级 / confidence / 状态）、页面状态生命周期、转换批次、共享组件表。


全局约定的推导逻辑：
- **设计令牌**：从 `styles.xml` / `themes.xml` / `colors.xml` 提取主色、文字色、背景色
- **图标方案**：扫描 `res/drawable*` 目录，确定图标格式（SVG/PNG/VectorDrawable）
- **沉浸式 + 安全区**：本节展示全工程统一的标准方案（4 Layer）；**每页是否需要产出对应配置由 `meta.json` 的 `page_type` / `needs_immersive_safearea` 字段自动决定**（由 ios-ui-analyzer 按实际呈现与生命周期证据填写）—— 本段无需再做词汇判定

优先级分配规则：
- P1：次级功能页面（设置、搜索、下载管理等）
- P2：辅助页面（关于、许可证、同步设置等）
