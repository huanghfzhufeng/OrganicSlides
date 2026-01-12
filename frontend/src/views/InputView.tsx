
import React from 'react';
import { ArrowRight, Globe, Lightbulb, Building2, GraduationCap, Heart } from 'lucide-react';
import BlobButton from '../components/BlobButton';
import { seedlingIcon } from '../assets/icons';

interface InputViewProps {
    prompt: string;
    setPrompt: (value: string) => void;
    onNext: () => void;
}

// 示例提示词
const EXAMPLE_PROMPTS = [
    {
        icon: Heart,
        title: "公益募捐",
        prompt: "为一家致力于海洋保护的非营利组织制作一份年度募捐演示文稿，包含项目成果、未来计划和捐赠方式",
        color: "#5D7052",
    },
    {
        icon: Building2,
        title: "商业路演",
        prompt: "为一家 AI 初创公司制作 A 轮融资路演 PPT，展示产品优势、市场规模、商业模式和团队背景",
        color: "#C18C5D",
    },
    {
        icon: GraduationCap,
        title: "学术报告",
        prompt: "制作一份关于可持续发展与碳中和的学术报告演示文稿，面向环境科学专业的研究生",
        color: "#78786C",
    },
    {
        icon: Lightbulb,
        title: "产品发布",
        prompt: "为一款智能家居产品制作新品发布会演示文稿，突出创新功能、用户场景和市场定位",
        color: "#A85448",
    },
];

const InputView: React.FC<InputViewProps> = ({ prompt, setPrompt, onNext }) => (
    <div className="flex flex-col items-center text-center page-enter max-w-4xl mx-auto">
        {/* 主视觉图标 */}
        <img
            src={seedlingIcon}
            alt="种子"
            className="w-28 h-28 mb-6 drop-shadow-lg breathe"
        />

        {/* 标题 */}
        <h1 className="font-fraunces text-4xl md:text-6xl text-[#2C2C24] mb-4 leading-tight">
            种下一颗<br /><span className="text-[#5D7052] italic">思想的种子</span>
        </h1>
        <p className="text-[#78786C] text-lg mb-8 max-w-lg">
            描述您想要的主题，我们的 AI 代理将开始全网搜索素材并为您构建逻辑框架。
        </p>

        {/* 示例提示词卡片 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8 w-full">
            {EXAMPLE_PROMPTS.map((example, idx) => (
                <button
                    key={idx}
                    onClick={() => setPrompt(example.prompt)}
                    className="example-card bg-white/70 backdrop-blur-sm border border-[#DED8CF] rounded-2xl p-4 text-left group"
                >
                    <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center mb-3 transition-transform group-hover:scale-110"
                        style={{ backgroundColor: `${example.color}15` }}
                    >
                        <example.icon size={20} style={{ color: example.color }} />
                    </div>
                    <h3 className="font-bold text-sm text-[#2C2C24] mb-1">{example.title}</h3>
                    <p className="text-xs text-[#78786C] line-clamp-2">{example.prompt.slice(0, 40)}...</p>
                </button>
            ))}
        </div>

        {/* 输入框 - 带流光边框 */}
        <div className="w-full glow-input bg-white/60 backdrop-blur-sm border border-[#DED8CF] p-2 shadow-xl rounded-[32px] transition-all focus-within:ring-4 ring-[#5D7052]/10">
            <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="输入您的演示文稿主题，或点击上方卡片选择示例..."
                className="w-full h-32 bg-transparent border-none focus:ring-0 focus:outline-none p-6 resize-none text-xl text-[#2C2C24] placeholder-[#78786C]/40 font-nunito"
            />
            <div className="flex justify-between items-center px-4 pb-2 pt-2">
                <button className="text-[#C18C5D] text-sm font-bold hover:text-[#A85448] transition-colors flex items-center gap-1.5 ripple-btn px-3 py-1.5 rounded-lg hover:bg-[#C18C5D]/10">
                    <Globe size={16} /> 启用联网搜索
                </button>
                <BlobButton onClick={onNext} disabled={!prompt.trim()} icon={ArrowRight}>
                    开始研究
                </BlobButton>
            </div>
        </div>

        {/* 提示文字 */}
        <p className="text-xs text-[#DED8CF] mt-4">
            💡 提示：描述越详细，生成效果越好
        </p>
    </div>
);

export default InputView;
