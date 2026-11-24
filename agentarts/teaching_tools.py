"""Model-facing teaching tool configuration and offline trace checks."""

from copy import deepcopy
from pathlib import Path

from .workflow import object_at, objects_at, ref_key, refs_at, require, text_at


PROMPT = Path(__file__).resolve().parent / "prompts" / "teacher-keeper.md"

REF_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["source", "node", "route", "record", "exam_item"]},
        "id": {"type": "string", "minLength": 1},
        "revision": {"type": "integer", "minimum": 1},
        "locator": {"type": "object"},
    },
    "required": ["kind", "id", "revision"],
    "additionalProperties": False,
}
QUERY = {"type": "string", "minLength": 1}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 10, "default": 5}

TOOLS = {
    "search_study_records": {
        "description": "按当前任务和相关性查找学习资料或已保存记录的版本。搜索命中是候选，引用前须有该版原文。",
        "properties": {
            "query": QUERY,
            "scope": {"type": "string", "enum": ["focus_node", "focus_graph", "learner_history"], "default": "focus_graph"},
            "limit": LIMIT,
        },
        "required": ["query"],
    },
    "read_reference": {
        "description": "按已知的 kind、id、revision 及位置读取该版原文。保留已有纠正的版本线索。",
        "properties": {"ref": REF_SCHEMA},
        "required": ["ref"],
    },
    "search_public_sources": {
        "description": "搜索与学习目标、考核范围或教材疑点有关的公开原始资料。返回的摘要用于选择候选。",
        "properties": {"query": QUERY, "limit": LIMIT},
        "required": ["query"],
    },
    "read_public_source": {
        "description": "用本次搜索返回或应用预先登记的 candidate_id 核对公开来源原文。",
        "properties": {"candidate_id": QUERY, "section": {"type": "string", "minLength": 1}},
        "required": ["candidate_id"],
    },
}

STUDY = ("search_study_records", "read_reference")
PUBLIC = ("search_public_sources", "read_public_source")
TASKS = {
    "teacher": {
        "ask": STUDY,
        "check": STUDY,
        "practice": STUDY,
        "suggest_next": STUDY,
        "review_related": STUDY,
        "exam_review": STUDY,
        "goal": PUBLIC,
        "limited": PUBLIC,
        "textbook_supplement": PUBLIC,
        "merge": (),
        "exam_rules": (),
        "exam_check": (),
    },
    "keeper": {"find_related": STUDY},
}


def tool_names(role, operation):
    try:
        return TASKS[role][operation]
    except KeyError as exc:
        raise ValueError(f"未知的教学工具场景 {role}/{operation}。") from exc


def teaching_config(role, operation):
    """Describe the tools exposed to the provider for one application task."""
    tools = []
    for name in tool_names(role, operation):
        spec = TOOLS[name]
        parameters = {"type": "object", "additionalProperties": False,
                      "properties": spec["properties"], "required": spec["required"]}
        tools.append({"name": name, "description": spec["description"], "parameters": deepcopy(parameters)})
    selection = "本次可用工具为 " + "、".join(tool["name"] for tool in tools) if tools else "本次使用已给定的快照。"
    prompt = f"本次角色为 {role}，操作为 {operation}。{selection}\n\n"
    return {"system_prompt": prompt + PROMPT.read_text(encoding="utf-8"), "tools": tools}


def tool_evidence(role, operation, calls, *, supplied_refs=(), public_candidate_ids=()):
    """Check an application tool trace for A10 without accessing app state."""
    exposed = tool_names(role, operation)
    refs = {ref_key(ref, "supplied_refs"): ref for ref in supplied_refs}
    public_candidates = set(public_candidate_ids)
    public_reads = []
    errors = []
    for index, call in enumerate(objects_at(calls, "calls")):
        path = f"calls[{index}]"
        name = text_at(call.get("tool"), f"{path}.tool")
        require(name in TOOLS, "UNKNOWN_TOOL", path, "未知的教学工具。")
        args = object_at(call.get("args"), f"{path}.args")
        response = object_at(call.get("response"), f"{path}.response")
        require(("data" in response) != ("error" in response), "INVALID_TOOL_RESPONSE", path, "工具响应应含 data 或 error。")
        if "error" in response:
            error = object_at(response["error"], f"{path}.error")
            code = text_at(error.get("code"), f"{path}.error.code")
            text_at(error.get("message"), f"{path}.error.message")
            object_at(error.get("details"), f"{path}.error.details")
            if operation == "exam_rules":
                require(code == "EXAM_LOCKED", "INVALID_EXAM_TOOL_RESPONSE", path, "计时规则问答的检索请求应返回 EXAM_LOCKED。")
            errors.append(code)
            continue

        require(name in exposed, "UNEXPECTED_TOOL", path, "本场景未开放此工具。")
        data = object_at(response["data"], f"{path}.data")
        if name.startswith("search_"):
            matches = objects_at(data.get("matches"), f"{path}.data.matches")
            for match in matches:
                match_path = f"{path}.data.matches"
                text_at(match.get("title"), f"{match_path}.title")
                require(isinstance(match.get("excerpt_md"), str), "INVALID_EXCERPT", match_path, "搜索候选缺少摘录字段。")
                if name == "search_public_sources":
                    candidate_id = text_at(match.get("candidate_id"), f"{match_path}.candidate_id")
                    text_at(match.get("url"), f"{match_path}.url")
                    public_candidates.add(candidate_id)
                else:
                    ref_key(match.get("ref"), f"{match_path}.ref")
                    if "corrected_by_ref" in match:
                        ref_key(match["corrected_by_ref"], f"{match_path}.corrected_by_ref")
            continue

        ref = data.get("ref")
        key = ref_key(ref, f"{path}.data.ref")
        text_at(data.get("title"), f"{path}.data.title")
        text_at(data.get("body_md"), f"{path}.data.body_md")
        if name == "read_reference":
            requested = args.get("ref")
            requested_key = ref_key(requested, f"{path}.args.ref")
            locator = ref.get("locator", {})
            same_place = all(locator.get(part) == value for part, value in requested.get("locator", {}).items())
            require(key[:3] == requested_key[:3] and same_place, "REFERENCE_MISMATCH", path, "工具返回的版本或位置与读取请求不同。")
            if "corrected_by_ref" in data:
                ref_key(data["corrected_by_ref"], f"{path}.data.corrected_by_ref")
        else:
            candidate_id = text_at(args.get("candidate_id"), f"{path}.args.candidate_id")
            require(candidate_id in public_candidates, "UNREGISTERED_PUBLIC_CANDIDATE", path, "公开候选必须来自本次搜索或应用登记。")
            require(key[0] == "source", "INVALID_PUBLIC_REF", path, "公开原文须返回来源版本。")
            text_at(data.get("url"), f"{path}.data.url")
            text_at(data.get("accessed_at"), f"{path}.data.accessed_at")
            public_reads.append(data)
        refs[key] = ref

    return {"citable_refs": list(refs.values()), "public_reads": public_reads, "errors": errors}


def check_citations(refs, evidence):
    allowed = refs_at(evidence["citable_refs"], "citable_refs")
    refs_at(refs, "result citations", allowed)
