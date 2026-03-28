import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OutlineEditor from '../views/OutlineEditor';
import type { OutlineItem } from '../api/client';

const initialOutline: OutlineItem[] = [
  { id: 'intro', title: '引言', type: 'Intro' },
  { id: 'body', title: '主体', type: 'Content' },
];

describe('OutlineEditor', () => {
  it('submits the edited local outline', async () => {
    const user = userEvent.setup();
    const onNext = vi.fn().mockResolvedValue(undefined);

    render(<OutlineEditor initialOutline={initialOutline} onNext={onNext} />);

    const inputs = screen.getAllByRole('textbox');
    await user.clear(inputs[0]);
    await user.type(inputs[0], '新的引言');
    await user.click(screen.getByRole('button', { name: '确认大纲并继续' }));

    expect(onNext).toHaveBeenCalledWith([
      { id: 'intro', title: '新的引言', type: 'Intro' },
      { id: 'body', title: '主体', type: 'Content' },
    ]);
  });

  it('keeps local edits isolated from the incoming outline prop', async () => {
    const user = userEvent.setup();
    const onNext = vi.fn().mockResolvedValue(undefined);
    render(<OutlineEditor initialOutline={initialOutline} onNext={onNext} />);

    const inputs = screen.getAllByRole('textbox');
    await user.clear(inputs[0]);
    await user.type(inputs[0], '本地编辑');

    expect(initialOutline[0].title).toBe('引言');
  });
});
