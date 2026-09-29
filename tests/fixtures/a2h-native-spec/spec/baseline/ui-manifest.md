# UI Manifest

source_platform: ios。iOS 列沿用原消费者标题，内容为真实 iOS 符号。

## 全局约定
- 导航架构：本样例仅包含单个 controller，无源导航跳转；不推断完整 App 架构。
- 设计令牌：CounterViewController.swift 中垂直栈 spacing=16，标签字号 24，居中约束。
- 命名规范：CounterPage.ets；状态由 CounterViewModel 持有。
- 图标方案：本源单元未引用图标。
- 沉浸式与安全区：源居中内容不绘制状态栏背景；宿主窗口策略需实际 App 装配证据，未伪造已验证状态。

## 页面清单
| 序号 | iOS | ArkTS 产出 | 优先级 | confidence | 状态 |
|------|---------|-----------|--------|-----------|------|
| 0001 | CounterViewController | CounterPage.ets | P0 | medium | pending |

### 页面状态生命周期
pending → converted → verified。只有实际执行和验收后才能由原 writeback 更新状态。

## 转换批次
- Batch 1 (P0): 0001

## 共享组件
无；仅本页元素。静态源证据不代表真实截图。
