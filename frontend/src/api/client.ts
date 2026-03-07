
const API_BASE_URL = 'http://localhost:8000/api/v1';

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

export interface ProjectResponse {
    session_id: string;
    status: string;
    session_access_token: string;
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
    created_at: string;
}

export interface ProjectPreviewSlide {
    page_number: number;
    title: string;
    render_path: string;
    status: 'pending' | 'complete' | 'failed' | string;
    preview_url: string;
    artifact_url: string;
    thumbnail_url: string;
}

export interface ProjectPreviewResponse {
    session_id: string;
    status: string;
    pptx_path: string;
    pptx_storage_key: string;
    last_restored_revision_number?: number | null;
    preview: {
        slides_count: number;
        completed_slides: number;
        failed_slides: number;
        thumbnail_urls: string[];
        slides: ProjectPreviewSlide[];
    };
}

export interface ProjectRevision {
    revision_id: string;
    project_id?: string | null;
    session_id: string;
    revision_number: number;
    revision_type: string;
    status: string;
    theme?: string | null;
    outline: OutlineItem[];
    outline_count: number;
    created_at: string;
    restored_from_revision_number?: number | null;
}

export interface ProjectRevisionListResponse {
    session_id: string;
    revisions: ProjectRevision[];
    total: number;
}

export interface ProjectRevisionRestoreResponse {
    status: string;
    session_id: string;
    restored_revision: ProjectRevision;
    restoration_revision: {
        revision_id: string;
        revision_number: number;
        revision_type: string;
    };
    current_state: {
        status: string;
        current_agent: string;
        outline: OutlineItem[];
        style_id: string;
        pptx_path: string;
        last_restored_revision_number?: number | null;
    };
}

export interface ProjectFailure {
    job_id: string;
    session_id: string;
    trigger: 'start_workflow' | 'resume_workflow' | string;
    status: string;
    current_agent: string;
    error_type: string;
    failure_stage: string;
    message: string;
    technical_message: string;
    recoverable: boolean;
    retry_available: boolean;
    retry_trigger: 'start_workflow' | 'resume_workflow' | string | null;
    details: Record<string, unknown>;
    failed_at: string | null;
}

export interface ProjectFailureResponse {
    session_id: string;
    failure: ProjectFailure | null;
}

export interface RetryProjectResponse {
    status: string;
    session_id: string;
    job_id: string;
    trigger: 'start_workflow' | 'resume_workflow' | string;
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

const withProjectAccessToken = (url: string, sessionAccessToken?: string): string => {
    if (!sessionAccessToken) {
        return url;
    }

    const urlObj = new URL(url);
    urlObj.searchParams.set('access_token', sessionAccessToken);
    return urlObj.toString();
};

// ==================== API 方法 ====================

export const api = {
    // 认证
    register: async (email: string, username: string, password: string): Promise<AuthResponse> => {
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
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
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
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
        const response = await fetch(`${API_BASE_URL}/auth/me`, {
            headers: tokenManager.getHeaders(),
        });
        if (!response.ok) throw new Error('Not authenticated');
        return response.json();
    },

    // 项目
    createProject: async (prompt: string, styleId?: string): Promise<ProjectResponse> => {
        const response = await fetch(`${API_BASE_URL}/project/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders()
            },
            body: JSON.stringify({ prompt, style_id: styleId ?? null, style: 'organic' }),
        });
        if (!response.ok) throw new Error('Failed to create project');
        return response.json();
    },

    listProjects: async (): Promise<{ projects: ProjectListItem[] }> => {
        const response = await fetch(`${API_BASE_URL}/projects`, {
            headers: tokenManager.getHeaders(),
        });
        if (!response.ok) throw new Error('Failed to fetch projects');
        return response.json();
    },

    getProjectPreview: async (
        sessionId: string,
        sessionAccessToken?: string,
    ): Promise<ProjectPreviewResponse> => {
        const response = await fetch(
            withProjectAccessToken(`${API_BASE_URL}/project/preview/${sessionId}`, sessionAccessToken),
        );
        if (!response.ok) throw new Error('Failed to fetch project preview');
        return response.json();
    },

    listProjectRevisions: async (
        sessionId: string,
        sessionAccessToken?: string,
        limit = 20,
    ): Promise<ProjectRevisionListResponse> => {
        const response = await fetch(
            withProjectAccessToken(
                `${API_BASE_URL}/project/revisions/${sessionId}?limit=${limit}`,
                sessionAccessToken,
            ),
        );
        if (!response.ok) throw new Error('Failed to fetch project revisions');
        return response.json();
    },

    restoreProjectRevision: async (
        sessionId: string,
        revisionNumber: number,
        sessionAccessToken?: string,
    ): Promise<ProjectRevisionRestoreResponse> => {
        const response = await fetch(`${API_BASE_URL}/project/revisions/restore`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders(),
            },
            body: JSON.stringify({
                session_id: sessionId,
                revision_number: revisionNumber,
                access_token: sessionAccessToken ?? null,
            }),
        });
        if (!response.ok) throw new Error('Failed to restore project revision');
        return response.json();
    },

    getProjectFailure: async (
        sessionId: string,
        sessionAccessToken?: string,
    ): Promise<ProjectFailureResponse> => {
        const response = await fetch(
            withProjectAccessToken(`${API_BASE_URL}/project/failure/${sessionId}`, sessionAccessToken),
        );
        if (!response.ok) throw new Error('Failed to fetch project failure');
        return response.json();
    },

    retryProjectGeneration: async (
        sessionId: string,
        trigger?: 'start_workflow' | 'resume_workflow' | string,
        sessionAccessToken?: string,
    ): Promise<RetryProjectResponse> => {
        const response = await fetch(`${API_BASE_URL}/project/retry`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders(),
            },
            body: JSON.stringify({
                session_id: sessionId,
                trigger: trigger ?? null,
                access_token: sessionAccessToken ?? null,
            }),
        });
        if (!response.ok) {
            let message = 'Failed to retry generation';
            try {
                const error = await response.json();
                message = error.detail || message;
            } catch {
                // Fall back to the default message when the error body is empty.
            }
            throw new Error(message);
        }
        return response.json();
    },

    getOutline: async (sessionId: string, sessionAccessToken?: string): Promise<OutlineResponse> => {
        const response = await fetch(
            withProjectAccessToken(`${API_BASE_URL}/workflow/outline/${sessionId}`, sessionAccessToken)
        );
        if (!response.ok) throw new Error('Failed to fetch outline');
        return response.json();
    },

    updateOutline: async (sessionId: string, outline: OutlineItem[], sessionAccessToken?: string): Promise<any> => {
        const response = await fetch(`${API_BASE_URL}/workflow/outline/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders()
            },
            body: JSON.stringify({ session_id: sessionId, outline, access_token: sessionAccessToken ?? null }),
        });
        if (!response.ok) throw new Error('Failed to update outline');
        return response.json();
    },

    getDownloadUrl: (sessionId: string, sessionAccessToken?: string) => {
        return withProjectAccessToken(`${API_BASE_URL}/project/download/${sessionId}`, sessionAccessToken);
    },

    getStartWorkflowUrl: (sessionId: string, sessionAccessToken?: string) => {
        return withProjectAccessToken(`${API_BASE_URL}/workflow/start/${sessionId}`, sessionAccessToken);
    },

    getResumeWorkflowUrl: (sessionId: string, sessionAccessToken?: string) => {
        return withProjectAccessToken(`${API_BASE_URL}/workflow/resume/${sessionId}`, sessionAccessToken);
    },

    // 更新会话风格（在大纲确认后、恢复工作流前调用）
    updateSessionStyle: async (
        sessionId: string,
        styleId: string,
        renderPathPreference?: string,
        sessionAccessToken?: string,
    ): Promise<void> => {
        const response = await fetch(`${API_BASE_URL}/project/style`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders()
            },
            body: JSON.stringify({
                session_id: sessionId,
                style_id: styleId,
                render_path_preference: renderPathPreference ?? 'auto',
                access_token: sessionAccessToken ?? null,
            }),
        });
        if (!response.ok) throw new Error('Failed to update session style');
    },

    // 风格
    getStyles: async (): Promise<Style[]> => {
        const response = await fetch(`${API_BASE_URL}/styles`);
        if (!response.ok) throw new Error('Failed to fetch styles');
        const data = await response.json();
        // Backend returns { styles: [...], total: N }
        return Array.isArray(data) ? data : (data.styles ?? []);
    },

    getStyleSample: (styleId: string): string => {
        return `${API_BASE_URL}/styles/${styleId}/sample`;
    },

    getStyleRecommendations: async (intent: string): Promise<string[]> => {
        const encoded = encodeURIComponent(intent);
        const response = await fetch(`${API_BASE_URL}/styles/recommend?intent=${encoded}`);
        if (!response.ok) throw new Error('Failed to fetch style recommendations');
        const data = await response.json();
        // Backend returns { recommended: [{id, ...}], intent }
        if (Array.isArray(data)) return data;
        if (data.recommended) return (data.recommended as Array<{ id: string }>).map((s) => s.id);
        return [];
    },
};
