"""Unit tests for bilingual huashu reference retrieval."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from agents.researcher.tools import (  # noqa: E402
    _build_query_signal,
    _search_huashu_references,
    _search_uploaded_documents,
    rag_search,
)


@pytest.mark.unit
class TestReferenceRetrieval:
    def test_build_query_signal_expands_chinese_editorial_query(self):
        signal = _build_query_signal("纽约时报风格的数据报告")

        assert "纽约时报" in signal["terms"]
        assert "nyt" in signal["terms"]
        assert "report" in signal["terms"]
        assert any("数据报告" in phrase for phrase in signal["phrases"])

    @pytest.mark.asyncio
    async def test_search_huashu_references_matches_chinese_editorial_query(self):
        results = await _search_huashu_references("纽约时报风格的数据报告")

        assert results
        assert any(
            "NYT Magazine Editorial" in result["content"]
            or "纽约时报编辑风" in result["content"]
            for result in results
        )

    @pytest.mark.asyncio
    async def test_search_huashu_references_matches_english_training_query(self):
        results = await _search_huashu_references("neo brutalism training deck")

        assert results
        assert any(
            "Neo-Brutalism" in result["content"]
            or "新粗野主义" in result["content"]
            for result in results
        )

    def test_search_uploaded_documents_supports_cross_lingual_queries(self):
        documents = [
            {
                "filename": "training-notes.md",
                "content": "这是一份企业AI培训课件，强调案例拆解、演示逻辑和现场互动。",
            }
        ]

        chinese_results = _search_uploaded_documents("企业AI培训课件", documents)
        english_results = _search_uploaded_documents("ai training deck", documents)

        assert chinese_results
        assert english_results
        assert chinese_results[0]["source"] == "training-notes.md"
        assert english_results[0]["source"] == "training-notes.md"

    @pytest.mark.asyncio
    async def test_rag_search_merges_reference_and_uploaded_document_results(self):
        documents = [
            {
                "filename": "brief.md",
                "content": "我们的培训课件需要参考新粗野主义，保证远距离可读和色块对比。",
            }
        ]

        results = await rag_search("新粗野主义培训课件", documents)
        sources = {result["source"] for result in results}

        assert results
        assert "brief.md" in sources
        assert any(source.startswith("huashu-slides/references/") for source in sources)
