
import React, { useState, useEffect } from 'react';
import {
    Download, Eye, Clock, CheckCircle2, Loader2,
    AlertCircle, RefreshCw, Plus, FileText
} from 'lucide-react';
import BlobButton from '../components/BlobButton';
import SlidePreviewModal from './SlidePreviewModal';
import { api, type ProjectListItem } from '../api/client';
import { forestGlobeIcon } from '../assets/icons';

interface HistoryViewProps {
    onNewProject: () => void;
}

// ==================== Status helpers ====================

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ElementType }> = {
    completed: { label: '已完成', color: '#5D7052', icon: CheckCircle2 },
    created: { label: '已创建', color: '#C18C5D', icon: Clock },
    outline_approved: { label: '生成中', color: '#C18C5D', icon: Loader2 },
    error: { label: '失败', color: '#A85448', icon: AlertCircle },
};

function getStatusConfig(status: string) {
    return STATUS_CONFIG[status] ?? { label: status, color: '#78786C', icon: Clock };
}

function formatDate(isoDate: string): string {
    const d = new Date(isoDate);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return '今天';
    if (diffDays === 1) return '昨天';
    if (diffDays < 7) return `${diffDays} 天前`;
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', year: 'numeric' });
}

// ==================== ProjectCard ====================

interface ProjectCardProps {
    project: ProjectListItem;
    onPreview: (id: string) => void;
}

const ProjectCard: React.FC<ProjectCardProps> = ({ project, onPreview }) => {
    const statusCfg = getStatusConfig(project.status);
    const StatusIcon = statusCfg.icon;

    return (
        <div className="bg-white/70 backdrop-blur-sm border border-[#DED8CF] rounded-2xl p-5 hover:shadow-md transition-all duration-300 group">
            <div className="flex items-start justify-between mb-3">
                {/* Status badge */}
                <span
                    className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full"
                    style={{ backgroundColor: `${statusCfg.color}15`, color: statusCfg.color }}
                >
                    <StatusIcon size={12} className={project.status === 'outline_approved' ? 'animate-spin' : ''} />
                    {statusCfg.label}
                </span>

                {/* Date */}
                <span className="text-[11px] text-[#DED8CF] font-bold">
                    {formatDate(project.created_at)}
                </span>
            </div>

            {/* Title / Intent */}
            <h3 className="font-fraunces text-base text-[#2C2C24] mb-2 line-clamp-2 leading-snug">
                {project.user_intent}
            </h3>

            {/* Theme */}
            <p className="text-xs text-[#78786C] mb-4 flex items-center gap-1.5">
                <FileText size={12} />
                {project.theme || 'organic'}
            </p>

            {/* Actions */}
            <div className="flex items-center gap-2">
                <button
                    onClick={() => onPreview(project.id)}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl text-xs font-bold
                        bg-[#5D7052]/5 text-[#5D7052] hover:bg-[#5D7052]/15 transition-colors"
                >
                    <Eye size={14} />
                    预览
                </button>

                {project.has_pptx && (
                    <a
                        href={api.getDownloadUrl(project.id)}
                        download
                        className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl text-xs font-bold
                            bg-[#C18C5D]/5 text-[#C18C5D] hover:bg-[#C18C5D]/15 transition-colors"
                    >
                        <Download size={14} />
                        下载
                    </a>
                )}
            </div>
        </div>
    );
};

// ==================== HistoryView ====================

const HistoryView: React.FC<HistoryViewProps> = ({ onNewProject }) => {
    const [projects, setProjects] = useState<ProjectListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [previewId, setPreviewId] = useState<string | null>(null);

    const fetchProjects = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await api.listProjects();
            setProjects(data.projects);
        } catch {
            setError('加载项目失败，请重试');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchProjects();
    }, []);

    return (
        <div className="page-enter max-w-5xl mx-auto">
            {/* Preview modal */}
            {previewId && (
                <SlidePreviewModal
                    sessionId={previewId}
                    onClose={() => setPreviewId(null)}
                />
            )}

            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                    <img src={forestGlobeIcon} alt="" className="w-12 h-12 drop-shadow" />
                    <div>
                        <h2 className="font-fraunces text-2xl text-[#2C2C24]">我的项目</h2>
                        <p className="text-sm text-[#78786C]">
                            {projects.length > 0 ? `共 ${projects.length} 个项目` : '暂无项目'}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={fetchProjects}
                        className="w-9 h-9 rounded-full bg-white border border-[#DED8CF] flex items-center justify-center hover:bg-[#5D7052]/5 transition-colors"
                        title="刷新"
                    >
                        <RefreshCw size={14} className={`text-[#78786C] ${loading ? 'animate-spin' : ''}`} />
                    </button>
                    <BlobButton onClick={onNewProject} icon={Plus}>
                        新建
                    </BlobButton>
                </div>
            </div>

            {/* Loading state */}
            {loading && projects.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20 gap-4">
                    <Loader2 size={32} className="animate-spin text-[#5D7052]" />
                    <span className="text-sm text-[#78786C]">加载中...</span>
                </div>
            )}

            {/* Error state */}
            {error && (
                <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-xl text-center text-sm">
                    {error}
                </div>
            )}

            {/* Empty state */}
            {!loading && !error && projects.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20 gap-4">
                    <img src={forestGlobeIcon} alt="" className="w-24 h-24 opacity-30" />
                    <h3 className="font-fraunces text-xl text-[#DED8CF]">暂无项目</h3>
                    <p className="text-sm text-[#DED8CF]">创建您的第一个演示文稿</p>
                    <BlobButton onClick={onNewProject} icon={Plus}>
                        创建项目
                    </BlobButton>
                </div>
            )}

            {/* Project grid */}
            {projects.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {projects.map((project) => (
                        <ProjectCard
                            key={project.id}
                            project={project}
                            onPreview={setPreviewId}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

export default HistoryView;
