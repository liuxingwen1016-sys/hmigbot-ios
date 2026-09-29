## Slice 1: 计数器 (F001)
parallel_group: 1 | complexity: complex
depends_on: []
source_anchors_ref: {count: 1, source: spec/baseline/features/F001-counter.md}

integration_points:
  - CounterPage.onAdd → CounterViewModel.increment()
  - CounterPage.onReset → CounterViewModel.resetCount()

wires:
  - page: entry/src/main/ets/pages/CounterPage.ets
    viewmodel: entry/src/main/ets/viewmodels/CounterViewModel.ets

- Step 3a: UI补充 — scope: 0001 | input: spec_refs: ui/page_0001_CounterViewController.md
- Step 3b: ViewModel — scope: CounterViewModel | input: spec_refs: features/F001-counter.md
- Step 3c: 数据层 — scope: 本功能无外部数据层，状态保留页面内 | input: spec_refs: features/F001-counter.md
- Step 3d/3e: 接线 + 验证 — 契约见a2h-execute §5e
