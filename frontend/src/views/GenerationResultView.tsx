
import React, { useState, useEffect } from 'react';
import { Loader2, Download, Layout, Palette, Feather, Sparkles, PartyPopper } from 'lucide-react';
import BlobButton from '../components/BlobButton';
import { api } from '../api/client';
import { dandelionIcon } from '../assets/icons';
import Confetti from '../components/Confetti';
import { GenerationSkeleton } from '../components/Skeleton';
import ErrorMessage from '../components/ErrorMessage';

interface GenerationResultViewProps {
    sessionId: string;
}

const GenerationResultView: React.FC<GenerationResultViewProps> = ({ sessionId }) => {
    const [isDone, setIsDone] = useState(false);
    const [logs, setLogs] = useState<any[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [showConfetti, setShowConfetti] = useState(false);
    const [progress, setProgress] = useState(0);

    const handleRetry = () => {
        window.location.reload();
    };

    useEffect(() => {
        const eventSource = new EventSource(api.getResumeWorkflowUrl(sessionId));

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("SSE Resume Event:", data);

            if (data.type === 'status') {
                setLogs(prev => [...prev, data]);
                setProgress(prev => Math.min(prev + 20, 95));
            } else if (data.type === 'complete') {
                setProgress(100);
                setIsDone(true);
                setShowConfetti(true);
                eventSource.close();
            } else if (data.type === 'error') {
                setError(data.message);
                eventSource.close();
            }
        };

        eventSource.onerror = (err) => {
            console.error("SSE Resume Error:", err);
            setError("连接中断，请检查网络后重试");
            eventSource.close();
        };

        return () => eventSource.close();
    }, [sessionId]);

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 h-full min-h-[500px] page-enter">
            {/* 庆祝动画 */}
            <Confetti isActive={showConfetti} />

            {/* Left: Logs & Status */}
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
                        {error ? "生成出错" : isDone ? "🎉 生成完毕" : "正在进行最终创作..."}
                    </h3>

                    {/* 进度条 */}
                    {!isDone && !error && (
                        <div className="w-full h-1.5 bg-[#DED8CF]/30 rounded-full overflow-hidden mb-4">
                            <div
                                className="h-full progress-bar rounded-full transition-all duration-500 ease-out"
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                    )}

                    <div className="flex-1 overflow-y-auto space-y-4 font-nunito text-sm text-[#78786C] pr-2 no-scrollbar">
                        {error && (
                            <ErrorMessage
                                message={error}
                                type="error"
                                onRetry={handleRetry}
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
                    <a href={api.getDownloadUrl(sessionId)} download>
                        <BlobButton variant="primary" icon={Download} className="w-full ripple-btn">
                            下载完整 .pptx
                        </BlobButton>
                    </a>
                )}
            </div>

            {/* Right: Preview */}
            <div className="lg:col-span-8 flex flex-col gap-4">
                <div className={`flex-1 bg-[#FEFEFA] border border-[#DED8CF] rounded-[24px] shadow-lg relative overflow-hidden flex items-center justify-center p-12 transition-all duration-700
                    ${isDone ? 'border-[#5D7052]/30' : ''}`}>
                    {/* 完成状态 */}
                    <div className="text-center z-10 animate-in fade-in duration-1000">
                        {isDone ? (
                            <>
                                <img src={dandelionIcon} alt="完成" className="w-36 h-36 mx-auto mb-6 drop-shadow-lg breathe" />
                                <h2 className="font-fraunces text-4xl text-[#2C2C24] mb-2">🎊 创作完成！</h2>
                                <p className="mt-4 text-[#78786C] max-w-sm mx-auto">您的专属演示文稿已生成完毕，点击下方按钮下载</p>
                            </>
                        ) : (
                            <>
                                <span className="text-xs font-bold tracking-widest text-[#5D7052] uppercase mb-4 block">PREVIEW ENGINE</span>
                                <h2 className="font-fraunces text-4xl text-[#2C2C24]">您的演示文稿即将就绪</h2>
                                <p className="mt-4 text-[#78786C] max-w-sm mx-auto">正在将 AI 生成的内容与视觉方案合成为标准的 Microsoft PowerPoint 格式</p>
                            </>
                        )}
                    </div>

                    {/* Blobs */}
                    <div className={`absolute top-[-50%] right-[-20%] w-[400px] h-[400px] rounded-full mix-blend-multiply blur-[80px] opacity-40 animate-pulse transition-colors duration-1000
                        ${isDone ? 'bg-[#5D7052]' : 'bg-[#E6DCCD]'}`}></div>
                    <div className={`absolute bottom-[-50%] left-[-20%] w-[300px] h-[300px] rounded-full mix-blend-multiply blur-[60px] opacity-20 animate-pulse transition-colors duration-1000
                        ${isDone ? 'bg-[#C18C5D]' : 'bg-[#5D7052]'}`} style={{ animationDelay: '1s' }}></div>

                    {!isDone && !error && (
                        <div className="absolute inset-0 bg-white/50 backdrop-blur-sm flex flex-col items-center justify-center z-20">
                            <Loader2 className="animate-spin text-[#5D7052] mb-4" size={48} />
                            <span className="bg-white px-4 py-2 rounded-full shadow-sm text-sm text-[#78786C]">渲染引擎正在生成原生 PPT 对象...</span>
                        </div>
                    )}
                </div>

                {/* Info */}
                <div className="bg-white/40 p-4 rounded-xl text-xs text-[#78786C] flex items-center justify-center gap-2">
                    <Sparkles size={14} className="text-[#C18C5D]" />
                    {isDone ? "恭喜！您可以直接在 PowerPoint 中打开并进行二次修改。" : "提示：生成完毕后，您可以直接下载并在 PowerPoint 中进行二次修改。"}
                </div>
            </div>
        </div>
    );
};

export default GenerationResultView;
