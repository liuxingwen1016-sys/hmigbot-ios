# F001: 计数器

```yaml
source_platform: ios
complexity: complex
tier: core
depth: full
source_anchors:
  - role: controller
    path: "CounterViewController.swift"
ios:
  source_kind: uikit
  symbol: CounterViewController
```

## 范围
涉及页面: CounterPage
依赖: feature-base；本样例为UIKit交互单元，不声称完整App工程。

## 数据流
Add/Reset按钮 → CounterViewModel.increment/resetCount → count → Count标签。

## 服务层（ArkTS目标接口）
CounterViewModel: increment(): void；resetCount(): void；count: number。

## 实现映射（Source→ArkTS）
| 源 | ArkTS目标 | 契约 | 难度 | 决策 |
| --- | --- | --- | --- | --- |
| UIKit target-action | Button.onClick调用ViewModel | 无跨平台句柄 | 低 | 保留上限分支 |
| UILabel.text | Text随@Trace count更新 | 显示Count: n | 低 | 初值0 |

## 状态管理
页面持有CounterViewModel，count初值0，增加上限5，重置0。

## 对接点
CounterPage.onAdd → CounterViewModel.increment()
CounterPage.onReset → CounterViewModel.resetCount()

## 验收标准
- [ ] F001-AC01 count=0时Add得到1并显示Count: 1　`源:CounterViewController.increment → 标:CounterViewModel.increment`　`判:unit | count从0变1`　`真:src:CounterViewController.swift:31`
- [ ] F001-AC02 count=5时再次Add保持5　`源:CounterViewController.increment → 标:CounterViewModel.increment`　`判:unit | count在上限不增加`　`真:src:CounterViewController.swift:31`
- [ ] F001-AC03 count=3时Reset变0并显示Count: 0　`源:CounterViewController.resetCount → 标:CounterViewModel.resetCount`　`判:unit | count重置为0`　`真:src:CounterViewController.swift:37`
