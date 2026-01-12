
import React from 'react';
import { ArrowRight, Globe } from 'lucide-react';
import BlobButton from '../components/BlobButton';

interface InputViewProps {
    prompt: string;
    setPrompt: (value: string) => void;
    onNext: () => void;
}

const InputView: React.FC<InputViewProps> = ({ prompt, setPrompt, onNext }) => (
    <div className="flex flex-col items-center text-center animate-in fade-in slide-in-from-bottom-4 duration-700 max-w-3xl mx-auto">
        <h1 className="font-fraunces text-4xl md:text-6xl text-[#2C2C24] mb-6 leading-tight">
            种下一颗<br /><span className="text-[#5D7052] italic">思想的种子</span>
        </h1>
        <p className="text-[#78786C] text-lg mb-8 max-w-lg">
            描述您想要的主题，我们的 AI 代理将开始全网搜索素材并为您构建逻辑框架。
        </p>
        <div className="w-full bg-white/60 backdrop-blur-sm border border-[#DED8CF] p-2 shadow-xl rounded-[32px] transition-all focus-within:ring-4 ring-[#5D7052]/10">
            <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="例如：为一家致力于海洋保护的非营利组织制作一份年度募捐演示文稿..."
                className="w-full h-40 bg-transparent border-none focus:ring-0 p-6 resize-none text-xl text-[#2C2C24] placeholder-[#78786C]/40 font-nunito"
            />
            <div className="flex justify-between items-center px-4 pb-2 pt-2">
                <button className="text-[#C18C5D] text-sm font-bold hover:text-[#A85448] transition-colors flex items-center gap-1">
                    <Globe size={16} /> 启用联网搜索
                </button>
                <BlobButton onClick={onNext} disabled={!prompt.trim()} icon={ArrowRight}>
                    开始研究
                </BlobButton>
            </div>
        </div>
    </div>
);

export default InputView;
