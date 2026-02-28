"""
测试主题定义 - 用于基准评估的三个标准主题

包含三个不同领域的演示主题：
1. 学术领域：AI人工智能在医疗领域的应用
2. 商业领域：新能源汽车市场分析与投资策略
3. 公益领域：校园心理健康关爱行动
"""

from typing import Dict, Any


class TestTheme:
    """测试主题基类"""

    def __init__(self, name: str, category: str, description: str):
        self.name = name
        self.category = category
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description
        }


# 学术主题：AI在医疗领域的应用
ACADEMIC_THEME = TestTheme(
    name="AI人工智能在医疗领域的应用",
    category="Academic",
    description="深入探讨人工智能技术在医疗诊断、治疗和管理中的应用，包括机器学习、深度学习在医学影像、药物发现和个性化医疗中的创新应用。"
)

# 商业主题：新能源汽车市场分析
BUSINESS_THEME = TestTheme(
    name="新能源汽车市场分析与投资策略",
    category="Business",
    description="分析全球新能源汽车市场的发展趋势、市场规模、竞争格局和投资机会，包括电动汽车、混合动力和氢燃料电池技术的商业前景分析。"
)

# 公益主题：校园心理健康关爱
PUBLIC_WELFARE_THEME = TestTheme(
    name="校园心理健康关爱行动",
    category="PublicWelfare",
    description="校园学生心理健康的现状分析、常见问题识别、心理援助资源和关爱行动建议，旨在提高学生心理健康意识和提供支持资源。"
)


# 主题集合，便于遍历测试
TEST_THEMES = [
    ACADEMIC_THEME,
    BUSINESS_THEME,
    PUBLIC_WELFARE_THEME
]


def get_theme_by_name(theme_name: str) -> TestTheme:
    """根据主题名称获取主题对象"""
    for theme in TEST_THEMES:
        if theme.name == theme_name:
            return theme
    raise ValueError(f"Unknown theme: {theme_name}")


def get_themes_by_category(category: str) -> list[TestTheme]:
    """根据分类获取主题列表"""
    return [theme for theme in TEST_THEMES if theme.category == category]
