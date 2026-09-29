# iOS源验证输入

保留原四项CHECK、选择规则、修复回流和verify-report格式。源根取config.ios，源预期来自iOS源码/测试/真实观察及已批平台决策。

- CHECK-1继续原目标静态分析。
- CHECK-2源身份从Info.plist/构建变量/Asset Catalog取得；核对名称、版本和已映射图标。bundleName/vendor/签名仍由实际目标部署配置决定，不能把bundle identifier机械覆盖成签名身份。
- CHECK-3继续arkts-visual-verify的目标采集/比较/修复步骤；源截图使用真实iPhone或Xcode/云运行材料。按已记录的 iOS 场景采集；没有源截图不生成虚假视觉一致率。
- CHECK-4继续arkts-ut-verifier设计→生成→执行→fix-loop，先读该技能的iOS oracle协议。Hypium、双HAP、设备执行、强断言和独占写入责任不变。

源端无Mac/设备不妨碍可执行的目标检查；缺失的已选检查记DEFERRED/PARTIAL，不能自动变SKIP。未选项仍按原规则，不扩大用户范围。
源码、目标和配置版本改变使相关旧结果失效；保留原始记录，在原findings家族关闭重测后不再出现的问题。

## 结构检查的实测边界

原wiring检查能拦截孤立ViewModel和缺失页面，但仅清空事件处理器中的业务调用时可能仍PASS。结构PASS不能作为功能AC通过的证据。验收必须沿按钮事件到ViewModel副作用审查，并执行具有独立iOS真值的行为测试；没有运行环境时保持DEFERRED，不将静态检查升格为行为一致。
