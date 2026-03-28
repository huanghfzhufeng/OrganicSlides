import React, { useEffect, useMemo, useState } from 'react';
import { Check, Loader2, RefreshCcw, Save, Sparkles } from 'lucide-react';
import BlobButton from './BlobButton';
import { api, type SlideReviewResponse } from '../api/client';

interface CollaborativeReviewPanelProps {
    sessionId: string;
    initialReview?: SlideReviewResponse | null;
    onApproved: () => void;
}

function toTextareaValue(items: string[]) {
    return (items ?? []).join('\n');
}

const CollaborativeReviewPanel: React.FC<CollaborativeReviewPanelProps> = ({
    sessionId,
    initialReview,
    onApproved,
}) => {
    const [review, setReview] = useState<SlideReviewResponse | null>(initialReview ?? null);
    const [selectedPage, setSelectedPage] = useState<number>(initialReview?.slides[0]?.page_number ?? 1);
    const [isLoading, setIsLoading] = useState(!initialReview);
    const [isSaving, setIsSaving] = useState(false);
    const [isAccepting, setIsAccepting] = useState(false);
    const [isRegenerating, setIsRegenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [draftTitle, setDraftTitle] = useState('');
    const [draftBullets, setDraftBullets] = useState('');
    const [draftSpeakerNotes, setDraftSpeakerNotes] = useState('');
    const [draftImagePrompt, setDraftImagePrompt] = useState('');
    const [draftFeedback, setDraftFeedback] = useState('');

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            if (initialReview) {
                setReview(initialReview);
                setIsLoading(false);
                return;
            }
            try {
                const next = await api.getSlideReview(sessionId);
                if (!cancelled) {
                    setReview(next);
                    setSelectedPage(next.slides[0]?.page_number ?? 1);
                }
            } catch (err: any) {
                if (!cancelled) {
                    setError(err.message ?? '加载逐页审阅数据失败');
                }
            } finally {
                if (!cancelled) {
                    setIsLoading(false);
                }
            }
        };
        load();
        return () => {
            cancelled = true;
        };
    }, [sessionId, initialReview]);

    const selectedSlide = useMemo(
        () => review?.slides.find((item) => item.page_number === selectedPage) ?? null,
        [review, selectedPage],
    );

    useEffect(() => {
        if (!selectedSlide) return;
        setDraftTitle(selectedSlide.title ?? '');
        setDraftBullets(toTextareaValue(selectedSlide.bullet_points ?? []));
        setDraftSpeakerNotes(selectedSlide.speaker_notes ?? '');
        setDraftImagePrompt(selectedSlide.image_prompt ?? '');
        setDraftFeedback(selectedSlide.feedback ?? '');
    }, [selectedSlide]);

    const acceptedCount = review?.slides.filter((item) => item.accepted).length ?? 0;
    const totalCount = review?.slides.length ?? 0;
    const allAccepted = !!review?.approved;

    const handleRefresh = async () => {
        const next = await api.getSlideReview(sessionId);
        setReview(next);
    };

    const handleSave = async () => {
        if (!selectedSlide) return;
        try {
            setIsSaving(true);
            setError(null);
            const bulletPoints = draftBullets
                .split('\n')
                .map((item) => item.trim())
                .filter(Boolean)
                .slice(0, 4);
            const next = await api.updateSlideReview(
                sessionId,
                selectedSlide.page_number,
                {
                    title: draftTitle,
                    content: {
                        bullet_points: bulletPoints,
                    },
                    speaker_notes: draftSpeakerNotes,
                    image_prompt: draftImagePrompt || null,
                },
                {
                    image_prompt: draftImagePrompt || null,
                },
                draftFeedback,
            );
            setReview(next);
        } catch (err: any) {
            setError(err.message ?? '保存修改失败');
        } finally {
            setIsSaving(false);
        }
    };

    const handleAccept = async () => {
        if (!selectedSlide) return;
        try {
            setIsAccepting(true);
            setError(null);
            const next = await api.acceptSlideReview(sessionId, selectedSlide.page_number);
            setReview(next);
        } catch (err: any) {
            setError(err.message ?? '接受页面失败');
        } finally {
            setIsAccepting(false);
        }
    };

    const handleRegenerate = async () => {
        if (!selectedSlide) return;
        try {
            setIsRegenerating(true);
            setError(null);
            const next = await api.regenerateSlideReview(sessionId, selectedSlide.page_number);
            setReview(next);
        } catch (err: any) {
            setError(err.message ?? '重生成失败');
        } finally {
            setIsRegenerating(false);
        }
    };

    if (isLoading) {
        return (
            <div className="rounded-[28px] border border-[#DED8CF] bg-white/80 p-8 text-center shadow-sm">
                <Loader2 className="mx-auto mb-3 animate-spin text-[#5D7052]" size={24} />
                <p className="text-[#78786C]">正在准备逐页审阅工作台...</p>
            </div>
        );
    }

    if (!review || !selectedSlide) {
        return (
            <div className="rounded-[28px] border border-red-200 bg-red-50 p-6 text-center text-red-600">
                逐页审阅数据不可用，请重新生成。
            </div>
        );
    }

    return (
        <div className="rounded-[30px] border border-[#DED8CF] bg-white/80 p-5 shadow-[0_28px_60px_-50px_rgba(93,112,82,0.75)] backdrop-blur-sm">
            <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-[#A38B74]">
                        Collaborative Review
                    </p>
                    <h3 className="mt-1 font-fraunces text-2xl text-[#2C2C24]">
                        逐页确认内容，再进入最终渲染
                    </h3>
                    <p className="mt-2 text-sm text-[#78786C]">
                        当前已接受 {acceptedCount} / {totalCount} 页。你可以逐页修改文案、接受结果，或者只重生成某一页。
                    </p>
                </div>
                <div className="inline-flex items-center gap-2 rounded-full border border-[#DED8CF] bg-[#F9F5EE] px-4 py-2 text-sm font-bold text-[#5D7052]">
                    <Sparkles size={15} />
                    <span>{allAccepted ? '全部通过，可以继续渲染' : '还有页面待确认'}</span>
                </div>
            </div>

            {error && (
                <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                    {error}
                </div>
            )}

            <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
                <div className="rounded-[24px] border border-[#E7DFD5] bg-[#FCF9F4] p-4">
                    <div className="mb-3 flex items-center justify-between">
                        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#A38B74]">
                            页面列表
                        </p>
                        <button
                            type="button"
                            onClick={handleRefresh}
                            className="text-xs font-bold text-[#5D7052] hover:text-[#3F5A3C]"
                        >
                            刷新
                        </button>
                    </div>

                    <div className="space-y-2">
                        {review.slides.map((slide) => (
                            <button
                                key={slide.page_number}
                                type="button"
                                onClick={() => setSelectedPage(slide.page_number)}
                                className={`w-full rounded-[20px] border px-4 py-3 text-left transition-all ${
                                    slide.page_number === selectedPage
                                        ? 'border-[#5D7052] bg-[#EEF3EB]'
                                        : 'border-[#DED8CF] bg-white hover:border-[#C9B9A6]'
                                }`}
                            >
                                <div className="mb-2 flex items-center justify-between gap-2">
                                    <span className="font-bold text-[#2C2C24]">第 {slide.page_number} 页</span>
                                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                                        slide.accepted
                                            ? 'bg-[#5D7052]/12 text-[#5D7052]'
                                            : slide.review_status === 'regenerated'
                                                ? 'bg-[#C18C5D]/12 text-[#C18C5D]'
                                                : 'bg-[#F3EEE6] text-[#AFA18F]'
                                    }`}>
                                        {slide.accepted ? '已接受' : slide.review_status}
                                    </span>
                                </div>
                                <p className="line-clamp-2 text-sm text-[#2C2C24]">{slide.title || '未命名页面'}</p>
                                <p className="mt-2 text-[11px] text-[#A38B74]">
                                    {slide.render_path} · 修订 {slide.revision_count} 次
                                </p>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="rounded-[24px] border border-[#E7DFD5] bg-[#FCF9F4] p-5">
                    <div className="mb-4 flex items-center justify-between gap-3">
                        <div>
                            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#A38B74]">
                                当前页
                            </p>
                            <h4 className="font-fraunces text-xl text-[#2C2C24]">
                                第 {selectedSlide.page_number} 页 · {selectedSlide.render_path}
                            </h4>
                        </div>
                        <div className="rounded-full bg-white px-3 py-1 text-xs font-bold text-[#78786C]">
                            {selectedSlide.visual_type} / {selectedSlide.layout_name}
                        </div>
                    </div>

                    <div className="space-y-4">
                        <div>
                            <label className="mb-2 block text-xs font-bold uppercase tracking-[0.18em] text-[#A38B74]">
                                标题
                            </label>
                            <input
                                value={draftTitle}
                                onChange={(e) => setDraftTitle(e.target.value)}
                                className="w-full rounded-2xl border border-[#DED8CF] bg-white px-4 py-3 text-[#2C2C24] focus:border-[#5D7052] focus:outline-none"
                            />
                        </div>

                        <div className="grid gap-4 lg:grid-cols-2">
                            <div>
                                <label className="mb-2 block text-xs font-bold uppercase tracking-[0.18em] text-[#A38B74]">
                                    要点
                                </label>
                                <textarea
                                    rows={6}
                                    value={draftBullets}
                                    onChange={(e) => setDraftBullets(e.target.value)}
                                    className="w-full rounded-2xl border border-[#DED8CF] bg-white px-4 py-3 text-[#2C2C24] focus:border-[#5D7052] focus:outline-none resize-none"
                                />
                            </div>
                            <div>
                                <label className="mb-2 block text-xs font-bold uppercase tracking-[0.18em] text-[#A38B74]">
                                    演讲备注
                                </label>
                                <textarea
                                    rows={6}
                                    value={draftSpeakerNotes}
                                    onChange={(e) => setDraftSpeakerNotes(e.target.value)}
                                    className="w-full rounded-2xl border border-[#DED8CF] bg-white px-4 py-3 text-[#2C2C24] focus:border-[#5D7052] focus:outline-none resize-none"
                                />
                            </div>
                        </div>

                        <div>
                            <label className="mb-2 block text-xs font-bold uppercase tracking-[0.18em] text-[#A38B74]">
                                Path B / 视觉提示词
                            </label>
                            <textarea
                                rows={4}
                                value={draftImagePrompt}
                                onChange={(e) => setDraftImagePrompt(e.target.value)}
                                className="w-full rounded-2xl border border-[#DED8CF] bg-white px-4 py-3 text-[#2C2C24] focus:border-[#5D7052] focus:outline-none resize-none"
                            />
                        </div>

                        <div>
                            <label className="mb-2 block text-xs font-bold uppercase tracking-[0.18em] text-[#A38B74]">
                                审阅意见
                            </label>
                            <textarea
                                rows={3}
                                value={draftFeedback}
                                onChange={(e) => setDraftFeedback(e.target.value)}
                                className="w-full rounded-2xl border border-[#DED8CF] bg-white px-4 py-3 text-[#2C2C24] focus:border-[#5D7052] focus:outline-none resize-none"
                            />
                        </div>
                    </div>

                    <div className="mt-5 flex flex-wrap gap-3">
                        <BlobButton onClick={handleSave} icon={isSaving ? Loader2 : Save} disabled={isSaving || isAccepting || isRegenerating}>
                            {isSaving ? '保存中...' : '保存修改'}
                        </BlobButton>
                        <BlobButton onClick={handleAccept} icon={isAccepting ? Loader2 : Check} disabled={isSaving || isAccepting || isRegenerating}>
                            {isAccepting ? '接受中...' : '接受本页'}
                        </BlobButton>
                        <BlobButton variant="ghost" onClick={handleRegenerate} icon={isRegenerating ? Loader2 : RefreshCcw} disabled={isSaving || isAccepting || isRegenerating}>
                            {isRegenerating ? '重生成中...' : '重生成本页'}
                        </BlobButton>
                        {allAccepted && (
                            <BlobButton onClick={onApproved} icon={Sparkles} disabled={isSaving || isAccepting || isRegenerating}>
                                全部通过，继续渲染
                            </BlobButton>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default CollaborativeReviewPanel;
