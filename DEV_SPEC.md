# OrganicSlides x huashu-slides Integration - Technical Specification

## 1. Overview

This document specifies the technical integration of huashu-slides capabilities into OrganicSlides, upgrading the system from a 3-theme prototype to a production-quality presentation generator with 17+ visual styles, dual rendering paths, and AI image generation.

## 2. Architecture Changes

### 2.1 Style System

**Current**: 3 hardcoded color themes (organic, tech, classic) in `state.py`

**Target**: Dynamic style registry with 17+ validated visual styles + 6 editorial styles

```
backend/
  static/
    styles/
      style-01-snoopy.json
      style-02-manga.json
      ...
      samples/
        style-01-snoopy.png
        style-02-manga.png
        ...
  styles/
    __init__.py
    registry.py      # StyleRegistry - loads/serves style configs
    recommender.py   # StyleRecommender - topic → style matching
```

**Style JSON Schema**:
```json
{
  "id": "style-01-snoopy",
  "name_zh": "史努比暖系漫画",
  "name_en": "Snoopy Warm Comics",
  "tier": 1,
  "colors": {
    "primary": "#333333",
    "secondary": "#87CEEB",
    "background": "#FFF8E8",
    "text": "#333333",
    "accent": "#FF6B35"
  },
  "typography": {
    "heading_font": "Comic Neue, cursive",
    "body_font": "system-ui, sans-serif",
    "heading_size": "36pt",
    "body_size": "24pt"
  },
  "use_cases": ["brand", "education", "personal_ip"],
  "sample_image_path": "samples/style-01-snoopy.png",
  "render_paths": ["path_b"],
  "base_style_prompt": "VISUAL REFERENCE: Charles Schulz Peanuts comic strip..."
}
```

**Style Tiers**:
- Tier 1 (Recommended): Snoopy, Manga, Ligne Claire, Neo-Pop
- Tier 2 (Advanced): xkcd, Oatmeal, Soviet, Dunhuang, Ukiyo-e
- Tier 3 (Specialized): Warm Narrative, Risograph, Isometric, Bauhaus, Blueprint, Vintage Ad, Collage, Pixel Art, Neo-Brutalism
- Editorial (Path A only): Pentagram, Fathom, Muller-Brockmann, Build Luxury, Takram, NYT Magazine

### 2.2 Dual Rendering Pipeline

**Path A: HTML to PPTX** (editable text, selective AI illustrations)
```
Visual Agent → HTML template (720×405pt) → [optional AI illustration] → html2pptx.js → slide
```

**Path B: Full AI Image** (maximum visual impact)
```
Visual Agent → image prompt (base_style + content) → generate_image.py → PNG → create_slides.py → slide
```

**Mixed Mode** (default: "auto"):
Per-slide routing based on content type and style capabilities.

```
backend/
  services/
    __init__.py
    image_generator.py     # Wraps generate_image.py (Gemini API)
    pptx_assembler.py      # Combines Path A + B results into PPTX
  agents/
    renderer/
      paths.py             # render_path_a(), render_path_b(), render_slide()
```

### 2.3 Agent Prompt Improvements

| Agent | Key Changes |
|-------|-------------|
| Researcher | Real web search (DuckDuckGo), knowledge base search |
| Planner | Assertion-evidence titles, visual_type field, ≤4 bullets |
| Writer | image_prompt field, path_hint field, content density rules |
| Visual | Design decision maker, render_path output per slide |
| Renderer | Dual path routing, parallel rendering, progress events |

### 2.4 State Extension

New fields in `PresentationState`:
```python
style_id: str                     # Selected style identifier
style_config: dict                # Full style configuration (from registry)
render_path_default: str          # "auto" | "path_a" | "path_b"
render_progress: List[dict]       # Per-slide render status tracking
```

### 2.5 New API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/styles` | List all visual styles |
| GET | `/api/v1/styles/{id}/sample` | Get style sample image |
| GET | `/api/v1/styles/recommend?intent=...` | Get top 3 style recommendations |

Modified endpoints:
- `POST /api/v1/project/create`: Accepts `style_id` and `render_path_preference`

### 2.6 New SSE Events

```json
{
  "type": "render_progress",
  "slide_number": 3,
  "total_slides": 8,
  "render_path": "path_b",
  "status": "completed"
}
```

## 3. New Configuration

```env
GEMINI_API_KEY=xxx
RENDER_PATH_DEFAULT=auto
STYLE_SAMPLES_DIR=./huashu-slides/assets/style-samples/
SKILL_SCRIPTS_DIR=./huashu-slides/scripts/
```

## 4. Frontend Changes

### 4.1 StyleSelector Rewrite
- Fetch styles from API
- Group by tier with visual cards showing real preview images
- Smart recommendations based on user intent
- Lightbox preview on click

### 4.2 Generation Experience
- Per-slide render progress cards
- Render path labels (Path A / Path B)
- Thumbnail previews on completion
- Real stats in ResearchView (replacing simulated data)

### 4.3 Render Path Selection
New UI element after style selection:
- Full AI Visual (Path B)
- HTML + AI Illustrations (Path A)
- Smart Mix (auto, default)

## 5. Error Handling

Graceful degradation hierarchy:
```
Path B (AI image) → Path A (HTML) → Basic python-pptx (text only) → Error
```

- Per-slide timeout: 90s (Path A), 120s (Path B)
- Overall workflow timeout: 10 minutes
- Partial success: deliver PPTX with all slides that rendered

## 6. Dependencies

### New Python Packages
- `duckduckgo-search` - Real web search for Researcher
- `google-genai>=1.0.0` - Gemini image generation

### New Node Packages
- `playwright` - HTML rendering
- `sharp` - Image processing
- `pptxgenjs` - PPTX generation

### Existing (verified)
- `python-pptx` - PPTX assembly
- `Pillow` - Image processing
