
import React, { useState, useEffect } from 'react';
import { Globe, FileText, Loader2 } from 'lucide-react';
import { api, type OutlineItem } from '../api/client';

interface ResearchViewProps {
    sessionId: string;
    onComplete: (outline: OutlineItem[]) => void;
}

const ResearchView: React.FC<ResearchViewProps> = ({ sessionId, onComplete }) => {
    const [logs, setLogs] = useState<any[]>([]);
    const [currentStatus, setCurrentStatus] = useState("正在初始化研究...");

    useEffect(() => {
        const eventSource = new EventSource(api.getStartWorkflowUrl(sessionId));

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("SSE Event:", data);

            if (data.type === 'status') {
                setLogs(prev => [...prev, data]);
                setCurrentStatus(data.message || `正在由 ${data.agent} 处理...`);
            } else if (data.type === 'hitl') {
                eventSource.close();
                onComplete(data.outline);
            } else if (data.type === 'error') {
                console.error("Workflow Error:", data.message);
                eventSource.close();
            }
        };

        eventSource.onerror = (err) => {
            console.error("SSE Error:", err);
            eventSource.close();
        };

        return () => eventSource.close();
    }, [sessionId, onComplete]);

    return (
        <div className="max-w-2xl mx-auto text-center">
            <div className="mb-8 relative inline-block">
                <div className="w-20 h-20 bg-[#5D7052]/10 rounded-full flex items-center justify-center mx-auto">
                    <Globe size={32} className="text-[#5D7052] animate-spin-slow" />
                </div>
                <div className="absolute top-0 right-0">
                    <span className="flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#C18C5D] opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-[#C18C5D]"></span>
                    </span>
                </div>
            </div>
            <h2 className="font-fraunces text-3xl text-[#2C2C24] mb-2">{currentStatus}</h2>
            <p className="text-[#78786C] mb-8 font-nunito">研究员与策划师正在协同工作，为您构建最优框架</p>

            <div className="space-y-3 text-left max-h-[400px] overflow-y-auto pr-2 no-scrollbar">
                {logs.length === 0 && (
                    <div className="flex items-center justify-center py-10 text-[#DED8CF]">
                        <Loader2 className="animate-spin mr-2" /> 正在建立连接...
                    </div>
                )}
                {logs.map((log, idx) => (
                    <div key={idx} className="bg-white p-4 rounded-xl border border-[#DED8CF] shadow-sm flex items-center gap-4 animate-in fade-in slide-in-from-bottom-2">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white ${log.agent === 'researcher' ? 'bg-[#5D7052]' : 'bg-[#C18C5D]'}`}>
                            {log.agent === 'researcher' ? <Globe size={18} /> : <FileText size={18} />}
                        </div>
                        <div className="flex-1">
                            <h4 className="font-bold text-[#2C2C24] text-sm uppercase tracking-wider">{log.agent}</h4>
                            <p className="text-xs text-[#78786C] mt-1">{log.message}</p>
                        </div>
                        <div className="text-[10px] font-bold text-[#5D7052] bg-[#5D7052]/10 px-2 py-1 rounded-full uppercase">
                            {log.status}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default ResearchView;
