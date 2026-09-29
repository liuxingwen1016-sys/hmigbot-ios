#!/usr/bin/env bash
# install_lang_regression.sh — MIG-317 回归测试
#
# 覆盖:
#   * 默认环境(LC_ALL/LANG 均未设置)下 ./install.sh --target <目录> 输出包含中文
#     (AC-1 原始复现命令;修改前为纯英文、0 中文字符)
#   * zh locale(zh*|*zh_*|*.zh*)→ zh 与 --lang zh|en 既有行为不被破坏
#   * 默认环境下 --target 目录缺失时错误信息为中文(install.sh 内 t() 之外的兜底分支)
#
# 运行:bash tests/install_lang_regression.sh   (任意 cwd,脚本自动定位仓库根)
# 退出:0=全部通过;1=存在失败(逐条打印 FAIL 详情)
# 写入范围:仅 /tmp/migbot-install-lang-reg-<pid>/ 下临时目录,退出时自动清理。
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

TMP_ROOT="/tmp/migbot-install-lang-reg-$$"
mkdir -p "$TMP_ROOT"
trap 'rm -rf "$TMP_ROOT"' EXIT

# 中 / 英 marker:t() 的 zh/en 分支各自必有其一
ZH_MARK='正在把 migbot(Codex 版)安装到'
EN_MARK='Installing migbot (Codex) into'

run_case() {  # $1=用例名  $2=期望 marker(空=不检查) $3=禁止 marker(空=不检查) 其余=env+args
  local name="$1" expect="$2" forbid="$3"; shift 3
  local out="$TMP_ROOT/$name.out"
  "$@" > "$out" 2>&1
  local st=$?
  [ "$st" -eq 0 ] || err "$name:退出码=$st(期望 0)"
  if [ -n "$expect" ] && ! grep -qF "$expect" "$out"; then
    err "$name:输出缺少 marker '$expect'"
  fi
  if [ -n "$forbid" ] && grep -qF "$forbid" "$out"; then
    err "$name:输出误含 marker '$forbid'"
  fi
}

fresh_target() {  # 每个用例独立目标目录(install.sh 不创建 --target 目录)
  mkdir -p "$TMP_ROOT/t$1"
  printf '%s' "$TMP_ROOT/t$1"
}

# 用例 1:默认环境(LC_ALL/LANG 均 unset)→ 输出包含中文 [AC-1]
run_case c1 "$ZH_MARK" "" \
  env -u LC_ALL -u LANG ./install.sh --target "$(fresh_target 1)"

# 用例 2:zh locale(LANG=zh_CN.UTF-8)→ 仍输出中文(既有行为保持)
run_case c2 "$ZH_MARK" "" \
  env -u LC_ALL LANG=zh_CN.UTF-8 ./install.sh --target "$(fresh_target 2)"

# 用例 3:--lang zh → 仍输出中文(既有行为保持)
run_case c3 "$ZH_MARK" "" \
  env -u LC_ALL -u LANG ./install.sh --lang zh --target "$(fresh_target 3)"

# 用例 4:--lang en → 仍输出英文、不含中文 marker(既有行为保持)
run_case c4 "$EN_MARK" "$ZH_MARK" \
  env -u LC_ALL -u LANG ./install.sh --lang en --target "$(fresh_target 4)"

# 用例 5:默认环境 + --target 目录不存在 → 错误信息为中文,退出非 0
T5="$TMP_ROOT/nonexistent-5"
env -u LC_ALL -u LANG ./install.sh --target "$T5" > "$TMP_ROOT/c5.out" 2>&1
st=$?
[ "$st" -ne 0 ] || err "用例5:缺失目录退出码=$st(期望非 0)"
grep -qF '目标目录不存在' "$TMP_ROOT/c5.out" || err "用例5:缺失目录错误信息非中文"

if [ "$fail" -eq 0 ]; then
  echo "PASS: install.sh 语言策略回归全部通过(默认环境中文 + zh locale/--lang zh/en 保持)"
else
  echo "FAIL: install.sh 语言策略回归存在失败" >&2
fi
exit "$fail"
