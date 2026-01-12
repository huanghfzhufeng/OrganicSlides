
import React, { useState } from 'react';
import { Sparkles, Check } from 'lucide-react';
import BlobButton from '../components/BlobButton';
import { forestGlobeIcon, organicGearsIcon, zenStonesIcon } from '../assets/icons';

interface StyleOption {
    id: string;
    name: string;
    color: string;
    secondaryColor: string;
    bgClass: string;
    desc: string;
    features: string[];
    previewIcon?: string;
}

interface StyleSelectorProps {
    onNext: () => void;
}

const StyleSelector: React.FC<StyleSelectorProps> = ({ onNext }) => {
    const styles: StyleOption[] = [
        {
            id: 'organic',
            name: "Organic Zen",
            color: "#5D7052",
            secondaryColor: "#C18C5D",
            bgClass: "bg-gradient-to-br from-[#FDFCF8] to-[#F0EBE5]",
            desc: "自然、柔和、衬线体、米纸质感",
            features: ["柔和配色", "衬线字体", "有机形状"],
            previewIcon: forestGlobeIcon,
        },
        {
            id: 'tech',
            name: "Neo Tech",
            color: "#2563EB",
            secondaryColor: "#60A5FA",
            bgClass: "bg-gradient-to-br from-[#F8FAFC] to-[#E0E7FF]",
            desc: "极简、冷调、无衬线、网格布局",
            features: ["网格系统", "无衬线", "科技感"],
            previewIcon: organicGearsIcon,
        },
        {
            id: 'classic',
            name: "Classic Serenity",
            color: "#475569",
            secondaryColor: "#94A3B8",
            bgClass: "bg-gradient-to-br from-[#FFFFFF] to-[#F1F5F9]",
            desc: "商务、稳重、宋体/衬线、留白",
            features: ["商务风格", "大量留白", "经典配色"],
            previewIcon: zenStonesIcon,
        }
    ];
    const [selected, setSelected] = useState('organic');

    return (
        <div className="max-w-5xl mx-auto text-center page-enter">
            <h2 className="font-fraunces text-3xl text-[#2C2C24] mb-2">选择视觉风格</h2>
            <p className="text-[#78786C] mb-8">为您的演示文稿选择最适合的视觉语言</p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
                {styles.map((style) => (
                    <div
                        key={style.id}
                        onClick={() => setSelected(style.id)}
                        className={`cursor-pointer rounded-[32px] overflow-hidden border-2 transition-all duration-500 relative group example-card
                            ${selected === style.id ? 'border-[#5D7052] shadow-2xl scale-105' : 'border-transparent shadow-lg hover:scale-[1.02]'}`}
                    >
                        {/* 幻灯片预览区域 */}
                        <div className={`h-56 ${style.bgClass} relative overflow-hidden p-6`}>
                            {/* 模拟幻灯片 */}
                            <div className="absolute inset-4 bg-white/80 backdrop-blur-sm rounded-xl shadow-lg p-4 flex flex-col items-center justify-center">
                                {/* 预览图标 */}
                                {style.previewIcon && (
                                    <img
                                        src={style.previewIcon}
                                        alt={style.name}
                                        className={`w-16 h-16 object-contain mb-3 transition-transform duration-500 group-hover:scale-110 
                                            ${selected === style.id ? 'breathe' : ''}`}
                                    />
                                )}
                                {/* 模拟标题 */}
                                <div
                                    className="w-3/4 h-3 rounded-full mb-2"
                                    style={{ backgroundColor: style.color }}
                                />
                                {/* 模拟内容行 */}
                                <div className="w-full space-y-1.5">
                                    <div className="h-1.5 bg-black/10 rounded-full w-full" />
                                    <div className="h-1.5 bg-black/10 rounded-full w-5/6" />
                                    <div className="h-1.5 bg-black/10 rounded-full w-4/6" />
                                </div>
                            </div>

                            {/* 选中标记 */}
                            {selected === style.id && (
                                <div className="absolute top-4 right-4 bg-[#5D7052] text-white p-2 rounded-full shadow-lg animate-in zoom-in duration-300">
                                    <Check size={16} />
                                </div>
                            )}

                            {/* 装饰圆点 */}
                            <div
                                className="absolute -bottom-8 -right-8 w-32 h-32 rounded-full opacity-20"
                                style={{ backgroundColor: style.color }}
                            />
                        </div>

                        {/* 风格信息 */}
                        <div className="bg-white p-5 text-left">
                            <div className="flex items-center gap-2 mb-2">
                                <div
                                    className="w-3 h-3 rounded-full"
                                    style={{ backgroundColor: style.color }}
                                />
                                <h3 className="font-fraunces font-bold text-lg text-[#2C2C24]">{style.name}</h3>
                            </div>
                            <p className="text-[#78786C] text-sm mb-3">{style.desc}</p>

                            {/* 特性标签 */}
                            <div className="flex flex-wrap gap-1.5">
                                {style.features.map((feature, i) => (
                                    <span
                                        key={i}
                                        className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                                        style={{
                                            backgroundColor: `${style.color}15`,
                                            color: style.color,
                                        }}
                                    >
                                        {feature}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            <BlobButton onClick={onNext} icon={Sparkles} className="ripple-btn">
                开始生成
            </BlobButton>
        </div>
    );
};

export default StyleSelector;
