
import React, { useState, useCallback } from 'react';
import { Globe, FileText, Loader2, Search, BookOpen, Database, CheckCircle2 } from 'lucide-react';
import { api, type OutlineItem } from '../api/client';
import { flowingLeavesIcon } from '../assets/icons';
import { ResearchSkeleton } from '../components/Skeleton';
import ErrorMessage from '../components/ErrorMessage';
import { useSSE } from '../hooks/useSSE';

interface ResearchViewProps {
    sessionId: string;
    onComplete: (outline: OutlineItem[]) => void;
}

interface ResearchStats {
    sourcesFound: number;
    dataProcessed: number;
    sectionsCreated: number;
}

// Parse real counts from researcher agent message text.
// Message format: "研究员已完成搜索: 找到 N 条网络资源, M 条文档片段"
function parseResearcherStats(message: string): Partial<ResearchStats> {
    const webMatch = message.match(/找到\s*(\d+)\s*条网络资源/);
    const docMatch = message.match(/(\d+)\s*条文档片段/);
    const result: Partial<ResearchStats> = {};
    if (webMatch) result.sourcesFound = parseInt(webMatch[1], 10);
    if (docMatch) result.dataProcessed = parseInt(docMatch[1], 10);
    return result;
}

const ResearchView: React.FC<ResearchViewProps> = ({ sessionId, onComplete }) => {
    const [logs, setLogs] = useState<any[]>([]);
    const [currentStatus, setCurrentStatus] = useState("正在初始化研究...");
    const [stats, setStats] = useState<ResearchStats>({
        sourcesFound: 0,
        dataProcessed: 0,
        sectionsCreated: 0,
    });
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState<string | null>(null);

    const handleMessage = useCallback((data: any) => {
        if (data.type === 'status') {
            setLogs(prev => [...prev, data]);
            setCurrentStatus(data.message || `正在由 ${data.agent} 处理...`);
            setProgress(prev => Math.min(prev + 15, 90));

            if (data.agent === 'researcher' && data.message) {
                const parsed = parseResearcherStats(data.message);
                setStats(prev => ({
                    ...prev,
                    sourcesFound: parsed.sourcesFound ?? prev.sourcesFound,
                    dataProcessed: parsed.dataProcessed ?? prev.dataProcessed,
                }));
            } else if (data.agent === 'planner') {
                setStats(prev => ({
                    ...prev,
                    sectionsCreated: prev.sectionsCreated + 1,
                }));
            }
        } else if (data.type === 'hitl') {
            setProgress(100);
            setTimeout(() => onComplete(data.outline), 500);
        } else if (data.type === 'error') {
            setError(data.message || '研究过程出错，请重试');
        }
    }, [onComplete]);

    const handleError = useCallback((errMsg: string) => {
        setError(errMsg);
    }, []);

    useSSE({
        url: api.getStartWorkflowUrl(sessionId),
        onMessage: handleMessage,
        onError: handleError,
    });

    if (error) {
        return (
            <div className="max-w-3xl mx-auto page-enter">
                <ErrorMessage
                    message={error}
                    type="network"
                    onRetry={() => window.location.reload()}
                />
            </div>
        );
    }

    return (
        <div className="max-w-3xl mx-auto page-enter">
            {/* 主视觉区域 */}
            <div className="text-center mb-8">
                <div className="mb-6 relative inline-block">
                    <div className="w-28 h-28 bg-[#5D7052]/10 rounded-full flex items-center justify-center mx-auto p-4 relative">
                        <img src={flowingLeavesIcon} alt="研究中" className="w-full h-full object-contain breathe" />
                        <div className="pulse-ring" />
                    </div>
                    <div className="absolute top-2 right-2">
                        <span className="flex h-3 w-3">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#C18C5D] opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-3 w-3 bg-[#C18C5D]"></span>
                        </span>
                    </div>
                </div>

                <h2 className="font-fraunces text-3xl text-[#2C2C24] mb-2">{currentStatus}</h2>
                <p className="text-[#78786C] mb-6 font-nunito">研究员与策划师正在协同工作，为您构建最优框架</p>

                {/* 进度条 */}
                <div className="w-full max-w-md mx-auto h-2 bg-[#DED8CF]/30 rounded-full overflow-hidden mb-8">
                    <div
                        className="h-full progress-bar rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>

            {/* 统计卡片 */}
            <div className="grid grid-cols-3 gap-4 mb-8">
                <div className="bg-white/70 backdrop-blur-sm rounded-2xl p-4 border border-[#DED8CF] text-center">
                    <Search className="w-6 h-6 text-[#5D7052] mx-auto mb-2" />
                    <div className="text-2xl font-bold text-[#2C2C24]">{stats.sourcesFound}</div>
                    <div className="text-xs text-[#78786C]">网络资源</div>
                </div>
                <div className="bg-white/70 backdrop-blur-sm rounded-2xl p-4 border border-[#DED8CF] text-center">
                    <Database className="w-6 h-6 text-[#C18C5D] mx-auto mb-2" />
                    <div className="text-2xl font-bold text-[#2C2C24]">{stats.dataProcessed}</div>
                    <div className="text-xs text-[#78786C]">文档片段</div>
                </div>
                <div className="bg-white/70 backdrop-blur-sm rounded-2xl p-4 border border-[#DED8CF] text-center">
                    <BookOpen className="w-6 h-6 text-[#A85448] mx-auto mb-2" />
                    <div className="text-2xl font-bold text-[#2C2C24]">{stats.sectionsCreated}</div>
                    <div className="text-xs text-[#78786C]">章节规划</div>
                </div>
            </div>

            {/* 日志列表 */}
            <div className="space-y-3 text-left max-h-[300px] overflow-y-auto pr-2 no-scrollbar">
                {logs.length === 0 ? (
                    <ResearchSkeleton />
                ) : (
                    logs.map((log, idx) => (
                        <div
                            key={idx}
                            className="bg-white p-4 rounded-xl border border-[#DED8CF] shadow-sm flex items-center gap-4 animate-in fade-in slide-in-from-bottom-2"
                        >
                            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white flex-shrink-0
                                ${log.agent === 'researcher' ? 'bg-[#5D7052]' : 'bg-[#C18C5D]'}`}>
                                {log.agent === 'researcher' ? <Globe size={18} /> : <FileText size={18} />}
                            </div>
                            <div className="flex-1 min-w-0">
                                <h4 className="font-bold text-[#2C2C24] text-sm uppercase tracking-wider">{log.agent}</h4>
                                <p className="text-xs text-[#78786C] mt-1 truncate">{log.message}</p>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                                {log.status === 'complete' ? (
                                    <CheckCircle2 size={16} className="text-[#5D7052]" />
                                ) : (
                                    <Loader2 size={16} className="animate-spin text-[#C18C5D]" />
                                )}
                                <span className="text-[10px] font-bold text-[#5D7052] bg-[#5D7052]/10 px-2 py-1 rounded-full uppercase">
                                    {log.status}
                                </span>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default ResearchView;
