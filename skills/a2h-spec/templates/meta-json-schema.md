# iOS 页面 meta v1

```json
{
  "schema_version": 1,
  "source_platform": "ios",
  "page_id": "page_0001",
  "source_languages": ["swift"],
  "frameworks": ["swiftui"],
  "source_refs": [{"path": "Screens/Screen.swift", "symbol": "Screen.body", "line": 10}],
  "page_type": "full_screen_page",
  "needs_immersive_safearea": false,
  "semantics_ref": "spec/baseline/ios-semantics.json#page_0001",
  "runtime": "not_run",
  "screenshot": null,
  "state_conditions": [],
  "resource_refs": [],
  "navigation_refs": []
}
```

page_type 取 full_screen_page/modal_overlay/dialog/sub_component，按真实呈现与生命周期判断。
needs_immersive_safearea 是目标适配决策，有源布局依据，不由目录或类名后缀猜测。
source_refs 必须实际存在；截图字段只引用真实采集文件，runtime 与 observed 状态相符。
