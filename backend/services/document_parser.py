"""
论文文档解析服务
将上传的 PDF/DOCX 文件解析为结构化的 source_docs 列表，
兼容现有 RAG 管道（researcher agent 的 _search_uploaded_documents）。

依赖: pip install pdfplumber python-docx
"""

import re
import logging
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import pdfplumber  # type: ignore[import-untyped]
except ImportError:
    pdfplumber = None  # type: ignore[assignment]

try:
    from docx import Document as DocxDocument  # type: ignore[import-untyped]
except ImportError:
    DocxDocument = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# 总字数上限（防止 LLM context 溢出）
MAX_TOTAL_CHARS = 80_000
# 单个 chunk 目标字数
TARGET_CHUNK_CHARS = 1_500


# ==================== 章节标题检测 ====================

# 中文章节标题：第X章、第一章 等
_CHAPTER_PATTERN = re.compile(
    r"^第[一二三四五六七八九十百千\d]+[章节篇]\s*.{0,50}$"
)

# 编号标题：1. / 1.1 / 1.1.1 等（允许中文或英文标题文字）
_NUMBERED_HEADING_PATTERN = re.compile(
    r"^(\d+\.)+\d*\s+\S.{0,80}$"
)

# 常见论文章节关键词（独占一行时视为标题）
_KEYWORD_HEADINGS = {
    "摘要", "abstract", "引言", "introduction", "绪论",
    "文献综述", "literature review", "研究背景", "背景",
    "研究方法", "methodology", "方法", "实验设计",
    "结果", "results", "实验结果", "结果与分析",
    "讨论", "discussion", "分析与讨论",
    "结论", "conclusion", "conclusions", "总结",
    "参考文献", "references", "bibliography",
    "致谢", "acknowledgements", "acknowledgments",
    "附录", "appendix",
}


def _is_chapter_heading(line: str) -> bool:
    """判断一行文本是否是章节标题。"""
    stripped = line.strip()
    if not stripped or len(stripped) > 100:
        return False
    if _CHAPTER_PATTERN.match(stripped):
        return True
    if _NUMBERED_HEADING_PATTERN.match(stripped):
        return True
    if stripped.lower().rstrip("：:") in _KEYWORD_HEADINGS:
        return True
    return False


# ==================== 文本切分 ====================

def _split_into_chunks(
    text: str,
    chapter_title: str,
    filename: str,
) -> list[dict]:
    """
    将一段文本（属于某个章节）按段落边界切分为多个 chunk。
    每个 chunk 前缀章节标题，格式兼容现有 source_docs。
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[dict] = []
    current_text = ""

    for para in paragraphs:
        # 如果加入当前段落后超过目标大小，先保存当前 chunk
        if current_text and len(current_text) + len(para) > TARGET_CHUNK_CHARS:
            chunks.append(_make_chunk(current_text, chapter_title, filename, len(chunks)))
            current_text = ""
        current_text = f"{current_text}\n{para}" if current_text else para

    # 保存最后一个 chunk
    if current_text:
        chunks.append(_make_chunk(current_text, chapter_title, filename, len(chunks)))

    return chunks


def _make_chunk(content: str, chapter_title: str, filename: str, index: int) -> dict:
    """构建单个 chunk 字典，兼容 source_docs 格式。"""
    prefixed_content = f"[{chapter_title}]\n{content}" if chapter_title else content
    return {
        "content": prefixed_content,
        "filename": filename,
        "source": "uploaded_thesis",
        "metadata": {
            "chapter": chapter_title,
            "chunk_index": index,
        },
    }


# ==================== PDF 提取 ====================

def _extract_pdf(file_path: Path) -> list[tuple[str, str]]:
    """从 PDF 文件提取文本，按章节切分。返回 [(chapter_title, text), ...]。"""
    if pdfplumber is None:
        raise RuntimeError(
            "PDF 解析需要 pdfplumber，请运行: pip install pdfplumber"
            "（Docker 用户请运行: docker-compose up --build）"
        )

    sections: list[tuple[str, str]] = []
    current_title = "正文"
    current_text = ""

    with pdfplumber.open(str(file_path)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            for line in page_text.split("\n"):
                if _is_chapter_heading(line):
                    if current_text.strip():
                        sections.append((current_title, current_text))
                    current_title = line.strip()
                    current_text = ""
                else:
                    current_text += line + "\n"

    if current_text.strip():
        sections.append((current_title, current_text))

    return sections


def _extract_docx(file_path: Path) -> list[tuple[str, str]]:
    """
    从 Word 文件提取文本。返回 [(chapter_title, text), ...]。

    优先使用 python-docx（可识别 Heading 样式），
    若失败（如 WPS/Google Docs 导出的非标准 DOCX）则回退到直接解析 XML。
    """
    try:
        return _extract_docx_with_library(file_path)
    except Exception as e:
        logger.warning(
            "python-docx failed for %s (%s), falling back to raw XML parsing",
            file_path.name, e,
        )
        return _extract_docx_raw(file_path)


def _extract_docx_with_library(file_path: Path) -> list[tuple[str, str]]:
    """使用 python-docx 提取，可识别 Heading 样式。"""
    if DocxDocument is None:
        raise RuntimeError(
            "DOCX 解析需要 python-docx，请运行: pip install python-docx"
            "（Docker 用户请运行: docker-compose up --build）"
        )

    doc = DocxDocument(str(file_path))
    sections: list[tuple[str, str]] = []
    current_title = "正文"
    current_text = ""

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        is_heading = (
            para.style
            and para.style.name
            and para.style.name.startswith("Heading")
        )

        if is_heading or _is_chapter_heading(text):
            if current_text.strip():
                sections.append((current_title, current_text))
            current_title = text
            current_text = ""
        else:
            current_text += text + "\n"

    if current_text.strip():
        sections.append((current_title, current_text))

    return sections


# Word XML namespace
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _extract_docx_raw(file_path: Path) -> list[tuple[str, str]]:
    """
    直接从 DOCX ZIP 中解析 word/document.xml 提取文本。
    不依赖 python-docx，兼容非标准 DOCX 文件。
    """
    with zipfile.ZipFile(str(file_path), "r") as zf:
        if "word/document.xml" not in zf.namelist():
            raise ValueError("DOCX 文件结构损坏：找不到 word/document.xml")

        xml_content = zf.read("word/document.xml")

    root = ET.fromstring(xml_content)

    # 收集 heading 样式 ID（从 styles.xml，如果可读）
    heading_style_ids: set[str] = set()
    try:
        with zipfile.ZipFile(str(file_path), "r") as zf:
            if "word/styles.xml" in zf.namelist():
                styles_xml = zf.read("word/styles.xml")
                styles_root = ET.fromstring(styles_xml)
                for style_el in styles_root.iter(f"{{{_WORD_NS}}}style"):
                    style_id = style_el.get(f"{{{_WORD_NS}}}styleId", "")
                    name_el = style_el.find(f"{{{_WORD_NS}}}name")
                    name_val = name_el.get(f"{{{_WORD_NS}}}val", "") if name_el is not None else ""
                    if name_val.lower().startswith("heading"):
                        heading_style_ids.add(style_id)
    except Exception:
        pass  # styles.xml 不可读时仍可通过正则检测章节

    sections: list[tuple[str, str]] = []
    current_title = "正文"
    current_text = ""

    for para_el in root.iter(f"{{{_WORD_NS}}}p"):
        # 提取段落全部文本
        runs_text = "".join(
            t.text for t in para_el.iter(f"{{{_WORD_NS}}}t") if t.text
        )
        text = runs_text.strip()
        if not text:
            continue

        # 检查段落样式是否为 heading
        is_heading = False
        ppr = para_el.find(f"{{{_WORD_NS}}}pPr")
        if ppr is not None:
            pstyle = ppr.find(f"{{{_WORD_NS}}}pStyle")
            if pstyle is not None:
                style_val = pstyle.get(f"{{{_WORD_NS}}}val", "")
                if style_val in heading_style_ids:
                    is_heading = True

        if is_heading or _is_chapter_heading(text):
            if current_text.strip():
                sections.append((current_title, current_text))
            current_title = text
            current_text = ""
        else:
            current_text += text + "\n"

    if current_text.strip():
        sections.append((current_title, current_text))

    return sections


# ==================== 公共接口 ====================

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def parse_document(file_path: str, filename: str) -> list[dict]:
    """
    解析上传的论文文件，返回 source_docs 列表。

    Args:
        file_path: 服务器上保存的文件路径
        filename: 原始文件名

    Returns:
        兼容 source_docs 格式的 chunk 列表:
        [{content, filename, source, metadata}, ...]

    Raises:
        ValueError: 文件类型不支持
        RuntimeError: 解析依赖缺失
        Exception: 文件读取或解析失败
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型: {suffix}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}")

    # 提取章节
    if suffix == ".pdf":
        sections = _extract_pdf(path)
    else:
        sections = _extract_docx(path)

    if not sections:
        raise ValueError("文件内容为空或无法解析")

    # 切分为 chunks
    all_chunks: list[dict] = []
    total_chars = 0

    for chapter_title, chapter_text in sections:
        chunks = _split_into_chunks(chapter_text, chapter_title, filename)
        for chunk in chunks:
            chunk_len = len(chunk["content"])
            if total_chars + chunk_len > MAX_TOTAL_CHARS:
                logger.warning(
                    "Document %s truncated at %d chars (limit %d)",
                    filename, total_chars, MAX_TOTAL_CHARS,
                )
                return all_chunks
            all_chunks.append(chunk)
            total_chars += chunk_len

    logger.info(
        "Parsed document %s: %d sections, %d chunks, %d chars",
        filename, len(sections), len(all_chunks), total_chars,
    )
    return all_chunks


def get_chapter_summary(source_docs: list[dict]) -> list[str]:
    """从 source_docs 提取章节标题列表（去重保序），用于前端展示。"""
    seen: set[str] = set()
    chapters: list[str] = []
    for doc in source_docs:
        chapter = doc.get("metadata", {}).get("chapter", "")
        if chapter and chapter not in seen:
            seen.add(chapter)
            chapters.append(chapter)
    return chapters
