"""
渲染引擎 Agent (Renderer) 提示词
注：Renderer 主要执行 python-pptx 操作，较少使用 LLM
"""

RENDERER_STATUS_MESSAGES = {
    "start": "渲染引擎启动，开始生成演示文稿...",
    "applying_theme": "正在应用主题样式...",
    "creating_slides": "正在创建幻灯片...",
    "adding_content": "正在添加内容...",
    "saving": "正在保存文件...",
    "complete": "演示文稿生成完成！",
    "error": "渲染过程中出现错误"
}

# 布局描述（用于调试和日志）
LAYOUT_DESCRIPTIONS = {
    0: "标题幻灯片 (Title Slide)",
    1: "标题和内容 (Title and Content)",
    2: "章节标题 (Section Header)",
    3: "两栏内容 (Two Content)",
    4: "对比 (Comparison)",
    5: "仅标题 (Title Only)",
    6: "空白 (Blank)",
    7: "带说明的内容 (Content with Caption)",
    8: "带说明的图片 (Picture with Caption)",
}
