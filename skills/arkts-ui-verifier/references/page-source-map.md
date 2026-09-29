# 可见页面与 iOS 源码映射

设计、生成、执行与修复前读取本文件。主线程维护 `spec/verify/ui/plan/page-source-map.json`，把前期查明的鸿蒙页面、iOS 源文件和真实到页证据保存下来，后续单页面 agent 直接按映射读取，不反复凭名称猜源文件。

## 页面范围与依据

- 默认覆盖归组后的全部页面。页面清单的 `expected_pages` 必须与各实例 `PAGE_SCOPE` 的互斥并集相等；明确列出未确认映射和用户授权排除项，不从已有测试文件反推全集。iOS 存在而鸿蒙尚未实现的目标保留缺口，不因当前看不到就消失。
- 预期行为以 iOS 源码为主：读取真实事件处理、状态变化、导航参数及相关调用链；用户明确的平台差异要求优先。UI/Feature Spec 与 iOS 冲突时记录差异与源码依据，不让过期 Spec 覆盖源码，也不机械复制已确认的 iOS 缺陷。无法判断语义或平台差异时报告待确认项。
- 实际 selector 取鸿蒙源码、资源和当前界面：已有稳定 ID 优先，无 ID 使用唯一可见文本。iOS ID、布局结构或路由 API 不直接作为鸿蒙点击定位依据。iOS 源目录缺失时请求路径，不默默降级为只按 Spec 编写或修复。

当前映射只维护在上述 plan 路径。每轮在 `round-N/evidence/plan-snapshot/page-source-map.json` 冻结实际使用版本，后续 agent 做失败定位时区分当前映射与失败轮快照；目录规则见 `execution-session-contract.md`。

## 映射最小结构

```json
{"revision":1,"source_platform":"ios","expected_pages":["page_0001"],"pages":[
  {"page_id":"page_0001","source_refs":[{"path":"Screens/Screen.swift","symbol":"Screen.body","line":10,"sha256":"<actual>"}],
   "target_file":"entry/src/main/ets/pages/ScreenPage.ets","frameworks":["swiftui"],
   "mapping_status":"SOURCE_CONFIRMED","navigation_status":"NOT_RUN","flow_ref":"<actual>","evidence_refs":[]}
]}
```



`mapping_status` 为 `SOURCE_CONFIRMED | UNRESOLVED | STALE`，`navigation_status` 为 `NOT_RUN | PASS | FAILED`，两者独立：鸿蒙到页成功并不能证明 iOS 对应文件正确。导航输入失效时 navigation_status 重置 NOT_RUN 并保留旧 evidence_refs 的包/版本上下文，旧 PASS 不能继续作为当前状态。页 ID 优先保留已有 Spec/映射编号；无编号时由主线程分配唯一稳定 ID 并记来源，不改 baseline Spec。

完整点击步骤与恢复路径只存在 navigation design/flow 中；映射引用它们，不复制第二份可漂移脚本。执行者每次到页记录包/设备指纹、截图/控件树（能力可用时）、flow/edge 与 landmark 观察，并返回映射更新建议；主线程单一 owner 合并到映射，原始运行证据保留在对应 round。

## 并行读取与失效

1. 导航设计期先保存有源码证据的映射。页面设计/生成 agent 可使用 `SOURCE_CONFIRMED` 行开始工作，不必等该页导航 PASS；不得把 NOT_RUN 写成已验证到页。
2. 派发时传 `SOURCE_ROOT`、`PAGE_MAP` 的实际绝对路径、`MAPPING_REVISION`、`PAGE_SCOPE` 和只读输入快照。先核对版本与路径，再直接读取该页的 iOS 文件和相关调用链；映射是索引，不替代读源码。
3. 页面 agent 只返回自身 `mapping_revision`、已读源码文件/主线程验证的快照哈希及 `mapping_updates`，不并发修改公共映射。前期设备执行与定位可同时进行，只有执行者持有设备锁；其他 agent 只读已归档证据。
4. 修复改变路由、页面归属、iOS/鸿蒙文件、locator 或公共 helper 时，相应映射/草稿标 STALE。主线程合并并递增 revision，通知受影响 owner 复核；最后合包前所有页面均须对齐当前 revision。未变页面也须确认输入未受影响，不能只改版本字符串。
5. `mapping_revision` 只覆盖结构、源码指纹和 selector/flow 引用，不因新增 PASS 截图反复使全部草稿失效；运行状态更新另存 evidence。缺文件、哈希漂移、歧义对应或遗漏宿主不能用缓存蒙混过关。

报告分别列出盘点的 Spec 数、归组页面数、已映射数、已到达数、Dialog 等页内功能用例数和未解决项。明确区分“已找到源码”“已实测到页”“功能已验证”，不能把其中一种当作另外两种。
