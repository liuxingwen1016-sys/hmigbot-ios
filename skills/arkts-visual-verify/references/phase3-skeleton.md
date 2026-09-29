# Phase 3 — 准备 spec/fix/round-N/ 目录骨架 + Android 截图缓存

> 从 SKILL.md §4 Phase 3 抽出。Phase 3 进入时 Read。

在进入逐页截图前，做两件事。

---

## (a) 准备 fix-markdown 目录

```
1. 读 spec/fix/_state.yaml.current_round → 取 N（不存在视为 N=0，并初始化 _state.yaml schema_version=2）
2. 建目录 spec/fix/round-N/ui/_systemic（bash `mkdir -p` / PowerShell `New-Item -ItemType Directory -Force` / python `os.makedirs(...,exist_ok=True)`）
3. 若 spec/fix/round-(N-1)/ui/ 存在 → 缓存所有文件的 frontmatter（id, disposition, disposition_reason, disposition_set_at_round），后续 Step 4.4 写入新 markdown 时按 schema §五 carry forward
4. 若 spec/fix/round-N/ui/ 已有残留（异常退出导致）→ 全部清空（防止遗留旧轮次的 markdown 污染本轮）
5. **物理 carry-forward 未收口 finding**（防"漏检即蒸发"）—— 在第 4 步清空后立即跑：

   ```bash
   python3 "$SKILL/scripts/carry_forward.py" --fix-dir spec/fix --round "$N"
   ```

   **不变量：文件名 = frontmatter `id`，跨轮恒定。** 结转信息落 frontmatter
   （`carried_from_round` / `carried_rounds`），**不落文件名**。

   **规则**（脚本自持，勿再手写 bash）：
   - 遍历上轮**实际存在**的子目录（至少 `ui/` `feat/` `ui/_systemic/`），跳过 `_` 开头文件
   - `disposition ∈ {fixed, skipped, manual_review, problematic}` → 不结转
   - 其余（`null` / `partial` / `pending_*`）→ **原样带走**：三字段、`blocked_by`、§6 正文全保留
   - legacy 输入：`CARRYOVER_<id>_from_rK.md` / 带 `carried_from_id` 的单 → 落成正名文件 `<id>.md`；
     `RESOLVED_<id>.md` 视为已收口，不结转（前缀只参与 id 归一）
   - 幂等：重复跑产出逐字相同

   **设计意图**：
   - **finding 不蒸发**：未收口的全部带到本轮，且**二次结转不会被自己的前缀过滤掉**
   - **名字不承载状态**：`run_fix_self_check.py` 规则 1（文件名=id）零 FAIL；
     `BLOCKED_P<pid>.md` 字面名不变，`lib_ledger.blocked_placeholders` /
     `build_batch_manifest` / `page_status --done` 继续认得占位
   - **不重置 disposition**：旧片段一律 sed 成 `null`，把 `pending_*`（BLOCKED 占位/待上游/
     待前置）变成可修 open 单并虚增 `round_budget.count_open`；`partial` 的"下轮重测"语义也靠
     不重置保住
   - **不在 Phase 3 判定 stubborn**：顽固 finding 搬移逻辑统一由 Phase 7 持有
     （详 phase7-stubborn-loop.md），避免双入口
   - **结转单不会被 judge 二次渲染**：结转后本轮目录里已存在 `<id>.md`（带 `carried_rounds`），
     Phase 4 judge 若对同 id 再调 `render_finding_skeleton.py`，脚本**拒绝新建并 exit 21**
     （stderr 提示"结转单已存在，原地更新"），逼 judge 走"原地写判定"而不是落 `<id>-2.md`。
     本轮**无** `carried_*` 字段的同 id 才是真冲突，仍走 `-2`/`-3`。
```

---

## (b) Android baseline 完整性速览

```
1. 统计 screenshots/android/{trip_id}/ 各 trip 的 baseline png 数（正式 gate 在
   build_batches.py 入口的 check_android_screenshot.py，这里只输出速览不拦截）：
   "Android baseline: trip_1={N} 张, trip_2={M} 张"
```

> **注意**：本 skill **不再做"跑 grep 批量预修复"**——批量修复是 visual-fixer 的职责。预修复机会被 visual-fixer 的 systemic 聚合（同根因 ≥3 页 → SYSTEMIC_*.md）覆盖，本 skill 只负责把症状写出来，不主动 grep 改代码。
