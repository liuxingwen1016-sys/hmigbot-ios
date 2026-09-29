#!/usr/bin/env python3
"""test_hit_chain_probe.py —— 命中链自检探针回归

每个用例对应 2026-08-29 AIPPT 退款弹窗事故里的一种 HitTestMode 形态。
不许删用例；新增形态往后追加。
跑: python3 _tests/test_hit_chain_probe.py
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PROBE = HERE.parent / "hit_chain_probe.py"
PY = sys.executable
PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f"\n       {detail}" if detail and not cond else ""))


def run(root: pathlib.Path) -> tuple[int, dict]:
    p = subprocess.run([PY, str(PROBE), "--project", str(root), "--json"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return p.returncode, json.loads(p.stdout or "{}")
    except json.JSONDecodeError:
        return p.returncode, {"_raw": (p.stdout or "") + (p.stderr or "")}


def mk(tmp: pathlib.Path, name: str, body: str) -> pathlib.Path:
    root = tmp / "proj"
    d = root / "entry/src/main/ets/components"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")
    return root


def blocked_lines(d: dict) -> set[int]:
    return {b["line"] for b in d.get("blocked", [])}


# ── 病态形态 ────────────────────────────────────────────────────────────
def case_1_visible_block_kills_button(tmp):
    """① 「显示时 Block」+ 交互子节点 → 必须报（AIPPT 实锤形态）。"""
    root = mk(tmp, "A.ets", """
@ComponentV2
export struct A {
  @Param visible: boolean = false
  build(): void {
    Stack() {
      Column() {
        Button('cancel').onClick((): void => {})
      }
      .hitTestBehavior(HitTestMode.Default)
    }
    .hitTestBehavior(this.visible ? HitTestMode.Block : HitTestMode.None)
  }
}
""")
    rc, d = run(root)
    check("① 显示时 Block 掐死按钮 → 报", d.get("blocked"), json.dumps(d, ensure_ascii=False)[:300])
    check("① 退出码 1", rc == 1)
    at = (d.get("blocked") or [{}])[0].get("blocked_at") or {}
    check("① 指认到根 Stack", at.get("owner") == "Stack", str(at))
    check("① 判为条件真值分支", at.get("verdict") == "cond-blocks", str(at))


def case_2_unconditional_block(tmp):
    """② 无条件 Block + 交互子节点 → 必须报。"""
    root = mk(tmp, "B.ets", """
@Component
export struct B {
  build() {
    Column() {
      Button('ok').onClick((): void => {})
    }
    .hitTestBehavior(HitTestMode.Block)
  }
}
""")
    rc, d = run(root)
    check("② 无条件 Block → 报", d.get("blocked"))
    at = (d.get("blocked") or [{}])[0].get("blocked_at") or {}
    check("② 判为无条件", at.get("verdict") == "blocks", str(at))


def case_3_nested_block_midchain(tmp):
    """③ Block 在链中间层 → 也要报（不能只看最外层）。"""
    root = mk(tmp, "C.ets", """
@Component
export struct C {
  build() {
    Stack() {
      Column() {
        Row() {
          Button('deep').onClick((): void => {})
        }
      }
      .hitTestBehavior(HitTestMode.Block)
    }
    .hitTestBehavior(HitTestMode.Default)
  }
}
""")
    rc, d = run(root)
    check("③ 中间层 Block → 报", d.get("blocked"))
    at = (d.get("blocked") or [{}])[0].get("blocked_at") or {}
    check("③ 指认到中间的 Column", at.get("owner") == "Column", str(at))


# ── 合法形态（必须零误伤）──────────────────────────────────────────────
def case_4_hidden_block_is_legal(tmp):
    """④ 「隐藏时 Block」（假值分支）= 文档形态②，合法，不得报。"""
    root = mk(tmp, "D.ets", """
@Component
export struct D {
  build() {
    Stack() {
      Button('x').onClick((): void => {})
    }
    .hitTestBehavior(this.visible ? HitTestMode.None : HitTestMode.Block)
  }
}
""")
    rc, d = run(root)
    check("④ 隐藏时 Block → 不报", not d.get("blocked"), json.dumps(d, ensure_ascii=False)[:300])
    check("④ 退出码 0", rc == 0)


def case_5_pure_mask_is_legal(tmp):
    """⑤ 纯遮罩（subtree 无交互子节点）Block → 合法，不得报。"""
    root = mk(tmp, "E.ets", """
@Component
export struct E {
  build() {
    Stack() {
      Column() {
        LoadingProgress().width(48)
        Text('loading')
      }
    }
    .hitTestBehavior(HitTestMode.Block)
  }
}
""")
    rc, d = run(root)
    check("⑤ 纯遮罩 Block → 不报", not d.get("blocked"))


def case_6_open_modes_are_legal(tmp):
    """⑥ Default / Transparent / None 祖先 → 一律不报（只有 Block 阻断后代）。"""
    root = mk(tmp, "F.ets", """
@Component
export struct F {
  build() {
    Stack() {
      Column() {
        Button('a').onClick((): void => {})
      }
      .hitTestBehavior(HitTestMode.Transparent)
    }
    .hitTestBehavior(HitTestMode.None)
  }
}
""")
    rc, d = run(root)
    check("⑥ None/Transparent 祖先 → 不报", not d.get("blocked"))
    check("⑥ 但交互节点仍被枚举", d.get("interactive_nodes", 0) >= 1, str(d.get("interactive_nodes")))


def case_7_leaf_block_is_legal(tmp):
    """⑦ Block 挂在叶子自身 → 无后代可挡，不得报。"""
    root = mk(tmp, "G.ets", """
@Component
export struct G {
  build() {
    Column() {
      Button('a').hitTestBehavior(HitTestMode.Block).onClick((): void => {})
    }
  }
}
""")
    rc, d = run(root)
    check("⑦ 叶子自带 Block → 不报", not d.get("blocked"), json.dumps(d, ensure_ascii=False)[:300])


def case_8_string_braces_do_not_break_pairing(tmp):
    """⑧ 字符串/注释里的花括号不得打乱配对（掩码正确性）。"""
    root = mk(tmp, "H.ets", """
@Component
export struct H {
  build() {
    Stack() {
      // 注释里有个 { 花括号
      Text('模板 ${x} 和 } 单括号')
      Button('a').onClick((): void => {})
    }
    .hitTestBehavior(HitTestMode.Block)
  }
}
""")
    rc, d = run(root)
    check("⑧ 掩码后仍能正确报出", d.get("blocked"), json.dumps(d, ensure_ascii=False)[:300])


def case_9_empty_scope_fails_loudly(tmp):
    """⑨ 扫描域为空 → exit 2，绝不能静默判通过。"""
    root = tmp / "empty"
    root.mkdir(parents=True, exist_ok=True)
    rc, _ = run(root)
    check("⑨ 空扫描域 → exit 2（不静默通过）", rc == 2, f"实际 {rc}")


def case_10_match_narrows(tmp):
    """⑩ --match 只筛上下文命中的节点。"""
    root = mk(tmp, "I.ets", """
@Component
export struct I {
  build() {
    Stack() {
      Button('取消').onClick((): void => {})
      Button('确定').onClick((): void => {})
    }
    .hitTestBehavior(HitTestMode.Block)
  }
}
""")
    def m(word):
        r = subprocess.run([PY, str(PROBE), "--project", str(root), "--match", word, "--json"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return json.loads(r.stdout or "{}")
    hit, miss, none = m("取消"), m("不存在的文本xyz"), run(root)[1]
    check("⑩ --match 命中 → 非空", len(hit.get("blocked") or []) > 0)
    check("⑩ --match 不命中 → 空", len(miss.get("blocked") or []) == 0,
          f"blocked={len(miss.get('blocked') or [])}")
    check("⑩ --match 不放大结果集",
          len(hit.get("blocked") or []) <= len(none.get("blocked") or []))


def main() -> int:
    cases = [v for k, v in sorted(globals().items()) if k.startswith("case_")]
    print(f"跑 {len(cases)} 组用例（HitTestMode 形态穷举）\n")
    for fn in cases:
        print(f"{fn.__name__}: {(fn.__doc__ or '').strip().splitlines()[0]}")
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="hitchain_"))
        try:
            fn(tmp)
        except Exception as e:                      # noqa: BLE001
            check(f"{fn.__name__} 抛异常", False, f"{type(e).__name__}: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print()
    print(f"结果: {len(PASS)} 通过 / {len(FAIL)} 失败")
    for f in FAIL:
        print(f"  ❌ {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
