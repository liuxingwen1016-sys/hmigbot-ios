# Feature Index

source_platform: ios。此目录是单个 UIKit 交互单元的协议回归样例，不是完整 iOS App 的迁移结果。

## 领域模型概览
Counter 状态：count，初值 0；上限 5；由当前页面对应状态所有者持有。

## 功能清单
| ID | 功能 | 优先级 | 依赖 | 涉及页面 | 状态 |
|----|------|--------|------|---------|------|
| F001 | 计数器 | P0 | base | CounterPage | pending |

## 依赖图
base → F001

## 执行顺序（拓扑排序）
1. feature-base 范围核对
2. F001
