"""知岗路由：JD 解析、分析历史、问澜联动与简历匹配（全部按登录用户隔离）。"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.models import JobAnalysis, JobPosition
from app.routers.interviews import get_ark_client
from app.schemas.interview import InterviewCreateRequest
from app.schemas.jobs import (
    InterviewFromJobRequest,
    JobAnalysisDetail,
    JobAnalysisSummary,
    JobAnalysisUpdateRequest,
    JobResumeMatchRequest,
    JobResumeMatchResponse,
    JdAnalyzeRequest,
    JdUploadResponse,
)
from app.schemas.resume import ResumeContent
from app.services import interview_service, jd_analysis, jd_matching, knowledge_service
from app.services import resume_service
from app.services.ark_client import ArkClient, ArkError

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def _owned_analysis(db: Session, analysis_id: int, user_id: int) -> JobAnalysis:
    analysis = db.get(JobAnalysis, analysis_id)
    if analysis is None or analysis.user_id != user_id:
        raise HTTPException(status_code=404, detail="岗位分析不存在")
    return analysis


def _summary(analysis: JobAnalysis) -> JobAnalysisSummary:
    return JobAnalysisSummary(
        id=analysis.id,
        title=analysis.title,
        version_no=analysis.version_no,
        status=analysis.status,
        created_at=analysis.created_at,
        jd_preview=analysis.jd_text[:120],
        source_job_id=analysis.source_job_id,
    )


def _detail(analysis: JobAnalysis) -> JobAnalysisDetail:
    return JobAnalysisDetail(
        **_summary(analysis).model_dump(),
        jd_text=analysis.jd_text,
        result=analysis.result,
        model_name=analysis.model_name,
        error_message=analysis.error_message,
        user_edited=bool((analysis.result or {}).get("user_edited")),
    )


@router.post("/analyze", response_model=JobAnalysisDetail, status_code=201)
def analyze_jd(
    request: JdAnalyzeRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> JobAnalysisDetail:
    """解析粘贴的 JD 文本：结构化校验 + 证据核验，失败不伪造结果。"""
    jd_text = request.jd_text.strip()
    if len(jd_text) < jd_analysis.MIN_JD_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"职位描述过短（至少 {jd_analysis.MIN_JD_CHARS} 字符），请粘贴完整的岗位 JD",
        )
    try:
        result, model_name = jd_analysis.analyze_jd(client, jd_text)
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc

    # 同一用户同一 JD 的重复解析：版本递增，保留全部历史
    fingerprint = jd_analysis.jd_fingerprint(jd_text)
    latest = db.scalar(
        select(JobAnalysis.version_no)
        .where(JobAnalysis.user_id == user_id, JobAnalysis.jd_hash == fingerprint)
        .order_by(JobAnalysis.version_no.desc())
        .limit(1)
    )
    source_job_id = request.source_job_id
    if source_job_id is not None:
        # 记录来源岗位（知潮资料库条目），建立「目录 → 分析」的可追溯链路
        source = db.get(JobPosition, source_job_id)
        if source is None:
            raise HTTPException(status_code=404, detail="来源岗位不存在")
    analysis = JobAnalysis(
        user_id=user_id,
        title=result.position_name.strip()[:120],
        jd_text=jd_text,
        jd_hash=fingerprint,
        version_no=(latest or 0) + 1,
        status="ready",
        result=result.model_dump(),
        model_name=model_name,
        source_job_id=source_job_id,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    _sync_skill_graph(db, analysis)
    return _detail(analysis)


def _sync_skill_graph(db: Session, analysis: JobAnalysis) -> None:
    """知岗解析完成后同步能力图谱（第十五阶段）：目标岗位 + 岗位要求技能（pending）。"""
    try:
        from app.services import career_skill_graph

        career_skill_graph.update_after_job_analysis(db, analysis.user_id, analysis)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("aurel.career").warning(
            "知岗解析后能力图谱同步失败", exc_info=True
        )


@router.post("/upload", response_model=JdUploadResponse, status_code=201)
async def upload_jd_file(
    file: UploadFile,
    user_id: int = Depends(current_user_id),
) -> JdUploadResponse:
    """上传岗位描述文件（txt/md/docx/pdf）：仅安全提取文本，不执行文件内容。"""
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=422, detail="文件内容为空")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件过大（上限 5MB）")
    filename = file.filename or "jd.txt"
    try:
        text = knowledge_service.extract_text(filename, data)
    except knowledge_service.DocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if len(text.strip()) < jd_analysis.MIN_JD_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"文件中可提取的文本过少（至少 {jd_analysis.MIN_JD_CHARS} 字符）",
        )
    return JdUploadResponse(
        filename=filename, text=text[: jd_analysis.MAX_JD_CHARS], char_count=len(text)
    )


@router.get("/analyses", response_model=list[JobAnalysisSummary])
def list_analyses(
    limit: int = 50,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> list[JobAnalysisSummary]:
    statement = (
        select(JobAnalysis)
        .where(JobAnalysis.user_id == user_id)
        .order_by(JobAnalysis.created_at.desc(), JobAnalysis.id.desc())
        .limit(min(max(limit, 1), 100))
    )
    return [_summary(a) for a in db.scalars(statement)]


@router.get("/analyses/{analysis_id}", response_model=JobAnalysisDetail)
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> JobAnalysisDetail:
    return _detail(_owned_analysis(db, analysis_id, user_id))


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> None:
    analysis = _owned_analysis(db, analysis_id, user_id)
    db.delete(analysis)
    db.commit()


@router.patch("/analyses/{analysis_id}", response_model=JobAnalysisDetail)
def update_analysis(
    analysis_id: int,
    request: JobAnalysisUpdateRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> JobAnalysisDetail:
    """用户修改解析结果：结构化校验 + 证据核验标准不降低，并标记 user_edited。

    修改后的结论仍必须能在 JD 原文中定位；定位不到的照常标记 is_inferred（模型推断），
    用户补充的判断同样不得脱离原文编造。
    """
    analysis = _owned_analysis(db, analysis_id, user_id)
    if analysis.status != "ready" or analysis.result is None:
        raise HTTPException(status_code=409, detail="该分析尚未成功完成，无法修改")
    try:
        verified = jd_analysis.revalidate_result(request.result, analysis.jd_text)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail=f"解析结果结构不符合要求：{jd_analysis._brief(str(exc), 160)}"
        ) from exc
    if request.title and request.title.strip():
        analysis.title = request.title.strip()[:120]
    analysis.result = {**verified.model_dump(), "user_edited": True}
    db.commit()
    db.refresh(analysis)
    return _detail(analysis)


@router.post("/analyses/{analysis_id}/interview-task", status_code=201)
def create_interview_from_analysis(
    analysis_id: int,
    request: InterviewFromJobRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
):
    """知岗 × 问澜联动：把解析出的职责/技能/经验/面试方向传入现有题集生成流程。

    复用 interview_service.create_task（现有问澜生成逻辑），不另建生成链路。
    """
    analysis = _owned_analysis(db, analysis_id, user_id)
    if analysis.status != "ready" or analysis.result is None:
        raise HTTPException(status_code=409, detail="该分析尚未成功完成，无法生成面试题")

    position = (request.position or analysis.title or "目标岗位").strip()[:120]
    description = jd_analysis.compose_interview_description(analysis.result, analysis.jd_text)
    interview_request = InterviewCreateRequest(
        position=position,
        description=description,
        difficulty=request.difficulty,
        language=request.language,
        question_count=request.question_count,
    )
    try:
        task = interview_service.create_task(db, interview_request, client, user_id=user_id)
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc
    from app.routers.interviews import _task_detail

    return _task_detail(task)


@router.post("/analyses/{analysis_id}/match", response_model=JobResumeMatchResponse, status_code=201)
def match_analysis_with_resume(
    analysis_id: int,
    request: JobResumeMatchRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> JobResumeMatchResponse:
    """知岗 × 履历成章/合契联动：结构化岗位要求与简历的可解释匹配。"""
    analysis = _owned_analysis(db, analysis_id, user_id)
    if analysis.status != "ready" or analysis.result is None:
        raise HTTPException(status_code=409, detail="该分析尚未成功完成，无法进行匹配")
    resume = resume_service.get_owned_resume(db, request.resume_id, user_id)
    content = ResumeContent(**resume.content)

    match = jd_matching.match_analysis_with_resume(
        client,
        jd_text=analysis.jd_text,
        analysis_result=analysis.result,
        resume_content=content,
    )
    return JobResumeMatchResponse(
        job_analysis_id=analysis.id,
        resume_id=resume.id,
        resume_title=resume.title,
        **match,
    )
