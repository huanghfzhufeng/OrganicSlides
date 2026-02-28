
import React, { useState } from 'react';
import { Sparkles, Check, Image, FileText, Shuffle, ChevronLeft } from 'lucide-react';
import BlobButton from '../components/BlobButton';

export type RenderPathPreference = 'path_b' | 'path_a' | 'auto';

interface RenderPathOption {
    id: RenderPathPreference;
    label: string;
    labelEn: string;
    icon: React.ReactNode;
    description: string;
    features: string[];
    color: string;
    recommended?: boolean;
}

const OPTIONS: RenderPathOption[] = [
    {
        id: 'auto',
        label: '智能混合',
        labelEn: 'Smart Mix',
        icon: <Shuffle size={28} strokeWidth={1.5} />,
        description: '系统根据每张幻灯片的内容自动选择最佳渲染方式，兼顾效率与视觉效果。',
        features: ['自动决策', '最佳平衡', '速度适中'],
        color: '#5D7052',
        recommended: true,
    },
    {
        id: 'path_b',
        label: '全 AI 视觉',
        labelEn: 'Full AI Visual',
        icon: <Image size={28} strokeWidth={1.5} />,
        description: '每张幻灯片均由 Gemini AI 生成专属插图，视觉冲击力最强，适合创意展示。',
        features: ['AI 生成插图', '视觉冲击强', '风格最一致'],
        color: '#C18C5D',
    },
    {
        id: 'path_a',
        label: 'HTML 排版',
        labelEn: 'HTML + AI Illustrations',
        icon: <FileText size={28} strokeWidth={1.5} />,
        description: '使用 HTML 模板精确排版，文字可在 PowerPoint 中直接编辑，适合商务报告。',
        features: ['文字可编辑', '排版精准', '生成速度快'],
        color: '#78786C',
    },
];

interface RenderPathSelectorProps {
    onNext: (preference: RenderPathPreference) => void;
    onBack?: () => void;
}

const RenderPathSelector: React.FC<RenderPathSelectorProps> = ({ onNext, onBack }) => {
    const [selected, setSelected] = useState<RenderPathPreference>('auto');

    return (
        <div className="max-w-4xl mx-auto page-enter">
            <div className="text-center mb-10">
                {onBack && (
                    <button
                        onClick={onBack}
                        className="flex items-center gap-1 text-sm text-[#78786C] hover:text-[#5D7052] mb-4 mx-auto transition-colors"
                    >
                        <ChevronLeft size={16} /> 返回风格选择
                    </button>
                )}
                <h2 className="font-fraunces text-3xl text-[#2C2C24] mb-2">选择渲染方式</h2>
                <p className="text-[#78786C]">选择幻灯片的视觉生成策略</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-12">
                {OPTIONS.map((option) => (
                    <div
                        key={option.id}
                        onClick={() => setSelected(option.id)}
                        className={`cursor-pointer rounded-[28px] p-6 border-2 transition-all duration-300 relative
                            ${selected === option.id
                                ? 'border-[#5D7052] shadow-xl scale-[1.02] bg-white'
                                : 'border-[#DED8CF] bg-white/60 hover:border-[#C18C5D]/50 hover:scale-[1.01]'
                            }`}
                    >
                        {option.recommended && (
                            <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#5D7052] text-white text-[10px] font-bold px-3 py-1 rounded-full whitespace-nowrap">
                                默认推荐
                            </div>
                        )}

                        {selected === option.id && (
                            <div className="absolute top-4 right-4 bg-[#5D7052] text-white p-1.5 rounded-full">
                                <Check size={12} />
                            </div>
                        )}

                        {/* Icon */}
                        <div
                            className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 text-white"
                            style={{ backgroundColor: option.color }}
                        >
                            {option.icon}
                        </div>

                        {/* Name */}
                        <h3 className="font-fraunces text-xl text-[#2C2C24] mb-1">{option.label}</h3>
                        <p className="text-[11px] text-[#78786C]/70 uppercase tracking-widest font-bold mb-3">{option.labelEn}</p>

                        {/* Description */}
                        <p className="text-sm text-[#78786C] mb-4 leading-relaxed">{option.description}</p>

                        {/* Features */}
                        <div className="flex flex-wrap gap-1.5">
                            {option.features.map((f, i) => (
                                <span
                                    key={i}
                                    className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                                    style={{ backgroundColor: `${option.color}15`, color: option.color }}
                                >
                                    {f}
                                </span>
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            <div className="flex justify-center">
                <BlobButton onClick={() => onNext(selected)} icon={Sparkles} className="ripple-btn">
                    开始生成
                </BlobButton>
            </div>
        </div>
    );
};

export default RenderPathSelector;
