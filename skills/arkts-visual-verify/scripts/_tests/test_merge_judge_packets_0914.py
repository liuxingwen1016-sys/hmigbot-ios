#!/usr/bin/env python3
"""J2.5 ①：K 包 judge notes → batch_notes.json 的机械合并（2026-09-14）。

  · 包齐闸（索引 K 包缺一 → exit 21 不落盘；--allow-missing 放行并记账）
  · list 拼接去重 / dict 子键并集保 owner / 标量保 owner，冲突全部记 _merge.conflicts
  · 同键异类型按多数定主形态，少数整份进 _merge.type_mismatch（无损）
  · part 不进产物；started_at/finished_at 取极值；确定性（两次合并逐字相同）
全合成夹具；子进程跑真脚本。
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
import merge_judge_packets as MJ  # noqa: E402


def _run(*args, cwd):
    return subprocess.run([sys.executable, str(SCRIPTS / "merge_judge_packets.py"), *map(str, args)],
                          cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def _cap(root: Path, notes: dict, index_parts=None, owner=None):
    """建 replay 出目录：judge_packets/notes_partNN.json + 可选索引。notes={part:int → dict}"""
    cap = root / "replay" / "round-1-trip_x"
    pk = cap / "judge_packets"
    pk.mkdir(parents=True, exist_ok=True)
    for p, d in notes.items():
        (pk / f"notes_part{p:02d}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    if index_parts is not None:
        idx = {"packets": [{"part": p, "file": f"x/judge_input_round1_part{p:02d}.json"} for p in index_parts]}
        if owner is not None:
            idx["trip_level_owner"] = owner
        (pk / "judge_packets.json").write_text(json.dumps(idx), encoding="utf-8")
    return cap


def _out(cap: Path):
    return json.load(open(cap / "batch_notes.json", encoding="utf-8"))


def test_completeness_gate_exit_21_and_allow_missing(tmp_path):
    cap = _cap(tmp_path, {1: {"new_findings": ["a"]}, 2: {"new_findings": ["b"]}}, index_parts=[1, 2, 3])
    r = _run("--capture-dir", cap, "--json", cwd=tmp_path)
    assert r.returncode == 21, r.stderr
    assert not (cap / "batch_notes.json").exists()
    assert json.loads(r.stdout)["missing"] == [3]
    r = _run("--capture-dir", cap, "--allow-missing", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    m = _out(cap)
    assert m["_merge"]["missing_parts"] == [3] and m["_merge"]["parts_found"] == [1, 2]
    assert m["new_findings"] == ["a", "b"]


def test_no_index_uses_found_parts_and_extra_parts_recorded(tmp_path):
    cap = _cap(tmp_path, {1: {"x": [1]}, 3: {"x": [2]}})
    r = _run("--capture-dir", cap, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    m = _out(cap)
    assert m["_merge"]["parts"] == [1, 3] and m["_merge"]["owner_part"] == 1 and m["_merge"]["missing_parts"] == []
    cap2 = _cap(tmp_path / "b", {1: {"x": [1]}, 2: {"x": [2]}}, index_parts=[1])
    r = _run("--capture-dir", cap2, cwd=tmp_path)
    assert r.returncode == 0
    m2 = _out(cap2)
    assert m2["_merge"]["extra_parts"] == [2] and m2["x"] == [1, 2]


def test_list_concat_order_and_dedup():
    merged, meta = MJ.merge_notes({
        2: {"coverage_debts": ["c", "a"]},
        1: {"coverage_debts": ["a", "b"]},
        3: {"coverage_debts": [{"k": 1}, {"k": 1}, "b"]},
    })
    assert merged["coverage_debts"] == ["a", "b", "c", {"k": 1}]      # 包号序拼接，规范化去重保首次
    assert meta["dedup_dropped"] == {"coverage_debts": 3}


def test_dict_union_owner_wins_and_leaf_conflict_recorded():
    merged, meta = MJ.merge_notes({
        1: {"judge_summary": {"PageA": {"status": "pass"}, "Shared": {"status": "fail"}}},
        2: {"judge_summary": {"PageB": {"status": "fail"}, "Shared": {"status": "pass"}}},
        3: {"judge_summary": {"PageC": {"status": "pass"}, "Shared": {"status": "fail"}}},
    }, owner_part=2)
    js = merged["judge_summary"]
    assert set(js) == {"PageA", "PageB", "PageC", "Shared"}
    assert js["Shared"] == {"status": "pass"}                          # owner=2 的值
    assert len(meta["conflicts"]) == 2                                 # 冲突记在叶子路径
    assert {c["part"] for c in meta["conflicts"]} == {1, 3} and all(c["kept_part"] == 2 for c in meta["conflicts"])
    assert all(c["path"] == "judge_summary.Shared.status" for c in meta["conflicts"])
    assert meta["owner_part"] == 2


def test_recursive_merge_wrapped_summary_and_nested_lists():
    """真实形态（0914 round-1 trip_2）：有的包 judge_summary 直接按页写，有的包套 {part,pages,totals}；
    trip_level_items 下同名子键各包各有一段 list。递归合并后 pages 并集、list 拼接，只有叶子标量才冲突。"""
    merged, meta = MJ.merge_notes({
        1: {"judge_summary": {"PageA": {"status": "pass"}},
            "trip_level_items": {"unverified_destructive": [{"node": "A"}], "ratio": "3/9"}},
        2: {"judge_summary": {"part": 2, "pages": {"PageB": {"status": "fail"}}, "totals": {"ui_new": 2}}},
        3: {"judge_summary": {"part": 3, "pages": {"PageC": {"status": "pass"}}, "totals": {"ui_new": 1}}},
        5: {"trip_level_items": {"unverified_destructive": [{"node": "E"}], "ratio": "3/9"}},
    })
    js = merged["judge_summary"]
    assert js["PageA"] == {"status": "pass"}
    assert js["pages"] == {"PageB": {"status": "fail"}, "PageC": {"status": "pass"}}   # 子 dict 并集，不挤进冲突
    assert js["totals"] == {"ui_new": 2} and js["part"] == 2
    assert merged["trip_level_items"]["unverified_destructive"] == [{"node": "A"}, {"node": "E"}]  # 嵌套 list 拼接
    assert merged["trip_level_items"]["ratio"] == "3/9"
    paths = sorted(c["path"] for c in meta["conflicts"])
    assert paths == ["judge_summary.part", "judge_summary.totals.ui_new"]  # 只有叶子标量冲突


def test_scalar_equal_ok_and_differ_keeps_owner():
    merged, meta = MJ.merge_notes({1: {"trip": "t2", "round": 1}, 2: {"trip": "t2", "round": 1}, 3: {"trip": "t1"}})
    assert merged["trip"] == "t2" and merged["round"] == 1
    assert [c for c in meta["conflicts"] if c["path"] == "trip"] == [{"path": "trip", "kept_part": 1, "part": 3, "value": "t1"}]


def test_type_mismatch_majority_then_precedence_any_depth():
    merged, meta = MJ.merge_notes({
        1: {"judge_summary": {"A": 1}, "llm": [1], "s": "x", "n": {"k": [1]}},
        2: {"judge_summary": {"B": 2}, "llm": {"k": 1}, "s": ["y"], "n": {"k": "散文"}},
        3: {"judge_summary": "散文", "llm": [2]},
    })
    assert merged["judge_summary"] == {"A": 1, "B": 2}                 # dict 2 : str 1
    assert meta["type_mismatch"]["judge_summary"]["dropped"] == [{"part": 3, "type": "scalar", "value": "散文"}]
    assert merged["llm"] == [1, 2]                                     # list 2 : dict 1
    assert meta["type_mismatch"]["llm"]["dropped"][0]["part"] == 2
    assert merged["s"] == ["y"]                                        # 平票 list > scalar
    assert meta["type_mismatch"]["s"]["kept"] == "list"
    assert merged["n"]["k"] == [1] and meta["type_mismatch"]["n.k"]["dropped"][0]["part"] == 2   # 嵌套层同样处理


def test_part_dropped_time_extremes_and_key_order():
    merged, meta = MJ.merge_notes({
        2: {"part": "02", "started_at": "2026-09-14T01:05:00Z", "finished_at": "2026-09-14T01:09:00Z", "zeta": [1]},
        1: {"part": 1, "started_at": "2026-09-14T01:00:00Z", "finished_at": "2026-09-14T01:08:00Z", "new_findings": ["n"]},
    })
    assert "part" not in merged and meta["parts"] == [1, 2]
    assert merged["started_at"] == "2026-09-14T01:00:00Z" and merged["finished_at"] == "2026-09-14T01:09:00Z"
    assert list(merged)[0] == "new_findings"                            # 契约键排最前


def test_owner_from_index_and_cli_override(tmp_path):
    notes = {1: {"trip": "a"}, 2: {"trip": "b"}, 3: {"trip": "c"}}
    cap = _cap(tmp_path, notes, index_parts=[1, 2, 3], owner=3)
    assert _run("--capture-dir", cap, cwd=tmp_path).returncode == 0
    assert _out(cap)["trip"] == "c" and _out(cap)["_merge"]["owner_part"] == 3
    assert _run("--capture-dir", cap, "--owner-part", 2, cwd=tmp_path).returncode == 0
    assert _out(cap)["trip"] == "b"


def test_deterministic_and_dry_run(tmp_path):
    notes = {1: {"new_findings": ["a"], "judge_summary": {"P": 1}}, 2: {"new_findings": ["b"], "judge_summary": {"Q": 2}}}
    cap = _cap(tmp_path, notes, index_parts=[1, 2])
    assert _run("--capture-dir", cap, cwd=tmp_path).returncode == 0
    first = (cap / "batch_notes.json").read_bytes()
    assert _run("--capture-dir", cap, cwd=tmp_path).returncode == 0
    assert (cap / "batch_notes.json").read_bytes() == first
    cap2 = _cap(tmp_path / "dry", notes, index_parts=[1, 2])
    r = _run("--capture-dir", cap2, "--dry-run", "--json", cwd=tmp_path)
    assert r.returncode == 0 and not (cap2 / "batch_notes.json").exists()
    assert json.loads(r.stdout)["sizes"] == {"judge_summary": 2, "new_findings": 2}


def test_input_errors(tmp_path):
    assert _run("--capture-dir", tmp_path / "nope", cwd=tmp_path).returncode == 2
    cap = tmp_path / "replay" / "empty"
    (cap / "judge_packets").mkdir(parents=True)
    assert _run("--capture-dir", cap, cwd=tmp_path).returncode == 2
    cap2 = _cap(tmp_path / "bad", {1: {"a": [1]}})
    (cap2 / "judge_packets" / "notes_part02.json").write_text("{not json", encoding="utf-8")
    assert _run("--capture-dir", cap2, cwd=tmp_path).returncode == 2
    assert _run("--capture-dir", cap2, "--allow-missing", cwd=tmp_path).returncode == 0
    assert _out(cap2)["_merge"]["broken"][0]["part"] == 2


def test_time_keys_non_string_not_lost():
    """D2①（验收记）：started_at/finished_at 全为非字符串 → 退回通用规则不丢；混写时非字符串进异型账。"""
    merged, meta = MJ.merge_notes({1: {"started_at": 1000, "finished_at": None}, 2: {"started_at": 2000}})
    assert merged["started_at"] == 1000 and merged["finished_at"] is None
    assert [c["path"] for c in meta["conflicts"]] == ["started_at"]
    merged, meta = MJ.merge_notes({1: {"finished_at": "2026-09-14T01:09:00Z"}, 2: {"finished_at": 5}})
    assert merged["finished_at"] == "2026-09-14T01:09:00Z"
    assert meta["type_mismatch"]["finished_at"]["dropped"] == [{"part": 2, "type": "scalar", "value": 5}]

