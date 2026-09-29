# arkts-visual-verify CHANGELOG

> 变更账本：每次改版记一节。**同步到 codex / 回滚 / 换版本**都以本文件为准，不靠记忆。
> 本文件不在任何必读清单里，运行时不进 agent 上下文。

---

## 2026-09-16 环境中立：skill 根 / agent 注册 / 资产模板定位收进 sibling_exec 一处（DiceRoller codex 实跑 C1 + claude 实跑 D8）

> **C1**：codex 线 vv 前置探针按 `~/.claude/agents/<a>.md` 找 visual-fixer / reviewer，codex 线 agent 在 `.codex/agents/<a>.toml`
> → 恒「未注册」→ UNIT 级 ABORT，整条 codex 线挡死（installer 明明铺了 31 个 toml）。根因是「平台事实」写死在代码里：
> `os.path.join(home, ".claude", "agents")` + `f"{agent}.md"`。codex-adapter 只改文档/提示词里的字面路径（`.claude/agents/` → `.codex/agents/`），
> 改不了这种拼法——codex 副本嘴上说「查了 ~/.codex/agents/」，手上查的仍是 `~/.claude/agents/`。
> **D8**：next_walk.fill_judge_prompt 用 `HERE/../references/phase2-judge-template.md`，打包态 HERE 在 `_entry.dist/` 里 → FileNotFoundError，
> 驱动断在判读派发（主会话手拼 prompt 绕过）。同族：SKILLS_ROOT = `__file__` 上溯两级（打包态落到 bin/）、Claude 线用户级 skills 目录写死、
> `CLAUDE_PROJECT_DIR` 下的 Claude 线工程级 skills 目录写死、hmos-fix-build-errors 只认 Claude 线的下划线旧名。

- 原则：**一份源码在四种环境都能跑**（Claude 用户级 / 插件缓存 / Codex `.agents`+`.codex` / DevEco 源码分发，各乘源码态与打包态），
  平台差异在源侧代码里处理，adapter 只改人看的文字；判「文件在不在」而不判「我在哪个环境」（判环境容易错，同级有 .codex 就当 codex 的坑）。
- `sibling_exec` 新增环境定位段（一处实现）：`SKILL_LAYOUTS` / `AGENT_LAYOUTS`、`scripts_dir()`（ARKTS_SKILL_DIR **自标记**：只在它指向本 skill 时才认，
  跨 skill 继承不串台；冻结态从 `<scripts>/bin/<平台>/_entry.dist` 上溯；源码态本目录）、`skill_dir()`、`skills_root()`、`skills_root_candidates()`、
  `project_skills_dirs()`、`find_in_skills()`、`agent_search_dirs()`、`agent_registered()`（`.md` 与 `.toml` 都认）。
- 11 个业务脚本改调它（连 sibling_exec 共 12 个文件；scenario-runner 那份 sibling_exec 未动）：check_dimension_prereqs（skill 根候选补 `.agents/skills`、agent 用 agent_registered、
  hmos fix 两种目录名 + 工程级两种布局；显式 --skills-root 的输出与既往一字不差，golden 047–052 照锁）、check_prereq_freshness（detect_arch 用 find_in_skills）、
  run_scenario_with_verify（SKILLS_ROOT / _resolve_dep / 已查路径）、check_android_screenshot、dispatch_phase2_batches、run_phase2_android_survey（SKILLS_ROOT 只用于提示路径）、
  verify_outcome（_SKILLS_ROOT，env 缺席时不再算成 `<scripts>/bin`——上轮验收 note）、next_walk（D8：模板按 skill_dir 找）、fill_chunk_prompt / fill_batch_prompt / materialize（scripts_dir）。
- 锁：`_tests/test_env_neutral_0916.py`（15 例）——定位函数三态（源码 / 冻结布局 / env 指本 skill·指别人·不存在）、skills 根候选与 find、agent_registered 六种布局、
  探针端到端（codex 形状 `.agents/skills`+`.codex/agents/*.toml` ✅、claude 形状 ✅、显式模式不打「另查过」）、**静态闸**：业务脚本不得再拼 `.claude/.codex/.agents`
  路径或 `<agent>.md`（逐行豁免须注 `env-literal-ok`），自带变异自检。test_plugin_form 夹具随探针一并拷 sibling_exec。
- 证据：影子根 Nuitka 真二进制：codex 形状工程（显式根 / 无 env 自动发现）两 agent ✅、claude 形状 ✅；vv 套件 683 passed；打包器 verify PASS=110。
- Opus 验收 PASS_WITH_NOTES：M1「冻结上溯只认装配后布局，打包器 verify 用的装配前 scripts/_entry.dist 会把 ARKTS_SKILL_DIR 判丢」→ 改成
  「最近一级名为 scripts 的祖先」（同 scenario_run._own_scripts_dir，装配前后都对，加了用例）；M2 codex 副本 CHANGELOG 措辞含 validate.sh 拦截词 → 已清；
  minor：find_in_skills 按文件判、fill_*_prompt 的 import 前补 sys.path、探针用例清 CLAUDE_PROJECT_DIR。静态闸已知漏网：`expanduser("~/.claude/agents")`、`agent + ".md"`、常量转手（记录，未扩）。
- vv 直接依赖的 skill 同批修（用户点名）：**android-fact-tree** dispatch.py 的 `_resolve_skill` 原只认 Claude 线用户级/工程级目录，改成两种布局都查（内联最小实现：
  该文件按打包器 EXCLUDE_STEMS 以源码发运、永不冻结，而打包器会删掉 lib 源，所以它**不能** import sibling_exec；其 `[sys.executable, 兄弟.py]` 在源码发运形态是对的，加说明与 `packaging-contract-ok` 标记）；
  codex 副本停在 #98 之前（gate 处直接 `[sys.executable, prereq]`、无 `_vv_cmd`），补齐；全缺时的回落提示路径由用户级改为同级根（都只是提示）；
  新增 android-fact-tree/scripts/_tests/test_resolve_skill_0916.py（6 布局矩阵、候选顺序与 sibling_exec 对齐、豁免标记真承重、_vv_cmd 回落）；**arkts-scenario-runner** sibling_exec 副本同步为 vv 版、ad_dismiss 守卫改 sibling_available；codex 侧 scenario_run.py 停在 #103 之前
  （无 sibling_exec、旧 SKILL_DIR 算法），整文件同步为源侧。其余 5 个依赖 skill（app-relationship-tree / a2h-functional-merge / compose-fact-tree / toolkit-fact-indexer / a2h-spec）过闸零命中。
  新增两例：sibling_exec 副本零漂移闸（所有 `*/scripts/sibling_exec.py` 必须与 vv 这份逐字节相同）、依赖 skill 过同一套打包/平台契约。
- 未动（另开单）：其它非依赖 skill 的同款命中（全仓 24 个 skill 过闸：arkts-router-verify/nav_common.py:61、arkts-structural-closure/structural_loop.py:422/432）；
  脚本 stdout 里的 `Skill(x)` 措辞（codex 是 `$x`，golden 锁死不动）；build_spec_oracle 只认 v1 feature-index（D9）。

## 2026-09-15 兄弟脚本守卫改用 `sibling_available`：8 处 `os.path.isfile / .exists(<兄弟>.py)` 打包态恒 False（D6 验收顺带发现；叠在 #106/#107 上）

> 打包态 `__file__` 在 `_entry.dist/` 里，那里一个 `.py` 都没有（整个 skill 编进同一个 `_entry.bin`）。调用方用
> `os.path.isfile(SCRIPTS/"x.py")` 做「兄弟在不在」的前置守卫 → 恒 False → 正确的 `sibling_cmd` 被挡在门外，兄弟**静默不被调用**：
> feat 单 §2 永远 UNRESOLVED（render_finding_skeleton→inject_spec_oracle）、截鸿蒙前的 baseline 安全闸消失（capture_or_reuse→
> check_android_screenshot）、Phase 2 出口验收与黑盒证据检查/反哺跳过（dispatch_phase2_batches ×3）、事务复验一律 degraded
> （reverify_transaction→verify_outcome）、黑盒基线缩图跳过（materialize_blackbox_to_factree→resize_screenshot）、跨 skill 的事务
> 场景执行在 ARKTS_SKILL_DIR 缺席时报 scenario_run_missing（verify_outcome→arkts-scenario-runner/scenario_run，静态闸揪出的第 8 处）。源码态跑不出来。

- 改：`sibling_exec.sibling_available(script)`——与 `sibling_cmd` 同一套冻结态判据（判据唯一来源）：源码态 = `isfile`（逐字节同行为）；
  冻结态同 skill = 本 `_entry` 在 + `importlib.util.find_spec(stem)` 能找到（漏编/拼错的 stem 不算可调）；跨 skill = 对方编译产物在或对方源码在。
  8 处守卫机械换用它（materialize 走本地 `_resize_available` 借同一判据，拿不到 sibling_exec 再回落 isfile）；提示文案不再说
  「不存在于 …/_entry.dist/…」。不动 SCRIPTS 取法，不依赖 ARKTS_SKILL_DIR，不改任何闸的语义；安全闸「不可用即跳过」的既有行为保持不变。
- 锁：`_tests/test_sibling_available_0915.py`——① 三种态判据；② 守卫守的兄弟冻结态一律可调且满足调度壳 main() 契约；
  ③ 端到端：render_finding_skeleton 出 feat 单，源码态与调度壳态 §2 都拿到解析后的验收行、无 UNRESOLVED；
  ④ **打包契约静态闸**（换项目通用）：不许 isfile/exists 守 `.py`、不许 `[sys.executable, …]` spawn、借打包器 `classify_scripts_dir` 不许 implicit/broken。
  静态闸的豁免只认「except 兜底分支且同函数先试过 sibling_available」，名字按「模块级 ∪ 所在函数」解析，`Path(x).is_file()` /
  `PY = sys.executable` 别名都绕不过，自带变异自检（test_contract_lint_selfcheck）；对改前文件重扫 8/8 全中。
  以后新脚本只要过这道 pytest 就天然兼容打包态，不用装成插件实跑才发现。
- 证据：影子根 Nuitka 重编真 `_entry.bin`：feat 单 §2 拿到验收行；`capture_or_reuse harmony …` 在空目录 rc=9「截 HMOS 被
  check_android_screenshot 拦住」（改前守卫恒 False、闸不会触发——**打包部署的可见行为变化，是预期的恢复**）；验收员用 symlink 把跨 skill
  目标掰进 `_entry.dist` 证明 `find_spec` 在冻结态真在把关（未编进的 stem 判 False）。打包器全量 verify PASS=110 FAIL=0；D6 六脚本 bin 夹具仍过。
  Opus 验收 PASS_WITH_NOTES（blocker 0；major 1 在测试侧=豁免过宽，已收窄；minor 5 已处理）。
- 未动（验收 note，待拍板）：`references/windows-setup.md:39`「脚本之间互相调用一律用 sys.executable」与本契约相悖，会把人教回坑里；
  `verify_outcome.py:52-54` 在 ARKTS_SKILL_DIR 缺席时把 `_SKILLS_ROOT` 算成 `<scripts>/bin`（既有，另开单）。

## 2026-09-15 打包入口契约：6 个模块级脚本包进 main(argv=None)（DiceRoller_arkTs_915cc 插件实跑 D6；PR 到 version_915 / version_915_codex）

> 打包态 `_entry.bin <stem> …` 只会 `importlib.import_module(stem).main()`。这 6 个脚本逻辑写在模块级、没有 main()：
> import 时逻辑跑完（调度壳已把 sys.argv 换成 `[stem.py, *args]`，参数是对的、产物也写了），随后取 `.main` →
> `AttributeError: module 'build_judge_input' has no attribute 'main'`，退出码 1，外层按失败处理（round-1 judge 组装实锤）。
> 源码态 `python x.py` 永远复现不了；打包器 `classify_scripts_dir` 把它们归为 `implicit`（无 main、无守卫、无人 import）仍照编。

- 改：build_judge_input / build_spec_oracle / inject_spec_oracle / merge_capture_dirs / slice_batches / trip_end_slice ——
  正文整体缩进进 `def main(argv=None)`（首行 `argv = list(sys.argv) if argv is None else list(argv)`，与 walk_finalize 等 0915 CI 修的 27 个同款）；
  `ap.parse_args()` → `ap.parse_args(argv[1:])`，直读 `sys.argv[i]` → `argv[i]`；`sys.exit(0)` / `raise SystemExit(0)` → `return 0`、
  `sys.exit(1)` → `return 1`（调度壳 `sys.exit(rc if isinstance(rc, int) else 0)`，退出码语义不变）；末尾 `if __name__ == "__main__": sys.exit(main())`。
  CLI 参数、stdout、产物路径零改动，文档里的调用方式不用动。`git diff -w` 只有 67 行。
- 顺手两处：inject_spec_oracle 正文一句冗余 `import os, re, json` 删除——包进函数后它让 `os` 在整个函数域成局部名，
  前一行的 `os.environ` 直接 UnboundLocalError（golden 021–025 抓到）；build_judge_input 的 `STITCH_FAILED = []` 从 import 块
  挪进 main（每次运行态，不留模块级状态）。
- 锁：`_tests/test_entry_main_wrappers_0915.py`（14 例，零 app 常量夹具）——① 6 脚本顶层只剩 import/docstring/def main/守卫、
  main 无必填位置参数、正文无「先读后绑定」；② 源码态 vs 调度壳态（与 `_entry` 同构的最小分派壳）在同一夹具上 rc/stdout/产物逐字一致；
  ③ inject 无参 usage rc=1、trip_end 空收尾趟 rc=0 语义保留。打包器分类：vv 110 entry + 8 lib，`implicit` 归零。
  影子根（`ARKTS_REPO_ROOT` 指向只含 vv 的拷贝）Nuitka 实编 macos-arm64 `_entry.bin`，用真二进制跑同一夹具：6/6 rc=0、stdout 与源码态逐字相同、
  产物一致；`_entry.bin inject_spec_oracle`（无参）rc=1。改动前的文件过同一分派壳：5/6 复现 `AttributeError: module has no attribute 'main'` rc=1；
  build_spec_oracle 因正文以 `sys.exit(0)` 收尾，import 期就退出（rc=0、产物已写，`.main` 同样从未存在）。
  Opus 验收 PASS_WITH_NOTES（blocker 0 / major 0）：补了「损坏图 → sbs_stitch_failed」与「首步非 coldstart → rc=1」两例（16 例）。
- 未做（用户拍板只做①）：打包器把 `implicit` 视为 fatal 的静态闸；其余脚本写法统一。

## 2026-09-15 插件安装形态四件（antennapod_v630_cc 上 hmigbot 1.5.1 插件实跑归因；PR 到 version_915 / version_915_codex）

> 打包版以 Claude Code 插件（`claude plugin install hmigbot@hmigbot`）装进工程后首次实跑，卡在 Phase 2 派第一个 walk。
> 四个问题都是**安装形态**（插件缓存路径 + Nuitka 二进制）暴露的，源码态（用户级 skills 目录直跑源码）跑不出来。

### 1. 前置探针不认插件布局（`check_dimension_prereqs.py`）
- 病：skills 根只认 `SKILLS_ROOT` / 用户级 skills 目录，agent 只查用户级与工程级 agents 目录；
  插件缓存 `~/.claude/plugins/cache/<mk>/<plugin>/<ver>/{skills,agents}` 里四样齐全却报 3 ❌ + 1 ⚠️。
- 修：显式 `--skills-root` / `SKILLS_ROOT` 时语义不变（golden 047–052 逐字不动）；未显式时自动发现
  `ARKTS_SKILL_DIR` 上溯两级（launcher 注入）→ 本脚本所在目录上溯两级 → 用户级 skills 目录 → 工程两处，只收含
  `arkts-visual-verify/` 的目录（打包态 `_entry.dist` 上溯两级不是根，被过滤）；agent 加查每个根的兄弟 `agents/`
  与 `../arkts-agents/agents`；`hmos-fix-build-errors` 同样查全部根。插件形态打一行 ℹ️（插件名 + 派发名前缀）。

### 2. agent 派发名（**改在发布侧处理，本 skill 不动**）
- 实测：插件里的 agent 在 Agent 工具注册为 `<plugin>:<name>`，裸名 `visual-fixer` → "Agent type 'visual-fixer' not found"；
  Skill 工具对裸名有回退、Agent 工具没有。规范里 `agent_type="visual-fixer"` 这类字面量是按用户级安装写的。
- 决定（用户）：**不在 skill 里加运行时取名**（曾做过 `agent_name.py` + 三处文档改写，已撤回），改在发布进 hmigbot 时
  机械改写——凡 `agent_type` 后面出现在 `agents/` 目录里的名字统一加 `<plugin>:` 前缀。源侧文档保持裸名，
  用户级安装不受影响。hmigbot 自己的 a2h 系 skill 同病，同一条改写一并覆盖。
- 本 skill 保留的只有探针（第 1 条）对插件布局的识别。

### 3. 打包态 `next_walk` 在派第一个 walk 时崩 + 吐错路径（`next_walk.py` / `walk_ledger.py` / `hit_chain_probe.py` / `lib_image.py`）
- 病：给模型看的 cmd 用 `HERE=dirname(__file__)` 拼 `plan_edge_walk.py`，打包态 `__file__` 在 `bin/<平台>/_entry.dist` 里、
  那里没有 .py；`fill_walk_prompt` / `run_bind` / walk_ledger settle / hit_chain_probe `--page` 用 `[sys.executable, 兄弟.py]`
  spawn，打包态 `sys.executable` 是不可执行的 libpython → 实跑 traceback（`fill_walk_prompt:432`）。CI 没抓到：这些脚本走
  argparse，smoke 只跑 `--help`。
- 修：`SCRIPTS = ARKTS_SKILL_DIR or HERE` 给模型看的路径一律用它（含 `after_return`）；四处 spawn 改 `sibling_exec.sibling_cmd`；
  `lib_image._ensure_pil` 的 pip 兜底不再用冻结态的 `sys.executable`。新静态闸 `test_no_bare_sys_executable_spawn_left_in_scripts`
  / `test_no_here_based_py_path_emitted_to_model` 守整类。`build/script-compression/scripts/verify.py` 补两条真参数用例
  （`next_walk` 走「计划不存在」分支吐 cmd、`hit_chain_probe --page` 真 spawn）。
- **同类漏网：`arkts-scenario-runner/scripts/scenario_run.py` 的 `ad_dismiss` 动作**（跨 skill 调 vv 的 ad_dismiss.py）：路径按
  `__file__` 上溯两级、spawn 用 `[sys.executable, …]`，打包态先报「依赖缺失」、路径对了也会 Errno 13。改为 `SKILL_DIR.parent`（ARKTS_SKILL_DIR
  优先）+ `sibling_cmd`（跨 skill 分支找 vv 自己的编译产物），runner 目录补一份 `sibling_exec.py`，`_tests/test_ad_dismiss_spawn_0915.py` 3 例
  （路径与 spawn 形态 / 依赖缺失报缺不崩 / 静态闸）。只影响冷启有广告或付费墙、场景里用 ad_dismiss 的项目；codex 线的 runner 没有该动作，不涉及。
  `android-fact-tree/scripts/dispatch.py` 的 `[sys.executable, …]` 经实测**不是问题**：它在打包版里以源码分发，由系统解释器跑、spawn 的是 launcher。
- **`ARKTS_SKILL_DIR` 会被子进程继承**（launcher 用 setdefault 不覆盖；`sibling_cmd` 跨 skill 分支直调对方二进制不经 launcher）：
  vv 冻结态调 scenario_run 时，它顶部按环境变量算的 SKILL_DIR 会变成 vv 的 skill 根，`assets/default_test_image.jpg`、`src_rel` 定位错
  （上传图片类场景才触发）。改 scenario_run：只在 `ARKTS_SKILL_DIR` 指向的目录里有本脚本同名文件时才认，否则冻结态按 `_entry.dist` 上溯两级、
  源码态用 `__file__`；2 例测试。其它靠该变量自我定位的 skill（a2h-spec / app-relationship-tree / arkts-router-verify / arkts-structural-closure /
  vv 自身）同一类风险，但只在"冻结态 + 被别的 skill 二进制直调"时触发，目前只有 vv→scenario_run 这一条路；整类修法（launcher 改覆盖 +
  sibling_cmd 跨 skill 改走对方 launcher）记为打包线待办。

### 4. 树覆盖闸被模型自行放宽（`app-relationship-tree/scripts/tree_coverage_report.py`，见该 skill CHANGELOG）
- 病：两次 FAIL 后模型没升级用户，改树里 walkability、写 `_phase_markers.coverage_gate_override`、以 `--min-e1 0.84 --min-e3 0.95`
  过闸（Step 1.0.7 铁律 4/5 双违）。根子上 E1 分母把抽象基类 / 外部拉起 / 死代码算进去（11 条缺口全是），E3=100% 太硬。
- 修（用户拍板）：E1/E3 分母剔除非 walkable；E3 默认 100% → 92%；任何低于默认的阈值须用户在 `spec/tree_hints.json` 写
  `coverage_gate_approved`（by=user + 阈值 + 理由）否则 `GATE: REFUSED` exit 3；阈值/放宽/批准人写进 `tree_coverage.json`。
  phase1-prepare Step 1.0.7 判据与铁律 5 同步改写。

### 测试
- 新 `_tests/test_plugin_form_0915.py` 11 例（三种布局的探针 / next_walk 路径与 spawn 形态 / 两条静态闸）、
  ART `_tests/test_tree_coverage_report_0915.py` 6 例。vv 套件 638 → 649；ART 30 → 36。
- 打包线：影子根重编 vv + ART，verify 逐例 src/bin 相同（含新增两条真参数用例）；冻结态 `next_walk` 对合成计划真派到
  `dispatch_walk`（此前 traceback）。

---

## 2026-09-15 文档 Windows 化回流 + 第 10 项补测 + golden/parity 路径无关化（阶段 C；**未 commit**）

> 阶段 B 留了三笔尾账：① vv 文档里还有 shell 一行式，而 codex 产物同位置早就改写过、从未回流；
> ② 并进 `run_fix_self_check` 第 10 项的三条硬约束**零测试守着**（验收实测可整段删掉而套件全绿）；
> ③ golden 与 parity 工具里冻着本机绝对路径，换目录就红 / 静默少跑。本节把这三笔结掉。

### C1. 文档 Windows 化措辞回流（人工逐段，禁机械 sed）
- 方法：`git show HEAD:codex/skills/arkts-visual-verify/<f>` 取**替换前**的 codex 产物文档，与源侧同名文档
  逐文件 diff，**只看含 shell 一行式的段落**，每处人工判三态：codex 版是等价的 py/跨平台写法 → 回流；
  是 codex 平台专属措辞（`$name` / `spawn_agent` / `.agents` 路径 / `.codex/agents`）→ **不回流**；
  源侧新版已重写该段 → 丢。**不做机械替换**：已知误匹配 `jq '.scenario_attempts'` 会撞上
  `已尝试: {attempts_summary}`，骨架相似度匹配的误匹配率在阶段 B 就试过、判为不可用。
- 结果：源侧 shell 一行式（jq/awk/sed/grep/管道/shell for-while/`$(ls …)`/trap/`$?`/xargs/find/`ls -`）
  **153 行 → 69 行**，17 个文件被改；改后这些文件的 shell 命中行与 codex 产物**逐字一致**。
  剩下的 69 行里 61 行与 codex 产物相同（散文里的 `grep`/`$?` 说明、`walk_clickables --grep` 这类脚本参数），
  另 8 行是**源侧新增、codex 产物没有对应段**的（`phase2-edge-walk` 的 `adb logcat -d | grep -i toast`、
  `phase3-skeleton` 的「旧片段一律 sed 成 null」、`phase5-systemic`/`phase6-summary` 的 0913-0914 归因段、
  `batch-sections/B0.6-dialog.md` 与 `phase2-page-dispatcher.md` 两个 codex 侧不存在的文件）——本轮不动。
- 典型回流：`write_blocked` bash 函数 → 三条 python 一行式 + Write 工具；`#via=` / KNOWN_TRIGGERS 的
  jq 大块 → 单条 python 一行式；`FOREGROUND=$(… | grep … | head -1)` 崩溃检测 → `subprocess` 一行式；
  `ROUND=$(grep … | awk …)` → `lib_resolve_round.py`；`which adb || find ~/Library` → `lib_tools.py`；
  `$SKILLS_ROOT/…/resize_screenshot.py`（裸执行，Windows 无 shebang）→ `python3 $SKILLS_ROOT/…`；
  一批 ```bash 代码块改标 ```text（块里本来就是带 `{占位符}` 的伪代码，不是可跑的 bash）。
- **不回流**的平台专属项逐条留痕：`spawn_agent`/`wait_agent`/`agent_type` ↔ sub-agent/`Agent(...)`、
  `$android-fact-tree` ↔ `Skill(android-fact-tree)`、`~/.agents/skills` ↔ Claude 侧的用户级 skills 目录、
  `.codex/agents/*.toml` ↔ `.codex/agents/*.md`。

### C2. `references/phase1-prepare.md` 的 `bash → python3 …` 笔误
代码块里 `bash → ` 前缀去掉（Step 1.0.7 树覆盖率记分卡门）。同文件 Step 1.0.5 / 1.0.6 两处同款笔误
在 C1 回流时被 codex 版同位置覆盖（codex 侧早已改对），一并落地 —— 三处均为 HEAD 就有的既有笔误。

### C3. `run_fix_self_check.py` 第 10 项补正向测试
- 新增 `_tests/test_fix_self_check_item10_0915.py`（9 例）：三条硬约束
  （`nav_failed` 必须 `android_verified: true` + `blocks_subtree`／`kind: BLOCKED` 的 `blocked_by` 必须指向
  存在的文件／`FACT_TREE_INVALID_EDGE` 必须 `suggested_fix_owner: app-relationship-tree`）
  各一个「违规必 FAIL」+ 一个「合规 PASS」，另加「只扫 `round-N/ui/` 不扫 `feat/`」口径锁与多单聚合例。
  断言同时卡 exit code 与**判定文案**（下游按文案分诊）。每个用例先 `assert_baseline_clean` 自证
  夹具在第 1~9 项下干净 —— 否则 FAIL 会被别的检查项冒领。
- **突变自证**：把第 10 项整段（1039 字节，与验收报告删的是同一段）注释掉 → 本文件 **9 例中 5 例红**；
  还原后 9/9 绿。此前同样的删除实验是 **626 passed、零失败**。
- `_overrides.json` 的 093 / 112 两条 `why` 补全：112 例 `FAIL: 435 → 438` 的 3 条
  `blocked_by 指向不存在` 逐条归因 —— 1 条是真 schema 违规（`blocked_by` 写成
  `precondition:hmos_device_has_no_local_documents` 这种前置态描述串），2 条是夹具只拷 `spec/fix/` 子树
  导致的路径缺席（树与证据目录没进沙箱）。

### C4. golden / parity 的路径无关化
- **`_dev/sh_py_parity.normalize` 新增两类占位符**：`<SKILLS>`（本 skill 安装根 / `~/.agents/skills` /
  `$CLAUDE_PROJECT_DIR/.agents/skills`，各含 realpath，顺序照抄 `run_scenario_with_verify._resolve_dep`）
  与 `<REAL_PROJECT>`。此前 golden 005/006 冻着 worktree 的绝对路径
  （`run_scenario_with_verify` 的「请先跑 …/arkts-scenario-runner/scripts/scenario_run.py」提示行），
  **把 skill 拷到别的目录这两例必红** —— 与"无 bash 的机器照跑"的初衷直接冲突。
- **新闸** `test_py_golden_0914.py::test_goldens_have_no_absolute_paths`：golden 落盘里不许出现任何
  绝对路径（含 Windows 盘符形）。撞红时**不许加白名单**，去 normalize 补占位符规则再重固化。
- **受影响 golden 已重生成**：从 git 取回 `run_scenario_with_verify.sh` → `freeze_golden.py --only
  run_scenario_with_verify` → 删回 `.sh`。7 份重固化产物里只有 005/006 各一行 stderr 变
  （绝对路径 → `<SKILLS>`），其余逐字节相同。另 8 份真实工程 golden 的 `requires_fixture` 元数据
  改写成 `<REAL_PROJECT>` 占位符。
- **顺手修 `freeze_golden --only` 的坑**：它原本无条件整份覆盖 `_manifest.json`，局部重固化会把没重跑的
  用例从清单里抹掉。现按 `file` 名合并（重固化后仍是 116 条）。
- **`_dev/parity_cases.py` 去硬编码**：`REAL_SPEC`/`REAL_SPEC_ALT` 两个本机绝对路径改成环境变量
  `VV_PARITY_REAL_PROJECT`（可指工程根或其 `spec/`），文件头写明用法。8 个【真实工程】用例
  **恒定留在矩阵里**（golden 靠 `case_index` 回指，条目数随环境增删 = 换机器全部错位），夹具缺席时
  由 runner 显式 skip 并打出环境变量名；`sh_py_parity --all` 同步加 SKIP 行与「跳过 N 例」汇总 ——
  治此前"换台机器少跑 8 例、报告照写全绿"的静默 skip。
- **异地跑绿证据**：整个 skill 目录拷到另一条路径后，`test_py_golden_0914.py` 不设 env
  **116 passed / 8 skipped**、设 env **124 passed**；全量 `scripts/_tests` **630 passed / 8 skipped**，
  与 worktree 内一致。

### 套件与产物
- vv 收集数 **628 → 638**（+9 第 10 项正向例、+1 无绝对路径闸）。设 `VV_PARITY_REAL_PROJECT` → **638 passed**；
  不设 → **630 passed / 8 skipped**。`app-relationship-tree` 30、`toolkit-fact-indexer` 23 不变。
- C1/C2 改了源侧文档 → 用 `codex-adapter/scripts/convert.py` 重建并按路径同步替换了
  `codex/skills/arkts-visual-verify`、`codex/skills/app-relationship-tree/scripts`、
  `codex/agents/visual-fixer*.toml`，替换后再重建一次证明逐字节相同。

---

## 2026-09-14 源侧全 py 化收口：23 个 .sh 退役 + codex 独有件回流（阶段 B；**未 commit**）

> 阶段 A 已把这 23 个 `.sh` 在源侧做出行为等价的 `.py`（116 例 parity 全过）。本节是收口：
> 把**引用**改过来、把 `.sh` **退役**、把只活在 codex 产物里的件**搬回源侧**，
> 使 codex 版随时可从源侧一键重建，且三平台（含 Windows 原生，无 bash/awk/grep/sed/jq/yq/sips）同一套脚本。

### 1. 引用改写（180 行 / 61 文件 + 19 处特例）
- 通用：`bash …/x.sh` → `python3 …/x.py`；裸 `x.sh` → `x.py`。范围 = vv 的 `SKILL.md`、`references/*.md`、
  `scripts/**/*.py`（文本与 `subprocess`）、`scripts/blocked_reason_routes.json`、`arkts-agents/agents/*.md`，
  以及 6 个跨 skill 真调用点（`a2h-dump-verify/scripts/ensure_android_dumps.py`、`android-fact-tree/scripts/dispatch.py`
  与其 `evals/evals.json`、`app-relationship-tree`、`arkts-completeness-verify`、`arkts-metric-verify`、`compose-fact-tree`）。
- **`TRIP_ID=<trip> bash …run_scenario_with_verify.sh` → `python3 …run_scenario_with_verify.py … --trip <trip>`（5 处）**：
  PowerShell 没有 `VAR=x cmd` 写法，env 前缀在 Windows 上根本传不进去。`--trip` 与 env `TRIP_ID` 等价、参数优先。
- **`subprocess` 调用点 8 处改走 `sibling_exec.sibling_cmd`**（walk_finalize / dismiss_popups×3 / resize_screenshot×3 /
  run_scenario_with_verify）：打包态下 `sys.executable` 是 Nuitka 的 libpython（不可执行），直接 spawn 会 `Errno 13/8`。
  `materialize_blackbox_to_factree.py` 因不在同目录，加了个 best-effort 的 `_resize_cmd()` 借同目录 `sibling_exec` 构造。
- **有意保留的历史提及**：`CHANGELOG.md` 23 行 + `references/rationale-log.md` 1 行（历史叙述，改了就是篡改记录）；
  `scripts/_dev/{sh_py_parity,parity_cases}.py` 各 1 行（它们就是对 `.sh` 的验证器，见下）。

### 2. 23 个 `.sh` 退役（`git rm`）+ golden 接班
- **删之前先固化**：`_dev/freeze_golden.py` 把 116 个 parity 用例的 **`.sh` 侧观测**
  （退出码 / stdout / stderr / 产物 / 删除的文件，归一化规则**复用** `sh_py_parity.normalize`）
  冻进 `_tests/fixtures/golden_sh_0914/`（116 份 + `_manifest.json` + `_compose_geometry.json`，共 576 KB）。
- **新闸** `_tests/test_py_golden_0914.py`：只跑 `.py` 与 golden 比（116 例）+ 接管原 parity 测的静态闸
  （同名 `.py` 齐备 / 零 shell 依赖 / `open()` 带 encoding / compose 只许标签带不同）+ 新增
  `test_no_sh_left_in_scripts`。**无 bash 的机器照跑** —— 这正是全 py 化的目的。
- **删** `_tests/test_sh_py_parity_0914.py`（它要两侧同时在场，`.sh` 没了就跑不起来）。
  **留** `_dev/sh_py_parity.py` + `_dev/parity_cases.py`：golden 是"结论"，它们是"怎么得出结论的"。
  头部写明重跑要先从 git 取回：`git show 915_vvSpeed:arkts-skills/skills/arkts-visual-verify/scripts/<name>.sh`。
- **真实工程夹具的 golden 带 `fixture_digest`**：工程演进后夹具漂移 → 用例 **skip 并说明**，而不是误红。
- **有意的行为超集走 `_overrides.json` 声明**（见 `_dev/golden.py: apply_override`），不许用 `ignore` 把整条差异吞掉。
- **补 `dismiss_popups` 的离线用例 14 例**（`_tests/test_dismiss_popups_offline_0914.py`）：它是阶段 A
  **覆盖最薄**的一个（只验到参数闸，L1~L4 关闭阶梯一步没验，因为每轮都要真设备 dump）。
  判定内核 `_parse_dump()` 是纯函数，拿合成 Android dump 直接喂：L1 catalog / L2 文本（含「不同意」负向保护、
  正文 vs 按钮同分取小）/ L3 几何角标（含 >6% 屏滤除）/ L4 BACK / CLEAN / overlay 签名复用与跨分辨率还原 /
  签名结构性（挪位置不变）/ HMOS 与缺 catalog 的 exit 3。**全程零设备。**
- **`.sh` 的 7 处真 bug 随退役消失**（阶段 A §⑤，`.py` 侧本就免疫，此处只作记档）：
  4 处「变量紧贴全角标点没写 `${}`」（`run_scenario_with_verify.sh:74` 让边遍历 trip1 债闸**当场崩、形同虚设**、
  `check_dimension_prereqs.sh:87` 让 exit 0/3 永远到不了、`auto_install_artifacts.sh:90`、
  `run_phase2_android_survey.sh:147` 静默吞退出码）；2 处集合运算缺 `LC_ALL=C`
  （`check_android_screenshot.sh` / `assert_run_success.sh` 在中文页名上 `sort -u` 塌缩 → **分母塌缩、覆盖率虚高、闸假绿**）；
  1 处 `_DEBT=$(… || echo "?")` 把 `"2\n?"` 当债数。**这些 bug 的原文只在 git 历史里了。**

### 3. codex 独有件回流（REPORT_A ④ 的 13 件）
| 件 | 去向 |
|---|---|
| `carry_forward_findings.py` | **丢弃** —— 源侧 `carry_forward.py` 正是为修它那套「文件名承载状态」的五处同根缺陷而写，搬入 = 回退 |
| `check_fix_schema.py` | **并进 `run_fix_self_check.py` 第 10 项**，不留第二道 schema 自检入口（双源是本 skill 反复吃亏的形态）；`fix-file-schema.md §十` 由 8 条改记 10 条并写明由来 |
| `check_reviewer_report.py` | 搬入；**替换** `phase6-summary.md` 里的内联 `python3 -c` + `test`/`grep`（PowerShell 下引号转义断串，`test/grep` 在 Windows 上根本没有） |
| `render_report.py` | 搬入并**改写结论源**：原读 `run_state.json` 的 verdict（自带一套判据），改读 `round_budget.py end` 落在 `spec/fix/_state.yaml.last_verdict` 的判定。配套给 `round_budget.py` 抽出 `verdict_of()`（那条规则的唯一表达式）并在 `end` 落痕。整轮账本若在则渲染覆盖账明细，不在只少一张表 |
| `assert_round_complete.py` | 搬入，**不新增主流程硬闸**。它与 `round_budget.py`、`assert_run_success.py` 的判据三方重叠，接上去就是两套整轮判据 —— **待合并**。现登记在 `cli-cheatsheet.md` 工具箱表 + `limitations.md` |
| `assert_gap_ticket_coverage.py` / `resolve_hmos_impl.py` / `smoke_one_page.py` / `device_triage.py` | 搬入并在 `cli-cheatsheet.md` 工具箱表逐条登记调用点（"文件在、没人调"= 零调用点，等于没搬） |
| `_tests/test_round_gates.py` | 搬入并**裁掉 case_7/8/11** —— 它们测的是**未回流**的 codex 侧 `round_budget.count_debt/read_round_state` 与 `compile_replay_plan.edge_untappable`；另加 pytest 壳，否则 `case_*` 函数会被整份漏收 |
| `references/windows-setup.md` | 搬入并改写：源侧现已全 py、`.sh` 已退役，不再有"以哪份为准" |
| `references/layout-troubleshooting.md` / `wiring-gap-detection.md` | 搬入（源侧此前 0 命中，纯方法论、零平台耦合）；一并补进 SKILL.md frontmatter `references` 清单 |

### 4. 顺带
- `codex-adapter/scripts/rewrite_rules.yaml` 的 `R2-paren-sh` 摘掉 `expect: required`：
  `$x` 写法此前只出现在 vv 的 `.sh` 里，退役后该规则必然 0 命中，留着每轮都是假警报
  （adapter SKILL.md §4a：防御性规则不要标 required）。规则本身保留。
- 套件：**490（阶段 A 前基线）→ 610（阶段 A）→ 628（本节）**。
  例数变化说明：阶段 A 的 116 个 bash parity 例被 116 个 golden 例**等量替换**（判据不变、不再需要 bash），
  净增 18 = `test_golden_set_is_complete` + `test_overrides_all_point_at_live_goldens` + `test_no_sh_left_in_scripts`
  + `test_round_gates_all_cases`（内含 52 个 case）+ 14 个 dismiss_popups 离线例。跑时从 38.9s 降到 24.4s。

### 5. 本节**没做**的（待拍板，见 REPORT_B ⑧）
- codex 产物里**从未回流源侧的脚本改动**：`round_budget.py` 的 `DEBT_DISPOSITIONS`/`count_debt()`/`read_round_state()`
  （2026-08-16 补洞：「把没测到写成终态单 → 缺页越多账面越干净」）与 `compile_replay_plan.py` 的
  `edge_untappable()`/`overlay_edge_notes()`（「控件实测不存在才降级 skip」编译闸）。
  **源侧至今没有这两道闸**；codex 产物重建后它们会消失。已记进 `limitations.md`。
- codex 产物里 **74 行已 Windows 化（jq/awk/grep/trap/`$?` → python 一行式/跨平台说法）的文档行**未回流
  （源侧 vv 文档仍有 134 行 shell 依赖，codex 产物只剩 60 行）。试过机械回流，误匹配率高，判为**须人工逐行**。
- codex SKILL.md / e2e-pipeline.md 的「Phase 6.4 整轮硬闸必跑」「Step 6.9 报告必须机械渲染」两节未回流
  （前者即上面的双源问题；后者随之）。

---

## 2026-09-14 关单判据统一为「页级 similarity ≥ 0.95」（用户拍板第 5 条；1–4 条改法待审）
- 用户目标：每页相似度 ≥ 0.95。四处 0.95 统一口径：fix-file-schema §五表格 `fixed` 行、关键规则 2、4 与 phase7-stubborn-loop.md 冲刺出口，
  一律改为「所在页**页级** similarity（rubric 评分、仅排除系统栏，定义落 phase4-multimodal.md 输出格式）≥ 0.95 且无 CRASH → 页关闭，
  页内单随页关闭；页未达标时该页任何单不得 fixed」。此前四处只写"sbs similarity ≥ 0.95"，整页/元素不明，且实测从未被执行。
- ① rubric 已落（phase4-multimodal.md 平台差异段 + 输出格式）：只豁免顶部状态栏与底部系统导航条，字体/图标/dp-vp 豁免作废；
  数据页动态区只比结构与样式不比内容条数；WebView 不做 UI 打分；`overall_similarity` 必须由 differences[] 按 high 0.05 / medium 0.02 /
  low 0.01 扣分算出，清单空 = 1.0；身份对等归采集侧闸。待落：② 采集侧身份闸；③ fixed_pending_page 记账态；④ 已并入 ①。

## 2026-09-14 取消 `RESOLVED_` 改名（B1）+ 四处规范措辞（M1–M4）（用户拍板；B2「整页 similarity」实验判不可用，未落）
- **B1 fixed 单不再改名**：schema §五第 3 条改"只写 `disposition: fixed` 三字段、文件仍叫 `<id>.md`"，第 38 行补"任何阶段不得用
  文件名前缀承载状态"；e2e-pipeline.md / schema §六.5 两句"升 RESOLVED"同步。配套：① `arkts-agents/agents/visual-fixer.md`
  候选集过滤从"靠 RESOLVED_ 前缀 glob 不到"改为**读 disposition**（`fixed/skipped/manual_review/problematic` 与 `pending_*` 不进候选，
  fixer 仍不写 disposition）——真实 round-1 规范化目录实测候选 31（= open）而老规则 110（把 66 张 fixed + 13 张 manual_review 当候选；
  老规则在 legacy 目录上还静默漏掉 3 张 `CARRYOVER_` null 单）；② `render_finding_skeleton.py` 目标 `<id>.md` 已存在且带
  `carried_rounds`/`carried_from_round` → 拒绝新建（exit 21，不产 `-2`），同轮真冲突仍 `-2/-3`；③ phase4-replay-judge.md J2 规则 4 与
  sub-agent-batch-prompt.md：round-N 已有同 id 结转单 → **原地**写判定（fixed 三字段 / §3 追加复验 / 回归另起 `-regression` / 未到达不判），
  不新建不改名。下游链在"fixed 不改名"目录实测：open 73/31/14、manifest 假 hard 0、delta 66/26、stubborn fixed 零命中、自检规则 1 FAIL 0。
- **M1** schema §4.3-4 改为"BLOCKED 占位原名结转、不计 open、到达后 judge 出正常单并删占位"；**M2** SKILL.md 第 625 行改口径；
  **M3** phase4-replay-run.md §2 新增 2.0 三个来源参数固定约定（`--baseline-dir` 按趟取 `screenshots/android/<trip_id>/`；
  `--walk-plan/--android-unreached/--android-edges` 必须同一次边遍历同目录；参数名以 argparse 为唯一真源）——核出 `--baseline-dir2`
  所指目录**没有任何脚本产出**（本工程 `_shots_round1` 系手工归置），规范如实写明，待补产出方；**M4** phase5-systemic.md Step 4.5.c 加
  "§5 修复建议写前必核安卓源码"硬规则。
- `test_skeleton_carried_0914.py` 7 例（本日三笔落完套件合计 490）。实验/验收账在 `~/.agents/exp/cf_exp_0914/b1/`（ACCEPTANCE_B1.md）。
- **未落（用户待定）B2 整页口径**：实验量化 judge 判 fixed 的 ui 单所在页整页 ≥0.95 仅 12/60（r1）、5/24（r2）；严格整页 open 轨迹
  73→82→79；41 张已对齐单会进 stubborn；judge 判 pass 页中位 0.93–0.94；`similarity` 全仓零计算点（模型目测 `overall_similarity`），
  sbs 不裁状态栏。最小变体 V1 = 整页值只作页账/收敛判据，单张 fixed 按元素证据 + bounds 量证。
- 附带核出：`~/.codex/agents/visual-fixer.md` 镜像停在 08-04（缺命中链自检等 7 段），本次只把 B1 过滤补丁打到镜像，整体同步待定。

## 2026-09-14 J2.5 补合并器：K 份 judge notes → batch_notes.json（0913-14 旁观三轮实跑归因，问题清单第 2 条）
J1.8 切包并派后批级判断散在 `judge_packets/notes_partNN.json`，J2.5 只写了 build_batch_manifest 读 `batch_notes.json`，中间无合并
步骤：主会话手写合并在 round-1 trip_2 当场崩（judge_summary 有包 dict 有包 str、llm_interventions_adjudicated 有 dict 有 list、
part 有 int 有 str），"包收齐没"也靠人肉。
- 新 `merge_judge_packets.py`（`--capture-dir|--packets-dir [--out --index --owner-part --allow-missing --dry-run --json]`）：
  包齐闸（索引 K 包缺 notes → exit 21 不落盘）；键级无损合并——list 拼接按规范化 JSON 去重、dict **逐层递归**并集、只有叶子标量
  不同才判冲突（保 owner 包 = 索引 `trip_level_owner`，其余记 `_merge.conflicts[]` 带路径）、同路径异型按多数定主形态（平票
  list > dict > 标量，少数整份记 `_merge.type_mismatch`）；`part` 不进产物，`started_at`/`finished_at` 取极值；确定性。
  递归而非"子键保 owner"的原因：真实 notes 里有的包 judge_summary 按页写、有的包套 `{part,pages,totals}`，`trip_level_items`
  同名子键各包各一段 list——一刀切会把整块 pages 挤进冲突记录。
- 真实 6 趟（round-0/1/2 × 两趟，5+7 包）实测：全部合并成功；逐叶无损核对 0 丢失；与另一会话手写合并对比 7 个契约键条数逐一
  相同；用两种 batch_notes 各拼一次 manifest，findings / fix_files / pages_status / 占位 / resolved_prev / assembly_checks /
  systemic_candidates **逐字相同**（只差 judge_summary 形态与 finished_at 时间戳）。
- 规范：phase4-replay-judge.md J1.8 ②（judge 写 `notes_partNN.json`、键类型约定）/ ③ 与 J2.5 加第 ① 步；SKILL 五步框 ⑥。
  `test_merge_judge_packets_0914.py` 12 例（全合成；验收记 D2①：时间键全为非字符串时退回通用规则不丢、混写记异型）。

## 2026-09-14 Phase 3 结转改按 id 搬运（0913-14 旁观三轮实跑归因；用户定只落实验改过的 7 处）
三轮实证：phase3-skeleton 第 5 步 bash 片段把未收口单复制成 `CARRYOVER_<id>_from_rN.md` 却不改 frontmatter id、一律 sed 重置
disposition、只走 ui/、跳过已带前缀的 → 五处同根：① 自检规则 1「文件名=id」每轮 77/77 FAIL ② 4 张 BLOCKED 占位 `pending_*`
被清成 null 混进可修集与 open ③ `CARRYOVER_BLOCKED_P*` 不被 page_status --done / build_batch_manifest 认作占位 ④ 二次结转被
自己的前缀过滤（round-2 丢 7 张仍开的单）⑤ `_delta.md` 按 id 集合差算 fixed 报 85、frontmatter 只有 66。
- 新 `carry_forward.py`（`--fix-dir --round [--dry-run --json]`）：**文件名 = id 跨轮恒定**，结转信息落 `carried_from_round` /
  `carried_rounds`，不落文件名；遍历上轮实际存在的子目录（ui / feat / ui/_systemic）；fixed/skipped/manual_review/problematic
  不结转，其余（null/partial/pending_*）原样带走不重置；吃 legacy 前缀输入落成正名；幂等。phase3-skeleton.md 第 5 步改为调用它。
- `render_round_summary.py` `_delta` 改按 disposition 迁移：fixed = 上轮 open 且本轮 fixed；new / regressed / unchanged 同套归一
  id；新增 `still_open` 节。规范目录上 `_index` / `_summary` 逐字不变。
- `lib_ledger.round_tickets` 与 `build_batch_manifest` 三处 `RESOLVED_` 前缀过滤改 `is_closed_ticket(basename, fm)`（disposition
  优先，前缀保留兼容历史）——不配套改则 fixed 单不改名时被当待办，一页 6 条假 `pass_with_findings`。
- 隔离副本上真实 round-0/1/2 实测：结转 77（ui 67 / feat 10）；BLOCKED 4 张 pending 原样；自检规则 1 FAIL 67→0；占位认出
  0→4、假 hard 4→0；round-1→2 非收口 35/35 含丢过的 7 张，`carried_rounds=[0,1]`；delta fixed 85→66、96→26，legacy 与规范目录
  逐字一致；open 轨迹 73/31/14 不变；套件 458→471。`test_carry_forward_0914.py` 13 例；`test_ledgers.py:123` 原断言编码
  「消失即 fixed」旧语义，已按新语义改写并加 still_open 断言。
- **本次未动，记档待办**：`reformat_markdown_to_schema.py` 白名单会把 pending_*/partial/fixed/problematic 清成 null（缺陷②复活
  点）；`detect_stubborn.EXCLUDE_DISPOSITIONS` 不含 pending_*/problematic（占位跨 3 轮会被搬进 stubborn/）；schema §4.3-4
  「BLOCKED 占位不结转」措辞与线上实践相反；schema §五第 3 条 `RESOLVED_` 改名与自检规则 1 互斥（配套过滤已落，judge 侧口径未改，
  仍改名也兼容）；SKILL.md「carry-forward 成 `CARRYOVER_*.md`」一句已过期。

## 2026-09-13 全流程干跑（Opus 子代理，不修复，5h18m）归因：回放模式下游接线
干跑实爆三处断点：Phase 3.5 从树重推 45/49 页（基线 14/19）；Phase 5/6 只读 `batches/*/manifest.json` 而回放 manifest 躺在
`replay/<run>/` → 聚类 0、`_summary.md` 页面表空；`assert_run_success` cond 1 只看 `progress.json.pages` 而无人写 → 62 页假红。
- `build_batches.py` 新增 `android_edgewalk_partition`：无 chunk manifest 时分批来源 = `_trip_assignment.json` + 安卓 png 全集
  （规范 §1.1 分母），`batching_source=android_edgewalk_assignment`；不变式闸照跑。
- `mark_batch_done.py` 真写页账：`progress.pages[pid]`（status/similarity/rounds/fix_files/trip/batch/last_round），同轮重跑不重复计。
- 规范 phase4-replay-judge.md 新增 J2.5（judge 返回后 build_batch_manifest 拼到 `batches/round-N/` + mark_batch_done）；SKILL 五步补 ⑥。
- 离线验收（同一份 round-0 产物）：聚类 46 条 → 1 候选簇；页面表 35 行；batches 14/19 与 png 逐页一致；cond 1 清零。
  仍红：cond 6 覆盖债把树里的抽象基类当页（口径问题另开）。测试 `test_replay_downstream_wiring_0913.py`。
- **判定并行与采集解耦（用户拍板 B，不许 hard code 页数）**：新增 `slice_judge_input.py`——判定包按**负载**（页级产物必读 +
  证据抽看 + 归属 escalations，预算 = 上下文×字节/token×输入份额）FFD 装箱切成 K 包，一包一个 judge；J1.8 改口径、SKILL 五步补 ⑤′。
  本项目 round-0：trip_1 15 页→5 包、trip_2 20 页→7 包（每包 2-4 页 ≤234 KB），对照干跑每趟 1 个 judge 各扛 3.5h。
  根因记档：旧 J1.8 把并行度绑在采集切段上，切段是可选且 `slice_batches.py` 边界（冷启落地页的 tab_switch）随计划形态漂移，
  现行计划一趟切不出段。v2 不劣化判定三条（关联组不拆/别名原子/DFS 连续切；escalation 单一归属 + 对侧只读存根；趟级明细按页分发、
  无页标识只进第一包）+ `--max-parallel 8` 分波 + `--max-packets` 硬上限。round-0 实测切断边 trip_1 10→3、trip_2 25→8。
  `test_slice_judge_input_0913.py` 11 例。
- 干跑其它结论记档：判定段 3.5h 占 66%；「登录门缺失」P0 是 mock 后端登录态未随 trip 边界归零的环境假象；执行器模糊匹配
  把「登录」点到「退出登录」（确认框弹出未确认）——破坏词运行时护栏待做。

## 2026-09-12 replay-t2b 归因后（B 批）：哨兵选词补"必要条件" + 计划外门放行收窄触发面
用户要求"理论保障"：两条都先在三趟（t1i/t2a/t2b）327 份真实 dump 上离线回放、旧判对零变错，才落地。
- **哨兵**（`compile_replay_plan.build_sentinels` / `static_texts_by_node`）：② 候选按"树里是静态文案"优先（`layout_facts.static_texts` ∪
  `discriminators.texts`），其次原稀有度/长度；③ 回退哨兵集整体落在另一页文本里 → 置空 + `plan.sentinel_notes` 记账（只加②大纲页仍被认成
  PPT 页）——**③ 已实现但默认关闭**（用户拍板：只有 PPTFilePage 一页受影响，为免引新问题先不启用；步 18 那类假 P0 按已知误判处理）。
  两条护栏：同屏页静态文案取并集；`lib_ui_words` 按钮词表不配当哨兵。候选集 / identify 打分 / 判位模型不动。
  离线：只加②三趟 327 份判定零变化；②+③ 时 t2b 3 份改判正确。重编译只动哨兵字段，翻译账相同。
- **计划外门**（`replay_exec._unplanned_gate_candidate`）：目标没到 ∧ 认不出任何计划页 ∧ 不站在登录门页（PAGE_REF）→ 问一次
  `choose_gate_control_hmos`；coldstart 在轮询循环内试、wait 分支并入旧触发面；放行后同一步重判到达（期望不变）。
  离线：327 份 dump 只在 8 份 trip_2 首启协议门上触发，零误触。
- **t2c 验收（trip_2 第三跑，与 t2b 严格 A/B，③开启的计划）**：两靶子 PASS——首启隐私门被执行器机械放行（`gates` 1 条、只点「同意并继续」、
  无误放行），t2b 第一次人工介入消失；步 18 `WRONG_LANDING→PPTFilePage`（假 P0）变 `ARRIVED_strong→CreateOutLinePage`，大纲页首次 captured
  并结清 reconcile，全趟 pd=true 0（t2b 1）。零回退：163 步只 6 步 verdict 变化全为改善/中性，escalations 15 条是 t2b 17 条的真子集，
  靶单 14/19（t2b 13，且退掉一张"大纲页冒充 PPT 页"的错页），功能点 69/116（t2b 59），墙钟 29m32s（t2b 36m32s），交接 14（t2b 16）。
  未达预期一项：PPTFilePage 空哨兵没落 `ARRIVED_unanchored`（置空未同步打 `expect.arrival_confidence`，t2b 同步同为 NO_NAV，非回退）——③
  已按用户拍板默认关闭，此项随之不触达。
- t2c 揪出执行器两处并已修：冷启"最多一次"写成了"最多问一次判据"（第一轮启动图把机会用掉，门靠 wait 分支兜住）→ 改"最多放行一次、判据每轮问"；
  wait 放行后重判到达只给原步预算（~9s），过门后首页初始化 16–20s → `GATE_PASS_SETTLE_S=60` 按冷启口径等。`test_sentinel_gate_b_0912.py` 12 例；
  全套 442。计划按③关闭重编装回（t2c 用过的③开启版留档 `replay-t2c/plan_used_rule3_on.json`）。

## 2026-09-12 replay-t1g 归因后：判位改「路径先验 + 同平台参考」（F3）+ 模糊匹配落错页不判路由错（F1）+ back 已在目标页不按（F4）
用户定稿的判位模型：每步只答三个假设（还在 from / 到了 to / 去了别处）；页一旦本趟采过就拿鸿蒙自己的 dump 比（`texts_pos` /
`page_ref_match` / `on_page_by_ref`，`PAGE_REF` 在 capture 四条成功路径登记；状态栏带与纯数字剔除），安卓哨兵只管首次到达。
- 离线：t1g 121 份 dump 回放——撞词现场（客服 H5 / 关于页）J≤0.056 判"不在"，真站在源页 J=1.0；同页再 dump 53/72 True，
  19 False 里 12 份实为已点走到别页。整页签名方案被数据否决（同页再 dump 相同 16/53）。
- 接线五处：`_blame` ABANDON 站位（`source_page_unconfirmed` / `source_confirmed_by`）、弱到达押栈、back 步身份作废与
  `SKIP_back_already_at_target`、reconcile 站位、「别处」按参考命名（`landed_by=reference`）。
- F1：`escalate(..., matched_by)` → WRONG_LANDING 非精确命中记 `wrong_landing_after_fuzzy_match`（needs_verification）。
- **t1h 验收（同计划严格 A/B，121 行只差 2 行）**：F1 通过（步 44 → wrong_landing_after_fuzzy_match）；F3 同进程内通过（步 36/38 →
  source_page_unconfirmed J=0.056，8R 那页从 DEFERRED 救成真采，真站在源页三处零误伤），**但跨 resume 失效**（PAGE_REF 进程内存）；
  F4 未触达（被跳过弹窗的配对 back 是 kind=dialog，被排除条件绕开）。修：resume 读回 `PAGE_REF`（`PAGE_REF_RESTORED`）；F4 加栈结构判据
  （栈顶==目标 ⇒ 不按，`by=stack`），弹窗类靠它。`test_replay_page_ref_f3.py` 10 例；全套 419。
- 测试：规范 phase4-replay-run.md §2 新段（含残余风险）。
- **鸿蒙接 mock + 自签装机**（路线 A，用户拍板）：两常量指向 127.0.0.1:8899 + `hdc rport` + SDK OpenHarmony CA 自签；配方见记忆
  hmos-mock-build-selfsign。**t2a**（trip_2 首跑，登录态）：机械跑完、新机制全生效；覆盖卡在 mock 的 VIP 只在安卓源码补丁里（待拍板）。
- **A 组**（t2a 归因，安卓已有逻辑照搬）：安卓真值按趟（别趟确认不救回、`confirmed_other_trip`、`edge_confirmed_only_in_other_trip`）；
  `type`/`renav` 分支；`find_input_target` 四级 + `find_subtab_candidates_hmos`（声明词优先、排页级 tab）+ `plan.subtab_labels`；
  计划外门 `_unplanned_gate_pass`；排除表子串；`encountered_destructive.json` 跨进程聚合；`web_url_from_dump`。
  `test_group_a_0912.py` 11 例；全套 430。
- **F2（只改编译器，用户拍板）**：`android_edge_lookup_how` 区分 label/pair/none 命中；`label_seen_on_android` 三源判据；`label_gate`
  分流 skip（已覆盖）/ replace（换安卓实测控件）/ static_unverified（安卓无记录）；门探测步同闸；执行器 `trigger_label_unverified`。
  离线：t1g 计划 diff 只有步 55/56 变 skip；trip_2 同样两步。走序计划器不消费 not_reproduced 的浪费另开待办。全套 416。

## 2026-09-11 完整跑法（replay-t1f）12 次熔断归因后的 A/B 档修复（用户拍板「A、B 档都做，先确认跨项目通用且不引新问题」）
每条先离线在 t1f 真实产物（101 份鸿蒙 dump / 计划 / run.jsonl / 安卓基线）上验证再落；重编译 t1f 计划 diff 只含预期字段
（MineFragment 哨兵 ×1、探测步 kind ×20、match.text_identity_source ×31）。全部零 app 常量。
- ② `compile_replay_plan.value_shaped()`：数值形文案不当哨兵。**单词命中硬规则离线 A/B 否决**（13 份正确首页识别会变 None），
  `replay_exec.identify_scored(single_hit_ok)` 参数化、默认旧行为（`IDENTIFY_SINGLE_HIT_OK=True`）。
- ① `rid_texts` 收 content-desc；tap 步 `match.text_identity_source` / `android_dump_text`；执行器 rid-only 兜底按安卓屏上文案定位
  （`matched_by=android_dump_text:*`）；`_blame` ABANDON：rid-only 无屏上身份 → `no_screen_identity`（None/needs_verification）。
- ⑤ `identity_is_destructive(..., screen_text)`：三处身份接纳点连安卓屏上文案过破坏词表。
- 门判据：`gate_landing_verdict` 落点==源页 ⇒ NOT_EXERCISED（不论 sig）；`_blame` NO_NAV 排除项⑥ `feedback_without_nav`（sig 变了没导航）；
  弱到达记 `identified_as`，身份仍是源页（非弹窗）不押栈 + 页槽注记。
- ③ 救回探测步 `kind`/`expect.kind` 按目标类型推（`NAV_KINDS_COMPILE`/`DIALOG_IDS`）；执行器 `_is_push` 含 probe_only（门探测除外）。
- ④ `stack_prefix_from_plan` 续跑重建 DFS 栈（run.jsonl `STACK_RECONSTRUCTED`、manifest `resume_stack_reconstructed`、交接包 `stack_at_handoff`）。
- a) `lib_dumpsys.overlay_dialogs`；walk_exec `_defer_late_settle_if_overlaid` / `_retry_deferred_settle`（两条 late_settle 路径 + 主循环每步前）；
  capture_page_e2e `_dumpsys_overlay_ids` → `on_page` 顶部硬闸 + `classify_arrival(overlay_ids)` → dialog_over_page(source=dumpsys)。
- 测试：新增 4 文件 25 例；全套 407 通过（原 382）。规范：phase4-replay-run.md §2 新段、phase2-edge-walk.md §4.ab 第 8 条。
- 未做（C 档，待拍板）：顶层 position 在 auto+late_settle 后不推进；布局占位文案进合成 xml；T-2/T-3/T-5/T-6。

## 2026-09-11 树重复节点四件（用户拍板「都做，先验证可行」；L2 核实为已存在撤销）
归纳：节点 id 的 `$` 被赋两种意思（JVM 内部类 vs toolkit **方法现场**），方法现场当成独立的屏入树 → 与真弹窗类节点重复
（0910r3 树 8/30 个 dialog：纯复制 4 / 共享参数化弹窗的状态 4）。另六种"像重复"（容器与默认子页同屏 / 弹窗叠宿主 / 设计同构向导页 /
黑盒噪音壳 / 伪节点 / 内部类串台）各有归属，本批**一个都不合**。
- **L1 树侧根治** → app-relationship-tree Phase 1.7 `fold_call_site_nodes.py`（见该 skill CHANGELOG）。
- **L3 遍历侧只报不删**：新 `scripts/tree_feedback.py`，`walk_finalize.sh` 6.5 步非阻塞调用 → `$EW/tree_feedback.json`
  （影子节点 / 同屏对(整份 md5，两边都有布局=host_overlay_or_container 不判重复) / 同控件集弱信号；同文件多趟按 trip 覆盖）。
  真产物：trip_1 10 条 18ms（影子 7 = 全部 `$` 节点 + `Unknown#via` 噪音壳；两对同屏全判"叠/容器"不判重复）。消费者 = ART 1.7 `--tree-feedback`。
- **L2 撤销（核实已存在）**：`coverage_targets` = 安卓基线 png 全集，未达/影子节点天然不在分母；别名交付由执行器 `alias_group_expansion`
  + `lib_coverage.captured_alias` 完成。无实例、无缺口，不加代码。
- **F6 auto 转场边 → `wait` 步**：`compile_replay_plan.py` 无控件身份的 auto 边不再 skip，编成 `wait`（`auto_wait_budget`：默认×2 /
  安卓 waited_s×1.5 / countdown×1.5 取大，≤30s；翻译账 `emitted_wait`）；`replay_exec.py` 新分支（哨兵/identify/别名组/歧义组/wait_hint
  文案任一命中 → settle 后采集押栈 `AUTO_ARRIVED`；没到 → `AUTO_NOT_OBSERVED` / `AUTO_LANDED_ELSEWHERE` 进归因
  `auto_transition_missing_in_hmos` / `auto_transition_diverged`，`product_defect=None + needs_verification`，不交接）；
  `build_judge_input.py` 透传 `needs_verification` + 两条 ticket_kind_hint + 提示词一行。规范 phase4-replay-run.md §2 补段。
- 通用性复审（用户追问）：等待上限从写死 30s 改为 `--auto-wait-cap`（默认 30；上限是 app 相关量，不能写死）。
- **零介入复跑 replay-t1d（Opus 5 子代理按规范执行）**：停在第 16 步（此前第 8 步），3 个 wait 全 AUTO_ARRIVED（步 6 真等 9.0s），
  六步引导链一次走通；停因 = 引导结束后鸿蒙落全屏会员中心而非首页（`auto_transition_missing_in_hmos`，needs_verification，D-1 待 judge 核实）。
- **T-4 元素文本身份**（先离线验证再落）：`compile_replay_plan.rid_texts/attach_element_identity`——元素 `match_labels` 头部插安卓 dump 里
  该 rid 的真实文案（驼峰/下划线互认），标 `text_identity_source`；执行器无身份元素记 `unverifiable_no_screen_identity`
  （blame_hint `no_screen_identity`）不再盖 control_missing；judge `alabel()` 驼峰互认、`no_screen_identity` 不进 P0 改判。
  离线模拟 replay-t1d 实采 dump：observe_only 命中 3→13/16。`_tests/test_element_text_identity.py` 6 例。
- **T-1 wait 开始前判位**：已站在已知别页 → 立即 `AUTO_LANDED_ELSEWHERE(diverged_before_wait)`，不空等、不再误判"没实装"；识别不出照常等。2 例。
- **零介入复跑 replay-t1e（Opus 5 子代理）验 T-4/T-1**：T-4 假账清零（`not_found+control_missing` 17→0，rendered 3→14，
  unverifiable 6 逐条核对＝真无文本身份）；T-1 步 13 → `AUTO_LANDED_ELSEWHERE(diverged_before_wait)` 0.8s；停点仍第 16 步（D-1）。
  抓到本批两处缺陷并修：**N-1** T-1 提前返回跳过轮询 → 落点页顺路采+插队 reconcile 那一路（t1d 靠 `_catch_transient` 碰巧命中）没了，
  会员中心 25 条观察丢失 → wait 未到达分支显式"落点∈靶单 → 顺路补采 + `_arm_reconcile`"；**N-4** `unverifiable_no_screen_identity`
  未进 `lib_coverage.UNVERIFIED_OUTCOMES`，无证据被计进分子 → 加入。各 1 例。
- **N-2 瞬态页采集根治（安卓侧，2026-09-11 真机实证后落）**：交付基线是首页图却账本 verified 的病根 = 尺子（uiautomator 等 idle，
  窗口内一次 7.4s）+ `chain_position` 绑定不核图。新 `lib_dumpsys.py`（`dumpsys activity top`：0.05s 身份尺 + View 树 + 布局文案）、
  `walk_exec._transient_burst`（候选机械筛：auto push 出边且 hint≠immediate；tap 后立刻窗口循环，身份一离开即止，绑最后一帧，
  合成 uiautomator xml 打包 pending_shots）、`capture_page_e2e.load/bind_transient_bundle`（优先吃包；没包且验不上 →
  `Esc(16, transient_missed)` 挂债，**chain_position 绑定路径删除**）。真机 28 份快照复核：0.7→5.66s 身份成立，5.96s 切首页。
  规范 phase2-edge-walk.md §4.ab。测试 +14。
  **真机验收**（scratch 副本项目 + 安卓模拟器 walk_0 前 14 步）：step12「继续」→ GuideInit 连拍 5 帧（0.35→4.31s，身份
  dumpsys_resumed_fragment，5.32s 离开）→ 绑定最后一帧（图=83%/正在进入AI 真加载页）；ledger `capture=verified /
  identity_by=dumpsys_resumed_fragment / dump_source=dumpsys`；边真值 waited_s=0.35 + transient_capture；step13 auto 边落首页
  waited 2.4 并补结账。验收抓出并修 1 处：瞬态页绑定后原路径还去"普查后判位"→ 误报 position_mismatch → 加
  `sweep_skipped_transient`（位置交下一步 auto 边落点）。顺带看见两处既有问题未修：① `classification_pending_streak` 熔断包
  记 `step ?`，`--resume` 会从上一步重跑（已到达的设备被再点一次、把瞬态页点穿），正确续走项是 `--mark-step-done N --assume-at`；
  ② Difficulty1/2/3 三页同文本 settle 连续 exit 16（T-5）。
- **上述①②③ 三处随即修掉（用户："刚遇到的问题你可以修了"）**：① `_ledger` streak 熔断前把游标推到下一步、位置=本步落点、
  熔断包带真实步号（主循环记 `_cur_idx/_cur_step`；escalate 的 expected_position 下标加护栏）；②③ 同根——文本/唯一 id 在
  "向导三页同文本"与"共享弹窗只渲染部分子 View"（step14 现场 dump 就是 AppTipsDialog 却判 0/5）两形态下都分不出 →
  `lib_dumpsys.identity_on_node` 补弹窗叠宿主语义（两者都 RESUMED：判弹窗在场即成立、判宿主页多出的只许是弹窗），
  walk_exec 全部 13 处 `sentinel_check` 调用换成 `self._sentinel`（不中/弱 → dumpsys 兜底），capture_page_e2e `on_page`
  在宿主闸与末尾两处加 `_dumpsys_on_page`（`_PKG` 全局由 --pkg 填）。踩坑：正则替换把包装器自身那行也换成了递归调用 → 57 例回归，改回。
  测试 +2（弹窗叠宿主 / on_page 假驱动兜底）。
  **真机验收（Opus 5 子代理，scratch 副本 walk_0 前 18 步，零人工介入）**：①③④ 通过、② 未触达（streak 本轮没发生）。
  Difficulty1/2/3 `verify_by=dumpsys_resumed_fragment`、零 exit 16；step12 连拍 5 帧 0.34→4.69s 绑真加载页（92%），step12 后无
  position_mismatch；step14 AppTipsDialog 放行（离线复现：同一份 dump 喂 sentinel_check 仍是 0/5，放行只能来自 dumpsys 兜底；
  step19 屏上真无弹窗时兜底**没有**放行）。走到 step 18，比修前多 4 步。
  子代理记下新现象（未修）：**a) HomeActivity 基线 dump 与 AppTipsDialog 的 md5 相同**——late_settle 时自动弹窗盖屏，uiautomator
  只 dump 顶层窗口，宿主内容零采集却因 activity 后缀相符判 verified（与 N-2 同族、方向相反："宿主页基线里只有弹窗"）；
  b) 合成 xml 进度文案是布局默认 40%（已声明 text-source=layout）；c) auto 边 + late_settle 路径不推进顶层 position/next_step；
  d) step19 立即开通无反应 = 协议勾选框未勾（勾选属禁点，0910 安全复核已知）。
- 记录未修（已被上条覆盖，留作历史）：**N-2** 安卓基线 `GuideInitFragment.android.xml` 采到的是首页内容（瞬态 loading 页采晚了）→ 该页两个 rid 永远拿不到身份、
  judge 会拿错基线比——**安卓采集侧缺口**，待安卓遍历侧处理；N-3 `_dump_observe` 顺路结账的观察在 run.jsonl 无对应事件（可追溯性）；
  T-2/T-3/T-5/T-6 同 t1d。
- 测试：`_tests/test_tree_feedback.py` 4 例、`test_compile_auto_wait.py`、`test_replay_wait_action.py`。
- 干跑核实：0910r3 → CodeX_0829 trip_1 重编，步 2/6/7（首启门 / Splash→引导 / 引导宿主→默认子页）由 skip 变 wait。

## 2026-09-10 晚 → 09-11（鸿蒙回放侧：首次真机两趟实跑后的对齐修复）
CodeX_0829 首跑：两趟零介入均停在第 5 步；根因链 = 树重复建模（`SplashActivity$showPrivacyDialog` 是无布局事实的影子节点，与
`LaunchAgreementDialog` 基线 md5 相同）→ 安卓侧归因「已消费不可再现」自洽掩盖 → 编译器不读安卓未达归因 → 鸿蒙照排放行步 →
鸿蒙执行器又没实现 gate_pass → 停摆。审查结论：**执行期已是「翻译失败⇒疑鸿蒙缺陷⇒三分归因⇒出单」模型，翻译期（编译）不是**——
登录趟 61 动作步编译期静默跳 47，其中 26 条安卓已 confirmed，0 条进归因。
- `compile_replay_plan.py --android-unreached <reason_overrides.json>`：安卓判「本趟到不了」的页不发动作，透传安卓原话；tap/deeplink 看 to，gate_pass 看 from。
  `_tests/test_compile_android_unreached.py` 7 例。两趟各拦 7 步，卡死点消失。
- 下面一节是 gate_pass 移植的待并原文。
- **翻译对等性三条（2026-09-11，用户拍板；「搬家」一条撤掉各自处理）**：`--android-edges` 救回安卓 confirmed 的边（unanchored 弱到达 /
  安卓运行时身份补触发物 / 反向门禁探测 `expect_blocked`→`GATE_HELD|GATE_MISSING`→`gate_missing_in_hmos` security 必出单）+ 翻译账
  `translation_ledger_<trip>.json` + skip 必带 reason。干跑：trip_1「安卓验过却被静默跳过」26→8（8 条全有结论），tap 18→31；trip_2 tap 19→35；
  空 skip_reason 33→0；不带新入参零差异。新增 42 例，全量 **341 passed**。
- ★主会话操作错误记档：CodeX_0829 首跑两趟都没传 `--walk-index`，登录趟计划编自登出趟走序；规范 §2 已补「每趟必传」。
- 下面一节是翻译对等性批的待并原文。

### 并入：鸿蒙翻译对等性（compile / replay_exec / build_judge_input）
> 待合入 `CHANGELOG.md`。改三个脚本 + 两个测试文件，**不碰设备 / adb / hdc / git**，不改别的文件。
> 一句话目标：**安卓已经验证过的边，鸿蒙侧一条都不许静默放过；安卓被门拦住的边，鸿蒙侧要去验门还在不在。**

---

#### 病

`AIPPT_CodeX_0829` 两趟真机回放跑完后审下来的结论：

**执行期**早就是一套完整模型 ——「翻译失败 ⇒ 疑鸿蒙缺陷 ⇒ 三分归因（`_blame`）⇒ 出单」；
**翻译期（编译）不是**。编译器是盲的：它只读安卓产物决定"试什么"，试不了就跳，跳了不留痕。

真产物的数字（只读核实，`AIPPT_CodeX_0829/spec/visual-verify/replay_plan_trip_1_logged_out.json`）：

| 事实 | 数 |
|---|---|
| 登录趟动作步 | 61 |
| 编译期静默跳过 | **47** |
| ↳ 其中对应的边**安卓已实测 `confirmed`** | **26** |
| 这 26 条进过执行器三分归因的 | **0** |
| `skip_reason` **为空**的步 | **33** |

后果是账面性的，不是性能性的：这 26 条边上，**「鸿蒙没验」和「鸿蒙没问题」长得一模一样**。
再加 33 步连"为什么没翻"都查不到（理由只落在上游 `note` 里，`skip_reason` 空着，
执行器只能报一个 `SKIP_PLAN`）。

还有一类**完全不可见**的东西：安卓在登出趟被登录/会员门拦住的边。鸿蒙侧从来没人去点它们，
所以「鸿蒙把这道门丢了」——未登录就能进本该登录才进的页——这件事**没有任何产出物会提到**。
这是安全属性，不是覆盖率数字。

顺带核实出的一条项目侧事实（不是 skill bug，不在本批修复范围）：
项目里那份 `replay_plan_trip_2_logged_in_vip.json` 是用 **`--walk-index 0`** 编的
（步型与 `walk_0_first_launch` 完全一致，且缺 walk 1 独有的 `type` / `renav` 步）——
两趟计划实际编自同一条走序。本批干跑按正确的 0/1 分别编译。

---

#### 治

##### 改动 1：安卓 confirmed 的边不许静默跳过（`compile_replay_plan.py`）

新入参 `--android-edges <edge_results.json>`。**不给则这条轴上行为一字不变**（老项目零回归，见验收）。

新模块级函数（全部可脱设备单测）：
`load_android_edges` / `android_edge_lookup` / `android_control_identity` / `identity_is_destructive`。

- **索引按 `(from,to[,trigger])` 分级**。只按 `(from,to)` 查会取回**兄弟边**的 rid ——
  安卓侧 2026-09-10 真机实测的 `mechanical_sibling_rid_collision` 就是这么点错控件的
  （同页两条边，一条 `取消订阅`、一条 `快速退款`，取回兄弟的那条实际点了退款）。
- **控件身份不按趟过滤**：同一个 rid 在哪一趟都是同一个控件。「这条边这一趟通不通」
  才是按趟的事（`status` / `device_state`）——两件事分开。

两条通路（对应用户说的两种跳过）：

| 原跳过 | 新处置 | 落在哪 |
|---|---|---|
| `no_trigger_captured`（树没采到 trigger） | 从安卓真值补 `control.rid` / `control.text` → `match.source="android_runtime"` 照发 | `resolve_identity` 四源合一（禁重实现，走序 tap 路径与探测路径共用一个实现） |
| 上游 walk_plan 自己压下去的 tap 边（`scope_exit` 等，`skip_reason` 空） | 安卓 `confirmed` 就救回来发出；目标页**无哨兵**时 `expect.arrival_confidence="unanchored"` + `expect.sentinel=[]` | 新增 `probe_only` 步 + 紧跟一条 `probe_return` 回位步 |
| 两条通路都补不出身份 | 仍跳过，但 `skip_reason="untranslatable_no_control_identity"` | 「真的翻不了」与「我们没去问」从此分得开 |

☠️ **两处必须成对出现的加固**（都是审自己这版代码时揪出来的）：

1. **补来的身份要重新过破坏性闸**。原来的闸只查走序 `trigger` 文案；"从安卓真值补身份"
   是一条**新通路**，绕开了那道闸。真产物里就有现成的炸弹：一条 `confirmed` 边走序
   trigger 为空、安卓真值里的控件 rid 命中资金 rid 表 —— 不重查就会被"照发"，
   而它是资金动作。`identity_is_destructive` 复用既有四张表（`DESTRUCTIVE_RE` /
   `_FUND_RE` / `_FUND_RID_RE` / annotations 黑名单），**不新造词**（新词表 = 新的追不上 app 的东西）。
   干跑实测拦下 2 条。
2. **救回来的边在 DFS 里没有配对的 back**（planner 决定不下钻就不会排回位步）。
   只发 tap 不发回位 = 一脚踩进另一棵子树，后面每一步都在错的屏幕上找控件 ——
   **正是首跑那场级联事故的形状**。所以成对发：`tap(probe_only)` + `back(probe_return, probe_from=<目标页>)`，
   执行器侧再加一道 **"栈顶不是它就整步跳过"** 的守卫（探测没进去就绝不按 BACK）。

##### 改动 2：反向门禁探测（`compile_replay_plan.py` + `replay_exec.py` + `build_judge_input.py`）

**门节点怎么认（零 app 硬编码）**：某节点 G 的入边前置条件里有
`kind ∈ {login_required, vip_required, login_conditional}` 且 **`polarity == "absent"`** ——
读作「登录/会员**缺席**时这条边会落到 G」⇒ **G 就是那道门**。
真产物实测：登录页靠 7 条 `login_conditional/absent` 入边被认出，会员中心靠 6 条
`vip_required/absent` 入边被认出，**全程没有一处写死页名**。
（副产物：计划新增 `login_gate_pages` / `gate_nodes` / `trip_id` / `trip_logged_out`。
前两个是**执行器早就在读、却从来没人写**的字段：`replay_exec.py:295` 读不到就退回双语正则。）

**本趟是不是登出态（三级，全非 app 常量）**：
① 注解显式 `logged_out_trips`（人说了算）→ ② 注解 `state_signatures[trip]` 与**门节点入边文案**有交集
（屏上写着"点击登录"这类字 = 还没登录；真产物实测：trip_1 的两条态签名**都是**登录页的入边文案，
trip_2 的两条一条都不是）→ ③ 趟名兜底正则（流水线命名习惯）。**判不出来一律不发探测**。

**被拦住的边（两选一、任一命中）**：
① 树里该边有 login/vip `polarity=="required"` 前置条件；
② 安卓真值里这条边 `landed` 落在门上（`landed ≠ to` 且 `landed ∈ 门集`，正则只兜底、且只作用在**落点节点名**上
——不扫全屏文本，否则登出屏上的"登录"字样会假阳）。
`expected_gate` 两级解析：同页同控件 → 同控件跨页（**真产物实测必要**：某入口的 `absent` 兄弟边
挂在另一页上，只按同页匹会解析不出门）。都不中留 `None`，执行期退回门节点全集判 ——
**不猜具体是哪道门，但知道"得是道门"**。

`--android-unreached` 的跳过对这类边**让位**：它们"安卓到不了"的原因**就是门**，
而门本身正是要验的东西。不让位 = 反向门禁探测整条线失效。

**执行期落点四分**（`gate_landing_verdict`，纯函数）：

| 落点 | verdict | 出单？ |
|---|---|---|
| 屏没变 & 仍在源页 | `GATE_NOT_EXERCISED` | 门没被触发 → 按**既有 NO_NAV 三分归因**走（排除项一条不动） |
| 门节点集 / 门页哨兵 / 兜底正则 | `GATE_HELD` | **正常行为，不出单** |
| 目标页或任何非门页 | `GATE_MISSING` | **安全缺陷**：`blame=gate_missing_in_hmos`，`product_defect=True`，`severity=security` |
| 识别不出 | `GATE_UNKNOWN` | **不猜**，走既有交接（exit 32） |

`GATE_NOT_EXERCISED` 这一档是**顺序上最要紧的一条**：不先判它，"点了没反应"会被反过来读成
"门没拦住"——方向正好相反。

回位：探测步（`probe_only=True`）两种结果都**立即单次 BACK 回起点**，根页守卫照旧
（鸿蒙栈根 BACK 实测致白屏卡前台，不可赌）。走序步（`probe_only=False`）不对称：
`GATE_HELD` → BACK + `phantom=1`（用既有级联机制安全跳过没进去的子树，而不是让后面每步都在错屏上找控件）；
`GATE_MISSING` → **不回位**，计划照常走完子树（我们确实进去了，覆盖不能丢），安全单已经出了。

`build_judge_input.py`：`gate_missing_in_hmos` 与 `control_missing_in_hmos` **同级**进 must_ticket 路径
（两者 `product_defect` 都是 `True`），另标 `severity: security`，新增 `ticket_kind_hint`
`SECURITY_GATE_MISSING`，并在缺页裁决说明里加一条「它与『到没到』无关，落点非门即成立」。

##### 改动 3：翻译账（`compile_replay_plan.py`）

落 `translation_ledger_<trip>.json`（与计划同目录）：安卓计划里**每条 tap 边**一条记录
`{from,to,trigger,android_status,hmos_disposition,reason,step,rescued?,expected_gate?,control_source?}`，
`hmos_disposition ∈ {emitted, emitted_unanchored, emitted_expect_blocked, folded_to_reconcile, skipped}`。
stderr 加一行摘要（**跳过原因只统计安卓 confirmed 的边** —— 把全部 skip 的原因混进来，
"安卓验过却没翻"这条线会被噪音淹没，那是分母取错的同一类错）。

**编译期任何 skip 一律要有非空 `skip_reason`**：上游 `skip_reason` 进透传键表（原先被丢），
再兜底填 `upstream_<kind>`。摘要里 `empty_reason_bug` 计数，非零就是 bug。

##### 不是什么

**不是"失败就出单"。** 执行器的三分归因与**六种防假单排除项一条没删**
（规范里记着一个根因报成 11 张缺页单、12 条假 `control_missing_in_hmos` 的事故）。
本批只保证「候选一条不漏、核实全部机械」。反而**新增了两道**防假单：

- `_blame` NO_NAV 排除项⑤：计划外探测步 + 安卓只在**另一趟**确认过这条边 →
  `product_defect=None`（态不对，不是 handler 没实装）。不加这条，跨趟救回来的边会整片刷成假 P0。
- 探测步的 `ABANDON_no_match` / `NO_NAV` **不交接**：交接的理由是"位置丢了、后续步全失效"，
  而探测步**根本没动过位置**（控件都没找到，一下都没点）。为一条计划外的额外观察中止整趟 =
  用 1 个观察换掉剩下的全部覆盖。归因照记、单照出，只是不 exit 32。

---

#### 判据（每条都可机械复核）

| 判据 | 吃什么 | 绝不吃什么 |
|---|---|---|
| 这条边安卓验过没 | `edge_results[].status` + `(from,to,trigger)` 精确键 | 页名、文案猜测 |
| 控件身份 | 走序 trigger → 树 runtime control → 安卓 `control.rid/text` → 树门前置条件的 `trigger_view_id/label` | 硬编码 rid |
| 这条边被门拦没 | 树 `edge_preconditions.kind/polarity` / 安卓 `landed` | `LoginActivity` 之类字面量 |
| 谁是门 | 树 `polarity=="absent"` 的宿主节点 | 页名正则（只兜底，且只作用在节点名上） |
| 本趟登出没 | 注解 `logged_out_trips` / `state_signatures` ∩ 门入边文案 / 趟名 | app 侧任何状态串 |
| 落点是不是门 | 计划 `login_gate_pages` + `expected_gate` + 门页 `node_sentinels` + 兜底正则 | 全屏文本扫"登录"二字 |
| 能不能点 | `DESTRUCTIVE_RE` / `_FUND_RE` / `_FUND_RID_RE` / annotations 黑名单（四表取并，复用） | 新造词表 |

#### 通用性自查

- **零应用硬编码**：三个脚本里新增的字面量只有 schema 词汇（`login_required` / `polarity` /
  `confirmed`）、流水线自己的字段名，以及一条**双语**登录门兜底正则
  （`Login|SignIn|Auth|登录|登入|ログイン|로그인`，与 `replay_exec._LOGIN_GATE_RE` 同源同义）。
  没有任何被测应用的页名 / rid / 文案。
- **测试夹具全占位串**：`PageA` / `GateX` / `ctlA` / `判别物A` / `入口甲`。断言里不出现真实应用常量。
- **树 schema 兼容**：门解析走既有 `tree_nodes()`（三数组 与 扁平 `nodes` 都认）。
- **没有门前置条件的树 / 非登出趟** → 一条探测都不发（有反例用例锁）。
- **不给 `--android-edges`** → 救边、补身份两条通路一字不变（A/B 实测见下）。
- **换 app 不改代码**：新增的每一个判据都只吃计划字段 / 树字段 / 注解 / 安卓边真值 / dump 属性。

---

#### 验收

##### 测试

`_tests/test_compile_android_edges_and_gate.py`（24 例）+
`_tests/test_replay_gate_probe_and_unanchored.py`（18 例）。
全量 `cd scripts && python3 -m pytest -q _tests`：**341 passed**（基线 299 → +42，零回归）。

编译侧逐 disposition 正反例：`emitted` / `emitted_unanchored` / `emitted_expect_blocked` /
`folded_to_reconcile` / `skipped`（含"补不出身份"与"补来的身份是资金动作"两种反例）、
不带新入参零变化、每一条 skip 都有非空 reason、`--android-unreached` 对门禁边让位。

执行侧（假设备，脚本化状态机，**不碰 hdc/adb**）：`GATE_HELD`（不出单 + 单次回位）、
`GATE_MISSING`（`product_defect=True` + `severity=security` + 走序步不回位继续走）、
`GATE_HELD` 走序步用 phantom 跳子树、落点判不出走交接（exit 32）、点了没反应回落 NO_NAV、
根页不 BACK、`ARRIVED_unanchored`（弱到达 + `position_confidence=low` + 不交接）、
无锚点落到别的已知页**不判** `WRONG_LANDING`、探测步找不到控件记归因但不中止、
探测回位步"没进去就不按"、老计划（无新字段）走法一字不变。

##### 只读干跑（真机产物重编译到 scratchpad，**没有覆盖项目里任何现有计划**）

输入：`AIPPT_0910r3_walk/spec/visual-verify/edgewalk/{walk_plan,edge_results,reason_overrides,grounding_results}.json`
+ `spec/toolkit-fact-tree.json` + `AIPPT_CodeX_0829/spec/visual-verify/{replay_annotations.json,_shots_round1}`。
两趟分别按 `--walk-index 0/1` 编译。

| | trip_1_logged_out | trip_2_logged_in_vip |
|---|---|---|
| 安卓 `confirmed` 的边 | 39 | 44 |
| 鸿蒙发出（其中从 skip 救回） | 24（14） | 32（7） |
| 降级发出（unanchored） | 3 | 0 |
| 反向门禁探测 | **4** | 0（非登出趟，按规矩不发） |
| 折进 reconcile | 0 | 3 |
| **仍跳过** | **8** | **9** |
| ↳ 原因 | `untranslatable_no_control_identity`×6（全是无控件可点的 auto 转场边）、`destructive_pruned`×2 | `android_unreached_*`×6、`untranslatable_*`×2、`first_launch_gate_consumed`×1 |
| 空 `skip_reason` | **0**（原 33） | **0** |
| tap 步 | 18 → **31** | 19 → **35** |

**这批的核心数字**：登录趟"安卓 confirmed 却被静默跳过"从 **26 → 8**，
且剩下 8 条每条都有可核对的结论（6 条是 auto 转场、安卓自己也没有控件可点；2 条是资金动作主动拒点），
**没有一条是"不知道为什么没翻"**。

##### 不带 `--android-edges` 的 A/B（HEAD 版编译器 vs 本版）

两趟逐步比对：**唯一差异**是 ① `skip_reason` 从空填上（改动 3，有意）；
② 登录趟 4 条门禁探测（改动 2，树驱动，有意；登录趟才有，会员趟 0 条）；
③ 顶层多 4 个字段。救边/补身份两条通路**零差异**。

---

#### 未做 / 待判

1. **重复探测不去重**：真产物里同一条 `(from,to)` 有 3 条兄弟边都被判为门禁边，
   会发 3 次同样的探测（tap+BACK，无害但费时）。去重要在上游 walk_plan 做，本批没碰。
2. **`GATE_MISSING` 的纯探测步不落页级图**：只存 `__gate_missing` 证据图 + 现场 dump，
   不进 `pages_status`（避免把"靠安全漏洞进去的页"算成正常交付）。judge 拿得到证据，但没有页级 sbs。
3. **未真机跑过**：本批只做到只读干跑 + 假设备单测。`GATE_HELD/MISSING` 的真实落点判定
   要等下一趟真机才算实证。
4. **项目侧 `--walk-index` 用错**（trip_2 编自 walk 0）是核实出的事实，未改动任何项目文件。


### 并入：鸿蒙 gate_pass 移植（replay_exec + lib_ui_words 单一真源）
> 2026-09-10。待合入 `CHANGELOG.md`。改三个文件、加一个测试文件，**不碰设备 / adb / hdc / git**。
> 通用性铁律：判据只吃**计划字段 / dump 属性 / UI 词表**；夹具一律 `PageA` / `GateDlg` / 「占位正文…」
> 这类占位串，逻辑与断言里不出现任何真实应用的页名、类名、控件名。

---

#### 病

`AIPPT_CodeX_0829` 第一次跑鸿蒙回放，**102 步只走了 8 步就退出**。

根因不是判据错，是**动作没人接**：安卓侧 2026-09-09 新增的 `gate_pass`（放行首启协议 / 权限门）
只落在 `scripts/walk_exec.py`（`Exec.do_gate_pass`），鸿蒙执行器 `scripts/replay_exec.py` 里
**零处出现 `gate_pass`**。编译器（`compile_replay_plan.py`）一切正常——步发了、`note` 也写清了
「放行门：执行器按放行词表点唯一放行控件后验回起点」——指令却掉进 `tap` 兜底分支：
`gate_pass` 步没有 `match`，`five_match` 拿 `rid=None,label=None` 空转，落
`ABANDON_no_match` 且 `tried: []`（**连试都没试**，这是账本里最刺眼的那行）。

后果是连锁的，不是单点的：首启协议弹窗一直挡在屏上 → 后面每一步都在**错误的屏幕**上找控件 →
第 8 步 `GuideStatusFragment --[下一步]--> GuideDifficulty1Fragment` 落 `control_not_found` 交接退出。

真机产物（只读留档）：`AIPPT_CodeX_0829/spec/visual-verify/replay-run1/`
（`run.jsonl` 步 3/5 是两次 `ABANDON_no_match / tried:[]`，`now.json` 是卡住时的真实 dump）。

#### 治

##### 1. 词表抽成单一真源（新增 `scripts/lib_ui_words.py`）

`UI_WORDS_DEFAULT` / `_UI_RE_KEYS` / `_compile_ui_words` / `UI_WORDS` / `load_ui_words`
整体搬进新模块，`walk_exec.py` 与 `replay_exec.py` **import 同一个对象**。
`walk_exec.py` 只留 re-export，对外名字与行为一字不变（安卓侧 265 个既有测试逐字依赖）。

> 为什么必须是**一份**而不是两份长得一样的：本仓已有前车之鉴——编译期 `_FUND_RE` 与执行期
> `DESTRUCTIVE_RE` 是两把不一样的尺子，结果「编译期挡住的元素，重导航时被自己点回去」。
> 门词表若各抄一份，同一堵门在安卓侧放行、鸿蒙侧不放行，且没人会发现。
> 照抄的先例：`replay_exec.py` 早就写着 `from blackbox_explore import DESTRUCTIVE_RE
> # ★复用通用破坏性词表…非手补窄词`。

**一处刻意的行为加固**：`load_ui_words` 改成**原地改写** `UI_WORDS`（`clear()` + `update()`），
不再重新绑定模块全局。原因是抽库后两端都是 `from lib_ui_words import UI_WORDS` ——
重新绑定只会换掉库里的名字，import 方手里仍是旧字典，**项目覆盖会静默失效**。
表内容前后完全一致，安卓侧 B9 那组覆盖用例（含幂等、未知键忽略、正则键编译）原样全绿。

`replay_exec.main()` 新增一行 `load_ui_words(dirname(--plan))`，与安卓 `$EW/ui_words.json`
同一契约（生效的覆盖键记进 `manifest.ui_words_overridden`）——换语种 / 换文案习惯的 app
靠**整表覆盖**，不改源码。

##### 2. 鸿蒙侧实现 `gate_pass`（`scripts/replay_exec.py`）

模块级新增（可脱离设备单测）：
`_gate_text_blob` / `gate_body_verdict` / `gate_body_present` / `_gate_label` /
`_gate_negative_hit` / `_gate_contains` / `choose_gate_control_hmos` / `gate_handoff_extra`；
`main()` 内新增 `act=="gate_pass"` 分发支（排在 `skip/verify/probe` 之后、`back_inpage` 之前），
并给 `_blame` 加 `GATE_PASS_UNKNOWN / GATE_PASS_UNVERIFIED` 两个归因分支。

**三道判据同时成立才点**（安卓 `choose_gate_control` 的原样语义，词表同一张表）：

| # | 判据 | 词表键 |
|---|------|--------|
| ① | 屏上正文命中门语义（协议 / 隐私 / 声明 / 承诺 / 权限说明…） | `GATE_BODY_RE` |
| ② | 正文**不含**退出登录 / 注销 / 删除 / 退款 / 支付… | `GATE_BODY_NO` |
| ③ | 候选控件先剔否定键，再挑白名单命中项或 id 命中项，**唯一才点** | `GATE_TEXT_NO` → `GATE_TEXT_OK` / `GATE_ID_RE` |

判据①②的「正文」= dump 里**全部**文本节点（含按钮自己的文案），与安卓
`" ".join(re.findall(r' text="([^"]*)"', xml))` 同一口径。这带来一个**刻意保留**的连带效果：
按钮文案带破坏词时（如「确认注销」），②先于③判 `body_has_destructive` —— 更保守，两端一致。

**选不出就不点**：0 个 → `no_allow_control`；多于 1 个 → `multiple_allow_controls`；
正文不像门 → `body_not_gate`；正文带破坏词 → `body_has_destructive`；dump 空 → `empty_dump`。
一律走既有 `escalate` + `_escalate_handoff`（exit 32），reason `gate_pass_unknown`，
交接包（`checkpoint.json`）带 `gate_candidates` / `gate_allow_candidates` / `gate_denied_candidates`
——「屏上有哪些候选文案」是人处置这一步的唯一输入，没有它人只能自己再跑一遍 dump
（0909 熔断成本治理的同一条教训）。**绝不猜、绝不退而求其次点别的键。**

**点完验落点**，三档：
- `GATE_PASSED`：`identify(post)==to` 或计划哨兵命中且签名变 → 正常结账 + `_arm_reconcile`。
- `GATE_PASSED_weak`：**门语义已从屏上消失且签名已变**（`settle_dump` 档验落点）→ 按弱到达
  如实入账（`captured_weak` + `__weak` 帧 + 降置信注记），继续走。
  为什么不硬要哨兵：本文件 `coldstart` 分支的长注已实测记账——**鸿蒙侧哨兵 14 个命中 0**
  （动态文案 + 两端文案不同），拿它当到达硬闸会让首启第一步就死，而「门还在不在」才是
  这一步真正承重、且完全机械的判据。
- `GATE_PASS_UNVERIFIED`：门还在 / 屏没变 → 交接（exit 32），**不静默继续**
  ——静默继续正是 0910 连锁失败的形态。

`descend`（下沉栈）**不动**：门是一次性浮层，计划里从没有一条 tap 边把它押进过栈
（门步前恒为 `skip / no_trigger_captured`），放行是消费不是弹栈。

##### 3. ★鸿蒙特有陷阱（真机 dump 实证，安卓没有这个问题）

`now.json` 实测的节点形态：

```
Stack  clickable=true   [247,1675][1072,1830]        ← 真正可点的是**容器**，自身无 text
└ Text clickable=false  text="同意并继续"             ← 放行键的文案在**不可点**的子节点上
Text   clickable=true   text="不同意"                 ← 拒绝键自己就是 clickable
```

安卓实现按 `clickable="true"` 扫 XML 节点。**照搬会出两种结果：要么一个都找不到，
要么更糟——只匹配到「不同意」并点下去**（那是拒绝协议，可能直接退出应用，
且会消费掉一次性门，冷启也回不来）。

治法两条，都写成显式代码 + 显式测试：
1. 候选一律取自 `from blackbox_explore import extract_clickables_hmos`
   （其 docstring 明写「clickable 容器自身往往无 text，文案在子 Text 节点上，
   提取时下钻 1-3 层抓最深的有意义 text」），**绝不自己扫 `clickable` 属性**；
2. 无论候选怎么来，**先按 `GATE_TEXT_NO` / `DESTRUCTIVE_RE` 把否定键剔掉**（查文案、
   描述、id 三处），再在剩下的里挑白名单命中项。顺序反了就会点错键。

「多于一个算选不出」的**唯一例外**：文案完全相同**且几何上一个包着另一个**
（下钻会让 clickable 容器与它的按钮拿到同一文案）——这在结构上不可能是两个不同的按钮，
合并成一个并取更内层（bounds 更小）那个。**文案不同的两个放行键仍然算歧义，一律交接。**

#### 判据（怎么算修好了）

- 拿 0910 卡住时的**真实 `now.json` + 真实计划步 3** 跑整条分发链（零设备）：
  tap 落在 `(659,1752)` = 「同意并继续」容器中心，**不是** `(660,1927)` = 「不同意」；
  verdict `GATE_PASSED_weak`，`gate_allow=["同意并继续"]`、`gate_denied=["不同意"]`。
- 回归闸：`gate_pass` 步不再出现 `ABANDON_no_match`，run.jsonl 行里不再有 `tried` 字段。
- `cd scripts && python3 -m pytest -q _tests` = **292 passed**（基线 265 + 新增 27）。

#### 通用性自查

| 项 | 结论 |
|---|---|
| app 硬编码 | 无。判据只吃 `lib_ui_words.UI_WORDS` + dump 属性 + 计划字段（`step.to` / `step.expect.sentinel`）。 |
| 词表可换 | 可。`<计划所在目录>/ui_words.json` 整表覆盖，与安卓 `$EW/ui_words.json` 同一契约；有英文门的用例。 |
| 两端会不会漂 | 不会。词表只有 `lib_ui_words.py` 一份，两端 `import` **同一个对象**（有 `is` 断言的测试）。 |
| 夹具 | 全合成 dump，app 侧文案一律占位串；出现的中文只有词表本身的跨项目词。 |
| 设备 / git | 全程零 adb / hdc / git；`DeviceAdapter` 由 monkeypatch 换成假设备。 |
| 其它脚本 | 未改。`compile_replay_plan.py` 本来就正确产出这一步，一个字没动。 |

#### 落盘

| 文件 | 动作 |
|---|---|
| `scripts/lib_ui_words.py` | **新增**（词表单一真源） |
| `scripts/walk_exec.py` | 词表块 → re-export import（对外名字/行为不变） |
| `scripts/replay_exec.py` | 8 个模块级门函数 + `act=="gate_pass"` 分发支 + `_blame` 两个分支 + `load_ui_words` 接线 |
| `scripts/_tests/test_replay_gate_pass.py` | **新增**（27 例） |

#### 未做（记账）

- `references/phase4-replay-run.md` / `SKILL.md` 未同步这一步的散文说明（本文件合入 CHANGELOG 时一并处理）。
- `codex/` 侧未重生成（走 `codex-adapter`，不在本次范围）。
- 未真机复跑 `AIPPT_CodeX_0829`（按铁律不碰设备）；下一趟原样重跑才是公平对照。

---

## 2026-09-10 晚（第四轮：第三轮验证跑 127 min 后归因的 10 条工具缺陷；三批并行，按文件归属切分）
本轮账（AIPPT_0910r3_walk，09:30→11:37）：墙钟 127 min（0910 为 245.5）、熔断 30 次（0910 为 41）、结账 30/47、基线 33 张；
收尾链趟与孤儿探测**双双算出零**（第三轮两项改动的效果被真机证实）；尾巴红三次全部按规范处置，零静默改绿。
- 三批改动分别见下三节（执行器 6 条 / 普查与回位 2 条 / 判读债与跨趟 2 条），互不重叠、各自带单测。
- 主会话侧本轮的产物级处置（不改代码，按 skill 既有铁律执行）：
  · 两条同起点同终点的破坏性边被执行器取回兄弟边控件而假 confirmed → 按边真值铁律降级 not_reproduced + 归类注记（负面证据不删边）；
  · 一条 `to=null` 的 unplanned_destructive 边按源码锚点消歧到真实目标、状态维持 deferred_destructive；
  · 一条判读证据路径因跨 trip 覆写失效 → 改指覆写前的落点帧；
  · 未达 17 条归因（禁点动作 8 / 数据态缺 7 / 工具缺陷 2）；其中 `WebViewActivity` 按 phase2.5-grounding §2c
    「H5 语义=功能项不是 UI 项」改判 structurally_unreachable（本就不该产 UI 基线，后续走三段式，**不要补图**）；
    `RecommendListFragment` 从 nav_unreachable 改判「绑定待判」（见本轮 C 批）。
- 测试：全量 `python3 -m pytest -q _tests` = **265 passed**（第三轮基线 200）。
- 未修（已记账，待拍板）：`_options.close_then_resume` 用 `_tap_cmd` 拼命令，而 `_tap_cmd` 结尾带 `#` 注释 →
  后接 `&& <续走命令>` 会整段落进 shell 注释，点完取消不会续走（既有缺陷，本轮 A3 新命令已避开该写法）。

### 并入：执行器第四轮（walk_exec r4，6 条）
> 2026-09-10。**只改一个文件** `scripts/walk_exec.py`，新增单测
> `scripts/_tests/test_walk_exec_round4a.py`（23 例，含逐条正例/反例与两条「行为一字不变」回归）。
> 全程合成计划 + 合成 dump + 假设备，子进程（node_sweep / walk_ledger）一律 monkeypatch，
> 不碰设备 / adb / git。
> 通用性铁律：判据只吃**计划字段 / 树字段 / dump 属性 / 哨兵表 / UI_WORDS 词表**；
> 夹具一律 RootPage / HubPage / LeafPage / ConfirmDlg 这类占位名，
> 逻辑与断言里不出现任何真实应用的页名、类名、控件名。
> 六条病灶全部来自 2026-09-10 真机回归（22 次熔断 + 边真值复核）。

---

#### A1 熔断菜单：一次性门已消费时首项空转

**病.** 计划要求到达一个**一次性首启门**（隐私弹窗 / 首启提示窗），但它已被前序步的放行控件消费掉、
宿主也已越过。此时菜单首项恒是 `resume_assume`（`position_mismatch` + 强落点分支），
而这类门边是 auto（wait-first）边，**每次都要等满 wait 预算才判失败**：0910 实测同一条门边
连试两次 = 49s + 24s 纯空烧，两次都只是把「门不在了」重新证明一遍。

**治.** `_options` 新增前置判据 `_gate_consumed_landing(step, diag)`，成立即把一条
`skip_gate_consumed` **旋转到 `options[0]`**（老首项退居其次，不删）：
`--skip-step N --skip-reason gate_consumed:landed_<落点>`，
effect 写明「一次性门已被前序步消费（放行即当场消费掉证据），本趟不可再现；门的基线若还没有，
靠下一趟 pm_clear 首启链补」，`coverage_loss=false`（D① 的「跳过整棵子树，共 N 步」照旧带上）。

**判据（三条全机械，零文案常量）.**
1. 计划把本步标了 `step.gate`（门的身份**只认计划字段**，执行器不认任何业务词）；
2. `diag.control.in_dump` 与 `in_clickables` **都为假**（屏上根本没有这个门）；
3. `diag.landing_node` 强落点（判别物投票命中 + 哨兵 `ok` 且非 `weak`）是计划里
   **只在本步之后**出现的节点（本步及之前从未作为任何步的 `from`/`to` 出现）= 宿主已越过该门。

**通用性自查.** 三条判据分别来自计划字段 / dump 属性 / 哨兵表 + 计划步序，
没有任何「隐私」「同意」类文案；换 app 只要计划照常标 `gate` 即生效。任一条不成立就退回原菜单
（反例已测：控件仍在 dump 或可点集、落点是更靠前的节点、落点弱判、本步不是门步）。

---

#### A2 熔断菜单：`chain_advanced_unresolved` 首项是死循环

**病.** 链页普查把一次性链推进了一格，计划里没有从新落点出发的步 → 熔断
`chain_advanced_unresolved`，但该 reason 没有专属分支，落进通用三选一，`options[0]` 是
`resume`（**原步重试**）。重试会重跑该步 → 重新普查 → **再推一次链**。
0910 实测 3 次共 590s，是本轮单位成本最高的一类。

**治（两处，缺一条仍是死循环）.**
1. `_options` 新增 `chain_advanced_unresolved` 分支：
   - 强落点在 → `options[0] = mark_done_assume_landing`：`--mark-step-done N --assume-at <实测落点>`
     （落点取熔断包 `diag` 的强投票结果）。effect 写明「边真值与结账在普查前已落，不重复记」。
   - 落点判不出 → `options[0] = skip`（`--skip-reason chain_advanced_landing_unresolved`），
     欠账已在 `state.capture_debt` / `sweep_debt` 里由收尾链趟补。
   - 该 reason **整体跳过 D② 重排**（D② 会把 `resume_assume` 提回推荐位 = 死循环复活）。
   - 无论哪条路径，`options[0]` 都不含 `--resume`。
2. `_maybe_sweep` 新增「**本 walk 已普查过该节点就直接返回**」（`state.sweep_ran` 去重）：
   `--mark-step-done N` 的续走路径会对该步的 `to` 再触发一次普查，节点若是一次性链页，
   第二次普查等于再推一次链——首项换了、循环还在。普查按设计本就是「首达一次」。

**判据.** `reason` 字符串 + `diag.landing_node/landing_sentinel` + `state.sweep_ran`；零业务常量。

**通用性自查.** 去重只挡「同一 walk 同一节点第二次」，不挡首达（反例已测：干净节点照跑，
argv 与老行为一致）；跨 walk 不受影响（state 换 walk 即归档重置）。

---

#### A3 熔断菜单：`action=="verify"` 的步首项只改声明不动设备

**病.** 宿主校验步（`action=verify`）熔断时首项是 `resume_assume --assume-at X`——
`--assume-at` 只改执行器**声明**的位置，改不动设备；而 `do_verify` 的判据正是设备真实
activity/哨兵 ⇒ 必然二次空烧（0910 实测 52s）。

**治.** `_options` 对 `action=="verify"` 的步把 `options[0]` 换成「先把设备弄回宿主再 `--resume`」：
- **当前落点是压在宿主上的子 activity** → `back_then_resume`：
  `adb shell input keyevent 4 && <--resume 续走命令>`（先动设备、再续走，顺序写进 cmd），
  effect 写明「**根 activity 上禁按 BACK**（会退出 app / 炸栈底），到了根还不对就改走重新导航」。
- **否则**（当前 activity 就是宿主 / 根 activity / launcher，或判不出）→ `renav_then_resume`：
  effect 给出 `plan_path_to` 算出的**到达路径**（`RootPage→HubPage`）与各层推进步号，人工重导航后 `--resume`。
两条 effect 都点明「verify 步只认设备真实 activity，`--assume-at` 改不了它」。

**判据.** `step.action` + `diag.activity` 短名 + 哨兵表的宿主（`_expect_host`）+ 行走 root 的宿主 +
`--launcher` 短名 + 计划栈模拟（`plan_path_to`）。全是计划/哨兵/dumpsys 字段。

**通用性自查.** 「子 activity」只按「当前 activity ≠ 宿主 activity 且 ≠ 根/launcher」判，
不认任何页面名；非 verify 步的菜单一字不变（回归用例已测 `resume_assume` 仍在首位）。

---

#### A4 门放行步：落点与计划不符时先信运行时

**病.** 计划把首启放行门的落点写成 `X`，实测放行后应用**直连** `Y`（计划/树的落点事实缺陷）。
`do_gate_pass` 放行后只会 `verify_at(X)` → `position_mismatch`；代理处置后重试，
放行控件已被第一次点击消费掉 → 第二次熔断 `gate_pass_unknown`。**同一个门连炸两次**。

**治.** `do_gate_pass` 放行后的落点校验改成三段：
1. 一次 dump + 哨兵：与计划一致 → 直接返回（与原 `verify_at` 首拍命中等价，happy path 设备动作不变）；
2. 不一致 → `_landing_strong` 强投票；落点 `Y` **是计划里后续某步的 `from`** →
   接受它、`_save_state(position=Y)`、记 `state.gate_landing_drift[]`
   `{step, gate, planned, observed, why, walk_id, device_state}` 与一条
   `gate_landing_drift: 计划 X → 实测 Y` 的 note（供人回写树），**不熔断**；
3. 判不出 / 不在计划后续步里 → 走原 `verify_at`（原熔断路径、原菜单）。

**判据.** dump + 哨兵表 + `lib_landing` 判别物投票 + 计划步的 `from` 序列；零业务常量。

**通用性自查.** 只接受「计划自己后面还要从它出发」的落点（= 计划仍然走得下去），
不接受任意落点（反例已测：树外落点仍熔断 `position_mismatch`，且不写漂移账）；
落点与计划一致时不记漂移、不多按任何键（回归用例已测）。

---

#### A5 边真值：同起点同终点的多重边取回兄弟边的控件（数据正确性，最重的一条）

**病.** 同一起点上两个不同控件指向同一目标（共用确认弹窗、同一 helper 起两条边）在树里是两条
`inbound_trigger`；`_runtime_rid(from,to)` 只按 `(from,to)` 找上一轮反哺的 rid，**取第一条命中**，
多重边分不出来 ⇒ 执行器点了**同一个控件两次**，第二条边却被写成 `confirmed`、证据帧是兄弟边的弹窗。
0910 实测两条**破坏性入口**（注销账号 / 取消订阅语义）各中一次——假确认后果最重。

**治（两处）.**
1. `_runtime_rid(frm, to, step=None)` 增加消歧维度：
   - 候选唯一 → 直接用（**老行为一字不变**）；
   - 多候选 → 用本步的 `static_rid` / `item_rid` / `trigger` / `span_text` 对齐候选的
     `trigger_view_id` / `trigger_label` / `span_text`（及候选自己的 runtime rid），
     **唯一命中才返回**；对不上、多命中、或没有本步信息 → **返回 `None`**（退回计划 `static_rid`），
     绝不返回兄弟边的 rid。rid 比较统一取尾段（`pkg:id/foo` → `foo`，`_rid_tail`）。
   - 三处调用点（`do_tap` / `_control_diag` / `_nav_tap` / `_repair_same_dest_check`）全部把 step 传下去。
2. tap 成功后校验：实际命中的 rid（`how` = `rid:X` / `static_rid:X` / `span:X`）与本步 `static_rid`
   不一致 → 边真值 `control.rid_mismatch_with_plan=true` + note
   （`rid_mismatch_with_plan: 实际命中 A（how）≠ 计划 static_rid B`）+ 一条 `state.notes`，
   **不得静默记 confirmed**。

**判据.** 树的 `inbound_triggers[*]`（`from_page` / `trigger_view_id` / `trigger_label` / `span_text` /
`runtime.status` / `runtime.control.rid`）+ 计划步字段 + `find_control` 的 `how`。零业务常量。

**通用性自查.** 消歧字段都是树/计划的通用契约字段，不认任何具体控件名；
候选唯一时行为不变（回归已测）；对不上时**宁缺**（返回 None 退回 static_rid）而不是猜，
反例已测「静默取兄弟 rid」会被 `test_a5_do_tap_hits_own_control_not_sibling` 抓住。

---

#### A6 结账：`settles_capture` 单点依赖导致弹窗零基线

**病.** 「首达才结账」此前是**计划步属性**（`step.settles_capture`）。某目标唯一带
`settles_capture` 的那一步在上一棒被 `--skip-step` 掉 ⇒ 本尊此后 4 次真到达（pending_shots 里有
pre/post 帧）却全都不结账；而 `_maybe_settle_dialog_variant` 第一行又要求「本尊已结账」⇒ 变体也永远不产。
结果 **0 张基线**。同一个洞还吃掉普通页（WebView 类）。

**治.** 判据从计划步属性改成**运行时事实**——`do_tap`（到达判定通过后）与 `_settle_and_advance`
（auto 边）两处：
```
_late_settle = 本步不带 settles_capture  且  目标不是 #via= 变体  且  目标不在 ledger.settled
               且（目标是 dialog 节点  或  settle 收权四参齐全）
```
成立即用**手上已有的帧/dump**补结账：dialog 走 `_settle_dialog`（截图+dump 直接入账），
非 dialog 走 `self._ledger("settle" …)`（与 `settles_capture` 同一条路），
并记 `state.late_settled[] {node, step, from, trigger, reason, no_sweep:true}` + 一条 note。

**四条边界（新增的结账点绝不越权）.**
1. **补结账不带普查**——普查只在带 `settles_capture` 的步做（确认窗上普查会碰确定键）；
2. `#via=` 变体不走这条路（变体由 `_maybe_settle_dialog_variant` 负责，逻辑**一字未动**）；
3. settle 收权四参（`--tree`/`--device-state`/`--package`/`--launcher` 或树内 `launcher_activity`）
   不齐时**非 dialog 目标不补**——补结账是运行时新增的结账点，不该让 `walk_ledger` 的 exit 2
   把整趟拖死（判据抽成 `_settle_grant()`，与 `_ledger` 同一份，不新增第二套口径）；
4. 目标已入账 → 不补，照旧走变体路径。

**判据.** `ledger.settled` + 计划步字段 + 树的 dialog 名单（`_is_dialog_node`）+ CLI 四参。零业务常量。

**通用性自查.** 「带 `settles_capture` 的步行为一字不变」有专门回归用例
（照样 settle、照样普查、不写 `late_settled`）；变体路径有反例用例（目标已入账时仍产 `#via=` 变体）；
auto 边单独有正例。本尊结上了，变体逻辑自然生效——不需要改变体那段代码。

---

#### 自测

`cd scripts && python3 -m pytest -q _tests` → **264 passed**（本批新增 23 例，其余为既有用例）。
另做**变异校验**：把六条修复逐条改回旧行为，对应用例全部转红
（A1/A2/A2 去重/A3/A4/A5 消歧/A5 mismatch/A6 各自命中自己的用例），确认无空转断言。

### 并入：普查与回位第四轮（node_sweep / walk_back_to，2 条）
> 2026-09-10。**只改两个文件** `scripts/node_sweep.py`、`scripts/walk_back_to.py`，
> 新增单测 `scripts/_tests/test_onlyrids_promote_and_back_guard.py`（17 例）。
> 全程合成 dump + 内存假设备，不碰设备 / adb / git。
> 通用性铁律：判据只吃**命令行参数 / dump 属性 / 树与计划字段**，夹具用占位名，
> 逻辑与断言里不出现任何真实应用的页名、类名、控件名。

---

#### B1 `--only-rids` 与 `--from-plan` 互斥失效（收尾会卡死的一条）

**病.**
边失败后的补救路径是「回退单独 tap 补点」（§5 覆盖率零损失协议的唯一活路），命令是
`node_sweep.py --node <页> --from-plan --only-rids <rid>`。
`--from-plan` 会把计划边的触发键灌进 `walk_keys`，于是目标元素在元素定性链里**先**被判成
`disposition="walk"`（「该走边、普查不该点」）；随后的 `--only-rids` 只做**收窄**——把不匹配的元素降成
`not_in_only`，**从不把匹配项从 `walk` / `same_dest` 提回可点档**。
结果：元素不被 tap，run_meta 里那条 check 又结成 `deferred_same_destination`，状态原地不动。
0910 收尾实测 `inventory={"walk":1}`、`processed_check_idx=[]` —— 补点这条补救路径被**计划自己堵死**，
代理只能去掉 `--from-plan` 改传 `--sentinel-rid` 绕开。

**治.**
`--only-rids` 的语义从「过滤器」纠正为「**调用方显式点名：这一个我要你点**」：
命中项**强制提档为可点档**，优先级压过 `walk` / `same_dest` / `h5_oracle` / `nav_back` / `in_plan`。
- 有 ground 认领 → 提到 `ground`（抓证据、写 run_meta、进 `processed_check_idx`）；
- 无认领（已 `settled_by_walk` / 本就无主）→ 提到 `unclaimed`（照点，进 `behavior_ledger`）；
- 未命中集合的元素**行为不变**：仍收成 `not_in_only`（不点、留账、不进覆盖率分母）。

**不放宽的两处边界（安全面绝不因点名而松动）.**
1. `ONLY_RIDS_NO_PROMOTE = ("input_field", "destructive")` —— 这两档不点是**安全判据**
   （tap 输入框只弹键盘且污染位置 / 破坏性动作不可逆），命中也保持原档，如实结成
   `input_field_no_tap` / `skipped_destructive`，并回显在 `only_rids_kept_safe`。
2. `--exclude-rids` / `--exclude-texts` 命中的元素绝不提档。
   ★自测抓到的一处真坑：排除档 `excluded` 压在 `ground` 正上方，`walk`/`destructive`/`nav_back`
   这些更高档的元素**带着排除标记却不叫 `excluded`**——只判 `disposition == "excluded"` 会让提档
   从上面绕过排除集。判据因此改成「**是否在排除集**」（`excluded_by`），不是「归宿是否叫 excluded」。

**判据（逐条只吃哪些输入）.**

| 判据 | 输入 | 是否含应用信息 |
| --- | --- | --- |
| 是否命中定向集 | `--only-rids`（rid 短名）× dump 的 `resource-id` / 树 check 的 `android_anchor.raw_identifier` | 否 |
| 是否安全档 | 元素 `class` 含 EditText/AutoComplete；共享 `DESTRUCTIVE_RE` 词表 | 否（词表本就跨应用共用） |
| 是否被调用方排除 | `--exclude-rids` / `--exclude-texts` × dump 的 `text` / `content-desc` | 否 |

**通用性自查.**
- 提档不新增任何词表、不读任何应用常量；换应用只换命令行传进来的 rid。
- 只在 `--only-rids` 打开时生效；不开旋钮时元素定性链**一个字节都没变**
  （回归用例 `test_only_rids_fields_are_contract_defaults_when_knob_off` 钉住）。
- 同构兄弟去重（`homogeneous_sibling`）**故意不绕过**：它只作用于 `unclaimed`，带 ground 认领的
  提档项进的是 `ground`，永远不会被去重吞掉 → 不会重新形成死锁。

**新增契约字段（恒在，不开旋钮就是两个空表，调用方免判存在）.**
- `only_rids_promoted`: `[{rid, text, from, to}]` —— 非空 = 命中项本来会被计划判成「不点」，已按点名提档 tap。
- `only_rids_kept_safe`: `[{rid, text, kept}]` —— 非空 = 命中项**故意没点**
  （`kept` ∈ `input_field` / `destructive` / `excluded_by_caller`），调用方自己决定怎么办。
- `behavior_ledger` 条目加 `only_rids_promoted_from`（提档留痕，判读可复核）。
manifest 与 stdout 双通道同时回显。

---

#### B2 回位脚本过冲把应用弹出去

**病.**
`walk_back_to.py` 命中目标宿主后**没有停**，继续按计数把 `--steps` 按完；栈被按穿，露出同一模拟器上
另一个应用的任务栈，目标包 activity 栈清零，只能冷启回来（本轮实测 2 次逃逸）。
两个成因叠在一起：
1. 循环里只判「计数够不够 / 是不是根 / 有没有进展」，**从不判「是不是已经到家了」**——
   `--expect-host` 只在计数归零后当**事后校验**用；调用方把弹窗/tab 误算进 `--steps`（常态）即过冲。
2. 根白名单只有一个信源 `derived_config.main_root / launcher`，盖不住真实栈底。

**治.**
1. **每按之后立刻判位**（不等下一轮循环头）：命中 `--expect-host` → 当场返回
   `stop_reason=host_reached`、`reached_host=true`；进循环前先判一次 → `already_at_host`（0 按返回）。
   `remaining_steps > 0` 是**故意的**，输出里写明「调用方报的 --steps 比真实下沉深度大，多按即过冲」。
   同一处顺带把 `pkg_escape` / `probe_dead` 也提前到按键之后判——按穿的那一下当场停，不再连按到上限。
2. **根 activity 上零 BACK**：撞到根 → `stop_reason=root_guard` + `at_root=true` +
   note「已在根、无法继续回退」，交调用方处置（前向 re-tap / 按熔断协议冷启重放前缀），绝不再按。
3. 根白名单扩到**三个信源取并集**，全部只吃树/计划字段：

| 信源 | 字段 | 理由 |
| --- | --- | --- |
| ① 树 | `navigation_contract.relationship_kind == "activity_root"` | 结构真值，换应用自动跟着变 |
| ② 计划 | `walks[].steps[]` 中 `action=="coldstart"` 的 `to`（节点 id，树里认得就再收其 `fq_class` 短名） | 冷启起点必然是栈底 |
| ③ 计划 | `derived_config.main_root` / `launcher` | 原有信源，保留 |

   取并集、宁枉勿纵：误收一个 → 少按一下（调用方 whereami 复核后自己补）；漏收 → 把 app 弹出去（不可逆）。
   每个根的来源回显在输出的 `roots` / `roots_why`，判读可复核。
   三个信源都给不出根仍然**拒跑**（`no_roots_config`, exit 2）——没有白名单就没有过冲保护，语义不变。

**判据（逐条只吃哪些输入）.**

| 判据 | 输入 | 是否含应用信息 |
| --- | --- | --- |
| 到没到目标 | `--expect-host`（调用方给的 activity 短名）× `dumpsys mResumedActivity` | 否 |
| 是不是根 | 树 `relationship_kind` / 计划 `coldstart.to` / `derived_config` | 否 |
| 是不是逃了 | `--package` × dumpsys 的包名 | 否 |

**顺带（为了能单测）.**
`SERIAL` 由 import 期常量改成惰性 `serial()`：原实现在**导入的一瞬**就跑 `adb devices`，
多台设备在线会直接 `sys.exit(2)`——脚本连 `import` 都做不到，且「配置错」也得先有设备才报得出来。
改后 `no_roots_config` 这类配置错在不碰设备的情况下就能报出。对 CLI 行为无影响（`main()` 立刻会用到）。

**新增/变化的输出字段.**
- 新 `stop_reason`：`already_at_host` / `host_reached`（两者 `reached_host=true`）。
- `root_guard` 增 `at_root: true` 与结构化 note；所有出口增 `roots` / `roots_why`。
- 新参数 `--tree`（可选）：缺省从 `walk_plan.json` 的 `tree` 字段推（相对 cwd 或 `--dir` 的各级祖先）。

**行为变化需知会调用方（1 条）.**
已经站在 `--expect-host` 上却仍传 `--steps N>0` 时，本原语现在返回 `already_at_host` 且**一下都不按**。
按 §4 分段协议这是正确的（弹窗的反向是「调用方在调本原语之前自己点取消」，不进 `--steps`）；
此前那种「顺手把弹窗按掉」的副作用不再发生，输出会明说剩余计数没按。

---

#### 测试

`scripts/_tests/test_onlyrids_promote_and_back_guard.py`，**17 例**：

- B1（7 例）：`--from-plan --only-rids` 死锁原样复现（walk + same_dest 两档同时提档并真 tap、
  run_meta 结成 ok、`processed_check_idx` 非空）；nav_back / in_plan / h5_oracle 也提档；
  ★**反例**：destructive / input_field 被点名也不提档、一下都不点、如实结成安全档状态且
  `processed_check_idx == []`；`--exclude-rids`（元素同时被 walk 认领的那种）与 `--exclude-texts`
  两路都挡得住提档；无活 check 认领时提到 unclaimed 照点；不开旋钮时字段默认值与旧行为不变。
- B2（10 例）：★**过冲原样复现**（`--steps 3` 而真实只沉 1 层 → 1 按即停、`escaped=False`）；
  已在目标宿主 → 0 按；★**根 activity 上零 BACK**（只用树 `activity_root` 一个信源，无计划文件）；
  只用计划 `coldstart.to` 一个信源同样零 BACK；中途落到根当场停；IME 那一下不计数也不过冲；
  不传 `--expect-host` 的纯计数语义回归；白名单没盖住时按穿的那一下当场判 `pkg_escape` 只按一次；
  三信源全空拒跑 exit 2；`--tree` 缺省时从计划字段推路径。

全量：`cd scripts && python3 -m pytest -q _tests`
- 本批单独落地时 → **217 passed**（= 基线 200 + 本批 17），零回归。
- 第四轮其余代理的批次也落地后，最终一次全量 → **240 passed**（全绿）。

> 记两笔中途现象，都不是本批引起的（本批两文件与它们无调用关系：`walk_exec` / `next_walk` 既不
> import `node_sweep` 也不 import `walk_back_to`，只把后者拼成命令字符串）：
> ① 一次 5 failed，全在 `test_walk_exec_{escalation,rules}.py`，统一停在 `walk_exec.py:813`
>    当时新加的 `settle 收权四参不齐` 硬闸（`SystemExit: 2`）；
> ② 一次 1 failed，`test_next_walk.py`，`next_walk.py:398` `NameError: name 'judged' is not defined`。
> 两者都是**别的代理**同一时刻在改自己文件的中间态，对方落地后自行消失。

---

#### 未做项（本批**没碰**，留给拍板）

1. **补点趟对「已 settled 的 check」不重新收权**：命中 rid 若对应的 check 已在
   `walked_grounding.json` 里结过账（例如 `same_dest` 继承写过），本轮只 tap、留 `behavior_ledger`，
   **不改写**该 check 的 `settled_by_walk` 状态。要不要允许定向补点「翻案」，牵涉 idx 感知的已结账
   语义，属另一条口径，未动。
2. **`--only-rids` 未接管同构兄弟去重**：命中 rid 若有 ≥3 个同构项，仍只点代表。判定是「这是既有的
   覆盖率语义，不属本次死锁」，故意保留。
3. **`walk_exec` 侧的调用串未同步**：`walk_exec.py:1113~` 拼的 `walk_back_to` 命令仍是
   `--steps 1 --package --dir [--expect-host]`，没有传 `--tree`（缺省能从计划字段推出来，不影响正确性），
   也没有消费新的 `at_root` / `already_at_host`。该文件本轮归另一代理，未动。
4. **文档未同步**：`references/phase2-edge-walk.md` §4 第 5 条的返回语义表、
   `references/phase2-chunk-dispatch-template.md` 的 back_failed 命令行仍是旧版
   （少 `already_at_host` / `host_reached` / `at_root` 三个出口）。按「只改两个文件」约束未动。

### 并入：判读债链路与跨趟隔离（walk_ledger / finalize / next_walk / place_baselines，2 条）
> 2026-09-10。**只改四个文件** `scripts/walk_finalize.sh`、`scripts/next_walk.py`、
> `scripts/walk_ledger.py`、`scripts/walk_place_baselines.py`，新增单测
> `scripts/_tests/test_binding_debt_and_bytrip.py`（25 例）。
> 全程合成产物 + 假采集内核（`walk_ledger.subprocess` 整体替名，不污染测试自己起的子进程），
> 不碰设备 / adb / git。
> 通用性铁律：判据只吃**账本字段 / 计划字段 / 池内条目字段 / 文件系统事实**；夹具一律
> `Root` / `SomeListFragment` / `trip_x_out` / `trip_y_in` 这类占位名，逻辑与断言里不出现
> 任何真实应用的页名、类名、trip 名。两条病灶都来自 2026-09-10 真机回归。

---

#### C1 判读债链路三处断点：债从产生到收尾结束没有任何机制报过

**病.** 采集内核 `exit 16` = 「证据已拍并入池、身份绑定待判」，`walk_ledger settle` 已经把它写进
`pending_bindings.json`（0910 实例：`RecommendListFragment`，`classified=uncertain`，
`why=expected 弱命中（共享id/宿主漂移）——需看图判读`，png + dump 两个证据文件都在盘）。
可是这笔债一路无人接：

1. **收尾不查池**：2.6 判读债闸的实现写在 `walk_ledger status` 里，而 `walk_finalize.sh`
   **从未调用过 walk_ledger**（实测 grep 计数 0）⇒ 两个 trip 的 finalize 全绿收工。
2. **驱动不排它**：`next_walk` 算判读任务只 glob `grounding/*/run_meta.json`，零处引用
   `pending_bindings` ⇒ 五份判读派发单的作用域清单里都没有这个节点，债永远没人判。
3. **归因归错**：节点因此留在 unreached，被写成 `nav_unreachable`（技术失败），
   而它其实是「证据已采、绑定待判」——结债手段现成且零设备。
   一句话：**挂债不建闸 = 机械收尾降级成自觉**，与「三账没反哺」是同一个病。

**治.**

- **债的三态**（`walk_ledger.binding_debt`，shell 闸 / 驱动 / 收尾账**共用这一个函数**，禁两处各写一套）：
  未判（无 `verdict`）→ 已判待结（`verdict` 已回写且**显式** `applied=False`）→ 已结（`applied=True`）。
- **闸**（`walk_finalize.sh` 新增 §2.6，位置在 2.5 批判定闸之后、§3 树反哺之前）：两态都**真拦**
  （`exit 20`，与 needs_retap 闸同规格），报文列节点(trip) + 两条结债路径；显式豁免开关
  `--accept-binding-debt`，豁免必留痕：树 `_phase_markers.<walk_id>.binding_debt`
  记 `count/unjudged/unapplied/source/note`（note 明写「别把它们当不可达」）。
- **驱动**（`next_walk.py`）：`binding_scope()` 把未判条目并进判读作用域，与 run_meta 观测并列——
  `dispatch_judge` / `dispatch_walk.also_dispatch_judge` 都带 `binding_nodes`；判读 prompt 追加
  「判读债（绑定待判，零设备）」一节，逐条给 `pending_shot` / `pending_dump` / 分类器理由 /
  当时 activity + 四条判定规则（看不出就 `reject`，**不许猜**：绑错图 = 下游拿错基线做全量对比）。
  **判读模板 `references/phase2-judge-template.md` 一字未改**（它是共享件；绑定判读是「看图定身份」，
  与 check 判定不同空间）——追加段在 `next_walk._binding_section()` 里拼。
- **合并**（`--merge-judge`）：`kind=="binding"`（或带合法 verdict 且无 `check_name`）的条目分流回
  `pending_bindings.json` 写 `verdict/judged_by/note/applied=False/judged_at`，
  **不进 `grounding_results` 的 check 空间**；幂等（已判条目不再改判，重复合并 `judged=0/skipped=1`）。
  真结债仍归 `walk_ledger bind-from-evidence`（拷图入 `shots/` + 记账这件有后果的事收权不旁落）。
- **新动作 `settle_binding_debt`**（已写进 `next_walk.py` 头部封闭动作集）：已判待结的债 → 逐条给出
  `walk_ledger --dir $EW bind-from-evidence --node X --tree T` 命令，`--apply` 真跑。
  ★ 结完**撤掉该 trip 的 `finalize_<trip>.ok`**：`finalized()` 只比行走产物 mtime、看不见账本/shots
  的变化，不撤标记的话新绑定的基线永远等不到下一次 finalize 落位（驱动会直接判 done）。
  动作顺序 = 判读 → 结债 → 归因 → finalize（结债会改 settled，必须排在归因之前）。
- **`bind-from-evidence` 收「已判待结」**：旧实现只找「无 verdict」条目，判读结论一旦回写就报
  「无未判 pending 条目」把自己锁死。现在开着的债 = 未判 ∪ 已判待结；缺 `--verdict` 时**先认条目里
  已回写的结论**，没有才离线重分类。结清写 `applied=True/applied_at`。
- **未达口径**：`unreached(split=True)` → (真未达, 绑定待判, 绑定已判)；`confirm_overrides` / `done`
  分别单列 `unreached_binding_pending`（债还开着，证据已采 → 别归因成 nav_unreachable）与
  `unreached_binding_judged`（债结过了仍未达，reject/new_node → 照未达归因，但别再派人重走）。
  `draft_overrides` 给前者**预填 `reason: binding_pending`** + 结债命令，给后者附 `_binding_judged` 素材。
- **BLOCKED 单**（`walk_place_baselines.py`）：还开着债的未达节点默认 `reason: binding_pending`
  （不再是 `nav_unreachable`），单里写明「证据已采、绑定待判，不是不可达」+ 零设备结债命令；
  `--reason-overrides` 仍然优先。trip 错配自愈队列不再对这类节点触发（它不是分派错，是没判）。

- **池读不出来也是红**：`load_pending_bindings(path, strict=True)`（闸与收尾账用）遇到「文件在、
  parse 不了」直接抛 → 闸 `exit 20` 当场拦；驱动用 `strict=False`（建议者不是闸，不该被一个坏文件崩掉，
  真值仍由闸兜底）。**「读不出来」当成「没有债」就是静默改绿**。

**判据.** 全是账面事实，不含语义猜测：条目有没有 `verdict`、有没有显式 `applied=False`、
节点在不在 `ledger.settled`、`pending_shot` 文件在不在盘。闸的判据函数与驱动、收尾账同一份。

**通用性自查.** 零应用常量：节点名/trip 名/包名一个不进代码，全部来自 `pending_bindings` 条目与
`walk_plan.targets`。老产物行为不变：没有 `pending_bindings.json` → 闸打印「本轮没挂过判读债 ✓」放行；
老条目没有 `applied` 键 → 只按 `verdict` 有无判，一律不算债（`test_legacy_entry_without_applied_key_is_not_debt`）。
新 reason `binding_pending` 不在验收闸的合法白名单里（`^reason: data_precondition_missing|structurally_unreachable`），
仍然算红——**这是故意的**：债没结就是没结，只是红得准确了。

---

#### C2 同节点跨 trip 复访：采集产物被整份覆写，前一 trip 的基线被写成后一 trip 的画面

**病.** `WorksFragment` 双 trip 分派。walk_0（登出态）已结账，`shots/WorksFragment.png|.android.xml`
是空态图；walk_1（登录态，11:02）对同一节点普查时把这两个文件**整份覆写**成有 4 条作品的登录态画面。
落位发生在覆写之后 ⇒ trip_1 的基线被写成登录态内容（已人工删除并出单
`spec/fix/baseline-blocked/BLOCKED_baseline_WorksFragment_trip_1_logged_out.md`）。
登出态绑定图永久丢失，只剩早拍帧（按铁律不能当基线）。
顺带第二处静默丢失：`ledger.settled` 按节点只存一份，复访后连「它在前一 trip 结过账」都查不到。

**治.** 绑定产物按 trip 隔离，既有消费者一个不动：

- `walk_ledger settle` **落盘前**：若账本里该节点已有**不同 trip** 的结账记录且 `shots/<node>.*` 存在 →
  `archive_shots_for_trip()` 把现存的一对**复制**进 `shots/_bytrip/<旧trip>/`（复制不搬走：采集若失败，
  `shots/` 原样留着，状态不变，可重跑），并把**上一 trip 的结账记录**原样留进
  `ledger.settled_by_trip[<旧trip>][<node>]`，其 `capture_meta.shots_archived` 指向归档路径；
  新记录带 `trip` 与 `archived_prior`。
  旧 trip 从哪来：新记录直接读 `trip`，老记录退回 `capture_meta.trip_id`（采集内核一直在写）；
  两者都取不到 → **不归档**（判不出「跨 trip」就不动，宁可保持旧行为）。
- `walk_place_baselines` 落位：`pick()` **本 trip 的归档优先**，没有归档才回落 `shots/`；
  两代命名（原名 + `.android.xml` / 安全名 + `.xml`）在两个目录里都认。输出加 `placed_from_archive`。
- `walk_ledger.finalize_account` 的 capture 账同步改成 `trip_shot_sources()`（归档优先）。
  **不改这里会把真修复变成假红**：落位的是归档（mtime 早），`shots/` 里那份是复访图（mtime 晚），
  旧对账会判「新图被旧图挡住 = stale」。
- 第三趟自然衔接：trip3 结账时把 trip2 留在 `shots/` 的那份归档进 `_bytrip/<trip2>/`，链式成立。

**判据.** 账本里该节点上一条结账记录的 trip ≠ 本次 `--trip`，且 `shots/` 里确有一对文件。
不看图、不看内容、不比像素。

**通用性自查.** 零应用常量；幂等（同名覆写=同一份，重跑无副作用）；老项目没有 `_bytrip/` 目录时
`pick()` 第一轮全落空、行为与改前逐字相同（`test_place_baselines_legacy_project_unchanged`）；
同 trip 复访（重试）不归档（`test_same_trip_resettle_does_not_archive`）；首次结账不归档。
`_bytrip` 是 `shots/` 的子目录，`glob("shots/*.png")` 不递归 ⇒ 不会被重复计数。

---

#### C3（顺手）落位后仍留着 BLOCKED 单 → 报出来，不自动删

**病.** 结债 / 补走之后节点落位了，往轮给它开的 BLOCKED 单还在（0910 真机干跑复现：
`RecommendListFragment` 结债落位后，`BLOCKED_baseline_RecommendListFragment_trip_2…md` 仍在盘）。
验收面上一个页面既有基线又有 BLOCKED 单。

**治.** `walk_place_baselines` 输出新增 `stale_blocked`（并 stderr 提示）：本 trip 里「已落位 + 单还在」
的清单。**不自动删**——单子可能带人工诊断，删人写的东西必须人点头。

---

#### 测试与实测

- **单测当场揪出一个真 bug**（新写的闸文案里 `$PB_JSON）` 紧贴全角右括号 → bash 3.2 把「）」的首字节
  当成变量名的一部分、`set -u` 崩在闸里）：改成 `${PB_JSON}`，并写了个全文件扫描确认
  `walk_finalize.sh` 里再无「裸 `$VAR` 紧跟非 ASCII 字符」。
- 新增 `scripts/_tests/test_binding_debt_and_bytrip.py` **25 例**：
  判据三态 / 老条目不算债 / 闸对未判·已判待结都报红且真拦 / 无债与无文件放行 /
  豁免开关留痕（真跑 finalize 验 `_phase_markers`）/ 驱动把债并进判读作用域（含 prompt 里有证据路径）/
  行走在派时债走 `also_dispatch_judge` / 合并分流不污染 check 空间且幂等 / check 行仍照走 /
  结债后撤 `.ok` 标记 / `bind-from-evidence` 收已判条目 / 未达三分 / 草稿预填 binding_pending /
  confirm_overrides 单列已判 / BLOCKED 单 reason 正确且无债时逐字不变 /
  跨 trip 归档 · 同 trip 不归档 · 首次不归档 / 落位优先本 trip 归档 · 老项目行为不变 /
  归档落位后收尾账不误报 stale / 池损坏时闸真拦（shell + finalize_account 两侧都验）。
- 全量 `cd scripts && python3 -m pytest -q _tests` = **265 passed**（本批开工时基线 200，
  期间 A/B 批代理各自加了单测；本批 25 例全绿，零回归）。
- **真机产物只读副本干跑**（`AIPPT_0910r3_walk` 整份拷进 scratchpad，池内绝对路径改指副本，
  真产物一个字节没动）：
  1. `walk_finalize.sh --dry-run` → **exit 20 停在 2.6 闸**，点名
     `RecommendListFragment(trip_2_logged_in_vip)`；改前这一趟是全绿收工的。
  2. `next_walk.py` → `dispatch_judge`，`binding_nodes=["RecommendListFragment"]`，
     prompt 里带两条真实证据路径。
  3. 模拟判读返回 `verdict=bind_as` → `--merge-judge` 只改池不改 `grounding_results` →
     驱动给 `settle_binding_debt` → `--apply` 真跑 `bind-from-evidence`：
     节点入账（`identity_by=judge_merge`）、`shots/RecommendListFragment.{png,android.xml}` 落盘、
     `finalize_trip_2….ok` 撤销。
  4. `walk_place_baselines --trip trip_2…` → `placed=["RecommendListFragment"]`，
     baseline 落位，并报出那张 `stale_blocked` 的旧 BLOCKED 单。
  结论：修完后 `RecommendListFragment` 不再是 `nav_unreachable` 的黑洞，而是
  「闸拦住 → 判读派单 → 结论回写 → 结债入账 → 基线落位」的闭环。

#### 未做 / 留给别人

- C2 是**预防性**修复：`WorksFragment` 登出态那张图在 0910 就已被覆写掉，副本里无从复原，
  只能靠下一趟 pm_clear 首启链重拍（真机验证要等下一轮真跑）。
- 干跑里 trip_1 的 finalize 仍 `exit 20`，原因是「14 个节点的新基线被『已有禁覆盖』挡住」——
  这是对**已完成的 finalize 再跑一次**的固有行为（副本里 trip_1 基线早已就位），与本批无关。
- `check_android_screenshot.sh`（验收闸）没纳入本批文件范围：新 reason `binding_pending` 落在它的
  「非法 reason = 技术失败」分支里，行为正确但文案上仍归在 nav_unreachable 一类的统计里，
  若要单列需改那个脚本。
- `stale_blocked` 只报不删；要不要在结债成功后自动删单，等拍板。

---

## 2026-09-10（第三轮：0910 真机回归 41 次熔断归因 → 目标逻辑落地；主会话部分）
0910 账：墙钟 245.5 min（行走核心 118 vs 0909 约 200），41 次熔断均 59 s（0909 均 198 s），0909 成因零复发；新层=创作链栈语义/首启门/默认子 tab/协议勾选/mock 无响应控件。
- 执行器 `renav` 动作落地（计划器 B1 改发的回位步）：`plan_path_to`/`replay_type_steps` 纯函数 + `do_renav`（已在位免动作 → 沿到达路径定层重放 → 重新拉起兜底 → 熔断 position_mismatch）；
  `precompute_positions/simulate_stack/subtree_end` 把 renav 当回位步；主循环派发。
- `do_back` 产 BACK 观测记录（新契约 `action:"back"` + landed/back_dialog），失败时落点走 `_landing_strong` 强判、确认窗身份走 `_open_dialogs`；
  `_fill_back`/`walk_inherit`/`walk_place_baselines`/`walk_timing`/`walk_finalize.sh` reach_path/`next_walk.draft_overrides` 一律按 `action` 跳过该类记录。
- 驱动 `next_walk.py`：`run_env.md` 的 `trip_build_scenario:` 显式建态场景（无登录应用的订阅/造数）；树无登录/会员类前置且未指定 → 免建态；
  「已建态」只认带 scenario 的 `trip_built:*` 事件。`_tests/test_next_walk.py` 15 例。
- 文档：`phase2-edge-walk.md` §4.z 第三轮契约；派发模板退出码补 `5`；`walk_finalize.sh` 5.8 文案改单趟链趟。
- 测试：`_tests/test_walk_exec_renav.py` 11 例；全量 `python3 -m pytest -q _tests` = **199 passed**；ART 14 / toolkit 23 passed。
- 下面三节是子代理产出的待并条目原文（执行器 r3 / node_sweep r3 / 计划器与写回 r3）。

### 并入：执行器第三轮（walk_exec r3）
> 待并入 `CHANGELOG.md`。本轮**只改** `scripts/walk_exec.py`，新增 `scripts/_tests/test_walk_exec_round3.py`（28 例）。
> 通用性铁律不变：逻辑零 app 硬编码，判据只吃 **计划字段 / 树字段 / dump 属性 / dumpsys / 哨兵表 / UI_WORDS 词表**；
> 词表跨项目通用且可被 `$EW/ui_words.json` 整表覆盖。
> `node_sweep.py` 侧的 `--chain-mode / --exclude-rids / --exclude-texts / --only-rids` 由另一代理实现，
> 本轮按契约调用；单测里 sweep 子进程一律 monkeypatch，不碰 adb / 模拟器。

#### A. 首启链页当场普查（取消收尾链趟的前提）

- `_maybe_sweep`：`chain_protected` 趟**不再整趟跳过普查**。旧行为（2026-08-14 事故修）是欠账记
  `state.sweep_skipped_chain`、交收尾链趟重跑整条首启链——实测比当场普查贵一个数量级。
  现在先结账（调用方已结）再当场普查，靠 `--chain-mode`（不做 BACK 回位）+ 排除集保住一次性链。
- 新增 `_chain_exclusions(node) -> (rids, texts)`：
  - `--exclude-rids` = 树该节点的 `wizard_exit_controls`（兼容 `{"view_id"|"resource_id"|"rid"}` dict 与裸串）
    ∪ `navigation_contract.exit_action_to_next.resource_id` ∪ 计划里**本节点出边**的 `static_rid`；取不到即空集。
  - `--exclude-texts` = `UI_WORDS["wizard_advance_texts"]`（**新增词表键**，默认
    `跳过/继续/下一步/开始/同意/不同意/同意并继续/我知道了/立即体验 + Skip/Next/Continue/Start/Agree/Disagree/Got it`，可覆盖）。
- 新增 `_sweep_manifest(node, stdout)`：优先读 `<blackbox_out>/<node>/<node>__manifest.json`，
  缺文件退回解析 stdout 末行 JSON；任何异常返回 `{}`（读不到就当没有，绝不带崩行走）。
- 新增 `_absorb_chain_advance(node, step, man)`：manifest `chain_advanced:true` 时机械同步位置——
  落点 = `lib_landing` 现场强投票优先、退 `advanced_to.landing_node`；在计划里从当前步往后找第一个
  `from == 落点` 的步 j，`steps[idx+1:j]` 记 `state.skipped`，其中带 `settles_capture` 且目标未结账的记
  `state.capture_debt`（形态必须是**页 id 列表**——`plan_chain_sweep.chain_debt` 直接 `set()` 它排收尾趟，
  塞 dict 会当场 unhashable；明细留在 `state.chain_advances`），`manifest.unswept` 记 `state.sweep_debt[node]`
  （形态与 `plan_chain_sweep` 既有契约一致），
  `position` 同步、`_jump_to=j` 续走，**不熔断**。落点解析不出 / 计划里没有该落点的落脚步 → 走原熔断
  （reason `chain_advanced_unresolved`，带完整 options 菜单）。
- `_maybe_sweep` 返回 `"chain_advanced"` 或 `None`；`do_tap` 据此跳过 `_post_sweep_verify`（位置已同步）。
- `state.chain_swept` 记每次链页普查（节点 / 排除集），`sweep_ran[-1].chain_mode=true`。

#### B. 普查发现当场入账

- 新增 `_ingest_discoveries(node, step, man, device_ok=True)`：manifest `discoveries[]` 里
  `landing_node` 是树内节点且未结账的：
  - **dialog 类** → 用该发现记录里的 `screenshot` / `dump` / `landing_ability` 调 `settle_dialog_direct` 结账（零设备动作）；
  - **activity/fragment 类** → 按 `trigger_center` 重点一次进入 → `_probe_at` 验到达 → `_ledger settle` →
    `_recover_to` 回起点（回不到走熔断菜单）；单次普查最多 `DISCOVERY_REENTRY_MAX=3` 个，防「入账」退化成第二次遍历。
  - 两类都 append 一条 `discovered:true` 的 confirmed 边（`control.matched_by="sweep_discovery"`）给 writeback。
  - `--no-blackbox` 时整体不做（没有 manifest）；链被推进时只做 dialog 类（`device_ok=False`）。
- 新增 `_recover_to(node, step, why)`：探 →（取消控件 | BACK）×3 → 仍回不去即熔断（带菜单）。

#### C. 边失败当场补点（覆盖零损失协议机械化）

- 新增 `_repair_same_dest_check(step, why)` + `_sweep_run_meta(node)` + `_back_ladder(node)`：
  tap 边落 `not_reproduced` 后，若起点 `grounding/<node>/run_meta.json` 里有
  `status == "deferred_same_destination"` 且 `anchor_rid`（兼容旧字段名 `rid`，按 `/` 后缀比）等于本步
  `static_rid` / `item_rid` / 反哺 rid 的 check → 立刻对起点调 `node_sweep --only-rids <rid>`（**不带** chain-mode）
  补点一次，结果由 node_sweep 自己写回 run_meta；记 `state.same_dest_repairs` + notes。`--no-grounding` 时不做。
- 接线点（三条 not_reproduced 机械收边路径）：`_suspect_fastpath`、`_arrival_landing_recover` 的
  `no_effect` 与 `landed_elsewhere` 两支。

#### D. 熔断菜单修正

- 新增 `_subtree_span(step)`（非 tap 步恒为 1）。
- ① `skip` / `skip_landed` 类选项的 `effect` 一律追加「；跳过整棵子树，共 N 步」（`add()` 里按 key 前缀统一加，
  原文案里重复的「并跳过整棵子树」已去重）。
- ② 子树 `N > 5` 时 `options[0]` 换成续走类，`skip` 类整体退到菜单末尾：
  落点强命中且 ≠ 期望 → `--mark-step-done <n> --assume-at <landing>`（effect 注明「边记 confirmed 但**未直接观测**，
  注记 transient/landed_elsewhere」）；否则 → `--resume --assume-at <landing|expect|from>`。
- ③ `manual_then_mark_done`（`input_failed` / `input_target_not_found` / `gate_pass_unknown`）的 `--assume-at`
  改取 `diag.landing_node`（强命中时），不再取计划步的 `to`。

#### E. 熔断预算按代理算

- 新增 `_agent_start_ts()`（`.driver_in_flight.json` 的 `ts`，墙钟预算与熔断预算共用同一个界）与
  `_escalations_scope()`：只数 `state.llm_gaps` 里 `escalated_at >= ts` 的条目；**无锁**（非驱动派发）沿用 walk 累计。
- `escalate` 的 `handoff_due` / `escalations_so_far` 改用该口径；熔断包新增
  `escalations_scope`（`agent|walk`）与 `escalations_walk_total`（整趟累计，只作观测）。
- `_wall_budget` 改为复用 `_agent_start_ts`，行为不变。

#### F. 裸重跑保护 + `--restart`

- 新增 `run()` 开头的 `_refuse_bare_rerun()`：本 walk 已有状态（`done_steps` 非空或 `escalations>0`）
  而本次调用不带任何续走参数（`--resume/--mark-step-done/--skip-step/--assume-at`）→
  打印 `{"status":"refused","reason":"state_exists_without_resume","hint":"续走请带 --resume；确要重走请带 --restart"}`
  并 **exit 5**（新退出码，已写进模块 docstring）。状态文件原封不动。
- 新增 `--restart`：`__init__` 里把旧状态归档成 `walk_exec_state.<walk_id>.restart.<ts>.json`，
  `_load_state` 给全新状态 → `done_steps` / `skipped` / `escalations` 一并归零（0910 实测 `skipped` 列表重跑时粘住），
  并在 `state.notes` 留痕。`main()` 里 `--restart` 永远压过 `--skip-step/--assume-at/--mark-step-done` 的隐含 resume。

#### G. 已知崩溃修复

- `_maybe_sweep` 逃逸自愈分支此前写 `self.state.setdefault("blackbox_ran", [])[-1]["escaped_app"]=True`，
  而普查记账追加在 `sweep_ran` → `blackbox_ran` 恒为空列表，**自愈第一行就 IndexError**（0910 实爆），
  逃逸自愈从未真正执行过。现统一到 `sweep_ran`（空列表也不炸）。新增两例回归：root 节点逃逸后自愈不抛、
  深层节点重放失败仍熔断。

#### H. type 步的子状态前置

- 新增模块函数 `find_subtab_candidates(dump, limit=3)`：同一父节点下存在 `selected="true"` 兄弟的
  `selected="false"` 可点元素（= 子 tab 组的未选中项），只吃 dump 属性，解析失败返回 `[]`。
- 新增 `_find_input_target(step, vid)`：`do_type` 找不到输入目标时逐个 tap 子 tab 候选（最多 3 个）后重找，
  命中即续走并记 notes `input_target_found_after_subtab_switch`；仍找不到才熔断
  （`input_target_not_found` 的 detail 里注明「已试过切子 tab」）。

#### 其他（本轮顺带）

- `run()` 的整段跳步（`_jump_to`）从「只在 tap 分支消费」改为**所有 action 之后统一消费**——
  此前 `coldstart` / `verify` 里的普查若推进了链，`_jump_to` 设了也白设。行为对 tap 步完全等价。

#### 新字段与参数契约（回显）

| 位置 | 键 | 形态 |
|---|---|---|
| CLI | `--restart` | flag；exit 5 的唯一出口 |
| 退出码 | `5` | `state_exists_without_resume` |
| `UI_WORDS` | `wizard_advance_texts` | 字符串数组，可 `$EW/ui_words.json` 覆盖 |
| node_sweep 入参 | `--chain-mode` / `--exclude-rids a,b` / `--exclude-texts t1,t2` / `--only-rids a,b` | 按另一代理的契约调用 |
| manifest 读 | `chain_advanced:bool`、`advanced_to:{activity,landing_node}`、`unswept:[{rid,text,center}]`、`discoveries[].{landing_node,trigger_center,trigger_text,trigger_resource_id,screenshot,dump,landing_ability}` | 只读不写 |
| run_meta 读 | `checks[].{status:"deferred_same_destination", anchor_rid\|rid, idx}` | 只读不写 |
| `state` 新增 | `capture_debt[<page_id>]`（下游 `plan_chain_sweep` 既有契约）、`sweep_debt{node:[…]}`、`chain_advances[]`、`chain_swept[]`、`discoveries_settled[]`、`same_dest_repairs[]` | 纯记账 |
| 熔断包新增 | `escalations_scope`、`escalations_walk_total`；options 新 key `mark_done_assume` / `resume_assume` | — |
| 边真值新增 | `discovered:true` + `control.matched_by="sweep_discovery"`（B） | writeback 按既有 discovered 边消费 |
| 新熔断 reason | `chain_advanced_unresolved` | 带完整 options 菜单 |

#### 测试

`scripts/_tests/test_walk_exec_round3.py` 28 例（A 6 / B 4 / C 4 / D 4 / E 2 / F 3 / G 2 / H 3）；
全量 `python3 -m pytest -q _tests` = **166 passed**（原 138 例零回归）。

### 并入：node_sweep 第三轮（三旋钮）
> 子代理产出的**待并条目**，不动共享 `CHANGELOG.md`（并入时插到 2026-09-10 节下）。
> 改动只落 `scripts/node_sweep.py`；测试追加进已有的 `scripts/_tests/test_node_sweep_rules.py`。
> **未 commit、未 push、未跑设备**（全部合成 dump + 内存假设备）。

#### 2026-09-10 · node_sweep：`--exclude-rids/--exclude-texts` / `--chain-mode` / `--only-rids`

来源：0910 真机回归后用户拍板的一批**通用**改进（执行器另一代理按同一契约调用）。
三条铁律照旧：判据只吃**命令行参数 + dump 属性 + 树/计划字段**，零具体应用的页名/控件 id/文案/包名。

##### 1. 调用方排除集 `--exclude-rids` / `--exclude-texts`

- 判据：`--exclude-rids` 按 **rid 短名精确**（传全名 `pkg:id/x` 也认，取 `/` 后一段）；
  `--exclude-texts` 按 **text 或 content-desc 精确**（不做子串/模糊，避免误伤）。
- 命中元素**不 tap**，入账 `outcome=excluded_by_caller` + `excluded_by: rid|text`；
  **计入 inventory**（`sweep_inventory_dispositions.excluded`），**不进覆盖率分母**
  （不进 `order` → `budget` 不含它们，与 destructive/in_plan 同一机制）。
- 优先级：**压在 `ground` 正上方**，`input_field > destructive > walk > same_dest > h5_oracle >
  nav_back > in_plan > **excluded** > ground > unclaimed`。理由：上面每一档本来就「不点」，
  真正会被点的只有 `ground/unclaimed` 两档 → 排除集只需盖住这两档。于是
  **`nav_back` 判据保持原样**、`destructive` 的 `unplanned_destructive` 安全信号不被排除清单静默吞掉、
  `walk/same_dest` 的继承结算照旧；`excluded` 计数正好 = 「从覆盖率分母里拿掉的元素数」。
- 被排除元素若认领了 check → run_meta 里如实记 `status=excluded_by_caller`
  （维持 `checks_total == len(checks)` 不变量，不静默丢 check）。

##### 2. `--chain-mode`：首启链页当场普查，**tap 推进即停**

- **第二个合法入口**：链页或门（`first_launch_onboarding` / `wizard_step` / `tree_chain` /
  `name_prefix` 四信号或门，exit 21）对 `--chain-mode` 放行，与 `--allow-chain-sweep` 并列；
  放行事实记 `manifest.chain_mode:true`（账面可复核）。老入口 `--allow-chain-sweep` 行为一字未动。
- 元素循环里**每次 tap 后先判落点**，三选一即判「推进」（全部只吃运行时事实）：
  ① `land_act != parent_act` ② 包名变了 ③ 结构签名变了**且**哨兵不在位（`on_page` 口径，
  同 activity 内换页的引导页 ViewPager 走这条）。
- 判为推进 → **不做任何 BACK/回位**（不走回位阶梯、不 ESC、不重拉起、不前向复位），立即停止循环并回报：
  - `chain_advanced: true`（ledger 该条 entry 上也打一份）
  - `advanced_to: {activity, landing_node, elem_slug}`——`landing_node` 走
    `lib_landing.resolve_landing_node`，**解析不出为 null**（不硬猜）
  - `unswept: [{rid, text, content_desc, center}]`——本次未点的其余元素（`order` 里排在后面的），
    调用方到了新页自行决定补不补
  - `position_lost: true`（调用方据此**同步位置、禁就地接力**）→ `coverage_complete: false`
- 未推进（noop / toast_only / 页内状态切换）→ 一切照旧继续扫，**不误停**。
- **不在脚本里写第二份破坏性词表**：chain-mode 下要拦的「同意/不同意/跳过/继续/下一步/开始」类
  推进与协议按钮，由调用方从 `--exclude-texts` 传入；`DESTRUCTIVE_RE` 与 `nav_back` 判据一律不动。
- `truncated_by_time` **不**被 chain 推进污染（它仍只表示「墙钟截断」）；未扫完的事实由
  `chain_advanced + unswept + position_lost` 三个字段承担。

##### 3. `--only-rids`：边失败后的当场补点 + run_meta **合并写回**

- 只处理【锚点 rid 在集合内的 check（ground 类）】与【rid 在集合内的元素】；
  其余元素一律 `not_in_only` → 入账 `outcome=skipped_not_in_only`（不点、留账）。
  收窄是分账的**最后一道**，排除集优先于它。
- **run_meta 从「整份覆写」改成「合并写回」（仅本模式）**：核过了，原实现是
  `json.dump(run_meta, open(run_meta.json,"w"))` 的整份覆盖——补点趟只处理集合内的 check，
  整份覆写会把其余 check 的既有证据全部降级成 `skipped_not_in_only`（**假报「本 trip 测不到」，直接毁覆盖率**）。
  新增模块级 `merge_run_meta(old, new, processed_idx)`：按 `idx` 对齐（无 idx 退 `name`），
  **只有 `processed_check_idx` 里的 check 才允许用本轮记录覆盖旧记录**，其余原样保留；
  旧账没有的 check 照收；顶层字段用本轮事实；留 `merged_with_previous: true` 痕迹。
  旧账缺失/损坏 → 等价首次写（直接落新账，不硬合）。
- `processed_check_idx` = 本轮**真 tap 过**的 ground check ∪ **集合内**的 orphan（回读锚点那一路）。
  被 `walk/same_dest` 等继承结算的 check 不算「处理过」（本轮没学到新事实）→ 保留旧证据。
- **全量普查趟（不带 `--only-rids`）仍是整份覆写**，行为零变化。

##### 4. manifest / stdout 契约回显（两处都写，恒在默认值，调用方免判存在）

`chain_mode`(bool)、`chain_advanced`(bool)、`advanced_to`(obj|null)、`unswept`(list)、
`excluded`(int 计数)、`skipped_not_in_only`(int 计数)、`only_rids`(list 回显)。
run_meta 仅在 `--only-rids` 趟追加 `only_rids` / `processed_check_idx` / `merged_with_previous`。
新 ledger outcome：`excluded_by_caller`（带 `excluded_by`）、`skipped_not_in_only`；
新 gmeta status：`excluded_by_caller`、`skipped_not_in_only`；ledger entry 新增 `chain_advanced`。

##### 测试

`scripts/_tests/test_node_sweep_rules.py` **新增 8 项**（复用既有 `FakeDev`/`run_sweep` 夹具；
夹具向后兼容扩参：`extra_args` / `checks` / `extra_pages` / `page_extra`，新增 `_stdout_json`）：
排除集不点但入账且不进分母（含 check 结账）、排除集不遮蔽 destructive/nav_back、
chain-mode 推进即停（零 BACK + unswept 完整 + landing_node 解析 + position_lost/coverage_complete）、
chain-mode 另两条推进判据（包名变 / 同 activity 换页，落点不在树内时 landing_node=null）、
chain-mode 放行链页或门（裸跑仍 exit 21、`--allow-chain-sweep` 不受影响）、
only-rids 只点集合内锚点且 run_meta 合并（旧证据逐字保留、集合内 check 被新证据覆盖）、
不带旋钮时默认值 + 全量趟仍整份覆写、`merge_run_meta` 单元规则（留旧/覆盖/新增/空旧账/坏旧账）。

`cd scripts && python3 -m pytest -q _tests` → **138 passed**（开工基线 130 全绿保持 + 新增 8）。

##### 已知取舍

- 排除集是**精确匹配**：调用方传的文案要与 dump 里的 `text`/`content-desc` 一字不差（含空格已 strip）。
  故意不做模糊——链页上「同意」与「不同意」只差一字，子串匹配会互相误伤。
- `--only-rids` 趟里的 `unplanned_destructive` 会是空的（集合外元素被收窄成 `not_in_only`）。
  补点趟本就不是全清单账，树漏边的探测以**全量普查那趟**为准。
- chain-mode 未推进时的回位仍走既有路径（NON_DESCENDING 只 ESC 不 BACK、页内状态切换前向复位）——
  「绝不 BACK/回位」的承诺只覆盖**判为推进**之后。
- 未跑真机：链页推进后的 `landing_node` 解析质量取决于树里 `layout_facts.discriminators` 的成色
  （解析不出即 null，调用方需要自己判位）。

### 并入：计划器/写回/孤儿/链趟第三轮（plan3）
范围：`scripts/plan_edge_walk.py` / `scripts/writeback_walk.py` / `scripts/plan_orphan_probe.py` /
`scripts/plan_chain_sweep.py` + 三个测试文件。**零 app 常量**：全部只吃树字段、计划字段、边真值字段与
执行器状态字段；测试夹具一律 RootPage/HubPage/LeafPage 这类占位名。未提交、未推送、未跑设备。

---

#### B1 BACK 落点：从「执行器看得见但没人记」到「计划器据此改发 renav」

**病（0910 实测，约 10 次熔断）**：创作链走到结果页后整条链出栈——从结果页 BACK 直接回到 tab 宿主；
大纲页的 BACK 会弹「退出确认」而唯一放行键是**禁点**的确定。计划里所有从这几页发出的 `back` 步
**结构上走不通**，重试只烧轮次预算。执行器其实在 `do_back` 里观测到了「BACK 实际落在哪 / 有没有弹确认窗」，
但从没回写成计划器能消费的事实 ⟹ 每趟原样重演。

##### 写回侧 `writeback_walk.py`
- 新增 `BACK_ACTIONS` / `back_observation(e)` / `_top()` / `aggregate_back_landing(obs, walk_id)`。
- 消费两种记录形态：
  - **新契约**（执行器 0910 起产）：`{"action":"back","from":按下BACK的页,"to":计划期望回到的页,
    "landed":实际落点,"back_dialog":确认窗或 null,"status":"confirmed|not_reproduced","walk_exec":true}`；
  - **旧形态**（本仓 `edge_results.json` 现状）：BACK 结果回填在**被 tap 的那条边**上
    （`back_returns_to_parent`）⟹ 按 BACK 的页 = `e["to"]`、期望父页 = `e["from"]`，落点只在成功时可知。
    ★该记录里的 `landed` 是 **tap** 的落点（子页），**绝不能**拿来当 BACK 落点（会把事实写反，已写成测试）。
- 汇总写进**按下 BACK 的那个节点**的 record：
  `runtime.back_landing = {"node":多数落点, "n":次数, "matched_n":…, "matches_parent":bool,
  "confirm_dialog":节点或 null, "expects":多数期望父页, "walk_id":…}`。
  多数取值平票按名字定序（零 LLM 反哺必须逐字节可复现）；`matches_parent` 要求**严格多数**
  （半数对半数按不成立算：回位不可靠就该 renav）。
- 纪律：只加 `runtime.back_landing` 一格，**与既有 runtime 字段并存**，不改其他字段；
  **负面证据不删边**（"BACK 回不去" 证不出入边不存在）。`action=="back"` 的记录不进 trigger 匹配
  （它不是 tap 边真值），因此不会产生 `discovered_edges`、也不会踩消歧闸。
- BACK 观测的宿主页不在树内（黑盒变体/未知落点）→ 记 `_defects.back_node_missing`，
  **不进** `node_missing`（那把闸会 exit 20）——缺的是回位事实，不该阻塞整次反哺。
- stderr 响亮报出「哪些页 BACK 回不到父页 / 弹确认窗」，`_phase_markers[walk_id].back_landing` 记条数。

##### 计划器 `plan_edge_walk.py`
- 新增 `back_landing_of(by_id, node)` / `renav_reason(bl)`；`plan_walk(..., back_landing=None)`。
- `ret()` 发 `back` 前查该节点事实：`confirm_dialog` 非空 → `back_needs_confirm`；
  否则 `matches_parent is False` → `back_landing_mismatch`；两者都不成立（含**无事实**）→ 行为一字不变。
  确认窗优先报：它是机制层面的原因，落点不符只是它的表象之一。
- 命中即改发 **renav** 步：
  `{"action":"renav","from":当前页,"to":应回到的节点,"kind":…,"reason":…,"observed_landing":…,
  "confirm_dialog":…,"note":…}`。语义（执行器实现）= **用计划里该节点的到达路径重新导航**
  （等价 coldstart + 重放前缀，或 tab 重点）后验哨兵。位置语义与 `back` 完全一致：下一步仍从父页出发，
  `subtree_end_step` 区间照旧覆盖回位步（已写成测试）。
- 不动 tab/sub_tab（本就不发 BACK，发 verify）与 wizard 单行道（自有回位阶梯）。
- `main()` 从树 record 建 `{节点 → back_landing}` 传给 walk_0/walk_1；有 renav 页时 stderr 列出。
- `walk_plan.txt` 新增 `⟲ 重新导航` 渲染行。
- **位置模拟**：`precompute_positions/simulate_stack` 在 `walk_exec.py`（本次不属本代理改动面），
  故本文件内无位置模拟需改；执行器侧把 `renav` 当「位置 = to」由另一线落地。

#### B5 通用小项
- `prune_tail`：`renav` 与 `back` 同等对待——进 `_PRUNABLE_ACTIONS`，并进规则②的
  「回已 finish 的 launcher/wizard 页」判据。尾部空转的 renav 更贵（一次冷启重放），更不该留。
- `_edge_runtime_fields` **未改**（按拍板保持原样）。

#### B2 孤儿探测：黑盒噪音变体不再排走（`plan_orphan_probe.py`）
**病**：0910 为一个 `Unknown#via=…` 变体排了一趟 walk_3——候选入口页 0 个、判别物 0 条，探测协议要求的
三样一样都没有，结构上只能记 unreached，白烧 6 分钟 + 一次冷启。
**治**：新增 `NOISE_ID_MARK="#via="` 与 `is_noise_orphan(tree,node,file_idx)`——id 带运行时变体标记
**且**机械候选为空，两条**同时**成立才算噪音（有候选的变体照常探，真节点零候选也照常探）。
噪音不排 walk、不进 `plan.orphans`，逐条记入 `plan.orphan_probe.skipped_noise[]`（带理由）。
全是噪音时连 walk_3 都不排。

#### B3 收尾链趟合并成**一趟**（`plan_chain_sweep.py`）
**病**：0910 每页各排一趟 pm clear + 重走首启链 + 普查，7 页 80 分钟；且前缀只抄了 `coldstart`/`tap`，
把首启协议弹窗的 `gate_pass` 放行步整排漏掉 ⟹ **每趟必熔断一次**。
**治**（整文件重写，接口不变：`--tree --dir [--dry-run]`）：
- 欠账三源并集：① `sweep_skipped_chain` − 已有 `grounding/<node>/run_meta.json`（老口径）；
  ② `state.sweep_debt {node:[unswept…]}`（扫了没扫完——run_meta 必然已存在，**不能**按 ① 过滤）；
  ③ `state.capture_debt [node]`（链趟里被跳过的采集）。
- **一趟** `walk_6_chain_sweep`：pm clear → 按 walk_0 **步序**重走首启链 → 沿途每到一个欠账页插一个
  `sweep` 步（`--allow-chain-sweep`）→ 走到最后一个欠账页即止。链页顺序 = walk_0 步序。
- 前缀**完整抄** `PREFIX_ACTIONS = coldstart/tap/gate_pass/type/back/back_inpage/renav/verify/
  coldstart_replay_prefix`（所有会改变或校验位置的步，含新加的 renav），只丢 `skip`/`note`
  （纯审计注记）。tap 步的 `static_rid` 等字段原样保留——执行器链页普查的排除集要用「本页出边 rid」。
- `capture_debt` 的页在链趟里**恢复 `settles_capture`**（首次到达那一步），其余步只途经
  （`settles_capture=None`、`settles_grounding=[]`）。walk 记 `chain_nodes` / `capture_restored`。
- 顶层 `dynamic:true` / `order_exempt:true` / `reset_before:pm_clear` / `chain_protected:true` /
  `trip_id`（沿用 walk_0）保持不变。带 `cancelled` 的既有链趟条目原样保留、其节点不重排
  （兼容 0910 前的一页一趟 id `walk_6_chain_sweep_<node>`，节点从 `chain_nodes` 或 id 后缀取）；
  重复调用幂等（链趟不叠加）。
- `plan.chain_sweep` 增记 `swept_in_walk` / `capture_restored` / `unreached`（walk_0 步序里无到达步的欠账页）
  / `sources`（三源明细）。
- ⚠️**明写的代价**：一趟连扫多页时，前面页的普查可能点掉一次性链上的推进控件而把链烧断。执行器侧链页普查
  已有排除集（wizard_exit_controls / contract 出口 / 本页出边 static_rid）+ 普查后独立判位重点兜底；
  仍烧断则熔断，剩余欠账下一次 finalize 会重新算出来再排一趟。

---

#### 测试
- 新增 `_tests/test_writeback_back_landing.py`（5 例）：新旧两种记录形态解析（含「tap 的 landed 不得当
  BACK 落点」）、多数/平票/严格多数聚合、端到端写回（并存既有 runtime、不删边、不产 discovered_edges）、
  未知宿主页不触发 exit 20 闸。
- `_tests/test_plan_rules.py` 追加 8 例（B1）：理由判据、事实读取、无事实行为不变、mismatch/confirm 两种
  情形发 renav、tab/wizard 不被改写、位置与 subtree 区间不变、prune_tail 同等对待、端到端（树带
  `runtime.back_landing` → 计划出 renav + stderr + txt 渲染）。
- `_tests/test_landing_and_orphan.py` 追加 8 例（B2/B3）：噪音判据双条件、噪音不排走只记账、全噪音时不排
  walk_3；链趟合并成一趟且前缀含 `gate_pass`/`type`、sweep 按步序插入、末尾截断、capture 恢复、
  `unreached`、cancelled 保留 + 幂等、前缀白名单覆盖体检。
- 全量：`python3 -m pytest -q _tests --ignore=_tests/test_next_walk.py` = **173 passed**；
  本批三个测试文件单跑 **48 passed**。整目录跑时 `test_next_walk.py` 有 1 例红，**与本批无关**：
  `next_walk.py` 与它的测试正被另一线同时改动（本机 mtime 比本批改动更新，两次运行红的还是不同用例），
  本批四个文件均未被 `next_walk.py` 引用。

#### 真实产物干跑（只读复制到临时目录，未改任何项目文件）
以 `AIPPT_0910_walk` 的树 + `edge_results.json` + `walk_exec_state*.json` 做回归：
- 写回：25 次 BACK 观测（全部走**旧形态**兼容路径）→ 12 页写出 `back_landing`，其中 1 页判「回不到父页」，
  正是 0910 出栈那条链上的大纲页；其余边统计与改动前一致，未触发任何闸。
- 计划：该页的 3 个 `back` 步全部换成 `renav`（stderr 与 walk_plan.txt 均有痕）；其余计划不变。
- 链趟：7 段 → **1 段 13 步**，且步 3/步 5 就是此前漏抄、每趟必熔断的两个 `gate_pass`；
  带 `cancelled` 的两段原样保留。
- 孤儿：`Unknown#via=…`（候选 0）不再排 walk_3，进 `skipped_noise`，全趟省下一次冷启。

#### 未做 / 交接
- `renav` 的**执行器实现**（重新导航 = coldstart + 重放前缀 / tab 重点）与 `precompute_positions/
  simulate_stack` 把 `renav` 当「位置 = to」——在 `walk_exec.py`，归另一线。
- `walk_exec` 产 `action=="back"` 的边真值记录（含 `landed`/`back_dialog`）——归另一线；
  在此之前写回侧走旧形态兼容路径，事实一样能建起来（只是落点在失败时未知）。
- `walk_finalize.sh` 第 5.8 段的提示文案仍写着 `walk_6_chain_sweep_*`（现在是单趟 `walk_6_chain_sweep`），
  不属本批改动面，只是文案。
- 链趟合并后可进一步按 walk_0 的 `subtree_end_step` 剪掉「不含欠账页的整段子树」再缩短一趟墙钟——
  本批未做（保守：先按拍板的「原样重走前缀」落地，避免多引入一层裁剪风险）。

---

## 2026-09-09 晚（第二批：36 次熔断归因后的通用修复 · 主会话部分）
归因：36 次熔断零偶现——执行器契约 10 / 计划器与分派 12 / 树数据 12 / 环境前置 2；另一趟登出态 walk 在登录后追加执行，因后端登录态不可逆整趟白跑。
- 新增 `scripts/walk_timeline.py`：安卓遍历时间线唯一写入口（mark/list/path，文件在 $EW 上一级）；
  `run_scenario_with_verify.sh` 安卓侧建态成功后自动 `mark --phase scenario:<name> --trip $TRIP_ID`——执行器 trip 顺序闸靠它判「登录已发生」。
- 新增 `scripts/walk_state_inventory.py`：派 chunk 前的态清单（按 kind:polarity 汇总前置、极性缺失清单、state_required 无 input 配方清单、每 trip 前置画像）。零 LLM。
- `check_prereq_freshness.sh` Gate 3.5：login/vip/login_conditional 类前置的 polarity 覆盖 <100% → NEED:app-relationship-tree；`VV_ALLOW_MISSING_POLARITY=1` 降为 warn。0909 树实测 0/30 → NEED（回填后应 PASS）。
- 文档：`references/phase2-edge-walk.md` §3 步 0（edge_lint → trip_assign 重生成 → 态清单 → trip 顺序铁律）、§4.y（type/门步/尾部剪枝/生成多调用方/suspect/verify_signal 哨兵/stop_at_dialog/_post 帧/UI_WORDS 契约）、§7.2 输入配方去项目化、§7.3 三条新坑；`SKILL.md` trip 态建立段加顺序铁律。
- 单测 `_tests/test_state_inventory_timeline.py` 2 项。
- **驱动脚本 `scripts/next_walk.py`（§3 散文流程的机械状态机，页粒度 next_batch.py 的对应物）**：无状态可重入，只读计划/账本/状态文件/时间线；
  封闭动作集 plan / write_safety_review / dispatch_walk(+also_dispatch_judge) / run_login / dispatch_judge / confirm_overrides / finalize / wait_in_flight / blocked / done；
  在飞锁（`.driver_in_flight.json`）机械落实「行走在飞主会话不碰 $EW」；trip 顺序闸与执行器 B1 同口径提前到派发前；登录 scenario 从 spec/scenarios 反查（多候选须指名）；
  判读任务按 finalize 2.5 闸同口径算出、快照到 judge_snapshots、prompt 由新模板 `references/phase2-judge-template.md` 填；`--merge-judge` 幂等键 (node,check_name,check_idx)；
  未达节点归因草稿 reason_overrides.draft.json（聚合 not_reproduced note）；finalize 新鲜度按日志 mtime 对产物 mtime 判，5.7/5.8 追加的 walk 自然进入下一轮；
  stop_if_settled 的生成走目标已结账即视为完成。`_tests/test_next_walk.py` 9 项（合成 $EW，动作序列逐站）。
- 独立复核（散文 vs 实现，11 条款）后的修正：①收尾链趟/孤儿探测走带 `order_exempt`（驱动与执行器 B1 同口径豁免，否则 finalize 5.8 排出的链趟永远被顺序闸拒）；
  ②`finalized()` 改认 `finalize_<trip>.ok`（仅 exit 0 落，闸红撤标记），此前按日志 mtime 会把闸红洗绿；③登录包装脚本 trip_1 封账闸边遍历感知（$EW/walk_plan.json 存在时按 walk 状态判债，`next_walk.py --first-trip-debt`）
  且 scenario 名按 login* 前缀匹配、头部补 exit 31；④驱动登录退出码路由补 31、30/40/50 与 SKILL「必跑 gate_experiment.sh」同口径；⑤登录 scenario 反查收紧（run_env 冻结值优先；stem 以 login 开头且排除 check/verify/relogin/oauth/logout）；
  ⑥新 walk 首派 RESUME 不再贴别的 walk 的交接；首步即熔断的走算 in_progress，续派 EXTRAS 机械带上熔断包路径；⑦判读 prompt 节点目录 `$`→`_`；⑧一步未走时树/分派表比计划新 → 回步 0 重出计划；
  ⑨执行器 `--budget-min`（缺省 max(30, 步数×2)，开工时间取在飞锁 ts）超时出 `wall_budget_exhausted` 且 `handoff_due=true`——墙钟止损从代理自觉变机械；⑩散文：SKILL trip 态建立段加边遍历分支（trip_2 不 pm clear）、安全复核口径改计划级一次。
- **共用弹窗按调用方分变体基线**（用户拍板；0909 实证：AppTipsDialog 七个调用方只有首个「退出大纲」有图，一键退款/取消订阅确认窗零截图，早拍帧全是父页）：
  执行器到达**已结账**的 dialog 节点且调用方不同 → `_settle_dialog("<node>#via=<from>__<rid|文案>")` 落变体基线+dump（首个调用方仍用本尊，同调用方复访不重拍，变体不普查），
  边真值加 `variant_baseline`/`evidence`；auto 边与 `--mark-step-done` 手工路同口径；`walk_place_baselines.py` 按本尊判目标/trip 后随本尊落位。判据只看 (node, from, rid|label)。
  `_tests/test_walk_exec_variants.py` 2 项。
- 派发模板 `references/phase2-chunk-dispatch-template.md` 改为执行器模式：不再要求精读 §4~§7，改一页「熔断处置卡」（默认执行 options[0]、不自行 dump、单次 3 分钟、抢救记 incidents、12 次熔断/墙钟到预算即交接）；
  步序文件只给路径不让代理读；新增 `{{WALK_ID}}`/`{{DEVICE_STATE}}` 槽（`fill_chunk_prompt.py --walk-id/--device-state`，缺省从 walk_plan.json 反查）；去掉写死的用户目录路径。
- 计划器 / 执行器 / node_sweep / 树侧 edge_lint 与 guard 的改动见同日各自条目（子代理落地，主会话合并）。
- 主会话合并后的收敛（子代理交付之上）：
  · `trip_assign.py` 跳过 disproven 前置、absent/required 分别进登出/登录趟、两者都有进两趟（此前读到第一条就返回，HomeActivity/MineFragment 上一条 disproven 的 absent 把登录趟整棵子树排出计划，可执行 37→32 才暴露）。
  · `plan_edge_walk.py` 新增 `TRIP_STATES`/`polarity_blocked`：前置极性与本趟态矛盾的边发 skip(precondition_polarity_mismatch)，BFS 同口径；auto 边目标已结账发 skip(auto_revisit)；prune_tail 对审计 skip/note 透明（尾部 back_inpage 此前被 skip 挡住剪不掉，执行器不认 back_inpage 会白熔断一次）。
  · `walk_exec.py` 门步只有目标是 dialog 节点才走 dialog 直接结账（launcher→引导页这类非瞬态门走正常结账，与计划器 A2 收窄口径对齐）。
  · `node_sweep.py` 状态切换判据收成「selected/checked 集变化」，只文本变记 text_drift（轮播/异步刷新页否则每次 tap 都判成状态切换）；复位判据同。
  · ART `edge_lint.py` 站点键用 trigger_owner_page、owner 豁免宿主闭包（contains/parent_id/parent_in_nav/装载类 attach_kind，≤3 跳）、带分支条件的一站点两目标改软标 site_two_targets_conditional；`llm_phase_guard` 极性/input 检查跳过 disproven；`run_all_phases.sh` 接 Phase 2.8 edge_lint --write。
  · 0909 树端到端验收（scratch，不写项目）：可执行 37→42、缺口只剩退款链 4 页、哨兵 weak 11→1、walk_0 含会员中心一族与 3 个门步、type 步 2、尾部无回启动页；三套单测 90+37 全绿。真机回归留待下一趟。


# CHANGELOG.pending（执行器一侧，待并入 CHANGELOG.md）

> 本文件只记 `scripts/walk_exec.py` 的改动，避免与并行改 `plan_edge_walk.py` / `node_sweep.py`
> 的分支抢同一个 CHANGELOG.md。验收后由拍板人合并进主 CHANGELOG 再删除本文件。

# 待合入 CHANGELOG（计划器一侧，2026-09-09）

> 本文件是**待合并草稿**，由计划器分支单独维护，主会话合并进 `CHANGELOG.md` 后删除。
> 触发来源：0909 安卓边遍历 36 次熔断中归计划器的 12 次。改动只落三个文件
> `scripts/plan_edge_walk.py` / `scripts/phase2_scope.py` / `scripts/trip_assign.py`，
> 新增测试 `scripts/_tests/test_plan_rules.py`（25 例，全合成小树，零真实项目名）。

# 待合入 CHANGELOG（执行器熔断成本治理，2026-09-09）

> 本文件是**待合并草稿**，只记 `scripts/walk_exec.py` 这一趟的改动，
> 避免与并行改计划器 / node_sweep 的分支抢同一个 `CHANGELOG.md`。
> 验收后由拍板人合并进主 `CHANGELOG.md` 再删除本文件。
>
> 改动文件：`scripts/walk_exec.py`（唯一）
> 新增测试：`scripts/_tests/test_walk_exec_escalation.py`（22 例，合成计划 + 合成 dump + 假设备，零设备）
> 回归：`scripts/_tests` 全量 **112 项全绿**（原 90 + 新 22）

## 动机（0909 安卓真走实测账）

36 次熔断，平均一次 3.3 分钟。拆开看，代理的时间几乎全花在**重复劳动**上：
读熔断 JSON → 回规范找协议 → 看截图 → **自己再跑一两次判位和控件清单** → 三选一 → 重拉执行器。
真正的决策只占一小部分。两个方向：把重复劳动机械前置（目标单次 <1min），
以及把几类高频原因干脆做成执行器自己能定的（不再熔断）。

---

## 一、熔断包自带诊断与决策菜单（`escalate`）

### 落点
- 新增 `Exec._diag()`：退出前机械采集诊断；每一项独立 `try/except`（模块级 `_safe()`），
  任何一项失败只置 `null`，**诊断绝不能自己抛错**把该交还的现场变成执行器崩溃。
- 新增 `Exec._options()`：按 `reason` + `diag` 生成**有序**决策菜单，`options[0]` 即推荐。
- 新增支撑件：`_landing()` / `_landing_strong()`（lib_landing 判别物投票）、`_open_dialogs()`、
  `_screen_size()`、`_expect_host()`、`_control_diag()`、`_resume_argv()` / `_cmd()` / `_tap_cmd()`；
  模块级 `find_view_bounds()` / `root_bounds()` / `_safe()`。
- `escalate()` 输出新增 `diag` / `options` / `escalation_card` 三个字段（旧字段 `resume_hint`
  与 `evidence_screenshot` **原样保留**，下游解析不破）；整包除 stdout 外**另存**
  `escalations/step<N>.json`（覆盖写），当次 dump 落 `escalations/step<N>.xml`。
- 熔断点补 `verify_node=`（`verify_at` 的两处、`_post_sweep_verify`、`do_tap` 到达侧），
  让菜单知道「期望在哪个节点」——`verify_at` 既可能在校验起点也可能在校验落点。

### `diag` 字段契约
| 字段 | 含义 |
| --- | --- |
| `activity` / `package` | 当前前台 |
| `ime_shown` | `dumpsys input_method` 含 `mInputShown=true` |
| `screen` | `[w, h]`，dump 根节点 bounds 优先，退 `wm size`，取不到 `null` |
| `landing_node` / `landing_why` | `lib_landing.resolve_landing_node(tree, activity, dump, parent_id=step.from)` |
| `landing_sentinel` / `expected_sentinel` | `{node, ok, weak, why}`，各跑一次 `sentinel_check` |
| `open_dialogs` | 哨兵表里 `kind=resource_id_unique` 且 `hosts` 非空的 dialog 类节点在当前 dump 上强命中的清单（≤5） |
| `cancel_control` | `choose_cancel_control` 选出的取消/关闭控件 `{rid, text, center}`（菜单 cmd 用） |
| `control` | 仅 tap 步：`{rid, static_rid, label, in_clickables, in_dump, bounds, offscreen, center, matched_by}`；`in_dump` 按 resource-id 后缀在**整份** dump 找（不限 clickable），`offscreen` = bounds 在屏幕高之外 |
| `clickables_top` | 可点元素前 15 条 `{rid, text, center}` |
| `target_settled` / `sole_settle_step` | 目标是否已入账 / 本步是否目标唯一未结账的结账步 |
| `evidence_dump` | 当次 dump 的落盘路径 |

### `options` 字段契约
每项 `{key, cmd, when, effect, coverage_loss}`。`cmd` 是**可直接执行的完整续走命令**——
由 `sibling_cmd` + 本次调用的 `--dir/--serial/--package/--walk/--tree/--device-state/--launcher/
--ad-profile/--blackbox-out/--blackbox-budget/--no-*/--allow-*` 原样复刻再拼处置参数；
需要先动手的项（`manual_tap` / `close_dialog_then_resume` / `walk_back_to_then_resume`）
把 `adb shell input tap`（或 `walk_back_to.py`）与续走命令用 `&&` 串成一条。

按 reason 分支（命中几条给几条，按序即优先级）：

| reason | 菜单 |
| --- | --- |
| `control_not_found` | ① 目标已结账或本步不结账 → `skip`（`coverage_loss=false`）② 控件在 dump 且屏外 → `resume`（下趟执行器会定向滚动）③ 在 dump 但不在可点集 → `manual_tap`（点 bounds 中心 + `--mark-step-done`）④ 都不中 → `skip`（`coverage_loss` = `sole_settle_step`） |
| `arrival_unverified` | ① 落点=起点且哨兵 ok → `skip --skip-reason no_effect` ② 落点是别的强命中节点 → `skip_landed`（`--skip-reason landed:<X> --assume-at <X>`）③ 有未关弹窗 → `close_dialog_then_resume` ④ 兜底 `resume` + `skip` |
| `weak_sentinel_confirm` | `resume_assume`（`--resume --assume-at <node>`，看截图确认）→ `skip` |
| `position_mismatch` | 落点强命中 → `--assume-at <landing>`；有弹窗 → `close_dialog_then_resume`；兜底 `--resume` |
| `back_failed` | 有弹窗 → `close_dialog_then_resume`；落点强命中 → `--assume-at <landing>`；兜底 `walk_back_to` 回位后 `--resume --assume-at` |
| `input_failed` / `input_target_not_found` / `gate_pass_unknown` | `manual_then_mark_done`（`--mark-step-done N --assume-at <to>`） |
| 其他（`llm_action` / `needs_discovery` / `side_effect_gate` / …） | 保留原三选一，只是结构化成 `resume` / `mark_step_done` / `skip` |

`escalation_card` 是一句固定话：
「包内已有判位/控件清单/弹窗判定，不要再自行 dump；按 options[0] 执行，不同意时在 notes
写明理由再选其他；单次处置预算 3 分钟，抢救类工作记 incidents 不在熔断里做」。

---

## 二、能机械收的不再熔断

四条规则，命中都记 `state.notes` **与**边真值 `note`（事后可统计哪条规则收了多少）。

- **(a) 到达落点解析**（`do_tap` → `_arrival_landing_recover()`）：到达判定失败后按判别物投票解析落点 X。
  · `X == step.from` → 这一下点击没效果，边记 `not_reproduced`（note `no_effect:`），跳子树续走；
  · `X` 是树内别的节点 → 边记 `not_reproduced` 带 `landed: X`，**另 append** 一条
    `{from, to: X, status: confirmed, discovered: true, control: 同本步}` 供 writeback 当发现边；
    X 是未结账的 dialog 顺手 `_settle_dialog`；随后最多 2 次机械回位（每次先 `_probe_at(from)`，
    到即停；BACK 前若 `choose_cancel_control` 选得出取消控件就点它而不是 BACK）；
    回到起点续走，回不到才熔断 `position_mismatch`（带菜单，且边真值已落账不白跑）。
  · 只认**强落点**（投票不歧义且判别物真有命中）——lib_landing 零命中时会退回 Activity 本身，
    那种「只是 activity 对上了」不足以拿来改写边真值。
- **(b) 屏外控件定向滚动**（`_scroll_to_offscreen_control()`）：`control_not_found` 前，
  若 rid/static_rid 在 dump 里有节点且 bounds 在屏幕高之外 → 按 bounds 与屏幕中心的纵向差值
  做**一次**定向 `input swipe`（方向只按上下），再 `find_control` 一次；仍无 → 原流程。
  控件就在屏内却没找到 = 别的原因（不可点/被遮），**不滚**。
- **(c) 到达弱哨兵按落点投票接受**（`do_tap` 到达判定）：`ok and weak` 且不满足既有两种接受
  （`--assume-at` / 向导顺序语义）时，若落点投票结果 == `step.to` → 接受，note
  `weak_accepted_by_landing_vote`。投票用的是树里的 `discriminators`，与哨兵表**不同源**，不是自证。
- **(d) 起点被弹窗挡住**（`verify_at` → `_dismiss_blocking_dialog()`）：判定失败进入熔断前，
  若 `open_dialogs` 非空且该 dialog 不是期望节点 → 用 `choose_cancel_control` 点一次取消/关闭
  （选不出就 BACK 一次），再判一次；仍失败才熔断。**只点取消词表，绝不点确定类**；
  `no_gate`（`stop_at_dialog` / 计划内门步）一律不适用——取消也是碰弹窗。
  同时 `verify_at` 改成预算式循环：放行（`_dismiss_gate`）与关弹窗**各自不占判定预算**，
  否则救场动作会吃掉最后一次重判。

### 覆盖优先于速度（公共闸）
新增 `Exec._is_sole_settle_step(step)`：本步是「该目标唯一且尚未结账的结账步」→ True。
`_suspect_fastpath`（B6，原本内联同一段逻辑）与 (a)、(c) 全部复用它：命中一律**让位给熔断**，
由代理拿菜单决定 skip 还是 resume。判据只吃计划字段 + ledger，零业务常量。

---

## 通用性自查（换项目零改）
逻辑不出现任何具体应用的页名/控件 id/文案/包名。全部输入只有：
计划字段（`step.action/from/to/trigger/static_rid/item_rid/suspect/gate/safety/settles_capture`、
`sentinels[node]`）、树字段（`layout_facts.discriminators`、`dialogs`、`inbound_triggers.runtime`）、
dump 属性（`resource-id` / `text` / `bounds` / `clickable`）、`dumpsys` 输出、
以及可整表覆盖的 `UI_WORDS`（`$EW/ui_words.json`）。

## 未做项
- 菜单里的 `cmd` 不做「自动执行」——处置权仍在代理手上（本轮只降成本，不改权责边界）。
- `escalations/step<N>.json` 只覆盖写不留历史；同一步多次熔断的对照要靠 `state.llm_gaps` 与
  `walk_exec_state.<walk_id>.json` 归档。
- (b) 只滚一次、只按上下：横向容器（HorizontalScrollView/ViewPager 内的横向列表）不猜方向，仍走熔断。
- 规则命中率的统计脚本没做——注记已按 `no_effect:` / `landed_elsewhere:` / `offscreen_scroll:` /
  `weak_accepted_by_landing_vote` 固定前缀落在边真值 `note` 与 `state.notes` 里，事后 grep 即可。
- 真机回归未跑（本轮全部合成用例，按铁律不碰设备）。

## A1 哨兵消费 LLM 的 `verify_signal`（治 8 次弱哨兵熔断）

- `plan_edge_walk.py`：新增 `_verify_signal_of()` / `_apply_verify_signal()`，把
  `navigation_contract.verify_signal`（`text_contains` / `view_id` / `ordinal_in_wizard`）
  **原样复制**进每条哨兵的 `verify_signal` 字段；`derive_sentinel()` 全部四个出口都过这道加工。
- 判强三条（`resource_id_unique` 不动，本来就强）：
  1. 带 `text_contains` 或 `view_id` → `weak:False`（宿主 + verify_signal 逐字命中即算到页）；
  2. 只带 `ordinal_in_wizard` 且本页 `relationship_kind == "wizard_step"` → `weak:False`
     （执行器按「宿主 + 第 N 步」接受）；
  3. 共享 id 的**全部持有者**宿主两两不相交 → `weak:False`（宿主校验已能区分）。
     持有者靠新增的 `build_holder_index()` 求（layout 解析口径与哨兵同源，见下）；
     索引缺失时本条不生效（不猜）。
- 顺带把 `derive_sentinel` 里的 layout 三级定位提成 `resolve_layout()`：持有者索引必须与哨兵
  用同一把尺解 layout，两处各写一套必漂移。
- **动机**：树侧 LLM 早就把到页判据写在 `verify_signal` 里，机械层从来没消费过；执行器拿着
  `weak:True` 不敢认到页，一路升级 LLM 直到轮次预算烧穿。
- **验证**：0909 树同一棵树上 `weak` **11 → 1**（7 条靠 verify_signal、3 条靠向导序号；
  剩下 1 条是 `#via=` 黑盒变体，树上本就没有 verify_signal）。判据 3 在这棵树上未触发
  （前两条已覆盖），由单测覆盖。

## A2 首启门边进 walk_0（治 3 次）

- `phase2_scope.py` `dialog_trigger()`：可采判据从「trigger_label 可用」放宽为**三选一**——
  文案可用 / `trigger_kind ∈ {auto, list_item, span, async_after_tap}` / `trigger_view_id` 是真值
  （`"null"`/`"None"` 脏值不算）。无文案时 label 位返回占位 `<trigger_kind>`。
  `excluded_dialogs()` 的排除理由同步更新。
- `plan_edge_walk.py`：新增 `is_first_launch_gate()`（`edge_preconditions[].kind` 以
  `first_launch` 开头 **且** `trigger_kind == "auto"`）与 `is_transient_gate_target()`；
  边上带 `gate` / `gate_transient` 两个标记。
- `plan_walk(consume_gates=True)`（只有 `chain_protected` 的 walk_0）：DFS 到每个节点时**先**发
  该节点的瞬态门边 `tap(gate=True, auto_transition, wait_hint, settles_capture=门目标)`，紧跟
  `gate_pass` 回起点；**门目标即使不在本趟 scope 也结账**（一次性资源，只有这趟见得到）。
  其余 walk 遇到瞬态门边 → `skip(skip_reason="first_launch_gate_consumed")`。
- 排序键 `_edge_sort_key()` 把门边排在同起点兄弟最前（原来 dialog 的 PRIO 排在 push 之后，
  门被后排 = 先排的边点在弹窗上）。
- **⚠️ 对给定契约的一处收窄（安全，需主会话与执行器对齐）**：契约原文只按
  「首启前置 + auto」定义门边，这会把 `launcher --auto--> 主界面` / `--auto--> 引导页`
  这类**真页面跳转**一并框进来；若按「tap 门 → gate_pass 回起点 → 结账即不再下钻」处理，
  整趟行走会在第二步把主界面标成已访问、子树全部掉出计划（0909 树上 walk_1 的根正是 launcher，
  一旦照做 walk_1 整趟归零）。故只有**瞬态目标**（树内 dialog 或 `relationship_kind ==
  "lifecycle_modal"`）走门边专用步与「已消费」skip；非瞬态门边只提前排序，仍交 DFS 正常下钻，
  但同样带 `gate:True` 供执行器识别。
- **验证**：0909 树可采 dialog **13 → 18**（新增 5 个全是无文案的 auto 门/列表弹窗）；
  walk_0 前 7 步变为 `冷启 → tap 门A → gate_pass → tap 门B → gate_pass → tap 引导 → …`，
  walk_1 里门边落 `first_launch_gate_consumed`。

## A3 尾部回栈剪枝（治 2 次）

- 新增 `prune_tail(walk, launcher, wizard)`，`main()` 在算覆盖前对每趟调用一次：
  1. 从末尾往前扫，连续的 `back` / `back_inpage` / `coldstart_replay_prefix` / `verify` /
     `skip(one_way|return_edge)` 全删（其后已无 tap 与结账 = 纯空转）；
  2. 另删「`back` 到 launcher 或 wizard_step 节点，且此后再无一步**真的**从该节点出发」的步
     （`skip` 只是审计注记，不算依赖）——这就是 0909「BACK 回已 finish 的启动页」那两次。
     踏脚石保护：其后一步仍属回位链时不动；带 `settles_capture` / `settles_grounding` 的步永不剪。
  3. 剪完连续重编号，并**重算 `subtree_end_step`**（映射到存活步里 ≤ 原步号的最大者）。
- 删除的步全量留在 walk 顶层 `pruned_tail_steps[]` 供审计；`main()` 打印总数到 stderr。
- **验证**：0909 树剪掉 3 步（walk_0 两步含一条回已消费向导页的 BACK、walk_1 一步回 launcher）。

## A4 输入守卫出 `type` 步（治 2 次）

- 新增 `derive_input_guard(edge, from_rec)`：
  ①契约优先——`edge_preconditions[]` 里 `kind=="state_required"` 且带
  `input:{"view_id","text_hint"}`（LLM 2.7 新字段）；`text_hint` **纯 ASCII** 才带进步序，
  否则置 `null` 交执行器用中性默认串。
  ②机械回退——起点页 `layout_facts.edit_ids`（机械层新字段，可能不存在）非空，且该前置的
  `evidence`/`data_hint` 里**逐字**出现其中某个 id → 用它，并在步里标
  `input_source:"evidence_id_match"`。都不满足则不出步（保持现状，绝不猜控件）。
- `plan_walk` 与 `plan_path_walk` 在对应 tap 步**之前**发
  `type(from=node, to=node, view_id, text, precondition_kind="state_required")`；
  破坏性不走的边不发（不必先打字）。
- **验证**：0909 树在本次改动期间被上游 LLM 补上了 2 条 `input` 契约，冒烟里如实出现 2 个
  `type` 步（一条 ASCII 提示原样带、一条中文提示置 null）；`layout_facts.edit_ids` 这棵树没有，
  机械回退分支保持零输出，由单测覆盖。

## A5 生成目标遍历全部调用方（治 1 次）

- `plan_path_walk()` 新增 `final_edge=` 参数（先 BFS 到该边起点再接这条边），BFS 提成 `_bfs_path()`。
- `main()` walk_2 循环：每个 generation 目标对其**全部** inbound 调用方各出一条走，
  调用方排序键 `(_rt_rank, from)`，`walk_id = walk_2_generation_{tgt}_via_{from}`
  （只有一个调用方时保持原 id 兼容）；每条走顶层加 `stop_if_settled: <tgt>`，
  执行器开工发现目标已结账即整趟跳过（副作用链只需真跑一次）。
- 顺带把 `plan_path_walk` 收尾 `await` 步里写死的两个 AIPPT 页名换成目标变量（换项目通用）。
- **验证**：0909 树未配 `--generation-targets`（0 条生成走），由合成树端到端单测覆盖
  （两个调用方 → 两条 `_via_` 走 + `stop_if_settled`）。

## A6 消费 `guard_flags`（树侧闸在标）

- 边上非空 `guard_flags` → 边字段 `suspect:[...]` → 经 `_edge_runtime_fields` 原样进步序；
  `_edge_sort_key` 在 `_rt_rank` 之后加一位「有 suspect 排后」，让干净兄弟先走完。
- **验证**：0909 树暂无 `guard_flags` 边（零影响），由单测覆盖。

## A7 分派表新鲜度闸

- `main()` 读 `_trip_assignment.json` 时校验：其 `pages` 键集合必须 ⊆ 树全部 record id
  （含 `#via=` 的黑盒变体豁免）。有树外页 → 打印清单并 `sys.exit(3)`；
  新增 `--allow-stale-assignment` 放行（只告警）。
- **动机**：旧表来自上一版树时，`& targets` 这个交集会把不新鲜**静默抹平**成看不见的缺口。
- **验证**：0909 项目现表通过闸；合成树注入一个树外页 → 退出码 3，加参数 → 0。

## A8 `trip_assign.py` 元数据

- 输出 JSON 顶层新增
  `meta: {source_tree, tree_records, prefix_whitelist_hits}`；
  `prefix_whitelist_hits` = 靠**名字**兜底才进 trip_1 的页（规则 4 前缀白名单 + 关键词加法），
  它越长说明树结构信号越弱、越该去修树。stdout 多一行「靠名字兜底 N 页」。
- 兼容性：全部消费者读的都是 `.pages`（`phase2_needs` / `walk_ledger` /
  `walk_place_baselines` / `check_android_screenshot.sh` / `dispatch_phase2_batches.sh`），
  加同级键安全。
- **验证**：0909 树跑出「靠名字兜底 0 页」（树结构信号已足够）。

## 冒烟与回归

- 单测：`cd scripts && python3 -m pytest -q _tests` → **90 passed**（含新增 25 例；
  改动前基线全绿，无回归）。
- 冒烟（真实树只读，产物落 scratchpad，未写回项目）：
  目标 42 → **47**（A2 多认 5 个门/列表弹窗）、可执行 37 → **39**、缺口 4 → **7**
  （新增 3 个缺口全是刚纳入的弹窗，被途经预算挡在 walk_0 外，由页粒度兜底，属如实记账不是回退）。

## 遗留 / 待主会话拍板

1. A2 的瞬态收窄（见上）需与执行器侧的 `gate` / `gate_pass` 实现对齐口径。
2. 项目现有 `_trip_assignment.json` 是放宽 dialog 判据**之前**跑的，5 个新可采弹窗不在表里
   （A7 闸只查 ⊆ 方向，不报这种"缺"）。用当前 `trip_assign.py` 重跑一次分派表会让
   trip_1 从 14 涨到 21、可执行反而降到 32——那是 0909 早些时候落的
   `preconditions.polarity==absent → trip_1` 规则叠加上来的，不属本批范围，是否重跑请主会话拍板。
3. `walk_exec` 侧需要认新的两个 action（`gate_pass` / `type`）与新字段
   （`gate` / `suspect` / `stop_if_settled` / `pruned_tail_steps`）——执行器分支同步实现中。

## 2026-09-09 执行器通用规则批 B1~B9（0909 安卓真走 36 次熔断的执行器侧收口）

**动机**：0909 全量安卓边遍历墙钟 226min，其中 36 次熔断有 10 次归执行器契约缺陷（不是应用缺陷、
也不是计划缺陷）；另有一趟 trip_1（未登录首启）在登录之后被追加执行，因后端登录态不可逆整趟白跑。
以下九条全部是**跨项目通用机制**：逻辑里零具体页名/控件 id/文案/包名，只吃计划字段、账本字段、
时间线事件、dump 属性与 `dumpsys` 输出。

### 新增计划字段契约（由 `plan_edge_walk.py` 侧产出，执行器只消费）

| 字段 | 位置 | 语义 |
| --- | --- | --- |
| `trip_id` | `walk` | trip 归属；**执行顺序 = 计划里 trip_id 的首现顺序**（不解析名字里的数字） |
| `stop_if_settled` | `walk` | 这趟的唯一目标；已结账则整趟免跑 |
| `action: "type"` | `step` | 配 `view_id` / `text`(可空) / `precondition_kind`；`from == to` |
| `action: "gate_pass"` | `step` | `from`=门、`to`=放行后应回到的节点 |
| `gate: true` | `tap` 步 | 该步的落点就是门（协议/权限说明浮层） |
| `suspect: [flag,…]` | `tap` 步 | 可疑边（树里存疑/上轮未复现）；非空即启用快路 |
| `verify_signal` | `sentinels[node]` | `{text_contains: str\|[str]} \| {view_id: str} \| {ordinal_in_wizard: int}` |

账本侧消费：`ledger.settled[*].capture_meta.trip_id`（capture_page_e2e 产）。
时间线侧消费：`$EW/../android_walk_timeline.jsonl`，事件 `phase` 含 `login` 子串即视为登录态已建
（写入口是 `walk_timeline.py`，本执行器只读，缺文件/坏行都当没有）。

### 逐条改动（函数级）

- **B1 trip 顺序闸** — 新增 `Exec._trip_order / _timeline_events / _ledger_raw / _check_trip_order`，
  由 `run()` 开头第一件事调用（早于任何设备动作）。命中「账本里已有更后 trip 的 settle」或
  「时间线已打 login 点而本 walk 是序号 0 的 trip」→ 打印
  `{"status":"refused","reason":"trip_order_violation",…}` 并 **exit 3**（模块 docstring 的退出码表已补）。
  新增 CLI `--allow-trip-backtrack REASON` 放行并把 REASON 写进 `state.notes`。
  `--dry-run` 与无 `trip_id` 的走（深链走/生成链走）不查。
- **B2 `type` 动作** — 新增 `find_view_point()`（按 resource-id 后缀取中心 + 回读 text，**不限
  clickable**，输入框常是 clickable=false）、`input_text_arg()`（非纯 ASCII/空 → 中性默认串
  `test input 1`，空格转 `%s`）、`Exec.do_type()`；`run()` 加 `elif a == "type"` 分派。
  找不到控件 → `input_target_not_found`；回读 text 不含首个单词 → `input_failed`；成功记
  `state.notes`，耗时由 `_record_step_time` 照常入账。键盘弹起（`mInputShown=true`）按一次 BACK 收。
- **B3 计划内门步** — `do_tap` 认 `step.gate`：走原 auto/tap 到达逻辑但**不调 `_dismiss_gate`**，
  结账强制走 `_settle_dialog`（`_settle_and_advance` 新增 `force_dialog_settle`），门上**不普查**
  （欠账记 `state.sweep_skipped_gate`，与链保护同款铁律：普查未认领元素=当场烧门）。
  新增 `Exec.do_gate_pass()` + `run()` 分派：`choose_gate_control` 选放行控件 → tap → 1.5s →
  `verify_at(to)`；选不出 → `gate_pass_unknown`（**不猜**，交人工点后 `--mark-step-done`）。
  `precompute_positions / simulate_stack` 补认 `gate_pass`（位置语义同 back/verify）。
  计划外门的 `_dismiss_gate` 逻辑一字未动。
- **B4 `stop_at_dialog` 显式分支** — `do_tap` 内 `_no_gate = step.gate or safety=="stop_at_dialog"`，
  到达判定循环与 `verify_at`（新增 `no_gate` 形参）全程不调 `choose_gate_control`；
  到达失败 → `arrival_unverified`（不放行、不重试点任何按钮）；到达成功的边真值加 `"safety":"stop_at_dialog"`。
  配对 back 步仍由 `do_back` 的取消词表关窗。
- **B5 `verify_signal` 消费 + 到达侧向导接受** — 新增 `verify_signal_hit()` 与 `sentinel_host_ok()`，
  `sentinel_check` 在 activity_suffix 分支之后先按 verify_signal 判强（三形态均要求宿主相符 +
  过 `visible_in_viewport` 可见性纪律；`view_id` 另过 `_app_id_hit` 排除 android: 系统 id）。
  宿主不符**不降档**，退回原弱哨兵路径（尺收敛判决不变）。
  `do_tap` 到达判定原本对 `ok and weak` 无条件熔断（与 `verify_at` 两把尺不一致），改成同两种接受：
  ① `--assume-at <node>` 一次性人工确认 ② `_is_wizard_node` 且宿主相符。
  同时给 `verify_at` 的向导接受补上宿主校验——「activity 已匹配即接受」本就是那条规则的原意。
- **B6 `suspect` 快路** — 新增 `Exec._suspect_fastpath()`，在 `do_tap` 的
  `control_not_found` 与 `arrival_unverified` 两个失败点前调用：`suspect` 非空时记
  `not_reproduced`（note 带 `suspect:<flags>`）+ 跳子树（`subtree_end` + `_jump_to`）续走，不熔断；
  arrival 失败那支额外做一次 BACK×≤2 的机械回位（探到起点即停）。
  唯一例外（覆盖优先于速度）：目标**未结账**且本步是它的**唯一结账步** → 仍走原熔断路径。
- **B7 `stop_if_settled`** — `run()` 开头（trip 闸之后）判 walk 顶层 `stop_if_settled` 是否已在
  `_ledger_settled()`，是则打印 `{"status":"walk_skipped_target_settled",…}`、存 state.status 后
  return（exit 0），一步不跑。
- **B8 到达后证据帧** — 新增 `Exec._evidence_post()`：到达判定成功后，若落点是 dialog 节点 /
  计划内门步 / 本步 `auto_transition`，补拍 `pending_shots/step{n}_{to}_post.png`（哨兵已命中的帧），
  边真值加 `"evidence_post"`。`_pre`（tap 后抢拍的转场帧）保留——两帧对照才说得清停在哪。
- **B9 词表可覆盖** — 7 个散落常量（`GATE_ID_RE/GATE_TEXT_OK/GATE_TEXT_NO/GATE_BODY_RE/
  GATE_BODY_NO/CANCEL_TEXT_OK/CANCEL_ID_RE`）收成 `UI_WORDS_DEFAULT` + 运行时表 `UI_WORDS`，
  新增 `load_ui_words(dir)`：`<dir>/ui_words.json` 存在则按同名键覆盖（正则键给字符串、加载时按
  `re.I` 编译；未知键忽略；坏 JSON 退默认），**幂等**（每次从默认表重建）。
  `choose_gate_control / choose_cancel_control` 改从 `UI_WORDS` 取值；`Exec.__init__` 调
  `load_ui_words(self.dir)` 并把生效的覆盖键留在 `self.ui_words_overridden`。

### 测试

`scripts/_tests/test_walk_exec_rules.py`（29 例，全部合成计划 + 合成 dump + FakeDev，**零 adb**）：
B1 违规拒绝 / 登录时间线拒绝 / backtrack 放行 / 后一 trip 与无 trip_id 免查；B2 文本归一与 `%s`
+ do_type 三条路径；B3 gate_pass 白名单与不猜、gate tap 步按 dialog 结账（含 B8 post 帧、门上不普查）；
B4 放行器在 stop_at_dialog 下零调用 + 边真值带 safety；B5 三形态判强/宿主不符仍弱/屏外不收/向导接受
与宿主不符仍熔断/assume-at 一次性；B6 两个失败点快路、唯一结账步仍熔断、无 suspect 行为不变；
B7 跳过与不跳过；B9 词表覆盖、正则键覆盖、Exec 自动加载、坏文件退默认。

### 未做 / 留给别人

- `precondition_kind`（type 步字段）执行器只透传不解释——它是计划器排步用的。
- `plan_edge_walk.py` 一行未动（并行分支在改，字段按上表产出即可对接）。
- 共享 CHANGELOG.md 未动（本文件即待并入项）。

# CHANGELOG（待并入主 CHANGELOG.md）· node_sweep 普查工具三处通用修复

> 本文件是子代理产出的**待并条目**，不动共享 `CHANGELOG.md`（并入时按日期插到 2026-09-09 节下）。
> 改动只落 `scripts/node_sweep.py` + 新增 `scripts/_tests/test_node_sweep_rules.py`。未 commit、未跑设备。

## 2026-09-09 · node_sweep：状态签名 / IME 感知回位 / position_lost 真值

归因来源：0909 安卓边遍历实测的三处执行器缺陷（全部与具体 app 无关，判据只吃 dump 属性 +
`dumpsys input_method` 输出 + 树/计划字段，零 hard code）。

### C1 页内状态切换识别 + 复位（治「判 noop 且不复位 → 下一条计划边打在错误分支」）

- 病灶：普查点了同宿主的**子 tab**，activity 不变、无新 window、结构签名
  （`DeviceAdapter.page_signature_from_dump` 只 hash 前 20 个节点的 text/rid）也不变
  → 判 `noop` → 按 NON_DESCENDING 不复位 → 页面被留在另一个子 tab，下一条计划边打在错误分支
  （实测：走了 1 次熔断 + 判读误判）。
- 新增模块级 `state_facts(xml)` / `state_signature(xml)`（**不改** blackbox_explore 的结构签名，
  两路正交）：状态签名 = 全部 `selected="true"` / `checked="true"` 节点的身份集
  （rid 短名优先，无 rid 退 bounds）+ 全量可见文本集 的 md5[:12]。正则解析，dump 截断也不崩。
- 新增模块级 `find_selected_sibling(xml, rid, bounds, max_levels=2)`：在 **tap 前的 dump** 里找被点
  元素同父下带选中/勾选态的兄弟（兄弟自身或其子树带态都算；直接父层没有就再向上爬 1 层；
  排除被点元素自身子树）。
- 元素循环：`noop` 判定成立但状态签名变了 → outcome 改记 **`state_switch_inplace`**，
  并加入 `NON_DESCENDING`（**绝不 BACK**，与 noop/toast_only 同路），随后前向 re-tap 那个兄弟复位、
  再 dump 比对状态签名：恢复 → `entry["restored"]=True`；未恢复或压根没兄弟 →
  `entry["state_left_changed"]=True` 且 manifest 顶层 `state_left_changed: true`。
  复位动作（`state_reset_sibling` / `state_reset_tap`）与状态差（`state_delta`：flags 前后 + 文本增减）
  全写进该元素的 ledger entry。
- 收尾兜底：仍在锚点页时，比对**进来/出去两次的选中集**（只比 flags，不比全量文本——动态内容不搅它），
  漂了同样置 `state_left_changed` 并输出 `exit_state_drift`（治「状态变化迟到、元素级判据没抓到」）。
- 口径不动：`coverage_complete` 仍 = 元素扫完 且 未丢位。状态被留在别处属**位置**问题，
  由 `state_left_changed` 单独承担，混进覆盖率会让调用方误以为要重扫元素。

### C2 回位阶梯先判 IME（治「第一下 BACK 被键盘吃掉 → 一路退到桌面」）

- 病灶：普查点到无标签功能键 → 进了带自动聚焦输入框的页 → 阶梯第一下 BACK 只收键盘不弹栈
  → 阶梯以为「按了没回来」继续按 → 把 app 退到桌面。
- 新增模块级 `ime_shown(dev)`（None-safe）与 `back_once_ime_aware(dev, stop_activity=None,
  stop_check=None)`：**每一次 BACK 之前**先查 `dumpsys input_method`，`mInputShown=true` 就先按一次
  BACK 专收键盘（计 `ime_closed_before_back`），**收完重新判 activity**——此刻若已在目标 activity
  （或 `stop_check` 成立）立即返回、不再按导航 BACK。
- 两条回位路都改走它：`land_act != parent_act` 的 4 次阶梯（`stop_activity=parent_act`）、
  同 activity 内 overlay 的单次 BACK（`stop_check` = 收完键盘后 dump 复核 on_page；
  未收键盘时不评估 → 正常路径零额外 dump）。
- 页首「枚举前收键盘」也收敛到 `ime_shown()`（顺带修掉 `dev.shell()` 返回 None 时的崩点）。

### C3 position_lost 真值（治「逃逸后被自愈重拉起，manifest 仍报 position_lost=false」）

- 病灶：逃逸发生在**回位阶梯里**（BACK 过冲退出 app），又被自愈重拉起；收尾自检看到 activity 与锚点
  相同就放过 → 账面 `position_lost=false`，调用方就地接力。
- 新增 `note_escape()`：**任何时刻** `dev.current_pkg() != a.package` 都当场
  `position_lost=True` 并追加 `escape_events: [{elem_slug, landing_pkg, landing_activity, where}]`；
  接入四个现场：tap 后 `escaped_app`、BACK 阶梯中途逃逸（`where=back_ladder`，本次新增探测点）、
  循环顶部位置守卫、收尾自检。
- 新增 `anchor_verified(xml)`：**activity 一路 + 哨兵/签名一路**双验证。`escaped_app` 重拉起分支只有
  双验证通过才允许把 `position_lost` 撤回 False，并记 `recovered_after_escape: true`（顶层 + entry）；
  原「回到宿主 activity → soft_return」分支保留（back_ok 仍为 True），但**不再撤回 position_lost**。

### manifest / stdout 新字段

`state_left_changed`(bool)、`exit_state_drift`(obj|null)、`escape_events`(list)、
`recovered_after_escape`(bool)、`ime_closed_before_back`(int)；
ledger entry 新增 `state_signature_before/after`、`state_delta`、`state_reset_sibling`、
`state_reset_tap`、`restored`、`state_left_changed`、`ime_closed_before_back`、
`escaped_during_back`、`recovered_after_escape`。新 outcome：`state_switch_inplace`。

### 测试

`scripts/_tests/test_node_sweep_rules.py` 9 项（合成 dump + 内存假设备，不碰 adb/模拟器）：
状态签名对 selected/尾部文本敏感而结构签名不敏感、同父 selected 兄弟查找、
state_switch_inplace 全流程（零 BACK + 复位回原 tab）、无兄弟时置顶层旗标、收尾漂移兜底、
`back_once_ime_aware` 两分支、阶梯不过冲（BACK 只按 2 下、没退到桌面）、
逃逸置 position_lost 且 activity 相同不抹掉、双验证通过才撤回。
`python3 -m pytest -q _tests` → **36 passed**（我开工时的基线 25 项 + 期间他人新增的
`test_state_inventory_timeline.py` 2 项，全部保持绿；新增 9 项）。

### 已知取舍

- 状态签名含**全量可见文本** → 异步刷新的列表页可能被判成 `state_switch_inplace`。后果可控：
  该 outcome 进 NON_DESCENDING（不 BACK），复位只会 re-tap 一个**当前已选中**的兄弟（本就是 noop）；
  真拿不准时置 `state_left_changed` 交调用方重判位——宁可多报一次，不骗调用方。
- 收尾漂移只比 flags，不比文本：文本一路留给元素级判据，避免动态内容刷屏式假阳。

## [2026-09-07] 热路径文本重构 + 三本账机械化（源侧已落地，**未 commit、未同步 ~/.agents/skills、未同步 codex**）

### 0. 一句话

把「模型每次都要读」的文本挪出热路径（按需机械注入），把「模型反复手抄」的账本交给脚本拼并反查——
**规则本体一字未改，判断仍归模型；改的是谁负责抄写、以及抄错了谁来发现。**

### 1. 动机（实证，AIPPT_830_test 跑次）

| 现象 | 数字 |
|---|---|
| 三轮全链路 19.5 h，34% 是两次 sub-agent 卡死；设备/机械只占 ~15% | 见 memory `vv-perf-baseline-and-plan-0907` |
| batch prompt 模板 60.7 KB，Phase B 里 58% 是只对特定页种类适用的条件段 | 本次 ① |
| 手写 batch manifest：24 份里 `findings[]` 共漏列 38 张工单；Phase 5 聚类只读 `findings[]` → 这 38 张对聚类隐形 | 本次 ③ |
| 自报 high/medium/low 计数与工单不符 40 处；**10 条 fail 页从没写过工单**（ManageRenewActivity 三轮 fail 零单） | 本次 ③ |
| fixer 手写 attempts.json 给 reviewer：212 个判断字段里 108 个是缩写改写版，reviewer 审的不是 §6 原文 | 本次 ④ |

### 2. 变更清单

#### 2.1 新增脚本（`scripts/`）

| 脚本 | 职责 | 输入 | 输出 | 退出码 | 接线点 |
|---|---|---|---|---|---|
| `fill_batch_prompt.py` | Phase 4 batch prompt 机械渲染：按 fact-tree 判定批内页种类，只注入用得着的条件段；填槽；内联本批 batches.json 片段（紧凑 JSON Lines） | batches.json、fact-tree、设备参数、可选 blocked/retry/b_gaps | `batches/<id>/prompt_round<N>.md` + `prompt_manifest.json`（注入凭证） | 0 / 2 输入错 / 3 渲染错（缺段文件、标记不齐、槽未填） | SKILL.md Phase 4；phase4-dispatch.md Step 4.A / 最小示例 / B 审核重派；sub-agent-batch-prompt.md 调用契约 |
| `page_status.py` | sub-agent 每页落判断账 `pages/<pid>.status.json`（合并写；elapsed 按桶合并） | `--status/--set/--elapsed/--json` | 每页一个小 JSON | 0 / 2 | sub-agent-batch-prompt.md B.7（挂页末已有 Bash 调用，零新增回合）；phase4-replay-judge.md J2 5.1 |
| `build_batch_manifest.py` | 从判断账 + `batch_notes.json` + 工单 frontmatter + 磁盘拼 manifest；**反查闸** | 批目录、batches.json、tree、fix 目录、截图目录 | `manifest.json`（含 `assembly_checks{hard,soft}`、`assembled_by`） | 0 / 20 有 hard 不一致（已落盘）/ 2 | sub-agent-batch-prompt.md Phase C；phase4-replay-judge.md J2 5.1 |
| `append_attempt.py` | fixer 的 §6 attempt 一次写、两处落（§6 块 + `docs/autofix-log/round-N/attempts.json`）；`--files-from-git`；`--check` 对账 | 工单路径、四个判断字段、改动文件 | 追加 §6 块；增/换 json 条目（history 从 §6 机械提取） | 0 / 1 check 不一致 / 2 / 3 无 §6 / 4 同轮已存在（`--replace`） | arkts-agents/visual-fixer.md；phase6-summary.md Step 6.7（派 reviewer 前 `--check`） |
| `render_round_summary.py` | 机械渲染 `_index.md / _summary.md / _delta.md`；模型只填「## 人工补充」 | 工单 frontmatter、batch manifest、tree、可选 `--extra` | 三份 md（机械段不出"完成/收敛/通过"） | 0 / 2 | SKILL.md Phase 6 步骤 1；phase6-summary.md Step 6.1–6.3；phase4-replay-judge.md J3 |
| `_tests/test_fill_batch_prompt.py` | 25 项单测 | — | — | — | — |
| `_tests/test_ledgers.py` | 37 项单测（page_status / build_batch_manifest / append_attempt / render_round_summary / skeleton `--from-json`） | — | — | — | — |

#### 2.2 新增参考文件（`references/`）

| 文件 | 内容 | 来源 | 何时被加载 |
|---|---|---|---|
| `batch-sections/NAV-compose.md`（2 KB） | Compose 导航规则段 | 自 sub-agent-batch-prompt.md 逐字拆出 | nav_mode==compose 时由 fill_batch_prompt 注入 |
| `batch-sections/B0.5-via-variant.md`（5.6 KB） | B.0.5 反哺节点特殊导航 | 同上 | 批内含 `#via=` 页 |
| `batch-sections/B0.6-dialog.md`（2.9 KB） | B.0.6 dialog 对比特殊路径 | 同上 | 批内含 tree.dialogs[] 页 |
| `batch-sections/B1-data-state.md`（1.6 KB） | B.1 数据态自愈梯 | 同上 | 批内页带 state_required/vip_required 前置 |
| `batch-sections/B4.5-dual-oracle.md`（14.8 KB） | B.4.5 功能点双 oracle 判定 | 同上 | 批内页带 functional_checks[] |
| `phase2-page-dispatcher.md`（7 KB） | 页粒度 dispatcher 兜底模式全文（架构/职责/触发/步骤 0,1,3,4/BLOCKED schema/产物） | 自 SKILL.md Phase 2 逐字迁出（步骤 2/2.5 两模式共用，留在 SKILL.md） | `dispatch_phase2_batches.sh --plan-only` stderr 点名；routes.json / check_android_screenshot.sh 兜底文案指向 |
| `rationale-log.md`（7 KB） | 9 段纯叙事（事故实录/为什么）原文归档 | 自 SKILL.md / phase1-prepare / phase2-edge-walk / phase4-replay-run 迁出 | 不在任何必读清单 |

#### 2.3 修改的文件（逐文件 hunk 摘要）

| 文件 | 改动 |
|---|---|
| `SKILL.md` | frontmatter 登记 7 个新 reference；Phase 2：dispatcher 块（50 行）迁出→5 行指针，步骤 2/2.5 改为「trip 态建立（两模式共用）」段；5 处纯叙事→rationale-log 指针；Phase 4：加 `fill_batch_prompt.py` 渲染命令块 + B.7/Phase C 一行；Phase 6 步骤 1：三份汇总改为 `render_round_summary.py` 渲染 |
| `references/sub-agent-batch-prompt.md` | 5 个条件段→`<!-- SECTION:… -->` 标记；文件头加「渲染方式」说明；输入槽位 `blocked_pages_json / retry_edges_json / b_gaps_json / retry_reason / batch_json_inline`；删 B.6 墓碑块（18 行）留 1 行；B.7 改为 `page_status.py`；Phase C 改为 `build_batch_manifest.py`（原 schema 保留作字段参考）；role=judge 块改为同一套账目流程；写单铁律 CLI 加 `--from-json`；尾段「调用契约」改为脚本调用 |
| `references/phase4-dispatch.md` | 主循环 `render(...)` 伪代码、最小示例 `render_template(...)`、B 审核重派 `render_a_retry(...)` 三处→`fill_batch_prompt.py` 调用 |
| `references/phase4-replay-judge.md` | J2 第 1 条加 `--from-json`；新增 5.1 账目机械化（page_status / batch_notes / build_batch_manifest）；J3 汇总改为 `render_round_summary.py` |
| `references/phase4-classify-write.md` | 第 3 行加 `--from-json` 说明 |
| `references/phase6-summary.md` | Step 6.1 前加渲染器说明（6.1–6.3 模板保留作格式参考）；Step 6.7 硬闸前加 `append_attempt.py --check` |
| `references/phase2-edge-walk.md` | §2 指针改为「trip 态建立（两模式共用）」段；§8 加 dispatcher 文档去向；判读制标题演进史→rationale-log |
| `references/phase1-prepare.md` | 1.1.d 历史块、ad_profile 实爆段→rationale-log（规则句留原位） |
| `references/phase4-replay-run.md` | §5.95 冒烟实测报告整节→rationale-log，留 1 行去向 |
| `scripts/validate_batch_output.py` | 新增 `prompt_sections` 闸（按树复算条件段⇄`prompt_manifest.json`，judge 角色豁免，`--no-prompt-gate`）；新增 `assembly_hard_checks` issue（透传拼装器 hard）；`manifest_hand_written` issue（`--no-ledger-gate` 降 warning） |
| `scripts/render_finding_skeleton.py` | 新增 `--from-json`：差异项 description/root_cause_hint/actual/element/region/category 原文灌 §3、expected 原文灌 §2、evidence 并入；指针「SKILL.md §4 Phase 2」→`phase2-page-dispatcher.md` |
| `scripts/dispatch_phase2_batches.sh` | `--plan-only` stderr 点名 `phase2-page-dispatcher.md` 必读 |
| `scripts/check_android_screenshot.sh` | 2 处兜底文案「SKILL.md §Phase2 BLOCKED 表」→`phase2-page-dispatcher.md §BLOCKED schema` |
| `scripts/blocked_reason_routes.json` | 3 处 `doc` 指针同上 |
| `arkts-agents/agents/visual-fixer.md`（**skill 目录外**） | attempts.json 手写块→`append_attempt.py` 一次写两处 + Step 5 出口 `--check`；旧块保留作字段参考并标「已被替代」 |

#### 2.4 删除的内容（文本保全核对逐行列过，共 65 行，全部属以下三类）

- sub-agent-batch-prompt.md：B.6 墓碑块 18 行（内容已由铁律 R8 承载）；旧「调用契约」python 示例 14 行（换成脚本调用）；5 行 schema 行换成槽位行
- phase4-dispatch.md：`render(...)` 伪代码 17 行（换成脚本调用注释）
- 各文档被改写的指针/标题行 ≈11 行（旧文在 rationale-log 或新文件里逐字可查）

### 3. 行为变化（默认生效的，运行前必知）

| 变化 | 谁受影响 | 逃生口 |
|---|---|---|
| Phase 4 batch prompt **必须**经 `fill_batch_prompt.py` 渲染；手工拼 prompt 派发会被 validate 判 `prompt_sections` FAIL | 主会话 | `validate_batch_output.py --no-prompt-gate`（仅调试） |
| batch manifest **必须**经 `build_batch_manifest.py` 拼装；手写（无 `assembled_by`）判 `manifest_hand_written` issue；拼装器 hard 不一致透传成 `assembly_hard_checks` issue | 页粒度 sub-agent、judge sub-agent | `--no-ledger-gate`（过渡/调试） |
| fixer 的 §6 attempt 与 attempts.json 由 `append_attempt.py` 产；Step 6.7 派 reviewer 前 `--check` 不齐 exit 1 | visual-fixer、主会话 | 无（对账不齐就是备料失败） |
| `_index/_summary/_delta` 由脚本渲染；机械段不出结论用语；模型只写「人工补充」 | 主会话 | `--dry-run` |
| 被省略的条件段在 prompt 里留一行说明 + 逃生口（遇到该类页记 `fatal_error=prompt_section_missing` 上报） | sub-agent | — |
| SKILL.md 主会话读量 −5 KB；batch prompt 每批 −137~−162 行 / −3.9~−8.6 KB（AIPPT 实测 7 批） | 主会话、sub-agent | — |

### 4. 验证

- 单测：`test_fill_batch_prompt.py` 25/25、`test_ledgers.py` 37/37、既有 `test_hit_chain_probe.py` 19/19
- AIPPT_830_test 离线回放（scratchpad 镜像，不占设备、不碰项目）：
  - `fill_batch_prompt.py`：7 批全部渲染成功，零残留标记；每批 51.0–55.8 KB vs 旧 59.7 KB
  - `build_batch_manifest.py`：24 份手写 manifest 拆成判断账重拼，**多找回 38 张漏列工单**，40 处计数不符，**10 条 fail 页零工单**（hard，属真漏）；宿主页 fail 经跨 manifest 宿主关联放行
  - `append_attempt.py`：`--check` 三轮 28/28、16/16、12/12 一致；往返重写 §6 文本仅差 1 空行；attempts.json 字段变为逐字原文（手写版 108/212 为缩写）
  - `render_round_summary.py`：三轮合计数与文件数一致（45/30/27，含 `_systemic/`）；`_delta` fixed/new/regressed 与手写版逐条一致（9/6/0）
- 文本保全：`scratchpad/check_text_refactor.py`（多重集差）——被删 65 行逐条列出，全属 §2.4；374 行搬迁差集为零
- 链接完整性：无新悬空（既有悬空 `page-identity.md` 与本次无关）

### 5. 纠正记录（本次分析中我先说错、被回放纠正的三条，防止以后再引用）

1. 「fix_files 11 条路径不存在」——错，10/10 存在（度量时 cwd 用错）
2. 「attempts.json 与 §6 三轮不一致」——错，含 `_systemic/` 后三轮一致；真问题是**内容缩写**（108/212）
3. 「_summary 合计漂移 45 vs 43」——错，手写合计含 2 张 systemic，是对的

### 6. 未做 / 已知限制

- 时间收益未实测（回放离线，仅字节估算 ~30–40 min/次）；需 S0 打点后跑真项目
- codex 侧 `render_report.py` + `assert_round_complete.py`（整轮闸、`run_state.json`）未移植到 CC
- `fix-file-schema.md`（judge 每批必读 51 KB，20 KB 示例）未拆
- B.4.5 内部按 check 属性（WebView / verify_by=outcome / enum_group）再拆一层未做
- 回放脚本未固化成 `_tests/replay_ledgers.py`（现为会话内临时脚本）
- 既有悬空引用 `references/page-identity.md`（android-navigation-playbook.md 引用）未处理

### 7. 同步到 codex 的指引（`ArkTs-Core/codex/skills/arkts-visual-verify/`）

⚠️ **禁止跑 codex-adapter 全量重建**：codex 侧有 11 个源侧没有的脚本（`assert_round_complete / assert_gap_ticket_coverage / check_fix_schema / check_reviewer_report / resolve_hmos_impl / render_report / carry_forward_findings / device_triage / smoke_one_page / lib_tools / lib_image`）与 `compile_replay_plan.py` 105 行独有逻辑，重建会回滚它们。按「(双侧)」提交惯例逐文件/逐 hunk 挪：

**A. 原样复制（先过 codex 侧的 Windows 编码垫片惯例：文件头加 `sys.platform.startswith("win")` reconfigure、`open()` 带 `encoding="utf-8"`——本次新脚本已全部显式 `encoding="utf-8"`，垫片按 codex 现有脚本样式补）**
- `scripts/fill_batch_prompt.py`、`page_status.py`、`build_batch_manifest.py`、`append_attempt.py`、`render_round_summary.py`
- `scripts/_tests/test_fill_batch_prompt.py`、`test_ledgers.py`
- `references/batch-sections/*.md`（5 个）、`references/phase2-page-dispatcher.md`、`references/rationale-log.md`

**B. 逐 hunk 移植（codex 侧同名文件已有平台差异，不能整文件覆盖）**
- `SKILL.md`：§2.3 表里列的 6 处 hunk。注意 codex 侧 `$SKILLS_ROOT` 根是 `~/.agents/skills`，命令示例照 codex 写法（`python` 而非 `python3` 的 Windows 注）
- `references/sub-agent-batch-prompt.md`：标记/槽位/B.7/Phase C/judge 块/写单铁律/调用契约；codex 版含 Join 协议 banner，别覆盖
- `references/phase4-dispatch.md`、`phase4-replay-judge.md`、`phase4-classify-write.md`、`phase6-summary.md`、`phase2-edge-walk.md`、`phase1-prepare.md`、`phase4-replay-run.md`：按 §2.3 摘要定位 hunk
- `scripts/validate_batch_output.py`：三段（prompt_sections / assembly_hard_checks / manifest_hand_written + 两个开关）；codex 版含 Windows 垫片，别整文件覆盖
- `scripts/render_finding_skeleton.py`：`--from-json` 三处 + 指针一处
- `scripts/check_android_screenshot.sh` → codex 是 `check_android_screenshot.py`：改同义文案两处
- `scripts/dispatch_phase2_batches.sh` → codex 是 `dispatch_phase2_batches.py`：加同一行 stderr 提示
- `scripts/blocked_reason_routes.json`：3 处 `doc`
- `arkts-agents/agents/visual-fixer.md` → codex 对应 `.codex/agents/visual-fixer.toml` 或同名 md：把 attempts 段换成 `append_attempt.py`

**C. codex 侧特有差异要顺手处理**
- `fill_batch_prompt.py` 的 `HERE`/`ARKTS_SKILL_DIR` 逻辑与 `fill_chunk_prompt.py` 相同，Nuitka 打包态可用
- 派发语法：文档里 `Agent(...)` 在 codex 侧写作 `spawn_agent(...)`（codex 版 SKILL.md banner 已约定），本次新增的说明文字里没有 `Agent(` 字样，无需改
- `check_scratch_pollution.sh` 在 codex 侧仍是 `.sh`（adapter 漏转，本次未处理）

**D. 移植后验证**
```bash
python scripts/_tests/test_fill_batch_prompt.py && python scripts/_tests/test_ledgers.py
# 有历史跑次时：把该跑次 spec/ 镜像到临时目录，对每份手写 manifest 拆判断账→build_batch_manifest --compare-legacy，看漏列/hard
```

### 8. 回滚

- 源侧：`git checkout -- arkts-skills/skills/arkts-visual-verify arkts-agents/agents/visual-fixer.md && git clean -fd arkts-skills/skills/arkts-visual-verify`
- `~/.agents/skills/arkts-visual-verify`：同步前的完整快照 `scratchpad/arkts-visual-verify.global-pre-sync-0907.tar.gz`（会话级目录，需长期保留请另存）

### 9. 安装 / 同步到 `~/.agents/skills`

验收通过后：`rsync -a --exclude='__pycache__' --exclude='.DS_Store' arkts-skills/skills/arkts-visual-verify/ ~/.agents/skills/arkts-visual-verify/`
（不带 `--delete`，保留全局目录里的 `.pre-winport-0815/` 备份）

---

## [2026-09-07 晚] N7/N2/N3/N5：判断账时间戳与完成声明、页粒度续跑、systemic 候选器、reviewer 预检（源侧已落地，未 commit）

### 0. 一句话
把「哪一页做完了」「哪些单该聚成一根」「哪个 attempt 是空手过场」三件事里**可机械判的部分**交给脚本，模型只做剩下的判断；
每一项都在 830 产物上先回放过再接线。顺带发现两处此前不可见的病：`category_pattern` 33/35 缺失、need-info.json 三轮三种手写形状。

### 1. 变更清单
| 项 | 新增 | 修改 | 机制与护栏 |
|---|---|---|---|
| **N7** 判断账时间戳 | — | `scripts/page_status.py`：每次写入记 `_ts_first/_ts_last/_writes`，`--done` 时记 `_ts_done` | S0 页级时间线零额外插桩（`prompt_manifest.rendered_at` = 派发起点） |
| **N2** 完成声明 + 页粒度续跑 | `scripts/lib_ledger.py`（完成判定唯一定义：done=true 且按 status 证据齐——compared 页有 round-N 截图/sbs、fail 有工单或 blocked_by、blocked 有占位） | `page_status.py --done --round N --trip T`（脚本当场核验，不过 exit 3 且**不置 done**）；`fill_batch_prompt.py --resume`（只把 done 且证据齐的页列为已完成，其余重做；凭证 `prompt_manifest.resume`）；模板加 `{resume_block}` 槽；B.7 加完成声明规则；phase4-dispatch 重派改 `--resume` | **只证伪不代判**：没标 done 的页一律重做（宁可重做不可漏）；模型不可能把没证据的页标成完成 |
| **N3** systemic 候选器 | `scripts/cluster_systemic_candidates.py` → `spec/fix/round-N/_systemic_candidates.json` | `phase5-systemic.md` 先跑候选器；`render_finding_skeleton.py` **`--category-pattern` 必填**（缺则 exit 2 并按 id 给建议值）；SKILL.md Phase 5 一句 | A 规则=文档正规则（同 pattern 跨 ≥2 批 ≥3 页）；B 启发式仅在 pattern 缺失时按 id 的 diff_kind/slug 词元出提示簇；候选是超集，主会话逐簇判同根因；报告缺失率 |
| **N5** reviewer 预检 | `scripts/precheck_attempts.py` → `docs/autofix-log/round-N/attempts_precheck.json` | `phase6-summary.md` Step 6.7 派 reviewer 前跑；`visual-fixer-reviewer.md` 新输入 `precheck_json_path`（flags 直接采信、`reviewer_can_skip` 免做 Check 1、`near_duplicate` 只是提示） | 兼容 `git diff` 与 `diff -ruN` 两种 patch 头；duplicate 只判归一化后**完全相同**，相似度≥0.9 只给 hint；need-info.json 核 Check 4 所需字段 |
| 测试 | `_tests/test_ledgers.py` 37→**49** 项 | — | — |

### 2. 830 回放实证
- N7/N2：round-0 39 页跑 `--done`：**37 通过，2 拒绝**——正是该轮两条「fail 却零工单」的页（HomeActivity#via=导入文档、ManageRenewActivity）；`--resume` 对 trip_2 batch_01 得 7 完成 / 1 待做，与 `--done` 结果一致
- N3：`category_pattern` 缺失率 round-0/1/2 = **100% / 92% / 80%** → 正规则零候选；启发式对已有 SYSTEMIC 单的召回：`guide-progress-state-drift` 4/4（两轮）、`nav-back-layout-drift` 4/7（其余 3 张是模型按语义并入的，脚本不代判）
- N5：三轮 56 个 attempt 预检 **0 硬 flag**，与 reviewer 报告一致（reviewer 只抓到语义类 wrong_edit/lazy_escalation）；round-0 patch 是 `diff -ruN` 格式，解析出 40 个文件；**need-info.json 三轮三种形状，均缺 Check 4 所需的 `info_type/exhaustion`**——reviewer Check 4 从未能按其算法执行

### 3. 行为变化
- 骨架产 ALIGN/CRASH/URL 单**必须**带 `--category-pattern`（SYSTEMIC/BLOCKED 除外）——judge 出单命令要补这一参数，错误信息里给了按 id 推的建议值
- 页只有经 `--done` 校验通过才会在续跑时被跳过；重派一律 `fill_batch_prompt.py --resume`
- Step 6.7 派 reviewer 前多两条脚本（`append_attempt.py --check`、`precheck_attempts.py`），后者不阻断派发

### 4. 新发现的待办
- need-info.json 需要像 attempts 一样有机械写入器 + 固定 schema（`report_need_info.py`），否则 reviewer Check 4 永远跑不了
- 历史轮次的 `category_pattern` 可用 `_systemic_candidates.json` 的 B 簇辅助人工回填（不自动改单）

### 5. codex 同步补充（在上一节 §7 基础上）
- A 类新增：`scripts/lib_ledger.py`、`precheck_attempts.py`、`cluster_systemic_candidates.py`
- B 类新增 hunk：`page_status.py`（--done/时间戳）、`fill_batch_prompt.py`（--resume）、`render_finding_skeleton.py`（category_pattern 必填）、`sub-agent-batch-prompt.md`（B.7 完成声明 + `{resume_block}`）、`phase4-dispatch.md`、`phase5-systemic.md`、`phase6-summary.md`、`SKILL.md`、`arkts-agents/agents/visual-fixer-reviewer.md`（codex 侧对应 `.codex/agents/visual-fixer-reviewer.*`）

---

## [2026-09-07 夜] N3-b：category_pattern 机械推导 + 项目映射表 + 置信度门槛聚类（源侧已落地，未 commit）

### 0. 一句话
judge 不再给 systemic 聚类起名：`category_pattern = <diff_kind>__<concept>` 由骨架从差异项元素/描述/rid **机械推导**（概念词典 + 从安卓 dump
自动扫出的项目映射表），写入置信度；聚类只吃 high/medium，不确定的不聚——**宁可多出几张单，不漏**。零人工确认环节。

### 1. 根因纠正
830 里 96/99 张单缺 `category_pattern` 的直接原因是**骨架此前根本不往 frontmatter 写这个字段**（`--category-pattern` 收了不写）——不是 judge 忘传。本次一并修。

### 2. 变更清单
| 新增/修改 | 内容 |
|---|---|
| `scripts/build_pattern_vocab.py`（新） | 扫 `screenshots/android/**/*.android.xml` 的 resource-id/class/屏幕带位 → 概念映射表 `spec/visual-verify/category-patterns.json`。词元级匹配（`feedback` 不再命中 `back`），必须词典命中才映射，navheader.*/tab_bar 带位硬门控；仅启发的进 `needs_confirm`（**不参与推导**），其余 `unmapped` |
| `scripts/derive_pattern.py`（新） | 三级推导：rid→项目映射 > 文本词元（id slug / element / 中文描述）→概念词典 > `other:<slug>`；`derive_for_skeleton()` 供骨架；`--round` 批量推导（回填/验收）；映射表缺失时词典兜底 |
| `scripts/render_finding_skeleton.py` | 自动推导并写 `category_pattern / category_pattern_confidence / category_pattern_source` 三行；`--category-pattern` 改为可选覆盖（给了也归一）；推不出 → `other:` **不拦单**（撤回上一节的"缺则拒产"） |
| `scripts/build_batch_manifest.py` | findings[] 带 `category_pattern_confidence`、`hmos_locus`（suggested_files 的 .ets） |
| `scripts/cluster_systemic_candidates.py` | A 完整键：high/medium；A2 概念级（跨 diff_kind 同部位）：仅 high；low/other → `unclustered`；id 词元启发式 → `hints`（不是候选）；`--derived` 回填历史轮 |
| 文档 | SKILL.md Phase 3.5 加"建批前生成映射表" + Phase 5 门槛；phase5-systemic.md；phase4-classify-write.md；sub-agent-batch-prompt.md 写单铁律 CLI 行 |
| 测试 | `_tests/test_ledgers.py` 49→**58** 项（词表生成/推导/骨架自动填/门槛聚类） |

### 3. 830 验收
- 映射表：172 rid → 105 映射 / 9 needs_confirm / 58 unmapped（装饰 View）；`navheader.back`={iv_back, iv_close_page}，`navheader`={titleBar}，`progress_indicator`={include_step, indicator_container, donut_progress, indicator_view}
- 推导：三轮 35 张 ALIGN 单 **35/35 得到概念，0 张 other**（high 28 / medium 6 / low 1）
- 聚类（带门槛）：round-0 `nav-back-layout-drift` **7/7**、`guide-progress-state-drift` **4/4**（误并 1：启动页加载进度条，作为候选交模型判）；round-1 4/4；低置信 1 张进 unclustered
- 骨架四条路径冒烟：--from-json 自动推导 / 旧式显式值归一 / 推不出 other 不拦 / 项目映射表 rid 直接命中

### 4. 边界
词表统一的是"哪个部位、什么偏差"的**叫法**，不是根因判断；候选仍是超集、模型逐簇确认。`needs_confirm` 只是记录，若想提升 rid 命中率可人工把条目搬进 `confirmed`（可选，不是流程环节）。

### 5. codex 同步补充
A 类新增：`build_pattern_vocab.py`、`derive_pattern.py`；B 类 hunk：`render_finding_skeleton.py`（推导块 + frontmatter 三行）、`build_batch_manifest.py`、`cluster_systemic_candidates.py`、SKILL.md（Phase 3.5/5）、phase5-systemic.md、phase4-classify-write.md、sub-agent-batch-prompt.md。

---

## [2026-09-08] N5-b：need-info（C.6 报缺）机械写入 + 校验（离线实验通过，源侧已落地，未 commit）

### 0. 一句话
fixer 的「报缺」改由 `report_need_info.py` 写入，写入前按 visual-fixer.md §C.6 既有 schema 当场核验（白名单 / 先修后问 / 参考文件覆盖），
不过不落盘；precheck 与 `_summary.md` 复用同一校验器。reviewer Check 4 第一次有了可核验的输入。

### 1. 变更清单
| 新增/修改 | 内容 |
|---|---|
| `scripts/report_need_info.py`（新） | 写入口 + `--check`：`info_type` 五值白名单；`prior_attempts` 须在本轮 attempts.json、改动文件非占位、未被预检标 empty_diff（缺省=本单本轮 attempt）；`searched_refs` 须覆盖 §1 三份参考文件中**存在的**那几份（缺失不阻塞，照 §1 原话）；落盘为 schema 规定的列表形状 + `_written_by`；同 finding 重报覆盖 |
| `scripts/precheck_attempts.py` | need-info 逐条复用 `validate_item`：无效/手写条目逐条 flag `lazy_escalation` 进 `need_info.results`（此前只报"缺键"） |
| `scripts/render_round_summary.py` | 新增 `## NEED_INFO` 段：按 (类型, 请求) 去重，列阻塞的单、先修证据、校验结论；手写/无效标 ⛔ 不代问 |
| 文档 | `arkts-agents/agents/visual-fixer.md` C.6 第 3 条改经脚本；`visual-fixer-reviewer.md` Check 4 采信预检结果、只判语义；`phase6-summary.md` Step 6.7 注释 |
| 测试 | `_tests/test_ledgers.py` 58→**67** 项 |

### 2. 离线实验（830 镜像，不改流程文件先做的）
- `--check` 三轮历史 need-info：**12/12 无效**（缺 finding_id / blocked_layer / info_type…，三轮三种键名）
- 先修后问：round-0 三条报缺关联的单**本轮零 attempt** → 写入被拒（与当轮 reviewer 抓到的 2 条 lazy_escalation 同向，但依据不同：reviewer 判"源码可推导"，脚本判"没先修"）；round-2 三张单有真实 attempt → 通过
- 白名单：`api_contract`（源码可查的东西）被拒；参考文件存在时漏一份被拒、两份都覆盖通过
- 历史 round-2 的 6 条手写报缺里混着「固化首页 VIP 图标 reach_path」这类**内部工作**——白名单会挡住
- `_summary` NEED_INFO 段：脚本写的一条 = "backend_env｜服务端代签契约与联调地址…｜3 张单｜✅ 合规"；历史手写全部 ⛔

### 3. 效果与边界
- 效果：Check 4 可执行；懒惰升级在写入时被挡而非事后审；用户每轮拿到去重后的"需要外部提供什么"清单（830 那个支付签名阻塞跨三轮三种格式，规范后是一行）
- 边界：脚本只判事实（存在/非空/覆盖），"信息是否源码可推导"仍归 reviewer；fixer 是否真会调脚本只有活跑才知道——手写文件会被判无效并 flag，这是唯一的机械保障
- 未做：round_budget 的停滞诊断不识别"等外部信息"；主线程"代问用户"后停轮的接线

### 4. codex 同步补充
A 类新增：`report_need_info.py`；B 类 hunk：`precheck_attempts.py`、`render_round_summary.py`、`visual-fixer.md`、`visual-fixer-reviewer.md`、`phase6-summary.md`。

## 5. 2026-09-08 计划器 tab/embed 修复 + 去 AIPPT 硬编码 + 树覆盖率门（分支 exp/plan-tab-rule，待验收）

### 5.1 计划器（plan_edge_walk.py / walk_exec.py）
- 根因：`main_root` 恒退化成 launcher（上游只给 launcher 标 activity_root）→ 宿主→tab 边全判 embed
  且不下钻 → 830 树 20/45 目标静默缺口，硬盘 4 份计划同病。
- R2 判据：起点==tab_host（tab 节点点击证据边的众数起点）→ tab_switch；否则有点击证据（非占位文案/非
  容器 view id）且方法名不含装载特征 → tab_switch；其余 embed。`main_root` 不动。
- embed 改 verify+首达下钻；有 tab_host 时深层 embed 撞到宿主 tab 只 verify（首达留给宿主）。
- skip_destructive 边计划不下钻（子树落 gap 交页粒度/scenario）+ walk_exec 补分支（此前没有这个分支，
  RefundProgressActivity 进页即真退订会被机械点进）。
- 步序带 `static_rid`（树边 trigger_view_id）；执行器定位顺序 runtime rid > static_rid > 文案。
- 向导链重建按 (wizard_index, id) 排序、冲突首个为准（旧实现随 PYTHONHASHSEED 变，AntennaPod 树三次
  跑 gap 18/20/18）。
- `spec/visual-verify/vocab_overrides.json`：项目专属破坏性/确认/loading/返回控件词表，不改代码。
- 回归：830 24→41/50（砍退款子树 4 页故意）、mock 11→34/41、0906 52→63/63、0826 与 glm 48→65/83；
  AntennaPod/DiceRoller 输出逐字节相同；`_tests/test_plan_tab_rule.py` 12 例。

### 5.2 去 AIPPT 硬编码（verify 侧）
- 新增 `lib_tree_struct.py`：首启链 / 主容器 / 登录页 / 项目词袋全从树结构推导；`_tests/test_lib_tree_struct.py`。
- `trip_assign.py`：首启链与登录页先取树结构；名字白名单去掉 LaunchAgreement。
- `node_sweep.py` / `capture_page_e2e.py` / `hmos_capture_page_e2e.py`：链页判定 = 树结构 ∪ 通用前缀；
  hmos 的 B.0.5 词袋 = 通用基础词 ∪ 树机械提取的项目词（曾写死 PPT/模版/作品）。
- `build_batches.py`：launcher 取 manifest 真值（树标 activity_root 或无入边时）→ 通用语义名；trip_2
  起点取主容器（承载最多 tab/宿主子页的 Activity）→ Home/Main 语义名；不再写死 SplashActivity/HomeActivity。
- `phase2_scope.py`：`dead_code_hint`（indexer/2.4 全仓零引用线索）与 dead_code 同权。
- `build_judge_input.py`：帮助文案去 app 名。

### 5.3 Phase 1 新门
- `references/phase1-prepare.md` Step 1.0.7：`tree_coverage_report.py --gate`，残树打回树侧。

### 5.4 未做 / 边界
- 执行器改动只有单元测试，未上真机。
- E2（边文案）机械上限：AIPPT 42% / AntennaPod 13%（菜单处理器、抽屉 RecyclerView、动态文案），
  由 LLM 阶段 2.5 按记分卡待补清单补。
- codex 版 / ~/.claude 版未同步（按 §7 逐 hunk）。

### 5.5 2026-09-08（下午）富化产物闸收紧
- `check_prereq_freshness.sh` (c) navnet 只认可机械执行的边（真文案 / 非容器 view id / 契约 trigger_actions 带 label）；
  机械候选（Phase 2.4）恒非空，旧口径会让无文案的树刷满 navnet。AIPPT 纯机械树 navnet 由 ~100% 回到 34%（NEED），
  830 LLM 树仍 PASS（96%）。

## 2026-09-08（夜）计划器/执行器消费树的语义字段（试点核定）
- `plan_edge_walk.py`：`needs_discovery` 认占位串（`trigger_label_unknown` 曾被当真文案，旧树 41 页"可执行"是假象）；
  读 `trigger_kind`：auto/back/async_after_tap → wait-first 不是探索，list_item/span/tap 带控件 id 即可执行；步序携带
  `trigger_kind` / `wait_hint` / `span_text` / `item_rid` / `trigger_owner_page`；walkability 非 walkable 的 record 不进目标集
  不算孤儿（`excluded_non_walkable`）。
- `walk_exec.py`：`find_span_point`（ClickableSpan 按子串位置定点）、`item_rid` 与反哺 rid 同级、`wait_attempts` 按 `wait_hint` 换算等待预算。
- `phase2_scope.py`：walkability dead/abstract/external_entry 与 dead_code_hint 同权。
- 试点树实测：切片 22 可走页 → 16 可执行 / 5 投机（切片边界）/ 零边需现场探索；无字段同树 1/22。

## 2026-09-08（深夜）
- `plan_edge_walk.py`：wizard 边读 contract 的 `exit_action_to_next.resource_id`（来自机械 wizard_exit_controls），`exit_unresolved` → 需探索
  而非自动跳转；external_entry 页有可解析深链 → `walk_5_deeplink_<id>` 一步 `am start -d` 直达（占位符未解析的留 `deeplink_unresolved`）。
- `walk_exec.py`：新增 `deeplink` 动作（am start VIEW + verify + settle），位置模拟/栈模拟认 deeplink。

## 2026-09-09 边行走时间账（用户拍板「先加计时再走安卓」；纯记账，不改任何行为）
- `walk_exec.py`：每步 `state.step_times[]{step,action,from,to,t_s,ended_at}`（机械+设备耗时）；熔断记 `escalated_at`/`step_elapsed_s`，
  `--resume` 时结算 `state.llm_gaps[]{step,reason,llm_s}`（熔断→恢复 = LLM 处置时长）；边真值条目补 `t_s`/`ts`（`stamp_timing`，writeback 不读）。
- `walk_ledger.py`：`at` 旁加绝对时刻 `ts`（coldstart/settle/pending_bindings 共 4 处）；账本缺 `t0` 时兜底。★830 那份 ledger 的 `at`/`cost_s`
  全 0 是重建账本（check_replay/walk_place_baselines 一次性写入）所致，相对时间不可信，以后只看 `ts`。
- 新 `walk_timing.py <edgewalk_dir> [--json]`：机械/LLM/空转三分账 + 按动作、按熔断原因、最慢五步、边真值计数；`walk_finalize.sh`
  收尾打印它（信息，不判定）。单测 `_tests/test_walk_timing.py` 2 项；vv 全套 20+19 绿。

## 2026-09-09 walk_3 孤儿探测重做 + 普查落点接回树（用户审核通过的四步）
- 新 `lib_landing.py`：落点 → 树节点。Activity 匹配为前提，`layout_facts.discriminators` 投票，弹窗 > 子页 > Activity，
  同层平票返回 None（歧义宁缺）。`node_sweep.py` / `blackbox_explore.py --tree` 每次 tap 后写 `landing_node`（老字段全保留）。
- `materialize_blackbox_to_factree.py`：落点解析成树内已知节点且 ≠ 父页 → 给该节点追加 inbound_triggers
  （source=blackbox_discovery，rid/文案来自真机，runtime confirmed，按 (from_page, rid|text) 幂等），落地截图+dump 当该节点首达基线，
  `--ledger` 给了就记 settled（identity_by=landing_node_vote）；解析不出/歧义/落点=父页照旧造 `#via` 变体。普查点到孤儿即闭环。
- `plan_edge_walk.py` 不再静态生成 walk_3；新 `plan_orphan_probe.py --tree --dir`：finalize 回填后重算孤儿（剔 dead/abstract/external、
  settled、有活入边），剩余才生成 walk_3，每个孤儿带 `candidates`（从 `walkability.facts.instantiation_examples` 反查引用它的页面）与
  discriminators；`walk_exec.py` 的 probe 熔断包携带 targets/candidates/protocol，LLM 定向探索，禁 am start 硬拉。
  `walk_finalize.sh` 5.7 步调用（dry-run 跳过）。
- 单测 `_tests/test_landing_and_orphan.py` 3 项（投票层级/平票/挂回幂等/孤儿重算与候选）；vv 全套 23+19 绿。
  AIPPT 0909 树与机械树 dry-run：孤儿 0，walk_3 不排。

## 2026-09-09（下午）范围事实源收口：撤 walkability 过滤、删 walk_5（用户拍板「安卓走到什么，鸿蒙就走什么」）
- `phase2_scope.py`：撤回 0908 加的「walkability dead/abstract/external_entry 视同死码」——范围的唯一事实源是安卓 ledger 的 settled + 边真值；
  静态可走性只剩两个用途：计划器出计划时跳过抽象类/零引用死码省探测、报告解释「为什么没到」。普查点到「外部拉起」页并结账后鸿蒙照比。
- `plan_edge_walk.py`：删 walk_5 深链走（外部拉起页 app 内本无路径，鸿蒙侧无对应动作，拉起截图无人比）；deeplink 事实仍留在
  `walkability.facts.manifest.deeplinks`，深链是否迁移属 manifest↔module.json5 静态契约，不在遍历里验。执行器 `deeplink` 动作保留不排。
- 不做 materialize 的 walkability 运行时翻转（下游不再读 walkability 过滤，无需翻）。
- AntennaPod 例证：VideoplayerActivity/PlaybackSpeedDialogActivity 由 `PlaybackService.getPlayerActivityIntent()` 以 action 字串拉起，
  类名零引用被判 external_entry——普查点播放按钮即可落到它并结账，范围跟 ledger 走就不会漏；静态 action 字串规则降为可选。

## 2026-09-09（中午）安卓真走 chunk0 实爆的执行器缺陷四修 + 首启门机械放行
- 背景：AIPPT 新契约树真走 walk_0（63 步）墙钟 33min，三分账 **机械 5% / LLM 79% / 空转 16%**，9 次熔断全是工具契约问题、
  零 needs_discovery（树侧假设成立）。逐项修：
- `do_coldstart` 执行计划的 `reset_before=pm_clear`（此前从不执行，首启链拿到残留态、错报 position_mismatch，630s）。
- `_dismiss_gate` + `choose_gate_control`：计划外的首启协议弹窗 / 无取消键的「声明」浮层挡住落点时，只点白名单放行控件
  （id 含 agree/sure/confirm/continue/know 且文案在「同意并继续/我知道了/确定…」白名单、不含否定与破坏性词），每步最多 2 次，
  记 `state.gates`；是前进动作不是排水，链保护趟同样适用（460s+）。verify_at / 到达判定 / 冷启探根三处接入。
- 弱哨兵：`--resume --assume-at <node>` 视为人工确认一次；向导步（contract wizard_step）activity 匹配即按顺序语义接受（351s，共享 rid 的五个 Guide 页此前 --resume 死循环）。
- dialog 结账：capture 内核对 dialog 设计性拒跑 → 新 `settle_dialog_direct`（截图+dump 直接入 ledger，身份=到达哨兵），tap/auto/mark-step-done 三处接入；
  `mark_step_done` 先存游标再 settle（此前 settle 拒跑 sys.exit 在存游标前，执行器锁死）。
- 兄弟边控件不在屏上且目标已结账 → 直接记 not_reproduced（reason control_absent_target_already_settled），不熔断（127s）。
- 单测 +1（门控件白名单/弹窗直接结账）；vv 全套 24+19 绿。

## 2026-09-09（下午）chunk1/chunk2 实爆再修四处 + 门放行安全收紧
- `do_coldstart` 瞬态补救链：夹着 skip/note/verify 步不再截断（trip_2 的 Splash 纯瞬态此前必 position_mismatch 死循环）。
- `do_back`：BACK 弹出确认窗 → 点白名单「取消/关闭」（含 dialog_id_catalog close_ids），不再连按 BACK（开关式来回翻）；`choose_cancel_control`。
- 每 walk 一份状态：换 walk 不 --resume 时归档 `walk_exec_state.<walk_id>.json`；`walk_timing.py` 跨 walk 聚合并逐 walk 打印。
- **安全收紧**（chunk2 子代理审出）：`choose_gate_control` 必须先命中门的正文语义（协议/隐私/声明/权限说明/承诺）且正文不含退出登录/注销/删除/清除/退款/退订/支付/购买等词，才允许点「同意/知道了/确定」类控件——此前只看按钮，退出登录确认窗的「确定」会被当门放行。
- `--skip-step` 对 back/verify/skip 步只跳自己（对 back 步曾把到 walk 末尾全吞）；skip_unless_verified 与「兄弟边控件不在」两条快路连子树一起跳（否则留下幽灵 BACK 步，BACK×3 退出 app）。
- 实测：chunk2（walk_1 42-89）27min 零冷启零工具失败；ledger 19→24；边 61。

## 2026-09-09（傍晚）finalize 实爆两修 + 首趟安卓真走收口
- `walk_exec.py`：边真值 `control.rid` 记「实际用来定位的 rid」（runtime > static_rid > span 宿主），此前只记反哺 rid → 按 static_rid 定位的边 rid 为空，
  writeback 同起点多候选消歧失败拒写 21 条。`writeback_walk.py`：rid 空时从 `matched_by` 兜底、文案退回计划标签；未复现且无控件线索的边计 `edge_skipped_no_control` 不算拒写。
- 首趟收口：finalize 两 trip 全绿（`--accept-retap-debt` 显式带 2 条状态所阻的 retap 债），基线 trip_1 14 / trip_2 21，runtime confirmed 36 边、not_reproduced 21、
  blackbox_behavior 13 节点、判定 23 条；孤儿重算 0。墙钟 226min（子代理 201min），三分账见 memory android-walk-0909-run。
