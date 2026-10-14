"""T10：提示词版本注册表。

所有进入模型调用的提示词在此登记版本号；每次真实调用会把所用版本写入
llm_call_records，配合 eval 评测与观测 API 对比不同提示词版本的效果。
修改提示词正文时必须同步递增对应版本号并在 CHANGELOG 追加一行。
"""

PROMPT_VERSIONS: dict[str, str] = {
    "question_generator": "v1.0",
    "question_set": "v1.0",
    "follow_up": "v1.0",
    "scoring": "v1.0",
    "matching_suggestions": "v1.0",
    "expression_workflow": "v1.0",
    "job_analysis": "v1.0",
    "resume_polish": "v1.0",
    "resume_parse": "v1.0",
    "career_guide": "v2.0",
    "career_summary": "v1.0",
    "career_fact_extract": "v1.0",
    "career_analyst": "v1.0",
    "career_planner": "v1.0",
    "career_path_compare": "v1.0",
    "career_review": "v1.0",
    "career_graph_extract": "v1.0",
    "career_eval": "v1.0",
}

CHANGELOG: dict[str, list[str]] = {
    service: ["v1.0 初始版本"] for service in PROMPT_VERSIONS
}
CHANGELOG["career_guide"].append(
    "v2.0 接入分层长期记忆：注入已确认档案与相关历史召回，明确事实/推断分离与不承诺求职结果"
)


def version_for(service: str) -> str:
    return PROMPT_VERSIONS.get(service, "unversioned")
