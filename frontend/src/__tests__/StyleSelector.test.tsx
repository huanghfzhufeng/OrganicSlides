import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import StyleSelector from '../views/StyleSelector';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    getStyles: vi.fn(),
    getStyleRecommendations: vi.fn(),
    getStyleSample: vi.fn((styleId: string) => `/samples/${styleId}.png`),
  },
}));

const mockStyles = [
  {
    id: '01-snoopy',
    name_zh: 'Snoopy温暖漫画',
    name_en: 'Warm Comic Strip',
    tier: 1,
    description: '温暖叙事风格',
    colors: {
      primary: '#FFF8E8',
      secondary: '#87CEEB',
      background: '#FFF8E8',
      text: '#333333',
      accent: '#8FBC8F',
    },
    use_cases: ['品牌/产品介绍', '教育培训', '个人IP分享'],
    render_paths: ['path_a', 'path_b'],
  },
  {
    id: '18-neo-brutalism',
    name_zh: 'Neo-Brutalism 新粗野',
    name_en: 'Neo-Brutalism',
    tier: 1,
    description: '强对比高冲击',
    colors: {
      primary: '#F5E6D3',
      secondary: '#FF3B4F',
      background: '#F5E6D3',
      text: '#1A1A1A',
      accent: '#FFD700',
    },
    use_cases: ['教育培训', '内部分享', '技术分享'],
    render_paths: ['path_a', 'path_b'],
  },
  {
    id: 'p6-nyt-magazine',
    name_zh: 'NYT Magazine Editorial纽约时报编辑风',
    name_en: 'NYT Magazine Editorial',
    tier: 'editorial' as const,
    description: '权威编辑排版',
    colors: {
      primary: '#FEFEF9',
      secondary: '#1A1A1A',
      background: '#FEFEF9',
      text: '#1A1A1A',
      accent: '#C8000A',
    },
    use_cases: ['正式商务汇报', '数据报告', '行业分析'],
    render_paths: ['path_a'],
  },
];

const mockedApi = vi.mocked(api);

function createPendingPromise<T>() {
  return new Promise<T>(() => undefined);
}

describe('StyleSelector Component', () => {
  let mockOnNext: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockOnNext = vi.fn();
    mockedApi.getStyles.mockResolvedValue(mockStyles);
    mockedApi.getStyleRecommendations.mockResolvedValue(['18-neo-brutalism', '01-snoopy']);
  });

  it('renders the loading state before styles arrive', () => {
    mockedApi.getStyles.mockReturnValueOnce(createPendingPromise());
    mockedApi.getStyleRecommendations.mockReturnValueOnce(createPendingPromise());

    render(<StyleSelector userIntent="教育培训" onNext={mockOnNext} />);
    expect(screen.getByText('选择视觉风格')).toBeTruthy();
    expect(screen.getByText('正在加载风格库...')).toBeTruthy();
  });

  it('loads styles and renders recommendation and tier sections', async () => {
    render(<StyleSelector userIntent="教育培训课件" onNext={mockOnNext} />);

    expect((await screen.findAllByText('Snoopy温暖漫画')).length).toBeGreaterThan(0);
    expect((await screen.findAllByText('Neo-Brutalism 新粗野')).length).toBeGreaterThan(0);
    expect((await screen.findAllByText('NYT Magazine Editorial纽约时报编辑风')).length).toBeGreaterThan(0);
    expect(screen.getByText('智能推荐 — 最适合您的主题')).toBeTruthy();
    expect(screen.getByText('Tier 1 — 推荐')).toBeTruthy();
    expect(screen.getByText('Editorial — 专业出版')).toBeTruthy();
  });

  it('selects the recommended style by default and advances with the current selection', async () => {
    const user = userEvent.setup();
    render(<StyleSelector userIntent="教育培训课件" onNext={mockOnNext} />);

    expect((await screen.findAllByText('Snoopy温暖漫画')).length).toBeGreaterThan(0);
    const selectedLabel = screen.getByText('已选：').parentElement;
    expect(selectedLabel?.textContent).toContain('Neo-Brutalism 新粗野');

    await user.click(screen.getByText('开始生成'));
    expect(mockOnNext).toHaveBeenCalledWith('18-neo-brutalism');
  });

  it('allows switching selection and uses the new style on submit', async () => {
    const user = userEvent.setup();
    render(<StyleSelector userIntent="正式商务汇报" onNext={mockOnNext} />);

    const nytStyle = await screen.findByText('NYT Magazine Editorial纽约时报编辑风');
    await user.click(nytStyle);
    await user.click(screen.getByText('开始生成'));

    expect(mockOnNext).toHaveBeenCalledWith('p6-nyt-magazine');
  });

  it('shows an error state when style loading fails', async () => {
    mockedApi.getStyles.mockRejectedValueOnce(new Error('boom'));

    render(<StyleSelector userIntent="测试主题" onNext={mockOnNext} />);

    await waitFor(() => {
      expect(screen.getByText('boom')).toBeTruthy();
    });
  });
});
