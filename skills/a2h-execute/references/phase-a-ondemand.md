# 按需补齐 iOS 源事实

遇到新增页面、缺失源证据、未解释的状态/事件或源版本变化时，暂停该依赖任务，
由 a2h-spec 重新调用 ios-ui-analyzer/ios-feature-analyzer 读取真实实现。
保持稳定 ID，更新源事实、page spec、meta 与相关 feature/decision，再重跑 source-check。
更新会影响已批准 plan 时进入增量重排，不能在 execute 里静默改变 AC。
补齐通过后恢复原 slice；独立任务继续。无源码时保留 blocked，不凭符号名猜骨架。
