# page_0001: CounterViewController

```yaml
source_platform: ios
source_anchors:
  CounterPage: "CounterViewController.swift"
```

## 溯源
- iOS UIKit控制器: CounterViewController
- 源码布局: CounterViewController.swift
- UI快照: ui-snapshots/page_0001_CounterViewController/meta.json，仅静态源码，无运行截图
- 输出文件: entry/src/main/ets/pages/CounterPage.ets

## 页面结构
垂直排列Count标签、Add和Reset，间距16；源约束使stack居中。

## 转换决策
UILabel→Text；UIButton→Button；UIStackView→Column；target-action→onClick。

## 状态接口
| @Local变量 | 类型 | 数据来源 | 关联功能 |
| --- | --- | --- | --- |
| model | CounterViewModel | 页面实例 | F001 |

## 导航关系
本源单元无导航，不据此推断整个应用无导航。
