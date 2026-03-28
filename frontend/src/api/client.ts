
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:18000/api/v1';

// ==================== 带超时的 fetch ====================

const DEFAULT_TIMEOUT_MS = 15_000;

function fetchWithTimeout(
    input: RequestInfo | URL,
    init?: RequestInit & { timeoutMs?: number },
): Promise<Response> {
    const { timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchInit } = init ?? {};
    const controller = new AbortController();
    const timer = setTimeout(
        () => controller.abort(new DOMException(`请求超时（${Math.round(timeoutMs / 1000)}秒）`, 'TimeoutError')),
        timeoutMs,
    );
    return fetch(input, { ...fetchInit, signal: controller.signal }).finally(() =>
        clearTimeout(timer),
    );
}

// ==================== 类型定义 ====================

export interface StyleColors {
    primary: string;
    secondary: string;
    background: string;
    text: string;
    accent: string;
    additional?: string[];
}

export interface Style {
    id: string;
    name_zh: string;
    name_en: string;
    tier: number | 'editorial';
    description?: string;
    colors?: StyleColors;
    typography?: { title_size: string; body_size: string; family: string };
    use_cases: string[];
    sample_image_path?: string;
    sample_image_url?: string;
    render_paths: string[];
}

export interface UploadedDocument {
    document_id: string;
    filename: string;
    source_docs: Array<{
        content: string;
        filename: string;
        source: string;
        metadata: { chapter: string; chunk_index: number };
    }>;
    chunk_count: number;
    chapters: string[];
}

export interface ProjectResponse {
    session_id: string;
    status: string;
    skill_id?: string;
    collaboration_mode?: CollaborationMode;
}

export type CollaborationMode = 'guided' | 'collaborative' | 'full_auto';

export interface SkillRuntimeMode {
    key: CollaborationMode;
    label: string;
    fit: string;
    checkpoints: string;
    is_default: boolean;
}

export interface SkillRuntimeCheckpoint {
    key: string;
    label: string;
    audiences: string;
}

export interface SkillRuntimeStep {
    number: number;
    title: string;
    mapped_stages: string[];
    checkpoints: SkillRuntimeCheckpoint[];
}

export interface SkillRuntimePath {
    key: 'path_a' | 'path_b';
    label: string;
    advantage: string;
    best_for: string;
    notes: string;
    is_default: boolean;
}

export interface SkillRuntimeSummary {
    skill_id: string;
    name: string;
    description: string;
    default_collaboration_mode: CollaborationMode;
    default_render_path: 'path_a' | 'path_b';
}

export interface SkillRuntime {
    skill_id: string;
    name: string;
    description: string;
    design_philosophy: string;
    skill_file: string;
    root_dir: string;
    scripts_dir: string;
    style_samples_dir: string;
    references_dir: string;
    reference_files: string[];
    supported_collaboration_modes: SkillRuntimeMode[];
    default_collaboration_mode: CollaborationMode;
    collaboration_mode: CollaborationMode;
    render_paths: SkillRuntimePath[];
    default_render_path: 'path_a' | 'path_b';
    runtime_steps: SkillRuntimeStep[];
    checkpoint_keys: string[];
}

export interface OutlineItem {
    id: string;
    title: string;
    type: string;
    key_points?: string[];
    notes?: string;
}

export interface OutlineResponse {
    outline: OutlineItem[];
    status: string;
}

export interface SlideBlueprintItem {
    id: string;
    section_id: string;
    section_title: string;
    page_number: number;
    title: string;
    slide_type: string;
    visual_type: string;
    path_hint: 'path_a' | 'path_b' | 'auto';
    goal: string;
    evidence_type: 'data' | 'case' | 'logic' | 'quote' | 'story';
    key_points: string[];
    content_brief: string;
    speaker_notes: string;
}

export interface BlueprintResponse {
    slide_blueprint: SlideBlueprintItem[];
    status: string;
    approved?: boolean;
}

export interface SlideReviewItem {
    page_number: number;
    title: string;
    visual_type: string;
    path_hint: 'path_a' | 'path_b' | 'auto' | string;
    render_path: 'path_a' | 'path_b' | string;
    layout_name: string;
    bullet_points: string[];
    speaker_notes: string;
    image_prompt: string;
    html_content: string;
    style_notes: string;
    review_status: string;
    accepted: boolean;
    revision_count: number;
    feedback: string;
}

export interface SlideReviewResponse {
    session_id: string;
    slides: SlideReviewItem[];
    approved: boolean;
    status: string;
}

export interface User {
    id: string;
    email: string;
    username: string;
    is_active: boolean;
    created_at: string;
}

export interface AuthResponse {
    user: User;
    token: {
        access_token: string;
        token_type: string;
        expires_in: number;
    };
}

export interface ProjectListItem {
    id: string;
    user_intent: string;
    theme: string;
    status: string;
    pptx_path: string;
    has_pptx: boolean;
    created_at: string;
}

export interface SlidePreview {
    page_number: number;
    title: string;
    content: { bullet_points?: string[]; [key: string]: unknown };
    speaker_notes: string;
    visual_type: string;
}

export interface ProjectPreview {
    session_id: string;
    user_intent: string;
    slides: SlidePreview[];
    total: number;
}

// ==================== Token 管理 ====================

const TOKEN_KEY = 'masppt_token';

export const tokenManager = {
    get: () => localStorage.getItem(TOKEN_KEY),
    set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
    remove: () => localStorage.removeItem(TOKEN_KEY),
    getHeaders: (): Record<string, string> => {
        const token = localStorage.getItem(TOKEN_KEY);
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }
};

// ==================== API 方法 ====================

export const api = {
    // 认证
    register: async (email: string, username: string, password: string): Promise<AuthResponse> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, username, password }),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
        }
        const data = await response.json();
        tokenManager.set(data.token.access_token);
        return data;
    },

    login: async (email: string, password: string): Promise<AuthResponse> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }
        const data = await response.json();
        tokenManager.set(data.token.access_token);
        return data;
    },

    logout: () => {
        tokenManager.remove();
    },

    getMe: async (): Promise<User> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/auth/me`, {
            headers: tokenManager.getHeaders(),
        });
        if (!response.ok) throw new Error('Not authenticated');
        return response.json();
    },

    // 文档上传
    uploadDocument: async (file: File): Promise<UploadedDocument> => {
        const formData = new FormData();
        formData.append('file', file);
        const response = await fetchWithTimeout(`${API_BASE_URL}/document/upload`, {
            method: 'POST',
            headers: tokenManager.getHeaders(),
            body: formData,
            timeoutMs: 60_000,  // 60s for large files
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: '文件上传失败' }));
            throw new Error(error.detail || '文件上传失败');
        }
        return response.json();
    },

    // 项目
    createProject: async (
        prompt: string,
        styleId?: string,
        sourceDocs?: UploadedDocument['source_docs'],
        isThesisMode?: boolean,
        skillId: string = 'huashu-slides',
        collaborationMode: CollaborationMode = 'guided',
    ): Promise<ProjectResponse> => {
        const hasThesisData = sourceDocs && sourceDocs.length > 0;
        const response = await fetchWithTimeout(`${API_BASE_URL}/project/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders()
            },
            body: JSON.stringify({
                prompt,
                style_id: styleId ?? null,
                style: 'organic',
                skill_id: skillId,
                collaboration_mode: collaborationMode,
                source_docs: sourceDocs ?? null,
                is_thesis_mode: isThesisMode ?? false,
            }),
            timeoutMs: hasThesisData ? 60_000 : DEFAULT_TIMEOUT_MS,
        });
        if (!response.ok) throw new Error('Failed to create project');
        return response.json();
    },

    getSkills: async (): Promise<{ skills: SkillRuntimeSummary[]; total: number }> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/skills`);
        if (!response.ok) throw new Error('Failed to fetch skills');
        return response.json();
    },

    getSkillRuntime: async (skillId: string): Promise<SkillRuntime> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/skills/${skillId}`);
        if (!response.ok) throw new Error('Failed to fetch skill runtime');
        return response.json();
    },

    listProjects: async (): Promise<{ projects: ProjectListItem[] }> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/projects`, {
            headers: tokenManager.getHeaders(),
        });
        if (!response.ok) throw new Error('Failed to fetch projects');
        return response.json();
    },

    getOutline: async (sessionId: string): Promise<OutlineResponse> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/workflow/outline/${sessionId}`);
        if (!response.ok) throw new Error('Failed to fetch outline');
        return response.json();
    },

    updateOutline: async (sessionId: string, outline: OutlineItem[]): Promise<any> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/workflow/outline/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders()
            },
            body: JSON.stringify({ session_id: sessionId, outline }),
        });
        if (!response.ok) throw new Error('Failed to update outline');
        return response.json();
    },

    generateBlueprint: async (sessionId: string): Promise<BlueprintResponse> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/workflow/blueprint/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders(),
            },
            body: JSON.stringify({ session_id: sessionId }),
            timeoutMs: 60_000,
        });
        if (!response.ok) throw new Error('Failed to generate slide blueprint');
        return response.json();
    },

    getBlueprint: async (sessionId: string): Promise<BlueprintResponse> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/workflow/blueprint/${sessionId}`, {
            headers: tokenManager.getHeaders(),
        });
        if (!response.ok) throw new Error('Failed to fetch slide blueprint');
        return response.json();
    },

    updateBlueprint: async (sessionId: string, slideBlueprint: SlideBlueprintItem[]): Promise<BlueprintResponse> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/workflow/blueprint/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders(),
            },
            body: JSON.stringify({
                session_id: sessionId,
                slide_blueprint: slideBlueprint,
            }),
        });
        if (!response.ok) throw new Error('Failed to update slide blueprint');
        return response.json();
    },

    getSlideReview: async (sessionId: string): Promise<SlideReviewResponse> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/workflow/slide-review/${sessionId}`, {
            headers: tokenManager.getHeaders(),
        });
        if (!response.ok) throw new Error('Failed to fetch slide review');
        return response.json();
    },

    updateSlideReview: async (
        sessionId: string,
        pageNumber: number,
        slidePatch: Record<string, unknown>,
        renderPatch: Record<string, unknown> = {},
        feedback: string = '',
    ): Promise<SlideReviewResponse> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/workflow/slide-review/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders(),
            },
            body: JSON.stringify({
                session_id: sessionId,
                page_number: pageNumber,
                slide_patch: slidePatch,
                render_patch: renderPatch,
                feedback,
            }),
        });
        if (!response.ok) throw new Error('Failed to update slide draft');
        return response.json();
    },

    acceptSlideReview: async (sessionId: string, pageNumber: number): Promise<SlideReviewResponse> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/workflow/slide-review/accept`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders(),
            },
            body: JSON.stringify({ session_id: sessionId, page_number: pageNumber }),
        });
        if (!response.ok) throw new Error('Failed to accept slide');
        return response.json();
    },

    regenerateSlideReview: async (sessionId: string, pageNumber: number): Promise<SlideReviewResponse> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/workflow/slide-review/regenerate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders(),
            },
            body: JSON.stringify({ session_id: sessionId, page_number: pageNumber }),
            timeoutMs: 60_000,
        });
        if (!response.ok) throw new Error('Failed to regenerate slide');
        return response.json();
    },

    getDownloadUrl: (sessionId: string) => {
        const token = tokenManager.get();
        const base = `${API_BASE_URL}/project/download/${sessionId}`;
        return token ? `${base}?token=${encodeURIComponent(token)}` : base;
    },

    getStartWorkflowUrl: (sessionId: string) => {
        const token = tokenManager.get();
        const base = `${API_BASE_URL}/workflow/start/${sessionId}`;
        return token ? `${base}?token=${encodeURIComponent(token)}` : base;
    },

    getResumeWorkflowUrl: (sessionId: string) => {
        const token = tokenManager.get();
        const base = `${API_BASE_URL}/workflow/resume/${sessionId}`;
        return token ? `${base}?token=${encodeURIComponent(token)}` : base;
    },

    getRenderWorkflowUrl: (sessionId: string) => {
        const token = tokenManager.get();
        const base = `${API_BASE_URL}/workflow/render/${sessionId}`;
        return token ? `${base}?token=${encodeURIComponent(token)}` : base;
    },

    // 更新会话风格（在大纲确认后、恢复工作流前调用）
    updateSessionStyle: async (sessionId: string, styleId: string, renderPathPreference?: string): Promise<void> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/project/style`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders()
            },
            body: JSON.stringify({
                session_id: sessionId,
                style_id: styleId,
                render_path_preference: renderPathPreference ?? 'auto',
            }),
        });
        if (!response.ok) throw new Error('Failed to update session style');
    },

    // 风格
    getStyles: async (): Promise<Style[]> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/styles`);
        if (!response.ok) throw new Error('Failed to fetch styles');
        const data = await response.json();
        // Backend returns { styles: [...], total: N }
        return Array.isArray(data) ? data : (data.styles ?? []);
    },

    getStyleSample: (styleId: string): string => {
        return `${API_BASE_URL}/styles/${styleId}/sample`;
    },

    getProjectPreview: async (sessionId: string): Promise<ProjectPreview> => {
        const response = await fetchWithTimeout(`${API_BASE_URL}/project/${sessionId}/preview`, {
            headers: tokenManager.getHeaders(),
        });
        if (!response.ok) throw new Error('Failed to fetch preview');
        return response.json();
    },

    getStyleRecommendations: async (intent: string): Promise<string[]> => {
        const encoded = encodeURIComponent(intent);
        const response = await fetchWithTimeout(`${API_BASE_URL}/styles/recommend?intent=${encoded}`);
        if (!response.ok) throw new Error('Failed to fetch style recommendations');
        const data = await response.json();
        // Backend returns { recommended: [{id, ...}], intent }
        if (Array.isArray(data)) return data;
        if (data.recommended) return (data.recommended as Array<{ id: string }>).map((s) => s.id);
        return [];
    },
};
