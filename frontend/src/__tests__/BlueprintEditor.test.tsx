import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BlueprintEditor from '../views/BlueprintEditor';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    getBlueprint: vi.fn(),
    generateBlueprint: vi.fn(),
    updateBlueprint: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const generatedBlueprint = [
  {
    id: 'slide_1',
    section_id: 'section_1',
    section_title: '研究背景与问题定义',
    page_number: 1,
    title: '为什么这个问题值得现在解决',
    slide_type: 'content',
    visual_type: 'illustration',
    path_hint: 'auto' as const,
    goal: '用一页建立问题的重要性',
    evidence_type: 'logic' as const,
    key_points: ['行业背景', '问题正在扩大'],
    content_brief: '先交代背景，再说明为什么此时必须行动',
    speaker_notes: '完整串联背景与紧迫性',
  },
];

describe('BlueprintEditor', () => {
  let onNext: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onNext = vi.fn();
    mockedApi.getBlueprint.mockResolvedValue({
      slide_blueprint: [],
      status: 'blueprint_missing',
    });
    mockedApi.generateBlueprint.mockResolvedValue({
      slide_blueprint: generatedBlueprint,
      status: 'blueprint_generated',
    });
    mockedApi.updateBlueprint.mockResolvedValue({
      slide_blueprint: generatedBlueprint,
      status: 'blueprint_updated',
    });
  });

  it('prefers existing blueprint before generating a new one', async () => {
    mockedApi.getBlueprint.mockResolvedValueOnce({
      slide_blueprint: generatedBlueprint,
      status: 'blueprint_generated',
      approved: true,
    });

    render(<BlueprintEditor sessionId="session-1" initialBlueprint={[]} onNext={onNext} />);

    expect(await screen.findByDisplayValue('为什么这个问题值得现在解决')).toBeTruthy();
    expect(mockedApi.getBlueprint).toHaveBeenCalledWith('session-1');
    expect(mockedApi.generateBlueprint).not.toHaveBeenCalled();
  });

  it('generates, edits, and confirms a new blueprint when none exists', async () => {
    const user = userEvent.setup();

    render(<BlueprintEditor sessionId="session-2" initialBlueprint={[]} onNext={onNext} />);

    expect(await screen.findByDisplayValue('为什么这个问题值得现在解决')).toBeTruthy();
    expect(mockedApi.generateBlueprint).toHaveBeenCalledWith('session-2');

    const titleInput = screen.getByDisplayValue('为什么这个问题值得现在解决');
    await user.clear(titleInput);
    await user.type(titleInput, '为什么这件事必须现在推进');
    await user.click(screen.getByText('确认页级策划并继续'));

    await waitFor(() => {
      expect(mockedApi.updateBlueprint).toHaveBeenCalledWith(
        'session-2',
        expect.arrayContaining([
          expect.objectContaining({ title: '为什么这件事必须现在推进' }),
        ]),
      );
    });
    expect(onNext).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ title: '为什么这件事必须现在推进' }),
      ]),
    );
  });
});
