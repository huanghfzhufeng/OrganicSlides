import React, { useEffect, useMemo, useState } from 'react';
import { Check, Loader2, AlertCircle } from 'lucide-react';
import BlobButton from '../components/BlobButton';
import { api, type SlideBlueprintItem } from '../api/client';

interface BlueprintEditorProps {
    sessionId: string;
    initialBlueprint: SlideBlueprintItem[];
    onNext: (updatedBlueprint: SlideBlueprintItem[]) => void;
}

const getErrorMessage = (error: unknown, fallback: string) =>
    error instanceof Error && error.message ? error.message : fallback;

const fetchBlueprint = async (sessionId: string, preferExisting = true) => {
    if (preferExisting) {
        const existing = await api.getBlueprint(sessionId);
        if ((existing.slide_blueprint ?? []).length > 0) {
            return existing.slide_blueprint;
        }
    }

    const generated = await api.generateBlueprint(sessionId);
    return generated.slide_blueprint ?? [];
};

const BlueprintEditor: React.FC<BlueprintEditorProps> = ({ sessionId, initialBlueprint, onNext }) => {
    const [blueprint, setBlueprint] = useState<SlideBlueprintItem[]>(initialBlueprint);
    const [isLoading, setIsLoading] = useState(initialBlueprint.length === 0);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadBlueprint = async (preferExisting = true) => {
        setIsLoading(true);
        setError(null);

        try {
            setBlueprint(await fetchBlueprint(sessionId, preferExisting));
        } catch (err: unknown) {
            setError(getErrorMessage(err, '页级策划生成失败'));
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        let cancelled = false;

        const initializeBlueprint = async () => {
            if (initialBlueprint.length > 0) {
                setBlueprint(initialBlueprint);
                setIsLoading(false);
                return;
            }

            setIsLoading(true);
            setError(null);

            try {
                const generated = await fetchBlueprint(sessionId);
                if (!cancelled) {
                    setBlueprint(generated);
                }
            } catch (err: unknown) {
                if (!cancelled) {
                    setError(getErrorMessage(err, '页级策划生成失败'));
                }
            } finally {
                if (!cancelled) {
                    setIsLoading(false);
                }
            }
        };

        void initializeBlueprint();
        return () => {
            cancelled = true;
        };
    }, [initialBlueprint, sessionId]);

    const groupedCount = useMemo(
        () => new Set(blueprint.map((item) => item.section_id)).size,
        [blueprint],
    );

    const handleFieldChange = (index: number, patch: Partial<SlideBlueprintItem>) => {
        setBlueprint((current) =>
            current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
        );
    };

    const handlePointsChange = (index: number, value: string) => {
        const points = value
            .split(/[\n,，]/)
            .map((item) => item.trim())
            .filter(Boolean)
            .slice(0, 4);
        handleFieldChange(index, { key_points: points });
    };

    const handleNext = async () => {
        try {
            setIsSubmitting(true);
            setError(null);
            await api.updateBlueprint(sessionId, blueprint);
            onNext(blueprint);
        } catch (err: unknown) {
            setError(getErrorMessage(err, '页级策划确认失败'));
        } finally {
            setIsSubmitting(false);
        }
    };

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto text-center page-enter">
                <h2 className="font-fraunces text-3xl text-[#2C2C24] mb-2">策划师正在展开逐页蓝图</h2>
                <p className="text-[#78786C] mb-10">系统会把章节级大纲拆成真正的页级结构，再进入风格选择。</p>
                <div className="inline-flex items-center gap-3 rounded-full bg-white/80 border border-[#DED8CF] px-6 py-3 shadow-sm">
                    <Loader2 className="animate-spin text-[#5D7052]" size={20} />
                    <span className="text-[#5D7052] font-bold">正在生成 Slide Blueprint...</span>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-5xl mx-auto page-enter">
            <div className="text-center mb-8">
                <h2 className="font-fraunces text-3xl text-[#2C2C24]">页级策划蓝图</h2>
                <p className="text-[#78786C]">
                    现在确认的不是“章节顺序”，而是“每一页到底讲什么”。当前共 {blueprint.length} 页，来自 {groupedCount} 个章节。
                </p>
            </div>

            {error && (
                <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-4 text-red-600">
                    <div className="mb-3 flex items-center justify-center gap-2">
                        <AlertCircle size={18} />
                        <span>{error}</span>
                    </div>
                    <div className="flex justify-center">
                        <BlobButton onClick={() => loadBlueprint(false)} icon={Loader2} disabled={isLoading}>
                            重新生成页级蓝图
                        </BlobButton>
                    </div>
                </div>
            )}

            <div className="space-y-4 mb-8">
                {blueprint.map((item, index) => (
                    <div key={item.id} className="rounded-[28px] border border-[#DED8CF] bg-white/80 p-6 shadow-sm">
                        <div className="flex flex-wrap items-center gap-2 mb-4">
                            <span className="rounded-full bg-[#5D7052]/10 px-3 py-1 text-xs font-bold text-[#5D7052]">
                                第 {item.page_number} 页
                            </span>
                            <span className="rounded-full bg-[#F0EBE5] px-3 py-1 text-xs font-bold text-[#78786C]">
                                章节：{item.section_title}
                            </span>
                            <span className="rounded-full bg-[#F8F3ED] px-3 py-1 text-xs font-bold text-[#A97C56]">
                                {item.visual_type} / {item.path_hint}
                            </span>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-xs font-bold uppercase tracking-[0.18em] text-[#A38B74] mb-2">页标题</label>
                                <input
                                    value={item.title}
                                    onChange={(e) => handleFieldChange(index, { title: e.target.value })}
                                    className="w-full rounded-2xl border border-[#DED8CF] bg-[#FFFCF7] px-4 py-3 text-[#2C2C24] focus:outline-none focus:border-[#5D7052]"
                                />
                            </div>

                            <div className="grid gap-4 md:grid-cols-2">
                                <div>
                                    <label className="block text-xs font-bold uppercase tracking-[0.18em] text-[#A38B74] mb-2">页面目标</label>
                                    <textarea
                                        value={item.goal}
                                        onChange={(e) => handleFieldChange(index, { goal: e.target.value })}
                                        rows={3}
                                        className="w-full rounded-2xl border border-[#DED8CF] bg-[#FFFCF7] px-4 py-3 text-[#2C2C24] focus:outline-none focus:border-[#5D7052] resize-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold uppercase tracking-[0.18em] text-[#A38B74] mb-2">内容摘要</label>
                                    <textarea
                                        value={item.content_brief}
                                        onChange={(e) => handleFieldChange(index, { content_brief: e.target.value })}
                                        rows={3}
                                        className="w-full rounded-2xl border border-[#DED8CF] bg-[#FFFCF7] px-4 py-3 text-[#2C2C24] focus:outline-none focus:border-[#5D7052] resize-none"
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-bold uppercase tracking-[0.18em] text-[#A38B74] mb-2">要点种子（逗号或换行分隔）</label>
                                <textarea
                                    value={item.key_points.join('，')}
                                    onChange={(e) => handlePointsChange(index, e.target.value)}
                                    rows={2}
                                    className="w-full rounded-2xl border border-[#DED8CF] bg-[#FFFCF7] px-4 py-3 text-[#2C2C24] focus:outline-none focus:border-[#5D7052] resize-none"
                                />
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            <div className="flex justify-center">
                <BlobButton onClick={handleNext} icon={isSubmitting ? Loader2 : Check} disabled={isSubmitting || blueprint.length === 0}>
                    {isSubmitting ? '正在确认页级策划...' : '确认页级策划并继续'}
                </BlobButton>
            </div>
        </div>
    );
};

export default BlueprintEditor;
