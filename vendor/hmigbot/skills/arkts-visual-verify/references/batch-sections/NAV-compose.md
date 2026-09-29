<!-- batch-section:NAV-compose — Compose 导航规则段（仅 nav_mode==compose 的批注入） -->
<!-- 本文件由 fill_batch_prompt.py 按批内页种类注入 sub-agent-batch-prompt.md 的 <!-- SECTION:NAV-compose --> 标记处；正文与 2026-09-07 拆分前逐字一致，勿在此处改判定规则以外的东西 -->

**IF nav_mode == "compose"（Jetpack Compose 应用，tree.source.toolkit=="compose-fact-tree"）**：
确定性 `walk_to`/`click_and_verify_edge`/`am-start` 对 Compose **不可靠**（单 Activity → Activity 名判页失效 + am-start 拉不起路由；底部 tab 无文字 → 文字匹配 trigger_not_found；同屏重复文字 → 点错）。因此 **Compose 模式下你（sub-agent，本身是带视觉的多模态 agent）自己导航**，用 fact-tree 的 `reach_path` + trigger `label` 当**语义提示**，按下列规则现场判断点哪：

```
Compose 导航规则（替代 walk_to / am-start / 严格 text 匹配）：
1. 判页：不看 activity 名（恒为单一 .MainActivity）。改用屏幕内容判断——
   dump 文字 / 截图,匹配该页 fact-tree 的 page_signature.positive 或语义。
2. 点元素：
   a. 有唯一可见文字的（按钮/设置行/"查看全部"）→ dump 找该文字节点,点其 bounds 中心。
      注意 Compose 节点常 clickable=false,**别按 clickable 过滤**,按文字 bounds 直接点。
   b. 无文字图标(底部 tab / 纯图标按钮)→ 按位置点:底部导航栏在屏幕最底,
      n 个 tab 等分屏宽,reach_path 里 tab 的语义序(或 fact-tree role/order)决定点第几格中心。
   c. 同屏重复文字(如多个"查看全部")→ 读截图/ dump 上下文,
      按它所属 section 标题(成就墙/数据统计…)选对应那个,点它附近(同行/紧邻)的那个。
3. 不走 am-start 直跳内部页(Compose 路由不是 Activity,必失败)。
4. 每跳后 sleep 2-3s(recomposition + 转场),再 dump/截图确认到没到目标页。
5. reach_path 是"语义意图链"不是确定性选择器——照它的顺序一跳跳走,每跳用上面 1-2 现场落点。
```

**Compose 模式下不调** `walk_to.py` / `click_and_verify_edge.py`（它们对 Compose 会 trigger_not_found/am_start_failed）；改由你按上面规则自走。其余流程（截图、多模态对比、写 markdown、manifest）**完全不变**。
