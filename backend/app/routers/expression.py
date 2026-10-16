"""T5/T6 表达分析路由：ASR 状态、音频转录、多角色工作流分析（含 SSE 流式）、历史记录。

表达记录按登录用户隔离；/status 为公开状态端点。
"""

import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ark_configured, ark_model
from app.database import get_db
from app.dependencies import current_user_id
from app.models import ExpressionAnalysis
from app.routers.interviews import get_ark_client
from app.schemas.expression import (
    AsrStatusOut,
    AudioMetricsOut,
    ExpressionAnalyzeRequest,
    ExpressionDetail,
    ExpressionRecordOut,
    ExpressionStatusResponse,
    ExpressionTranscribeResponse,
    ExpressionWorkflowResponse,
    PauseProfileOut,
    SpeechMetricsOut,
)
from app.services import audio_metrics
from app.services.ark_client import ArkClient
from app.services.asr_service import AsrError, asr_status, get_asr_provider
from app.services.expression_workflow import iter_expression_workflow, run_expression_workflow
from app.services.usage_tracking import record_event

logger = logging.getLogger("aurel.expression")

router = APIRouter(prefix="/api/v1/expression", tags=["expression"])

MAX_AUDIO_BYTES = 20 * 1024 * 1024  # 豆包语音极速版建议 20MB 以内

SUPPORTED_AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac")


def _not_configured_message() -> str:
    """无任何就绪提供方时，给出全部可选路径的如实指引。"""
    status = asr_status()
    hints = []
    for info in status["providers"].values():
        if not info["configured"] and info.get("setup"):
            hints.append(f"{info['label']}：{info['setup']}")
    return (
        "语音转文字尚未配置，本次未生成转录，本条记录只包含本地可测的客观指标。"
        "可任选其一启用：" + "；".join(hints)
    )


@router.get("/status", response_model=ExpressionStatusResponse)
def expression_status() -> ExpressionStatusResponse:
    """语音服务与 AI 模型配置状态（不泄露密钥）。"""
    status = asr_status()
    return ExpressionStatusResponse(
        asr=AsrStatusOut(**status),
        ark={"configured": ark_configured(), "model": ark_model() if ark_configured() else None},
        audio_limits={
            "max_bytes": MAX_AUDIO_BYTES,
            "max_mb": MAX_AUDIO_BYTES // (1024 * 1024),
            "supported_extensions": list(SUPPORTED_AUDIO_EXTENSIONS),
            "note": "WAV 音频可在本地直接计算时长与停顿指标；其他格式依赖语音服务返回时长",
        },
    )


@router.post("/transcribe", response_model=ExpressionTranscribeResponse, status_code=201)
async def transcribe_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
) -> ExpressionTranscribeResponse:
    """上传音频：本地计算客观指标（WAV 时长 / 停顿），ASR 配置时进行真实转录。

    ASR 未配置时 transcript 为空并明确标注 not_configured——不伪造转录，
    本地可测指标照常返回。
    """
    filename = file.filename or "audio"
    lowered = filename.lower()
    if not lowered.endswith(SUPPORTED_AUDIO_EXTENSIONS):
        raise HTTPException(
            status_code=415,
            detail=f"不支持的音频格式：仅支持 {'、'.join(SUPPORTED_AUDIO_EXTENSIONS)}",
        )

    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="音频文件为空")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"音频文件过大（{len(audio) // (1024 * 1024)} MB），上限 {MAX_AUDIO_BYTES // (1024 * 1024)} MB",
        )

    # 本地客观指标（无外部依赖）：WAV 时长 + 静音停顿画像
    audio_out = AudioMetricsOut(available=False, unavailable_reason=None)
    pause_profile = None
    try:
        duration_ms, samples, rate = audio_metrics.parse_wav(audio)
        pause_profile = audio_metrics.detect_pauses(samples, rate)
        audio_out = AudioMetricsOut(
            available=True,
            duration_ms=duration_ms,
            pause=PauseProfileOut(
                pause_count=pause_profile.pause_count,
                longest_pause_ms=pause_profile.longest_pause_ms,
                total_pause_ms=pause_profile.total_pause_ms,
                silence_ratio=pause_profile.silence_ratio,
            ),
        )
    except audio_metrics.AudioFormatError as exc:
        audio_out = AudioMetricsOut(available=False, unavailable_reason=str(exc))

    # 真实转录（可插拔；未配置时如实标注）
    transcript: str | None = None
    asr_provider_name: str | None = None
    asr_error: str | None = None
    provider = get_asr_provider()
    if provider is None:
        asr_status_value = "not_configured"
        asr_error = _not_configured_message()
        logger.info("transcribe skipped: ASR not configured")
    else:
        try:
            result = provider.transcribe(
                audio,
                filename,
                content_type=file.content_type or "audio/wav",
            )
            transcript = result.text
            asr_provider_name = result.provider
            asr_status_value = "ok"
            if audio_out.duration_ms is None and result.duration_ms:
                audio_out = AudioMetricsOut(
                    available=True,
                    duration_ms=result.duration_ms,
                    pause=audio_out.pause,
                )
        except AsrError as exc:
            asr_status_value = "failed"
            asr_error = str(exc)
            logger.warning("transcribe failed: %s", asr_error)

    speech = audio_metrics.speech_metrics(transcript, audio_out.duration_ms, pause_profile)
    record = ExpressionAnalysis(
        source="upload",
        filename=filename,
        transcript=transcript,
        asr_status=asr_status_value,
        asr_provider=asr_provider_name,
        asr_error=asr_error,
        audio_duration_ms=audio_out.duration_ms,
        metrics={
            "audio": audio_out.model_dump(exclude_none=False),
            "speech": speech.model_dump(exclude_none=False),
        },
        user_id=user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return ExpressionTranscribeResponse(
        id=record.id,
        source=record.source,
        transcript=transcript,
        asr_status=asr_status_value,
        asr_provider=asr_provider_name,
        asr_error=asr_error,
        audio=audio_out,
        speech=SpeechMetricsOut(**speech.model_dump(exclude_none=False)),
    )


@router.post("/analyze", response_model=ExpressionWorkflowResponse, status_code=201)
def analyze_expression(
    request: ExpressionAnalyzeRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> ExpressionWorkflowResponse:
    """T6 多角色工作流：结构分析师 → 内容深度分析师 → 表达教练。

    输入可以是直接粘贴的文本，或引用一次转录记录（analysis_id）。
    """
    transcript, source, filename = _resolve_analyze_input(request, db, user_id)
    workflow = run_expression_workflow(transcript, client=client)
    record = _persist_workflow_record(db, transcript, source, filename, workflow, user_id)
    return ExpressionWorkflowResponse(
        id=record.id,
        asr_status=record.asr_status,
        transcript=record.transcript,
        metrics=record.metrics,
        workflow=workflow,
        model_name=record.model_name,
    )


def _resolve_analyze_input(
    request: ExpressionAnalyzeRequest, db: Session, user_id: int
) -> tuple[str, str, str | None]:
    """校验并解析分析输入：text 与 analysis_id 必须二选一，返回 (转录文本, 来源, 文件名)。"""
    if (request.text is None) == (request.analysis_id is None):
        raise HTTPException(status_code=400, detail="text 与 analysis_id 必须二选一")

    if request.analysis_id is not None:
        record = db.get(ExpressionAnalysis, request.analysis_id)
        if record is None or record.user_id != user_id:
            raise HTTPException(status_code=404, detail="转录记录不存在")
        transcript = (record.transcript or "").strip()
        if not transcript:
            raise HTTPException(
                status_code=409,
                detail="该记录没有可用转录（ASR 未配置或转录失败），无法进行文本分析",
            )
        return transcript, record.source, record.filename
    return (request.text or "").strip(), "text", None


def _persist_workflow_record(
    db: Session, transcript: str, source: str, filename: str | None, workflow: dict,
    user_id: int,
) -> ExpressionAnalysis:
    record = ExpressionAnalysis(
        source=source,
        filename=filename,
        transcript=transcript,
        asr_status="ok" if source != "text" else "not_attempted",
        asr_provider=None,
        asr_error=None,
        audio_duration_ms=None,
        metrics={
            "audio": None,
            "speech": audio_metrics.speech_metrics(transcript, None).model_dump(exclude_none=False),
        },
        workflow=workflow,
        model_name=workflow.get("model_name"),
        user_id=user_id,
    )
    db.add(record)
    record_event(db, user_id=user_id, module="xiezou", name="expression_analyze")
    db.commit()
    db.refresh(record)
    return record


@router.post("/analyze/stream", status_code=201)
def analyze_expression_stream(
    request: ExpressionAnalyzeRequest,
    db: Session = Depends(get_db),
    client: ArkClient = Depends(get_ark_client),
    user_id: int = Depends(current_user_id),
) -> StreamingResponse:
    """T8 SSE 流式复盘：逐步推送每个角色的开始/结束事件，最后推送完整结果。

    事件流格式：`event: step_started|step_finished|result|error` + `data: <json>`。
    前端据此实时展示「结构分析师阅读中…」等进度。
    """
    transcript, source, filename = _resolve_analyze_input(request, db, user_id)

    def event_stream():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        workflow: dict | None = None
        try:
            for kind, payload in iter_expression_workflow(transcript, client=client):
                if kind == "done":
                    workflow = payload
                else:
                    yield sse(kind, payload)
        except Exception as exc:  # 防御：流中任何异常都如实告知，不伪造结果
            yield sse("error", {"detail": str(exc)})
            return

        if workflow is None:
            yield sse("error", {"detail": "复盘流程未产出结果"})
            return

        record = _persist_workflow_record(db, transcript, source, filename, workflow, user_id)
        response = ExpressionWorkflowResponse(
            id=record.id,
            asr_status=record.asr_status,
            transcript=record.transcript,
            metrics=record.metrics,
            workflow=workflow,
            model_name=record.model_name,
        )
        yield sse("result", response.model_dump(mode="json"))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/records", response_model=list[ExpressionRecordOut])
def list_records(
    limit: int = 50,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    statement = (
        select(ExpressionAnalysis)
        .where(ExpressionAnalysis.user_id == user_id)
        .order_by(ExpressionAnalysis.created_at.desc(), ExpressionAnalysis.id.desc())
        .limit(limit)
    )
    return [
        ExpressionRecordOut(
            id=r.id,
            source=r.source,
            filename=r.filename,
            asr_status=r.asr_status,
            asr_provider=r.asr_provider,
            asr_error=r.asr_error,
            has_transcript=bool(r.transcript),
            has_workflow=bool(r.workflow),
            created_at=r.created_at,
        )
        for r in db.scalars(statement)
    ]


@router.get("/records/{record_id}", response_model=ExpressionDetail)
def get_record(
    record_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    record = db.get(ExpressionAnalysis, record_id)
    if record is None or record.user_id != user_id:
        raise HTTPException(status_code=404, detail="表达分析记录不存在")
    return ExpressionDetail(
        id=record.id,
        source=record.source,
        filename=record.filename,
        asr_status=record.asr_status,
        asr_provider=record.asr_provider,
        asr_error=record.asr_error,
        has_transcript=bool(record.transcript),
        has_workflow=bool(record.workflow),
        created_at=record.created_at,
        transcript=record.transcript,
        audio_duration_ms=record.audio_duration_ms,
        metrics=record.metrics,
        workflow=record.workflow,
        model_name=record.model_name,
    )


@router.delete("/records/{record_id}", status_code=204)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    record = db.get(ExpressionAnalysis, record_id)
    if record is None or record.user_id != user_id:
        raise HTTPException(status_code=404, detail="表达分析记录不存在")
    db.delete(record)
    db.commit()
