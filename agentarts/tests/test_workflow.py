import os
import unittest
from copy import deepcopy
from unittest.mock import MagicMock, patch

from agentarts.run import cases, check_case, decode_result, invoke, make_body, validate_response
from agentarts.workflow import dump, error_issue, load_object, main


PASS = {"coverage": "pass", "prerequisites": "pass", "activities": "pass", "issues": []}
RATE_ANSWERS = {
    "act_avg": "位移为 -4 m，时间为 2 s，平均速度为 -2 m/s，沿位置减小的方向。",
    "act_limit": "对于 h 非零，位置差是 6h+h²。除以 h 得 6+h，极限是 6 m/s。原式不能除以 0。",
}


class Workflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples = cases()

    def stage(self, sample, step, **inputs):
        return main({"step": step, "payload_json": dump(sample["request"]), **inputs})

    def result(self, stage):
        return load_object(stage["result_json"], "result_json")

    def draft(self, name="textbook"):
        return deepcopy(self.samples[name]["expected"]["result"])

    def mock_independent(self, draft, issues=()):
        return {
            "answers": [
                {"node_id": node["temp_id"], "activity_id": activity["id"],
                 "solution_md": RATE_ANSWERS.get(activity["id"], activity["solution_md"])}
                for node in draft.get("nodes", []) for activity in node["activities"]
            ],
            "issues": list(issues),
        }

    def complete_plan(self, sample, draft, findings=(), review=PASS, allow_repair=False):
        return self.stage(sample, "finish_textbook", draft_json=dump(draft),
                          independent_json=dump(self.mock_independent(draft, findings)),
                          review_json=dump(review), allow_repair=allow_repair)

    def expect_issue(self, stage, code):
        result = self.result(stage)
        self.assertIsNone(result["result"])
        self.assertEqual(result["issues"][0]["code"], code)
        return result

    def expect_repair(self, stage, code):
        self.assertEqual(stage["action"], "repair")
        self.assertEqual(stage["result_json"], "")
        context = load_object(stage["repair_json"], "repair_json")
        self.assertEqual(context["issues"][0]["code"], code)

    def append_mock_analysis(self, section_json, analyses="[]"):
        section = load_object(section_json, "section_json")["section"]
        analysis = {"section_id": section["section_id"], "summary_md": section["text_md"]}
        return main({"step": "append_analysis", "section_json": section_json,
                     "analysis_output": dump(analysis), "analysis_json": analyses})["analysis_json"]

    def test_shared_and_extended_fixtures_validate(self):
        for name, sample in self.samples.items():
            with self.subTest(name=name):
                validate_response(sample["request"], sample["expected"])

    def test_successful_textbook_pipeline_with_mock_model_outputs(self):
        for name, sample in self.samples.items():
            if sample["request"]["workflow"] != "textbook_plan" or sample["expected"]["outcome"] != "ok":
                continue
            with self.subTest(name=name):
                initial = self.stage(sample, "prepare_textbook")
                self.assertEqual(initial["action"], "run")
                analyses = "[]"
                for section_json in initial["section_inputs"]:
                    analyses = self.append_mock_analysis(section_json, analyses)
                collected = self.stage(sample, "collect_sections", analysis_json=analyses)
                self.assertEqual(collected["action"], "run")
                assembly = load_object(collected["context_json"], "context_json")
                self.assertEqual([part["section_id"] for part in assembly["section_analyses"]],
                                 sample["request"]["input"]["scope"]["section_ids"])
                self.assertTrue(all("text_md" not in section for section in assembly["sections"]))

                draft = self.draft(name)
                prepared = self.stage(sample, "prepare_review", draft_json=dump(draft))
                self.assertEqual(prepared["action"], "run")
                self.assertNotIn('"solution_md"', prepared["context_json"])
                audit_source = load_object(prepared["context_json"], "context_json")["sections"]
                self.assertTrue(all(section["text_md"] for section in audit_source))
                independent = self.mock_independent(draft)
                compared = self.stage(sample, "compare_review", draft_json=dump(draft), independent_json=dump(independent))
                self.assertEqual(compared["action"], "run")
                compare_ctx = load_object(compared["context_json"], "context_json")
                self.assertEqual(compare_ctx["independent_review"], independent)
                result = self.result(self.complete_plan(sample, draft))
                self.assertEqual(result, sample["expected"])

    def test_missing_section_fails_before_model_call(self):
        stage = self.stage(self.samples["textbook-missing"], "prepare_textbook")
        envelope = self.expect_issue(stage, "MISSING_SECTION")
        self.assertEqual(envelope["outcome"], "needs_source")
        self.assertEqual(envelope["issues"][0]["section_id"], "sec_2")
        self.assertEqual(stage["section_inputs"], [])

    def test_collection_reports_missing_and_wrong_section_ids(self):
        sample = self.samples["textbook"]
        section_json = self.stage(sample, "prepare_textbook")["section_inputs"][0]
        collection = main({"step": "append_analysis", "section_json": section_json,
                           "analysis_output": '{"section_id":"different","summary_md":"Wrong section"}'})
        stage = self.stage(sample, "collect_sections", **collection)
        issues = self.result(stage)["issues"]
        self.assertEqual([(issue["section_id"], issue["code"]) for issue in issues], [
            ("sec_1", "ANALYSIS_SCOPE_MISMATCH"), ("sec_2", "MISSING_ANALYSIS"), ("sec_3", "MISSING_ANALYSIS"),
        ])

    def test_collection_rejects_previous_version_and_can_refresh_one_section(self):
        sample = deepcopy(self.samples["textbook"])
        analyses = "[]"
        for section_json in self.stage(sample, "prepare_textbook")["section_inputs"]:
            analyses = self.append_mock_analysis(section_json, analyses)
        revised = sample["request"]["input"]["sections"][1]
        revised["source_ref"]["revision"] += 1
        revised["text_md"] = "这一版修订了 TTL 示例。"
        stale = self.stage(sample, "collect_sections", analysis_json=analyses)
        rejected = self.expect_issue(stale, "ANALYSIS_SNAPSHOT_MISMATCH")
        self.assertEqual([issue["section_id"] for issue in rejected["issues"]], ["sec_2"])

        revised_input = self.stage(sample, "prepare_textbook")["section_inputs"][1]
        refreshed = self.append_mock_analysis(revised_input, analyses)
        collected = self.stage(sample, "collect_sections", analysis_json=refreshed)
        context = load_object(collected["context_json"], "context_json")
        self.assertEqual([item["section_id"] for item in context["section_analyses"]], ["sec_1", "sec_2", "sec_3"])
        self.assertEqual(context["section_analyses"][1]["summary_md"], revised["text_md"])

    def test_corrupted_collection_returns_readable_failure(self):
        sample = self.samples["textbook"]
        first = self.stage(sample, "prepare_textbook")["section_inputs"][0]
        for invalid in ("[", "{}"):
            with self.subTest(value=invalid):
                analyses = self.append_mock_analysis(first, invalid)
                stage = self.stage(sample, "collect_sections", analysis_json=analyses)
                result = self.expect_issue(stage, "INVALID_ANALYSIS")
                self.assertEqual(result["request_id"], sample["request"]["request_id"])

    def test_cycle_is_repairable_and_must_be_rechecked(self):
        draft = self.draft()
        draft["routes"][0]["edges"].append({"kind": "prerequisite", "from_node_id": "unit_2",
                                          "to_node_id": "unit_1", "target_objective_id": "obj_roles", "reason_md": "Cycle"})
        sample = self.samples["textbook"]
        stage = self.stage(sample, "prepare_review", draft_json=dump(draft), allow_repair=True)
        self.expect_repair(stage, "PREREQUISITE_CYCLE")
        repeated = self.stage(sample, "prepare_review", draft_json=dump(draft), allow_repair=False)
        self.assertEqual(repeated["action"], "done")
        self.expect_issue(repeated, "PREREQUISITE_CYCLE")
        rechecked = self.complete_plan(sample, self.draft())
        self.assertEqual(self.result(rechecked)["outcome"], "ok")

    def test_coverage_and_practice_errors(self):
        sample = self.samples["textbook"]
        draft = self.draft()
        draft["coverage"].pop()
        self.expect_issue(self.stage(sample, "prepare_review", draft_json=dump(draft)), "UNCOVERED_SECTION")
        draft = self.draft()
        draft["nodes"][0]["activities"][0]["objective_ids"] = ["outside"]
        self.expect_issue(self.stage(sample, "prepare_review", draft_json=dump(draft)), "UNKNOWN_OBJECTIVE")

    def test_textbook_plan_cannot_cite_different_location_or_revision(self):
        sample = self.samples["textbook"]
        draft = self.draft()
        draft["nodes"][0]["source_refs"][0]["revision"] = 2
        self.expect_issue(self.stage(sample, "prepare_review", draft_json=dump(draft)), "REF_OUTSIDE_SNAPSHOT")
        draft = self.draft()
        draft["coverage"][0]["source_refs"][0]["locator"]["section"] = "Different page"
        self.expect_issue(self.stage(sample, "prepare_review", draft_json=dump(draft)), "REF_OUTSIDE_SNAPSHOT")

    def test_non_equivalent_reuse_must_be_repaired(self):
        sample = self.samples["textbook-add"]
        draft = self.draft("textbook-add")
        draft["reuse"][1]["equivalent"] = True
        finding = {"code": "NON_EQUIVALENT_REUSE", "severity": "blocking",
                   "message": "旧要求只考计算到期时间，本题还要辨认答案来源。"}
        stage = self.complete_plan(sample, draft, [finding], allow_repair=True)
        self.expect_repair(stage, "NON_EQUIVALENT_REUSE")
        corrected = self.result(self.complete_plan(sample, self.draft("textbook-add")))
        self.assertEqual([row["equivalent"] for row in corrected["result"]["reuse"]], [True, False])

    def test_untaught_formula_is_blocked_and_model_cannot_self_approve(self):
        sample = self.samples["textbook"]
        draft = self.draft()
        draft["nodes"][1]["activities"][0]["prompt_md"] = "使用本教材尚未讲过的指数衰减模型判断缓存过期。"
        finding = {"code": "UNTAUGHT_FORMULA", "activity_id": "act_ttl", "severity": "blocking",
                   "message": "需要把题目改为教材中的 TTL 到期计算。"}
        stage = self.complete_plan(sample, draft, [finding], allow_repair=True)
        self.expect_repair(stage, "UNTAUGHT_FORMULA")

    def test_material_gap_and_minor_convention(self):
        sample = self.samples["textbook"]
        draft = self.draft()
        issue = {"code": "MISSING_SOURCE", "section_id": "sec_2", "severity": "blocking",
                 "message": "请补上例题所依赖的图。"}
        stage = self.complete_plan(sample, draft, [issue], allow_repair=True)
        self.assertEqual(self.expect_issue(stage, "MISSING_SOURCE")["outcome"], "needs_source")
        self.assertEqual(stage["action"], "done")
        note = {"code": "CONVENTION", "severity": "note", "message": "保留教材明确给出的简化缓存假设。"}
        envelope = self.result(self.complete_plan(sample, draft, [note]))
        self.assertEqual(envelope["outcome"], "ok")
        self.assertEqual(envelope["result"]["verification"]["issues"], [note])

    def test_partial_independent_check_cannot_publish(self):
        sample = self.samples["textbook-rate"]
        draft = self.draft("textbook-rate")
        independent = self.mock_independent(draft)
        independent["answers"].pop()
        stage = self.stage(sample, "compare_review", draft_json=dump(draft), independent_json=dump(independent))
        self.expect_issue(stage, "INCOMPLETE_INDEPENDENT_CHECK")

    def test_resume_pair_and_fallbacks(self):
        replies = []
        for name in ("resume", "resume-alt", "resume-empty", "resume-stale", "resume-unrelated"):
            with self.subTest(name=name):
                sample = self.samples[name]
                stage = self.stage(sample, "prepare_resume")
                self.assertEqual(stage["action"], "run")
                if name in ("resume-empty", "resume-stale"):
                    context = load_object(stage["context_json"], "context_json")
                    self.assertEqual(context["branch_records"], [])
                    self.assertNotIn("rec_s_note", stage["context_json"])
                expected = sample["expected"]
                result = self.result(self.stage(sample, "finish_resume", draft_json=dump(expected["result"])))
                check_case(name, sample, result)
                self.assertEqual(result, expected)
                replies.append(result["result"])
        self.assertNotEqual(replies[0]["reply_md"], replies[1]["reply_md"])
        self.assertNotEqual(replies[0]["next_step_md"], replies[1]["next_step_md"])

    def test_resume_rejects_citing_a_different_snapshot(self):
        sample = self.samples["resume-alt"]
        draft = deepcopy(self.samples["resume"]["expected"]["result"])
        stage = self.stage(sample, "finish_resume", draft_json=dump(draft))
        self.expect_issue(stage, "REF_OUTSIDE_SNAPSHOT")

    def test_incorrect_record_quote_removed_from_allowlist(self):
        sample = deepcopy(self.samples["resume"])
        sample["request"]["input"]["allowed_refs"][1]["locator"] = {"quote": "旧记录里根本没有的句子"}
        context = load_object(self.stage(sample, "prepare_resume")["context_json"], "context_json")
        self.assertFalse(context["branch_records"])

    def test_wrong_focus_graph_rejected(self):
        sample = deepcopy(self.samples["resume"])
        sample["request"]["input"]["branch_records"][0]["graph_id"] = "another_graph"
        stage = self.stage(sample, "prepare_resume")
        self.expect_issue(stage, "BRANCH_SCOPE_MISMATCH")

    def test_bad_json_and_version_return_envelopes(self):
        stage = main({"step": "prepare_resume", "payload_json": '{"workflow":1,"workflow":2}'})
        self.assertEqual(self.expect_issue(stage, "INVALID_JSON")["workflow"], "resume_branch")
        sample = deepcopy(self.samples["resume"])
        sample["request"]["schema_version"] = "2.0"
        envelope = self.expect_issue(self.stage(sample, "prepare_resume"), "UNSUPPORTED_SCHEMA")
        self.assertEqual(envelope["request_id"], sample["request"]["request_id"])


class Transport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = cases()["resume"]

    def terminal(self, status="succeeded"):
        return {"event": "workflow_finished", "data": {
            "status": {"code": 1 if status == "succeeded" else 2, "desc": status},
            "outputs": {"user_fields": {"result_json": dump(self.sample["expected"])}},
            "execution_id": "synthetic_execution",
        }}

    def test_decode_json_and_sse_terminal(self):
        expected = self.sample["expected"]
        body = f'data: {{"event":"message","data":{{"text":"some partial text"}}}}\r\n\r\ndata: {dump(self.terminal())}\r\n\r\ndata: [DONE]\r\n'
        self.assertEqual(decode_result(body), (expected, "synthetic_execution"))
        self.assertEqual(decode_result(dump(self.terminal())), (expected, "synthetic_execution"))
        wrapped = dump({"deployment": {"result_json": dump(expected)}})
        self.assertEqual(decode_result(wrapped, "deployment.result_json"), (expected, None))

    def test_decode_rejects_unsuccessful_or_incomplete_stream(self):
        with self.assertRaisesRegex(ValueError, "终态执行未成功"):
            decode_result(f"data: {dump(self.terminal('failed'))}\n\n")
        with self.assertRaisesRegex(ValueError, "缺少 workflow_finished"):
            decode_result('data: {"event":"message"}\n\n')

    def test_invoke_uses_start_variable_and_correlates_result(self):
        request = self.sample["request"]
        stream = MagicMock()
        stream.__enter__.return_value.read.return_value = dump(self.terminal()).encode()
        with patch.dict(os.environ, {"AGENTARTS_RESUME_BRANCH_URL": "https://agentarts.example/invocations",
                                     "AGENTARTS_RESUME_BRANCH_API_KEY": "synthetic-test-only"}, clear=True):
            with patch("agentarts.run.urlopen", return_value=stream) as open_mock:
                result = invoke(request, 10, None, None)
        self.assertEqual(result, self.sample["expected"])
        call = open_mock.call_args.args[0]
        self.assertEqual(call.method, "POST")
        self.assertEqual(call.get_header("Authorization"), "Bearer synthetic-test-only")
        self.assertEqual(call.get_header("X-request-id"), request["request_id"])
        self.assertEqual(load_object(call.data.decode(), "body"), make_body(request))

    def test_external_response_must_echo_request_id(self):
        invalid = deepcopy(self.sample["expected"])
        invalid["request_id"] = "different"
        with self.assertRaises(ValueError) as exc:
            validate_response(self.sample["request"], invalid)
        self.assertEqual(error_issue(exc.exception)["code"], "REQUEST_ID_MISMATCH")


if __name__ == "__main__":
    unittest.main()
