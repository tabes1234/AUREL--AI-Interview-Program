"""T2 知识库路由：上传、列表、详情、检索验证、删除（按登录用户隔离）。"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.models import KnowledgeDocument
from app.schemas.features import (
    KnowledgeDocumentDetail,
    KnowledgeDocumentOut,
    KnowledgeSearchResponse,
)
from app.services import knowledge_service
from app.services.knowledge_service import DocumentError
from app.services.usage_tracking import record_event

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def get_document(db: Session, document_id: int, user_id: int) -> KnowledgeDocument:
    document = db.get(KnowledgeDocument, document_id)
    if document is None or document.user_id != user_id:
        raise HTTPException(status_code=404, detail="知识库文档不存在")
    return document


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
def list_documents(
    db: Session = Depends(get_db), user_id: int = Depends(current_user_id)
):
    documents = knowledge_service.list_documents(db, user_id=user_id)
    return [
        KnowledgeDocumentOut(
            id=doc.id,
            title=doc.title,
            filename=doc.filename,
            char_count=doc.char_count,
            status=doc.status,
            error_message=doc.error_message,
            created_at=doc.created_at,
            chunk_count=len(doc.chunks),
        )
        for doc in documents
    ]


@router.post("/documents", response_model=KnowledgeDocumentOut, status_code=201)
async def upload_document(
    file: UploadFile,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=422, detail="文件内容为空")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件过大（上限 5MB）")
    filename = file.filename or "untitled.txt"
    try:
        text = knowledge_service.extract_text(filename, data)
    except DocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if len(text.strip()) < 20:
        raise HTTPException(status_code=422, detail="文档内容过短（至少 20 字符）")
    if len(text) > knowledge_service.MAX_DOCUMENT_CHARS:
        raise HTTPException(status_code=413, detail="文档过长（上限 20 万字符）")
    document = knowledge_service.create_document(
        db, title=filename.rsplit(".", 1)[0], filename=filename, text=text, user_id=user_id
    )
    record_event(db, user_id=user_id, module="zhicang", name="document_upload")
    db.commit()
    return KnowledgeDocumentOut(
        id=document.id,
        title=document.title,
        filename=document.filename,
        char_count=document.char_count,
        status=document.status,
        error_message=document.error_message,
        created_at=document.created_at,
        chunk_count=len(document.chunks),
    )


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentDetail)
def get_document_detail(
    document_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    document = get_document(db, document_id, user_id)
    return KnowledgeDocumentDetail(
        id=document.id,
        title=document.title,
        filename=document.filename,
        char_count=document.char_count,
        status=document.status,
        error_message=document.error_message,
        created_at=document.created_at,
        chunk_count=len(document.chunks),
        content_text=document.content_text,
        chunks=list(document.chunks),
    )


@router.get("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    q: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="检索词不能为空")
    evidence = knowledge_service.retrieve_evidence(db, query, top_k=5, user_id=user_id)
    return KnowledgeSearchResponse(
        query=query,
        evidence=[
            {
                "document_id": e.document_id,
                "document_title": e.document_title,
                "chunk_id": e.chunk_id,
                "chunk_index": e.chunk_index,
                "content": e.content,
                "score": e.score,
            }
            for e in evidence
        ],
    )


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    document = get_document(db, document_id, user_id)
    db.delete(document)
    db.commit()
