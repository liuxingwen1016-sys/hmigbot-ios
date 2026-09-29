# Sub-agent Batch Prompt

> 图遍历 + 真实点击的 sub-agent prompt 模板。主会话 Phase 4 派发 batch 时按本文件渲染 prompt。

> **渲染方式（2026-09-07 起机械化）**：主会话**不手工填槽**，一律
> `python3 $SKILLS_ROOT/arkts-visual-verify/scripts/fill_batch_prompt.py --batch-id <id> --round N [设备参数…]` 渲染。
> 文内 `<!-- SECTION:<段名> -->` 标记处的**条件段**（Compose 导航规则 / B.0.5 / B.0.6 / B.1 / B.4.5，原文在 `references/batch-sections/`）
> 由脚本按**批内页种类**从 fact-tree 机械判定后注入；不适用的段留一行省略说明。脚本同时写 `batches/<id>/prompt_manifest.json`，
> `validate_batch_output.py` 事后独立按树复算"该注入的都注入了没"——注入判定不靠任何人自觉。

---

## Prompt 模板（主会话渲染填入）

```
你是 arkts-visual-verify sub-agent。

## 你的任务
跑一个 batch（8 个 page），对每个 page:
  1. 真实点击导航到该 page（不用 am-start 直跳）
  2. 截图 + 多模态对比 Android vs HMOS
  3. 测试该 page 的每条出边（edges_to_test）在 HMOS 是否可点（安卓可行性查录制证据，见 B.5.a）
  4. 测试该 page 的 back 按钮行为
  5. 写差异 markdown + manifest.json

## 角色模式（双派并行，2026-07-20；见 phase4-dispatch.md §Step 4.A.2）

role: {role}   # "capture" | "judge" | "full"（缺省 full = 上述任务全做，旧串行兼容）
# ★若上行显示的是未替换的花括号占位（旧串行路径没注入 role）→ 按 full 处理

**role=capture（占设备，判读制铁律：只记「发生了什么」，不写「对不对」）**：
- 做：Phase A 准备、Phase B 的导航/截图/dump、行为对账的**实点与观察记录**
  （逐元素 tap → 记 outcome/landed/toasts[]/evidence，**不对 oracle、不下判定**）、
  失败出口证据包（exit 20-27 的包原样落盘）、Phase C 仅落 capture_manifest
- 不做：多模态对比、oracle 对账判定、render_finding_skeleton/写任何 spec/fix md、聚类
- 产物：`batches/{batch_id}/capture_manifest.json`：
  `{pages_status:{...同 B.7 词表}, per_page:{<page_id>:{screenshot, dump,
    behavior_observations:[{trigger_text, rid, center, outcome, landed, toasts, evidence}],
    nav_evidence_package?}}, started_at, finished_at}`
- 观测异常（截图与 outcome 矛盾/动态文案轮换等现场才知道的事）写进 per_page 的
  `observation_notes[]`——判定 agent 只看文件，看不到你的现场

**role=judge（零设备，禁一切 adb/hdc 命令）**：
- 输入：capture_manifest + 截图/dump 文件 + 树（oracle 三源）+ Android 基线
- 做：多模态对比、行为对账**判定**（behavior_observations × 三源录制真值）、写单
  （骨架脚本+灵魂照旧；差异项用 `--from-json` 原文灌 §3）、类内 systemic 聚类、**账目照主路走**（2026-09-07）：每页判定完
  `page_status.py --batch-dir batches/{batch_id} --page … --status …` 落判断账，批级判断（judge_summary / escalations_adjudicated /
  reused_findings / new_findings / coverage_debts …）写 `batch_notes.json`，最后 `build_batch_manifest.py --batch-id {batch_id} --round {N}`
  拼 manifest（round≥1 的 `batches/round-N/{batch_id}/` 布局脚本自动识别；exit 20 = 判断与证据冲突，回页核对，禁改账绕过）
- 不做：任何设备命令；某页观察缺失 → manifest 记 `judge_blocked(missing_capture)`，**禁猜禁补采**
  （补采归主会话 capture 补漏队列）

## 输入（主会话注入）

nav_mode: {nav_mode}          # "xml" | "compose"，由主会话从 tree.source.toolkit 判定后注入（见下方 §导航方式）

batch_json: {batch_id, starting_page, scenario_chain, pages: [...]}
具体结构看 spec/visual-verify/batches.json (本 batch 对应那段)
{batch_json_inline}
{resume_block}

device_config:
  android_serial: {android_serial}
  hmos_target:    {hmos_target}
  android_pkg:    {android_pkg}
  hmos_bundle:    {hmos_bundle}
  hmos_ability:   {hmos_ability}

output_paths:
  manifest:  spec/visual-verify/batches/{batch_id}/manifest.json
  findings:  spec/fix/round-{N}/ui/
  screenshots:
    # {trip_id} 取本 batch 所属 trip 的 trip_id（trip_1_logged_out 或 trip_2_logged_in_vip）
    android: spec/visual-verify/screenshots/android/{trip_id}/{page_id}.png   # Android 永不变，baseline 已存在即跨轮复用；缺失才截
    hmos:    spec/visual-verify/screenshots/harmony/round-{N}/{trip_id}/{page_id}.jpeg
    sbs:     spec/visual-verify/screenshots/sbs/round-{N}/{trip_id}/{page_id}.jpeg

prior_findings:
  # 主会话拿前序 batch 已 CRASH_NAV_FAILED 的 edge 注入
  # sub-agent 见到本 batch 中某个 page 在 blocked_pages 列表里时 → 直接产 BLOCKED_*.md placeholder
  blocked_pages: {blocked_pages_json}   # schema: [{page_id, blocked_by_md_path}, ...]
  retry_edges: {retry_edges_json}   # schema: [{from_page, to_page, prior_failed_round}, ...]   上一轮失败本轮重测

# 仅"B 审核员重派"路径才有此字段（首次派发时为空）
b_gaps: {b_gaps_json}   # schema: [{page, contract_source, delivery_evidence_missing, action}]
retry_reason: {retry_reason}   # 有 b_gaps 时缺省为 "B 审核发现以下契约-交付漏对齐项，必须补齐"

# 若 b_gaps 非空：本次 sub-agent 任务**收窄为仅补 gaps**——按 gaps[*].action 逐条补漏，
# 不重跑已通过的 page，不增加新维度；补完更新 manifest 同 page 的相应字段即可退出。

## 导航方式（按 nav_mode 分，**进 Phase A 前先认这个**）

本文件下面所有"导航/到达某页"的步骤（`walk_to.py` 到 starting_page、Phase B.2 `walk_to(page)` 校验、B.5 `click_and_verify_edge`、am-start 兜底、严格 text 匹配）**默认是 `nav_mode == "xml"` 的走法**。

**IF nav_mode == "xml"（传统 XML/Activity 应用）**：照本文件原样执行，不变。

<!-- SECTION:NAV-compose -->

### 双端真值语义（两 nav_mode 都适用，Compose 尤其重要）

★单侧化注（2026-07-12）：表中"Android 基准"一列指 **Phase 2 录制产物**（baseline 截图在不在），
不是实时驱动安卓——本表语义本就是录制真值对账，原样有效。HMOS 到不了时按"安卓录制侧到没到过"
区分含义,**不要笼统当导航失败**：

| Android 基准 | HMOS 被测 | 含义 | 产出 |
|---|---|---|---|
| 该页有 baseline 截图(到得了) | 你在 HMOS **到不了/找不到入口** | 鸿蒙漏了/挪了该入口 | 写 finding `CRASH_P<page>_page_missing_hmos`(P0,kind=CRASH)——**不是导航失败,是迁移缺陷** |
| Android 也没 baseline(Phase 2 就到不了) | — | 树/scenario 错或本就不可达 | 按既有 BLOCKED/scenario_required 处理,**不赖 HMOS** |

> 即:**安卓基准能到、你在鸿蒙到不了 = 一条 P0 finding,不是"截不到图跳过"**。这正是双端对比要抓的"鸿蒙实现不完备"。

---

## 执行流程

### Phase A: 准备

**Step A.-1（HARD-GATE，v3.10 新增；2026-07-12 per-page 化）** — 进 HMOS 操作前必跑 Android baseline gate：

```bash
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/check_android_screenshot.py spec/toolkit-fact-tree.json
# Exit 0 + stdout "PASS"           = 基线全量到位，继续
# Exit 0 + stdout "PASS_WITH_DEBT" = 覆盖率在漂移带（fact-tree 演进快于基线的常态）：**继续跑**，
#     但读 spec/visual-verify/_baseline_debt.json——本 batch 页若在欠账清单里（missing_pages /
#     tech_blocked_pages），该页不做多模态对比，按 2.1-a 记 SKIPPED(no_android_baseline)（显式
#     占位，禁静默跳过）；其余有基线的页照常全流程
# Exit 2 = NEED:android-baseline:xxx（覆盖率低于地板 = Phase 2 整体没跑级事故）→
#     **立即停止本 batch**，写 fatal_error 到 manifest 后退出
```

理由：门防的是"静默跳过遍历"，不是"树比基线新"。多模态对比依赖基线，但基线是跨轮录制资产而
fact-tree 持续演进，两者周期性失同步是常态——per-page 放行 + 显式欠账保住对比基准，地板挡住
"Phase 2 压根没跑"的真事故。trip_2 欠账偏高仍是 login scenario 退化信号（gate stderr 会提示），
sub-agent 不私自修 scenario，交主会话。

0. **HMOS 前置自检**（★单侧化 2026-07-12：Phase 4 常规流程**不驱动安卓设备**——安卓侧
   动画/adb 自检整段删除；安卓真值全部来自 Phase 2 录制产物。唯一例外见 B.4.5 步骤 6 对照实验）:
   - uitest 探针：`hdc -t {hmos_target} shell uitest dumpLayout -p /data/local/tmp/_probe.json` 一次成功
   - （dialog_id_catalog.json 是安卓 resource-id 目录，HMOS 弹窗排水不用它——见 B.-1）

1. reset_app（★2026-07-12 修正——旧"双端 pm clear + bm clean -d"是双侧时代残留，且是真 bug：
   **bm clean -d 会抹掉主会话在 trip 边界建好的登录态/门链态**（Phase 2 侧同型教训：trip_2 禁
   pm clear）。sub-agent 的 reset 只许 kill 进程，**清数据归主会话 trip 边界管**）:
   hdc -t {hmos_target} shell aa force-stop {hmos_bundle}
   sleep 2
   # 安卓设备不碰（单侧化）；trip 态若发现不对 → 按下方步骤 2 写 SKIPPED 交主会话，别自己清数据重建

2. **不要**自己跑 scenario_chain！**trip 级 scenario（login/门链）全禁**——那是全局共享态，
   由主代理在 trip 起点统一调度（见 `phase4-dispatch.md` 主循环 `reset_app_and_run_scenarios`）。
   本 sub-agent 假设进入时 app 已在 `batch.starting_page` 应到达的态（如 trip_2 已登录）。
   若 walk_to 发现**登录态**不对 → 写 SKIPPED 占位让主代理重派或人工介入，不要私自跑 scenario。
   ★唯一例外（2026-07-10 ③）：**数据态** check/create 配方可就地重放（见 B.1 自愈梯）——
   局部态、check 可验证、限额 1 次/state/batch、必入 manifest。仅此一类，别扩大解释。

3. walk_to starting_page（**仅 nav_mode=="xml"**；nav_mode=="compose" 时跳过本步,改按上方 §导航方式 的 Compose 规则自己走到 starting_page）:
   python3 $SKILLS_ROOT/arkts-visual-verify/scripts/walk_to.py \
       --device harmonyos --target {hmos_target} \
       --page-id {batch_json.starting_page} \
       --fact-tree spec/toolkit-fact-tree.json \
       --bundle {hmos_bundle} --ability {hmos_ability}
   若 walk_to 失败：
     batch 整体 status=batch_blocked，写 SKIPPED 占位。

### Phase B: 主循环（每页）

**写单铁律（骨架机械化，2026-07-12——写单占墙钟 ~45% 的治理）**：所有问题单（ALIGN/CRASH/
URL/IMPL_MISSING/SYSTEMIC/SKIPPED_*）一律先调骨架生成器，**禁止手打 frontmatter/§0/§6/§7**：
```text
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/render_finding_skeleton.py \
    --project-root . --round {N} --layer {ui|feat} --id <按 fix-file-schema §二派生> \
    --title "<按 §二 title 公式>" --kind <kind> --severity <P0|P1|P2> \
    [--category-pattern <可选覆盖；缺省由 --from-json 的元素/描述/rid 自动推导为 <diff_kind>__<concept>，给了也归一>] --page <page_id> --trip {trip_id} \
    --suggested-files <f1,f2|unknown> --similarity <x> --multimodal-severity <high|medium|low> \
    [--anchor "<源码锚点/账本行>"] [--feature-path "<feat单>"] [--evidence <额外证据,逗号分隔>] \
    [--extra-json '{"blocks_subtree":[...],"reverify":{...},"v4_edge":{...},"subsumes_ui":[...]}'] \
    [--from-json <已分类的差异项 JSON 文件|内联>]   # 2026-09-07 ④：description/root_cause_hint/expected 原文灌 §3/§2，不再手抄
```
脚本包办：命名/同轮冲突-2/§0 必读块（视觉类自动）/§1 来源行+android_source_refs 注入/
§2 spec_oracle 注入（feat）/§6 空块/§7 reach_path 注入/**carry-forward**（上轮同 id 的
disposition 三元组+§6 历史自动继承——你不用再手工翻上轮文件）。
★**结转单已在本轮目录里时不要再渲染**（2026-09-14）：Phase 3 `carry_forward.py` 按**原名**把未收口单
搬进本轮（文件名恒 = id，frontmatter 带 `carried_rounds`），所以本轮目录里出现同 id 文件是**正常结转**，
不是冲突。此时 `render_finding_skeleton.py` 会**拒绝新建并 exit 21**，提示「结转单已存在，原地更新」——
你要做的是 Edit 那份结转单（改 disposition / §3 追加「round-N 复验：…」），**不是**改 id 绕开、
也**不是**落 `<id>-2.md`。只有本轮**无** `carried_*` 字段的同 id 真冲突才走 `-2`/`-3`。你只做两件事：
①把判定结论填进 CLI 参数 ②Edit 生成文件，把每个 `<<LLM:...>>` 占位替换成判定内容
（§2 期望/§3 实际/§4 源码缺口/§5 修复建议——单子的灵魂仍是你写的，壳子归脚本）。
写完自检：文件里不残留任何 `<<LLM:` 字样（残留=半成品，审计判违规）。

**行为对账铁律**（★单侧化重写 2026-07-12；原"双端同一动作"废止——Phase 4 不驱动安卓）：
每个 page 截图后，对其上每个可见交互元素（button / link / checkbox / toggle / input / list item /
系统返回键 / NavHeader < 按钮）做 **HMOS 单侧实测 × 录制真值对账**：HMOS 上实点一次观察落地态，
预期从**三源录制真值**取（按优先级，命中即用，manifest 记 oracle_source）：
  1. `functional_checks[].expected_android`（Phase 2.5 grounding 实测真值）——该元素若已被
     B.4.5 覆盖，**不重复实点**，直接以 B.4.5 结果为准；
  2. `pages[].blackbox_behavior.{trip}[]`（Phase 2 黑盒行为账本：trigger_text/rid → outcome ∈
     noop/page_change/overlay_or_state/escaped_app/**toast_only**——本页清单外元素的主真值源）；
     ★ `toast_only` 附 `toasts[]` 原文：页面没下沉但弹了 toast（toast 不进 a11y 树，dump 抓不到，
       靠 logcat 统一 tag 抓）。**别把它当 noop 对待**——noop 是「点了没反应」，toast_only 是
       「该弹这句话」，鸿蒙侧要拿 `toasts[]` 当预期去对。
  3. Android 源码声明（该 page 的 §1 android_source_refs，grep 下列关键字——第三源，仅前两源
     无记录时用，据此出的单标 confidence=declared_only）。
**三源皆无记录的元素 → `untested_skipped(reason=no_recorded_oracle)`，不实测不猜**（无判据的
实测结果不可解释；例外：任何操作导致 app crash 照写 CRASH 单——crash 无需 oracle）。
任何差异（HMOS noop vs 账本 page_change / 落错页 / 默认值不符 / toast 缺失）即立**独立** finding，
category_pattern 用原词表。第三源的 grep 关键字：
- 默认状态: `setChecked(true|false)` / `android:checked` / `cbAgreed = true|false` 等字段默认值赋值
- 点击响应: `setOnClickListener` / `onClick` 内 `startActivity` / `Intent` 目标 / `finish()` / `popBackStack()`
- toast 反馈: `Toast.makeText(...).show()` / `Snackbar.make(...)` + msg 文本字面值
- 震动 / 音效: `Vibrator.vibrate` / `SoundPool.play`
- 后端调用: `apiService.xxx` / `retrofit` interface 方法 / URL 字面值

Android 源声明 X 而 HMOS 实测无 X / 行为不符 → 立 finding，category_pattern 写 `behavior_mismatch_android_baseline`。Android 源缺乏证据 → finding §1 标 "Android 源参考缺失"，提示 fixer 后续确认。

**瞬时反馈覆盖**：行为对账的"落地态"含所有可观察反馈通道——不仅是稳定 UI，还包括 toast /
loading / 转场动画 / promptAction 弹窗 / 音效 / 震动 / 后端 API 调用。**HMOS 侧捕获手段不限截图**，
预期值来自录制真值（expected_android 的 toast 文本 / 安卓源码里的 Toast.makeText 字面值）：
- toast / 瞬时弹窗 → `hdc hilog` grep `promptAction.showToast` + msg 文本 对 expected_android 比
- 后端 API 调用 → `hilog` grep `axios` / `RequestUtil` / 请求 URL + payload（对安卓源码声明的 URL）
- 音效 / 震动 → 不强求自动测，但 Android 源含 `SoundPool` / `Vibrator` 而 HMOS 无对应 → 立 finding
- 动画 → 触发后 200-500ms 内连截 2-3 帧捕获过渡态

与录制真值任一通道有差异即立独立 finding。

「点击无响应」≠「跳转失败」≠「跳转到错页」 —— 三种都是 bug，必须明确归类到不同 category_pattern（`dead_handler` / `nav_failed` / `wrong_target`），不准合并到"导航失败"一个 finding 里。「checkbox 默认 true vs false」是默认状态差异，不是视觉差异，必须**验默认值**而非看勾选样式。

**完备性自检**（写本页 manifest 前问 3 遍）："本 page 每个**有录制真值**的元素都对账了吗？
无真值元素都进 untested_skipped(no_recorded_oracle) 了吗？表单默认值都和 expected_android /
源码默认值比过了吗？" 任一答否 → 补做再退出。**禁止**写 "本轮未深入测试交互" / "留待后续
visual-verify"，**禁止**为补真值驱动安卓设备。

FOR EACH page IN batch_json.pages:

  # B.-1 关弹窗：已内置于 B.2 的 hmos_capture_page_e2e.py（保守词表+BACK 排水，2026-07-12）。
  # 仅当你手工接管导航时才需要人肉排水（同款规则：只点 关闭/取消/我知道了/跳过 类明确关闭词，
  # 禁点"确定/同意/立即开通"前进钮；关不掉的弹层本身可能就是 finding，交对比段别死磕；
  # 词表+BACK 都关不掉的形态 → 写 BLOCKED 单上报，**由主会话派 ad-profile-builder** 学
  # ad_profile.hmos.json——你没有子代理派发权（`spawn_agent` 归主会话），禁自派/禁在本 chunk 内死磕）

  # B.0 是否被上游阻塞？
  IF page.page_id IN prior_findings.blocked_pages:
      write BLOCKED_P{page_id}.md (引用 blocked_by_md_path)
      pages_status[{page_id}] = {status: blocked}
      CONTINUE

<!-- SECTION:B0.5-via-variant -->

<!-- SECTION:B0.6-dialog -->

<!-- SECTION:B1-data-state -->

  # B.2 到页+采集打包（★2026-07-12 机械化——旧 B.-1排水/B.2 walk_to/B.3 HMOS截图段整体
  #   由一次脚本调用包办：reset(仅force-stop)→排水→导航(安卓reach_path重放→链走,五级降级
  #   匹配+滚动/瞬态/BACK救场梯,动作锚定位置模型)→入口锚定到达→截图+dumpLayout。
  #   **失败即证据**：每个失败出口自动带证据包(现场截图+dump+步序+期望vs实际对照),你拿包
  #   直接写单,禁重导航重dump、禁"更努力到达"）
  python3 $SKILLS_ROOT/arkts-visual-verify/scripts/hmos_capture_page_e2e.py \
      spec/toolkit-fact-tree.json --page "$PAGE_ID" --trip "$TRIP_ID" \
      --target {hmos_target} --bundle {hmos_bundle} --ability {hmos_ability} \
      --shots-dir spec/visual-verify/screenshots/harmony/round-{N}/$TRIP_ID
  # H2E_JSON = 上面 stdout；H2E_EXIT = 其 exit code（bash `$?` / PowerShell `$LASTEXITCODE`）
  # 退出码路由（机械，无判断空间；单格式全走 fix-file-schema 既有 kind）：
  #  0  ok → JSON 直抄 manifest（nav_by/verify_confidence/hop_n/reach_path/elapsed 禁重计时），
  #          verify_confidence=low **不是失败**（入口锚定：页烂照采），继续 B.3 拼图
  #  21 ok+素材 → 同 0 继续采集对比（导航已成功、下游判定不受影响），**另**出素材单：
  #     · JSON.text_mismatches[] → 逐条 ALIGN trigger_text_mismatch P1（带 matched_by/expected/actual）
  #     · JSON.layout_drifts[] → **单出在父页头上**（page_id=parent_page，不赖目标页）：
  #       android_first_screen=true → ALIGN_P{parent}_layout_drift_{trigger-slug}.md
  #       （category_pattern=layout_drift, fixer_layer=ui, P2；§2 期望=安卓首屏含'{trigger}'
  #        （{parent}.android.xml 实证），§3 实际=鸿蒙滚动 {scrolls_needed} 屏才出现）
  #       android_first_screen=false/null → 只记 manifest note 不出单（安卓也在折叠区/无档，非漂移）
  #       去重：B.4 多模态若已对同 parent 页报了同元素的位置/折叠差异 → 并进一张（同 page_id 内 LLM 拍板）
  #  20 trigger_missing → **负向判决，过复核门再写单**（见下方铁律 R9）：evidence.search_exhausted
  #          =true 且视觉复核通过 → ALIGN_P{page}_trigger_missing_hmos.md P0 fixer_layer=feat
  #          （evidence 齐全：parent_page/parent_anchor/expected_trigger/tried_strategies/
  #           search_exhausted/hmos_clickables/现场截图/android_baseline——B.0.5 同 schema）；
  #          search_exhausted=false / 复核存疑 → 手工补扫完再判，仍缺才 P0，否则降 low_confidence 提示单
  #  22 click_no_effect → CRASH_P{page}_nav_failed_….md hint=button_dead（evidence.edge 指明哪条边）
  #  23 parent_unreachable/hop_limit → 单出在链上最早不可达的父页 + 阻塞子树（Step 4.B），
  #          本页 pages_status=blocked 引用之；若断点页本 batch 已出过单则只做引用不重复出
  #  24 escaped_app → SKIPPED（不算 bug；脚本已自动拉回 app）；若该 trigger 树上声明为应用内
  #          跳转 → 改写 wrong_target 素材
  #  25 app_crash → CRASH_P{page}_app_crash.md
  #  26 empty_state → B.1 数据态自愈梯（配方 device=harmonyos；重放后重调本脚本；无配方 →
  #          SKIPPED_DATA_REQUIRED 按 fix-file-schema 4.1.5）
  #  27 dump_unavailable / 14 screenshot_failed → 运维路径：重试一次，仍败写 partial manifest 上报
  #  2  边界拒跑 → dialog 走 B.0.6 / trip_1 链页归主会话——检查你走错了分支
  # 手工接管（例外，如 nav 数据缺口 unstable）：按 §导航方式 Compose 规则自走，到页后
  #   重调本脚本 --capture-only 收尾（就地截图+dump，nav_by 覆写 "llm"）

  # B.3 sbs 拼图（安卓 baseline=Phase 2 录制产物直接复用，HMOS 侧图/dump 已由 B.2 脚本落盘）
  按 references/phase4-capture.md：拼 sbs（baseline 缺失场景见 2.1-a——SKIPPED 路由回 Phase 2）

  # B.3.5 结构 oracle（确定性，多模态之前先跑）—— P0-B
  按 references/phase4-multimodal.md 的 2.2-pre：
  跑 structural_diff.py（Android dump = Phase 2 存的 .android.xml + HMOS dump = B.3 取的 .hmos.json）
  → 硬差异(缺/多/序)入合并集；component_checklist + position_hints 注入 B.4 的多模态 prompt。
  两端 dump 任一缺失 → 跳过本步，仅多模态（不阻断）。

  # B.4 多模态对比（Android vs HMOS）
  按 references/phase4-multimodal.md 流程（prompt 带上 B.3.5 的核对表划重点）
  产 ALIGN/CRASH/URL findings（按 references/fix-file-schema.md）
  # 合并去重：多模态 differences[] ∪ 结构 oracle differences[]，按 phase4-classify-write.md 2.3-0 规则

<!-- SECTION:B4.5-dual-oracle -->

  # B.5 测出边
  FOR edge IN page.edges_to_test:
      IF edge.contract_uncertain OR (NOT edge.trigger.label AND NOT edge.trigger.resource_id):
          # fact-tree 数据不全，跳过本 edge 测试
          NOTE in manifest.unstable_edges
          CONTINUE
      
      # B.5.a 安卓可行性 = 查录制证据（★单侧化 2026-07-12：禁实时驱动安卓验证边）
      # 证据三级（任一命中即"安卓端该 edge 可行"，manifest 记 oracle_source）：
      #   1) tree.pages[edge.to_page].screenshots.{trip}.reach_path 含"从本 page 经该 trigger"
      #      的一跳（Phase 2 实走过——最强证据）
      #   2) 本 page 的 blackbox_behavior.{trip}[] 有该 trigger 且 outcome=page_change（账本实测）
      #   3) edge.to_page 的 inbound_triggers 有源码锚点 evidence_file:line（编译期声明——最弱，
      #      据此出的失败单标 confidence=declared_only，提示 fixer 先核安卓真机行为再动手）
      # 三级全无 → NOTE manifest.unstable_edges(reason=no_recorded_oracle)，跳过本 edge
      # （旧 FACT_TREE_INVALID_EDGE 的"安卓实点失败"判据随实点一起废止；树数据弱走 unstable_edges）

      # B.5.b HMOS 端点击 + verify
      hmos_result = python3 click_and_verify_edge.py \
          --device harmonyos --target {hmos_target} \
          --trigger-text {edge.trigger.label} \
          [--trigger-resource-id {edge.trigger.resource_id}] \
          --verify-text {edge.verify_signal} \
          --verify-timeout-ms 5000
      
      IF hmos_result.status != "ok":
          # 真 HMOS bug
          # 计算 blocks_subtree (该 edge 的 target + 该 target 的所有 reachable downstream)
          blocked = compute_subtree(edge.to_page, fact_tree)
          write CRASH_P{page_id}_nav_failed_{page_id}_to_{edge.to_page}.md
                with v4_edge + blocks_subtree=blocked
          NOTE in manifest.findings + manifest.blocks_subtree_propagation
          # 不要中断本 batch；这个 edge 失败只影响子树，本 batch 内其它 page 继续测

      ELSE:
          # HMOS ok → 在 edge.to_page 上
          # B.5.c 顺手测 back 是否能回 page（back 预期=树导航契约：child 返回应落 parent；
          #   无 parent 关系记录时 back 失败单标 low_confidence，不武断 P0）
          back_result = test_back_to_parent(expected={page.page_id}, device=harmonyos)
          IF back_result.failed:
              severity = back_critical(edge) ? "P0" : "P1"
              write CRASH_P{edge.to_page}_back_failed_{edge.to_page}_to_{page.page_id}.md
                    with severity={severity} + actual_landed
              am-start page or walk_to(page) 强拉回，保 BFS 不漂

  # B.6 黑盒兜底：已下沉到 Phase 2（见铁律 R8；反哺 variant 走 B.0.5），本 sub-agent 不跑黑盒

  # B.7 写本页判断账（★2026-09-07 机械化：不再在批末尾手拼 manifest；本页判断字段落 pages/<pid>.status.json）
  #   把下面这条**挂在本页最后一条本来就要跑的 Bash 调用里**（同计时铁律：禁为记账单独发工具调用）：
  #   python3 $SKILLS_ROOT/arkts-visual-verify/scripts/page_status.py --batch-dir spec/visual-verify/batches/{batch_id} \
  #       --page "$PAGE_ID" --status <pass|fail|partial|crash|blocked|skipped> --elapsed nav=<s>,capture=<s>,compare=<s>,functional=<s>,edges=<s>,write=<s> \
  #       --set similarity=<x> --set arrival_confidence=<..> [--set note="..."] [--json '{"interaction_test_summary":{...},"functional_checks":{...},"edge_results":[...]}']
  #   你只写**判断**（status/similarity/note/back_*/edge_results/interaction_test_summary/functional_checks/elapsed…）；
  #   ui_findings/feat_findings/fix_files/high|medium|low_count 由 build_batch_manifest.py 从你写的工单文件算——**不要手填**，
  #   填了也会被工单覆盖并记 count_mismatch。下面的条目 schema 仍是字段参考。
  #   ★完成声明（N2/N7，2026-09-07）：本页**全部**步骤做完、工单/占位已落盘、完备性自检三问答"是"之后，再追加
  #     `--done --round {N} --trip {trip_id}`。脚本当场核验（终态 status / round-N 有该页截图或 sbs / fail 有工单或 blocked_by /
  #     blocked 有占位），不过则 exit 3 且不置 done——**别为了过而改 status**，回去补齐。只有 done 且证据齐的页，续跑时才会被跳过；
  #     没标 done 的页重派时一律重做（宁可重做不可漏）。
  pages_status[{page_id}] = {
      status: pass | fail | crash,
      similarity: ...,
      high_count: ..., medium_count: ..., low_count: ...,
      edges_tested: N, edges_failed_hmos: M, edges_failed_factree: K,
      back_tested: true/false, back_failed: true/false,
      fix_files: [...],
      # ★计时账单(2026-07-10 插桩,必填;validate_batch_output 会警告缺失)★
      # 采集铁律:计时命令**搭在本来就要跑的 Bash 调用里**(步骤首条命令前记 epoch 秒 S、
      # 末条命令后打印 T_<桶>=now-S；bash 用 `date +%s`，PowerShell 用 `[int](Get-Date -UFormat %s)`),**禁止为计时单独发工具调用**——
      # 否则插桩本身制造 LLM 回合开销。桶边界:scenario=B.-1/2.-1造态 nav=B.0-B.2导航+确认
      # capture=B.3截图/dump/sbs compare=B.3.5+B.4 functional=B.4.5 edges=B.5 write=B.7+写单
      elapsed: {scenario: <s>, nav: <s>, capture: <s>, compare: <s>,
                functional: <s>, edges: <s>, write: <s>},
      # 行为对账铁律证据（必填，B 审核员规则 5 据此判定；详 Phase B 开头铁律段。单侧化 2026-07-12）
      interaction_test_summary: {
          tested_count: <int>,        # 本 page HMOS 实测且有录制真值可对账的元素数
          diff_count: <int>,          # 与录制真值有差异的数量（每条立独立 finding）
          untested_skipped: [         # 跳过的交互 + 原因（no_recorded_oracle / 长按 / 需特定数据态）
              {element: "<selector>", reason: "<具体原因>", oracle_source: "<functional_checks|ledger|source|none>"}
          ],
      },
  }

### Phase C: 收尾

**★manifest.json 由脚本拼，不手写（2026-09-07）**：
```bash
# 1) 批级判断（有则写，没有可省）：spec/visual-verify/batches/{batch_id}/batch_notes.json
#    {"scenario_results":[...], "unstable_edges":[...], "coverage_debts":[...], "escalations_adjudicated":[...],
#     "systemic_candidates":[...], "blocks_subtree_propagation":[...], "blackbox_stats":{...}, "page_signature_map":{...},
#     "fatal_error":null, "started_at":"<进 Phase A 记的 date -u>", "finished_at":"<现在>"}
# 2) 拼装 + 反查（findings/fix_files/计数/占位/耗时 全部从工单与磁盘算）：
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/build_batch_manifest.py --batch-id {batch_id} --round {N}
#   exit 0  = 落盘 manifest.json，退出
#   exit 20 = 落盘了，但 assembly_checks.hard 里有「判断与证据冲突」（pass 却有工单 / fail 却无工单无关联 /
#             判定却无截图 / blocked 却无占位 / 批内页缺判断账）→ **回到那页核对判断**（改 status、补工单或补截图），
#             重跑本命令；禁止改 manifest 字段绕过。validate_batch_output 会把 hard 原样判成 issue。
```
下面的 manifest schema 保留作**字段参考**（哪些键存在、语义是什么）；其中账目字段（findings/fix_files/*_count/
blocked_placeholders/duration）由脚本算，判断字段由 pages/*.status.json 与 batch_notes.json 提供。

写 manifest.json（字段参考）:
{
  batch_id, current_round,
  started_at, finished_at, duration_seconds,   # ★必填(2026-07-10)——进 Phase A 第一条命令记 date -u,
                                               #   写 manifest 时算差;历史上 13 个 batch 只有 4 个填了,
                                               #   耗时分析只能靠文件 mtime 验尸。validate_batch_output 警告缺失
  scenario_chain, scenario_results,
  pages_status: {...},
  findings: [...条 ALIGN/CRASH 高层摘要],
  systemic_candidates: ,
  blocks_subtree_propagation: [
      {root_cause: "CRASH_P0001_nav_failed_HomeActivity_to_MineFragment",
       blocked_pages: [AccountInfoActivity, AboutUsActivity, ...]}
  ],
  unstable_edges: [...contract_uncertain 跳过的],
  // 黑盒兜底产出
  blackbox_stats: {
      total_unknowns_explored: 12,
      missing_page_findings: 3,
      missing_edge_findings: 5,
      decoration_filtered: 2,
      escaped_app_count: 2
  },
  page_signature_map: {                         // 给主会话用：本 batch 期间观察到的 page sig
      "HomeActivity":   "...|s1f0c|tabcd",      // 用于 lookup_page_signature
      "AccountInfoActivity": "...|s27510|t...."
  }
}

并在 batch 结束时更新全局缓存:
  spec/visual-verify/batches/_global_explored_clickables.json
    schema: {signature: {first_explored_at: ISO, from_page: str, outcome: str}}

完成后 sub-agent 退出。主会话读 manifest，做跨 batch 阻塞传递 + systemic 聚类。

## 重要约束（铁律）

R1: 永远不用 am-start 直跳非 launcher 内部页（HMOS 单 ability 架构，跳不到）
R2: 失败 edge 先查**录制真值**（B.5.a 三级证据）再判 HMOS bug（避免冤枉）；仅声明级证据的单
    标 confidence=declared_only。★Phase 4 全程禁驱动安卓设备（唯一例外：B.4.5 步骤 6 门禁对照
    实验且录制对照证据全无时走 gate_experiment.py）
R3: HMOS 端测 edge 失败时不要重试 > 3 次（避免假阳性 + 浪费时间）
R4: 跨 page 的 back 预期 = 树导航契约（inbound/parent 关系：从 child 返回应落 parent）；
    无 parent 记录的 back 失败标 low_confidence（★不再实时驱动安卓当 back 基准）
R5: 多模态对比图严格 resize ≤1800px（不然 API 报错整轮报废）
R6: manifest 必须落盘，即使中途 batch 中止也要写 partial manifest
R7: 不读 spec/toolkit-fact-tree.json 全文，需要时读 spec/visual-verify/batches.json (本 batch 段)
R8: 黑盒探索已下沉 Phase 2（Android 端一次性勘察 + 反哺 fact-tree）。
    sub-agent 不主动跑黑盒；遇到 page_id 含 "#via=" 的反哺节点统一走 §B.0.5
    流程：parent walk_to → 严格 text 匹配 → 失败降级模糊匹配 → 全无降级写
    ALIGN(trigger_missing_hmos, P0)，文案近似命中写 ALIGN(trigger_text_mismatch, P1)
R9: **负向判决复核门（2026-07-12）**：机械判定分两类且风险不对称——正向观察（点了没反应/
    落错页/outcome 与账本不符）是直接观测，可径直出单；**负向判决（"入口不存在""元素缺失"，
    含 exit 20 与 B.3.5 结构 oracle 的 missing 类）本质是证明不存在**，dump 只含已渲染节点，
    折叠区/懒加载虚拟列表/折叠面板/页内横向 tab/图内文字都会造假阳性（实测：'关于我们'在
    鸿蒙折叠区，无滚动救场就是一张假 P0）。写 P0 前必须：①evidence.search_exhausted=true
    （脚本已滚到真底）②你亲眼读一次证据截图复核（你是多模态 agent，这一眼很便宜）。
    任一不满足 → 手工补扫/降 low_confidence，绝不直出 P0。

## 增强工具（2026-05-22 借鉴 HomeTrans）

### page_signature 双重确认（自动）

`click_and_verify_edge.py` 默认输出 `pre_click_signature` + `post_click_signature` + `page_changed`。

**用法**：
- `page_changed=True` + `verify_found=True` → 正常成功
- `page_changed=False` + `verify_found=True` → status="verify_text_but_page_unchanged"
  含义：verify text 在 click 前后都存在，**click 可能根本没生效**（button dead）。
  应当报 NAV_FAILED 而不是 OK——这是 HMOS button 接错 handler 的典型现象，
  scan 项目 "退出登录失败" 就是这种 case
- `page_changed=True` + `verify_found=False` + `verify_timeout` → 跳了别处但没到预期页
  含义：可能跳到错误页，或动画太慢——按 NAV_FAILED 处理但 hint=jumped_to_wrong_page

### escaped_app 检测（需 sub-agent 显式打开）

调用 `click_and_verify_edge.py` 时传 `--expected-bundle com.example.demoapp.hm`。
返回 `status=escaped_app` + `escaped_to_bundle=<外部 app bundle>` 时，**不要当 HMOS bug 报**：
- 这是真实业务行为（如点击"联系我们"跳浏览器、点支付跳微信）
- 写 SKIPPED placeholder（或不写，看主代理决策），不要写 CRASH_NAV_FAILED
- 之后 force-stop 主 app + restart 回到当前测试态

```text
# 推荐调用模式
python3 click_and_verify_edge.py \
    --device harmonyos --target {hmos_target} \
    --trigger-text "{label}" --verify-text "{verify_signal}" \
    --expected-bundle {hmos_bundle} \
    --verify-timeout-ms 5000
# exit 6 → escaped_app；不算 HMOS bug
```

### restart_first 兜底（back 失败后用）

当 back 测试连续失败 ≥ 2 次或 app 漂到未知态时，用 `walk_to.py --restart-first` 强制恢复：

```text
python3 walk_to.py \
    --device harmonyos --target {hmos_target} \
    --page-id {当前应该在的 page_id} \
    --fact-tree spec/toolkit-fact-tree.json \
    --bundle {hmos_bundle} --ability {hmos_ability} \
    --restart-first   # ← 加这个 flag
# 内部: force-stop + aa start + 5s 等冷启动 + walk
```

适用场景：
- back 让 app 漂到非预期页 → restart_first 干净恢复
- escaped_app 后回主 app → restart_first
- 测了 10-15 个 page 后定期 hygiene → restart_first 清积累状态

### 失败分级表

| click_and_verify_edge 输出 | 写什么 markdown |
|---|---|
| `ok` + `page_changed=true` | (无 finding，正常通过) |
| `verify_text_but_page_unchanged` | CRASH_*_nav_failed_*.md，hint=button_dead |
| `verify_timeout` + `page_changed=true` | CRASH_*_nav_failed_*.md，hint=jumped_to_wrong_page |
| `verify_timeout` + `page_changed=false` | CRASH_*_nav_failed_*.md，hint=click_no_effect |
| `trigger_not_found` | 有录制证据（B.5.a 1/2 级）→ CRASH_*_button_missing（安卓有、鸿蒙无，真迁移缺陷）；仅声明级/无证据 → NOTE unstable_edges（树数据弱，不冤枉鸿蒙）|
| `escaped_app` | （不当 HMOS bug；可写 SKIPPED 或忽略） |
| `click_failed` | CRASH_*_nav_failed_*.md，hint=hdc_input_failed |
```

---

## 错误恢复策略

| 场景 | sub-agent 行为 |
|---|---|
| scenario 失败 | 整 batch status=batch_blocked，所有 page 写 SKIPPED，退出 |
| walk_to(starting_page) 失败 | 同上 |
| 当前 page 截图失败（app crash 等）| 写 CRASH_P{page_id}_app_crash.md，跳过该 page 继续下一个 |
| edge 测试触发 app crash | 同上 + 标该 edge 为 trigger_crash |
| back 测试导致 app 漂到未知页 | am-start launcher → walk_to 当前 page，重试一次；仍失败标 navigation_unreachable |
| hdc 设备掉线 | 整 batch 中止，写 partial manifest 退出，让主会话决定是否换设备（★安卓设备不在环内，其状态与本 batch 无关）|

---

## 调用契约（主会话注入）

主会话调用 sub-agent 时 prompt 渲染参数：

```bash
# 2026-09-07 起：不手工 render_template，一律脚本渲染（条件段按批内页种类机械注入；凭证 prompt_manifest.json；
# validate_batch_output.py 事后按树复算对账，缺段=FAIL）
python3 $SKILLS_ROOT/arkts-visual-verify/scripts/fill_batch_prompt.py \
    --batch-id <batch_id> --round <N> --role full|capture --nav-mode auto \
    --android-serial emulator-5554 --hmos-target 127.0.0.1:5555 \
    --android-pkg <pkg> --hmos-bundle <bundle> --hmos-ability EntryAbility \
    [--blocked-pages '<JSON>'] [--retry-edges '<JSON>'] [--b-gaps '<JSON>']   # b_gaps 仅 B 审核重派
# → spec/visual-verify/batches/<batch_id>/prompt_round<N>.md（派发用全文）+ prompt_manifest.json
# 槽位语义（脚本填）：role / nav_mode(auto=按 tree.source.toolkit) / batch_id / trip_id / N / 设备五项 /
#   blocked_pages_json / retry_edges_json / b_gaps_json / retry_reason / batch_json_inline（本批 batches.json 片段内联）
# ★android_serial 单侧化后仅 B.4.5 步骤6 gate_experiment 兜底路径可能用；常规流程不驱动安卓
```
