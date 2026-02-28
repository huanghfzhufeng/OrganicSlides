# Agent Prompt Redesign: huashu-slides Knowledge Integration

> Research date: 2026-03-01
> Scope: All 5 agents (Researcher, Planner, Writer, Visual, Renderer)
> Goal: Integrate huashu-slides design philosophy and dual rendering paths into all agent prompts

---

## Executive Summary

The current OrganicSlides agent system produces structurally correct but visually generic presentations. The huashu-slides knowledge base contains battle-tested principles for creating visually compelling slides across 18+ proven styles with dual rendering paths. This document specifies exact prompt and schema changes for each agent.

**Core philosophy shift:** From "generate content + apply template" to "design decisions flow through agents." The Visual agent becomes a true decision-maker selecting rendering path, style system, and per-slide visual strategy.

---

## Global State Schema Changes

The `PresentationState` TypedDict in `backend/state.py` must be extended before any agent changes take effect.

### New Fields Required in `PresentationState`

```python
class PresentationState(TypedDict, total=False):
    # === EXISTING FIELDS (unchanged) ===
    session_id: str
    user_intent: str
    source_docs: List[dict]
    search_results: List[dict]
    outline: List[dict]
    outline_approved: bool
    slides_data: List[dict]
    theme_config: dict
    generated_assets: List[dict]
    pptx_path: str
    current_status: str
    current_agent: str
    error: Optional[str]
    messages: List[dict]

    # === NEW FIELDS ===
    # Style system (set by user selection, carried throughout)
    style_id: str           # e.g. "snoopy", "neo-brutalism", "nyt-editorial"
    style_config: dict      # Full style config from styles JSON (colors, typography, etc.)
    render_path: str        # "path_a" | "path_b" | "mixed"

    # Per-slide rendering decisions (set by Visual agent)
    slide_render_plans: List[dict]  # Visual agent's output: one plan per slide

    # Generated slide files (set by Renderer)
    slide_files: List[dict]  # {"slide_num": 1, "path": "...", "type": "html"|"image"}
```

### `OutlineSection` dataclass changes

```python
@dataclass
class OutlineSection:
    id: str
    title: str                    # MUST be assertion sentence, not topic word
    slide_type: str = "content"
    visual_type: str = "illustration"  # NEW: illustration|chart|flow|quote|data
    key_points: List[str] = field(default_factory=list)  # MAX 4 items
    notes: str = ""
```

### `SlideModel` dataclass changes

```python
@dataclass
class SlideModel:
    page_number: int
    layout_intent: str
    title: str
    speaker_notes: str = ""
    elements: List[SlideElement] = field(default_factory=list)
    # NEW FIELDS:
    visual_type: str = "illustration"    # from outline
    image_prompt: Optional[str] = None  # Path B full image prompt
    path_hint: str = "path_a"           # path_a | path_b | auto
    html_content: Optional[str] = None  # Path A rendered HTML
```

---

## Agent 1: Researcher

### Current State

- `web_search()` is mocked with fake data (hardcoded example.com URLs)
- `rag_search()` returns dummy chunk content
- No knowledge base integration
- Generates generic search keywords with no style awareness

### Problem

The researcher produces fake data that creates a false sense of research-backed content. When agents downstream use this "research," they generate hallucinated facts. This undermines trust and quality.

### Redesign Goals

1. Replace mock `web_search` with real DuckDuckGo search (no API key required)
2. Add `huashu-slides/references/` as a local knowledge base for style and design queries
3. Generate smarter, presentation-focused search queries
4. Return structured, honest results (including empty results when nothing found)

### New `tools.py` Implementation Plan

```python
# web_search: Replace mock with real DuckDuckGo search
# Use: duckduckgo-search Python package (pip install duckduckgo-search)

async def web_search(query: str) -> List[Dict[str, Any]]:
    """
    Real web search using DuckDuckGo (no API key required).
    Falls back to empty list on failure — never returns fake data.
    """
    from duckduckgo_search import DDGS
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")[:300],
                "domain": _extract_domain(r.get("href", "")),
                "relevance_score": None  # DuckDuckGo doesn't provide scores
            }
            for r in results
        ]
    except Exception as e:
        # Log error, return empty — never fake data
        logger.warning(f"web_search failed: {e}")
        return []


# rag_search: Search huashu-slides/references/ as knowledge base
async def rag_search(query: str, documents: List[Dict] = None) -> List[Dict[str, Any]]:
    """
    Search local huashu-slides knowledge base + uploaded user documents.
    Uses simple keyword matching (no vector DB required for Phase 1).
    """
    results = []

    # 1. Search huashu-slides reference files
    reference_files = [
        "huashu-slides/references/design-principles.md",
        "huashu-slides/references/proven-styles-gallery.md",
        "huashu-slides/references/prompt-templates.md",
        "huashu-slides/references/design-movements.md",
    ]
    for filepath in reference_files:
        chunks = _search_file(filepath, query)
        results.extend(chunks)

    # 2. Search user-uploaded documents
    if documents:
        for doc in documents:
            chunks = _search_document(doc, query)
            results.extend(chunks)

    # Sort by relevance, return top 5
    return sorted(results, key=lambda x: x["relevance_score"], reverse=True)[:5]
```

### New `prompts.py` Schema

```python
SEARCH_QUERY_TEMPLATE = """根据以下演示需求，生成 3-5 个搜索关键词。

演示需求：{user_intent}

要求：
- 关键词要精确，聚焦于主题的核心概念
- 包含数据/统计类关键词（用于找数据支撑）
- 包含行业/场景类关键词（用于找案例）
- 不要生成明显无法搜索到结果的关键词

输出格式（JSON 数组）：
["关键词1", "关键词2", "关键词3"]
"""
```

### Input/Output Schema

**Input (from state):**
```json
{
  "user_intent": "string",
  "source_docs": "List[dict]  (user-uploaded documents)"
}
```

**Output (to state):**
```json
{
  "source_docs": "List[dict]  (rag results appended to uploaded docs)",
  "search_results": [
    {
      "title": "string",
      "url": "string (real URL or empty string)",
      "snippet": "string (max 300 chars)",
      "domain": "string",
      "relevance_score": "float or null"
    }
  ],
  "current_status": "research_complete"
}
```

---

## Agent 2: Planner

### Current State

- Generates topic-word titles (e.g., "Q3销售", "方法论") — violates assertion-evidence principle
- No `visual_type` per slide
- No connection to style selection
- Allows up to 5 bullet points (should be max 4)
- `type` field uses vague categories (content|data|comparison) with no visual guidance

### Problem

Topic-word titles force viewers to read the body text to understand the slide's message. Assertion sentences allow distracted viewers to grasp the point from the title alone (evidence from Penn State research: better comprehension, fewer misconceptions, lower cognitive load).

### Redesign Goals

1. Enforce assertion-evidence titles (complete sentences that state the conclusion)
2. Add `visual_type` field per slide (illustration|chart|flow|quote|data)
3. Limit `key_points` to max 4 per slide
4. Carry forward `style_config` context so planner knows the visual system
5. Add `path_hint` recommendation per slide based on content type

### New `prompts.py`

```python
PLANNER_SYSTEM_PROMPT = """你是一位专业的演示文稿策划师。你深知：**幻灯片标题是断言句，不是主题词。**

## 核心原则

### 1. 断言-证据框架（Assertion-Evidence Framework）
标题必须是完整的断言句，陈述核心结论：

| ❌ 错误（主题词） | ✅ 正确（断言句） |
|----------------|----------------|
| Q3销售 | Q3销售额增长23%，新用户是主要驱动力 |
| 方法论 | 我们用双盲实验验证了这个假设 |
| 关键发现 | 10000个用户会话中浮现出三种模式 |

标题应该是「这页最重要的一句话」。

### 2. 信息密度控制
- 每页最多 4 个要点（不是 5 个）
- 每个要点控制在 12 字以内
- 一页只传达一个核心信息

### 3. 视觉类型分配
根据内容性质为每页选择视觉类型：
- `illustration`：人物场景、概念比喻、故事叙述（最适合漫画/插画风格）
- `chart`：数据趋势、百分比、数量对比（用折线图/柱状图表达）
- `flow`：流程步骤、因果关系、决策树（用箭头/步骤图表达）
- `quote`：引用/金句/数据亮点（大字体居中，简洁有力）
- `data`：多维数据表格、矩阵对比（适合信息密集的对比页）
- `cover`：封面和过渡页

## 输出格式（JSON）

```json
{
  "outline": [
    {
      "id": "section_1",
      "title": "断言句标题——说明这页最重要的结论",
      "slide_type": "cover|content|data|comparison|quote|chart|conclusion",
      "visual_type": "illustration|chart|flow|quote|data|cover",
      "key_points": ["要点1（≤12字）", "要点2（≤12字）"],
      "path_hint": "path_a|path_b|auto",
      "notes": "演讲者备注——扩展讲解这页的内容"
    }
  ],
  "total_slides": 8,
  "estimated_duration": "15分钟",
  "target_audience": "目标受众描述",
  "recommended_structure": "开头：问题/钩子 → 主体：逻辑论证 → 结尾：行动号召"
}
```

`path_hint` 选择规则：
- `path_b`：封面、引言页、情感驱动页、漫画/插画风格页
- `path_a`：数据表格、代码、精确排版、文字密集页
- `auto`：由 Visual Agent 根据内容最终决定
"""

PLANNER_USER_TEMPLATE = """请为以下演示需求设计大纲：

<用户需求>
{user_intent}
</用户需求>

<风格配置>
{style_context}
</风格配置>

<研究素材>
{research_context}
</research_context>

要求：
1. 每页标题必须是断言句（完整陈述结论），不能是主题词
2. 每页最多 4 个要点
3. 根据内容性质分配 visual_type
4. 封面和情感页优先考虑 path_b（全AI视觉）
5. 数据和文字密集页优先考虑 path_a（HTML渲染）

请输出 JSON 格式的大纲结构。"""
```

### Input/Output Schema

**Input (from state):**
```json
{
  "user_intent": "string",
  "style_id": "string (e.g. 'snoopy')",
  "style_config": "dict (colors, typography, render_path preference)",
  "search_results": "List[dict]",
  "source_docs": "List[dict]"
}
```

**Output (to state):**
```json
{
  "outline": [
    {
      "id": "section_1",
      "title": "断言句标题（必须是完整句子）",
      "slide_type": "cover|content|data|comparison|quote|chart|conclusion",
      "visual_type": "illustration|chart|flow|quote|data|cover",
      "key_points": ["最多4条要点"],
      "path_hint": "path_a|path_b|auto",
      "notes": "演讲者备注"
    }
  ],
  "total_slides": 8,
  "estimated_duration": "15分钟",
  "target_audience": "目标受众描述",
  "recommended_structure": "结构说明"
}
```

---

## Agent 3: Writer

### Current State

- `visual_needs` is a vague object with `needs_image: bool` — no prompt generated
- `layout_intent` doesn't map to dual rendering paths
- No `image_prompt` for Path B slides
- No `path_hint` propagation
- Bullet points allow up to 15 characters (should be tighter)

### Problem

The Writer generates content but cannot communicate to downstream agents *how* a slide should be rendered. The Visual agent receives content but has no signal about rendering strategy. Image prompts for Path B don't exist at all.

### Redesign Goals

1. Add `image_prompt` field: Writer drafts the Path B image prompt using prompt-templates.md patterns
2. Add `path_hint` field: carry forward from Planner's outline
3. Add `visual_type` field: carry forward from outline
4. Enforce max 4 bullet points
5. Use assertion sentences in slide titles (validate/refine from outline)

### New `prompts.py`

```python
WRITER_SYSTEM_PROMPT = """你是一位专业的演示文稿撰稿人，同时负责为每张幻灯片起草视觉描述。

## 核心原则

### 标题继承原则
保留策划阶段的断言句标题。如果标题是主题词，补充改写为断言句。

### 要点密度原则
- 每页最多 4 条要点
- 每条要点控制在 12 字以内
- 宁可少，不要多

### 视觉描述原则（image_prompt）
对于 path_hint 为 "path_b" 或 visual_type 为 "illustration" 的页面，生成 image_prompt：

**好的 image_prompt（描述情绪和场景）：**
```
角色在阳光照耀的草地上若有所思地看着远处，身旁是一只趴着的小狗，
画面传达出「有些问题需要慢下来才能看清楚」的哲学感。
```

**坏的 image_prompt（CSS式布局指令）：**
```
标题居中偏上，字体36pt，右侧放一张图，左侧三列bullet points，
背景色#FFF8E8
```

image_prompt 描述**情绪和视觉场景**，不描述**布局位置和字号**。
实际文字内容通过 `text_to_render` 字段指定。

## 输出格式（JSON 数组）

```json
[
  {
    "page_number": 1,
    "section_id": "section_1",
    "title": "断言句标题",
    "visual_type": "illustration|chart|flow|quote|data|cover",
    "path_hint": "path_a|path_b|auto",
    "layout_intent": "cover|bullet_points|two_column|data_driven|quote|conclusion",
    "content": {
      "main_text": "主要内容文本（如适用）",
      "bullet_points": ["要点1", "要点2", "要点3"],
      "supporting_text": "补充说明"
    },
    "image_prompt": "视觉场景描述（path_b或illustration页面必填，其余可为null）",
    "text_to_render": {
      "title": "标题文字（必须精确渲染）",
      "subtitle": "副标题（如有）",
      "bullets": ["要点1", "要点2"]
    },
    "speaker_notes": "演讲者备注：这页主要讲解..."
  }
]
```

`image_prompt` 写作要求：
- 描述情绪氛围，不描述布局
- 包含「这页让观众感受到什么」
- 避免方位词（左/右/上/下/居中）
- 避免字号数字（36pt/120px）
- 用感官语言和比喻
"""

WRITER_USER_TEMPLATE = """请根据以下大纲，为每个章节撰写幻灯片内容：

<演示主题>
{user_intent}
</演示主题>

<风格系统>
{style_context}
</风格系统>

<大纲结构>
{outline_text}
</大纲结构>

<研究素材>
{research_context}
</research_context>

要求：
1. 保留大纲中的断言句标题
2. 每页最多 4 条要点，每条 ≤12 字
3. 对 visual_type=illustration 或 path_hint=path_b 的页面，生成 image_prompt
4. image_prompt 描述情绪和场景，不描述布局位置
5. text_to_render 中的文字要精确（AI 会逐字渲染）

请为每个章节生成详细的幻灯片内容，输出 JSON 数组格式。"""
```

### Input/Output Schema

**Input (from state):**
```json
{
  "user_intent": "string",
  "outline": "List[dict]  (with visual_type and path_hint per slide)",
  "style_id": "string",
  "style_config": "dict",
  "search_results": "List[dict]",
  "source_docs": "List[dict]"
}
```

**Output (to state):**
```json
{
  "slides_data": [
    {
      "page_number": 1,
      "section_id": "section_1",
      "title": "断言句标题",
      "visual_type": "illustration|chart|flow|quote|data|cover",
      "path_hint": "path_a|path_b|auto",
      "layout_intent": "cover|bullet_points|two_column|data_driven|quote|conclusion",
      "content": {
        "main_text": "string or null",
        "bullet_points": ["max 4 items"],
        "supporting_text": "string or null"
      },
      "image_prompt": "string or null",
      "text_to_render": {
        "title": "string",
        "subtitle": "string or null",
        "bullets": ["array"]
      },
      "speaker_notes": "string"
    }
  ]
}
```

---

## Agent 4: Visual (Major Redesign)

### Current State

- Acts as a passive "layout picker" — no design philosophy
- Outputs `layout_id` integers from PowerPoint's default layouts (0-8)
- No connection to style system (style_config not used)
- No awareness of rendering paths
- `animation_suggestion` field has no implementation
- Cannot produce HTML templates or image prompts

### Problem

The Visual agent is the critical design decision-maker but currently just maps content length to PowerPoint layout numbers. It has no understanding of the huashu-slides style system, the dual rendering paths, or the visual principles that make presentations compelling.

### Redesign: Visual as "Design Decision Maker"

The Visual agent must:
1. **Decide final render_path per slide** (based on style, content, and path_hint)
2. **For Path A slides**: produce a complete HTML template following html2pptx constraints
3. **For Path B slides**: refine the `image_prompt` from Writer using full Path B template structure
4. **Apply style_config** to every design decision (colors, typography, composition rules)

### New `prompts.py`

```python
VISUAL_SYSTEM_PROMPT = """你是演示文稿视觉总监，同时是渲染路径决策者。

## 你的职责

1. **渲染路径决策**：为每张幻灯片决定最终渲染路径（path_a 或 path_b）
2. **Path A slides**：生成完整的 HTML（遵循 html2pptx 4条硬性约束）
3. **Path B slides**：根据风格系统完善 image_prompt，写成完整的 Path B 提示词

## 渲染路径选择规则

选择 path_b（全AI视觉）当：
- visual_type = "illustration" 且风格支持 Path B（漫画/插画类）
- 封面页（cover）且风格为 Snoopy、Manga、Ligne Claire、Neo-Pop 等
- path_hint = "path_b"

选择 path_a（HTML→PPTX）当：
- visual_type = "chart"、"data"、"flow"（需要精确排版）
- 风格为 Neo-Brutalism、NYT Editorial、Pentagram 等 Path A 专用风格
- path_hint = "path_a"
- 内容含大量中文文字（AI图片生成中文错误率高）

## Path A HTML 硬性约束（必须遵守）

生成 HTML 时，以下 4 条规则违反会导致 html2pptx 报错：

1. **DIV 里不能直接写文字** — 必须用 `<p>` 或 `<h1>`-`<h6>` 包裹
2. **不支持 CSS 渐变** — 只能用纯色（linear-gradient 会报错）
3. **背景/边框只能在 DIV 上** — `<p>` 不能有 background 或 border
4. **DIV 不能用 background-image** — 改用 `<img>` 标签

body 尺寸固定：`width: 720pt; height: 405pt`

## Path B Image Prompt 结构

Path B 提示词结构（不是 CSS 布局，是视觉叙事）：

```
Create a slide that feels like [visual reference — specific publication/brand].

[Base Style from style_config]

DESIGN INTENT: [What should the viewer FEEL?]

TEXT TO RENDER (must be perfectly legible):
- [Role]: "[exact text]" — rendered as [design instruction]

VISUAL NARRATIVE: [Describe what to SEE using metaphors, not layout positions]
```

## 输出格式（JSON 数组）

```json
[
  {
    "page_number": 1,
    "render_path": "path_a|path_b",
    "layout_name": "title_slide|bullet_list|two_content|comparison|picture_with_caption|blank",
    "html_content": "完整 HTML 字符串（path_a 时必填，path_b 时为 null）",
    "image_prompt": "完整 Path B 提示词（path_b 时必填，path_a 时为 null）",
    "style_notes": "设计决策说明，方便调试",
    "color_system": {
      "background": "#hex",
      "text": "#hex",
      "accent": "#hex"
    }
  }
]
```
"""

VISUAL_USER_TEMPLATE = """请为以下幻灯片确定视觉设计方案：

<风格系统>
{style_config_json}
</风格系统>

<幻灯片内容>
{slides_summary}
</幻灯片内容>

<base_style_prompt>
{base_style_prompt}
</base_style_prompt>

要求：
1. 为每张幻灯片决定最终 render_path（path_a 或 path_b）
2. Path A 页面：生成完整 HTML，严格遵守 html2pptx 4 条约束
3. Path B 页面：生成完整 image_prompt，使用 DESIGN INTENT + TEXT TO RENDER + VISUAL NARRATIVE 结构
4. 应用风格系统的色彩（使用 style_config 中的具体 hex 值）
5. 标题必须保持断言句形式（不得简化为主题词）

请为每张幻灯片输出 JSON 数组。"""
```

### Input/Output Schema

**Input (from state):**
```json
{
  "slides_data": "List[dict]  (from Writer, with image_prompt and path_hint per slide)",
  "style_id": "string",
  "style_config": {
    "id": "snoopy",
    "name_en": "Warm Comic Strip",
    "render_paths": ["path_b"],
    "base_style_prompt": "VISUAL REFERENCE: Charles Schulz Peanuts...",
    "colors": {
      "background": "#FFF8E8",
      "text": "#333333",
      "accent": "#87CEEB"
    },
    "typography": {
      "heading_font": "system-ui",
      "body_font": "system-ui",
      "heading_size": "36pt"
    }
  }
}
```

**Output (to state):**
```json
{
  "slide_render_plans": [
    {
      "page_number": 1,
      "render_path": "path_a|path_b",
      "layout_name": "string",
      "html_content": "<!DOCTYPE html>...</html> or null",
      "image_prompt": "Full Path B prompt string or null",
      "style_notes": "string",
      "color_system": {
        "background": "#hex",
        "text": "#hex",
        "accent": "#hex"
      }
    }
  ],
  "render_path": "path_a|path_b|mixed"
}
```

---

## Agent 5: Renderer (Major Redesign)

### Current State

- Only implements python-pptx text placement (Path A, simplified)
- No Path B (image-based slides) support
- No html2pptx integration
- No parallel image generation
- Cannot handle mixed path presentations

### Redesign Goals

1. Support Path A: call `html2pptx.js` to convert HTML slides to PPTX
2. Support Path B: call `generate_image.py` to generate slide images, then `create_slides.py` to assemble
3. Support Mixed: handle presentations with both path_a and path_b slides
4. Parallel image generation for Path B (batch 3-5 at a time)
5. Use `slide_render_plans` from Visual agent, not raw `slides_data`

### New `prompts.py` — Status Messages

```python
RENDERER_STATUS_MESSAGES = {
    "start": "渲染引擎启动，开始生成演示文稿...",
    "detecting_path": "检测渲染路径...",
    "generating_html": "正在生成 HTML 幻灯片（Path A）...",
    "html_to_pptx": "正在将 HTML 转换为 PPTX...",
    "generating_images": "正在 AI 生成幻灯片图片（Path B）...",
    "assembling_slides": "正在组装 PPTX 文件...",
    "applying_theme": "正在应用主题样式...",
    "saving": "正在保存文件...",
    "complete": "演示文稿生成完成！",
    "error": "渲染过程中出现错误",
    "partial_error": "部分幻灯片渲染失败，已跳过"
}
```

### New `agent.py` Logic

```python
async def run(state: dict) -> dict[str, Any]:
    """
    Renderer Agent — supports dual rendering paths.

    Path A: HTML files → html2pptx.js → PPTX
    Path B: image_prompt → generate_image.py (parallel) → create_slides.py → PPTX
    Mixed: Generate both, combine into one PPTX with ordering
    """
    slide_render_plans = state.get("slide_render_plans", [])
    style_config = state.get("style_config", {})
    session_id = state.get("session_id", uuid.uuid4().hex)
    scripts_dir = _find_scripts_dir()  # Glob for huashu-slides/scripts/

    # Separate by render path
    path_a_slides = [s for s in slide_render_plans if s["render_path"] == "path_a"]
    path_b_slides = [s for s in slide_render_plans if s["render_path"] == "path_b"]

    slide_files = []

    # Path A: Write HTML files, run html2pptx
    if path_a_slides:
        html_files = await _generate_html_files(path_a_slides, session_id)
        slide_files.extend(html_files)

    # Path B: Generate images in parallel (batches of 3-5)
    if path_b_slides:
        style_sample = style_config.get("sample_image_path")
        image_files = await _generate_slide_images(
            path_b_slides, session_id, scripts_dir, style_sample
        )
        slide_files.extend(image_files)

    # Sort by page_number, assemble PPTX
    slide_files.sort(key=lambda x: x["page_number"])
    filepath = await _assemble_pptx(slide_files, session_id, scripts_dir)

    return {
        "pptx_path": filepath,
        "slide_files": slide_files,
        "current_status": "render_complete",
        "current_agent": "renderer",
    }


async def _generate_slide_images(slides, session_id, scripts_dir, style_sample):
    """Generate Path B images in parallel batches of 3-5."""
    BATCH_SIZE = 4
    results = []
    for i in range(0, len(slides), BATCH_SIZE):
        batch = slides[i:i+BATCH_SIZE]
        tasks = [
            _generate_single_image(slide, session_id, scripts_dir, style_sample)
            for slide in batch
        ]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)
    return results
```

### Input/Output Schema

**Input (from state):**
```json
{
  "slide_render_plans": [
    {
      "page_number": 1,
      "render_path": "path_a|path_b",
      "html_content": "string or null",
      "image_prompt": "string or null"
    }
  ],
  "style_config": "dict (includes sample_image_path for Path B reference image)",
  "session_id": "string"
}
```

**Output (to state):**
```json
{
  "pptx_path": "/path/to/output.pptx",
  "slide_files": [
    {
      "page_number": 1,
      "path": "/tmp/session_id/slide-01.html",
      "type": "html"
    },
    {
      "page_number": 2,
      "path": "/tmp/session_id/slide-02.png",
      "type": "image"
    }
  ],
  "current_status": "render_complete"
}
```

---

## Data Flow Diagram

```
User Input
    │
    ▼
Researcher
    │  source_docs (real search results + huashu knowledge base)
    │  search_results (real DuckDuckGo results)
    ▼
Planner                    ← receives: user_intent, style_id, style_config, research results
    │  outline[]:
    │    - title (assertion sentence)
    │    - visual_type (illustration|chart|flow|quote|data)
    │    - path_hint (path_a|path_b|auto)
    │    - key_points (max 4)
    ▼
[HITL: User approves outline]
    │
    ▼
Writer                     ← receives: outline, style_config, research results
    │  slides_data[]:
    │    - title (assertion sentence, validated)
    │    - visual_type, path_hint (carried from outline)
    │    - content.bullet_points (max 4)
    │    - image_prompt (drafted for Path B slides)
    │    - text_to_render (exact text for AI rendering)
    ▼
Visual                     ← receives: slides_data, style_config (full), base_style_prompt
    │  slide_render_plans[]:
    │    - render_path (FINAL decision: path_a | path_b)
    │    - html_content (complete HTML for path_a slides)
    │    - image_prompt (complete Path B prompt for path_b slides)
    │    - color_system (exact hex values from style_config)
    │  render_path (overall: path_a | path_b | mixed)
    ▼
Renderer                   ← receives: slide_render_plans, style_config, session_id
    │  Path A: write HTML → run html2pptx.js
    │  Path B: run generate_image.py (parallel) → run create_slides.py
    │  Mixed: both paths → combine ordered by page_number
    │  slide_files[] (intermediate file paths)
    │  pptx_path (final PPTX)
    ▼
Output: .pptx file
```

---

## Style Config Schema

The `style_config` that flows through the pipeline should conform to this schema (produced by the style system, set at session start):

```json
{
  "id": "neo-brutalism",
  "name_zh": "Neo-Brutalism 新粗野主义",
  "name_en": "Neo-Brutalism",
  "tier": 2,
  "render_paths": ["path_a"],
  "colors": {
    "primary": "#FF3B4F",
    "secondary": "#FFD700",
    "background": "#F5E6D3",
    "text": "#1A1A1A",
    "accent": "#FF3B4F"
  },
  "typography": {
    "heading_font": "Helvetica Neue Bold, Arial Black, sans-serif",
    "body_font": "system-ui, sans-serif",
    "heading_size": "3-6vw",
    "body_size": "14pt"
  },
  "use_cases": ["企业内训", "线下分享", "信息密集报告"],
  "sample_image_path": "backend/static/styles/samples/style-18-neo-brutalism.png",
  "base_style_prompt": null,
  "path_a_css_signature": "border: 4-6px solid #1A1A1A; box-shadow: 8px 8px 0 #1A1A1A;"
}
```

For Path B styles (e.g., Snoopy), `base_style_prompt` is a non-null string and `render_paths` includes `"path_b"`.

---

## Implementation Priority

### Phase 2.1 (Task #7): Refactor agent prompts

Implement in this order:
1. **Planner** — assertion-evidence titles + visual_type + path_hint (lowest risk, highest impact)
2. **Writer** — image_prompt + text_to_render + path_hint propagation
3. **Visual** — redesign as decision-maker (Path A HTML generation + Path B prompt refinement)
4. **Researcher** — replace mock with DuckDuckGo (can be done independently)
5. **Renderer** — dual path support (depends on Visual output schema being stable)

### State Changes Needed First

Before refactoring prompts, update `backend/state.py`:
- Add `style_id`, `style_config`, `render_path` to `PresentationState`
- Add `slide_render_plans`, `slide_files` to `PresentationState`
- Add `visual_type`, `path_hint`, `image_prompt`, `text_to_render` to `SlideModel`

### Dependencies

- Task #7 (prompt refactor) is blocked by Task #4 (this document) ✓
- Task #8 (rendering pipeline) is blocked by Task #2 (style API, which defines style_config schema)
- Task #9 (LangGraph flow) is blocked by Task #7 (new agent output schemas)

---

## Key Insights from huashu-slides Research

### What makes Path B prompts work

1. **Describe experience, not layout.** "标题居中偏上" → generates boring layouts. "像WIRED杂志的开篇大图" → generates compelling visuals.
2. **Visual Reference + Design Intent + Visual Narrative** — the 3-part structure that consistently produces good results.
3. **Short prompts beat long prompts.** Over-constraining (with hex ratios, pixel positions, font sizes in numbers) kills diversity.
4. **For Snoopy/comic styles:** Never say "NOT Snoopy." Never specify exact hex proportions. Trust the AI's creative judgment.

### Why Path A works for text-heavy styles

1. Neo-Brutalism, NYT Editorial, Pentagram — their quality comes from precise CSS (thick borders, exact font hierarchies, grid systems). AI image generation cannot reliably reproduce this.
2. html2pptx preserves text editability — essential for business presentations.
3. HTML is more reliable for Chinese text rendering than AI image generation.

### Style selection heuristic

- **Comic/illustration styles** (Snoopy, Manga, Ligne Claire, Neo-Pop, xkcd) → prefer Path B
- **Typography/grid styles** (Neo-Brutalism, NYT, Pentagram, Müller-Brockmann, Build Luxury) → Path A only
- **Data-heavy any style** → Path A for data slides, Path B for cover/illustration slides (Mixed)

---

*Document authored by agent-architect | Phase 1.4 | 2026-03-01*
