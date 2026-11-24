"""Emit fixtures, validate saved results, or call a published AgentArts workflow."""

import argparse
from copy import deepcopy
import os
from datetime import datetime, timezone
import math
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from .teaching_tools import check_citations, teaching_config, tool_evidence, tool_names
from .workflow import (
    SCHEMA_VERSION, dump, is_checklist, load_object, objects_at, request_input, require,
    resume_context, resume_result, review_issues, textbook_input, text_at, validate_plan,
)


ROOT = Path(__file__).resolve().parent
SHARED = ROOT.parent / "study-agent-teaching-agentarts" / "docs" / "development" / "examples.json"
EXTENDED = ROOT / "fixtures" / "workflow-cases.json"
TEACHING_FIXTURES = ROOT / "fixtures" / "teaching-cases.json"


def read_json(path):
    return load_object(Path(path).read_text(encoding="utf-8-sig"), str(path))


def cases():
    examples = read_json(SHARED)
    workflows = examples["workflows"]
    plan = workflows["textbook_plan"]
    resume = workflows["resume_branch"]
    result = {
        "textbook": plan,
        "textbook-missing": plan["missing_source"],
        "textbook-add": examples["goal_flow"]["add_textbook"],
        "resume": resume,
        "resume-alt": resume["alternate"],
    }
    result.update(read_json(EXTENDED))
    for days in (3, 7):
        for with_assessment in (False, True):
            name = f"textbook-{days}" + ("-assessment" if with_assessment else "")
            result[name] = limited_case(plan, name, days, with_assessment)
    for condition in ("empty", "unrelated", "stale"):
        result[f"resume-{condition}"] = branch_fallback_case(resume, condition)
    return result


def tool_cases():
    shared = read_json(SHARED)["tool_cases"]
    return {**shared, **read_json(TEACHING_FIXTURES)["tool_cases"]}


def tool_replay(name, alternate=False):
    available = tool_cases()
    if name not in available:
        raise ValueError(f"未知教学工具用例 {name}，可用 tool-replay 查看。")
    case = available[name]
    calls = deepcopy(case["calls"])
    if alternate:
        switched = False
        for call in calls:
            if "alternate_response" in call:
                call["response"] = call.pop("alternate_response")
                switched = True
        if not switched:
            raise ValueError(f"用例 {name} 没有备用响应。")
    role, operation = case["role"], case["operation"]
    evidence = tool_evidence(role, operation, calls)
    expected = case.get("expected", {})
    if "source_ref" in expected:
        check_citations([expected["source_ref"]], evidence)
    return {
        "mode": "mock", "case": name, "role": role, "operation": operation,
        "offered_tools": list(tool_names(role, operation)), "calls": calls,
        "evidence": evidence, "expected": expected,
    }


def limited_case(baseline, name, days, with_assessment):
    case = {key: deepcopy(baseline[key]) for key in ("request", "expected")}
    request, expected = case["request"], case["expected"]
    request["request_id"] = expected["request_id"] = name.replace("-", "_")
    data = request["input"]
    data.update(intent="limited", days_available=days)
    ttl_ref = data["sections"][1]["source_ref"]
    basis = "当前未提供本课考核资料，采用教材基础安排。"
    selected_nodes = ["unit_1", "unit_2", "unit_3"]
    if with_assessment:
        title = "短教材配套检查的题型和范围"
        assessment_ref = {"kind": "source", "id": "src_network_exam", "revision": 1, "locator": {"section": title}}
        data["assessment_refs"] = [assessment_ref]
        data["source_catalog"].append({
            "id": "src_network_exam", "revision": 1, "title": "自编限时检查范围",
            "sections": [{"title": title, "excerpt_md": "先根据取得时间与 TTL 判定缓存是否到期。能说明递归解析器为何在地址更新后仍可返回缓存。"}],
        })
        basis = "依据已提供的本课检查范围，优先练习 DNS 查询角色和 TTL 判断。"
        selected_nodes = selected_nodes[:2]
    if days < 7:
        expected["result"] = {
            "kind": "study_checklist", "note_md": basis,
            "items": [{"title": "马上练一次 TTL 判断", "reason_md": "先按教材例子的取得时刻和 TTL 计算到期时间，再解释答案来自哪里。", "source_refs": [ttl_ref]}],
        }
    else:
        full_route = expected["result"]["routes"][0]
        expected["result"]["routes"].append({
            **full_route, "kind": "limited", "title": "七天限时路线", "note_md": basis,
            "node_ids": selected_nodes, "counted_node_ids": selected_nodes,
        })
    return case


def branch_fallback_case(baseline, condition):
    case = {key: deepcopy(baseline[key]) for key in ("request", "expected")}
    request, expected = case["request"], case["expected"]
    request["request_id"] = expected["request_id"] = f"req_resume_{condition}"
    data = request["input"]
    branch_ref = next(ref for ref in data["allowed_refs"] if ref["id"] == "rec_s_note")
    if condition == "unrelated":
        data["branch_records"][0]["body_md"] = "我在支线上记了一种命名图片文件的方式。"
        data["branch_records"][0]["refs"] = []
    elif condition == "stale":
        branch_ref["revision"] = 2
    else:
        data["branch_records"] = []
        data["allowed_refs"].remove(branch_ref)
    expected["result"] = {
        "reply_md": "我们沿原问题继续。先区分权威地址更新的时间与解析器原先缓存的时间。",
        "used_refs": [data["focus"]["checkpoint"]["record_ref"]],
        "next_step_md": "以解析器取得旧记录的时刻为起点，标出 TTL 决定的到期时间。",
    }
    return case


def make_body(request):
    return {"inputs": {"payload_json": dump(request)}}


def validate_response(request, envelope):
    workflow = request.get("workflow")
    require(workflow in ("textbook_plan", "resume_branch"), "UNKNOWN_WORKFLOW", "workflow", "未知的工作流。")
    data = request_input(request, workflow)
    require(envelope.get("schema_version") == SCHEMA_VERSION, "UNSUPPORTED_SCHEMA", "schema_version", "结果契约版本应为 1.0。")
    require(envelope.get("workflow") == workflow, "WORKFLOW_MISMATCH", "workflow", "请求和结果的工作流不同。")
    require(envelope.get("request_id") == request["request_id"], "REQUEST_ID_MISMATCH", "request_id", "请求和结果的 request_id 不同。")
    outcome = envelope.get("outcome")
    require(outcome in ("ok", "needs_source", "failed"), "INVALID_OUTCOME", "outcome", "未知的工作流结果状态。")
    issues = objects_at(envelope.get("issues"), "issues", nonempty=outcome != "ok")
    for issue in issues:
        text_at(issue.get("code"), "issues.code")
        text_at(issue.get("message"), "issues.message")
    require("result" in envelope, "MISSING_RESULT", "result", "工作流结果缺少 result 字段。")
    result = envelope["result"]
    if outcome != "ok":
        require(result is None, "INVALID_RESULT", "result", "失败或待补材料时 result 应为 null。")
        return

    require(isinstance(result, dict), "INVALID_RESULT", "result", "成功结果需要一个对象。")
    if workflow == "resume_branch":
        resume_result(result, resume_context(data))
        return

    sections, missing = textbook_input(data)
    require(not missing, "MISSING_SECTION", "input.sections", "教材仍缺范围内原节。")
    validate_plan(result, data, sections)
    if not is_checklist(data):
        checks = result.get("verification")
        require(isinstance(checks, dict), "MISSING_VERIFICATION", "result.verification", "计划缺少教学核查。")
        require(all(checks.get(key) == "pass" for key in ("coverage", "prerequisites", "activities")), "TEACHING_CHECK_FAILED", "result.verification", "计划仍有验收项未通过。")
        findings = review_issues(checks.get("issues"), "result.verification.issues")
        require(all(issue["severity"] == "note" for issue in findings), "TEACHING_CHECK_FAILED", "result.verification.issues", "计划仍有阻碍发布的问题。")


def check_case(name, case, observed):
    expected = case["expected"]
    want = expected["outcome"]
    if observed["outcome"] != want:
        raise ValueError(f"{name} 预期 {want}，实际 {observed['outcome']}。{dump(observed['issues'])}")
    if want == "needs_source":
        missing = {issue.get("section_id") for issue in expected["issues"]}
        found = {issue.get("section_id") for issue in observed["issues"]}
        require(missing <= found, "FIXTURE_MISSING_SECTION", "issues", "待补材料结果缺少样例指定的原节。")
    if want == "ok" and observed["workflow"] == "resume_branch":
        branch_ids = {record["id"] for record in case["request"]["input"]["branch_records"]}
        want_refs = {(ref["id"], ref["revision"]) for ref in expected["result"]["used_refs"] if ref["id"] in branch_ids}
        used_refs = {(ref["id"], ref["revision"]) for ref in observed["result"]["used_refs"] if ref["id"] in branch_ids}
        require(want_refs == used_refs, "FIXTURE_BRANCH_REF_MISMATCH", "result.used_refs", "续学未使用对照样例所要求的支线记录版本。")


def read_sse(data):
    terminal = None
    parts = []
    for raw_line in [*data.split("\n"), ""]:
        line = raw_line.rstrip("\r")
        if line.startswith("data:"):
            parts.append(line.removeprefix("data:").lstrip(" "))
        elif not line and parts:
            event = "\n".join(parts)
            if event != "[DONE]":
                record = load_object(event, "SSE data")
                if record.get("event") == "workflow_finished":
                    terminal = record
            parts.clear()
    if terminal is None:
        raise ValueError("SSE 响应缺少 workflow_finished 终态事件。")
    return terminal


def decode_result(body, result_path=None):
    if body.lstrip().startswith("{"):
        wrapper = load_object(body, "response")
    else:
        wrapper = read_sse(body)
    runtime = wrapper.get("data", wrapper)
    if not isinstance(runtime, dict):
        runtime = {}
    if wrapper.get("event") == "workflow_finished":
        status = runtime.get("status", {})
        if not isinstance(status, dict) or status.get("desc") != "succeeded":
            raise ValueError("AgentArts 终态执行未成功，请按控制台执行 ID 查看运行日志。")

    if result_path:
        value = wrapper
        for part in result_path.split("."):
            if not isinstance(value, dict) or part not in value:
                raise ValueError("指定的响应路径缺少字段，请检查本部署的真实响应。")
            value = value[part]
    elif "schema_version" in wrapper:
        return wrapper, None
    elif "result_json" in wrapper:
        value = wrapper["result_json"]
    else:
        outputs = runtime.get("outputs", {})
        fields = outputs.get("user_fields", {}) if isinstance(outputs, dict) else {}
        value = fields.get("result_json") if isinstance(fields, dict) else None
        if value is None:
            raise ValueError("没有找到 result_json，请按部署回执指定 --result-path。")
    return load_object(value, "result_json"), runtime.get("execution_id")


def invoke(request, timeout, result_path, receipt_path):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("请求超时须为大于 0 的秒数。")
    prefix = "AGENTARTS_" + request["workflow"].upper()
    url = os.environ.get(f"{prefix}_URL", "")
    secret = os.environ.get(f"{prefix}_API_KEY")
    extra_headers = os.environ.get(f"{prefix}_HEADERS_JSON")
    deployment = os.environ.get(f"{prefix}_DEPLOYMENT")
    if urlsplit(url).scheme != "https" or not urlsplit(url).netloc:
        raise ValueError(f"请在 {prefix}_URL 填写控制台的 HTTPS 调用端点。")
    if not secret and not extra_headers:
        raise ValueError(f"请通过团队密钥渠道配置 {prefix}_API_KEY 或 {prefix}_HEADERS_JSON。")
    if receipt_path and not deployment:
        raise ValueError(f"生成真实回执前请配置 {prefix}_DEPLOYMENT。")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "X-Invoke-Mode": "published",
        "X-Request-Id": request["request_id"],
        "x-hw-agentarts-session-id": uuid4().hex,
    }
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    if extra_headers:
        overrides = load_object(extra_headers, "deployment headers")
        if not all(isinstance(value, str) for value in overrides.values()):
            raise ValueError("部署 header 的值须为字符串。")
        headers.update(overrides)
    call = Request(url, data=dump(make_body(request)).encode("utf-8"), headers=headers, method="POST")
    started = time.perf_counter()
    try:
        with urlopen(call, timeout=timeout) as reply:
            body = reply.read().decode("utf-8-sig")
    except HTTPError as exc:
        raise ValueError(f"AgentArts HTTP {exc.code}，请核对部署、鉴权和控制台日志。") from exc
    except (URLError, TimeoutError) as exc:
        raise ValueError("AgentArts 请求无法完成，请核对网络与超时后用同一输入重试。") from exc
    duration_ms = round((time.perf_counter() - started) * 1000)
    response, execution_id = decode_result(body, result_path or os.environ.get(f"{prefix}_RESULT_PATH"))
    validate_response(request, response)
    if receipt_path:
        receipt = {
            "mode": "agentarts", "deployment": deployment, "execution_id": execution_id,
            "observed_at": datetime.now(timezone.utc).isoformat(), "duration_ms": duration_ms,
            "request": request, "response": response,
        }
        Path(receipt_path).write_text(dump(receipt) + "\n", encoding="utf-8")
    return response


def run(args):
    if args.command == "teaching-config":
        return dump(teaching_config(args.role, args.operation))
    if args.command == "tool-replay":
        if args.case is None:
            return "\n".join(tool_cases())
        return dump(tool_replay(args.case, args.alternate))
    available = cases()
    if args.command == "cases":
        return "\n".join(available)
    case = available.get(args.case)
    if case is None:
        raise ValueError(f"未知联调样例 {args.case}，可用 python -m agentarts.run cases 查看。")
    request = case["request"]
    if args.command == "fixture":
        if args.format == "api":
            return dump(make_body(request))
        if args.format == "payload":
            return dump(request)
        return dump(case["expected"])
    if args.command == "verify":
        body = Path(args.response).read_text(encoding="utf-8-sig")
        response, _ = decode_result(body, args.result_path)
        validate_response(request, response)
    else:
        response = invoke(request, args.timeout, args.result_path, args.receipt)
    check_case(args.case, case, response)
    return dump(response)


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("cases", help="list the available fixture names")
    config = sub.add_parser("teaching-config", help="emit the model prompt and tool definitions for a teaching task")
    config.add_argument("role", choices=("teacher", "keeper"))
    config.add_argument("operation")
    replay = sub.add_parser("tool-replay", help="list or verify the A10 mock tool transcripts")
    replay.add_argument("case", nargs="?")
    replay.add_argument("--alternate", action="store_true")
    fixture = sub.add_parser("fixture", help="print a request, API body, or expected (mock) envelope")
    fixture.add_argument("case")
    fixture.add_argument("--format", choices=("payload", "api", "expected"), default="payload")
    verify = sub.add_parser("verify", help="verify a saved JSON or SSE response against a fixture")
    verify.add_argument("case")
    verify.add_argument("response")
    verify.add_argument("--result-path")
    remote = sub.add_parser("invoke", help="call a published deployment using its environment configuration")
    remote.add_argument("case")
    remote.add_argument("--result-path")
    remote.add_argument("--timeout", type=float, default=120)
    remote.add_argument("--receipt")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        print(run(args))
    except (OSError, UnicodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
