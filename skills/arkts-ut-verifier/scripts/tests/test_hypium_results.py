import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("hypium_results", Path(__file__).parents[1] / "hypium_results.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def event(cid, code, index=1):
    return (f"OHOS_REPORT_STATUS: class=Suite\nOHOS_REPORT_STATUS: current={index}\n"
            f"OHOS_REPORT_STATUS: id=JS\nOHOS_REPORT_STATUS: numtests=4\n"
            f"OHOS_REPORT_STATUS: test={cid}\nOHOS_REPORT_STATUS_CODE: {code}\n")


def log_for(results):
    body = "".join(event(cid, 1, i) + event(cid, code, i) for i, (cid, code) in enumerate(results, 1))
    codes = [code for _, code in results]
    return body + (f"OHOS_REPORT_RESULT: stream=Tests run: {len(results)}, Failure: {codes.count(-2)}, Error: {codes.count(-1)}, Pass: {codes.count(0)}, Ignore: {codes.count(-3)}\n"
                   "OHOS_REPORT_CODE: 0\nOHOS_REPORT_STATUS: taskconsuming=0.5\n")


class HypiumParserTest(unittest.TestCase):
    def test_official_start_and_terminal_codes(self):
        results = [("F001_AC01_pass", 0), ("F001_AC02_error", -1), ("F001_AC03_fail", -2), ("F001_AC04_skip", -3)]
        parsed = module.parse_log(log_for(results), [cid for cid, _ in results])
        self.assertEqual(parsed["status"], "valid", parsed["diagnostics"])
        self.assertEqual([r["status"] for r in parsed["cases"]], ["GREEN", "ERROR", "RED", "IGNORE"])
        self.assertEqual(parsed["raw"], {"Tests run": 4, "Pass": 1, "Failure": 1, "Error": 1, "Ignore": 1})

    def test_start_is_not_an_error_or_a_completed_result(self):
        parsed = module.parse_log(event("F001_AC01_wait", 1), ["F001_AC01_wait"])
        self.assertEqual(parsed["status"], "invalid")
        self.assertEqual(parsed["cases"], [])
        self.assertEqual(parsed["missing_ids"], ["F001_AC01_wait"])

    def test_summary_mismatch_and_missing_ignore_do_not_infer_passes(self):
        log = log_for([("a", 0)])
        for broken in (log.replace("Pass: 1", "Pass: 2"), log.replace(", Ignore: 0", "")):
            with self.subTest(log=broken):
                self.assertEqual(module.parse_log(broken, ["a"])["status"], "invalid")

    def test_missing_unexpected_and_duplicate_ids_fail_closed(self):
        log = log_for([("a", 0)])
        for broken, expected in ((log, ["a", "b"]), (log, ["b"]), (event("a", 1) + log, ["a"]), (log + log, ["a"])):
            with self.subTest(log=broken, expected=expected):
                self.assertEqual(module.parse_log(broken, expected)["status"], "invalid")

    def test_unknown_code_incomplete_block_or_no_finish_marker(self):
        log = log_for([("a", 0)])
        for broken in (log.replace("STATUS_CODE: 0", "STATUS_CODE: 2"), log.replace("OHOS_REPORT_STATUS: taskconsuming=0.5\n", ""), log.replace("OHOS_REPORT_STATUS_CODE: 0\n", "")):
            self.assertEqual(module.parse_log(broken, ["a"])["status"], "invalid")

    def test_ignore_in_summary_cannot_hide_an_unseen_terminal(self):
        log = log_for([("a", 0)]).replace("Tests run: 1", "Tests run: 2").replace("Ignore: 0", "Ignore: 1")
        self.assertEqual(module.parse_log(log, ["a", "skipped"])["status"], "invalid")

    def test_empty_run_is_valid_only_for_empty_expected_set(self):
        self.assertEqual(module.parse_log(log_for([]), [])["status"], "valid")
        self.assertEqual(module.parse_log(log_for([]), ["a"])["status"], "invalid")

    def test_official_reporter_print_chunks_without_added_newlines(self):
        log = log_for([("pass", 0), ("skip", -3)])
        log = log.replace("numtests=4\nOHOS_REPORT_STATUS: test=", "numtests=4OHOS_REPORT_STATUS: stream=OHOS_REPORT_STATUS: test=")
        parsed = module.parse_log(log, ["pass", "skip"])
        self.assertEqual(parsed["status"], "valid", parsed["diagnostics"])
        self.assertEqual(parsed["raw"]["Pass"], 1)
        self.assertEqual(parsed["raw"]["Ignore"], 1)


class VerificationMetricsTest(unittest.TestCase):
    def data(self, count=10, passing=10):
        ids = [f"F001_AC{i:02d}_case" for i in range(count)]
        result = module.parse_log(log_for([(cid, 0 if i < passing else -2) for i, cid in enumerate(ids)]), ids)
        return {"logic_ac_ids": [f"F001-AC{i:02d}" for i in range(count)],
                "cases": [{"case_id": cid, "source_ac_ids": [f"F001-AC{i:02d}"], "required_groups": ["real"], "quality_passed": True, "wiring_complete": True} for i, cid in enumerate(ids)],
                "groups": [{"group_id": "real", "result": result}]}

    def test_eight_pass_two_fail_is_eighty_not_sixty_four(self):
        result = module.metrics(self.data(passing=8))
        for key in ("raw_pass_rate", "design_verification_rate", "ac_completion_rate"):
            self.assertEqual(result[key]["percent"], 80)

    def test_false_greens_remain_in_design_denominator(self):
        data = self.data()
        for row in data["cases"][5:]:
            row["quality_passed"] = False
        result = module.metrics(data)
        self.assertEqual(result["raw_pass_rate"]["percent"], 100)
        self.assertEqual(result["design_verification_rate"]["percent"], 50)
        self.assertEqual(result["ac_completion_rate"]["percent"], 50)

    def test_unexecuted_and_ac_without_cases_remain_denominators(self):
        data = self.data(count=2)
        data["cases"][1]["required_groups"] = []
        data["logic_ac_ids"].append("F001-AC99")
        result = module.metrics(data)
        self.assertEqual(result["design_verification_rate"]["percent"], 50)
        self.assertEqual(result["ac_completion_rate"]["denominator"], 3)
        self.assertEqual(result["ac_completion_rate"]["numerator"], 1)

    def test_all_applicable_groups_and_wiring_are_required(self):
        data = self.data(count=2)
        other = copy.deepcopy(data["groups"][0])
        other["group_id"] = "injected"
        ids = [row["case_id"] for row in data["cases"]]
        other["result"] = module.parse_log(log_for([(ids[0], -2), (ids[1], 0)]), ids)
        data["groups"].append(other)
        for row in data["cases"]:
            row["required_groups"].append("injected")
        data["cases"][1]["wiring_complete"] = False
        result = module.metrics(data)
        self.assertEqual(result["raw_pass_rate"]["percent"], 75)
        self.assertEqual(result["design_verification_rate"]["percent"], 50)
        self.assertEqual(result["ac_completion_rate"]["percent"], 0)

    def test_one_ac_requires_every_case_obligation(self):
        data = self.data(count=2, passing=1)
        data["logic_ac_ids"] = ["F001-AC00"]
        data["cases"][1]["source_ac_ids"] = ["F001-AC00"]
        self.assertEqual(module.metrics(data)["ac_completion_rate"]["percent"], 0)

    def test_invalid_log_never_grants_verified_ids(self):
        data = self.data(count=1)
        data["groups"][0]["result"]["status"] = "invalid"
        self.assertEqual(module.metrics(data)["verified_ids"], [])

    def test_empty_scope_has_na_rates(self):
        result = module.metrics(self.data(count=0))
        for key in ("raw_pass_rate", "design_verification_rate", "ac_completion_rate"):
            self.assertIsNone(result[key]["percent"])

    def test_missing_applicable_group_marks_raw_rate_incomplete(self):
        data = self.data(count=1)
        data["cases"][0]["required_groups"].append("missing")
        result = module.metrics(data)
        self.assertFalse(result["raw_pass_rate_complete"])
        self.assertEqual(result["missing_groups"], ["missing"])
        self.assertEqual(result["verified_ids"], [])
