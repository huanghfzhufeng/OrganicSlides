"""Tests for the new content-quality guards and style packet injection."""

from agents.researcher.tools import _compute_relevance, _tokenize_query
from agents.researcher.tools import should_run_web_search
from agents.visual.tools import validate_render_plans
from agents.writer.tools import validate_slides_content
from agents.planner.tools import infer_min_outline_slides
from styles.recommender import StyleRecommender
from styles.context_builder import build_style_packet


def test_tokenize_query_keeps_chinese_phrases_and_ngrams():
    tokens = _tokenize_query("毕业论文答辩PPT 风格化设计")

    assert "毕业论文答辩" in tokens
    assert "答辩" in tokens
    assert "风格化设计" in tokens
    assert "ppt" in tokens


def test_relevance_prefers_longer_phrase_matches():
    query_tokens = _tokenize_query("毕业论文答辩")
    high = _compute_relevance("这份毕业论文答辩需要突出研究贡献和结果图表。", query_tokens)
    low = _compute_relevance("这是完全无关的旅游游记内容。", query_tokens)

    assert high > low
    assert high > 0


def test_build_style_packet_includes_style_metadata_and_reference_snippets(sample_style_json):
    packet = build_style_packet(
        "01-snoopy",
        sample_style_json,
        user_intent="做一份温暖叙事风格的毕业论文答辩 PPT",
    )

    assert "风格ID：01-snoopy" in packet
    assert "风格名称：" in packet
    assert "参考知识摘录：" in packet
    assert "样例图：" in packet


def test_validate_slides_content_rejects_layout_style_image_prompt():
    slides = [
        {
            "page_number": 1,
            "section_id": "section_1",
            "title": "这个问题已经迫使团队重新评估路径",
            "visual_type": "illustration",
            "path_hint": "path_b",
            "layout_intent": "cover",
            "content": {
                "main_text": None,
                "bullet_points": ["影响范围", "关键变量"],
                "supporting_text": None,
            },
            "image_prompt": "标题居中偏上，右侧放一张图，背景色浅米白",
            "text_to_render": {
                "title": "重新评估路径",
                "subtitle": None,
                "bullets": ["影响范围", "关键变量"],
            },
            "speaker_notes": "说明问题升级的原因。",
        }
    ]

    is_valid, message = validate_slides_content(slides, outline=[{"id": "section_1"}])

    assert not is_valid
    assert "image_prompt" in message


def test_style_recommender_detects_thesis_defense_intent():
    recommender = StyleRecommender()

    results = recommender.recommend_ids("做一份毕业论文答辩 PPT，突出研究方法、实验结果和结论")

    assert results
    assert results[0] in {"p6-nyt-magazine", "p2-fathom", "03-ligne-claire"}


def test_validate_render_plans_rejects_missing_required_payload():
    slides = [
        {
            "page_number": 1,
            "title": "研究结果已经证明方案更优",
            "visual_type": "chart",
            "path_hint": "path_a",
        }
    ]
    plans = [
        {
            "page_number": 1,
            "render_path": "path_a",
            "layout_name": "bullet_list",
            "html_content": "",
            "image_prompt": None,
            "style_notes": "",
            "color_system": {},
        }
    ]

    is_valid, message = validate_render_plans(plans, slides, {"render_paths": ["path_a"]})

    assert not is_valid
    assert "html_content" in message


def test_should_run_web_search_skips_network_when_local_context_is_enough():
    should_search = should_run_web_search(
        "做一份毕业论文答辩 PPT，突出研究方法和实验结果",
        documents=[{"content": "doc1"}, {"content": "doc2"}, {"content": "doc3"}],
        local_results=[{"content": "hit1"}, {"content": "hit2"}, {"content": "hit3"}],
        is_thesis_mode=True,
    )

    assert not should_search


def test_infer_min_outline_slides_requires_deeper_deck_for_complex_topic():
    min_slides = infer_min_outline_slides(
        "做一份关于 AI Agent 产品化落地复盘的汇报，重点分析问题、方案和下一步动作",
        source_docs=[],
        is_thesis_mode=False,
    )

    assert min_slides >= 8
