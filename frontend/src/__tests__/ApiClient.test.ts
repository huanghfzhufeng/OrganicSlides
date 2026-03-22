import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api, type OutlineItem } from '../api/client';

const mockFetch = vi.fn();

describe('api client', () => {
  beforeEach(() => {
    const storage = new Map<string, string>();
    vi.stubGlobal('fetch', mockFetch);
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => {
        storage.set(key, value);
      }),
      removeItem: vi.fn((key: string) => {
        storage.delete(key);
      }),
    });
    mockFetch.mockReset();
  });

  it('creates projects with the trimmed request contract', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        session_id: 'session-1',
        status: 'created',
        session_access_token: 'token-1',
      }),
    });

    await api.createProject('生成一个产品路演');

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/project/create',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          prompt: '生成一个产品路演',
          style_id: null,
          style: 'organic',
        }),
      }),
    );
  });

  it('updates outlines with a typed response payload', async () => {
    const outline: OutlineItem[] = [
      { id: 'intro', title: '引言', type: 'Intro' },
    ];

    mockFetch.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        status: 'outline_updated',
        outline,
      }),
    });

    const result = await api.updateOutline('session-1', outline, 'access-1');

    expect(result.status).toBe('outline_updated');
    expect(result.outline).toEqual(outline);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/workflow/outline/update',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          session_id: 'session-1',
          outline,
          access_token: 'access-1',
        }),
      }),
    );
  });
});
