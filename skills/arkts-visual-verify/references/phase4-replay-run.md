# Phase 4 鸿蒙一笔画回放 — 运行手册（2026-07-23）

> **状态:投产主路。** 一笔画回放是**鸿蒙侧覆盖的主方式**(与安卓 Phase 2 边遍历对称),不是实验特性——
> 覆盖主链(Home→大纲→模板→PPTFile)一律走一笔画。**只有过程中撞阻塞时才按节点回退页粒度保底**:
> 触发条件 = replay_exec 级联升级(exit 32)/ 回位连败(`needs_pagegranular_fallback`)/ 异步时序·前置态
> 震荡够不到的节点(见 [`phase4-replay-judge.md`](phase4-replay-judge.md) J1.5 + [`phase2-edge-walk.md`](phase2-edge-walk.md))。
> **保底只兜"一笔画够不到的那几个节点",不是整趟降级页粒度。**

回放全链:**编译(compile_replay_plan) → [切段 slice_batches,可选] → 执行(replay_exec,纯机械) → 判定(judge 出单) → 修复(visual-fixer) → 回归**。
本手册讲**编译+切段+执行**(前半程);**判定+修复+回归闭环接线见 [`phase4-replay-judge.md`](phase4-replay-judge.md)(J1–J5,复用主线 Phase 5/6+visual-fixer+Phase 6.5 自持闭环,不另造)**。
capture_manifest 与页粒度 role=capture 契约同构,故下半程零改复用。
设计根由见 phase4-replay-compile.md / phase4-replay-executor.md;本文是**怎么实际跑**。

## 0. 铁律:先读全树字段,别在运行时重新发明(2026-07-23 用户纠正,最重要一条)
树里安卓侧已定性的账**必须尊重**,别把它已经处理过的当待办:
- `blackbox_behavior[].outcome` 以 `skipped_` 开头(skipped_homogeneous/skipped_in_plan/skipped_destructive)
  = node_sweep **已做过同构去重/已定性**,**不是待测功能点**,消费时直接跳过。
- 忽略此标记 → 把 18 张同构模板卡、9 条动态示例文案全拉进 reconcile → 侵入 + 拖时间 + 逼你在运行时
  重造同构去重(答案本就在树里)。**教训:消费树先读全字段,尤其 outcome/status 这类『已定性』标记。**
- reconcile 的元素**主来源 = `functional_checks`(该页干净功能点清单)**;blackbox_behavior 只补真实观察(非 skipped)。

## 1. 前置产物(缺一不可)
| 产物 | 谁产 | 内容 |
|---|---|---|
| `spec/toolkit-fact-tree.json` | 安卓侧流水线(indexer+ART+反哺) | 含 runtime/functional_checks/blackbox_behavior;waited_s 需已反哺 |
| `spec/visual-verify/edgewalk-run2/walk_plan.json` | plan_edge_walk.py | 边粒度 DFS 步序(kind:push/dialog/tab_switch…) |
| 安卓基线 dump ×2 轮 | 两轮遍历的 shots/*.xml | dump-diff 识别动态文案(哨兵去噪) |
| `spec/visual-verify/replay_annotations.json` | **编译期 LLM/人手写(每 app 一份)** | 见 §3 |

## 2. 编译:产 replay_plan_hmos.json（机械,零 app 常量在代码里）
> 下文 `$SCRIPTS` = `$SKILLS_ROOT/arkts-visual-verify/scripts`（全 py，三平台同一份；Windows `python3` 读作 `python`，见 windows-setup.md）。
```text
python3 $SCRIPTS/compile_replay_plan.py \
    --walk-plan <walk_plan.json> --tree <fact-tree.json> \
    --baseline-dir <轮2 shots目录> --baseline-dir2 <轮1 shots目录> \
    --annotations <replay_annotations.json> --out <replay_plan_hmos.json> [--default-wait 4] \
    --android-unreached <安卓那轮的 $EW/reason_overrides.json> \
    --android-edges <安卓那轮的 $EW/edge_results.json> \
    --walk-index <本趟对应的 walk 下标>
```

### 2.0 三个来源参数的固定约定（2026-09-14 立规；混用 = 全表漂移）

| 参数 | 取什么 | 谁产 / 怎么核 |
|---|---|---|
| `--baseline-dir` | **本趟**安卓基线目录 `spec/visual-verify/screenshots/android/<trip_id>/` | `walk_place_baselines.py` 落位（每页 `<page>.android.xml` + `<page>.png`）；**按趟**取，趟名即 `walk_plan.json` 的 `walks[i].trip_id` |
| `--baseline-dir2` | **首轮**基线 dump 目录（同一趟的另一轮，用于 dump-diff 去噪） | ⚠️ 该目录**没有任何脚本读写点**（全仓脚本零引用），是运行方手工归置的历史轮次 dump；本工程实例叫 `spec/visual-verify/_shots_round1/`（只有 `*.android.xml`，无 png）。**换工程时以实际产物目录为准**，编译前先 `ls` 确认里面是 `*.xml` |
| `--walk-plan` / `--android-unreached` / `--android-edges` | 必须取自**同一次**安卓边遍历的输出目录：`walk_plan.json`、`reason_overrides.json`、`edge_results.json` **同目录** | 边遍历产物不在本工程时以实际产物目录为准（本工程实例为 `spec/visual-verify/edgewalk/`）。**混用不同次遍历的三份会让全部步骤的 `android_status` 漂移**——0912 实证 128 步全变 |

★**两个 baseline 目录是同一趟的两轮**（做 dump 差分识别动态文案），**不是两个趟**；每趟各编一次。
★`--walk-index` 按 `walk_plan.json` 的 `walks[i].trip_id` 对号（见下条）。
★参数名以 `compile_replay_plan.py` 的 argparse 为唯一真源（`--help` 为准）：`--walk-plan` / `--tree` / `--baseline-dir` /
`--baseline-dir2` / `--annotations` / `--out` / `--default-wait` / `--walk-index` / `--android-unreached` /
`--android-edges` / `--grounding` / `--hmos-profile` / `--auto-wait-cap` / `--allow-zero-functional` /
`--allow-no-destructive-signal`（2026-09-14 核对一致）。
★`--walk-index`（2026-09-11 实爆，**每趟必传**）：缺省 0 = 安卓计划里的第一条走（通常是登出态首启趟）。CodeX_0829 首跑两趟
都没传，登录趟的计划其实编自登出趟那 77 步，登录趟独有的 144 步（含 type/renav）从未被编译——两趟 tap 数一样、跳过数一样就是这个原因。
分趟编译时按 `walk_plan.json` 里 `walks[i].trip_id` 对号：trip_1 → 含首启链那条，trip_2 → 主趟。
★`--android-edges`（2026-09-11，翻译对等性，必带）：读安卓边真值。安卓 `confirmed` 的边**不许静默跳过**——无判位依据的照发并标
`expect.arrival_confidence="unanchored"`（执行器按屏幕签名变化判弱到达，不按哨兵，绝不因无哨兵交接）；无触发物的从安卓运行时
`control.rid/text` 补身份（补来的身份必须重过破坏性词表）；安卓在本趟被登录/会员门拦住的边发 `expect_blocked` 探测步（点一次、验落点、
成对 back 回起点、不下钻）：落到门 = `GATE_HELD` 正常，放行进去 = `GATE_MISSING` → `_blame` 判 `gate_missing_in_hmos`（security，必出单）。
编译期落 `translation_ledger_<trip>.json`：安卓每条 tap 边的鸿蒙去向（emitted / emitted_unanchored / emitted_expect_blocked /
folded_to_reconcile / skipped+reason），任何 skip 必带非空 `skip_reason`。
★`--android-unreached`（2026-09-10 鸿蒙首跑实证，必带）：安卓运行时已判「这一趟到不了」的页（一次性门已消费 /
数据态缺 / 禁点动作才能到），编译期一律不发动作步，改记 `skip_reason=android_unreached_<安卓的 reason>` 并把安卓原话透传进
`android_attribution`。判据看哪一端有讲究：tap/deeplink 是「去够目标页」看 `to`；**gate_pass 是「站在门那一页按放行键」看 `from`**
（第一版只看 to，把卡死两趟的那个放行步照样发了出来，真产物干跑抓出）。back/verify/reconcile 不拦。
病根：安卓花 2×49s 才买到「隐私门已被消费」这个结论，写进了未达归因与 BLOCKED 单，但编译器此前**零处引用**——同一个发现鸿蒙又撞一次，
且无人接时直接停摆。★两个基线目录是**同一趟的两轮**（做转储差分识别动态文案），不是两个趟；分趟各编各的计划。
★auto 转场边 → `wait` 步（F6，2026-09-11 零介入复跑实证）：安卓 `auto_transition=True` 的边（首启门自动弹出 / Splash 倒计时 /
宿主装默认子页）**不点任何控件、只等**（实走 waited_s 2.4–2.6s）。此前无控件身份一律编成 `untranslatable_no_control_identity` skip，
鸿蒙既不等也不判到达，下一步在还没转场的屏上找控件必死（失败 dump 里 app 文本 0 条；两趟零介入都死在第 8 步）。现在编成
`action=wait`：`wait_budget_s`=max(默认×2, 安卓 waited_s×1.5, wait_hint countdown×1.5) 上限 `--auto-wait-cap`（默认 30s，上限是 app 相关量，倒计时更长的 app 调大），`wait_hint` 透传，`expect.sentinel`
照常（无哨兵标 `arrival_confidence=unanchored`），翻译账记 `emitted_wait`。执行器 `wait`：轮询到哨兵 / identify==to / 别名组 / 歧义组 /
wait_hint 文案任一命中 → `settle_dump` 后采集入账押栈（`AUTO_ARRIVED`）；等满没到 → `AUTO_NOT_OBSERVED`（屏没变）或
`AUTO_LANDED_ELSEWHERE`（落到别页），进 `escalations` 但 `_blame` 记 `auto_transition_missing_in_hmos` / `auto_transition_diverged`
且 **`product_defect=None + needs_verification`**——不直接进 must_ticket，judge 看失败 dump 核实"没实装"还是"更慢/条件不同"；
等待步没发过任何点击、位置没丢，**不交接**，后续步按各自判位如实入账。
wait 开始前先判位（T-1，零介入复跑实证）：已站在**已知别页**（非 from/to、不在二者别名/歧义组）= 发散发生在前一步之内被其耗时盖住
→ 立即 `AUTO_LANDED_ELSEWHERE(diverged_before_wait)`，不空等预算；识别不出时不下判、照常等。
★reconcile 元素的屏上文本身份从安卓 dump 取（T-4，零介入复跑实证）：元素 `trigger_text` 是树/LLM 的描述名（「场景选择标题」），
屏上不会有；它的 rid 在安卓基线 dump 里带着真实文案（`tv_title`→「你常使用的PPT演示场景」），鸿蒙屏上同一句在。此前执行器拿描述名
找不到就盖 `control_missing_in_hmos`——一页 7/7 假 P0。编译期 `rid_texts()`+`attach_element_identity()`：`match_labels` 头部插安卓
dump 文案（rid 驼峰/下划线互认：树里常是 ViewBinding 的 `cbOne`，dump 是 `cb_one`），并标 `text_identity_source ∈
{android_dump_rid, android_dump_name, hmos_profile, None}`；动态文案不当身份。执行器：**无身份的元素找不到≠缺失**（无证据≠反证），
记 `unverifiable_no_screen_identity / blame_hint=no_screen_identity`，只有带身份仍找不到才是 `not_found / control_missing_in_hmos`；
judge `readjudicate` 的 `alabel()` 同样驼峰互认。离线模拟（replay-t1d 实采 dump）：observe_only 元素命中 3→13/16，3 个无身份改判不可判。
★完整跑法归因后的 A/B 档修复（2026-09-11，replay-t1f 77 步零介入跑 12 次熔断逐条归因；每条先离线在 t1f 真实产物上验证再落）：
- **哨兵不收数值形文案**（②）：`value_shaped()`——手机号/`ID:…`/缓存大小/百分比/货币/日期时间/版本号这类**文本形状**不当哨兵
  （两轮同账号它们不算 dynamic）。t1f 实爆："我的"页哨兵=手机号/用户ID/缓存大小 → 鸿蒙一个不中 → 会员中心的「立即开通」单词把"我的"
  认成会员中心（WRONG_LANDING 假 P0 + 回位错）。重编译只改这一页的哨兵。**「≥2 哨兵只中 1 词不认页」的硬规则离线 A/B 否决**
  （101 份 dump：首页 2 哨兵之一是输入框占位文案，13 份正确识别全变 None）→ `identify_scored(single_hit_ok)` 参数化、默认旧行为。
- **rid-only 控件的身份来源**（①）：tap 步 `match.text_identity_source ∈ {trigger, android_dump_rid, None}`；rid-only 但安卓基线 dump
  里该 rid 有 text/**content-desc**（`rid_texts` 现在也收 content-desc）→ `match.android_dump_text`，执行器 rid 找不到时按它兜底定位
  （`matched_by=android_dump_text:*`，degraded）。两者皆无（纯图标）且鸿蒙 dump 无该 rid → `_blame` 记 **`no_screen_identity`
  （product_defect=None, needs_verification）**，不再 `control_missing_in_hmos` P0（t1f 步 17/38：`iv_home_vip`/`iv_vip_enter` 无文案无 desc）。
- **破坏词表连屏上文案一起过**（⑤）：`identity_is_destructive(text, rid, blacklist, screen_text)`——三处身份接纳点（门探测 / 救回 / 主路径）
  都把安卓屏上该 rid 的文案过表；rid-only 的图标控件此前对词表不可见。
- **门探测判据**：`gate_landing_verdict` 落点仍是源页 ⇒ `GATE_NOT_EXERCISED`，**不论屏有无局部变化**（t1f 步 29：输入为空点「立即生成」
  → toast「内容不能为空」→ 旧判据滑到 GATE_MISSING 假安全单）。NO_NAV 归因新排除项⑥：屏签名变了但没导航 → `feedback_without_nav`
  （needs_verification），不按 handler 空实现出单。走序 tap 的同形（弱到达）不改判，只记 `identified_as=源页` + 页槽注记，且**不押栈**。
- **救回的探测步导航类型按目标类型推**（③）：上游 skip 的 `kind` 是跳过理由（scope_exit）不是导航类型，沿用它 → 到达不押栈 → 配对 back
  判"没进去"跳过 → 位置漂移连锁 ABANDON。现在弹窗→dialog，其余→push；执行器 `_is_push` 对 `probe_only`（非门探测）一律押栈（老计划也对）。
- **续跑重建 DFS 栈**（④）：`--resume-from` 按计划模拟 resume_from 之前的押栈/回位（`stack_prefix_from_plan`，coldstart 清栈、探测对抵消、
  门探测不入栈），run.jsonl 首行 `STACK_RECONSTRUCTED`；此前从空栈起跑，t1f 一趟 7 条 back 全 SKIP_no_descend。交接包带 `stack_at_handoff`。
验证：`_tests/test_ab_fixes_pure_0911.py` `test_replay_ab_fixes_exec.py` `test_compile_ab_fixes_e2e.py`；t1f 计划重编译 diff 只含预期字段。

★判位改成「路径先验 + 同平台参考」（F3，2026-09-12，replay-t1g 完整跑法归因后用户定稿）：
- 病：判位是"开放世界分类"——安卓基线算出的 3 个稀有词对全部页打分。别页恰好带本页哨兵词就被认成本页：客服 H5 的常见问题里
  有独立的「一键退款」「取消订阅」节点、关于页标题就是「关于我们」，执行器在 H5 上自称"已确认站在 MineFragment"→ 判控件缺失
  （假 P0 ×2）、62B 因"没到达"不回位 → 人真留在 H5 里丢位置。整页签名不能替代（同页再 dump 签名相同只有 16/53：动态页恒变）。
- 判据：每步只回答三个假设——还在 from / 到了 to / 去了别处。页一旦本趟被鸿蒙采过（`capture()` 四条成功路径登记 `PAGE_REF`：
  文本集 + 各文案 bounds，状态栏带与纯数字剔除），"站不站在这页"用鸿蒙自己那份 dump 比：`on_page_by_ref` = 文本集 Jaccard ≥0.5
  或（有文案同位且 ≥0.15）→ 在；<0.15 且无同位 → 不在；其余不下判。安卓哨兵只负责**第一次到达**（strong/weak/unanchored 三档不变）。
  t1g 121 份 dump 离线回放：撞词现场 J=0.056/0.00 全判"不在"，真站在源页 J=1.0；同页再 dump 53 True / 19 False，19 份里 12 份
  实为已点走到会员中心（对会员中心 J=1.0）、其余为空白过渡屏。
- 接线：① `_blame` ABANDON 的"站在源页"以参考为准——参考说不在 → `wrong_position_not_source_page`（能命名落点）或
  `source_page_unconfirmed`（None/needs_verification）；参考说在 → 哨兵不中也算站对（`source_confirmed_by=reference`）；
  ② 弱/无锚点到达押栈判据：身份仍是源页**且**参考没说离开才不押（撞词页算离开 → 押栈 → 配对 back 真按，62B 自动逃出 H5）；
  ③ back 步：哨兵身份被参考否决则作废（否则根守卫把"站在 H5"当"站在 tab 根"拒按）；④ reconcile 站位：参考优先；
  ⑤ 「别处」命名：哨兵/签名都认不出时按参考找最像的页（J≥0.5 且领先 2×，`landed_by=reference`）。
- 残余风险（不当解决了）：目标页缺失、而实际落到的页恰好带目标页的安卓哨兵词 → 首次到达仍会误判；靠领先倍数 + 编译期撞词表压概率，
  judge 拿截图对安卓基线兜底。
- **F1**：`WRONG_LANDING` 归因看 `matched_by`——降级模糊匹配（char_overlap 等）抓到的未必是计划指名的控件，落错页只记
  `wrong_landing_after_fuzzy_match`（needs_verification）；精确命中才 `routing_target_wrong`（t1g 步 44：字重叠抓到会员横幅）。
- **F4**：back 步先看是否**已站在目标页**（目标页参考说在、非弹窗类 back、屏无模态）→ `SKIP_back_already_at_target` 并弹掉未真正
  进入的那层栈；治被跳过弹窗的配对 back 把续跑重建的真栈弹掉（t1g 步 20 真退出了会员中心）。
- **续跑必须把参考读回来**（t1h 验收实爆）：`PAGE_REF` 只活在进程内存，`--resume-from` 时按 manifest 的 captured/captured_alias 页
  把 `dumps/<node>.hmos.json` 读回（run.jsonl `PAGE_REF_RESTORED`，manifest `page_ref_restored`）；不读回则 8 个交接点里 6 个处于
  "本进程没采过该页"状态，F3 三处判据全部退回哨兵（步 63 仍假 P0、62B 仍不回位）。
- **F4 两条判据**：① 目标页参考说在（非弹窗类 back、屏无模态）；② **DFS 栈顶就是 back 的目标**——被跳过的弹窗的配对 back
  恰是 `kind=dialog`，不能用 kind 排除，栈结构本身就说明"上一层从没进去"（`by=stack`）。参考明确说"不在"时两条都不适用，照按。
验证：`_tests/test_replay_page_ref_f3.py`（10 例）；全套 419 通过。

★计划文案「安卓见过没有」闸（F2，2026-09-12，用户定稿只改编译器）：树/LLM 的描述名（「个人中心」：布局里的死文案，安卓运行时
从不显示）会顺着走序进编译器；安卓边真值按 (from,to,文案) 精确键查不到时**退到 (from,to) 兜底**，拿到的是安卓用**别的控件**
（tv_user_id）确认这对页的记录，于是编译器认定"安卓确认过"照发一个搜死标签的 tap → 鸿蒙必搜不到 → 假 P0（t1g 步 56）。
写回其实早把这条边标成 `runtime.not_reproduced`（"控件不存在，树侧标签错"），断在消费。
- `android_edge_lookup_how` 带出命中方式 label / pair / none；身份来源只有精确命中运行时记录才标 runtime，兜底记录只借 waited_s。
- `label_seen_on_android(from,to,文案)` 三源任一即算见过：树 runtime 用该文案确认过 / 安卓边真值按文案键命中 / 源页两轮基线 dump
  里有这句（text 或 content-desc）。没见过时 `label_gate` 分流：pair 命中且安卓有实测控件 → (from,to) 已由别的步（含可救回的 skip）覆盖
  ⇒ `skip(label_never_observed_on_android, covered_by_steps, android_control)`，无人覆盖 ⇒ 换成安卓实测控件发步（`label_replaced`）；
  none ⇒ 照发但 `text_identity_source=static_unverified`，执行器找不到记 `trigger_label_unverified`（needs_verification）不判缺失。
  门探测步同一闸（`gate_probe_label_unobserved`）。翻译账新增 `label_replaced` / `label_unverified_on_android` / `covered_by_steps`。
- 不能按 `not_reproduced` 一刀切：本树 24 条 not_reproduced 入边里只有 3 条是死标签，其余 21 条是安卓那趟的态门/协议未勾/自动边未触发，
  跳掉就丢覆盖。走序计划器每趟重排死标签是安卓侧的浪费，另开待办，不在本批。
- 离线：t1g 计划重编译 diff 只有步 55/56（个人中心 ×2）变 skip，分别由 42/43 与 44/49/51/53 覆盖；trip_2 同样只有两步。
验证：`test_compile_ab_fixes_e2e.py::test_f2_*`（skip / replace / unverified / 护栏）+ `test_replay_ab_fixes_exec.py` 执行器归因。

★A 组：安卓遍历已有的逻辑/字段照搬到鸿蒙侧（2026-09-12，trip_2 首跑 t2a 归因后用户拍板"按安卓遍历+鸿蒙映射的逻辑不该出问题"）：
- **安卓真值按趟**：`android_edge_lookup_how(..., trip)` 同趟记录优先；别趟确认记 `android_status=confirmed_other_trip`，**不救回**
  （t2a 把 trip_1 确认的 6 条边救进了登录趟，1 张假 P0；trip_1 同理少了 10 条别趟探测）；走序 tap 照发但标 `trip_state_unverified` +
  `runtime.device_state`，执行器 ABANDON 记 `edge_confirmed_only_in_other_trip`（None）。PAIR_COVER 只算同趟确认。
- **`type` 步**（安卓 B2 对应件）：编译透传 view_id/text/precondition_kind，身份 = rid 变体 → 安卓基线里该 rid 的屏上文案（空输入框的
  text 就是 hint，两端同一句）；执行器 `find_input_target` 四级定位 rid → hint → 类型；找不到先切子 tab（安卓 H 逻辑）：鸿蒙子 tab 文本没有
  `selected` 属性，按 `plan.subtab_labels[node]`（= 注解 reconcile_exclude）找并优先有可点祖先的，安卓同款 selected 判据排掉页级 tab 栏
  （tab_switch 文案）。计划文本优先于 `--input-text`。找不到记 `TYPE_TARGET_MISSING`/`input_target_missing`，不交接。
- **`renav` 步**（安卓 B1 对应件）：已在位 `RENAV_NOOP`；否则 `_renav_to`；失败 `RENAV_FAILED` 交接（`position_lost_on_renav`）。
- **计划外门**（安卓 `_dismiss_gate` 对应件）：wait/coldstart 落在已知门节点或模态上时按白名单放行一次，记 `gates(via=unplanned_gate_pass)`
  + `observed_hmos_only(kind=unexpected_gate)`（鸿蒙多了一道门 = 产品观察；t2a 首启隐私门每次冷启重弹）。
- 排除表：注解词与元素名**子串互认**（「切换到输入主题」），chrome 词仍全等；破坏性遭遇账从 manifest.per_page 跨进程聚合
  （11 次续跑分散 12 进程曾致文件不存在）；H5 URL 先从 dump 的 Web 节点取。
验证：`_tests/test_group_a_0912.py`（11 例）；全套 430。重编译 diff：trip_2 163 步（6 条别趟探测及配对 back 去掉、type 步带字段、
首页 reconcile 去 4 个子 tab 元素）；trip_1 91 步（10 条别趟探测去掉）。

★B 批：哨兵选词补"必要条件" + 计划外门放行收窄触发面（2026-09-12，replay-t2b 归因后用户拍板；两条都先在三趟 327 份真实 dump 上离线回放零回退才落地）：
- **哨兵选词 `build_sentinels`**（只改排序键与回退，候选集 / identify 打分 / 三假设判位模型一字不动）：
  ② 同为候选，**树里是该页静态文案**（`layout_facts.static_texts` ∪ `discriminators.texts`，`static_texts_by_node`）的词优先，其次原有
  稀有度升序、长度降序。反例：大纲页独有词全是安卓那次生成的大纲标题（"1.3.面临的主要挑战"），鸿蒙这次生成的正文不同 → 0 命中；
  "大纲生成/重新生成"是源码字面量，两端都在。
  ③ **回退**哨兵集整体落在另一页（文本集不同）的基线文本里 → 安卓自己就分不开这两页，到鸿蒙只会把别页认成本页（PPTFilePage 的回退词
  "保存本地/本内容由AI生成"全在大纲页上、df=1 满分 → 大纲页被认成 PPT 页 → 假 P0 + 错页交付）→ 宁空（identify None → 交参考/视觉），
  `plan.sentinel_notes[node]={fallback_voided, contained_in}` 记账。文本集相同的页（已在 alias/ambiguous 组）不算"另一页"。
  **③ 已实现但默认关闭**（`void_contained_fallback=False`，2026-09-12 用户拍板：两趟只有 PPTFilePage 一页受影响，"比较难以解决，
  先不管，以免引入新的问题"）。后果：只加②大纲页仍判 PPTFilePage（2.0 对 1.0），replay-t2b 步 18 那类假 P0 会复现——是**已知误判**，
  出单时在 judge 任务书里标明；t2c 实跑（③开启的计划）步 18 落点 CreateOutLinePage 是③有效的证据，留档备查。
  两条护栏（都是离线回放揪出的回退）：同屏页（稳定文本集相同）静态文案取**并集**（树只把静态文案挂在 Fragment 上、宿主为空 → 两页哨兵不同
  → identify 平局判 None，t1i 3 份引导页回退）；`lib_ui_words` 三张按钮词表（同意/取消/下一步/确定…）**不配当哨兵**（静态键会把"取消"顶到
  客服弹窗哨兵首位，作品页管理态一出现"取消"就被抢分，t2b 11 份回退）。
  离线账：只加②（现行默认）t1i 118 / t2a 105 / t2b 104 份 dump 判定**零变化**（大纲页仍判 PPTFilePage）；②+③ 时 t2b 只有 3 份改判
  （全是大纲页 PPTFilePage → CreateOutLinePage，即步 18 假 P0 现场），其余 324 份原样。重编译 diff 只动 `node_sentinels` / `roots.sentinel` /
  各步 `expect.sentinel`，翻译账逐字相同。
- **计划外门 `_unplanned_gate_candidate`**：t2b 首启隐私门在鸿蒙上不是 Dialog 节点、不在本趟 GATE_NODES、哨兵认不出 → 旧触发面
  （已知门节点 / `modal_type`）进不去，步 3 空等、步 5 在门上找控件必失败。新触发面：目标没到 **且** `identify()` 认不出任何计划页 **且**
  不站在登录门页（`PAGE_REF` 鸿蒙参考 `on_page_by_ref` 判）→ 才把屏交给 `choose_gate_control_hmos`（正文门语义 / 无破坏词 / 唯一白名单控件），
  每步最多一次；点前 `_shot(step{N}__unplanned_gate)`，记 `gates(via=unplanned_gate_pass, gate=unknown_screen)` +
  `observed_hmos_only(kind=unexpected_gate)`。放行后**重做同一步的到达判定，期望目标不变**：coldstart 在同一轮询循环里继续判根页；wait 用
  同一预算重新 `_auto_hit`。落别处照记 AUTO_LANDED_ELSEWHERE / position_unknown，没到的页进 coverage 缺页——放行只是多点了一下同意键，
  不改路径、不改期望（A→B→C→D 因 B 阻塞放行后直落 D：B/C 仍是缺页，不会被"发现新页"抹掉）。
  离线账：327 份 dump 只在 8 份 trip_2 首启协议门上触发；trip_1 那 4 份被认成 SplashActivity 走计划内门；登录页（"我已阅读并同意…"）
  无白名单键、会员中心/续订管理正文带"开通"、关于页"用户协议"行无键、AppTipsDialog（认得出宿主页）全部 None。
  t2c 实跑修正两处：冷启是"最多**放行**一次，判据每轮都问"（写成"最多问一次"会在启动图那轮把机会用掉）；wait 放行后重判到达的预算取
  `max(原步预算, GATE_PASS_SETTLE_S=60)`——过门后的首页初始化是冷启级转场（实测 16–20s）。
验证：`_tests/test_sentinel_gate_b_0912.py`（12 例）；t2c 与 t2b 严格 A/B：两靶子 PASS、零回退、pd=true 归零（见 CHANGELOG）。
机械 pass:①dump-diff 识别动态文案(剔哨兵/剔 reconcile)②`functional_checks`+`blackbox_behavior`(尊重 outcome)
产 reconcile 清单③node_sweep 四规则分边:**push 深下沉留 DFS 走序 / dialog 浅下沉移进 reconcile 当场测**
(dialog 的 DFS 步+配对 back 一起跳过)④哨兵**确定性排序**(按跨页稀有度,治抖动)⑤chrome/tab栏/子tab/破坏性剔除。

## 3. annotations schema(每 app 数据,不进代码——app 无关性靠这个)
```jsonc
{"app": {"bundle": "...", "ability": "..."},
 "input_edges": {"<from>--<trigger>": {"field_type":"TextInput","text_from_cli":true}},  // 需先输入的边(创作流填主题)
 "state_signatures": {"<trip>": ["ID:","VIP会员"]},        // 态检测(登录/VIP)——preflight 用
 "edge_overrides": {"<from>--<trigger>": {"locate_budget_s":70}},  // 异步门边:控件延迟渲染,轮询定位
 "reconcile_exclude": {"<node>": ["输入主题","导入文档"]},  // 页内子tab等非walk导航,reconcile不点
 "extra_blacklist": ["转人工","咨询客服"]}                   // 追加破坏性/危险词(默认词表见 plan_edge_walk)
```
★ **换 app 时代码不动,只重写这份 annotations + 换树 + 换基线**。这几项**原则上 LLM 编译期可从树推导**
(sub_tab 从 navigation_contract、异步预算从 waited_s、态签名从登录基线),现为手写——**LLM 自动生成是待做项(#9正式编译器)**。

## 3.5 切段(可选):slice_batches.py — 分段独立冷启跑
整条计划可切成"每段=冷启+一个 root-tab 子树"的 batch(分段冒烟/并行/单区域重跑)。边界从计划结构推导(root 的 tab_switch tap),零 app 常量。
```text
python3 $SCRIPTS/slice_batches.py --plan <replay_plan_hmos.json> --out-dir <目录> [--strip-login]
```
`--strip-login`:去 preflight.login_scenario(smoke 用,设备须已登录;避免撞未验证的自动登录)。产 `batch_<i>_<lead>.json`,各自 `replay_exec` 单跑。

## 3.9 ★机械为主 / LLM 为辅：退出码交接 + 断点续跑（2026-07-25 用户拍板）

**为什么改**：纯 0-LLM 回放在目标实现良好时最快（实测 125 步 43s），但目标一旦跑偏就**死磕**——
实测 25 个 tap 全撞同一个鸿蒙独有启动弹窗，1 节点采到、124 步空转，**1 个根因报成 11 张缺页单**。
安卓侧「分工轴铁律」早记同一教训（脚本编排 5 节点就断 / LLM 编排跑完 20）。
区别：鸿蒙侧**已有安卓 GT 当路径**，LLM 不必"探"，只在墙前出场 → 代价远小于安卓侧。

```
┌─ replay_exec --resume-from N   （机械，全速）
│    exit 0  完成
│    exit 30 未知模态挡路（无白名单安全关闭键）
│    exit 31 位置失配（期望页 X，实际在 Y）
│    exit 32 级联根因（连撞同一障碍）
└─→ LLM 读 out-dir/checkpoint.json（含 modal_type / buttons / streak / evidence / diagnosis）
      ① 判性质 ② 处置或判定不可过 ③ **记 llm_intervention** → 回到顶部 --resume-from N
```

### 门禁确认键：**当场判，不用词表**（用户拍板，2026-07-25）
撞到"唯一按钮是确认类"的门（首启协议/隐私/声明/权限说明…）时，
**不加白名单第三档**——词表换个 app 就崩（文案不含"协议"二字的门禁遍地都是）。
改由 **LLM 看现场判**，判据是**语义不是字面**：

| 判据 | 可点 | 不可点 |
|---|---|---|
| 后果可逆性 | 仅确认知悉/授予展示权限 | 涉金额、订阅、注销、删除、权限授予后不可撤 |
| 是否消费资源 | 否 | 扣费/耗次数/发短信/发消息给真人 |
| 安卓侧对照 | 安卓有同类门且已过 | 安卓没有 → 更要谨慎，先记差异 |

**拿不准一律不点**，记 `blocked` + checkpoint 交人工。

### 铁律：介入必留痕、必出单
> LLM 介入解决了障碍 ≠ 差异不存在。**机械回放走不下去，本身就是两端结构对不上的证据。**
> 每次介入必须写 `manifest.llm_intervention[]`（含**看到什么 / 为何判可点 / 做了什么 / 产生什么 finding**），
> `build_judge_input` 会把它们收进 `llm_interventions[]` 并标 `must_ticket`，**judge 不得只当"恢复成功"翻篇**。
> 不立这条，等于拿 LLM 的善意帮忙把迁移缺陷洗白——与覆盖完整性铁律（SKILL.md §1.1 第 4 条）直接冲突。

## 4. 执行:跑 replay_exec.py（机械段；撞墙按 §3.9 交接）
```text
python3 $SCRIPTS/replay_exec.py \
    --plan <replay_plan_hmos.json> --serial <hdc目标> \
    --bundle <bundle> --ability <ability> --out-dir <输出目录> [--input-text "测试主题"]
```
产物:`capture_manifest.json`(role=capture 契约:pages_status + per_page.{screenshot,dump,behavior_observations,
observation_notes} + **functional_coverage** + **reconcile_unsettled**)+ shots/ + dumps/ + run.jsonl。

### 4.1 ★落位 + 闸(2026-07-25 新增,**不做这两步不许进判定**)
`replay/<run>/` 是**工作区不是交付位**(output-layout 铁律)。跑完必须:
```text
python3 $SCRIPTS/replay_place_artifacts.py --capture-dir <out> --round N --trip <trip> \
    --project-root <根> --android-baseline-dir spec/visual-verify/screenshots/android/<trip>
python3 $SCRIPTS/assert_replay_artifacts.py <根> N <trip> <out>      # 红了=漏测,不许当通过
```
闸的四条:①canonical 交付集 ≡ 安卓 baseline png 全集 ②每张图配对 `.hmos.json` ③sbs 齐套
④**功能点行为覆盖=1.0**(feat 单的素材供给率;页覆盖 100% 也可能行为覆盖 0%)。

### 4.1.5 ★破坏性收尾趟（trip-end pass）—— 完整接线（2026-07-25 补，此前只有散文没有步骤）
正常趟对破坏性元素**只定位不点**（记 `encountered_destructive`），所以：
`<页>#via=<破坏性触发>` 这类**安卓交付过基线**的确认窗页，鸿蒙侧**唯一可采时刻 = 确认窗弹出那一刻**。
它们不是豁免，是**必须跑收尾趟**（`coverage_pending_trip_end` 里逐页列名，闸 cond 1b 卡）。

```text
# ① 读 handler 产本轮 hprof（LLM 读 ArkTS 源码定性；只对正常趟**真遭遇过**的组件读，读码集塌到个位数）
#    输入 = <正常趟out>/encountered_destructive.json，产物 schema 见 phase4-replay-hmos-destructive-profile.md
# ② 裁最小走序（纯机械：只留"真渲染过 + hprof 判可安全验"的支路，无关支路整棵剪掉）
python3 $SCRIPTS/trip_end_slice.py --plan <replay_plan.json> \
    --encountered <正常趟out>/encountered_destructive.json --hprof <hprof.json> \
    --out <trip_end_plan.json>
# ③ 跑收尾趟——★必须换 out 目录（同目录跑会截断正常趟的 run.jsonl 与 manifest）
python3 $SCRIPTS/replay_exec.py --plan <trip_end_plan.json> --trip-end-pass \
    --hmos-profile <hprof.json> --out-dir <收尾out> --serial … --bundle … --ability …
# ④ 合并两趟——★必须给 --plan（用**完整**计划，不是裁过的），否则覆盖账不重算
python3 $SCRIPTS/merge_capture_dirs.py --out <merged> --plan <replay_plan.json> \
    <正常趟out> <收尾out>
# ⑤ 对 merged 目录落位 + 过闸（**不是**对任一单趟目录）
python3 $SCRIPTS/replay_place_artifacts.py --capture-dir <merged> --round N --trip <trip> \
    --project-root <根> --android-baseline-dir spec/visual-verify/screenshots/android/<trip>
python3 $SCRIPTS/assert_replay_artifacts.py <根> N <trip> <merged> <replay_plan.json>
```
**为什么必须这样串**（2026-07-25 审核实测的三方打架）：
- 对**收尾趟目录**单独过闸 → cond 1/4/5 全红（页太少 / 非破坏性元素全 `continue` 零观察 / `_full` 恒 false）；
- 对**正常趟目录**单独过闸 → cond 1b 永远红（它的 manifest 不会因为收尾趟跑过而更新）；
- 合并但**不给 `--plan`** → 字段来自"先到先得"的某个目录，两趟观察合不到一本账上 → **闸假红 + 假绿并存**。
⇒ 三本覆盖账（页 / 功能点 / reconcile 欠账）统一由 [`lib_coverage.py`](../scripts/lib_coverage.py) 算，
**是对 (计划, manifest) 的纯函数**，所以合并后能原样重算。执行器与合并侧共用同一实现（禁重实现）。

**诚实失败出口**：收尾趟跑过、且 hprof 如实判"鸿蒙没有确认弹窗"→ 执行器**正确地拒绝点** →
该页在鸿蒙侧根本不存在可采时刻。此时进 `justified_uncapturable`，闸不再计欠账
（否则就是"去跑你已经跑过的那趟"式假红——**假红比空过更危险，它教人绕闸**），
但 `unverified_destructive` 强制报缺桩仍在，judge 必出单。

### 4.2 每张截图必配 dump —— 唯一落盘口 `_shot()`
执行器**禁止直接调 `drv.screencap()`**,一律走 `_shot(name, txt)`(图 `X.jpeg` ↔ dump `X.hmos.json` 同名配对)。
实测教训:11 个截图点只有 `capture()` 一处写 dump → 60 张图对 20 份 dump,而裸奔的恰是两条承重线
(`__el*` = reconcile 逐元素现场 / `__weak` = 弱到达现场)→ judge 拿到 15 条 not_found + 5 条 noop
**一份现场 dump 都没有** → 三分归因无法执行 → 20 条疑点出单接近 0。

## 5. 血泪教训清单(去别处踩之前先读)
**A 通用原则(任何 app 适用)**:
- ★§0 那条:消费树读全字段,尊重 outcome/status 已定性标记,别运行时重造(同构去重/动态识别答案都在树里)。
- 每次 tap 前重新 dump,绝不缓存世界观(被测物"坏是常态",屏会自己变;缓存=拿过期世界观 mis-tap)。
- 到达门控:验证到达目标才截图入账,未到达绝不按目的地命名(否则截图账本说谎)。
- reconcile 对齐 node_sweep 四规则:walk(push)留走序 / ground+dialog 当场 tap→观察→BACK / destructive 不点 /
  同构 N≥3 抽验1;每元素保险丝(连续2个回不来中止本页)。
- ★**reconcile 判位靠页身份,不靠计划步序**(2026-07-25 实测):绑死步序 = 错过就永不重试。
  MemberCenter 的 reconcile 排在计划 idx46(从 AccountInfoActivity 过去),那条边 WRONG_LANDING,
  实际 step62 才从 MineFragment 到了页上——**站在页上却因为"那一步早翻篇了"16 个功能点一个没测**。
  改法:`_PEND` 欠账表 + 每次到页 `_arm_reconcile()` 就地插队;站在**别的已知页**上时
  发 `RECONCILE_DEFERRED` 但**不消费欠账**(绝不在错页上采,会产整片假 not_found)。
- ★**回位失败先重导航,连败 2 次才中止**(2026-07-25 实测):旧实现 `if not restored: break`
  一次失败即丢整页剩余元素,且让下方 `consec_fail>=2` 成为**永远执行不到的死代码**。
  实测 RecommendFragment 元素#7 一次失败吃掉剩余 8 个;全局 82 个计划元素只观察到 36 个(43%)。
  重导航策略全部取自计划(入边 tap / 受 ROOTS 守卫的 BACK),零 app 常量。
- ★**中途中止 ≠ 结账**:只有全部元素过完才 `RECONCILE`,否则 `RECONCILE_PARTIAL` 且**留在欠账表**,
  下次站上这页按 `(trigger_text, rid)` 去重续采。旧实现采 1 个也算翻篇。
- ★**未定位现场必须留证**:`not_found` 是 P0(控件不在 dump=`control_missing_in_hmos`)与
  自证工具 bug(控件在 dump=`locator_failed`)的**分水岭**,恰恰最需要证据。三条 not_found 出口
  原先零截图零 dump → judge 只能弃权。现在一律留 `__notfound` 图+dump,并机械落
  `label_in_page_texts` / `enumerated_screens` / `blame_hint` 供三分。
- ★**危险是方法约束不是覆盖豁免**(SKILL §1.1 第4条在回放侧的落法):首启单行道页原先整页
  `elements=[]`,把「进度条/轮播/加载进度/权限说明」这种**根本不用点**的功能点一起丢了
  (安卓有 7 条 android_trusted 真值,鸿蒙一条没验)。改按 `needs_tap()` 三分——判据取
  **安卓基线 dump 的 clickable 属性**(零词表,换 app 照用):可点的跳过并记原因,
  不可点的走 `observe_only`**只验渲染不点击**。错向安全(误判只会少点一次,绝不会点穿向导)。
- 安全双保险:safety!=normal 整边跳 + 触发词硬黑名单(防计划标注洞)。
- 弃权≠缺陷:ABANDON 只说"没够着",判定层禁自动升级成 feat 单(定位数据坏时它对错什么都没说)。

**B 鸿蒙特有(因单 ability/无 id/键盘/异步)**:
- **pagePath 退化**(这个 app 整个跑在单 SplashPage)→ 判位不能靠 pagePath,靠**内容哨兵 + 页签名双引擎**
  (identify 加权哨兵管有名页 / page_signature_from_dump 注册表管无名页+精确同一性+环检测)。
- **app 组件无 rid**(ArkTS 不设 .id())→ 定位/同构判据不能用 rid,用文本(five_match)/结构(class+坐标带)。
- 哨兵**确定性排序**必须做(集合切片非确定→哨兵抖动→"时好时坏"的元凶)。
- input 后**先判键盘真开着再收**(误发 back=假BACK退页);中文可直填(免安卓 ASCII 绕行)。
- 每轮开跑干净重启(别把上轮打断残留当 app 缺陷);冷启时长是变量→轮询根哨兵禁固定 sleep。
- 异步门边(生成完才渲染的控件)→ annotations 给 locate_budget 轮询定位。
- **屏外元素两级滚动**(2026-07-22,师承 blackbox enumerate/hmos_capture find-then-scroll):walk 边定位 miss→scroll_find 上滑≤3屏(到底=两屏签名同,miss 滚回复原);reconcile 进页**一次滚动全量枚举**(合并 page_texts+clicks,回顶)→枚举都没有=真 not_found(searched:full_page),有=滚到出现实时 tap;滚动消费后回位判据放宽(滚动位或页顶均算)+滚回顶。swipe 走 DeviceAdapter 中线坐标(避 4pt 边缘系统手势)。
- **dialog 边命名按因果不按"屏上有模态"**(2026-07-26 实测事故):原判据 `mt or changed` 两处松口——
  `changed` 单独成立就给一页命名(屏变了但根本没弹窗);`mt` 只证明**有**模态、不证明是**这次 tap 弹的**。
  实测鸿蒙独有的内容声明门(全屏 `Dialog [0,132][1272,2756]`)在 tap 前就盖着,点哪都落在它身上
  (同页两个不同控件算出同一个 tap 中心=点的本就是同一块遮罩),点完模态还在 → 声明门被存成
  `AppPermissionIntroDialog.jpeg` 并记 `captured`,页覆盖虚报 16/17。**同一条观察里 `outcome`
  已经写着 `overlay_or_state`(点到的是遮罩不是控件)——反证就在手边,判据没读它。**
  ⇒ 判据改成:必须有模态 **且**「tap 前无同类模态 或 点后签名变了」。
  **不要求哨兵命中**——变体页(`AppTipsDialog#via=*`)存在的意义就是两端文案不同,按文字验身份会误杀。
  拒采时写 `dialog_capture_refused` + `__dialog_capture_refused` 存证,`capture()` 返回值必须接。
- **顺路补采会抢先占位,把计划到达挡在门外**(2026-07-26 实测,同一个病的第三个变种):
  顺路补采是"站上了就采"的便宜货,但 `capture()` 见该页已 `captured` 就跳过 →
  **后来那次计划到达的干净图再也覆盖不进去**。实测 v9 的 HomeFragment:step10 在鸿蒙内容
  声明门(全屏 `Dialog`)盖着时被顺路采走,step15 `ARRIVED_strong` 时被跳过,于是
  **页级图永远是隔着遮罩那张,而逐元素证据(到达后采的)却是干净的** —— 同一页两套证据不同源,
  只看其中一套会得出相反结论。两处一起修才够:
  ① 屏上有**计划没声明**的模态时,顺路补采不许命名该页(记 `opportunistic_skipped`);
  ② `pages_status` 记 `provenance`(arrival/opportunistic),**计划到达有权改写顺路补采**。
- **`overlay_or_state` 是"没验到"不是"验过了"**(2026-07-26):tap 被遮罩吃掉,点到的不是那个控件。
  它此前不在 `lib_coverage.UNVERIFIED_OUTCOMES` 里 → 执行器如实记了遮挡、覆盖账却当有效观察,
  实测把 55/72 顶成了 59/72。凡"点了但没点着"的 outcome 一律留在分母里当欠账。

## 5.5 元素对齐与验证边界（规则）
- 鸿蒙侧 reconcile 用 `elem_signature`（标准化文本+rid+content_desc，**不含 type/bounds**）把 fact-tree 的 trigger spec 与 dump 抽出的元素**同签名对齐**，five_match 文本匹配只作兜底；`normalize_text_for_sig` 把动态文案归一。
- 边到达验证 = 哨兵命中 **且** page_signature 也变化才算到达（防"哨兵词点前屏上本就有"的假命中）；单 ability / degenerate pagePath 的 app **必需**落点身份识别（identify+签名注册表）+ 环检测，**不可退化成单 verify_text 判位**。
- **鸿蒙侧只验、不发现**：reconcile 严格只验树声明的 `functional_checks`，树没说的不测（树没说 = 安卓没遍历过 = 无 oracle，鸿蒙扫到也判不了）。黑盒扫漏是**安卓侧建 ground truth**的机制，不在鸿蒙侧平移。

## 5.9 ★双侧审计结论 + 开跑 checklist(2026-07-23,两审计agent实测坐实)
**已修(本轮直接修掉,离线验过)**:①BLOCKER webview边压下沉栈(漏则H5卡死后续全废)②reconcile回位改NON_DESCENDING
(只page_change/overlay才BACK,toast/noop不BACK→防tab根BACK退app)③破坏性判据编译器+执行器都改**复用
blackbox_explore.DESTRUCTIVE_RE**(通用全词表,含退出登录/清缓存/退款/支付,全plan reconcile已验零危险词)
④input_field改rect(dict)优先(真机dump用rect,原只认attributes.bounds→创作主链断)⑤coldstart加preflight态校验
(state_signatures不命中→告警"未登录/态没就绪")⑥waited_s从run-2台账反哺(FileListPage 2.5→8.5s,异步边预算不误判)。

**开跑前必备 checklist(不备必返工)**:
1. **trip 首 batch 前由 dispatch 层建态一次**(dispatch 层建态,执行器零建态职责):`python3 run_scenario_with_verify.py login_harmonyos harmonyos --trip trip_2 --device-id <id> --package <bundle>`;验证步在 YAML 自身(切「我的」验 ID:)。exit 10→派 scenario-builder 自修/20→凭据找用户。后续 batch 不重跑。⚠️现 YAML 的 package/首启链是 630_tool 的,换靶 baseline_630 需先适配(从没在鸿蒙跑通,progress=0)。
2. **两轮基线dump齐**(--baseline-dir + --baseline-dir2);缺一轮→动态识别静默关→哨兵抖动。
3. 树 **waited_s 已反哺**(已做);异步门边在 annotations.edge_overrides 给 locate_budget_s。
4. annotations 补全:reconcile_exclude(带子tab的页)、input_edges(需输入的边)、state_signatures。
5. 设备**首启同意/隐私弹窗手动过掉**(执行器无排水drain_popups——HIGH-5未实装,换app/清数据必炸)。
6. 开跑后立即抽验:run.jsonl webview步后有无连片ABANDON(=webview栈没修干净);MineFragment reconcile后设备还在不在前台。

**剩余待修(按阻塞度;非本轮修)**:🟠webview landed_url未反哺→H5 URL对比缺oracle(采集侧补loadUrl);🟠收尾/resume/
阻塞传播(§5/§6/§8)未实装→出错带病硬跑不回补;🟡弱到达仍占正牌to命名(judge拿贴错标签基线);🟡is_walk模糊
子串可能漏测功能点(应改rid精确);🟡blackbox不按trip过滤(混入登出态元素噪声);🟢elem_signature因app无rid
基本空转(不有害,宣称的复用收益不存在,靠five_match兜底)。

## 5.95 冒烟实测发现（2026-07-22）
已归档至 [`rationale-log.md`](rationale-log.md) §replay 冒烟实测 2026-07-22（T1 执行器建态职责已修；T2–T5 的结论已分别并入 §0/§5 教训清单、编译器 trigger_label_unknown 处理与 edge_overrides.locate_budget_s 现行规则）。

## 5.97 precond(前置数据态)哲学:顺序对齐,绝不鸿蒙侧自建(2026-07-24,用户问"安卓侧有做接线吗"后定)
安卓侧**没有**功能点级自动建态机制——数据态靠**遍历顺序副产品**(创作流先生成PPT→作品区自然有数据)+grounding诚实记账(precondition字段,具体到源码行号)。鸿蒙侧同构:
- **态对齐=按 walk 顺序跑**(batch_4 的"列表非空"依赖 batch_1 副产品;单跑后区段撞 precond_unmet→先按序跑上游段);
- 编译器透传 `precond/precondition` → 执行器全页不见时定性 **precond_unmet**(非缺陷疑点)→ manifest.need_scenarios 结构化报缺(scenario-builder 可消费);
- **绝不自动建安卓没建过的态**(无 oracle 测了也判不了);涉支付/订阅/注销的态=可弃账号隔离 trip,红线。

## 6. 复用点名(禁重实现,审核铁律)
DeviceAdapter(设备层+page_signature) / extract_clickables_hmos / five_match(五级匹配,降级命中=text_mismatch P1) /
evidence_pack —— 均 import 现行实现。判定段复用 role=judge。建态委托 run_scenario_with_verify.py。

关联:phase4-replay-compile.md(编译设计) / phase4-replay-executor.md(执行设计) / node_sweep.py(四规则+同构去重源) /
memory [[vv-hmos-replay-landing]] [[design-precedent-protocol]]
