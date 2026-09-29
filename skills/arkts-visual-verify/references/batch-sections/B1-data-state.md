<!-- batch-section:B1-data-state — B.1 注入数据态自愈梯（仅批内页带 state_required/vip_required 前置时注入） -->
<!-- 本文件由 fill_batch_prompt.py 按批内页种类注入 sub-agent-batch-prompt.md 的 <!-- SECTION:B1-data-state --> 标记处；正文与 2026-09-07 拆分前逐字一致，勿在此处改判定规则以外的东西 -->

  # B.1 注入数据态（如有 precondition）——自愈梯（2026-07-10 ③，替代旧"造不出就 SKIPPED"）
  FOR pc IN page.preconditions:
      IF pc.kind == "state_required" AND NOT _state_satisfied(pc):
          # 态蒸发 ≠ 配方坏——主会话 checkpoint（dispatch 0.b）造过态，配方是活的，先重放再认输：
          # 1) 复验：重跑 check 配方（廉价非消耗；配方名读 progress.json.states_provisioned，
          #    checkpoint 已记；查无此 state → 不自愈，直接 3)——学习归主会话派 builder）
          # 2) check 红 → 就地重放 create 配方（包装脚本，device=harmonyos）→ 重回本页
          #    → _state_satisfied 复验过 → 继续 B.2+。★限额：同 state 同 batch 最多 1 次
          #    （create 多为消耗型）。★自愈必入账：manifest 本页记 state_repaired: {state, elapsed}
          # 3) create 重放失败 / 二次蒸发 / 无配方 →
          #    write SKIPPED_DATA_REQUIRED_P{page_id}.md（按 fix-file-schema 4.1.5：
          #    v4_data_state.reason=creation_flow_failed|db_empty，attempted_creation=true +
          #    attempted_creation_error=自愈梯已试记录，disposition=pending_data_seed）
          #    CONTINUE OUTER LOOP（主会话按路由派 scenario-builder 播种数据——配方级问题）
      IF pc.kind == "vip_required" AND NOT user_is_vip():
          # 不该到这里：trip_2 假设是 vip 账号
          log error, CONTINUE
      # login_required / nav_redirect_target / credits_required_amount 等
      # 由 scenario_chain 已经满足
