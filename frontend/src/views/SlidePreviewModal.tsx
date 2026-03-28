
import React, { useState, useEffect, useCallback } from 'react';
import { X, ChevronLeft, ChevronRight, StickyNote, Loader2 } from 'lucide-react';
import { api, type SlidePreview } from '../api/client';

interface SlidePreviewModalProps {
    sessionId: string;
    onClose: () => void;
}

const SlidePreviewModal: React.FC<SlidePreviewModalProps> = ({ sessionId, onClose }) => {
    const [slides, setSlides] = useState<SlidePreview[]>([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showNotes, setShowNotes] = useState(false);

    useEffect(() => {
        const fetchPreview = async () => {
            try {
                const data = await api.getSlidePreview(sessionId);
                setSlides(data.slides);
            } catch {
                setError('预览数据不可用');
            } finally {
                setLoading(false);
            }
        };
        fetchPreview();
    }, [sessionId]);

    const goNext = useCallback(() => {
        setCurrentIndex(prev => Math.min(prev + 1, slides.length - 1));
    }, [slides.length]);

    const goPrev = useCallback(() => {
        setCurrentIndex(prev => Math.max(prev - 1, 0));
    }, []);

    // Keyboard navigation
    useEffect(() => {
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
            if (e.key === 'ArrowRight') goNext();
            if (e.key === 'ArrowLeft') goPrev();
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [onClose, goNext, goPrev]);

    const currentSlide = slides[currentIndex];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="bg-[#FDFCF8] rounded-3xl shadow-2xl w-[90vw] max-w-5xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-300">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-[#DED8CF]/30">
                    <h3 className="font-fraunces text-lg text-[#2C2C24]">
                        {loading ? '加载中...' : `第 ${currentIndex + 1} / ${slides.length} 页`}
                    </h3>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-full bg-[#DED8CF]/20 flex items-center justify-center hover:bg-[#DED8CF]/40 transition-colors"
                    >
                        <X size={16} className="text-[#78786C]" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-hidden flex flex-col items-center justify-center p-6 relative">
                    {loading && (
                        <div className="flex flex-col items-center gap-3">
                            <Loader2 size={32} className="animate-spin text-[#5D7052]" />
                            <span className="text-sm text-[#78786C]">加载预览...</span>
                        </div>
                    )}

                    {error && (
                        <div className="text-center">
                            <p className="text-[#A85448] font-bold mb-2">{error}</p>
                            <p className="text-sm text-[#78786C]">会话数据可能已过期，请尝试重新生成。</p>
                        </div>
                    )}

                    {!loading && !error && currentSlide && (
                        <div className="w-full flex items-center gap-4">
                            {/* Prev button */}
                            <button
                                onClick={goPrev}
                                disabled={currentIndex === 0}
                                className="flex-shrink-0 w-10 h-10 rounded-full bg-white border border-[#DED8CF] flex items-center justify-center hover:bg-[#5D7052]/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            >
                                <ChevronLeft size={20} className="text-[#5D7052]" />
                            </button>

                            {/* Slide preview card */}
                            <div className="flex-1 bg-white rounded-2xl border border-[#DED8CF] shadow-lg aspect-[16/9] p-8 md:p-12 flex flex-col justify-center overflow-y-auto">
                                {/* Slide number badge */}
                                <span className="text-[10px] font-bold uppercase tracking-widest text-[#C18C5D] mb-4">
                                    第 {currentSlide.page_number} 页
                                    {currentSlide.visual_type && ` - ${currentSlide.visual_type}`}
                                </span>

                                {/* Title */}
                                <h2 className="font-fraunces text-2xl md:text-3xl text-[#2C2C24] mb-6 leading-tight">
                                    {currentSlide.title || '无标题幻灯片'}
                                </h2>

                                {/* Bullet points */}
                                {currentSlide.content?.bullet_points && currentSlide.content.bullet_points.length > 0 && (
                                    <ul className="space-y-3">
                                        {currentSlide.content.bullet_points.map((point, idx) => (
                                            <li key={idx} className="flex items-start gap-3 text-[#2C2C24]/80">
                                                <span className="mt-1.5 w-2 h-2 rounded-full bg-[#5D7052] flex-shrink-0" />
                                                <span className="text-sm md:text-base leading-relaxed">{point}</span>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>

                            {/* Next button */}
                            <button
                                onClick={goNext}
                                disabled={currentIndex === slides.length - 1}
                                className="flex-shrink-0 w-10 h-10 rounded-full bg-white border border-[#DED8CF] flex items-center justify-center hover:bg-[#5D7052]/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                            >
                                <ChevronRight size={20} className="text-[#5D7052]" />
                            </button>
                        </div>
                    )}
                </div>

                {/* Footer with speaker notes toggle + slide thumbnails */}
                {!loading && !error && slides.length > 0 && (
                    <div className="border-t border-[#DED8CF]/30">
                        {/* Speaker notes */}
                        {showNotes && currentSlide?.speaker_notes && (
                            <div className="px-6 py-3 bg-[#F5F0EB]/50 text-sm text-[#78786C] leading-relaxed max-h-24 overflow-y-auto">
                                {currentSlide.speaker_notes}
                            </div>
                        )}

                        <div className="px-6 py-3 flex items-center justify-between">
                            {/* Notes toggle */}
                            <button
                                onClick={() => setShowNotes(prev => !prev)}
                                className={`flex items-center gap-1.5 text-xs font-bold transition-colors ${
                                    showNotes ? 'text-[#5D7052]' : 'text-[#78786C] hover:text-[#5D7052]'
                                }`}
                            >
                                <StickyNote size={14} />
                                {showNotes ? '隐藏备注' : '演讲备注'}
                            </button>

                            {/* Slide dots */}
                            <div className="flex gap-1.5">
                                {slides.map((_, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => setCurrentIndex(idx)}
                                        className={`w-2 h-2 rounded-full transition-all ${
                                            idx === currentIndex
                                                ? 'bg-[#5D7052] w-6'
                                                : 'bg-[#DED8CF] hover:bg-[#C18C5D]'
                                        }`}
                                    />
                                ))}
                            </div>

                            {/* Keyboard hint */}
                            <span className="text-[10px] text-[#DED8CF] hidden md:block">
                                方向键翻页 · ESC 关闭
                            </span>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default SlidePreviewModal;
