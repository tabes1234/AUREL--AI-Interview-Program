"""T2 RAG：文档提取、分块与知识库检索（证据可追溯）。"""

import io
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.retrieval import BM25Index

SUPPORTED_SUFFIXES = (".txt", ".md", ".docx", ".pdf")
MAX_DOCUMENT_CHARS = 200_000
CHUNK_TARGET_CHARS = 500

_DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


class DocumentError(Exception):
    """文档解析失败（message 面向用户可读）。"""


def extract_text(filename: str, data: bytes) -> str:
    lower = filename.lower()
    if lower.endswith((".txt", ".md")):
        for encoding in ("utf-8", "gb18030"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise DocumentError("无法解码文件内容：请使用 UTF-8 或 GB18030 编码的文本文件")
    if lower.endswith(".docx"):
        return _extract_docx(data)
    if lower.endswith(".pdf"):
        return _extract_pdf(data)
    supported = "、".join(SUPPORTED_SUFFIXES)
    raise DocumentError(f"暂不支持的文件格式：请上传 {supported} 文件")


def _extract_pdf(data: bytes) -> str:
    """PDF 纯文本提取（pypdf）：只读取文本流，不执行文件内的任何脚本或附件。"""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except (PdfReadError, ValueError, OSError) as exc:
        raise DocumentError("无法解析 PDF 文件：文件可能已损坏或已加密") from exc
    text = "\n".join(part.strip() for part in pages if part.strip())
    if not text:
        raise DocumentError("PDF 中未提取到文本内容（可能是扫描图片版）")
    return text


def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise DocumentError("无法解析 docx 文件：文件可能已损坏") from exc
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise DocumentError("无法解析 docx 文件：内部结构异常") from exc
    paragraphs: list[str] = []
    for para in root.iter(f"{{{ _DOCX_NS['w'] }}}p"):
        runs = [node.text or "" for node in para.iter(f"{{{ _DOCX_NS['w'] }}}t")]
        line = "".join(runs).strip()
        if line:
            paragraphs.append(line)
    text = "\n".join(paragraphs).strip()
    if not text:
        raise DocumentError("docx 中未提取到文本内容")
    return text


def chunk_text(text: str) -> list[str]:
    """按段落聚合成约 CHUNK_TARGET_CHARS 的块，保证句子完整。"""
    normalized = text.replace("\r\n", "\n").strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", normalized) if p.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        # 单段超长时按句号硬切
        if len(paragraph) > CHUNK_TARGET_CHARS * 2:
            for sentence in _split_long_paragraph(paragraph):
                if buffer:
                    chunks.append(buffer)
                    buffer = ""
                chunks.append(sentence)
            continue
        if len(buffer) + len(paragraph) + 1 > CHUNK_TARGET_CHARS and buffer:
            chunks.append(buffer)
            buffer = paragraph
        else:
            buffer = f"{buffer}\n{paragraph}" if buffer else paragraph
    if buffer:
        chunks.append(buffer)
    return chunks


def _split_long_paragraph(paragraph: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；.!?;])", paragraph)
    merged: list[str] = []
    buffer = ""
    for part in parts:
        if not part.strip():
            continue
        if len(buffer) + len(part) > CHUNK_TARGET_CHARS and buffer:
            merged.append(buffer.strip())
            buffer = part
        else:
            buffer += part
    if buffer.strip():
        merged.append(buffer.strip())
    return merged


def create_document(
    db: Session, *, title: str, filename: str, text: str, user_id: int
) -> KnowledgeDocument:
    chunks = chunk_text(text)
    document = KnowledgeDocument(
        title=title.strip() or filename,
        filename=filename,
        content_text=text,
        char_count=len(text),
        status="ready",
        user_id=user_id,
    )
    db.add(document)
    db.flush()
    for index, chunk in enumerate(chunks):
        db.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=index,
                content=chunk,
                char_count=len(chunk),
            )
        )
    db.commit()
    db.refresh(document)
    return document


def list_documents(db: Session, *, user_id: int) -> list[KnowledgeDocument]:
    statement = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.user_id == user_id)
        .order_by(KnowledgeDocument.created_at.desc(), KnowledgeDocument.id.desc())
    )
    return list(db.scalars(statement))


@dataclass
class RetrievedEvidence:
    document_id: int
    document_title: str
    chunk_id: int
    chunk_index: int
    content: str
    score: float


def retrieve_from_document(document: KnowledgeDocument, *, query: str, top_k: int = 3) -> list[str]:
    """在单个文档的分块内检索，返回最相关的分块原文。"""
    chunks = list(document.chunks)
    if not chunks:
        return []
    index = BM25Index({chunk.id: chunk.content for chunk in chunks})
    hits = index.search(query, top_k=top_k)
    if not hits:
        # 完全无词面交集时退回文档开头，保证 RAG 仍可注入背景
        return [chunks[0].content]
    chunk_by_id = {chunk.id: chunk for chunk in chunks}
    return [chunk_by_id[hit.key].content for hit in hits]


def retrieve_evidence(db: Session, query: str, top_k: int = 3, *, user_id: int) -> list[RetrievedEvidence]:
    """知识库检索：返回真实分块原文 + BM25 分数 + 来源文档（可追溯）。仅限本人文档。"""
    chunks = list(
        db.scalars(
            select(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.user_id == user_id)
        )
    )
    if not chunks:
        return []
    index = BM25Index({chunk.id: chunk.content for chunk in chunks})
    hits = index.search(query, top_k=top_k)
    if not hits:
        return []
    chunk_by_id = {chunk.id: chunk for chunk in chunks}
    evidence: list[RetrievedEvidence] = []
    for hit in hits:
        chunk = chunk_by_id[hit.key]
        evidence.append(
            RetrievedEvidence(
                document_id=chunk.document_id,
                document_title=chunk.document.title,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=hit.score,
            )
        )
    return evidence


def knowledge_stats(db: Session, *, user_id: int) -> dict:
    documents = list_documents(db, user_id=user_id)
    total_chunks = sum(len(doc.chunks) for doc in documents)
    return {"document_count": len(documents), "chunk_count": total_chunks}
