# OrganicSlides 用户指南

> 从创意到专业演讲稿：AI 智能体协作生成系统

---

## 目录

1. [快速开始](#快速开始)
2. [完整工作流](#完整工作流)
3. [选择合适的视觉风格](#选择合适的视觉风格)
4. [理解双路径渲染](#理解双路径渲染)
5. [常见问题排查](#常见问题排查)
6. [高级用法](#高级用法)

---

## 快速开始

### 启动应用

#### 方案 A：Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/your-username/OrganicSlides.git
cd OrganicSlides

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入您的 API Keys
# - OPENAI_API_KEY (GPT-4o 用于内容生成)
# - GEMINI_API_KEY (Gemini 3 Pro Image 用于图像生成)

# 3. 启动所有服务
docker-compose up --build

# 4. 访问应用
# 前端: http://localhost:5173
# API 文档: http://localhost:8000/docs
# Redis 管理: http://localhost:6379 (如需连接)
```

**所需时间**: 3-5 分钟（首次构建）

#### 方案 B：手动启动（开发环境）

```bash
# 后端服务
cd backend
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="sk-..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 前端应用（新终端）
cd frontend
npm install
npm run dev  # 访问 http://localhost:5173
```

**所需时间**: 5-10 分钟（首次安装依赖）

---

## 完整工作流

### 第 1 步：输入主题

打开 OrganicSlides 前端，在首页输入您的演讲主题：

```
示例：
"2026 年 AI 企业应用趋势分析"
"如何建立高效的远程团队"
"产品发布会：新一代智能助手"
```

**输入提示**:
- ✓ 清晰表述主题（不是关键词列表）
- ✓ 包含目标受众信息（高管 / 开发者 / 普通用户）
- ✓ 指定演讲时长（5 分钟 / 30 分钟 / 1 小时）
- ✗ 不需要指定风格（系统会推荐）

### 第 2 步：多智能体协作

系统激活 5 个专业 AI 智能体，各司其职：

| 阶段 | 智能体 | 任务 | 输出 |
|-----|--------|------|------|
| 📚 **研究** | Researcher | 查找相关资料和案例 | 背景素材 |
| 📋 **策划** | Planner | 设计幻灯片大纲和结构 | 幻灯片提纲 |
| ✍️ **撰写** | Writer | 撰写标题、要点和备注 | 完整文案 |
| 🎨 **设计** | Visual | 选择风格、配色、布局 | 设计方案 |
| 🖨️ **渲染** | Renderer | 生成最终 PPTX 文件 | PowerPoint 文件 |

**进度显示**:
- 实时 SSE 流式更新（无需刷新页面）
- 每个阶段完成时间估算
- 可随时暂停或修改

### 第 3 步：人机回环（可选审核）

系统完成初稿后，您可以：

#### 审核大纲
```
自动生成的大纲结构：
1. 开场：吸引注意力（为什么要关注 AI？）
2. 现状：2025 年 AI 进展回顾
3. 趋势：2026 年的 5 大看点
4. 案例：企业成功应用故事
5. 行动：如何准备应对变化
6. 收场：核心观点总结
```

**修改选项**:
- ✏️ 调整章节顺序
- ➕ 增加新章节（如"竞争分析"）
- ➖ 删除不相关的章节
- 📝 编辑章节标题和要点

#### 修改后重新生成
点击"继续生成"，系统基于您的修改生成新的文案和设计。

### 第 4 步：选择视觉风格

系统推荐 3 个最适合的风格。您也可以手动选择：

**快速选择表**:

| 演讲场景 | 推荐风格 | 原因 |
|--------|---------|------|
| 品牌发布 | Snoopy 温暖漫画 | 亲切感强，易传播 |
| 企业培训 | Neo-Brutalism | 远距离可读，信息清晰 |
| 数据报告 | NYT Magazine | 权威感，专业 |
| 技术分享 | xkcd 白板 | 简洁，易理解 |
| 年轻用户 | Neo-Pop | 潮流感，视觉冲击 |
| 国风品牌 | 敦煌壁画 | 文化底蕴，高端 |

**预览风格**:
- 点击每个风格看样例幻灯片
- 理解其视觉特点和最佳用途
- 选择最符合您品牌调性的

### 第 5 步：选择渲染路径

系统会询问您的偏好：

#### 路径 A：可编辑 HTML（推荐用于商务）
```
HTML → Playwright 渲染 → PPTX
优势：
✓ 文字可在 PowerPoint 中继续编辑
✓ 中文渲染完美
✓ 排版精确，支持复杂布局
✓ 兼容所有 PowerPoint 版本

劣势：
✗ 图片是预先制作的
✗ 视觉风格不如 Path B 统一
```

#### 路径 B：全 AI 视觉（推荐用于演讲）
```
文字 → Gemini 生成图像 → PPTX
优势：
✓ 视觉风格完全统一
✓ 场景丰富，视觉冲击力强
✓ 适合台上演讲（视觉优先）

劣势：
✗ 生成较慢（每张 30-60 秒）
✗ 成本较高（使用 API）
✗ 文字不可编辑
```

#### 路径 Auto（自动）
```
系统根据演讲主题智能选择：
- 需要高度定制？→ Path A
- 需要视觉冲击？→ Path B
- 普通演讲？→ Path A（快速可靠）
```

### 第 6 步：下载和使用

```
✓ PPTX 文件已生成
├─ 在浏览器中下载
├─ 用 PowerPoint 或 Keynote 打开
├─ 根据需要添加：
│  ├─ 动画和过渡效果
│  ├─ 演讲者备注
│  └─ 扬声器备注
└─ 导出为 PDF 或视频
```

**质量检查清单**:
- [ ] 文案准确，无明显错误
- [ ] 图片清晰，分辨率足够
- [ ] 配色与品牌一致
- [ ] 字体大小易于远处观看
- [ ] 过渡效果不过度

---

## 选择合适的视觉风格

### 快速决策流程

```
您的演讲主题是？
│
├─ 品牌/产品介绍
│  └─ Snoopy 温暖漫画（首选）
│     或 Neo-Pop 新波普（年轻品牌）
│
├─ 企业培训/内部分享
│  └─ Neo-Brutalism 新粗野主义（首选）
│     或 学習漫画（趣味性强）
│
├─ 技术分享/开发者大会
│  └─ xkcd 白板手绘（首选）
│     或 Neo-Brutalism（信息量大）
│
├─ 数据报告/财务汇报
│  └─ NYT Magazine 编辑风（★ 强烈推荐）
│     或 Pentagram Editorial（高端）
│
├─ 年轻受众/创意行业
│  └─ Neo-Pop 新波普（首选）
│     或 像素画 RPG（游戏化）
│
└─ 国风/东方品牌
   └─ 敦煌壁画（首选）
      或 浮世绘（日本市场）
```

### 详细风格对比

参考完整的《风格选择指南》：[docs/style-selection-guide.md](./style-selection-guide.md)

**快速查询**:
- 想要最专业的？→ 使用 **NYT Magazine Editorial** 或 **Pentagram**（皆为 Path A）
- 想要最有趣？→ 使用 **Snoopy 温暖漫画** 或 **The Oatmeal**
- 想要最强视觉冲击？→ 使用 **Neo-Pop** 或 **苏联构成主义**
- 想要最快速度？→ 使用 **Neo-Brutalism**（纯 CSS，无需 AI）
- 想要文化底蕴？→ 使用 **敦煌壁画** 或 **浮世绘**

---

## 理解双路径渲染

### 架构对比

```
Path A: HTML → PPTX（可编辑）
┌─────────────────────────────────────┐
│ 1. 生成 HTML 文件（纯文本）           │
│ 2. 创建 CSS 样式（排版、配色）        │
│ 3. 嵌入选择性 AI 图片（可选）        │
│ 4. Playwright 渲染为截图             │
│ 5. html2pptx 转换为 PPTX             │
│ 6. PPTX 中文字保持可编辑状态         │
└─────────────────────────────────────┘
      耗时：30-60 秒
      成本：低（无 AI 图片生成费用）
      适用：商务、需要修改的场景

Path B: Prompt → AI Image → PPTX
┌─────────────────────────────────────┐
│ 1. 为每张幻灯片生成视觉描述          │
│ 2. Gemini API 生成 AI 图片（30-60s）  │
│ 3. 创建全屏幻灯片布局                │
│ 4. Python-pptx 组装最终文件          │
│ 5. 幻灯片完全由图片组成（不可编辑）  │
└─────────────────────────────────────┘
      耗时：5-10 分钟（N 张幻灯片）
      成本：较高（API 调用费用）
      适用：演讲、视觉优先的场景
```

### 何时使用 Path A

✓ 您需要在 PowerPoint 中修改文案
✓ 内容经常变动
✓ 您的网络连接不稳定
✓ 您想快速生成（< 1 分钟）
✓ 您想降低 API 成本
✓ 您使用 **Editorial 专业风格**（仅支持 Path A）

### 何时使用 Path B

✓ 您需要视觉震撼效果
✓ 这是一次重要的公开演讲
✓ 您想展示 AI 生成的艺术风格
✓ 您的幻灯片数量不多（< 10 张）
✓ 您有充足的 API 预算
✓ 您想让每张幻灯片都独一无二

### 混合策略

**推荐做法**：
```
1. 使用 Path A 快速生成初稿
2. 在 PowerPoint 中审核文案
3. 对关键幻灯片（封面、总结）使用 Path B 增强视觉
4. 通过 Gemini API 逐张生成，控制成本
```

---

## 常见问题排查

### Q1: "GEMINI_API_KEY 未设置" 错误

**症状**: 无法生成 AI 图片，收到 API key 错误

**解决方案**:

```bash
# 检查环境变量
echo $GEMINI_API_KEY

# 如果为空，设置它
export GEMINI_API_KEY="sk-your-gemini-key"

# 验证
curl https://generativelanguage.googleapis.com/v1beta/models/list?key=$GEMINI_API_KEY
```

**如果还是失败**:
1. 检查您的 Gemini API Key 是否有效（访问 Google AI Studio）
2. 确认 Key 被正确粘贴（无多余空格）
3. 尝试在浏览器中直接访问 API 文档链接

### Q2: "HTML 转换失败" 或 "PPTX 导出空白"

**症状**: Path A 生成空白 PPTX 或转换错误

**原因**: HTML 不符合 html2pptx 的 4 条硬性约束

**解决方案**:
```html
✗ 错误: <div>直接文字</div>
✓ 正确: <div><p>直接文字</p></div>

✗ 错误: background: linear-gradient(...)
✓ 正确: background: #FF0000

✗ 错误: <h1 style="background: red;">标题</h1>
✓ 正确: <div style="background: red;"><h1>标题</h1></div>

✗ 错误: div { background-image: url(...) }
✓ 正确: <img src="..." alt="...">
```

详见：[../setup-huashu-deps.md](./setup-huashu-deps.md#html-规范)

### Q3: "图像生成太慢" 或超时

**症状**: Path B 生成单张图片需要 > 2 分钟

**原因**: Gemini API 响应缓慢或网络延迟

**解决方案**:
1. 尝试更简短的 prompt（描述越详细，生成越慢）
2. 降低分辨率（2K → 1K）
3. 检查网络连接（VPN、代理）
4. 在 Google AI Studio 直接测试 API 连接

**高级**: 在脚本中增加超时时间
```python
# backend/services/script_wrappers/image_gen.py
DEFAULT_TIMEOUT = 300  # 改为 600（10 分钟）
```

### Q4: "中文显示错误" 或乱码

**症状**: PPTX 中中文字变成方块或乱码

**原因**: 字体编码或缺失

**解决方案**:
- Path A：确保 HTML 包含 `<meta charset="UTF-8">`
- Path B：图片中的中文由 AI 直接生成，通常无此问题
- 在 PowerPoint 中手动选择合适的中文字体（微软雅黑、思源黑体）

### Q5: "API 费用太高"

**症状**: Path B 生成费用超出预期

**解决方案**:
1. 使用 Path A（无图片生成费用）
2. 降低图片分辨率（1K 比 2K 便宜 30%）
3. 减少幻灯片数量（合并相似内容）
4. 使用 **Neo-Brutalism 风格**（可纯 CSS 实现，无需 AI）
5. 批量处理（API 通常提供量大优惠）

**估算成本**:
- Gemini 3 Pro Image: ~$0.05 - $0.2 per image
- 10 张幻灯片: $0.5 - $2 USD
- 100 张幻灯片: $5 - $20 USD

### Q6: 我选了 Editorial 风格，为什么只支持 Path A？

**答**: Professional Editorial 风格（NYT Magazine、Pentagram 等）依赖精确的 HTML/CSS 排版和网格系统。Path B 的 AI 图片生成无法保证排版精确性，所以只支持 Path A（HTML→PPTX）。

如果您需要全 AI 视觉，请选择其他 18 种风格中的任意一个。

---

## 高级用法

### 自定义风格

如果预设的 24 种风格都不符合您的要求，您可以：

```
1. 提供参考图片或设计稿
2. 系统基于参考图生成相似风格的幻灯片
3. 在视觉设计阶段与系统互动调整
```

**示例**：
```
"我想要宫崎骏动画那样的温暖手绘风格"
→ 系统识别视觉特征：
  - 水彩质感
  - 自然色调
  - 精细背景 + 简洁角色
→ 生成接近的定制风格
```

### 批量生成

为多个主题快速生成演讲稿：

```bash
# API 端点
POST /api/v1/project/batch-create
Content-Type: application/json

{
  "topics": [
    "第一季度财务报告",
    "产品路线图 2026",
    "团队建设工作坊"
  ],
  "style": "Neo-Brutalism",
  "render_path": "path_a"
}

# 系统并行处理多个主题
# 完成后一次性下载所有 PPTX
```

### 与您的 CMS 集成

如果您运行一个内容平台：

```python
from backend.services.script_wrappers import (
    generate_image,
    create_pptx_from_images,
)

# 在您的工作流中调用
presentation = create_pptx_from_images(
    image_paths=your_images,
    output_path="presentations/auto-generated.pptx",
    layout="fullscreen"
)

# 自动发布到您的网站
publish_to_cms(presentation)
```

---

## 支持和反馈

- **问题报告**: [GitHub Issues](https://github.com/your-username/OrganicSlides/issues)
- **功能建议**: [GitHub Discussions](https://github.com/your-username/OrganicSlides/discussions)
- **邮件支持**: support@organicslides.example.com

---

<div align="center">

**用 AI 种下一颗思想的种子 🌱**

[返回主文档](../README.md) | [查看风格指南](./style-selection-guide.md) | [技术文档](./setup-huashu-deps.md)

</div>
