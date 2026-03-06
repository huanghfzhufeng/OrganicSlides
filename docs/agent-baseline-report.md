# Agent 基准评估报告

**生成日期**: 2026-03-01
**评估范围**: OrganicSlides Agent 系统 v1.0
**评估方法**: 代码分析 + 提示词审查 (未实际运行)

---

## 摘要

本报告基于对五个核心 Agent 的代码分析和提示词审查，建立了演示文稿生成系统的基准质量标准。评估框架定义了三个主要维度：

1. **大纲质量** (Outline Quality)
2. **内容质量** (Content Quality)
3. **视觉设计质量** (Visual Design Quality)

### 关键发现

- ✅ **架构健全**: Agent 流程清晰，数据传递一致
- ⚠️ **基础阶段**: 多个 Agent 依赖模拟数据和默认实现
- ⚠️ **提示词待优化**: 部分 Agent 提示词缺乏具体指导
- ✅ **完整的降级策略**: 所有 Agent 都有默认大纲/内容生成

---

## 第1章 系统架构分析

### 1.1 Agent 流程架构

```
用户需求
   ↓
[Researcher] - 搜索资料和文档检索
   ↓
[Planner] - 生成结构化大纲
   ↓
[Writer] - 撰写每页内容
   ↓
[Visual] - 确定布局和视觉元素
   ↓
[Renderer] - 生成最终 PPTX 文件
```

### 1.2 数据流结构

各 Agent 通过共享状态字典传递数据：

```python
state = {
    "user_intent": str,              # 用户需求
    "source_docs": List[Dict],       # 上传的文档
    "search_results": List[Dict],    # 搜索结果
    "outline": List[Dict],           # 大纲结构
    "slides_data": List[Dict],       # 幻灯片内容
    "theme_config": Dict,            # 主题配置
    "current_status": str,           # 当前状态
    "current_agent": str,            # 当前 Agent
    "messages": List[Dict]           # 对话历史
}
```

### 1.3 错误处理策略

| Agent | 输入缺失 | LLM 失败 | 验证失败 |
|-------|---------|---------|---------|
| Researcher | 返回空结果 | 返回模拟结果 | N/A |
| Planner | 返回默认大纲 | 返回默认大纲 | 使用默认大纲 |
| Writer | 报错返回 | 返回默认幻灯片 | 使用默认幻灯片 |
| Visual | 跳过处理 | 应用默认设计 | 应用默认设计 |
| Renderer | 报错返回 | 异常捕获 | 保存文件或抛出异常 |

---

## 第2章 Agent 详细分析

### 2.1 研究 Agent (Researcher)

**职责**: RAG 检索和联网搜索

#### 输出模式
```python
{
    "source_docs": List[Dict],          # 合并后的文档
    "search_results": List[Dict],       # 搜索结果
    "current_status": "research_complete",
    "messages": List[Dict]              # 状态消息
}
```

#### 当前限制
- 🔴 `web_search()`: 返回模拟数据 (TODO: 集成真实 API)
- 🔴 `rag_search()`: 返回模拟数据 (TODO: 集成 LlamaIndex)
- ✅ 数据去重逻辑完整
- ✅ 并行执行搜索任务

#### 质量评估
- **提示词质量**: ⭐⭐⭐ (基础但清晰)
- **实现完整性**: ⭐⭐ (主要为模拟)
- **预期性能**: 待集成真实 API 后评估

---

### 2.2 策划 Agent (Planner)

**职责**: 分析用户意图，生成结构化大纲

#### 输出模式
```python
{
    "outline": [
        {
            "id": "section_xxx",
            "title": "章节标题",
            "type": "cover|content|data|comparison|quote|chart|conclusion",
            "key_points": ["要点1", "要点2"],
            "notes": "演讲者备注"
        }
    ],
    "current_status": "outline_generated",
    "messages": List[Dict]
}
```

#### 提示词分析

**强项**:
- ✅ 清晰定义了 8 种章节类型
- ✅ 明确指定了总页数范围 (6-12页)
- ✅ 要求结构逻辑清晰（开头+结尾）

**缺陷**:
- ❌ 对"标题质量"无具体指导 (命令式 vs 话题式)
- ❌ 缺少受众分析指导
- ❌ key_points 数量无约束 (未指定 2-4 的范围)
- ❌ 未提及演讲时长估计的细节

#### 验证逻辑
```
✓ 大纲非空
✓ 至少 2 个章节
✓ 不超过 20 个章节
✓ 首页为 cover 或包含 cover 类型
⚠️ 不检查重复标题
⚠️ 不检查逻辑顺序
```

#### 默认大纲
```
1. 封面 (cover) - 无要点
2. 介绍 (content) - ["背景", "目标"]
3. 主要内容 (content) - ["核心观点"]
4. 总结 (conclusion) - ["回顾", "行动号召"]
```

#### 质量评估
- **提示词质量**: ⭐⭐⭐⭐ (详细、结构清晰)
- **实现完整性**: ⭐⭐⭐ (LLM 集成 + 验证 + 降级)
- **预期输出评分**: 50-70/100 (依赖 LLM 质量)

---

### 2.3 撰写 Agent (Writer)

**职责**: 根据大纲生成每页内容

#### 输出模式
```python
[
    {
        "page_number": 1,
        "section_id": "section_1",
        "title": "页面标题",
        "layout_intent": "cover|bullet_points|two_column|data_driven|quote|conclusion",
        "content": {
            "main_text": "主要内容",
            "bullet_points": ["要点1", "要点2", "要点3"],
            "supporting_text": "补充说明"
        },
        "speaker_notes": "演讲者备注...",
        "visual_needs": {
            "needs_image": false,
            "needs_chart": false,
            "chart_type": null,
            "image_description": null
        }
    }
]
```

#### 提示词分析

**强项**:
- ✅ 完整的 JSON 输出格式规范
- ✅ 明确的撰写原则 (5条要点上限、15字限制)
- ✅ 区分 main_text、bullet_points、supporting_text
- ✅ 要求演讲者备注详细

**缺陷**:
- ❌ 缺少对大纲上下文的充分利用
- ❌ 没有针对不同类型页面的撰写指导
- ❌ 对"简洁"的定义不够量化
- ❌ 未指定 speaker_notes 的最小长度

#### 验证逻辑
```
✓ 幻灯片非空
✓ 每页都有标题
⚠️ 不检查 bullet_points 数量
⚠️ 不检查文本长度
⚠️ 不检查 speaker_notes 覆盖率
```

#### 默认幻灯片生成
```
基于大纲自动生成：
- page_number: 顺序编号
- title: 来自大纲
- bullet_points: 来自大纲 key_points
- speaker_notes: 来自大纲 notes
```

#### 质量评估
- **提示词质量**: ⭐⭐⭐⭐ (规范清晰)
- **实现完整性**: ⭐⭐⭐ (LLM 集成 + 验证 + 降级)
- **预期输出评分**: 50-70/100 (高度依赖大纲质量)

---

### 2.4 视觉总监 Agent (Visual)

**职责**: 确定布局、视觉元素和颜色方案

#### 输出模式
```python
[
    {
        "page_number": 1,
        "layout_id": 0,
        "layout_name": "title_slide|bullet_list|two_content|comparison|picture_with_caption|blank",
        "visual_elements": [
            {
                "type": "image|chart|icon|shape",
                "position": "left|right|center|background",
                "description": "视觉元素描述",
                "chart_config": {
                    "type": "bar|line|pie|donut",
                    "data": {"labels": [], "values": []}
                }
            }
        ],
        "color_emphasis": ["#5D7052"],
        "animation_suggestion": "fade_in|slide_left|none"
    }
]
```

#### 提示词分析

**强项**:
- ✅ 明确的布局选择规则 (基于文本长度)
- ✅ 完整的布局类型定义
- ✅ 支持颜色强调和动画建议

**缺陷**:
- ❌ 布局规则只涵盖文本长度，未考虑内容类型
- ❌ 缺少色彩搭配原则
- ❌ 对"视觉元素"的具体例子不足
- ❌ 动画建议缺乏场景指导

#### 默认设计逻辑
```
文本长度 < 50字 → blank (大字号居中)
文本长度 50-150字 → bullet_list (标准列表)
文本长度 > 150字 → two_content (双栏)
需要图表 → two_content
需要图片 → picture_with_caption
```

#### 质量评估
- **提示词质量**: ⭐⭐⭐ (基础但不够细致)
- **实现完整性**: ⭐⭐⭐ (LLM 集成 + 默认设计)
- **预期输出评分**: 40-60/100 (布局多样性可能不足)

---

### 2.5 渲染引擎 Agent (Renderer)

**职责**: 调用 python-pptx 生成最终 PPTX 文件

#### 技术栈
- 🟢 **python-pptx**: 基础 PPTX 生成库
- 🟢 **主题配置**: 支持背景色、文本色、主色
- 🟢 **布局映射**: 10 种标准布局类型

#### 支持的功能
- ✅ 标题设置 (支持主题颜色)
- ✅ 要点列表 (支持多级)
- ✅ 演讲者备注 (添加到 notes_slide)
- ✅ 主题应用 (背景色、文本色)

#### 已知限制
- ❌ 不支持插入图片
- ❌ 不支持创建图表数据
- ❌ 不支持动画效果
- ❌ 不支持高级排版 (如文本换行、对齐)
- ⚠️ 颜色硬编码，需要通过 theme_config 传递

#### 质量评估
- **实现完整性**: ⭐⭐⭐ (基础功能完整)
- **预期输出评分**: 60-70/100 (缺少视觉多样性)

---

## 第3章 评估框架定义

### 3.1 三个测试主题

#### 1️⃣ 学术主题 (Academic)
**主题**: AI人工智能在医疗领域的应用
**特点**:
- 需要专业术语和数据支持
- 通常采用严谨的逻辑结构
- 包含大量技术细节和案例研究

**预期大纲**: 背景-发展历程-关键应用-案例-未来方向-结论

#### 2️⃣ 商业主题 (Business)
**主题**: 新能源汽车市场分析与投资策略
**特点**:
- 注重市场数据和竞争分析
- 强调商业价值和投资收益
- 包含对比分析和趋势预测

**预期大纲**: 市场背景-行业分析-竞争格局-投资机会-风险评估-结论

#### 3️⃣ 公益主题 (Public Welfare)
**主题**: 校园心理健康关爱行动
**特点**:
- 强调实际可操作的方案
- 需要同理心和关怀导向
- 包含资源列表和行动指南

**预期大纲**: 问题现状-心理影响-资源介绍-关爱方案-行动指南-结论

### 3.2 评估指标

#### 📋 大纲质量 (权重: 30%)

| 指标 | 评估维度 | 目标值 |
|------|---------|-------|
| section_count | 章节数量 | 6-12 |
| has_cover | 是否有封面 | true |
| has_conclusion | 是否有总结 | true |
| title_quality | 标题质量评分 | 7-10 |
| key_points_avg | 平均要点数 | 2-4 |
| type_distribution | 类型多样性 | ≥3种 |

**评分公式**:
```
基础分: 50
- 章节数量合理 (+20): 6-12页
- 有完整结构 (+10+10): cover + conclusion
- 标题质量好 (+title_quality): 0-10
- 要点合理 (+5): 2-4个/页
```

#### 📄 内容质量 (权重: 40%)

| 指标 | 评估维度 | 目标值 |
|------|---------|-------|
| slide_count | 幻灯片数量 | 6-12 |
| text_length_avg | 平均文本长度 | 50-200字 |
| bullet_point_avg | 平均要点数 | 2-5个 |
| speaker_notes_coverage | 备注覆盖率 | >80% |
| content_variety | 内容多样性 | ≥3种布局 |

**评分公式**:
```
基础分: 50
- 幻灯片数量合理 (+15): 6-12张
- 文本长度合理 (+15): >70%在50-200字
- 要点分布合理 (+10): >70%在2-5个
- 演讲者备注充分 (+10): >80%覆盖
- 内容多样性 (+10): ≥3种布局
```

#### 🎨 视觉质量 (权重: 30%)

| 指标 | 评估维度 | 目标值 |
|------|---------|-------|
| layout_variety | 布局多样性 | ≥4种 |
| visual_element_coverage | 视觉元素覆盖 | >50% |
| color_usage | 颜色使用 | ≥2种 |
| color_emphasis_ratio | 色彩强调覆盖 | >50% |
| animation_suggestions | 动画建议覆盖 | >50% |

**评分公式**:
```
基础分: 50
- 布局多样 (+20): ≥4种
- 视觉元素多 (+15): >50%覆盖
- 颜色使用恰当 (+15): ≥2种 + 50%强调
- 动画建议 (+10): >50%覆盖
```

#### 🎯 综合评分 (0-100)

```
综合评分 = 大纲质量 × 0.3 + 内容质量 × 0.4 + 视觉质量 × 0.3
```

**评级标准**:
- ⭐⭐⭐⭐⭐: 90-100 (优秀)
- ⭐⭐⭐⭐: 80-89 (良好)
- ⭐⭐⭐: 70-79 (及格)
- ⭐⭐: 60-69 (基础)
- ⭐: <60 (需改进)

---

## 第4章 当前系统的预期性能

### 4.1 理想场景 (所有 Agent 正常运行)

#### 预期大纲评分: 65-75/100
- ✅ 章节结构合理 (6-10页)
- ✅ 有封面和总结
- ⚠️ 标题质量取决于 LLM
- ⚠️ 可能缺少类型多样性

#### 预期内容评分: 60-70/100
- ✅ 文本长度合理
- ✅ 要点分布合理
- ⚠️ 演讲者备注可能不足
- ⚠️ 内容多样性有限

#### 预期视觉评分: 40-55/100
- ❌ 布局多样性有限 (主要依赖 Writer 布局意图)
- ❌ 无法插入图片和图表
- ⚠️ 颜色方案简单
- ❌ 动画建议未实现

#### 综合预期: 55-65/100
**评级**: ⭐⭐⭐ (及格)

### 4.2 当前限制对评分的影响

| 限制 | 影响维度 | 降分幅度 |
|------|---------|---------|
| Researcher 全为模拟数据 | 内容多样性 | -5-10 |
| Writer 缺少针对性提示 | 内容质量 | -10-15 |
| Visual 提示词简单 | 视觉质量 | -20-30 |
| Renderer 无图片/图表 | 视觉质量 | -15-25 |
| 无实际 LLM 运行验证 | 全维度 | -5-10 (预估偏差) |

---

## 第5章 改进机会

### 5.1 短期改进 (Phase 2)

#### 1. 增强 Planner 提示词
**改进内容**:
- 添加"标题不使用笼统词汇"的约束
- 明确指定每页要点数量 (2-4)
- 根据主题类型的大纲模板

**预期增益**: 大纲质量 +10-15 分

#### 2. 优化 Writer 提示词
**改进内容**:
- 为不同类型页面提供写作指导
- 明确 speaker_notes 的最小长度
- 基于大纲上下文的内容生成

**预期增益**: 内容质量 +10-15 分

#### 3. 增强 Visual 提示词
**改进内容**:
- 基于内容类型的布局推荐
- 颜色搭配原则和指南
- 视觉元素的具体例子

**预期增益**: 视觉质量 +10-15 分

### 5.2 中期改进 (Phase 2-3)

#### 1. 集成真实搜索 API
- 集成 Tavily/SerpAPI 获取真实搜索结果
- 预期增益: 内容多样性 +5-10 分

#### 2. 增强 Renderer 功能
- 支持图片插入 (通过 AI 生成或 unsplash)
- 支持基础图表 (条形图、饼图)
- 预期增益: 视觉质量 +15-20 分

#### 3. 添加代理知识库
- 集成 huashu-slides 知识库
- 个性化提示词基于主题
- 预期增益: 综合评分 +10-20 分

---

## 第6章 基准输出示例

### 6.1 期望的优秀大纲 (80+/100)

```json
{
  "outline": [
    {
      "id": "sec_001",
      "title": "AI驱动的医疗革命",
      "type": "cover",
      "key_points": [],
      "notes": ""
    },
    {
      "id": "sec_002",
      "title": "医疗AI的三大应用场景",
      "type": "content",
      "key_points": [
        "医学影像诊断 - 识别肺癌准确率达99%",
        "药物研发加速 - 周期缩短50%",
        "个性化治疗方案 - 基于患者基因数据"
      ],
      "notes": "展示具体数字和案例..."
    },
    {
      "id": "sec_003",
      "title": "全球领先的医疗AI公司",
      "type": "comparison",
      "key_points": [
        "IBM Watson for Oncology - 癌症诊疗",
        "Google DeepMind - 蛋白质折叠",
        "国内先行者 - 推想医学、深睿医疗"
      ],
      "notes": "对比其核心优势和应用领域..."
    },
    ...
    {
      "id": "sec_007",
      "title": "医疗AI的未来方向",
      "type": "conclusion",
      "key_points": [
        "监管框架不断完善，保证患者安全",
        "融合多模态数据，提升诊疗精准度",
        "构建生态系统，实现全面健康管理"
      ],
      "notes": "强调行业发展的长期机遇..."
    }
  ]
}
```

**质量指标**:
- 章节数: 7 (在 6-12 范围内) ✅
- 标题质量: 9/10 (具体、有力，不笼统) ✅
- 类型分布: 5种 (cover, content, comparison, conclusion) ✅
- 要点平均: 3.2个 (在 2-4 范围内) ✅
- **大纲评分**: 82/100 ⭐⭐⭐⭐

---

## 第7章 实施建议

### 7.1 立即行动

1. **建立评估基准** (已完成)
   - ✅ 创建三个测试主题
   - ✅ 定义评估指标
   - ✅ 实现评估器

2. **运行基准测试** (Task #12)
   - 使用三个测试主题
   - 记录每个 Agent 的输出
   - 生成基准报告

3. **优化提示词** (Task #7)
   - 根据评估结果改进 Planner、Writer、Visual 提示词
   - 重新运行测试并比对改进幅度

### 7.2 关键指标监控

在 Phase 2-3 中持续追踪：
- 大纲质量评分趋势
- 内容质量评分趋势
- 视觉质量评分趋势
- 综合评分改进幅度

### 7.3 验收标准

**Phase 2 目标**: 综合评分 ≥ 70/100 (⭐⭐⭐)
- 大纲质量: ≥ 75
- 内容质量: ≥ 70
- 视觉质量: ≥ 65

**Phase 3 目标**: 综合评分 ≥ 80/100 (⭐⭐⭐⭐)
- 大纲质量: ≥ 80
- 内容质量: ≥ 80
- 视觉质量: ≥ 75

---

## 附录

### A. 评估框架代码位置

```
tests/agent_eval/
├── __init__.py              # 框架导出
├── test_themes.py           # 三个测试主题定义
└── evaluator.py             # 评估器实现
    ├── OutlineEvaluator     # 大纲质量评估
    ├── ContentEvaluator     # 内容质量评估
    ├── VisualEvaluator      # 视觉质量评估
    └── ComprehensiveEvaluator  # 综合评估
```

### B. 使用示例

```python
from tests.agent_eval import ComprehensiveEvaluator, TEST_THEMES

# 评估单个主题
result = ComprehensiveEvaluator.evaluate_full_pipeline(
    outline=state["outline"],
    slides_data=state["slides_data"],
    theme_name=TEST_THEMES[0].name
)

# 查看综合评分
print(f"综合评分: {result['overall_score']}/100")
print(result['summary'])
```

### C. 提示词改进检查清单

#### Planner 提示词改进
- [ ] 添加标题创意指导 (命令式 vs 话题式)
- [ ] 明确指定 key_points 数量 (2-4)
- [ ] 添加基于主题的大纲模板
- [ ] 强调逻辑连贯性

#### Writer 提示词改进
- [ ] 为每种布局类型提供撰写建议
- [ ] 明确 speaker_notes 最小长度 (50字)
- [ ] 添加要点长度约束 (15字以内)
- [ ] 提供内容扩展示例

#### Visual 提示词改进
- [ ] 基于内容类型的布局推荐规则
- [ ] 颜色搭配原则和对比度指南
- [ ] 视觉元素类型的具体例子
- [ ] 动画效果的适用场景

---

**报告结束**

更新日期: 2026-03-01
下一步: 运行 Phase 1.6 基准测试 (Task #12)
