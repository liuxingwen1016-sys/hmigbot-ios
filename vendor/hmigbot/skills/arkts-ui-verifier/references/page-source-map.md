# 可见页面与 Android 源码映射

设计、生成、执行与修复前读取本文件。主线程维护 `spec/verify/ui/plan/page-source-map.json`，把前期查明的鸿蒙页面、Android 源文件和真实到页证据保存下来，后续单页面 agent 直接按映射读取，不反复凭名称猜源文件。

## 页面范围与依据

- 测试单位是用户实际看到的独立页面/Tab 主内容，不是 Activity、Fragment、UI Spec 文件或 `.ets` 文件数量。盘点 Android UI 源码、生产页面/导航注册和可用的运行界面；UI Spec、ui-manifest 只作索引与参考。`ets/pages/` 不覆盖 components 中的独立 Tab，也不能代替实际页面盘点。
- 普通 Dialog、Sheet、菜单和嵌入式 Fragment/组件合入宿主页测试；独立 Tab/全屏 Fragment 按实际页面测试。仅提供宿主外壳的 Activity 不重复建页面 suite。Dialog Spec 保留为宿主页需求来源，不单独创建页面到达 preflight。
- 默认覆盖归组后的全部页面。页面清单的 `expected_pages` 必须与各实例 `PAGE_SCOPE` 的互斥并集相等；明确列出未确认映射和用户授权排除项，不从已有测试文件反推全集。Android 存在而鸿蒙尚未实现的目标保留缺口，不因当前看不到就消失。
- 预期行为以 Android 源码为主：读取真实事件处理、状态变化、导航参数及相关调用链；用户明确的平台差异要求优先。UI/Feature Spec 与 Android 冲突时记录差异与源码依据，不让过期 Spec 覆盖源码，也不机械复制已确认的 Android 缺陷。无法判断语义或平台差异时报告待确认项。
- 实际 selector 取鸿蒙源码、资源和当前界面：已有稳定 ID 优先，无 ID 使用唯一可见文本。Android ID、布局结构或路由 API 不直接作为鸿蒙点击定位依据。Android 源目录缺失时请求路径，不默默降级为只按 Spec 编写或修复。

当前映射只维护在上述 plan 路径。每轮在 `round-N/evidence/plan-snapshot/page-source-map.json` 冻结实际使用版本，后续 agent 做失败定位时区分当前映射与失败轮快照；目录规则见 `execution-session-contract.md`。

## 映射最小结构

```json
{
  "schema_version": 1,
  "mapping_revision": "<结构映射与源码哈希的指纹>",
  "android_root": "<实际绝对路径>",
  "harmony_root": "<实际绝对路径>",
  "expected_pages": ["P0010"],
  "user_excluded_pages": [],
  "unresolved": [],
  "pages": [
    {
      "page_id": "P0010",
      "page_short": "settings",
      "display_name": "设置",
      "harmony_sources": ["entry/src/main/ets/pages/SettingsPage.ets"],
      "android_sources": [
        {"path": "app/src/main/java/example/SettingsFragment.kt", "symbols": ["onPreferenceClick"], "sha256": "<内容哈希>"}
      ],
      "related_android_sources": [
        {"path": "app/src/main/java/example/ConfirmDialog.kt", "symbols": ["onConfirm"], "sha256": "<内容哈希>"}
      ],
      "spec_refs": ["spec/baseline/ui/page_0010_SettingsFragment.md"],
      "in_page_surfaces": ["ConfirmDialog"],
      "entry_kind": "IN_APP",
      "navigation_design": "spec/verify/ui/plan/navigation/P0010_SettingsPage.md",
      "flow_id": "NAV_P0010_FROM_APP_ENTRY",
      "target_landmark": {"kind": "text", "value": "设置", "scope": "<确保唯一的可见上下文>"},
      "mapping_status": "SOURCE_CONFIRMED",
      "navigation_status": "NOT_RUN",
      "evidence_refs": []
    }
  ]
}
```

示例路径仅说明结构，必须替换为实际存在的文件；一页可映射多个 Kotlin/Java、XML、Compose、ViewModel 或事件处理文件，多个页面也可共享源文件。映射须有类/符号、调用或资源关系依据，不能只凭同名或截图宣称对应。

`mapping_status` 为 `SOURCE_CONFIRMED | UNRESOLVED | STALE`，`navigation_status` 为 `NOT_RUN | PASS | FAILED`，两者独立：鸿蒙到页成功并不能证明 Android 对应文件正确。导航输入失效时 navigation_status 重置 NOT_RUN 并保留旧 evidence_refs 的包/版本上下文，旧 PASS 不能继续作为当前状态。页 ID 优先保留已有 Spec/映射编号；无编号时由主线程分配唯一稳定 ID 并记来源，不改 baseline Spec。

完整点击步骤与恢复路径只存在 navigation design/flow 中；映射引用它们，不复制第二份可漂移脚本。执行者每次到页记录包/设备指纹、截图/控件树（能力可用时）、flow/edge 与 landmark 观察，并返回映射更新建议；主线程单一 owner 合并到映射，原始运行证据保留在对应 round。

## 并行读取与失效

1. 导航设计期先保存有源码证据的映射。页面设计/生成 agent 可使用 `SOURCE_CONFIRMED` 行开始工作，不必等该页导航 PASS；不得把 NOT_RUN 写成已验证到页。
2. 派发时传 `ANDROID_ROOT`、`PAGE_MAP` 的实际绝对路径、`MAPPING_REVISION`、`PAGE_SCOPE` 和只读输入快照。先核对版本与路径，再直接读取该页的 Android 文件和相关调用链；映射是索引，不替代读源码。
3. 页面 agent 只返回自身 `mapping_revision`、已读源码文件/主线程验证的快照哈希及 `mapping_updates`，不并发修改公共映射。前期设备执行与定位可同时进行，只有执行者持有设备锁；其他 agent 只读已归档证据。
4. 修复改变路由、页面归属、Android/鸿蒙文件、locator 或公共 helper 时，相应映射/草稿标 STALE。主线程合并并递增 revision，通知受影响 owner 复核；最后合包前所有页面均须对齐当前 revision。未变页面也须确认输入未受影响，不能只改版本字符串。
5. `mapping_revision` 只覆盖结构、源码指纹和 selector/flow 引用，不因新增 PASS 截图反复使全部草稿失效；运行状态更新另存 evidence。缺文件、哈希漂移、歧义对应或遗漏宿主不能用缓存蒙混过关。

报告分别列出盘点的 Spec 数、归组页面数、已映射数、已到达数、Dialog 等页内功能用例数和未解决项。明确区分“已找到源码”“已实测到页”“功能已验证”，不能把其中一种当作另外两种。
