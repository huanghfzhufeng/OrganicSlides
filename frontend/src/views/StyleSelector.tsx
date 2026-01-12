
import React, { useState } from 'react';
import { Sparkles, Check } from 'lucide-react';
import BlobButton from '../components/BlobButton';

interface StyleOption {
    id: string;
    name: string;
    color: string;
    img: string;
    desc: string;
}

interface StyleSelectorProps {
    onNext: () => void;
}

const StyleSelector: React.FC<StyleSelectorProps> = ({ onNext }) => {
    const styles: StyleOption[] = [
        { id: 'organic', name: "Organic Zen", color: "#5D7052", img: "bg-[#FDFCF8]", desc: "自然、柔和、衬线体、米纸质感" },
        { id: 'tech', name: "Neo Tech", color: "#2563EB", img: "bg-[#F8FAFC]", desc: "极简、冷调、无衬线、网格布局" },
        { id: 'classic', name: "Classic Serenity", color: "#475569", img: "bg-[#FFFFFF]", desc: "商务、稳重、宋体/衬线、留白" }
    ];
    const [selected, setSelected] = useState('organic');

    return (
        <div className="max-w-5xl mx-auto text-center">
            <h2 className="font-fraunces text-3xl text-[#2C2C24] mb-8">选择视觉风格</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
                {styles.map((style) => (
                    <div
                        key={style.id}
                        onClick={() => setSelected(style.id)}
                        className={`cursor-pointer rounded-[32px] overflow-hidden border-2 transition-all duration-300 relative group
              ${selected === style.id ? 'border-[#5D7052] shadow-xl scale-105' : 'border-transparent shadow-md hover:scale-[1.02]'}`}
                    >
                        <div className={`h-48 ${style.img} relative overflow-hidden p-6 flex flex-col justify-between`}>
                            {/* Mockup Preview */}
                            <div className="w-16 h-16 rounded-full mix-blend-multiply opacity-50" style={{ backgroundColor: style.color }}></div>
                            <div className="w-full h-2 bg-black/5 rounded-full mt-4"></div>
                            <div className="w-2/3 h-2 bg-black/5 rounded-full"></div>

                            {selected === style.id && (
                                <div className="absolute top-4 right-4 bg-[#5D7052] text-white p-2 rounded-full">
                                    <Check size={16} />
                                </div>
                            )}
                        </div>
                        <div className="bg-white p-6 text-left">
                            <h3 className="font-fraunces font-bold text-xl text-[#2C2C24]">{style.name}</h3>
                            <p className="text-[#78786C] text-sm mt-2">{style.desc}</p>
                        </div>
                    </div>
                ))}
            </div>

            <BlobButton onClick={onNext} icon={Sparkles}>
                开始生成
            </BlobButton>
        </div>
    );
};

export default StyleSelector;
