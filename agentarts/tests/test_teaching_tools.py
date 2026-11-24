from copy import deepcopy
import unittest

from agentarts.run import cases, tool_cases, tool_replay, validate_response
from agentarts.teaching_tools import check_citations, teaching_config, tool_evidence
from agentarts.workflow import error_issue


class TeachingTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = tool_cases()

    def evidence_for(self, name, calls, **context):
        case = self.cases[name]
        return tool_evidence(case["role"], case["operation"], calls, **context)

    def assert_issue(self, code, action, *args, **kwargs):
        with self.assertRaises(ValueError) as raised:
            action(*args, **kwargs)
        self.assertEqual(error_issue(raised.exception)["code"], code)

    def test_provider_schemas_and_scope(self):
        private = teaching_config("teacher", "ask")["tools"]
        self.assertEqual([tool["name"] for tool in private], ["search_study_records", "read_reference"])
        self.assertEqual(teaching_config("keeper", "find_related")["tools"], private)
        self.assertEqual(teaching_config("teacher", "review_related")["tools"], private)
        self.assertEqual(teaching_config("teacher", "exam_review")["tools"], private)
        search = private[0]["parameters"]
        self.assertEqual(search["required"], ["query"])
        self.assertFalse(search["additionalProperties"])
        self.assertEqual(search["properties"]["scope"]["default"], "focus_graph")
        self.assertEqual(search["properties"]["scope"]["enum"], ["focus_node", "focus_graph", "learner_history"])
        self.assertEqual(search["properties"]["limit"], {"type": "integer", "minimum": 1, "maximum": 10, "default": 5})
        public = teaching_config("teacher", "goal")["tools"]
        self.assertEqual([tool["name"] for tool in public], ["search_public_sources", "read_public_source"])
        self.assertEqual(public[1]["parameters"]["required"], ["candidate_id"])
        self.assertEqual(teaching_config("teacher", "limited")["tools"], public)
        self.assertEqual(teaching_config("teacher", "textbook_supplement")["tools"], public)

    def test_a10_cases_replay(self):
        for name in self.cases:
            with self.subTest(case=name):
                self.assertEqual(tool_replay(name)["mode"], "mock")

    def test_known_reference_can_be_read_directly(self):
        report = tool_replay("teacher_known_reference")
        self.assertEqual([call["tool"] for call in report["calls"]], ["read_reference"])
        self.assertEqual(report["evidence"]["citable_refs"], [report["calls"][0]["args"]["ref"]])

    def test_changing_revision_or_requested_location_is_rejected(self):
        name = "teacher_known_reference"
        for change in ({"revision": 99}, {"locator": {"section": "另一节"}}):
            with self.subTest(change=change):
                calls = deepcopy(self.cases[name]["calls"])
                calls[0]["response"]["data"]["ref"].update(change)
                self.assert_issue("REFERENCE_MISMATCH", self.evidence_for, name, calls)

    def test_no_match_and_missing_revision_grant_no_new_refs(self):
        empty = tool_replay("teacher_no_match")["evidence"]
        self.assertEqual(empty["citable_refs"], [])
        self.assertEqual(empty["errors"], [])
        unavailable = tool_replay("teacher_missing_revision")["evidence"]
        self.assertEqual(unavailable["citable_refs"], [])
        self.assertEqual(unavailable["errors"], ["REF_UNAVAILABLE"])

    def test_study_search_matches_need_read_or_snapshot_before_citation(self):
        name = "keeper_cross_graph"
        case = self.cases[name]
        ref = case["expected"]["source_ref"]
        search_only = self.evidence_for(name, case["calls"][:1])
        self.assert_issue("REF_OUTSIDE_SNAPSHOT", check_citations, [ref], search_only)
        check_citations([ref], self.evidence_for(name, case["calls"][:1], supplied_refs=[ref]))
        check_citations([ref], tool_replay(name)["evidence"])
        self.assertEqual(case["expected"]["relation_kind"], "analogy")
        self.assertEqual(tool_replay("keeper_unrelated")["expected"]["suggestion_count"], 0)

    def test_search_hit_requires_the_contract_fields(self):
        name = "keeper_cross_graph"
        calls = deepcopy(self.cases[name]["calls"][:1])
        calls[0]["response"]["data"]["matches"][0].pop("excerpt_md")
        self.assert_issue("INVALID_EXCERPT", self.evidence_for, name, calls)

    def test_corrected_by_ref_needs_its_own_body(self):
        name = "teacher_known_reference"
        calls = deepcopy(self.cases[name]["calls"])
        correction = {"kind": "record", "id": "rec_later_correction", "revision": 1}
        calls[0]["response"]["data"]["corrected_by_ref"] = correction
        self.assert_issue("REF_OUTSIDE_SNAPSHOT", check_citations, [correction], self.evidence_for(name, calls))

    def test_public_source_error_never_becomes_a_citation(self):
        verified = tool_replay("teacher_public_source")["evidence"]
        read = verified["public_reads"][0]
        self.assertEqual(read["ref"]["locator"]["section"], "§3.2.1 Format")
        self.assertTrue(read["body_md"] and read["url"] and read["accessed_at"])
        check_citations([read["ref"]], verified)
        failed = tool_replay("teacher_public_source", alternate=True)["evidence"]
        self.assertEqual(failed, {"citable_refs": [], "public_reads": [], "errors": ["TOOL_UNAVAILABLE"]})
        self.assert_issue("REF_OUTSIDE_SNAPSHOT", check_citations, [read["ref"]], failed)

    def test_public_candidates_must_belong_to_current_task(self):
        name = "teacher_public_source"
        read = self.cases[name]["calls"][1:]
        self.assert_issue("UNREGISTERED_PUBLIC_CANDIDATE", self.evidence_for, name, read)
        candidate_id = read[0]["args"]["candidate_id"]
        evidence = self.evidence_for(name, read, public_candidate_ids=[candidate_id])
        self.assertEqual(len(evidence["public_reads"]), 1)

    def test_prepared_public_excerpt_is_valid_in_textbook_snapshot(self):
        public = tool_replay("teacher_public_source")["evidence"]["public_reads"][0]
        ref = public["ref"]
        catalog_entry = {
            "id": ref["id"], "revision": ref["revision"], "locator": ref["locator"],
            "title": public["title"], "url": public["url"], "accessed_at": public["accessed_at"],
            "excerpt_md": public["body_md"],
        }
        sample = cases()["textbook"]
        sample["request"]["input"]["source_catalog"].append(catalog_entry)
        sample["expected"]["result"]["nodes"][1]["source_refs"].append(ref)
        validate_response(sample["request"], sample["expected"])

    def test_exam_rules_and_background_review_have_no_retrieval_tools(self):
        self.assertEqual(teaching_config("teacher", "exam_check")["tools"], [])
        locked = tool_replay("teacher_during_exam")
        self.assertEqual(locked["offered_tools"], [])
        self.assertEqual(locked["evidence"]["errors"], ["EXAM_LOCKED"])
        self.assertEqual(locked["evidence"]["citable_refs"], [])
        calls = deepcopy(locked["calls"])
        calls[0]["response"] = {"data": {"matches": []}}
        self.assert_issue("UNEXPECTED_TOOL", self.evidence_for, "teacher_during_exam", calls)
