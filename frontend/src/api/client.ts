
const API_BASE_URL = 'http://localhost:8000/api/v1';

// ==================== 类型定义 ====================

export interface ProjectResponse {
    session_id: string;
    status: string;
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
    createProject: async (prompt: string, style: string = 'organic'): Promise<ProjectResponse> => {
        const response = await fetch(`${API_BASE_URL}/project/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...tokenManager.getHeaders()
            },
            body: JSON.stringify({ prompt, style }),
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

    getOutline: async (sessionId: string): Promise<OutlineResponse> => {
        const response = await fetch(`${API_BASE_URL}/workflow/outline/${sessionId}`);
        if (!response.ok) throw new Error('Failed to fetch outline');
        return response.json();
    },

    updateOutline: async (sessionId: string, outline: OutlineItem[]): Promise<any> => {
        const response = await fetch(`${API_BASE_URL}/workflow/outline/update`, {
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

    getDownloadUrl: (sessionId: string) => {
        return `${API_BASE_URL}/project/download/${sessionId}`;
    },

    getStartWorkflowUrl: (sessionId: string) => {
        return `${API_BASE_URL}/workflow/start/${sessionId}`;
    },

    getResumeWorkflowUrl: (sessionId: string) => {
        return `${API_BASE_URL}/workflow/resume/${sessionId}`;
    }
};
