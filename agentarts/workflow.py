def main(args: dict) -> dict:
    """AgentArts Code node entry point, also called by the local regression tests."""
    return run_step(args)


import json
import math
from collections import deque


SCHEMA_VERSION = "1.0"


def contract_error(code, message, path):
    return ValueError({"code": code, "message": message, "path": path})


def error_issue(error):
    if error.args and isinstance(error.args[0], dict):
        return error.args[0]
    raise error


def require(condition, code, path, message):
    if not condition:
        raise contract_error(code, message, path)


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def load_json(value, path):
    if not isinstance(value, str):
        raise contract_error("INVALID_JSON", "需要 JSON 字符串。", path)
    try:
        return json.loads(value, parse_constant=finite_number, parse_float=finite_number, object_pairs_hook=unique_object)
    except (ValueError, RecursionError) as exc:
        raise contract_error("INVALID_JSON", "无法读取 JSON，请检查格式和输出长度。", path) from exc


def load_object(value, path):
    return object_at(load_json(value, path), path)


def finite_number(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite number")
    return number


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate key")
    return result


def object_at(value, path):
    require(isinstance(value, dict), "INVALID_OBJECT", path, "需要 JSON 对象。")
    return value


def array_at(value, path, nonempty=False):
    require(isinstance(value, list), "INVALID_ARRAY", path, "需要 JSON 数组。")
    if nonempty:
        require(value, "EMPTY_ARRAY", path, "至少需要一项。")
    return value


def text_at(value, path):
    require(isinstance(value, str) and value.strip(), "INVALID_TEXT", path, "需要非空文本。")
    return value


def objects_at(value, path, nonempty=False):
    return [object_at(item, f"{path}[{i}]") for i, item in enumerate(array_at(value, path, nonempty))]


def text_list(value, path, nonempty=False):
    return [text_at(item, f"{path}[{i}]") for i, item in enumerate(array_at(value, path, nonempty))]


def ids_at(value, path, nonempty=False):
    ids = text_list(value, path, nonempty)
    require(len(set(ids)) == len(ids), "DUPLICATE_ID", path, "ID 重复。")
    return ids


def index_by(items, field, path):
    indexed = {}
    for item in items:
        key = text_at(item.get(field), f"{path}.{field}")
        require(key not in indexed, "DUPLICATE_ID", path, f"{field} {key} 重复。")
        indexed[key] = item
    return indexed


def revision_at(value, path):
    require(isinstance(value, int) and not isinstance(value, bool) and value > 0, "INVALID_REVISION", path, "版本须为正整数。")
    return value


def ref_key(ref, path):
    object_at(ref, path)
    kind = ref.get("kind")
    require(kind in ("source", "node", "route", "record", "exam_item"), "INVALID_REF", path, "未知的引用类型。")
    ref_id = text_at(ref.get("id"), f"{path}.id")
    revision = revision_at(ref.get("revision"), f"{path}.revision")
    locator = object_at(ref.get("locator", {}), f"{path}.locator")
    return kind, ref_id, revision, json.dumps(locator, sort_keys=True, allow_nan=False)


def refs_at(value, path, allowed=None, nonempty=False):
    keys = set()
    for ref in objects_at(value, path, nonempty):
        key = ref_key(ref, path)
        if allowed is not None:
            require(key in allowed, "REF_OUTSIDE_SNAPSHOT", path, f"引用 {key[1]} 的版本或定位不在本次快照中。")
        require(key not in keys, "DUPLICATE_REF", path, f"引用 {key[1]} 重复。")
        keys.add(key)
    return keys


def review_issues(value, path):
    issues = objects_at(value, path)
    for issue in issues:
        text_at(issue.get("code"), f"{path}.code")
        text_at(issue.get("message"), f"{path}.message")
        require(issue.get("severity") in ("blocking", "note"), "INVALID_SEVERITY", path, "用 blocking 或 note 标记问题。")
        if "section_id" in issue:
            text_at(issue["section_id"], f"{path}.section_id")
    return issues


def response(workflow, request_id, outcome, result=None, issues=None):
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow": workflow,
        "request_id": request_id,
        "outcome": outcome,
        "result": result,
        "issues": [] if issues is None else issues,
    }


def request_input(request, workflow):
    require(request.get("schema_version") == SCHEMA_VERSION, "UNSUPPORTED_SCHEMA", "schema_version", "工作流契约版本应为 1.0。")
    require(request.get("workflow") == workflow, "WORKFLOW_MISMATCH", "workflow", f"请求应调用 {workflow}。")
    text_at(request.get("request_id"), "request_id")
    return object_at(request.get("input"), "input")


def resume_context(data):
    focus = object_at(data.get("focus"), "input.focus")
    graph_id = text_at(focus.get("graph_id"), "input.focus.graph_id")
    node_id = text_at(focus.get("node_id"), "input.focus.node_id")
    revision_at(focus.get("revision"), "input.focus.revision")
    require(focus.get("lock") is None, "FOCUS_LOCKED", "input.focus.lock", "此焦点已被自测锁定。")
    checkpoint = focus.get("checkpoint")
    if checkpoint is not None:
        object_at(checkpoint, "input.focus.checkpoint")

    node = object_at(data.get("focus_node"), "input.focus_node")
    require(node.get("graph_id") == graph_id and node.get("id") == node_id, "FOCUS_MISMATCH", "input.focus_node", "节点与已恢复的焦点不一致。")
    revision_at(node.get("revision"), "input.focus_node.revision")
    objectives = objects_at(node.get("objectives"), "input.focus_node.objectives")
    for objective in objectives:
        text_at(objective.get("id"), "input.focus_node.objectives.id")
        text_at(objective.get("text"), "input.focus_node.objectives.text")

    origin = object_at(data.get("origin_question"), "input.origin_question")
    origin_key = record_key(origin, "input.origin_question")
    require(origin.get("graph_id") == graph_id and origin.get("node_id") == node_id, "FOCUS_MISMATCH", "input.origin_question", "原问题须属于出发节点。")

    refs = data.get("allowed_refs")
    allowed_records = {ref[:3] for ref in refs_at(refs, "input.allowed_refs") if ref[0] == "record"}
    branch = []
    available_text = {origin_key: origin["body_md"]}
    branch_keys = set()
    branch_node_id = None
    for record in objects_at(data.get("branch_records"), "input.branch_records"):
        key = record_key(record, "input.branch_records")
        record_node_id = text_at(record.get("node_id"), "input.branch_records.node_id")
        require(record.get("graph_id") == graph_id and record_node_id != node_id, "BRANCH_SCOPE_MISMATCH", "input.branch_records", "记录须来自当前图中本次返回的支线。")
        if branch_node_id is None:
            branch_node_id = record_node_id
        require(branch_node_id == record_node_id, "BRANCH_SCOPE_MISMATCH", "input.branch_records", "一次续学只能携带同一支线的正文。")
        require(key not in branch_keys, "DUPLICATE_RECORD", "input.branch_records", "支线包含重复的记录版本。")
        branch_keys.add(key)
        if key not in allowed_records or not record["body_md"].strip():
            continue
        branch.append(record)
        available_text[key] = record["body_md"]

    record_refs = set()
    for ref in refs:
        key = ref_key(ref, "input.allowed_refs")
        body = available_text.get(key[:3])
        if body is not None and record_locator_matches(ref.get("locator", {}), body):
            record_refs.add(key)
    usable_records = {key[:3] for key in record_refs}
    branch = [record for record in branch if record_key(record, "input.branch_records") in usable_records]
    supplied_sources = {
        ref_key(ref, "input record/source refs")
        for owner in [origin, node, *branch]
        for ref in objects_at(owner.get("source_refs", owner.get("refs", [])), "input record/source refs")
        if ref.get("kind") == "source"
    }
    available = record_refs | supplied_sources
    return {
        "focus": focus,
        "focus_node": {"title": node.get("title"), "objectives": objectives},
        "origin_question": origin,
        "branch_records": branch,
        "allowed_refs": [ref for ref in refs if ref_key(ref, "input.allowed_refs") in available],
    }


def record_key(record, path):
    ref_id = text_at(record.get("id"), f"{path}.id")
    revision = revision_at(record.get("revision"), f"{path}.revision")
    require(isinstance(record.get("body_md"), str), "INVALID_TEXT", f"{path}.body_md", "记录需要冻结的正文。")
    return "record", ref_id, revision


def record_locator_matches(locator, body):
    quote = locator.get("quote")
    return quote is None or (isinstance(quote, str) and bool(quote.strip()) and quote in body)


def resume_result(result, context):
    text_at(result.get("reply_md"), "result.reply_md")
    text_at(result.get("next_step_md"), "result.next_step_md")
    allowed = refs_at(context["allowed_refs"], "input.allowed_refs")
    keys = refs_at(result.get("used_refs"), "result.used_refs", allowed)
    branch = {record_key(record, "input.branch_records") for record in context["branch_records"]}
    used_branch = {key[:3] for key in keys} & branch
    require(len(used_branch) <= 2, "TOO_MANY_BRANCH_REFS", "result.used_refs", "续学只需带回一两条相关记录。")
    return {field: result[field] for field in ("reply_md", "used_refs", "next_step_md")}


def textbook_input(data):
    text_at(data.get("goal"), "input.goal")
    intent = data.get("intent")
    require(intent in ("full", "limited", "add_textbook", "revise"), "INVALID_INTENT", "input.intent", "教材编排需要 full、limited、add_textbook 或 revise。")
    days = data.get("days_available")
    if intent == "limited" or days is not None:
        require(isinstance(days, int) and not isinstance(days, bool) and days >= 0, "INVALID_DAYS", "input.days_available", "请传入已确认的可用天数。")
    scope = object_at(data.get("scope"), "input.scope")
    section_ids = ids_at(scope.get("section_ids"), "input.scope.section_ids", nonempty=True)
    sections = index_by(objects_at(data.get("sections"), "input.sections"), "section_id", "input.sections")
    refs_at(data.get("assessment_refs"), "input.assessment_refs")
    objects_at(data.get("source_catalog"), "input.source_catalog")
    nodes = objects_at(data.get("existing_nodes"), "input.existing_nodes")
    for node in nodes:
        existing_node_key(node)

    selected = []
    issues = []
    for section_id in section_ids:
        section = sections.get(section_id, {})
        material = section.get("text_md")
        if material is None or (isinstance(material, str) and not material.strip()):
            title = section.get("title") or section_id
            issues.append({"code": "MISSING_SECTION", "section_id": section_id, "message": f"编排范围包含「{title}」，请补上该节。"})
            continue
        text_at(section.get("title"), "input.sections.title")
        text_at(section.get("text_md"), "input.sections.text_md")
        ref = section.get("source_ref")
        key = ref_key(ref, "input.sections.source_ref")
        locator = ref.get("locator", {})
        page, heading = locator.get("page"), locator.get("section")
        has_page = isinstance(page, int) and not isinstance(page, bool) and page > 0
        has_heading = isinstance(heading, str) and bool(heading.strip())
        require(key[0] == "source" and (has_page or has_heading), "MISSING_LOCATOR", "input.sections.source_ref", "教材原节需要具体的页或小节定位。")
        selected.append(section)
    return selected, issues


def textbook_refs(data, sections):
    refs = [section["source_ref"] for section in sections] + data["assessment_refs"]
    for source in data["source_catalog"]:
        ref = {"kind": "source", "id": source.get("id"), "revision": source.get("revision")}
        ref_key(ref, "input.source_catalog")
        # Only named passages with excerpts are available as additional locations.
        for part in objects_at(source.get("sections", []), "input.source_catalog.sections"):
            if part.get("excerpt_md"):
                locator = part.get("locator") or {"section": text_at(part.get("title"), "input.source_catalog.sections.title")}
                refs.append({**ref, "locator": locator})
        if source.get("excerpt_md"):
            refs.append({**ref, "locator": source["locator"]} if source.get("locator") else ref)
    unique = {}
    for ref in refs:
        unique.setdefault(ref_key(ref, "input source refs"), ref)
    return unique


def existing_node_key(node):
    ref = node.get("node_ref", {"kind": "node", "id": node.get("id"), "revision": node.get("revision")})
    key = ref_key(ref, "input.existing_nodes.node_ref")
    require(key[0] == "node" and key[3] == "{}", "INVALID_REF", "input.existing_nodes.node_ref", "旧节点须带准确的完整节点版本。")
    return key


def is_checklist(data):
    return data["intent"] == "limited" and data["days_available"] < 7


def validate_plan(plan, data, sections):
    allowed = textbook_refs(data, sections)
    if is_checklist(data):
        require(plan.get("kind") == "study_checklist", "EXPECTED_CHECKLIST", "result.kind", "不足七天时返回优先学习清单。")
        text_at(plan.get("note_md"), "result.note_md")
        for item in objects_at(plan.get("items"), "result.items", nonempty=True):
            text_at(item.get("title"), "result.items.title")
            text_at(item.get("reason_md"), "result.items.reason_md")
            refs_at(item.get("source_refs"), "result.items.source_refs", allowed, nonempty=True)
        return {}

    nodes = index_by(objects_at(plan.get("nodes"), "result.nodes", nonempty=True), "temp_id", "result.nodes")
    goals, activities = validate_nodes(nodes, allowed)
    full_members = validate_routes(plan.get("routes"), data["intent"], goals)
    validate_coverage(plan.get("coverage"), sections, nodes, full_members, allowed)
    validate_alignment(plan.get("practice_alignment"), activities)
    validate_reuse(plan.get("reuse"), data["existing_nodes"], nodes, allowed)
    return activities


def validate_nodes(nodes, allowed):
    goals = {}
    activities = {}
    for node_id, node in nodes.items():
        path = f"result.nodes.{node_id}"
        require(node.get("kind") == "mainline", "INVALID_NODE_KIND", path, "教材计划节点应为主线节点。")
        text_at(node.get("title"), f"{path}.title")
        refs_at(node.get("source_refs"), f"{path}.source_refs", allowed, nonempty=True)
        objectives = index_by(objects_at(node.get("objectives"), f"{path}.objectives", nonempty=True), "id", path)
        goals[node_id] = set(objectives)
        for objective in objectives.values():
            text_at(objective.get("text"), f"{path}.objectives.text")
        reading = object_at(node.get("reading"), f"{path}.reading")
        text_at(reading.get("intro_md"), f"{path}.reading.intro_md")
        text_list(reading.get("steps"), f"{path}.reading.steps", nonempty=True)
        text_list(reading.get("key_points"), f"{path}.reading.key_points", nonempty=True)
        refs_at(reading.get("source_refs"), f"{path}.reading.source_refs", allowed, nonempty=True)
        node_activities = index_by(objects_at(node.get("activities"), f"{path}.activities", nonempty=True), "id", path)
        for activity_id, activity in node_activities.items():
            activity_path = f"{path}.activities.{activity_id}"
            text_at(activity.get("kind"), f"{activity_path}.kind")
            text_at(activity.get("prompt_md"), f"{activity_path}.prompt_md")
            text_at(activity.get("solution_md"), f"{activity_path}.solution_md")
            targets = set(ids_at(activity.get("objective_ids"), f"{activity_path}.objective_ids", nonempty=True))
            require(targets <= goals[node_id], "UNKNOWN_OBJECTIVE", activity_path, "过关题引用了此节点不存在的目标。")
            refs_at(activity.get("source_refs"), f"{activity_path}.source_refs", allowed, nonempty=True)
            activities[(node_id, activity_id)] = targets
    return goals, activities


def validate_routes(raw_routes, intent, goals):
    routes = index_by(objects_at(raw_routes, "result.routes", nonempty=True), "kind", "result.routes")
    if intent in ("full", "add_textbook"):
        require({"full", "core"} <= routes.keys(), "MISSING_ROUTE", "result.routes", "需要全书路线和核心路线。")
    if intent == "limited":
        require("limited" in routes, "MISSING_ROUTE", "result.routes", "至少七天的限时任务需要限时路线。")
    all_edges = {node_id: set() for node_id in goals}
    memberships = {}
    for kind, route in routes.items():
        path = f"result.routes.{kind}"
        require(kind in ("full", "core", "limited"), "INVALID_ROUTE_KIND", path, "未知的路线类型。")
        text_at(route.get("title"), f"{path}.title")
        members = set(ids_at(route.get("node_ids"), f"{path}.node_ids", nonempty=True))
        counted = set(ids_at(route.get("counted_node_ids"), f"{path}.counted_node_ids"))
        require(members <= goals.keys() and counted <= members, "UNKNOWN_ROUTE_NODE", path, "路线引用了不存在的节点，或把成员以外的节点计入进度。")
        memberships[kind] = members
        for edge in objects_at(route.get("edges"), f"{path}.edges"):
            start = text_at(edge.get("from_node_id"), f"{path}.from_node_id")
            end = text_at(edge.get("to_node_id"), f"{path}.to_node_id")
            require(start in members and end in members, "UNKNOWN_EDGE_NODE", path, "路线关系的两端须属于该路线。")
            require(edge.get("kind") in ("prerequisite", "related"), "INVALID_EDGE_KIND", path, "未知的路线关系类型。")
            if edge.get("kind") == "prerequisite":
                target = text_at(edge.get("target_objective_id"), f"{path}.target_objective_id")
                require(target in goals[end], "UNKNOWN_EDGE_OBJECTIVE", path, "前置关系须指出后续节点实际使用的目标。")
                text_at(edge.get("reason_md"), f"{path}.reason_md")
                all_edges[start].add(end)

    indegree = {node_id: 0 for node_id in goals}
    for followers in all_edges.values():
        for follower in followers:
            indegree[follower] += 1
    ready = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    while ready:
        for follower in all_edges[ready.popleft()]:
            indegree[follower] -= 1
            if indegree[follower] == 0:
                ready.append(follower)
    require(not any(indegree.values()), "PREREQUISITE_CYCLE", "result.routes.edges", "必要前置存在循环，请重新核对学习目标和边方向。")
    if "full" in memberships and "core" in memberships:
        require(memberships["core"] <= memberships["full"], "INVALID_CORE_ROUTE", "result.routes.core", "核心路线成员须来自全书路线。")
    return memberships.get("full")


def validate_coverage(raw_coverage, sections, nodes, full_members, allowed):
    rows = index_by(objects_at(raw_coverage, "result.coverage"), "section_id", "result.coverage")
    expected = {section["section_id"]: section["source_ref"] for section in sections}
    missing = expected.keys() - rows.keys()
    require(not missing, "UNCOVERED_SECTION", "result.coverage", f"未映射的教材原节：{', '.join(sorted(missing))}。")
    require(rows.keys() <= expected.keys(), "UNKNOWN_SECTION", "result.coverage", "覆盖表包含编排范围外的节。")
    for section_id, source in expected.items():
        row = rows[section_id]
        path = f"result.coverage.{section_id}"
        text_at(row.get("disposition"), f"{path}.disposition")
        node_ids = set(ids_at(row.get("node_ids"), f"{path}.node_ids", nonempty=True))
        require(node_ids <= nodes.keys() and (full_members is None or node_ids <= full_members), "COVERAGE_OUTSIDE_ROUTE", path, "覆盖映射须指向本次计划的节点，在有全书路线时须在该路线中。")
        refs = refs_at(row.get("source_refs"), f"{path}.source_refs", allowed, nonempty=True)
        require(ref_key(source, path) in refs, "COVERAGE_MISSING_SOURCE", path, "覆盖映射缺少该教材节的原始来源。")


def validate_alignment(raw_rows, activities):
    aligned = set()
    for row in objects_at(raw_rows, "result.practice_alignment"):
        key = activity_key(row, "result.practice_alignment")
        require(key in activities and key not in aligned, "INVALID_PRACTICE_ALIGNMENT", "result.practice_alignment", "题目映射必须唯一，且指向本次节点的真实题目。")
        targets = set(ids_at(row.get("objective_ids"), "result.practice_alignment.objective_ids", nonempty=True))
        require(targets == activities[key], "INVALID_PRACTICE_ALIGNMENT", "result.practice_alignment", "题目映射与该题声明的学习目标不一致。")
        text_at(row.get("check"), "result.practice_alignment.check")
        aligned.add(key)
    require(aligned == activities.keys(), "MISSING_PRACTICE_ALIGNMENT", "result.practice_alignment", "有过关题缺少目标映射。")


def validate_reuse(raw_rows, existing_nodes, nodes, allowed):
    existing = {existing_node_key(node) for node in existing_nodes}
    reused = set()
    for row in index_by(objects_at(raw_rows, "result.reuse"), "temp_node_id", "result.reuse").values():
        path = "result.reuse"
        key = ref_key(row.get("existing_node_ref"), f"{path}.existing_node_ref")
        require(key in existing, "REUSE_OUTSIDE_SNAPSHOT", path, "复用须指向本次输入的旧节点版本。")
        require(row["temp_node_id"] in nodes, "UNKNOWN_REUSE_NODE", path, "复用映射缺少计划中的目标节点。")
        require(isinstance(row.get("equivalent"), bool), "INVALID_REUSE", path, "复用映射须给出明确的等价判断。")
        text_at(row.get("reason_md"), f"{path}.reason_md")
        refs_at(row.get("added_source_refs"), f"{path}.added_source_refs", allowed)
        if row["equivalent"]:
            require(key[1] not in reused, "DUPLICATE_REUSE", path, "同一个旧节点只能映射到一个等价草案。")
            reused.add(key[1])


def activity_key(row, path):
    return text_at(row.get("node_id"), f"{path}.node_id"), text_at(row.get("activity_id"), f"{path}.activity_id")


def plan_context(data, sections):
    return {
        **data,
        "sections": sections,
        "allowed_refs": list(textbook_refs(data, sections).values()),
        "deliverable": "study_checklist" if is_checklist(data) else "route_plan",
    }


def step_prepare_textbook(args, request, data):
    sections, issues = textbook_input(data)
    if issues:
        return finished(request, "needs_source", issues=issues)
    textbook_refs(data, sections)
    return {
        "action": "run",
        "section_inputs": [dump({"goal": data["goal"], "intent": data["intent"], "section": section}) for section in sections],
    }


def section_analysis_snapshot(data, section):
    return {"goal": data["goal"], "intent": data["intent"], "source_ref": section["source_ref"]}


def load_analysis_rows(value):
    try:
        return objects_at(load_json(value, "analysis_json"), "analysis_json")
    except ValueError as exc:
        raise contract_error("INVALID_ANALYSIS", "无法读取章节分析汇编。", "analysis_json") from exc


def step_append_analysis(args):
    prepared = load_object(args.get("section_json"), "section_json")
    section = prepared["section"]
    section_id = section["section_id"]
    analysis_json = args.get("analysis_json", "[]")
    try:
        rows = load_analysis_rows(analysis_json)
    except ValueError:
        # Preserve the failure for collect_sections, which has the request ID for the error result.
        return {"analysis_json": analysis_json if isinstance(analysis_json, str) else ""}
    row = {"section_id": section_id, "snapshot": section_analysis_snapshot(prepared, section)}
    try:
        analysis = load_object(args.get("analysis_output"), "analysis_output")
        require(analysis.get("section_id") == section_id, "ANALYSIS_SCOPE_MISMATCH", "analysis_output.section_id", "分组产物须回传本节的 section_id。")
        text_at(analysis.get("summary_md"), "analysis_output.summary_md")
        row["analysis"] = analysis
    except ValueError as exc:
        row["error"] = error_issue(exc)
    rows = [previous for previous in rows if previous.get("section_id") != section_id]
    return {"analysis_json": dump([*rows, row])}


def step_collect_sections(args, request, data):
    sections, issues = textbook_input(data)
    if issues:
        return finished(request, "needs_source", issues=issues)
    rows = index_by(load_analysis_rows(args.get("analysis_json", "[]")), "section_id", "analysis_json")
    expected = {section["section_id"] for section in sections}
    require(rows.keys() <= expected, "ANALYSIS_SCOPE_MISMATCH", "analysis_json", "章节分析含有本轮范围外的节。")
    analyses = []
    for section in sections:
        section_id = section["section_id"]
        row = rows.get(section_id)
        if row is None:
            issues.append({"code": "MISSING_ANALYSIS", "section_id": section_id, "message": "此节尚缺分析产物，请重跑对应小节。"})
        elif row.get("snapshot") != section_analysis_snapshot(data, section):
            issues.append({"code": "ANALYSIS_SNAPSHOT_MISMATCH", "section_id": section_id, "message": "本节分析的来源版本、位置或编排目标已变更，请重跑对应小节。"})
        elif "error" in row:
            issues.append({**object_at(row["error"], f"analysis_json.{section_id}.error"), "section_id": section_id})
        else:
            analysis = object_at(row.get("analysis"), f"analysis_json.{section_id}.analysis")
            require(analysis.get("section_id") == section_id, "ANALYSIS_SCOPE_MISMATCH", f"analysis_json.{section_id}", "分析内容与所登记的教材节不同。")
            text_at(analysis.get("summary_md"), f"analysis_json.{section_id}.summary_md")
            analyses.append(analysis)
    if issues:
        return finished(request, "failed", issues=issues)

    context = plan_context(data, sections)
    context["sections"] = [
        {key: section[key] for key in ("section_id", "title", "source_ref")}
        for section in sections
    ]
    context["section_analyses"] = analyses
    return {"action": "run", "context_json": dump(context)}


def checked_draft(args, data, sections):
    draft = load_object(args.get("draft_json"), "draft_json")
    return draft, validate_plan(draft, data, sections)


def step_prepare_review(args, request, data):
    sections, issues = textbook_input(data)
    if issues:
        return finished(request, "needs_source", issues=issues)
    try:
        draft, _ = checked_draft(args, data, sections)
    except ValueError as exc:
        return repair_or_fail(args, request, data, sections, [error_issue(exc)])

    context = plan_context(data, sections)
    if is_checklist(data):
        context["draft"] = draft
    else:
        # The independent pass reads the learner's question before seeing the proposed solution.
        context["draft"] = {key: draft[key] for key in ("routes", "coverage", "reuse")}
        context["draft"]["nodes"] = [
            {**node, "activities": [
                {key: activity[key] for key in ("id", "objective_ids", "prompt_md", "source_refs")}
                for activity in node["activities"]
            ]}
            for node in draft["nodes"]
        ]
    return {"action": "run", "context_json": dump(context)}


def independent_review(args, activities):
    review = load_object(args.get("independent_json"), "independent_json")
    answered = set()
    for answer in objects_at(review.get("answers"), "independent_json.answers"):
        key = activity_key(answer, "independent_json.answers")
        require(key in activities and key not in answered, "INVALID_INDEPENDENT_CHECK", "independent_json.answers", "独立作答必须逐题对应本次草案。")
        text_at(answer.get("solution_md"), "independent_json.answers.solution_md")
        answered.add(key)
    require(answered == activities.keys(), "INCOMPLETE_INDEPENDENT_CHECK", "independent_json.answers", "仍有题目缺少独立作答。")
    review_issues(review.get("issues"), "independent_json.issues")
    return review


def step_compare_review(args, request, data):
    sections, issues = textbook_input(data)
    if issues:
        return finished(request, "needs_source", issues=issues)
    draft, activities = checked_draft(args, data, sections)
    try:
        independent = independent_review(args, activities)
    except ValueError as exc:
        return repair_or_fail(args, request, data, sections, [error_issue(exc)])
    context = plan_context(data, sections)
    context.update({"draft": draft, "independent_review": independent})
    return {"action": "run", "context_json": dump(context)}


def step_finish_textbook(args, request, data):
    sections, issues = textbook_input(data)
    if issues:
        return finished(request, "needs_source", issues=issues)
    try:
        draft, activities = checked_draft(args, data, sections)
        independent = independent_review(args, activities)
        review = load_object(args.get("review_json"), "review_json")
        checks = {key: review.get(key) for key in ("coverage", "prerequisites", "activities")}
        require(all(value in ("pass", "fail") for value in checks.values()), "INVALID_REVIEW", "review_json", "覆盖、前置和练习各须给出 pass 或 fail。")
        findings = independent["issues"] + review_issues(review.get("issues"), "review_json.issues")
    except ValueError as exc:
        return repair_or_fail(args, request, data, sections, [error_issue(exc)])

    blocking = [issue for issue in findings if issue["severity"] == "blocking"]
    section_ids = {section["section_id"] for section in sections}
    missing = [issue for issue in blocking if issue["code"] in ("MISSING_SECTION", "MISSING_SOURCE")
               and issue.get("section_id") in section_ids]
    if missing:
        return finished(request, "needs_source", issues=missing)
    if blocking or "fail" in checks.values():
        issues = blocking or [{"code": "TEACHING_CHECK_FAILED", "message": "教学核查仍有未通过项，请查看流程中的复核结果。"}]
        return repair_or_fail(args, request, data, sections, issues)

    if is_checklist(data):
        return finished(request, "ok", result={key: draft[key] for key in ("kind", "items", "note_md")})
    result = {key: draft[key] for key in ("nodes", "routes", "coverage", "practice_alignment", "reuse")}
    result["verification"] = {**checks, "issues": findings}
    return finished(request, "ok", result=result)


def repair_or_fail(args, request, data, sections, issues):
    if args.get("allow_repair") is True:
        context = plan_context(data, sections)
        context.update({"prior_draft_json": args.get("draft_json", ""), "issues": issues})
        return {"action": "repair", "repair_json": dump(context)}
    return finished(request, "failed", issues=issues)


def step_prepare_resume(args, request, data):
    return {"action": "run", "context_json": dump(resume_context(data))}


def step_finish_resume(args, request, data):
    draft = load_object(args.get("draft_json"), "draft_json")
    result = resume_result(draft, resume_context(data))
    return finished(request, "ok", result=result)


def finished(request, outcome, result=None, issues=None):
    envelope = response(request["workflow"], request["request_id"], outcome, result, issues)
    return {"action": "done", "result_json": dump(envelope)}


STEPS = {
    "prepare_textbook": ("textbook_plan", step_prepare_textbook),
    "collect_sections": ("textbook_plan", step_collect_sections),
    "prepare_review": ("textbook_plan", step_prepare_review),
    "compare_review": ("textbook_plan", step_compare_review),
    "finish_textbook": ("textbook_plan", step_finish_textbook),
    "prepare_resume": ("resume_branch", step_prepare_resume),
    "finish_resume": ("resume_branch", step_finish_resume),
}


def run_step(args):
    step = args["step"]
    if step == "append_analysis":
        return step_append_analysis(args)

    workflow, run = STEPS[step]
    request_id = None
    defaults = {"action": "done", "result_json": "", "context_json": "", "repair_json": "", "section_inputs": []}
    try:
        request = load_object(args.get("payload_json"), "payload_json")
        if isinstance(request.get("request_id"), str):
            request_id = request["request_id"]
        result = run(args, request, request_input(request, workflow))
    except ValueError as exc:
        result = {"result_json": dump(response(workflow, request_id, "failed", issues=[error_issue(exc)]))}
    return {**defaults, **result}
