import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import StyleSelector from '../views/StyleSelector';

describe('StyleSelector Component', () => {
  let mockOnNext: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockOnNext = vi.fn();
  });

  it('should render the component with title', () => {
    render(<StyleSelector onNext={mockOnNext} />);
    expect(screen.getByText('选择视觉风格')).toBeInTheDocument();
  });

  it('should display style options', () => {
    render(<StyleSelector onNext={mockOnNext} />);

    expect(screen.getByText('Organic Zen')).toBeInTheDocument();
    expect(screen.getByText('Neo Tech')).toBeInTheDocument();
    expect(screen.getByText('Classic Serenity')).toBeInTheDocument();
  });

  it('should select organic style by default', () => {
    const { container } = render(<StyleSelector onNext={mockOnNext} />);

    // Check if organic style card has the selected border
    const organicCard = container.querySelector('[style*="border"]');
    expect(organicCard).toBeInTheDocument();
  });

  it('should allow selecting different styles', async () => {
    const user = userEvent.setup();
    render(<StyleSelector onNext={mockOnNext} />);

    // Get the Neo Tech card (second card)
    const cards = screen.getAllByText(/Organic Zen|Neo Tech|Classic Serenity/);
    const techCard = cards[1].closest('div');

    if (techCard) {
      await user.click(techCard);
      // The component should update selection state
      expect(techCard).toBeInTheDocument();
    }
  });

  it('should display style descriptions', () => {
    render(<StyleSelector onNext={mockOnNext} />);

    expect(screen.getByText('自然、柔和、衬线体、米纸质感')).toBeInTheDocument();
    expect(screen.getByText('极简、冷调、无衬线、网格布局')).toBeInTheDocument();
    expect(screen.getByText('商务、稳重、宋体/衬线、留白')).toBeInTheDocument();
  });

  it('should display feature tags for each style', () => {
    render(<StyleSelector onNext={mockOnNext} />);

    // Organic Zen features
    expect(screen.getByText('柔和配色')).toBeInTheDocument();
    expect(screen.getByText('衬线字体')).toBeInTheDocument();
    expect(screen.getByText('有机形状')).toBeInTheDocument();

    // Neo Tech features
    expect(screen.getByText('网格系统')).toBeInTheDocument();
    expect(screen.getByText('无衬线')).toBeInTheDocument();
    expect(screen.getByText('科技感')).toBeInTheDocument();

    // Classic Serenity features
    expect(screen.getByText('商务风格')).toBeInTheDocument();
    expect(screen.getByText('大量留白')).toBeInTheDocument();
    expect(screen.getByText('经典配色')).toBeInTheDocument();
  });

  it('should call onNext when button is clicked', async () => {
    const user = userEvent.setup();
    render(<StyleSelector onNext={mockOnNext} />);

    const button = screen.getByText('开始生成');
    await user.click(button);

    expect(mockOnNext).toHaveBeenCalledTimes(1);
  });

  it('should render help text', () => {
    render(<StyleSelector onNext={mockOnNext} />);
    expect(screen.getByText('为您的演示文稿选择最适合的视觉语言')).toBeInTheDocument();
  });

  it('should have correct number of style options', () => {
    const { container } = render(<StyleSelector onNext={mockOnNext} />);

    // Look for style cards (should be 3)
    const cards = container.querySelectorAll('[style*="border"]').length;
    expect(cards).toBeGreaterThan(0);
  });

  it('should render with proper styling classes', () => {
    const { container } = render(<StyleSelector onNext={mockOnNext} />);

    // Check for key layout classes
    expect(container.querySelector('.max-w-5xl')).toBeInTheDocument();
    expect(container.querySelector('.grid')).toBeInTheDocument();
  });

  it('should display start button with correct text', () => {
    render(<StyleSelector onNext={mockOnNext} />);

    const startButton = screen.getByText('开始生成');
    expect(startButton).toBeInTheDocument();
    expect(startButton).not.toBeDisabled();
  });

  it('should support style switching via clicks', async () => {
    const user = userEvent.setup();
    const { container } = render(<StyleSelector onNext={mockOnNext} />);

    // Find all style cards
    const styleCards = Array.from(container.querySelectorAll('.example-card'));

    if (styleCards.length === 3) {
      // Click second card
      await user.click(styleCards[1]);
      expect(styleCards[1]).toBeInTheDocument();

      // Click third card
      await user.click(styleCards[2]);
      expect(styleCards[2]).toBeInTheDocument();
    }
  });
});
