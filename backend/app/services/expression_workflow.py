"""T6：有结构化输入输出的多角色工作流引擎。

每个角色定义明确的输入来源与输出 schema（Pydantic 校验），
顺序执行、单步失败重试一次、失败后依赖方如实标记 skipped，
全流程记录每步耗时与尝试次数，不伪造任何角色输出。
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from pydantic import BaseModel, Field, ValidationError

from app.services.ark_client import ArkClient, ArkError, parse_json_output

logger = logging.getLogger("aurel.workflow")


# ---- 角色输出 schema（结构化输出契约）----


class IssueItem(BaseModel):
    type: str = Field(description="问题类型，如逻辑跳跃 / 论据缺失")
    evidence: str = Field(description="原文证据片段")
    suggestion: str = Field(description="改进方向")


class StructureAnalystOutput(BaseModel):
    logic_score: float = Field(ge=0, le=10, description="逻辑结构得分 0-10")
    structure_summary: str = Field(description="一两句话概括回答的组织方式")
    discourse_markers: list[str] = Field(default_factory=list, description="用到的衔接词")
    issues: list[IssueItem] = Field(default_factory=list)


class DepthAnalystOutput(BaseModel):
    depth_score: float = Field(ge=0, le=10, description="内容深度得分 0-10")
    concrete_examples: list[str] = Field(default_factory=list, description="回答中出现的具体例证")
    missing_substance: list[str] = Field(default_factory=list, description="缺失的实质内容")
    issues: list[IssueItem] = Field(default_factory=list)


class PriorityFix(BaseModel):
    title: str
    detail: str


class ExpressionCoachOutput(BaseModel):
    overall_assessment: str = Field(description="整体评价，两三句话")
    priority_fixes: list[PriorityFix] = Field(min_length=1, max_length=3)
    drill_suggestions: list[str] = Field(min_length=1, max_length=4, description="可立即执行的练习")


# ---- 步骤定义与执行记录 ----


@dataclass
class StepSpec:
    role: str
    title: str
    system: str
    build_user: Callable[[str, dict], str]  # (transcript, 之前步骤输出) -> user prompt
    output_model: type[BaseModel]
    depends_on: list[str] = field(default_factory=list)


@dataclass
class StepResult:
    role: str
    title: str
    status: str  # completed / failed / skipped
    output: dict | None = None
    error: str | None = None
    elapsed_ms: int = 0
    attempts: int = 0


def _schema_hint(model: type[BaseModel]) -> str:
    import json

    return json.dumps(model.model_json_schema(), ensure_ascii=False)


def _coerce_issue_list(data: dict) -> dict:
    """宽容修正常见偏差：issues 元素缺字段时填充占位，保证结构完整。"""
    issues = data.get("issues")
    if isinstance(issues, list):
        fixed = []
        for item in issues:
            if isinstance(item, str):
                fixed.append({"type": "其他", "evidence": item, "suggestion": ""})
            elif isinstance(item, dict):
                fixed.append(
                    {
                        "type": str(item.get("type") or "其他"),
                        "evidence": str(item.get("evidence") or ""),
                        "suggestion": str(item.get("suggestion") or ""),
                    }
                )
        data["issues"] = fixed
    return data


def _coerce_fix_list(data: dict) -> dict:
    for key in ("priority_fixes",):
        items = data.get(key)
        if isinstance(items, list):
            fixed = []
            for item in items:
                if isinstance(item, str):
                    fixed.append({"title": item, "detail": ""})
                elif isinstance(item, dict):
                    fixed.append({"title": str(item.get("title") or ""), "detail": str(item.get("detail") or "")})
            data[key] = fixed
    return data


def default_steps() -> list[StepSpec]:
    """表达复盘工作流：结构分析师 → 内容深度分析师 → 表达教练。"""
    return [
        StepSpec(
            role="structure_analyst",
            title="结构分析师",
            system=(
                "你是表达结构分析师。分析给定回答的逻辑组织：得分 0-10、组织方式概述、"
                "使用的衔接词、存在的问题。每个问题必须引用原文片段作为证据。"
                "只输出 JSON，字段结构如下 JSON Schema：\n"
                + _schema_hint(StructureAnalystOutput)
            ),
            build_user=lambda transcript, prev: f"回答原文：\n{transcript}",
            output_model=StructureAnalystOutput,
        ),
        StepSpec(
            role="depth_analyst",
            title="内容深度分析师",
            system=(
                "你是内容深度分析师。分析给定回答的实质内容：得分 0-10、出现的具体例证、"
                "缺失的实质内容（如缺少数据 / 案例 / 权衡分析）、存在的问题。"
                "每个问题必须引用原文片段作为证据。只输出 JSON，字段结构如下 JSON Schema：\n"
                + _schema_hint(DepthAnalystOutput)
            ),
            build_user=lambda transcript, prev: f"回答原文：\n{transcript}",
            output_model=DepthAnalystOutput,
        ),
        StepSpec(
            role="expression_coach",
            title="表达教练",
            system=(
                "你是表达教练。基于结构分析与内容深度分析两份报告，给出整体评价、"
                "1-3 条优先改进项（title + detail）、1-4 条可立即执行的练习建议。"
                "只输出 JSON，字段结构如下 JSON Schema：\n"
                + _schema_hint(ExpressionCoachOutput)
            ),
            build_user=lambda transcript, prev: (
                f"回答原文：\n{transcript}\n\n"
                f"结构分析师报告：\n{prev.get('structure_analyst', {})}\n\n"
                f"内容深度分析师报告：\n{prev.get('depth_analyst', {})}"
            ),
            output_model=ExpressionCoachOutput,
            depends_on=["structure_analyst", "depth_analyst"],
        ),
    ]


def _step_dict(result: StepResult) -> dict:
    return {
        "role": result.role,
        "title": result.title,
        "status": result.status,
        "output": result.output,
        "error": result.error,
        "elapsed_ms": result.elapsed_ms,
        "attempts": result.attempts,
    }


def iter_expression_workflow(
    transcript: str,
    *,
    steps: list[StepSpec] | None = None,
    client: ArkClient | None = None,
    max_attempts: int = 2,
):
    """生成器版本的工作流：逐步产出事件，最后产出完整结果。

    事件格式：(kind, payload)
      - ("step_started", {role, title})
      - ("step_finished", step_dict)
      - ("done", {status, steps, model_name})
    全流程不抛异常，失败如实记录，不伪造任何角色输出。
    """
    steps = steps if steps is not None else default_steps()
    client = client or ArkClient()
    outputs: dict[str, dict] = {}
    results: list[StepResult] = []

    for step in steps:
        missing = [dep for dep in step.depends_on if dep not in outputs]
        if missing:
            result = StepResult(
                role=step.role,
                title=step.title,
                status="skipped",
                error=f"依赖的步骤未完成：{'、'.join(missing)}",
            )
            results.append(result)
            yield "step_finished", _step_dict(result)
            continue

        yield "step_started", {"role": step.role, "title": step.title}

        output: dict | None = None
        error: str | None = None
        attempts = 0
        started = time.monotonic()
        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            try:
                raw = client.chat_json(
                    step.system, step.build_user(transcript, outputs),
                    service="expression_workflow",
                )
                if step.role == "structure_analyst" or step.role == "depth_analyst":
                    raw = _coerce_issue_list(raw)
                if step.role == "expression_coach":
                    raw = _coerce_fix_list(raw)
                validated = step.output_model.model_validate(raw)
                output = validated.model_dump()
                break
            except (ValidationError, ArkError) as exc:
                error = _readable_error(exc)
                logger.info("workflow step %s attempt %d failed: %s", step.role, attempt, error)
        elapsed_ms = int((time.monotonic() - started) * 1000)

        if output is not None:
            outputs[step.role] = output
            result = StepResult(
                role=step.role,
                title=step.title,
                status="completed",
                output=output,
                elapsed_ms=elapsed_ms,
                attempts=attempts,
            )
        else:
            result = StepResult(
                role=step.role,
                title=step.title,
                status="failed",
                error=error,
                elapsed_ms=elapsed_ms,
                attempts=attempts,
            )
        results.append(result)
        yield "step_finished", _step_dict(result)

    completed = [r for r in results if r.status == "completed"]
    if len(completed) == len(steps):
        status = "completed"
    elif completed:
        status = "partial"
    else:
        status = "failed"
    yield "done", {
        "status": status,
        "steps": [_step_dict(r) for r in results],
        "model_name": client.model,
    }


def run_expression_workflow(
    transcript: str,
    *,
    steps: list[StepSpec] | None = None,
    client: ArkClient | None = None,
    max_attempts: int = 2,
) -> dict:
    """执行工作流。返回 {status, steps, model_name}，不抛异常（失败如实记录）。"""
    result: dict | None = None
    for kind, payload in iter_expression_workflow(
        transcript, steps=steps, client=client, max_attempts=max_attempts
    ):
        if kind == "done":
            result = payload
    assert result is not None
    return result


def _readable_error(exc: ValidationError | ArkError) -> str:
    if isinstance(exc, ValidationError):
        detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:3])
        return f"模型输出不符合角色 schema：{detail}"
    return str(exc)
