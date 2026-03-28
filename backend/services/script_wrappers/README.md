# Script Wrapper Modules

Clean Python interface for huashu-slides scripts with comprehensive validation, error handling, and logging.

## Overview

Three wrapper modules provide production-ready interfaces to external scripts:
- `image_gen.py` — Generate images via Gemini API
- `html_converter.py` — Convert HTML slides to PPTX
- `slide_creator.py` — Create PPTX from image sequences

**Key features:**
- Full parameter validation with clear error messages
- Subprocess timeout handling (prevents hanging)
- Comprehensive logging for debugging
- Type hints for IDE support
- Error recovery (returns None on failure, never raises subprocess exceptions)

---

## 1. Image Generation (`image_gen.py`)

### Function Signature

```python
def generate_image(
    prompt: str,
    output_path: str,
    input_image: Optional[str] = None,
    resolution: str = "1K",
    api_key: Optional[str] = None,
) -> Optional[str]:
    """
    Generate an image using the `gemini-3.1-flash-image-preview` API.

    Returns:
        Absolute path to generated image on success, None on failure
    """
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | str | Yes | Image description/generation instruction (non-empty) |
| `output_path` | str | Yes | Path where image will be saved |
| `input_image` | str | No | Reference image for style transfer/editing (file must exist) |
| `resolution` | str | No | Output resolution: `1K`, `2K`, or `4K` (default: `1K`) |
| `api_key` | str | No | Gemini API key (uses `GEMINI_API_KEY` env var if not provided) |

### Return Value

- **Success**: Absolute path to generated PNG file
- **Failure**: `None` (errors logged but not raised)

### Validation

- ✓ Prompt must be non-empty string
- ✓ Output path must be valid
- ✓ Input image (if provided) must exist and be readable
- ✓ Resolution must be 1K, 2K, or 4K
- ✓ API key must be available (parameter or environment)
- ✓ Output directory created automatically

### Examples

```python
from backend.services.script_wrappers import generate_image

# Basic usage
image_path = generate_image(
    prompt="A serene mountain landscape at sunset",
    output_path="slides/cover.png"
)

# With style reference
image_path = generate_image(
    prompt="Manga style: excited character discovering something",
    output_path="slides/scene-01.png",
    input_image="style-samples/manga.png",  # Use this for style consistency
    resolution="2K"
)

# With custom API key
image_path = generate_image(
    prompt="...",
    output_path="...",
    api_key="sk-..."  # Override default
)

# Handle errors
if image_path is None:
    # Check logs for details (error was logged but not raised)
    print("Image generation failed")
else:
    print(f"Generated: {image_path}")
```

### Error Handling

All errors are logged and return `None` (no exceptions raised):

| Condition | Behavior | Log Level |
|-----------|----------|-----------|
| Invalid prompt | ValueError raised (before subprocess) | (exception) |
| Missing output path | ValueError raised | (exception) |
| Invalid resolution | ValueError raised | (exception) |
| Input image not found | ValueError raised | (exception) |
| No API key available | ValueError raised | (exception) |
| Subprocess timeout (300s) | Logs error, returns None | ERROR |
| API call fails | Logs stderr, returns None | ERROR |
| Output file not created | Logs error, returns None | ERROR |

### Environment Variables

```bash
# Required (if api_key parameter not provided)
export GEMINI_API_KEY="sk-your-api-key"

# Optional for proxies
export HTTP_PROXY="http://proxy.example.com:8080"
export HTTPS_PROXY="https://proxy.example.com:8080"
```

---

## 2. HTML to PPTX Converter (`html_converter.py`)

### Function Signature

```python
def html_to_pptx_slide(html_file_path: str) -> Optional[dict]:
    """
    Convert a single HTML slide to PPTX format.

    Returns:
        Dict with slide metadata on success, None on failure
    """
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `html_file_path` | str | Yes | Path to HTML file (must exist and have .html extension) |

### Return Value

**Success** — Dictionary with slide metadata:
```python
{
    "success": True,
    "output_path": "/abs/path/to/slide.pptx",
    "width_px": 960,
    "height_px": 540,
    "placeholders": [
        {"id": "placeholder-1", "x": 0.0, "y": 0.0, "w": 1.0, "h": 0.5},
        ...
    ]
}
```

**Failure** — `None` (errors logged but not raised)

### Validation

- ✓ HTML file path required
- ✓ File must exist
- ✓ File must have .html extension
- ✓ File must be readable

### Examples

```python
from backend.services.script_wrappers import html_to_pptx_slide

# Convert single slide
slide_data = html_to_pptx_slide("slides/slide-01.html")

if slide_data:
    print(f"Converted to: {slide_data['output_path']}")
    for placeholder in slide_data.get("placeholders", []):
        print(f"  Placeholder: {placeholder['id']} at ({placeholder['x']}, {placeholder['y']})")
else:
    print("Conversion failed (check logs)")
```

### HTML Constraints

The html2pptx.js script has four hard constraints. Violations cause conversion failures:

#### 1. Text must be in semantic tags

```html
<!-- ❌ WRONG -->
<div>Some text</div>

<!-- ✅ CORRECT -->
<div>
  <h1>Title</h1>
  <p>Some text</p>
</div>
```

#### 2. No CSS gradients

```css
/* ❌ WRONG */
background: linear-gradient(to right, red, blue);

/* ✅ CORRECT */
background: #FF0000;
```

#### 3. Paragraphs/headings can't have backgrounds

```html
<!-- ❌ WRONG -->
<h1 style="background: red;">Title</h1>

<!-- ✅ CORRECT -->
<div style="background: red;">
  <h1>Title</h1>
</div>
```

#### 4. Images must use <img>, not background-image

```css
/* ❌ WRONG */
div { background-image: url('image.png'); }

/* ✅ CORRECT */
<img src="image.png" alt="description">
```

### Error Handling

| Condition | Behavior | Log Level |
|-----------|----------|-----------|
| Invalid path | ValueError raised | (exception) |
| File not found | ValueError raised | (exception) |
| Wrong extension | ValueError raised | (exception) |
| Conversion timeout (120s) | Logs error, returns None | ERROR |
| Invalid HTML format | Logs error, returns None | ERROR |
| JSON parse error | Logs error, returns None | ERROR |

---

## 3. Slide Creator (`slide_creator.py`)

### Function Signature

```python
def create_pptx_from_images(
    image_paths: list[str],
    output_path: str,
    layout: str = "fullscreen",
    titles: Optional[list[str]] = None,
    bg_color: str = "FFFFFF",
) -> Optional[str]:
    """
    Create PowerPoint from image sequence.

    Returns:
        Absolute path to PPTX file on success, None on failure
    """
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image_paths` | list[str] | Yes | List of image file paths (all must exist) |
| `output_path` | str | Yes | Path where PPTX will be saved |
| `layout` | str | No | Slide layout mode (see table below) |
| `titles` | list[str] | No | Slide titles (count must match image count) |
| `bg_color` | str | No | Background color hex (default: FFFFFF) |

### Layout Modes

| Layout | Description | Use Case |
|--------|-------------|----------|
| `fullscreen` | Image fills entire slide | Path B (full AI visuals) |
| `title_above` | 20% title bar at top | Captioned images |
| `title_below` | 20% title bar at bottom | Gallery with captions |
| `title_left` | 30% title area on left | Title + image layouts |
| `center` | Image centered, maintains aspect | Natural sizing |
| `grid` | Multiple images per slide | Contact sheets, galleries |

### Return Value

- **Success**: Absolute path to created PPTX file
- **Failure**: `None` (errors logged but not raised)

### Examples

```python
from backend.services.script_wrappers import create_pptx_from_images

# Path B: Full-screen images (AI-generated visuals)
pptx_path = create_pptx_from_images(
    image_paths=[
        "output/slide-01.png",
        "output/slide-02.png",
        "output/slide-03.png",
    ],
    output_path="presentation.pptx",
    layout="fullscreen"
)

# With titles
pptx_path = create_pptx_from_images(
    image_paths=["img1.png", "img2.png"],
    output_path="titled-slides.pptx",
    layout="title_above",
    titles=["Introduction", "Methodology"]
)

# Grid layout for gallery
pptx_path = create_pptx_from_images(
    image_paths=[f"gallery/{i}.png" for i in range(1, 10)],
    output_path="gallery.pptx",
    layout="grid"
)

# Handle errors
if pptx_path:
    print(f"Created: {pptx_path}")
else:
    print("PPTX creation failed")
```

### Validation

- ✓ At least one image path required
- ✓ All images must exist and be readable
- ✓ Output path must be valid
- ✓ Layout must be one of: fullscreen, title_above, title_below, title_left, center, grid
- ✓ Titles (if provided) count must match image count
- ✓ Output directory created automatically

### Error Handling

| Condition | Behavior | Log Level |
|-----------|----------|-----------|
| Empty image list | ValueError raised | (exception) |
| Image not found | ValueError raised | (exception) |
| Invalid layout | ValueError raised | (exception) |
| Titles mismatch | ValueError raised | (exception) |
| Creation timeout (60s) | Logs error, returns None | ERROR |
| Subprocess fails | Logs stderr, returns None | ERROR |
| Output not created | Logs error, returns None | ERROR |

---

## Integration with FastAPI

### Basic endpoint example

```python
from fastapi import FastAPI, File, UploadFile
from backend.services.script_wrappers import generate_image, create_pptx_from_images

app = FastAPI()

@app.post("/api/generate-image")
async def generate(prompt: str, resolution: str = "1K"):
    """Generate image from prompt"""
    output_path = f"/tmp/generated-{id(prompt)}.png"
    result = generate_image(
        prompt=prompt,
        output_path=output_path,
        resolution=resolution
    )

    if result is None:
        return {"error": "Image generation failed"}

    return {
        "status": "success",
        "image_url": f"/images/{Path(result).name}",
        "path": result
    }

@app.post("/api/create-presentation")
async def create_pptx(image_urls: list[str]):
    """Create PPTX from images"""
    output_path = f"/tmp/presentation-{id(image_urls)}.pptx"

    result = create_pptx_from_images(
        image_paths=image_urls,
        output_path=output_path,
        layout="fullscreen"
    )

    if result is None:
        return {"error": "PPTX creation failed"}

    return {
        "status": "success",
        "pptx_url": f"/files/{Path(result).name}",
        "path": result
    }
```

---

## Logging Configuration

All wrappers use Python's `logging` module. Configure in your app:

```python
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

# Set script_wrappers to DEBUG for detailed logs
logging.getLogger('backend.services.script_wrappers').setLevel(logging.DEBUG)
```

---

## Testing

Run unit tests (no external scripts needed):

```bash
# Install pytest if needed
pip install pytest pytest-mock

# Run all tests
pytest tests/unit/test_script_wrappers.py -v

# Run specific test class
pytest tests/unit/test_script_wrappers.py::TestImageGenWrapper -v

# Run with coverage
pytest tests/unit/test_script_wrappers.py --cov=backend.services.script_wrappers
```

Test coverage:
- ✓ Parameter validation
- ✓ Input file existence checks
- ✓ Timeout handling
- ✓ Subprocess communication
- ✓ Error recovery
- ✓ Environment variable handling

---

## Troubleshooting

### "ModuleNotFoundError: uv"

Ensure `uv` is installed:
```bash
pip install uv  # Or: curl -PsSL https://astral.sh/uv/install.sh | sh
```

### "GEMINI_API_KEY not set"

```bash
export GEMINI_API_KEY="sk-..."
# Or pass as parameter: generate_image(..., api_key="sk-...")
```

### "Image file not found: /path/to/file.png"

Ensure all image paths are absolute and files exist:
```python
from pathlib import Path
paths = [str(Path(p).resolve()) for p in image_list]
```

### "HTML conversion failed"

Check that HTML follows the four constraints (see HTML Constraints section above).

### Timeout errors

Increase timeout if processing takes longer:
- `generate_image`: Default 300s, can be overridden in code
- `html_to_pptx_slide`: Default 120s
- `create_pptx_from_images`: Default 60s

---

## Design Principles

1. **Fail Gracefully**: Return None instead of raising subprocess exceptions
2. **Validate Early**: Check inputs before subprocess, raise ValueError for bad params
3. **Log Everything**: All errors logged with context (stdout, stderr, etc.)
4. **Type Safe**: Full type hints for IDE support and type checking
5. **Immutable Paths**: Always return absolute paths, never modify inputs
6. **Timeout Protected**: All subprocess calls have timeouts to prevent hangs

---

## Future Enhancements

- [ ] Async subprocess calls for non-blocking generation
- [ ] Batch processing API (generate multiple images in parallel)
- [ ] Progress callbacks (60% complete, etc.)
- [ ] Image format options (JPEG, WebP, etc.)
- [ ] Caching layer for duplicate prompts
- [ ] Retry logic with exponential backoff for transient failures
