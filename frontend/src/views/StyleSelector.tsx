
import React, { useState, useEffect, useCallback } from 'react';
import { Sparkles, Check, X, ZoomIn, Loader2, AlertCircle, Star } from 'lucide-react';
import BlobButton from '../components/BlobButton';
import { api, type Style } from '../api/client';

interface StyleSelectorProps {
    userIntent: string;
    onNext: (styleId: string) => void;
}

// ==================== Tier helpers ====================

type TierKey = '1' | '2' | '3' | 'editorial';

const TIER_LABELS: Record<TierKey, string> = {
    '1': 'Tier 1 — 推荐',
    '2': 'Tier 2 — 进阶',
    '3': 'Tier 3 — 特色',
    'editorial': 'Editorial — 专业出版',
};

const RENDER_BADGE: Record<string, { label: string; color: string }> = {
    path_a: { label: 'Path A', color: '#5D7052' },
    path_b: { label: 'Path B', color: '#C18C5D' },
};

function getTierKey(tier: number | string): TierKey {
    return String(tier) as TierKey;
}

function groupByTier(styles: Style[]): Record<TierKey, Style[]> {
    return styles.reduce<Record<TierKey, Style[]>>(
        (acc, style) => {
            const key = getTierKey(style.tier);
            return { ...acc, [key]: [...(acc[key] ?? []), style] };
        },
        { '1': [], '2': [], '3': [], 'editorial': [] }
    );
}

// ==================== StyleCard ====================

interface StyleCardProps {
    style: Style;
    isSelected: boolean;
    isRecommended: boolean;
    onSelect: (id: string) => void;
    onPreview: (style: Style) => void;
}

const StyleCard: React.FC<StyleCardProps> = ({ style, isSelected, isRecommended, onSelect, onPreview }) => {
    const renderPaths = style.render_paths;
    const hasBoth = renderPaths.includes('path_a') && renderPaths.includes('path_b');

    return (
        <div
            onClick={() => onSelect(style.id)}
            className={`cursor-pointer rounded-[24px] overflow-hidden border-2 transition-all duration-300 relative group
                ${isSelected
                    ? 'border-[#5D7052] shadow-2xl scale-[1.02]'
                    : 'border-[#DED8CF] shadow-md hover:border-[#C18C5D]/50 hover:scale-[1.01]'
                }`}
        >
            {/* Recommended badge */}
            {isRecommended && (
                <div className="absolute top-3 left-3 z-10 flex items-center gap-1 bg-[#C18C5D] text-white text-[10px] font-bold px-2 py-1 rounded-full shadow">
                    <Star size={10} fill="currentColor" /> 智能推荐
                </div>
            )}

            {/* Selected badge */}
            {isSelected && (
                <div className="absolute top-3 right-3 z-10 bg-[#5D7052] text-white p-1.5 rounded-full shadow-lg">
                    <Check size={14} />
                </div>
            )}

            {/* Preview image */}
            <div className="relative h-44 bg-[#F5F0EB] overflow-hidden">
                <img
                    src={api.getStyleSample(style.id)}
                    alt={style.name_en}
                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                    onError={(e) => {
                        const target = e.target as HTMLImageElement;
                        target.style.display = 'none';
                        const parent = target.parentElement;
                        if (parent) {
                            parent.style.background = style.colors
                                ? `linear-gradient(135deg, ${style.colors.background}, ${style.colors.primary})`
                                : '#F5F0EB';
                        }
                    }}
                />
                {/* Zoom button */}
                <button
                    onClick={(e) => { e.stopPropagation(); onPreview(style); }}
                    className="absolute bottom-2 right-2 bg-white/80 backdrop-blur-sm p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:bg-white"
                >
                    <ZoomIn size={14} className="text-[#2C2C24]" />
                </button>
            </div>

            {/* Info */}
            <div className="bg-white p-4">
                {/* Name + color palette */}
                <div className="flex items-start justify-between gap-2 mb-1">
                    <div>
                        <h3 className="font-fraunces font-bold text-[#2C2C24] text-sm leading-tight">{style.name_zh}</h3>
                        <p className="text-[#78786C] text-[11px]">{style.name_en}</p>
                    </div>
                    {style.colors && (
                        <div className="flex gap-1 flex-shrink-0 pt-0.5">
                            {[style.colors.primary, style.colors.secondary, style.colors.accent].map((c, i) => (
                                <div key={i} className="w-3 h-3 rounded-full border border-black/10" style={{ backgroundColor: c }} />
                            ))}
                        </div>
                    )}
                </div>

                {/* Use cases */}
                <div className="flex flex-wrap gap-1 mb-2">
                    {style.use_cases.slice(0, 3).map((uc, i) => (
                        <span key={i} className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-[#F0EBE5] text-[#78786C]">
                            {uc}
                        </span>
                    ))}
                </div>

                {/* Render path badges */}
                <div className="flex gap-1">
                    {hasBoth ? (
                        <span className="text-[9px] font-bold px-2 py-0.5 rounded-full text-white" style={{ backgroundColor: '#A85448' }}>
                            Path A + B
                        </span>
                    ) : (
                        renderPaths.map((rp) => {
                            const badge = RENDER_BADGE[rp];
                            return badge ? (
                                <span key={rp} className="text-[9px] font-bold px-2 py-0.5 rounded-full text-white" style={{ backgroundColor: badge.color }}>
                                    {badge.label}
                                </span>
                            ) : null;
                        })
                    )}
                </div>
            </div>
        </div>
    );
};

// ==================== Lightbox ====================

interface LightboxProps {
    style: Style;
    onClose: () => void;
}

const Lightbox: React.FC<LightboxProps> = ({ style, onClose }) => (
    <div
        className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
        onClick={onClose}
    >
        <div
            className="bg-white rounded-[24px] overflow-hidden max-w-2xl w-full shadow-2xl"
            onClick={(e) => e.stopPropagation()}
        >
            <div className="relative">
                <img
                    src={api.getStyleSample(style.id)}
                    alt={style.name_en}
                    className="w-full object-contain max-h-[60vh]"
                />
                <button
                    onClick={onClose}
                    className="absolute top-3 right-3 bg-white/90 rounded-full p-2 shadow hover:bg-white"
                >
                    <X size={18} className="text-[#2C2C24]" />
                </button>
            </div>
            <div className="p-5">
                <h3 className="font-fraunces text-xl text-[#2C2C24] mb-1">{style.name_zh}</h3>
                <p className="text-[#78786C] text-sm mb-3">{style.description ?? style.name_en}</p>
                <div className="flex flex-wrap gap-1.5">
                    {style.use_cases.map((uc, i) => (
                        <span key={i} className="text-xs font-bold px-2 py-0.5 rounded-full bg-[#F0EBE5] text-[#78786C]">{uc}</span>
                    ))}
                </div>
            </div>
        </div>
    </div>
);

// ==================== TierSection ====================

interface TierSectionProps {
    tierKey: TierKey;
    styles: Style[];
    selected: string;
    recommendedIds: string[];
    onSelect: (id: string) => void;
    onPreview: (style: Style) => void;
}

const TierSection: React.FC<TierSectionProps> = ({ tierKey, styles, selected, recommendedIds, onSelect, onPreview }) => {
    if (styles.length === 0) return null;
    return (
        <section className="mb-10">
            <h3 className="font-fraunces text-lg text-[#2C2C24] mb-4 flex items-center gap-2">
                <span className="w-1.5 h-5 rounded-full bg-[#5D7052] inline-block" />
                {TIER_LABELS[tierKey]}
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {styles.map((style) => (
                    <StyleCard
                        key={style.id}
                        style={style}
                        isSelected={selected === style.id}
                        isRecommended={recommendedIds.includes(style.id)}
                        onSelect={onSelect}
                        onPreview={onPreview}
                    />
                ))}
            </div>
        </section>
    );
};

// ==================== StyleSelector ====================

const TIER_ORDER: TierKey[] = ['1', '2', '3', 'editorial'];

const StyleSelector: React.FC<StyleSelectorProps> = ({ userIntent, onNext }) => {
    const [styles, setStyles] = useState<Style[]>([]);
    const [recommendedIds, setRecommendedIds] = useState<string[]>([]);
    const [selected, setSelected] = useState<string>('');
    const [previewStyle, setPreviewStyle] = useState<Style | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        const fetchData = async () => {
            try {
                setIsLoading(true);
                setError(null);

                const [allStyles, recs] = await Promise.all([
                    api.getStyles(),
                    userIntent ? api.getStyleRecommendations(userIntent).catch(() => []) : Promise.resolve([]),
                ]);

                if (cancelled) return;

                setStyles(allStyles);
                const topRecs = recs.slice(0, 3);
                setRecommendedIds(topRecs);

                // Default selection: first recommended or first Tier 1
                const defaultId = topRecs[0]
                    ?? allStyles.find((s) => getTierKey(s.tier) === '1')?.id
                    ?? allStyles[0]?.id
                    ?? '';
                setSelected(defaultId);
            } catch (err: unknown) {
                if (!cancelled) {
                    setError(err instanceof Error && err.message ? err.message : 'Failed to load styles');
                }
            } finally {
                if (!cancelled) setIsLoading(false);
            }
        };

        fetchData();
        return () => { cancelled = true; };
    }, [userIntent]);

    const handleSelect = useCallback((id: string) => setSelected(id), []);
    const handlePreview = useCallback((style: Style) => setPreviewStyle(style), []);
    const handleClosePreview = useCallback(() => setPreviewStyle(null), []);
    const handleNext = useCallback(() => { if (selected) onNext(selected); }, [selected, onNext]);

    const grouped = groupByTier(styles);
    const recommendedStyles = recommendedIds
        .map((id) => styles.find((s) => s.id === id))
        .filter((s): s is Style => Boolean(s));
    const selectedStyle = styles.find((s) => s.id === selected);

    if (isLoading) {
        return (
            <div className="max-w-5xl mx-auto text-center page-enter">
                <h2 className="font-fraunces text-3xl text-[#2C2C24] mb-2">选择视觉风格</h2>
                <p className="text-[#78786C] mb-12">正在加载风格库...</p>
                <div className="flex justify-center">
                    <Loader2 className="animate-spin text-[#5D7052]" size={40} />
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="max-w-5xl mx-auto text-center page-enter">
                <h2 className="font-fraunces text-3xl text-[#2C2C24] mb-2">选择视觉风格</h2>
                <div className="flex items-center justify-center gap-2 text-red-500 mt-8">
                    <AlertCircle size={20} />
                    <span>{error}</span>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto page-enter">
            <div className="text-center mb-10">
                <h2 className="font-fraunces text-3xl text-[#2C2C24] mb-2">选择视觉风格</h2>
                <p className="text-[#78786C]">为您的演示文稿选择最适合的视觉语言，共 {styles.length} 种风格</p>
            </div>

            {/* Smart Recommendations */}
            {recommendedStyles.length > 0 && (
                <section className="mb-10">
                    <h3 className="font-fraunces text-lg text-[#2C2C24] mb-4 flex items-center gap-2">
                        <Star size={18} className="text-[#C18C5D]" fill="#C18C5D" />
                        智能推荐 — 最适合您的主题
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {recommendedStyles.map((style) => (
                            <StyleCard
                                key={style.id}
                                style={style}
                                isSelected={selected === style.id}
                                isRecommended={true}
                                onSelect={handleSelect}
                                onPreview={handlePreview}
                            />
                        ))}
                    </div>
                    <div className="border-b border-[#DED8CF]/50 mt-10" />
                </section>
            )}

            {/* All styles grouped by tier */}
            {TIER_ORDER.map((tierKey) => (
                <TierSection
                    key={tierKey}
                    tierKey={tierKey}
                    styles={grouped[tierKey] ?? []}
                    selected={selected}
                    recommendedIds={recommendedIds}
                    onSelect={handleSelect}
                    onPreview={handlePreview}
                />
            ))}

            {/* Sticky CTA */}
            <div className="sticky bottom-6 flex justify-center pt-4">
                <div className="bg-white/80 backdrop-blur-md rounded-full px-6 py-3 shadow-xl border border-[#DED8CF]/50 flex items-center gap-4">
                    {selectedStyle && (
                        <span className="text-sm text-[#78786C] font-nunito">
                            已选：<span className="font-bold text-[#5D7052]">{selectedStyle.name_zh}</span>
                        </span>
                    )}
                    <BlobButton onClick={handleNext} icon={Sparkles} disabled={!selected} className="ripple-btn">
                        开始生成
                    </BlobButton>
                </div>
            </div>

            {/* Lightbox */}
            {previewStyle && <Lightbox style={previewStyle} onClose={handleClosePreview} />}
        </div>
    );
};

export default StyleSelector;
