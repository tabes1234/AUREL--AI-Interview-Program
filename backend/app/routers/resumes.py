"""履历成章路由：简历 CRUD、模板、版本管理、AI 润色、拖拽解析与导出（按登录用户隔离）。

导出为真实文件生成（reportlab / python-docx），无真实导出逻辑的假按钮不存在。
"""

import io
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.models import JobAnalysis, Resume
from app.routers.interviews import get_ark_client
from app.schemas.resume import (
    ResumeContent,
    ResumeCreateRequest,
    ResumeDetail,
    ResumeOptimizeForJobRequest,
    ResumeOptimizeForJobResponse,
    ResumeParseResponse,
    ResumePolishRequest,
    ResumePolishResponse,
    ResumeSaveRequest,
    ResumeSummary,
    ResumeTemplateOut,
    ResumeVersionDetail,
    ResumeVersionSummary,
    TemplateSourceOut,
)
from app.models import JobAnalysis
from app.services import interview_service, resume_export, resume_service
from app.services.ark_client import ArkClient, ArkError, ArkNotConfiguredError
from app.services.knowledge_service import DocumentError, extract_text
from app.services.resume_templates import (
    RESUME_TEMPLATES,
    TEMPLATE_BY_ID,
    TEMPLATE_REFERENCE_SOURCES,
)

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PARSE_MAX_FILE_BYTES = 8 * 1024 * 1024


def _summary(resume: Resume) -> ResumeSummary:
    return ResumeSummary(
        id=resume.id,
        title=resume.title,
        template_id=resume.template_id,
        current_version_no=resume.current_version_no,
        created_at=resume.created_at,
        updated_at=resume.updated_at,
    )


def _detail(resume: Resume, *, with_versions: bool = True) -> ResumeDetail:
    versions = (
        [
            ResumeVersionSummary(
                version_no=v.version_no,
                title=v.title,
                template_id=v.template_id,
                note=v.note,
                created_at=v.created_at,
            )
            for v in resume.versions
        ]
        if with_versions
        else []
    )
    return ResumeDetail(
        **_summary(resume).model_dump(),
        content=resume.content,
        versions=versions,
    )


def _validate_template(template_id: str) -> str:
    if template_id not in TEMPLATE_BY_ID:
        raise HTTPException(status_code=422, detail="简历模板不存在")
    return template_id


@router.get("/templates", response_model=list[ResumeTemplateOut])
def list_templates(user_id: int = Depends(current_user_id)) -> list[ResumeTemplateOut]:
    """模板目录：分节顺序与主题色由后端统一下发，导出与预览共用同一事实源。"""
    return [ResumeTemplateOut(**t) for t in RESUME_TEMPLATES]


@router.get("/template-sources", response_model=list[TemplateSourceOut])
def list_template_sources(user_id: int = Depends(current_user_id)) -> list[TemplateSourceOut]:
    """模板设计参考来源：官方指导资料链接与查阅时间（真实可追溯）。"""
    return [TemplateSourceOut(**s) for s in TEMPLATE_REFERENCE_SOURCES]


@router.post("/parse", response_model=ResumeParseResponse)
async def parse_resume_file(
    file: UploadFile = File(...),
    jd_text: str = Form(""),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> ResumeParseResponse:
    """拖拽解析简历：安全提取文本（txt/md/docx/pdf），AI 忠实转录为结构化内容。

    只提取文本、不执行文件内容；结果不落库。
    AI 不可用或未通过防编造校验时如实降级：text 照常返回，
    title/position/content 为空并附 parse_error，绝不伪造。
    """
    data = await file.read()
    if len(data) > PARSE_MAX_FILE_BYTES:
        raise HTTPException(status_code=422, detail="文件过大：请上传 8MB 以内的简历文件")
    filename = file.filename or "resume"
    try:
        text = extract_text(filename, data)
    except DocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not text.strip():
        raise HTTPException(status_code=422, detail="文件中未提取到文本内容")

    fallback_title = filename.rsplit(".", 1)[0].strip()[:60] or "我的简历"
    try:
        title, position, content = resume_service.parse_resume_ai(
            client, resume_text=text, jd_text=jd_text
        )
    except ArkNotConfiguredError as exc:
        return ResumeParseResponse(filename=filename, text=text, parse_error=str(exc))
    except ArkError as exc:
        return ResumeParseResponse(
            filename=filename, text=text, parse_error=f"AI 解析失败：{exc}"
        )

    return ResumeParseResponse(
        filename=filename,
        text=text,
        title=title or fallback_title,
        position=position or None,
        content=content.model_dump(),
    )


@router.post("", response_model=ResumeDetail, status_code=201)
def create_resume(
    request: ResumeCreateRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ResumeDetail:
    template_id = _validate_template(request.template_id)
    resume = resume_service.create_resume(
        db, title=request.title, template_id=template_id, content=request.content, user_id=user_id
    )
    return _detail(resume)


@router.get("", response_model=list[ResumeSummary])
def list_resumes(
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> list[ResumeSummary]:
    return [_summary(r) for r in resume_service.list_resumes(db, user_id=user_id)]


@router.get("/{resume_id}", response_model=ResumeDetail)
def get_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ResumeDetail:
    return _detail(resume_service.get_owned_resume(db, resume_id, user_id))


@router.put("/{resume_id}", response_model=ResumeDetail)
def save_resume(
    resume_id: int,
    request: ResumeSaveRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ResumeDetail:
    """保存草稿并生成新版本快照。"""
    resume = resume_service.get_owned_resume(db, resume_id, user_id)
    if request.template_id:
        _validate_template(request.template_id)
    resume = resume_service.save_resume(db, resume, request)
    return _detail(resume)


@router.delete("/{resume_id}", status_code=204)
def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> None:
    resume = resume_service.get_owned_resume(db, resume_id, user_id)
    db.delete(resume)
    db.commit()


@router.get("/{resume_id}/versions", response_model=list[ResumeVersionSummary])
def list_versions(
    resume_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> list[ResumeVersionSummary]:
    resume = resume_service.get_owned_resume(db, resume_id, user_id)
    return [
        ResumeVersionSummary(
            version_no=v.version_no,
            title=v.title,
            template_id=v.template_id,
            note=v.note,
            created_at=v.created_at,
        )
        for v in resume.versions
    ]


@router.get("/{resume_id}/versions/{version_no}", response_model=ResumeVersionDetail)
def get_version(
    resume_id: int,
    version_no: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ResumeVersionDetail:
    resume = resume_service.get_owned_resume(db, resume_id, user_id)
    version = resume_service.get_version(db, resume, version_no)
    return ResumeVersionDetail(
        version_no=version.version_no,
        title=version.title,
        template_id=version.template_id,
        note=version.note,
        created_at=version.created_at,
        content=version.content,
    )


@router.post("/{resume_id}/versions/{version_no}/restore", response_model=ResumeDetail)
def restore_version(
    resume_id: int,
    version_no: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ResumeDetail:
    resume = resume_service.get_owned_resume(db, resume_id, user_id)
    version = resume_service.get_version(db, resume, version_no)
    return _detail(resume_service.restore_version(db, resume, version))


@router.post("/{resume_id}/versions/{version_no}/duplicate", response_model=ResumeVersionDetail)
def duplicate_version(
    resume_id: int,
    version_no: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ResumeVersionDetail:
    resume = resume_service.get_owned_resume(db, resume_id, user_id)
    version = resume_service.get_version(db, resume, version_no)
    new_version = resume_service.duplicate_version(db, resume, version)
    return ResumeVersionDetail(
        version_no=new_version.version_no,
        title=new_version.title,
        template_id=new_version.template_id,
        note=new_version.note,
        created_at=new_version.created_at,
        content=new_version.content,
    )


@router.post("/{resume_id}/polish", response_model=ResumePolishResponse)
def polish_resume_text(
    resume_id: int,
    request: ResumePolishRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> ResumePolishResponse:
    """AI 表达优化：只返回建议（含防捏造校验），不写入简历，需用户确认后应用。"""
    resume_service.get_owned_resume(db, resume_id, user_id)  # 校验归属（不读取内容）
    try:
        polished, notes, model_name = resume_service.polish_text(
            client, section=request.section, text=request.text
        )
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc
    return ResumePolishResponse(polished=polished, notes=notes, model_name=model_name)


@router.post("/{resume_id}/optimize-for-job", response_model=ResumeOptimizeForJobResponse)
def optimize_resume_for_job(
    resume_id: int,
    request: ResumeOptimizeForJobRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> ResumeOptimizeForJobResponse:
    """面向真实岗位的简历优化诊断：关键词缺口（统计）+ 表达追问（AI，引用须来自原文）。

    只诊断、不代写：绝不虚构经历与数字，建议应用与否由用户决定。
    输入可以是知岗解析（job_analysis_id）或直接粘贴的 JD。
    """
    resume = resume_service.get_owned_resume(db, resume_id, user_id)
    content = ResumeContent(**resume.content)

    if request.job_analysis_id is not None:
        analysis = db.get(JobAnalysis, request.job_analysis_id)
        if analysis is None or analysis.user_id != user_id:
            raise HTTPException(status_code=404, detail="岗位分析不存在")
        if analysis.status != "ready" or not analysis.jd_text:
            raise HTTPException(status_code=409, detail="该岗位分析尚未成功完成，无法诊断")
        jd_text, position = analysis.jd_text, analysis.title
        analysis_result = analysis.result
    else:
        jd_text = (request.jd_text or "").strip()
        if len(jd_text) < 30:
            raise HTTPException(
                status_code=422, detail="请提供知岗分析 ID 或粘贴完整岗位描述（至少 30 字符）"
            )
        position = request.position.strip() or "目标岗位"
        analysis_result = None

    try:
        result = resume_service.optimize_for_job(
            client,
            resume_content=content,
            jd_text=jd_text,
            position=position[:120],
            analysis_result=analysis_result,
        )
    except ArkNotConfiguredError as exc:
        raise interview_service.map_ark_error(exc) from exc
    except ArkError as exc:
        raise interview_service.map_ark_error(exc) from exc
    return ResumeOptimizeForJobResponse(**result)


@router.get("/{resume_id}/export")
def export_resume(
    resume_id: int,
    format: str = "pdf",
    version_no: int | None = None,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> StreamingResponse:
    """导出简历：PDF / DOCX 真实生成，内容与版本快照一致。"""
    fmt = format.lower()
    if fmt not in ("pdf", "docx"):
        raise HTTPException(status_code=422, detail="导出格式仅支持 pdf 或 docx")
    resume = resume_service.get_owned_resume(db, resume_id, user_id)
    if version_no is not None and version_no != resume.current_version_no:
        version = resume_service.get_version(db, resume, version_no)
        content, template_id, v_no = ResumeContent(**version.content), version.template_id, version.version_no
    else:
        content, template_id, v_no = ResumeContent(**resume.content), resume.template_id, resume.current_version_no
    _validate_template(template_id)

    try:
        if fmt == "pdf":
            payload = resume_export.export_pdf(content, template_id)
            media_type = "application/pdf"
        else:
            payload = resume_export.export_docx(content, template_id)
            media_type = DOCX_MEDIA_TYPE
    except Exception as exc:  # noqa: BLE001 — 导出失败如实报错，不返回损坏文件
        raise HTTPException(status_code=500, detail=f"导出失败：{exc.__class__.__name__}") from exc

    filename = resume_export.export_filename(resume.title, v_no, fmt)
    quoted = quote(filename)
    ascii_name = filename.encode("ascii", "ignore").decode() or "resume"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted}",
        },
    )
