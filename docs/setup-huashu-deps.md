# Huashu-Slides 依赖安装与环境配置指南

> 完整配置 AI 演示文稿工作流的所有依赖和脚本环境。基于 `huashu-slides/scripts/` 中的三个核心脚本。

## 快速开始

```bash
# 1. 验证 Python 版本
python3 --version  # 需要 >=3.10

# 2. 配置 Gemini API Key
export GEMINI_API_KEY="your-api-key-here"

# 3. 验证脚本环境（见下文）
```

---

## 脚本依赖详解

### 脚本 #1: `generate_image.py` — AI 图像生成

**用途**：使用 Google Gemini 3 Pro Image 生成或编辑演示文稿中的图像。

**系统要求**：
- Python ≥ 3.10
- `uv` 包管理工具（推荐）或标准 `pip`

**核心依赖**（PEP 723 script dependencies）：
```python
requires-python = ">=3.10"
dependencies = [
    "google-genai>=1.0.0",      # Google Gemini API 客户端
    "pillow>=10.0.0",            # 图像处理（PNG 输出）
    "httpx[socks]",              # HTTP 客户端（API 通信）
]
```

**安装方式**：

#### 方案 A：使用 uv（推荐）
```bash
# uv 会自动读取脚本中的 PEP 723 headers
uv run huashu-slides/scripts/generate_image.py \
  --prompt "你的图像描述" \
  --filename "output.png"
```

#### 方案 B：使用 pip
```bash
pip install google-genai pillow httpx
python3 huashu-slides/scripts/generate_image.py \
  --prompt "你的图像描述" \
  --filename "output.png"
```

**使用示例**：

```bash
# 生成新图像（Path B）
export GEMINI_API_KEY="sk-..."
uv run huashu-slides/scripts/generate_image.py \
  --prompt "Neo-Brutalism style slide: red rectangle with bold 'HELLO WORLD' text" \
  --filename "slide-01.png" \
  --resolution 2K

# 基于样例图风格生成（Path A 辅助，垫图）
uv run huashu-slides/scripts/generate_image.py \
  --input-image "huashu-slides/assets/style-samples/style-01-snoopy.png" \
  --prompt "Snoopy comic style: happy characters working together" \
  --filename "slide-illustration.png" \
  --resolution 2K
```

**参数说明**：
- `--prompt` / `-p` ：图像描述或 AI 生成指令（必需）
- `--filename` / `-f` ：输出文件名，如 `output.png`（必需）
- `--input-image` / `-i` ：可选的参照图，强制生成与其风格一致的图像
- `--resolution` / `-r` ：输出分辨率（1K / 2K / 4K，默认 1K）
- `--api-key` / `-k` ：API 密钥（覆盖环境变量 `GEMINI_API_KEY`）

**故障排查**：

| 问题 | 解决方案 |
|------|---------|
| `ModuleNotFoundError: google` | 运行 `pip install google-genai` 或使用 `uv run` |
| `No API key provided` | 设置 `export GEMINI_API_KEY="your-key"` |
| 图像输出质量低 | 尝试 `--resolution 2K` 或 `4K`；优化 prompt |
| API 超时 | 检查网络连接；重试请求 |

---

### 脚本 #2: `html2pptx.js` — HTML 转 PowerPoint（Path A）

**用途**：将 HTML 幻灯片（可编辑）转换为 PowerPoint 文件。

**系统要求**：
- Node.js ≥ 18
- npm 或 yarn

**核心依赖**：
```json
{
  "dependencies": {
    "playwright": "^1.40+",    // 浏览器自动化（HTML 渲染/截图）
    "sharp": "^0.32+",         // 图像处理（PNG 优化）
    "pptxgenjs": "^3.12+"      // PowerPoint 生成库
  }
}
```

**安装方式**：

```bash
# 进入 huashu-slides 目录
cd huashu-slides

# 方案 A：使用 npm（推荐）
npm install

# 方案 B：使用 yarn
yarn install

# 方案 C：仅安装必需依赖
npm install playwright sharp pptxgenjs
```

**首次使用**：
```bash
# Playwright 需要下载浏览器二进制文件
npx playwright install chromium
```

**使用示例**：

```bash
# 单个 HTML 文件转 PPT
node huashu-slides/scripts/html2pptx.js \
  slide-01.html \
  -o output.pptx

# 多个 HTML 文件合并
node huashu-slides/scripts/html2pptx.js \
  slide-01.html slide-02.html slide-03.html \
  -o presentation.pptx

# 指定输出目录
node huashu-slides/scripts/html2pptx.js \
  slide-*.html \
  -o ./output/my-presentation.pptx
```

**HTML 规范**（重要！）：

Path A 使用 html2pptx 时必须遵守这四条硬性约束，否则导出会失败：

1. **DIV 中的文字必须用标签包裹**
   ```html
   <!-- ❌ 错误 -->
   <div>直接文字</div>

   <!-- ✅ 正确 -->
   <div>
     <h1>标题</h1>
     <p>正文</p>
   </div>
   ```

2. **不支持 CSS 渐变**
   ```css
   /* ❌ 错误 */
   background: linear-gradient(to right, red, blue);

   /* ✅ 正确 */
   background: #FF0000;  /* 纯色 */
   ```

3. **段落和标题不能有背景或边框**
   ```html
   <!-- ❌ 错误 -->
   <h1 style="background: red; border: 2px solid black;">标题</h1>

   <!-- ✅ 正确 -->
   <div style="background: red; border: 2px solid black; padding: 10px;">
     <h1>标题</h1>
   </div>
   ```

4. **DIV 不能用 background-image，改用 <img> 标签**
   ```css
   /* ❌ 错误 */
   div { background-image: url('image.png'); }

   /* ✅ 正确 */
   <img src="image.png" alt="描述">
   ```

**故障排查**：

| 问题 | 解决方案 |
|------|---------|
| `Cannot find module 'playwright'` | 运行 `npm install playwright` |
| Playwright 浏览器缺失 | 运行 `npx playwright install chromium` |
| `ERR: Content overflows body` | 减少内容或增大容器；检查 HTML 尺寸 |
| PPT 样式丢失 | 确保 CSS 使用纯色（无渐变）；避免复杂 SVG |
| 中文显示错误 | 添加 `<meta charset="UTF-8">` 到 HTML `<head>` |

---

### 脚本 #3: `create_slides.py` — 图像序列转 PowerPoint（Path B）

**用途**：将生成的图像（PNG）序列组装为 PowerPoint 演示文稿。每张图像占满整个幻灯片。

**系统要求**：
- Python ≥ 3.10
- `uv` 包管理工具或标准 `pip`

**核心依赖**：
```python
requires-python = ">=3.10"
dependencies = [
    "python-pptx>=1.0.0",   # PowerPoint 文件生成
    "Pillow>=10.0.0",       # 图像处理和验证
]
```

**安装方式**：

#### 方案 A：使用 uv（推荐）
```bash
# uv 自动读取脚本 headers
uv run huashu-slides/scripts/create_slides.py --help
```

#### 方案 B：使用 pip
```bash
pip install python-pptx Pillow
python3 huashu-slides/scripts/create_slides.py --help
```

**使用示例**：

```bash
# 基础用法：全屏图像
uv run huashu-slides/scripts/create_slides.py \
  slide-01.png slide-02.png slide-03.png \
  -o output.pptx

# 指定布局：标题在上方
uv run huashu-slides/scripts/create_slides.py \
  slide-01.png slide-02.png \
  --layout title_above \
  -t "Slide 1 Title" "Slide 2 Title" \
  -o titled-slides.pptx

# 指定标题在下方
uv run huashu-slides/scripts/create_slides.py \
  *.png \
  --layout title_below \
  -o with-captions.pptx
```

**参数说明**：
- `image1.png image2.png ...` ：输入 PNG 文件列表（必需）
- `-o` / `--output` ：输出 PPT 文件名（默认 `output.pptx`）
- `--layout` ：布局模式（fullscreen / title_above / title_below / title_left / center / grid）
- `-t` / `--titles` ：各幻灯片标题列表（可选）
- `--cols` ：网格布局的列数（仅 grid 布局）

**布局说明**：

| 布局 | 适用场景 | 图像尺寸 |
|------|---------|---------|
| `fullscreen` | Path B（AI 全视觉） | 占满整个幻灯片 |
| `title_above` | 图像+上方标题 | 图像 80%，标题 20% |
| `title_below` | 图像+下方标题 | 图像 80%，标题 20% |
| `title_left` | 图像+左侧标题 | 图像 70%，标题 30% |
| `center` | 居中图像 | 维持原始宽高比，最大化 |
| `grid` | 缩略图网格 | 每行多张，常见于相册 |

**故障排查**：

| 问题 | 解决方案 |
|------|---------|
| `ModuleNotFoundError: pptx` | 运行 `pip install python-pptx` |
| `File not found: slide-01.png` | 检查文件路径；使用绝对路径或相对路径 |
| PPT 文件无法打开 | 确保所有输入 PNG 有效；尝试不同布局 |
| 图像显示模糊 | 使用 2K 或 4K 分辨率生成 PNG |

---

## 完整工作流示例

### 场景：生成一份 5 页教育培训 PPT

#### 步骤 1：准备内容和风格

```bash
cd /Users/zeke/agent\ dome/OrganicSlides

# 设置 API Key
export GEMINI_API_KEY="sk-..."

# 确认风格样例图可用
ls huashu-slides/assets/style-samples/style-02-manga.png
```

#### 步骤 2：Path B（全 AI 视觉）— 生成 5 张图像

```bash
# 参照样例图，确保风格一致（垫图机制）
for i in {1..5}; do
  uv run huashu-slides/scripts/generate_image.py \
    --input-image huashu-slides/assets/style-samples/style-02-manga.png \
    --prompt "Manga educational slide $i: teaching concept $i" \
    --filename "slide-0${i}.png" \
    --resolution 2K
done

# 生成 PPT
uv run huashu-slides/scripts/create_slides.py \
  slide-01.png slide-02.png slide-03.png slide-04.png slide-05.png \
  -o training-slides.pptx
```

#### 步骤 3：Path A（可编辑 HTML）— 手工 HTML + 选择性插画

```bash
# 为主要页面生成插画（其他页面纯 HTML）
uv run huashu-slides/scripts/generate_image.py \
  --input-image huashu-slides/assets/style-samples/style-02-manga.png \
  --prompt "Manga cover: exciting introduction to machine learning" \
  --filename "cover-illustration.png" \
  --resolution 2K

# 编写 5 个 HTML 文件（slide-01.html ~ slide-05.html）
# 在需要的地方嵌入上面生成的 PNG

# 转换为 PPT
node huashu-slides/scripts/html2pptx.js \
  slide-01.html slide-02.html slide-03.html slide-04.html slide-05.html \
  -o training-slides.pptx
```

---

## 环境变量配置

### 必需变量

```bash
# Gemini API 密钥（generate_image.py 必需）
export GEMINI_API_KEY="sk-..."
```

### 可选配置

```bash
# 代理设置（如需翻墙）
export HTTP_PROXY="http://proxy.example.com:8080"
export HTTPS_PROXY="https://proxy.example.com:8080"

# Python 输出编码（防止中文乱码）
export PYTHONIOENCODING=utf-8
```

### 持久化配置

添加到 `~/.zshrc` 或 `~/.bashrc`：

```bash
# 在 ~/.zshrc 最后添加
export GEMINI_API_KEY="sk-..."
```

然后重新加载：
```bash
source ~/.zshrc
```

---

## 系统依赖检查清单

在开始前运行此脚本验证环境：

```bash
#!/bin/bash

echo "=== Python 环境检查 ==="
python3 --version  # 需要 >=3.10
which uv || echo "⚠️  uv 未安装，改用 pip"

echo ""
echo "=== Node.js 环境检查 ==="
node --version  # 需要 >=18
npm --version

echo ""
echo "=== API 密钥检查 ==="
if [ -z "$GEMINI_API_KEY" ]; then
  echo "⚠️  GEMINI_API_KEY 未设置"
  echo "运行: export GEMINI_API_KEY='your-key-here'"
else
  echo "✓ GEMINI_API_KEY 已设置"
fi

echo ""
echo "=== 脚本文件检查 ==="
ls -la huashu-slides/scripts/generate_image.py
ls -la huashu-slides/scripts/html2pptx.js
ls -la huashu-slides/scripts/create_slides.py

echo ""
echo "=== 风格样例检查 ==="
ls huashu-slides/assets/style-samples/ | wc -l
echo "风格样例文件数量应为 17 个"

echo ""
echo "✓ 环境检查完成！"
```

---

## 常见问题 (FAQ)

### Q: 能否在 macOS/Linux/Windows 上运行？
**A**: 可以。所有脚本都是跨平台的。但在 Windows 上需要使用 WSL2 或 PowerShell。

### Q: 如何使用本地 Ollama 模型代替 Gemini？
**A**: 目前 `generate_image.py` 仅支持 Google Gemini API。要使用本地模型，需要修改脚本替换为 Ollama 客户端。

### Q: generate_image.py 支持批量生成吗？
**A**: 可以用 shell 循环或 Python 脚本批量调用。示例见"完整工作流"。

### Q: 图像生成很慢怎么办？
**A**: Gemini 3 Pro Image 通常需要 20-60 秒生成一张图像。使用更小的分辨率 (1K) 可加速，但会影响质量。

### Q: html2pptx 能保留动画吗？
**A**: 不能。html2pptx 生成静态 PPT。动画需要在 PowerPoint 或 Keynote 中手工添加。

### Q: 能否自定义 PPT 的母版或主题？
**A**: 可以。导出的 PPT 是标准 Office 格式，可在 PowerPoint/Keynote 中继续编辑母版。

---

## 故障排查快速指南

### 现象：`SyntaxError: invalid syntax`
```bash
# 原因：Python 版本过低
python3 --version
# 解决：安装 Python 3.10+
```

### 现象：`ModuleNotFoundError: google`
```bash
# 解决方案 A：使用 uv
uv run huashu-slides/scripts/generate_image.py --help

# 解决方案 B：安装缺失包
pip install google-genai pillow httpx
```

### 现象：html2pptx 输出空白 PPT
```bash
# 原因：HTML 中有 DIV 裸文字或使用了渐变
# 解决：检查 HTML 是否符合四条硬性约束（见上文）
```

### 现象：中文显示为方块或乱码
```bash
# 解决 Path A (HTML)：
# 在 HTML <head> 添加
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width">

# 解决 Path B (Python)：
export PYTHONIOENCODING=utf-8
```

---

## 推荐工作流图

```
┌─────────────────────────────────────────────────────┐
│         内容结构化 + 风格选择                         │
└──────────────┬──────────────────────────────────────┘
               │
         ┌─────┴─────┐
         │           │
    Path A        Path B
    (编辑)        (全AI)
     │              │
     ├─→ HTML ──────┤
     │   +插画       │
     │              │
     └─→ html2pptx  └─→ generate_image (×N)
            │             │
            └─→ PPT ←─────┘
                │
                └─→ create_slides.py (仅Path B)
                     │
                     └─→ PPT
```

---

## 相关文档

- **演示文稿制作流程**：`huashu-slides/SKILL.md`
- **风格参考指南**：`huashu-slides/references/proven-styles-gallery.md`
- **Snoopy 风格深度指南**：`huashu-slides/references/proven-styles-snoopy.md`
- **API 文档**：见各脚本的 `--help` 输出

---

## 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| 1.0 | 2026-03-01 | 初版：3 个核心脚本的完整文档 |
