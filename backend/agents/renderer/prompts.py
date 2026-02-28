"""
渲染引擎 Agent (Renderer) 提示词和状态消息
支持双渲染路径：Path A (HTML→PPTX) 和 Path B (AI图片→PPTX)
"""

RENDERER_STATUS_MESSAGES = {
    "start": "渲染引擎启动，开始生成演示文稿...",
    "detecting_path": "检测渲染路径...",
    "path_a_html": "正在生成 HTML 幻灯片（Path A）...",
    "path_a_convert": "正在将 HTML 转换为 PPTX（html2pptx）...",
    "path_b_generate": "正在 AI 生成幻灯片图片（Path B）...",
    "path_b_assemble": "正在将图片组装为 PPTX...",
    "mixed_assembling": "正在合并 Path A 和 Path B 内容...",
    "applying_theme": "正在应用主题样式...",
    "saving": "正在保存文件...",
    "complete": "演示文稿生成完成！",
    "error": "渲染过程中出现错误",
    "partial_error": "部分幻灯片渲染失败，已跳过继续生成",
}

# Path A: html2pptx layout names
PATH_A_LAYOUT_DESCRIPTIONS = {
    "title_slide": "标题幻灯片 (Title Slide)",
    "bullet_list": "标题和内容 (Title and Content)",
    "section_header": "章节标题 (Section Header)",
    "two_content": "两栏内容 (Two Content)",
    "comparison": "对比 (Comparison)",
    "title_only": "仅标题 (Title Only)",
    "blank": "空白 (Blank)",
    "content_with_caption": "带说明的内容 (Content with Caption)",
    "picture_with_caption": "带说明的图片 (Picture with Caption)",
}

# Fallback: python-pptx layout IDs (used if html2pptx is unavailable)
PPTX_LAYOUT_IDS = {
    "title_slide": 0,
    "bullet_list": 1,
    "section_header": 2,
    "two_content": 3,
    "comparison": 4,
    "title_only": 5,
    "blank": 6,
    "content_with_caption": 7,
    "picture_with_caption": 8,
}
