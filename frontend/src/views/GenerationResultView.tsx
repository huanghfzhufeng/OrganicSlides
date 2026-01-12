
import React, { useState, useEffect } from 'react';
import { Loader2, Check, Download, Layout, Palette, Feather, Sparkles } from 'lucide-react';
import BlobButton from '../components/BlobButton';
import { api } from '../api/client';

interface GenerationResultViewProps {
    sessionId: string;
}

const GenerationResultView: React.FC<GenerationResultViewProps> = ({ sessionId }) => {
    const [isDone, setIsDone] = useState(false);
    const [logs, setLogs] = useState<any[]>([]);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const eventSource = new EventSource(api.getResumeWorkflowUrl(sessionId));

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("SSE Resume Event:", data);

            if (data.type === 'status') {
                setLogs(prev => [...prev, data]);
            } else if (data.type === 'complete') {
                setIsDone(true);
                eventSource.close();
            } else if (data.type === 'error') {
                setError(data.message);
                eventSource.close();
            }
        };

        eventSource.onerror = (err) => {
            console.error("SSE Resume Error:", err);
            eventSource.close();
        };

        return () => eventSource.close();
    }, [sessionId]);

    // Slide preview data can be fetched from API in the future

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 h-full min-h-[500px]">
            {/* Left: Logs & Status */}
            <div className="lg:col-span-4 flex flex-col gap-6">
                <div className="bg-white/60 p-6 rounded-[24px] border border-[#DED8CF] shadow-sm flex-1 overflow-hidden flex flex-col">
                    <h3 className="font-fraunces text-xl mb-4 flex items-center gap-2">
                        {!isDone && !error ? <Loader2 className="animate-spin text-[#5D7052]" /> : error ? <span className="text-red-500">!</span> : <Check className="text-[#C18C5D]" />}
                        {error ? "生成出错" : isDone ? "生成完毕" : "正在进行最终创作..."}
                    </h3>

                    <div className="flex-1 overflow-y-auto space-y-4 font-nunito text-sm text-[#78786C] pr-2 no-scrollbar">
                        {error && <div className="text-red-500 bg-red-50 p-3 rounded-lg border border-red-100">{error}</div>}
                        {logs.map((log, i) => (
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
                        ))}
                    </div>
                </div>

                {isDone && (
                    <a href={api.getDownloadUrl(sessionId)} download>
                        <BlobButton variant="primary" icon={Download} className="w-full">
                            下载完整 .pptx
                        </BlobButton>
                    </a>
                )}
            </div>

            {/* Right: Preview */}
            <div className="lg:col-span-8 flex flex-col gap-4">
                <div className="flex-1 bg-[#FEFEFA] border border-[#DED8CF] rounded-[24px] shadow-lg relative overflow-hidden flex items-center justify-center p-12 transition-all duration-700">
                    {/* Simple slide preview mockup */}
                    <div className="text-center z-10 animate-in fade-in duration-1000">
                        <span className="text-xs font-bold tracking-widest text-[#5D7052] uppercase mb-4 block">PREVIEW ENGINE</span>
                        <h2 className="font-fraunces text-4xl text-[#2C2C24]">您的演示文稿即将就绪</h2>
                        <p className="mt-4 text-[#78786C] max-w-sm mx-auto">正在将 AI 生成的内容与视觉方案合成为标准的 Microsoft PowerPoint 格式</p>
                    </div>

                    {/* Blobs */}
                    <div className="absolute top-[-50%] right-[-20%] w-[400px] h-[400px] bg-[#E6DCCD] rounded-full mix-blend-multiply blur-[80px] opacity-40 animate-pulse"></div>
                    <div className="absolute bottom-[-50%] left-[-20%] w-[300px] h-[300px] bg-[#5D7052] rounded-full mix-blend-multiply blur-[60px] opacity-20 animate-pulse" style={{ animationDelay: '1s' }}></div>

                    {!isDone && (
                        <div className="absolute inset-0 bg-white/50 backdrop-blur-sm flex flex-col items-center justify-center z-20">
                            <Loader2 className="animate-spin text-[#5D7052] mb-4" size={48} />
                            <span className="bg-white px-4 py-2 rounded-full shadow-sm text-sm text-[#78786C]">渲染引擎正在生成原生 PPT 对象...</span>
                        </div>
                    )}
                </div>

                {/* Info */}
                <div className="bg-white/40 p-4 rounded-xl text-xs text-[#78786C] flex items-center justify-center gap-2">
                    <Sparkles size={14} className="text-[#C18C5D]" />
                    提示：生成完毕后，您可以直接下载并在 PowerPoint 中进行二次修改。
                </div>
            </div>
        </div>
    );
};

export default GenerationResultView;
