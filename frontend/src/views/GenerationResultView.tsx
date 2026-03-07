
import React, { useState, useEffect } from 'react';
import {
    Loader2, Download, Layout, Palette, Feather, Sparkles, PartyPopper,
    CheckCircle2, XCircle, Clock, FileImage
} from 'lucide-react';
import BlobButton from '../components/BlobButton';
import { api, type ProjectFailure } from '../api/client';
import { dandelionIcon } from '../assets/icons';
import Confetti from '../components/Confetti';
import { GenerationSkeleton } from '../components/Skeleton';
import ErrorMessage from '../components/ErrorMessage';

interface GenerationResultViewProps {
    sessionId: string;
    sessionAccessToken: string;
}

// ==================== Types ====================

type SlideStatus = 'pending' | 'rendering' | 'complete' | 'failed';

interface SlideProgress {
    slideIndex: number;
    title: string;
    renderPath: 'path_a' | 'path_b' | string;
    status: SlideStatus;
    thumbnailUrl?: string;
    error?: string;
}

// ==================== SlideCard ====================

const RENDER_PATH_LABEL: Record<string, string> = {
    path_a: 'Path A',
    path_b: 'Path B',
};

const RENDER_PATH_COLOR: Record<string, string> = {
    path_a: '#5D7052',
    path_b: '#C18C5D',
};

interface SlideCardProps {
    slide: SlideProgress;
}

const SlideCard: React.FC<SlideCardProps> = ({ slide }) => {
    const pathColor = RENDER_PATH_COLOR[slide.renderPath] ?? '#78786C';
    const pathLabel = RENDER_PATH_LABEL[slide.renderPath] ?? slide.renderPath;

    return (
        <div className="bg-white rounded-2xl border border-[#DED8CF] overflow-hidden shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-300">
            {/* Thumbnail or status area */}
            <div className="h-24 bg-[#F5F0EB] relative flex items-center justify-center">
                {slide.thumbnailUrl ? (
                    <img
                        src={slide.thumbnailUrl}
                        alt={`Slide ${slide.slideIndex + 1}`}
                        className="w-full h-full object-cover"
                    />
                ) : (
                    <div className="flex flex-col items-center gap-2">
                        {slide.status === 'rendering' && (
                            <Loader2 size={24} className="animate-spin text-[#C18C5D]" />
                        )}
                        {slide.status === 'pending' && (
                            <Clock size={24} className="text-[#DED8CF]" />
                        )}
                        {slide.status === 'complete' && !slide.thumbnailUrl && (
                            <CheckCircle2 size={24} className="text-[#5D7052]" />
                        )}
                        {slide.status === 'failed' && (
                            <XCircle size={24} className="text-red-400" />
                        )}
                        {slide.status === 'pending' && (
                            <FileImage size={16} className="text-[#DED8CF]" />
                        )}
                    </div>
                )}

                {/* Render path badge */}
                <span
                    className="absolute top-2 right-2 text-[9px] font-bold px-1.5 py-0.5 rounded text-white"
                    style={{ backgroundColor: pathColor }}
                >
                    {pathLabel}
                </span>
            </div>

            {/* Info */}
            <div className="p-3">
                <p className="text-xs font-bold text-[#2C2C24] truncate mb-1">
                    {slide.slideIndex + 1}. {slide.title || '幻灯片'}
                </p>
                <div className="flex items-center gap-1.5">
                    {slide.status === 'pending' && (
                        <span className="text-[9px] text-[#DED8CF] font-bold uppercase">等待中</span>
                    )}
                    {slide.status === 'rendering' && (
                        <span className="text-[9px] text-[#C18C5D] font-bold uppercase">渲染中...</span>
                    )}
                    {slide.status === 'complete' && (
                        <span className="text-[9px] text-[#5D7052] font-bold uppercase">完成</span>
                    )}
                    {slide.status === 'failed' && (
                        <span className="text-[9px] text-red-400 font-bold uppercase truncate">
                            {slide.error ? `失败: ${slide.error.slice(0, 30)}` : '失败'}
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
};

// ==================== GenerationResultView ====================

const GenerationResultView: React.FC<GenerationResultViewProps> = ({ sessionId, sessionAccessToken }) => {
    const [isDone, setIsDone] = useState(false);
    const [logs, setLogs] = useState<any[]>([]);
    const [slides, setSlides] = useState<SlideProgress[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [showConfetti, setShowConfetti] = useState(false);
    const [progress, setProgress] = useState(0);
    const [failure, setFailure] = useState<ProjectFailure | null>(null);
    const [attemptKey, setAttemptKey] = useState(0);
    const [isRetrying, setIsRetrying] = useState(false);

    useEffect(() => {
        setError(null);
        const eventSource = new EventSource(api.getResumeWorkflowUrl(sessionId, sessionAccessToken));

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'status') {
                setLogs(prev => [...prev, data]);
                setProgress(prev => Math.min(prev + 15, 90));
            } else if (data.type === 'render_progress') {
                // Per-slide rendering progress event from Task #8 backend
                // Expected shape: { type, slide_index, slide_title, render_path, status, thumbnail_url?, error? }
                const { slide_index, slide_title, render_path, status, thumbnail_url, error: slideError } = data;
                setSlides(prev => {
                    const existing = prev.find(s => s.slideIndex === slide_index);
                    const updated: SlideProgress = {
                        slideIndex: slide_index,
                        title: slide_title ?? existing?.title ?? '',
                        renderPath: render_path ?? existing?.renderPath ?? 'path_a',
                        status: (status as SlideStatus) ?? 'pending',
                        thumbnailUrl: thumbnail_url ?? existing?.thumbnailUrl,
                        error: slideError ?? existing?.error,
                    };
                    const next = existing
                        ? prev.map(s => s.slideIndex === slide_index ? updated : s)
                        : [...prev, updated].sort((a, b) => a.slideIndex - b.slideIndex);

                    // Derive progress from next state (no nested setState)
                    const completed = next.filter(s => s.status === 'complete' || s.status === 'failed').length;
                    if (next.length > 0) {
                        setProgress(Math.min(10 + Math.round((completed / next.length) * 85), 95));
                    }
                    return next;
                });
            } else if (data.type === 'slides_initialized') {
                // Backend sends initial slide list so we can show pending cards immediately
                // Expected: { type, slides: [{ index, title, render_path }] }
                if (Array.isArray(data.slides)) {
                    setSlides(data.slides.map((s: any) => ({
                        slideIndex: s.index ?? s.slide_index ?? 0,
                        title: s.title ?? '',
                        renderPath: s.render_path ?? 'path_a',
                        status: 'pending' as SlideStatus,
                    })));
                }
            } else if (data.type === 'complete') {
                setProgress(100);
                setSlides(prev => prev.map(s =>
                    s.status !== 'failed' ? { ...s, status: 'complete' } : s
                ));
                setIsDone(true);
                setShowConfetti(true);
                setFailure(null);
                eventSource.close();
            } else if (data.type === 'error') {
                const nextFailure: ProjectFailure = {
                    job_id: data.job_id ?? '',
                    session_id: sessionId,
                    trigger: data.retry_trigger ?? 'resume_workflow',
                    status: data.status ?? 'error',
                    current_agent: data.failure_stage ?? data.agent ?? 'workflow',
                    error_type: data.error_type ?? 'generation_failed',
                    failure_stage: data.failure_stage ?? data.agent ?? 'workflow',
                    message: data.user_message ?? data.message ?? '生成过程出错，请重试',
                    technical_message: data.message ?? '生成过程出错，请重试',
                    recoverable: data.recoverable ?? true,
                    retry_available: data.retry_available ?? true,
                    retry_trigger: data.retry_trigger ?? 'resume_workflow',
                    details: data.details ?? {},
                    failed_at: data.failed_at ?? null,
                };
                setFailure(nextFailure);
                setError(nextFailure.message);
                eventSource.close();
            }
        };

        eventSource.onerror = () => {
            setFailure(null);
            setError("连接中断，请检查网络后重试");
            eventSource.close();
        };

        return () => eventSource.close();
    }, [sessionId, sessionAccessToken, attemptKey]);

    const handleRetry = async () => {
        try {
            setIsRetrying(true);
            setIsDone(false);
            setShowConfetti(false);
            setLogs([]);
            setSlides([]);
            setProgress(0);
            setError(null);
            await api.retryProjectGeneration(
                sessionId,
                failure?.retry_trigger ?? 'resume_workflow',
                sessionAccessToken,
            );
            setFailure(null);
            setAttemptKey((value) => value + 1);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setIsRetrying(false);
        }
    };

    const completedCount = slides.filter(s => s.status === 'complete').length;
    const failedCount = slides.filter(s => s.status === 'failed').length;

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 h-full min-h-[500px] page-enter">
            <Confetti isActive={showConfetti} />

            {/* Left: Agent logs + progress */}
            <div className="lg:col-span-4 flex flex-col gap-6">
                <div className="bg-white/60 p-6 rounded-[24px] border border-[#DED8CF] shadow-sm flex-1 overflow-hidden flex flex-col">
                    <h3 className="font-fraunces text-xl mb-4 flex items-center gap-2">
                        {!isDone && !error ? (
                            <Loader2 className="animate-spin text-[#5D7052]" />
                        ) : error ? (
                            <span className="text-red-500">!</span>
                        ) : (
                            <PartyPopper className="text-[#C18C5D]" />
                        )}
                        {error ? "生成出错" : isDone ? "生成完毕" : "正在进行最终创作..."}
                    </h3>

                    {/* Overall progress bar */}
                    {!isDone && !error && (
                        <div className="w-full h-1.5 bg-[#DED8CF]/30 rounded-full overflow-hidden mb-4">
                            <div
                                className="h-full progress-bar rounded-full transition-all duration-500 ease-out"
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                    )}

                    {/* Slide completion summary */}
                    {slides.length > 0 && (
                        <div className="flex items-center gap-3 text-xs text-[#78786C] mb-4 font-nunito">
                            <span className="text-[#5D7052] font-bold">{completedCount} / {slides.length}</span>
                            <span>幻灯片已完成</span>
                            {failedCount > 0 && (
                                <span className="text-red-400 font-bold">{failedCount} 失败</span>
                            )}
                        </div>
                    )}

                    <div className="flex-1 overflow-y-auto space-y-4 font-nunito text-sm text-[#78786C] pr-2 no-scrollbar">
                        {error && (
                            <ErrorMessage
                                message={error}
                                title={failure ? "生成任务失败" : "连接异常"}
                                details={failure ? [
                                    `失败阶段：${failure.failure_stage}`,
                                    `错误类型：${failure.error_type}`,
                                    `技术信息：${failure.technical_message}`,
                                ] : []}
                                type={failure ? "error" : "network"}
                                retryLabel={isRetrying ? '重新排队中...' : failure ? '重新排队' : '重新连接'}
                                onRetry={
                                    failure
                                        ? (failure.retry_available ? handleRetry : undefined)
                                        : () => setAttemptKey((value) => value + 1)
                                }
                            />
                        )}
                        {logs.length === 0 && !error ? (
                            <GenerationSkeleton />
                        ) : (
                            logs.map((log, i) => (
                                <div key={i} className="flex items-start gap-3 animate-in fade-in slide-in-from-left-2">
                                    <div className={`mt-1 flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px]
                                        ${log.agent === 'writer' ? 'bg-[#5D7052]' : log.agent === 'visual' ? 'bg-[#C18C5D]' : 'bg-[#A85448]'}`}>
                                        {log.agent === 'writer' ? <Feather size={12} /> : log.agent === 'visual' ? <Palette size={12} /> : <Layout size={12} />}
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="font-bold uppercase text-[10px] tracking-widest text-[#2C2C24]/40">{log.agent}</span>
                                        <span>{log.message}</span>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {isDone && (
                    <a href={api.getDownloadUrl(sessionId, sessionAccessToken)} download>
                        <BlobButton variant="primary" icon={Download} className="w-full ripple-btn">
                            下载完整 .pptx
                        </BlobButton>
                    </a>
                )}
            </div>

            {/* Right: Per-slide progress OR completion view */}
            <div className="lg:col-span-8 flex flex-col gap-4">
                {slides.length > 0 ? (
                    <>
                        {/* Per-slide grid */}
                        <div className="flex-1 bg-[#FEFEFA] border border-[#DED8CF] rounded-[24px] p-6 overflow-y-auto">
                            <h4 className="font-fraunces text-base text-[#2C2C24] mb-4 flex items-center gap-2">
                                <span className="w-1.5 h-4 rounded-full bg-[#5D7052] inline-block" />
                                逐页渲染进度
                            </h4>
                            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                                {slides.map((slide) => (
                                    <SlideCard key={slide.slideIndex} slide={slide} />
                                ))}
                            </div>
                        </div>

                        {isDone && (
                            <div className="bg-[#5D7052]/5 border border-[#5D7052]/20 rounded-2xl p-6 text-center">
                                <img src={dandelionIcon} alt="完成" className="w-16 h-16 mx-auto mb-3 drop-shadow breathe" />
                                <h2 className="font-fraunces text-2xl text-[#2C2C24] mb-1">创作完成！</h2>
                                <p className="text-sm text-[#78786C]">已生成 {slides.length} 张幻灯片，点击左侧按钮下载</p>
                            </div>
                        )}
                    </>
                ) : (
                    /* No slide progress data yet — show legacy preview pane */
                    <div className={`flex-1 bg-[#FEFEFA] border border-[#DED8CF] rounded-[24px] shadow-lg relative overflow-hidden flex items-center justify-center p-12 transition-all duration-700
                        ${isDone ? 'border-[#5D7052]/30' : ''}`}>
                        <div className="text-center z-10 animate-in fade-in duration-1000">
                            {isDone ? (
                                <>
                                    <img src={dandelionIcon} alt="完成" className="w-36 h-36 mx-auto mb-6 drop-shadow-lg breathe" />
                                    <h2 className="font-fraunces text-4xl text-[#2C2C24] mb-2">创作完成！</h2>
                                    <p className="mt-4 text-[#78786C] max-w-sm mx-auto">您的专属演示文稿已生成完毕，点击下方按钮下载</p>
                                </>
                            ) : (
                                <>
                                    <span className="text-xs font-bold tracking-widest text-[#5D7052] uppercase mb-4 block">RENDER ENGINE</span>
                                    <h2 className="font-fraunces text-4xl text-[#2C2C24]">您的演示文稿即将就绪</h2>
                                    <p className="mt-4 text-[#78786C] max-w-sm mx-auto">正在将 AI 生成的内容与视觉方案合成为标准的 Microsoft PowerPoint 格式</p>
                                </>
                            )}
                        </div>

                        {/* Blobs */}
                        <div className={`absolute top-[-50%] right-[-20%] w-[400px] h-[400px] rounded-full mix-blend-multiply blur-[80px] opacity-40 animate-pulse transition-colors duration-1000
                            ${isDone ? 'bg-[#5D7052]' : 'bg-[#E6DCCD]'}`} />
                        <div className={`absolute bottom-[-50%] left-[-20%] w-[300px] h-[300px] rounded-full mix-blend-multiply blur-[60px] opacity-20 animate-pulse transition-colors duration-1000
                            ${isDone ? 'bg-[#C18C5D]' : 'bg-[#5D7052]'}`} style={{ animationDelay: '1s' }} />

                        {!isDone && !error && (
                            <div className="absolute inset-0 bg-white/50 backdrop-blur-sm flex flex-col items-center justify-center z-20">
                                <Loader2 className="animate-spin text-[#5D7052] mb-4" size={48} />
                                <span className="bg-white px-4 py-2 rounded-full shadow-sm text-sm text-[#78786C]">渲染引擎正在生成原生 PPT 对象...</span>
                            </div>
                        )}
                    </div>
                )}

                {/* Info footer */}
                <div className="bg-white/40 p-4 rounded-xl text-xs text-[#78786C] flex items-center justify-center gap-2">
                    <Sparkles size={14} className="text-[#C18C5D]" />
                    {isDone ? "恭喜！您可以直接在 PowerPoint 中打开并进行二次修改。" : "提示：生成完毕后，您可以直接下载并在 PowerPoint 中进行二次修改。"}
                </div>
            </div>
        </div>
    );
};

export default GenerationResultView;
